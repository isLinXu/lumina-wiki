"""
Lumina Wiki - Enhanced 5-Pass Compiler Pipeline
参考 sage-wiki 的架构设计，实现完整的 5 遍编译流水线：
  Pass 1: Diff    - 差异检测（增量编译）
  Pass 2: Summarize - 摘要生成
  Pass 3: Extract   - 概念/实体提取
  Pass 4: Write     - 文章撰写（增量更新）
  Pass 5: Post      - 后处理（索引/日志/反向链接）
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn,
    MofNCompleteColumn, TimeElapsedColumn,
)

from .config import LuminaConfig, load_config
from .llm_client import LLMClient

console = Console()


# ─── 数据结构 ────────────────────────────────────────────────────────

@dataclass
class DiffResult:
    """Pass 1 输出：差异检测结果。"""
    added: list[Path] = field(default_factory=list)
    modified: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)

    @property
    def needs_processing(self) -> list[Path]:
        return self.added + self.modified


@dataclass
class SummaryResult:
    """Pass 2 输出：摘要结果。"""
    source_file: Path
    title: str = ""
    summary_text: str = ""
    key_points: list[str] = field(default_factory=list)
    authors: str = ""
    methodology: str = ""
    results: str = ""
    limitations: str = ""
    doc_type: str = "note"  # paper | note | other


@dataclass
class ExtractResult:
    """Pass 3 输出：实体提取结果。"""
    entities: list[dict] = field(default_factory=list)
    # entities: [{"name": "...", "type": "algorithm|model|paper|...|other", "confidence": 0.9}]


@dataclass
class ArticleResult:
    """Pass 4 输出：文章写入结果。"""
    output_path: Path
    created: bool = False  # True=新建, False=更新
    concept_pages_created: int = 0
    concept_pages_updated: int = 0


@dataclass
class CompileStats:
    """完整编译统计。"""
    added: int = 0
    modified: int = 0
    removed: int = 0
    summarized: int = 0
    concepts_extracted: int = 0
    new_concepts: int = 0
    articles_written: int = 0
    errors: int = 0
    duration_seconds: float = 0.0

    def __str__(self) -> str:
        return (
            f"+{self.added} added, ~{self.modified} modified, "
            f"-{self.removed} removed, {self.summarized} summarized, "
            f"{self.concepts_extracted} concepts ({self.new_concepts} new), "
            f"{self.articles_written} articles"
            + (f", {self.errors} errors" if self.errors else "")
        )


# ─── 核心编译器 ──────────────────────────────────────────────────────

class CompilerPipeline:
    """
    Lumina Wiki 5-Pass 编译流水线。
    
    设计参考 sage-wiki (xoai/sage-wiki) 的架构，适配 Python/GitHub-Native 场景。
    """

    COMPILED_INDEX_FILE = "wiki/.compiled.json"
    BACKLINK_INDEX_FILE = "wiki/.backlinks.json"
    LOG_FILE = "wiki/log.md"
    INDEX_FILE = "wiki/index.md"

    def __init__(self, config: LuminaConfig | None = None):
        self.config = config or load_config()
        self.llm = LLMClient(self.config)
        
        # 路径
        self.raw_path = Path(self.config.ingest.raw_dir)
        self.wiki_path = Path(self.config.compiler.wiki_dir)
        self.concepts_path = self.wiki_path / self.config.compiler.concepts_dir
        self.papers_path = self.wiki_path / self.config.compiler.papers_dir
        self.notes_path = self.wiki_path / self.config.compiler.notes_dir
        self.comparisons_path = self.wiki_path / "comparisons"

        # 索引状态
        self._compiled_index = self._load_index()
        self._backlink_index = {}
        self._all_concepts: set[str] = set()

    # ═══════════════════════════════════════════════════════════════════
    # 公开接口
    # ═══════════════════════════════════════════════════════════════════

    async def compile(self, dry_run: bool = False, fresh: bool = False) -> CompileStats:
        """执行完整的 5-pass 编译流水线。"""
        import time
        start_time = time.time()

        console.print(Panel(
            "[bold cyan]🌙 Lumina Wiki — 5-Pass Compiler Pipeline[/bold cyan]\n"
            "[dim]Reference: sage-wiki architecture (xoai/sage-wiki)[/dim]\n"
            "[dim]Idea: Karpathy's LLM Wiki pattern[/dim]",
            border_style="cyan",
        ))

        stats = CompileStats()

        if fresh:
            console.print("[yellow]⚠️  Fresh mode: 忽略已有索引，完全重新编译[/yellow]")
            self._compiled_index = {"compiled": {}, "concepts": {}, "last_run": None}

        # ── Pass 1: Diff ──────────────────────────────────────────
        console.print("\n[bold]▶ Pass 1/5: Diff[/bold] — 扫描变更...")
        diff_result = await self.pass1_diff()
        stats.added = len(diff_result.added)
        stats.modified = len(diff_result.modified)
        stats.removed = len(diff_result.removed)

        pending = diff_result.needs_processing
        if not pending:
            console.print("[green]✅ 所有素材已是最新，无需编译。[/green]")
            self._save_stats(stats, start_time)
            return stats

        console.print(f"   📊 {len(pending)} 个文件待处理 (+{stats.added} ~{stats.modified} -{stats.removed})")

        if dry_run:
            for f in pending:
                rel = f.relative_to(self.raw_path)
                console.print(f"   📄 {rel}")
            return stats

        # 加载已有概念集合（用于 wikilink）
        self._refresh_concept_set()

        # ── Pass 2-5: 对每个文件执行 ─────────────────────────────
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style="cyan"),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            main_task = progress.add_task("编译中...", total=len(pending))

            for raw_file in pending:
                rel = raw_file.relative_to(self.raw_path)
                
                try:
                    # Pass 2: Summarize
                    progress.update(main_task, description=f"📝 摘要: {rel}")
                    summary = await self.pass2_summarize(raw_file)
                    stats.summarized += 1

                    # Pass 3: Extract Concepts
                    progress.update(main_task, description=f"🏷️  提取: {rel}")
                    extract = await self.pass3_extract(raw_file, summary)
                    stats.concepts_extracted += len(extract.entities)

                    # Pass 4: Write Articles
                    progress.update(main_task, description=f"✍️  撰写: {rel}")
                    article = await self.pass4_write(raw_file, summary, extract)
                    stats.articles_written += 1
                    if article.created:
                        stats.added += 1  # 或细分
                    stats.new_concepts += article.concept_pages_created

                    # 更新编译索引
                    self._mark_compiled(raw_file)

                    # 实时注册新概念到概念集
                    for e in extract.entities:
                        name = e.get("name", "")
                        if name and name not in self._all_concepts:
                            self._all_concepts.add(name)

                except Exception as e:
                    stats.errors += 1
                    console.print(f"[red]  ❌ {rel}: {e}[/red]")

                progress.advance(main_task)

        # ── Pass 5: Post-Process ─────────────────────────────────
        console.print("\n[bold]▶ Pass 5/5: Post-Process[/bold] — 后处理...")
        await self.pass5_postprocess(stats)

        stats.duration_seconds = time.time() - start_time
        self._save_stats(stats, start_time)

        # 最终报告
        self._print_final_report(stats)
        return stats

    async def re_extract(self) -> dict:
        """从已有摘要重新运行 Pass 3+4（不重新摘要）。"""
        # 找到所有已编译的源文件记录
        to_reextract = []
        for rel, mtime in self._compiled_index.get("compiled", {}).items():
            src = self.raw_path / rel
            if src.exists():
                to_reextract.append(src)

        stats = CompileStats()
        self._refresh_concept_set()

        for raw_file in to_reextract:
            try:
                # 从缓存或重新生成摘要
                summary = SummaryResult(source_file=raw_file)
                summary.title = raw_file.stem.replace("_", " ").title()

                extract = await self.pass3_extract(raw_file, summary)
                stats.concepts_extracted += len(extract.entities)

                article = await self.pass4_write(raw_file, summary, extract)
                stats.articles_written += 1
                stats.new_concepts += article.concept_pages_created
            except Exception as e:
                stats.errors += 1

        await self.pass5_postprocess(stats)
        return {"concepts_extracted": stats.concepts_extracted,
                "articles_written": stats.articles_written,
                "errors": stats.errors}

    # ═══════════════════════════════════════════════════════════════════
    # Pass 1: Diff — 差异检测
    # ═══════════════════════════════════════════════════════════════════

    async def pass1_diff(self) -> DiffResult:
        """扫描 raw/ 目录，与已编译索引对比，找出新增/修改/删除的文件。"""
        result = DiffResult()

        if not self.raw_path.exists():
            return result

        current_files: dict[Path, int] = {}
        for md_file in self.raw_path.rglob("*.md"):
            # 跳过辅助文件
            if md_file.name.endswith(".desc.md") or md_file.name.startswith("."):
                continue
            rel = md_file.relative_to(self.raw_path)
            current_files[rel] = md_file.stat().st_mtime_ns

        compiled = self._compiled_index.get("compiled", {})

        for rel, mtime in sorted(current_files.items()):
            abs_path = self.raw_path / rel
            prev_mtime = compiled.get(str(rel))
            
            if prev_mtime is None:
                result.added.append(abs_path)
            elif mtime > int(prev_mtime):
                result.modified.append(abs_path)
            else:
                result.unchanged.append(abs_path)

        # 检测删除的文件（可选：清理对应的 wiki 页面）
        for rel in list(compiled.keys()):
            if rel not in current_files and not rel.startswith("."):
                removed_abs = self.raw_path / rel
                if not removed_abs.exists():
                    result.removed.append(removed_abs)

        return result

    # ═══════════════════════════════════════════════════════════════════
    # Pass 2: Summarize — 摘要生成
    # ═══════════════════════════════════════════════════════════════════

    async def pass2_summarize(self, raw_file: Path) -> SummaryResult:
        """对原始文件生成结构化摘要。"""
        metadata, body = self._parse_raw_markdown(raw_file.read_text(encoding="utf-8"))
        title = metadata.get("title", raw_file.stem.replace("_", " ").title())

        prompt = f"""你是一个学术/技术知识提炼专家。请对以下内容生成结构化摘要。

