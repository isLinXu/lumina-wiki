"""
Lumina Wiki - Knowledge Compiler Core
将 raw/ 目录下的原始素材编译为 wiki/ 结构化知识库。

核心流程：
1. Scan: 扫描 raw/ 中未编译的文件
2. Summarize: 生成文档摘要
3. Entity Linking: 提取核心概念/实体
4. Wiki Patching: 增量更新或创建 Wiki 页面
5. Auto-linking: 在文中添加 [[wikilink]]
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .config import LuminaConfig, get_token, load_config
from .llm_client import LLMClient

console = Console()


class WikiCompiler:
    """知识编译器 - Lumina Wiki 的核心引擎。"""

    # 编译状态跟踪文件
    COMPILED_INDEX_FILE = "wiki/.compiled.json"

    def __init__(self, config: LuminaConfig | None = None):
        self.config = config or load_config()
        self.llm = LLMClient(self.config)
        self.raw_path = Path(self.config.ingest.raw_dir)
        self.wiki_path = Path(self.config.compiler.wiki_dir)
        self.concepts_path = Path(self.config.compiler.wiki_dir) / self.config.compiler.concepts_dir
        self.papers_path = Path(self.config.compiler.wiki_dir) / self.config.compiler.papers_dir
        self.notes_path = Path(self.config.compiler.wiki_dir) / self.config.compiler.notes_dir
        
        # 加载已编译索引
        self.compiled_index = self._load_compiled_index()

    def _load_compiled_index(self) -> dict:
        """加载已编译文件索引，避免重复编译。"""
        index_path = Path(self.COMPILED_INDEX_FILE)
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"compiled": {}, "concepts": {}, "last_run": None}

    def _save_compiled_index(self) -> None:
        """保存编译索引。"""
        index_path = Path(self.COMPILED_INDEX_FILE)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        self.compiled_index["last_run"] = datetime.now(timezone.utc).isoformat()
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self.compiled_index, f, ensure_ascii=False, indent=2)

    def scan_raw_files(self) -> list[Path]:
        """
        扫描 raw/ 目录中尚未编译的 .md 文件。
        """
        if not self.raw_path.exists():
            console.print("[yellow]⚠️  raw/ 目录不存在，暂无素材可编译。[/yellow]")
            return []

        all_md_files = list(self.raw_path.rglob("*.md"))
        
        # 过滤掉 .desc.md 文件（它们是辅助文件）
        source_files = [
            f for f in all_md_files 
            if not f.name.endswith(".desc.md") 
            and f.name.endswith(".md")
        ]

        # 排除已编译的文件
        uncompiled = []
        for f in source_files:
            rel = str(f.relative_to(self.raw_path))
            file_mtime = f.stat().st_mtime_ns
            compiled_mtime = self.compiled_index["compiled"].get(rel)
            
            if compiled_mtime is None or file_mtime > int(compiled_mtime):
                uncompiled.append(f)

        return uncompiled

    def get_existing_concepts(self) -> set[str]:
        """获取已有的概念页面名称集合。"""
        concepts: set[str] = set()
        if self.concepts_path.exists():
            for md_file in self.concepts_path.glob("*.md"):
                concepts.add(md_file.stem)
        # 也从索引加载
        concepts.update(self.compiled_index.get("concepts", {}).keys())
        return concepts

    async def compile_all(self, dry_run: bool = False) -> dict:
        """
        执行完整编译流程。
        返回编译统计信息。
        """
        uncompiled = self.scan_raw_files()

        if not uncompiled:
            console.print("[green]✅ 所有素材已编译完毕，无需更新。[/green]")
            return {"status": "up_to_date", "files_processed": 0}

        console.print(f"\n📚 发现 [bold]{len(uncompiled)}[/bold] 个待编译文件:\n")
        for f in uncompiled:
            rel = f.relative_to(self.raw_path)
            size = f.stat().st_size
            console.print(f"  📄 {rel} ({size:,} bytes)")

        if dry_run:
            return {"status": "dry_run", "files_pending": len(uncompiled)}

        stats = {
            "status": "success",
            "files_processed": 0,
            "pages_created": 0,
            "pages_updated": 0,
            "entities_extracted": 0,
            "errors": [],
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("编译中...", total=len(uncompiled))

            for raw_file in uncompiled:
                try:
                    result = await self.compile_single(raw_file)
                    stats["files_processed"] += 1
                    stats["pages_created"] += result.get("created", 0)
                    stats["pages_updated"] += result.get("updated", 0)
                    stats["entities_extracted"] += result.get("entities", 0)

                    # 更新索引
                    rel = str(raw_file.relative_to(self.raw_path))
                    self.compiled_index["compiled"][rel] = str(raw_file.stat().st_mtime_ns)

                except Exception as e:
                    error_msg = f"{raw_file.name}: {e}"
                    stats["errors"].append(error_msg)
                    console.print(f"[red]  ❌ 编译失败: {error_msg}[/red]")
                
                progress.advance(task)

        # 保存索引和概念注册表
        self._save_compiled_index()

        # 打印统计
        self._print_stats(stats)
        return stats

    async def compile_single(self, raw_file: Path) -> dict:
        """
        编译单个原始文件。

        Returns:
            包含 created, updated, entities 计数的字典
        """
        rel_path = raw_file.relative_to(self.raw_path)
        console.print(f"\n{'='*60}")
        console.print(f"🔧 编译: [bold]{rel_path}[/bold]")

        # 1. 读取原始内容
        content = raw_file.read_text(encoding="utf-8")
        metadata, body = self._parse_raw_markdown(content)

        # 2. 生成摘要
        summary = await self.llm.summarize(body)
        console.print(f"  📝 摘要已生成 ({len(summary)} 字)")

        # 3. 实体提取
        entities = await self.llm.extract_entities(body + "\n\n" + summary)
        console.print(f"  🏷️  发现 {len(entities)} 个实体")

        # 4. 判断文档类型并路由到对应目录
        doc_type = self._classify_document(metadata, body, entities)

        # 5. 创建/更新 Wiki 页面
        created_count, updated_count = await self._create_or_update_wiki_page(
            raw_file, metadata, body, summary, entities, doc_type
        )

        # 6. 为新发现的实体创建概念页
        concept_created = 0
        existing_concepts = self.get_existing_concepts()
        for entity in entities:
            name = entity.get("name", "")
            if name and name not in existing_concepts:
                await self._create_concept_page(entity, summary, body)
                existing_concepts.add(name)
                self.compiled_index.setdefault("concepts", {})[name] = {
                    "type": entity.get("type", "unknown"),
                    "source": str(rel_path),
                    "created": datetime.now(timezone.utc).isoformat(),
                }
                concept_created += 1

        if concept_created:
            console.print(f"  🆕 创建了 {concept_created} 个概念页面")

        return {
            "created": created_count + concept_created,
            "updated": updated_count,
            "entities": len(entities),
        }

    def _parse_raw_markdown(self, content: str) -> tuple[dict, str]:
        """
        解析 raw markdown 文件，分离 front matter 和正文。
        Returns: (metadata_dict, body_text)
        """
        metadata: dict = {}

        # 解析 YAML front matter
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if fm_match:
            fm_text, body = fm_match.group(1), fm_match.group(2)
            # 简单解析 YAML key: value
            for line in fm_text.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    # 尝试解析 JSON 值（如 labels 数组）
                    if v.startswith("[") or v.startswith("{"):
                        try:
                            v = json.loads(v)
                        except (json.JSONDecodeError, ValueError):
                            pass
                    metadata[k] = v
        else:
            body = content

        return metadata, body.strip()

    def _classify_document(
        self, metadata: dict, body: str, entities: list[dict]
    ) -> str:
        """判断文档类型，决定存储到哪个子目录。"""
        title_lower = metadata.get("title", "").lower()
        labels = metadata.get("labels", [])
        entity_types = [e.get("type", "") for e in entities]

        # 论文检测关键词
        paper_keywords = ["paper", "论文", "arxiv", "cvpr", "neurips", "icml", "iclr", "aaai", "emnlp"]
        is_paper = any(kw in title_lower for kw in paper_keywords) or "paper" in labels

        # 笔记检测
        note_keywords = ["笔记", "note", "学习", "learn", "reading", "阅读"]
        is_note = any(kw in title_lower for kw in note_keywords) or "note" in labels

        if is_paper:
            return "paper"
        elif is_note:
            return "note"
        elif any(t == "paper" for t in entity_types):
            return "paper"
        else:
            return "note"

    async def _create_or_update_wiki_page(
        self,
        raw_file: Path,
        metadata: dict,
        body: str,
        summary: str,
        entities: list[dict],
        doc_type: str,
    ) -> tuple[int, int]:
        """
        创建或增量更新 Wiki 页面。
        Returns: (created_count, updated_count)
        """
        # 选择输出目录
        if doc_type == "paper":
            output_dir = self.papers_path
        else:
            output_dir = self.notes_path

        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        title = metadata.get("title", "Untitled")
        safe_name = _slugify(title)
        output_file = output_dir / f"{safe_name}.md"

        exists = output_file.exists()

        # 构建页面内容
        page_content = self._build_wiki_page(
            metadata, body, summary, entities, exists
        )

        # 写入文件
        output_file.write_text(page_content, encoding="utf-8")

        if exists:
            console.print(f"  🔄 已更新: {output_file.relative_to(Path('.'))}")
            return (0, 1)
        else:
            console.print(f"  ✅ 已创建: {output_file.relative_to(Path('.'))}")
            return (1, 0)

    def _build_wiki_page(
        self,
        metadata: dict,
        original_body: str,
        summary: str,
        entities: list[dict],
        is_update: bool = False,
    ) -> str:
        """构建 Wiki 页面的 Markdown 内容。"""
        lines: list[str] = []
        timestamp = datetime.now().strftime(self.config.output.timestamp_format)

        # --- Front Matter ---
        if self.config.output.front_matter:
            lines.append("---")
            lines.append(f'title: "{metadata.get("title", "Untitled")}"')
            lines.append(f'author: {metadata.get("author", self.config.output.author)}')
            lines.append(f"created: {timestamp}")
            lines.append(f'source: {metadata.get("source", "")}')
            lines.append(f'issue_url: {metadata.get("url", "")}')
            
            if entities:
                tags = [e["name"] for e in entities]
                lines.append(f"tags: {json.dumps(tags, ensure_ascii=False)}")

            if is_update:
                lines.append("updated: " + timestamp)

            lines.append("---")
            lines.append("")

        # --- 标题 ---
        title = metadata.get("title", "Untitled")
        lines.append(f"# {title}\n")

        # --- 摘要 ---
        lines.append("> 💡 **摘要**")
        lines.append(f"> {summary}")
        lines.append("")

        # --- 元数据栏 ---
        lines.append("| 属性 | 值 |")
        lines.append("|------|-----|")
        if metadata.get("author"):
            lines.append(f"| 投喂者 | @{metadata['author']} |")
        if metadata.get("issue_number"):
            lines.append(f"| 来源 Issue | [#{metadata['issue_number']}](metadata.get('url', '')) |")
        lines.append(f"| 编译时间 | {timestamp} |")
        if entities:
            entity_links = " | ".join(f"[[{e['name']}]]" for e in entities[:10])
            lines.append(f"| 关键实体 | {entity_links} |")
        lines.append("")

        # --- 正文（自动 wikilink）---
        lines.append("## 详细内容\n")
        
        processed_body = original_body
        if self.config.compiler.auto_link:
            processed_body = self._auto_link(original_body, entities)
        
        lines.append(processed_body)
        lines.append("")

        # --- 相关实体 ---
        if entities:
            lines.append("## 相关实体\n")
            for entity in entities:
                name = entity.get("name", "")
                etype = entity.get("type", "unknown")
                confidence = entity.get("confidence", 0)
                lines.append(f"- **{name}** (`{etype}`) — 置信度: {confidence:.0%}")
            lines.append("")

        # --- 反向链接区域（Obsidian 兼容）---
        lines.append("---\n")
        lines.append("**🔗 Lumina Wiki** | [[wiki/Home]] | 自动编译于 " + timestamp)

        return "\n".join(lines)

    async def _create_concept_page(
        self, entity: dict, context_summary: str, source_text: str
    ) -> None:
        """为新发现的概念创建独立页面。"""
        name = entity.get("name", "Unknown")
        etype = entity.get("type", "concept")

        self.concepts_path.mkdir(parents=True, exist_ok=True)
        safe_name = _slugify(name)
        page_path = self.concepts_path / f"{safe_name}.md"

        timestamp = datetime.now().strftime(self.config.output.timestamp_format)

        # 使用 LLM 生成初始概念定义
        definition_prompt = f"""你是一个知识管理助手。请为以下学术/技术概念创建一个简洁的百科条目页面。