## 输出格式（严格 JSON）
```json
{{
  "summary": "一段话概括核心内容（200-300字，中文）",
  "key_points": ["要点1", "要点2", "要点3", "要点4", "要点5"],
  "authors": "作者（如有）",
  "methodology": "使用的方法/技术路线",
  "results": "关键结果/数据",
  "limitations": "局限性",
  "doc_type": "paper|note|other"
}}
```

## 原始内容
标题：{title}

{body[:6000]}
"""

        try:
            result = await self.llm.extract_json(
                [{"role": "user", "content": prompt}],
                system_prompt="你是 Lumina Wiki 的摘要生成器。输出严格的 JSON 格式，不要添加任何额外文字。",
            )
        except Exception:
            # 降级：如果 JSON 解析失败，用纯文本摘要
            summary_text = await self.llm.summarize(body)
            result = {
                "summary": summary_text,
                "key_points": [],
                "authors": "",
                "methodology": "",
                "results": "",
                "limitations": "",
                "doc_type": "note",
            }

        return SummaryResult(
            source_file=raw_file,
            title=title,
            summary_text=result.get("summary", ""),
            key_points=result.get("key_points", []),
            authors=result.get("authors", ""),
            methodology=result.get("methodology", ""),
            results=result.get("results", ""),
            limitations=result.get("limitations", ""),
            doc_type=result.get("doc_type", "note"),
        )

    # ═══════════════════════════════════════════════════════════════════
    # Pass 3: Extract — 概念/实体提取
    # ═══════════════════════════════════════════════════════════════════

    async def pass3_extract(self, raw_file: Path, summary: SummaryResult) -> ExtractResult:
        """从原文+摘要中提取核心实体和概念。"""
        # 组合文本用于提取
        combined = f"标题: {summary.title}\n"
        combined += f"摘要: {summary.summary_text}\n"
        combined += f"要点: {' | '.join(summary.key_points)}\n"
        
        # 也读取部分原文
        _, body = self._parse_raw_markdown(raw_file.read_text(encoding="utf-8"))
        combined += f"\n原文前3000字:\n{body[:3000]}"

        # 已有概念提示（避免重复提取）
        existing_hint = ""
        if self._all_concepts:
            sample = sorted(list(self._all_concepts))[:20]
            existing_hint = f"以下概念已经存在，不需要重复提取：{', '.join(sample)}\n"

        prompt = f"""从以下学术/技术文档中提取核心概念和实体。

{existing_hint}
## 分类体系
- algorithm: 具体算法（如 FlashAttention, RMSNorm, MoE Routing）
- model: 模型架构（如 GPT-4, Llama, Mixtral, DeepSeek）
- paper: 论文（作为引用实体）
- method: 训练技巧/方法（如 LoRA, RLHF, KV-Cache）
- concept: 抽象概念（如 Scaling Law, Emergence, Grokking）
- metric: 评估指标（如 mAP, BLEU, Perplexity, FLOPs）
- dataset: 数据集（如 ImageNet, C4, The Pile）
- person: 研究者
- tool: 工具/框架（如 PyTorch, vLLM, Triton）
- other: 其他

## 输出格式（严格 JSON）
```json
{{"entities": [{{"name": "概念名", "type": "类型", "confidence": 0.95}}]}}
```

只提取重要的、有独立页面价值的实体。
过滤掉过于通用的词（如"深度学习"、"神经网络"，除非有特定上下文）。
置信度 < 0.7 的不要包含。

## 文档内容
{combined}
"""

        try:
            result = await self.llm.extract_json([{"role": "user", "content": prompt}])
            entities = result.get("entities", [])
            
            # 过滤低置信度
            threshold = self.config.compiler.entity_confidence
            entities = [e for e in entities if e.get("confidence", 0) >= threshold]
            
            # 过滤已存在的概念（降低噪声）
            entities = [e for e in entities 
                       if e.get("name", "") not in self._all_concepts 
                       or e.get("confidence", 0) > 0.9]
            
            return ExtractResult(entities=entities)
        except Exception as e:
            console.print(f"[yellow]  ⚠️ 实体提取失败({raw_file.name}): {e}[/yellow]")
            return ExtractResult(entities=[])

    # ═══════════════════════════════════════════════════════════════════
    # Pass 4: Write — 文章撰写（增量更新策略）
    # ═══════════════════════════════════════════════════════════════════

    async def pass4_write(
        self,
        raw_file: Path,
        summary: SummaryResult,
        extract: ExtractResult,
    ) -> ArticleResult:
        """基于摘要和实体，创建或增量更新 Wiki 页面。"""
        # 确定目标目录
        doc_type = summary.doc_type
        if doc_type == "paper":
            output_dir = self.papers_path
        else:
            output_dir = self.notes_path
        
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_name = _slugify(summary.title)
        output_path = output_dir / f"{safe_name}.md"
        exists = output_path.exists()

        # 构建页面内容
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rel_source = raw_file.relative_to(Path("."))

        if exists:
            # 增量更新模式：追加新信息块
            content = output_path.read_text(encoding="utf-8")
            update_block = (
                f"\n\n---\n\n**▸ 更新于 {timestamp}**\n"
                f"> 来源: `{rel_source}`\n\n"
            )
            if summary.summary_text:
                update_block += f"**补充摘要**: {summary.summary_text}\n\n"
            if extract.entities:
                new_entities = [e["name"] for e in extract.entities]
                update_block += f"**相关实体**: {' | '.join(f'[[{e}]]' for e in new_entities)}\n"
            
            content += update_block
            created_flag = False
        else:
            # 新建页面
            content = self._build_article_page(summary, extract, timestamp, rel_source, doc_type)
            created_flag = True

        # 自动 wikilink
        if self.config.compiler.auto_link and extract.entities:
            content = self._auto_link(content, extract.entities)

        output_path.write_text(content, encoding="utf-8")

        # 为新概念创建/更新概念页
        concepts_created = 0
        concepts_updated = 0
        for entity in extract.entities:
            name = entity.get("name", "")
            if not name:
                continue
            
            concept_existed = name in self._all_concepts
            await self._upsert_concept_page(entity, summary, raw_file)
            
            if concept_existed:
                concepts_updated += 1
            else:
                concepts_created += 1
                self._all_concepts.add(name)

        status_icon = "✅ 新建" if created_flag else "🔄 更新"
        console.print(f"  {status_icon}: {output_path.relative_to(Path('.'))}")

        return ArticleResult(
            output_path=output_path,
            created=created_flag,
            concept_pages_created=concepts_created,
            concept_pages_updated=concepts_updated,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Pass 5: Post-Process — 后处理
    # ═══════════════════════════════════════════════════════════════════

    async def pass5_postprocess(self, stats: CompileStats) -> None:
        """后处理：更新索引、日志、反向链接。"""
        # 1. 保存编译状态索引
        self._save_compiled_index()

        # 2. 更新全局 index.md
        self._update_global_index()

        # 3. 更新反向链接索引
        from .linker import AutoLinker
        linker = AutoLinker(self.config)
        self._backlink_index = linker.scan_all_wikilinks()

        # 4. 追加编译日志
        self._append_log(stats)

        # 5. 更新 Home.md 统计
        self._update_home_stats(stats)

        console.print("  💾 索引已保存 | 日志已追加 | 反向链接已更新")

    # ═══════════════════════════════════════════════════════════════════
    # 内部工具方法
    # ═══════════════════════════════════════════════════════════════════

    def _parse_raw_markdown(self, content: str) -> tuple[dict, str]:
        """解析 raw markdown，分离 front matter 和正文。"""
        metadata: dict = {}
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if fm_match:
            fm_text, body = fm_match.group(1), fm_match.group(2)
            for line in fm_text.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip().strip('"').strip("'")
                    if v.startswith("[") or v.startswith("{"):
                        try:
                            v = json.loads(v)
                        except (json.JSONDecodeError, ValueError):
                            pass
                    metadata[k] = v
        else:
            body = content
        return metadata, body.strip()

    def _build_article_page(
        self,
        summary: SummaryResult,
        extract: ExtractResult,
        timestamp: str,
        source_rel: str,
        doc_type: str,
    ) -> str:
        """构建新的 Wiki 文章页面（遵循 CLAUDE.md Schema）。"""
        lines = []

        # Front Matter
        lines.append("---")
        lines.append(f'title: "{summary.title}"')
        lines.append(f"type: {doc_type}")
        lines.append(f"created: {timestamp}")
        lines.append(f"source: {source_rel}")
        lines.append(f'status: seed')

        tags = [e["name"] for e in extract.entities[:15]]
        if tags:
            lines.append(f"tags: {json.dumps(tags, ensure_ascii=False)}")

        if summary.authors:
            lines.append(f'author: "{summary.authors}"')

        lines.append("---")
        lines.append("")
        lines.append(f"# {summary.title}")
        lines.append("")

        # 摘要框
        lines.append("> 💡 **摘要**")
        lines.append(f"> {summary.summary_text}")
        lines.append("")

        # 元数据表格
        lines.append("| 属性 | 值 |")
        lines.append("|------|-----|")
        if summary.authors:
            lines.append(f"| 作者 | {summary.authors} |")
        if summary.methodology:
            lines.append(f"| 方法论 | {summary.methodology} |")
        if summary.results:
            lines.append(f"| 关键结果 | {summary.results} |")
        lines.append(f"| 类型 | {doc_type} |")
        lines.append(f"| 来源 | `{source_rel}` |")
        lines.append(f"| 编译时间 | {timestamp[:10]} |")
        lines.append("")

        # 关键要点
        if summary.key_points:
            lines.append("## 关键要点\n")
            for i, point in enumerate(summary.key_points, 1):
                lines.append(f"{i}. {point}")
            lines.append("")

        # 方法论
        if summary.methodology:
            lines.append("## 方法论\n")
            lines.append(f"{summary.methodology}\n")

        # 结果
        if summary.results:
            lines.append("## 关键结果\n")
            lines.append(f"{summary.results}\n")

        # 局限性
        if summary.limitations:
            lines.append("## 局限性\n")
            lines.append(f"{summary.limitations}\n")

        # 相关实体
        if extract.entities:
            lines.append("## 相关实体\n")
            for entity in extract.entities:
                name = entity.get("name", "")
                etype = entity.get("type", "unknown")
                conf = entity.get("confidence", 0)
                lines.append(f"- **[[{name}]]** (`{etype}`) — 置信度: {conf:.0%}")
            lines.append("")

        # 底部元信息
        lines.append("---\n")
        lines.append(f"*由 **Lumina Compiler** 于 {timestamp} 自动生成*")
        lines.append(f"*来源: `{source_rel}`*")

        return "\n".join(lines)

    async def _upsert_concept_page(
        self, entity: dict, summary: SummaryResult, raw_file: Path
    ) -> None:
        """创建或更新概念页（Upsert = Update or Insert）。"""
        name = entity.get("name", "Unknown")
        etype = entity.get("type", "concept")

        self.concepts_path.mkdir(parents=True, exist_ok=True)
        safe_name = _slugify(name)
        page_path = self.concepts_path / f"{safe_name}.md"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if page_path.exists():
            # 增量更新：在末尾追加来源引用
            existing = page_path.read_text(encoding="utf-8")
            rel_src = raw_file.relative_to(Path("."))
            append_block = (
                f"\n\n### 来源补充 ({timestamp})\n"
                f"- 发现于: [[{_slugify(summary.title)}]] (`{rel_src}`)\n"
                f"- 上下文: {summary.summary_text[:200]}...\n"
            )
            # 如果还没有这个来源就追加
            if _slugify(summary.title) not in existing:
                page_path.write_text(existing + append_block, encoding="utf-8")
        else:
            # 新建概念页 —— 使用 LLM 定义
            definition_prompt = f"""为以下技术/学术概念写一个简洁的百科条目。