概念名称: {name}
类型: {etype}
上下文（来源文档摘要）: {context_summary[:500]}

返回格式：
- 第一段：一句话定义
- 第二段：详细解释（2-3句话）
- 第三段：相关方向/应用场景
- 不要使用 markdown 标题，用段落即可
"""

        definition = await self.llm.chat([{"role": "user", "content": definition_prompt}])

        content = f"""---
title: "{name}"
type: {etype}
created: {timestamp}
status: seed
---

# {name}

{definition}

## 来源
> 首次发现于 Lumina Wiki 编译过程。

## 相关
<!-- 反向链接将由后续编译自动补充 -->
"""

        page_path.write_text(content, encoding="utf-8")
        console.print(f"  🆕 概念页: {page_path.relative_to(Path('.'))}")

    def _auto_link(self, text: str, entities: list[dict]) -> str:
        """
        在正文中为已知概念自动添加 [[wikilink]] 语法。
        使用最长匹配优先策略避免冲突。
        """
        # 获取所有已知概念（包括已有页面中的）
        known_concepts = self.get_existing_concepts()
        for e in entities:
            known_concepts.add(e.get("name", ""))

        # 按长度降序排列，确保长词优先匹配
        sorted_concepts = sorted(
            [c for c in known_concepts if len(c) >= self.config.linking.min_concept_length],
            key=len,
            reverse=True,
        )

        result = text
        linked: set[str] = set()  # 避免同一概念重复加链接

        for concept in sorted_concepts:
            if concept in linked:
                continue

            # 构建匹配模式（区分大小写或不区分）
            flags = 0 if self.config.linking.case_sensitive else re.IGNORECASE

            # 匹配不在 [[]] 内的独立概念词
            # 使用 word boundary 和 negative lookahead 避免重复链接
            pattern = rf"(?<![\[\|])(?<!\w){re.escape(concept)}(?!\w)(?![^\[]*\]\])"

            replacement = f"[[{concept}]]"

            if re.search(pattern, result, flags):
                result = re.sub(pattern, replacement, result, flags=flags)
                linked.add(concept)

        return result

    def _print_stats(self, stats: dict) -> None:
        """打印编译统计信息。"""
        console.print(f"\n{'='*60}")
        console.print(f"[bold green]✅ 编译完成！[/bold green]\n")
        console.print(f"  文件处理: {stats['files_processed']}")
        console.print(f"  新建页面: {stats.get('pages_created', 0)}")
        console.print(f"  更新页面: {stats.get('pages_updated', 0)}")
        console.print(f"  实体提取: {stats.get('entities_extracted', 0)}")

        if stats.get("errors"):
            console.print(f"\n[red]  错误 ({len(stats['errors'])}):[/red]")
            for err in stats["errors"]:
                console.print(f"    • {err}")

        console.print()


def _slugify(text: str) -> str:
    """将文本转换为安全文件名。"""
    from slugify import slugify
    result = slugify(text, separator="_", lowercase=False)
    return result[:80] if len(result) > 80 else result


# ─── CLI 入口 ──────────────────────────────────────────────────────────────
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Lumina Wiki - Knowledge Compiler")
    parser.add_argument("--token", help="GitHub Token（或设置 GITHUB_TOKEN）")
    parser.add_argument("--config", "-c", help="lumina.toml 路径")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不编译")
    parser.add_argument("--file", "-f", help="指定单个文件编译")
    args = parser.parse_args()

    if args.token:
        os.environ["GITHUB_TOKEN"] = args.token

    config = load_config(args.config)
    compiler = WikiCompiler(config)

    if args.file:
        target = Path(args.file)
        if not target.exists():
            console.print(f"[red]文件不存在: {target}[/red]")
            sys.exit(1)
        result = await compiler.compile_single(target)
        console.print(f"\n结果: {result}")
    else:
        stats = await compiler.compile_all(dry_run=args.dry_run)
        if not args.dry_run:
            # 输出统计为 JSON（供 GitHub Actions 使用）
            stats_path = Path("wiki/.compile-stats.json")
            stats_path.parent.mkdir(exist_ok=True)
            stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