概念名称: {name}
类型: {etype}
首次发现于: {summary.title}

要求（中文）：
1. 第一行：一句话定义（用 **加粗**
2. 第二段：详细解释（2-3句话，通俗易懂但专业）
3. 第三段：典型应用场景或相关工作
不要使用markdown标题符号(#)，直接用段落即可。
"""
            try:
                definition = await self.llm.chat([{"role": "user", "content": definition_prompt}])
            except Exception:
                definition = f"**{name}** 是一个 {etype} 类型的概念。首次发现于「{summary.title}」。\n\n详细定义待后续编译充实。"

            content = f"""---
title: "{name}"
type: {etype}
created: {timestamp}
status: seed
first_seen_in: {_slugify(summary.title)}
tags: [{etype}]
---

# {name}

{definition}

## 来源
- [[{_slugify(summary.title)}]] — 首次发现

---
*由 Lumina Compiler 自动创建*
"""
            page_path.write_text(content, encoding="utf-8")

    def _auto_link(self, text: str, entities: list[dict]) -> str:
        """自动为已知概念添加 [[wikilink]]（最长匹配优先）。"""
        all_known = self._all_concepts | {e.get("name", "") for e in entities}
        sorted_concepts = sorted(
            [c for c in all_known 
             if len(c) >= self.config.linking.min_concept_length],
            key=len, reverse=True,
        )

        result = text
        linked: set[str] = set()

        for concept in sorted_concepts:
            if concept in linked or not concept:
                continue
            pattern = rf"(?<![\[\|])(?<!\w){re.escape(concept)}(?!\w)(?![^\[]*\]\])"
            replacement = f"[[{concept}]]"
            if re.search(pattern, result, re.IGNORECASE):
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
                linked.add(concept)

        return result

    def _refresh_concept_set(self) -> None:
        """刷新内存中的已知概念集合。"""
        self._all_concepts = set()
        if self.concepts_path.exists():
            for md in self.concepts_path.glob("*.md"):
                self._all_concepts.add(md.stem)
        #也从索引中加载
        self._all_concepts.update(self._compiled_index.get("concepts", {}).keys())

    def _mark_compiled(self, raw_file: Path) -> None:
        """标记文件为已编译。"""
        rel = str(raw_file.relative_to(self.raw_path))
        self._compiled_index.setdefault("compiled", {})[rel] = str(raw_file.stat().st_mtime_ns)

    # ─── Index I/O ──────────────────────────────────────────────────

    def _load_index(self) -> dict:
        idx_path = Path(self.COMPILED_INDEX_FILE)
        if idx_path.exists():
            try:
                return json.loads(idx_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                return {"compiled": {}, "concepts": {}, "last_run": None}
        return {"compiled": {}, "concepts": {}, "last_run": None}

    def _save_compiled_index(self) -> None:
        path = Path(self.COMPILED_INDEX_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._compiled_index["last_run"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(self._compiled_index, ensure_ascii=False, indent=2), encoding="utf-8")

    def _update_global_index(self) -> None:
        """更新 wiki/index.md 全局实体索引。"""
        lines = ["# Lumina Wiki — 全局索引\n"]
        lines.append("> 由 Lumina Compiler 自动维护 | 最后更新: "
                     f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")
        
        # 按类型分组显示所有概念页
        type_labels = {
            "algorithm": "🧮 算法",
            "model": "🤖 模型",
            "paper": "📄 论文",
            "method": "⚙️ 方法",
            "concept": "💡 概念",
            "metric": "📏 指标",
            "dataset": "📊 数据集",
            "person": "👤 人物",
            "tool": "🛠️ 工具",
            "other": "📦 其他",
        }

        by_type: dict[str, list[str]] = {}

        # 收集所有 wiki 页面
        for subdir in [self.concepts_path, self.papers_path, self.notes_path]:
            if subdir.exists():
                for md in sorted(subdir.rglob("*.md")):
                    name = md.stem
                    # 尝试读取 type
                    rel_subdir = subdir.name
                    if rel_subdir == "concepts":
                        by_type.setdefault("concept", []).append(f"[[{name}]]")
                    elif rel_subdir == "papers":
                        by_type.setdefault("paper", []).append(f"[[{name}]]")
                    else:
                        by_type.setdefault("note", []).append(f"[[{name}]]")

        for etype, label in type_labels.items():
            items = by_type.get(etype, [])
            if items:
                lines.append(f"### {label} ({len(items)})\n")
                # 分列显示
                cols = 3
                for i in range(0, len(items), cols):
                    row = items[i:i+cols]
                    lines.append(" | ".join(row))
                lines.append("")

        Path(self.INDEX_FILE).write_text("\n".join(lines), encoding="utf-8")

    def _append_log(self, stats: CompileStats) -> None:
        """追加编译日志到 wiki/log.md。"""
        now = datetime.now(timezone.utc)
        entry = f"""\n## [{now.strftime('%Y-%m-%d %H:%M:%S')} UTC]

### 统计
| 指标 | 数值 |
|------|------|
| 新增 | {stats.added} |
| 修改 | {stats.modified} |
| 删除 | {stats.removed} |
| 摘要生成 | {stats.summarized} |
| 概念提取 | {stats.concepts_extracted} (新: {stats.new_concepts}) |
| 文章撰写 | {stats.articles_written} |
| 错误 | {stats.errors} |
| 耗时 | {stats.duration_seconds:.1f}s |

### 健康度
<!-- 由 linter 计算 -->

---
"""
        log_path = Path(self.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            existing = log_path.read_text(encoding="utf-8")
            log_path.write_text(existing + entry, encoding="utf-8")
        else:
            header = "# Lumina Wiki — 编译日志\n\n> 每次编译自动追加一条记录。\n\n"
            log_path.write_text(header + entry, encoding="utf-8")

    def _update_home_stats(self, stats: CompileStats) -> None:
        """更新 Home.md 的统计数据。"""
        home_path = self.wiki_path / "Home.md"
        if not home_path.exists():
            return

        content = home_path.read_text(encoding="utf-8")
        # 统计当前总页面数
        total_pages = 0
        concept_count = 0
        for d in [self.concepts_path, self.papers_path, self.notes_path]:
            if d.exists():
                total_pages += len(list(d.glob("*.md")))
                if d == self.concepts_path:
                    concept_count = len(list(d.glob("*.md")))

        new_stats = f"""| 总页面数 | {total_pages} |
| 概念数 | {concept_count} |
| 健康度 | -- |
| 最后编译 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC |"""

        # 替换统计区域
        import re
        pattern = r"\| 总页面数 \|.*?\|\n(?:\|.*?\|\n)*"
        if "| 总页面数 |" in content:
            content = re.sub(r"(\| 总页面数 \|.*\|(?:\n\|.*\|)*?)", new_stats + "\n", content)
        else:
            content = content.rstrip() + "\n\n" + new_stats + "\n"

        home_path.write_text(content, encoding="utf-8")

    def _save_stats(self, stats: CompileStats, start_time: float) -> None:
        """保存编译统计为 JSON。"""
        stats_path = self.wiki_path / ".compile-stats.json"
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "added": stats.added,
            "modified": stats.modified,
            "removed": stats.removed,
            "summarized": stats.summarized,
            "concepts_extracted": stats.concepts_extracted,
            "new_concepts": stats.new_concepts,
            "articles_written": stats.articles_written,
            "errors": stats.errors,
            "duration_seconds": round(stats.duration_seconds, 2),
        }
        stats_path.write_text(json.dumps(stats_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    def _print_final_report(self, stats: CompileStats) -> None:
        """打印最终编译报告面板。"""
        panel_content = f"""\
[bold green]✅ 编译完成！[/bold green]

```
{stats}
```

耗时: **{stats.duration_seconds:.1f}s**
{"❌ 包含错误" if stats.errors else ""}
"""
        console.print(Panel(panel_content, title="Lumina Compiler Report", border_style="green"))


def _slugify(text: str) -> str:
    from slugify import slugify
    return slugify(text, separator="_", lowercase=False)[:80]
