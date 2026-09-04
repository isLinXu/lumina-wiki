"""
Lumina Wiki - Knowledge Linter & Health Check
定期扫描知识库，发现冲突、断链、空隙，并生成健康度报告。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import load_config, LuminaConfig
from .linker import find_broken_links, AutoLinker

console = Console()


class KnowledgeLinter:
    """知识库体检工具。"""

    def __init__(self, config: LuminaConfig | None = None):
        self.config = config or load_config()
        self.wiki_path = Path(self.config.compiler.wiki_dir)

    async def run_full_check(self) -> dict:
        """执行完整体检，返回报告。"""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "wiki_path": str(self.wiki_path),
            "checks": {},
            "health_score": 0,
            "suggestions": [],
        }

        console.print("\n[bold cyan]🩺 Lumina Wiki 知识体检[/bold cyan]\n")

        # 1. 断链检测
        broken = self._check_broken_links()
        report["checks"]["broken_links"] = {"count": len(broken), "items": broken[:20]}
        
        if broken:
            console.print(f"[red]  🔗 断链: {len(broken)} 个[/red]")
            for b in broken[:10]:
                console.print(f"     {b['source']}:{b['line']} → [[{b['link']}]]")
        else:
            console.print("[green]  ✅ 无断链[/green]")

        # 2. 孤儿页面检测（没有任何页面链接到它）
        orphans = self._check_orphan_pages()
        report["checks"]["orphan_pages"] = {"count": len(orphans), "items": orphans}

        if orphans:
            console.print(f"[yellow]  🏝️  孤儿页面: {len(orphans)} 个[/yellow]")
        else:
            console.print("[green]  ✅ 无孤儿页面[/green]")

        # 3. 空内容/种子页检测
        seeds = self._check_seed_pages()
        report["checks"]["seed_pages"] = {"count": len(seeds)}

        if seeds:
            console.print(f"[yellow]  🌱 种子页面（待充实）: {len(seeds)} 个[/yellow]")

        # 4. 冲突检测（需要 LLM）
        conflicts = await self._detect_conflicts()
        report["checks"]["conflicts"] = conflicts

        # 5. 计算健康分数
        score = self._calculate_health_score(report)
        report["health_score"] = score

        # 6. 生成探索建议
        suggestions = await self._generate_suggestions(report)
        report["suggestions"] = suggestions

        # 打印最终面板
        self._print_report_panel(report)

        # 保存报告
        self._save_report(report)

        return report

    def _check_broken_links(self) -> list[dict]:
        """检测所有指向不存在页面的链接。"""
        return find_broken_links(Path(self.config.compiler.wiki_dir))

    def _check_orphan_pages(self) -> list[str]:
        """检测没有被任何其他页面链接到的孤立页面。"""
        import re as _re

        linker = AutoLinker(self.config)
        backlinks = linker.scan_all_wikilinks()

        all_pages: set[str] = set()
        referenced: set[str] = set()

        wiki_path = Path(self.config.compiler.wiki_dir)
        if not wiki_path.exists():
            return []

        for md_file in wiki_path.rglob("*.md"):
            if md_file.name.startswith("."):
                continue
            page_name = md_file.stem.lower()
            all_pages.add(page_name)
            
            content = md_file.read_text(encoding="utf-8")
            links = [l.strip().lower() for l in _re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", content)]
            referenced.update(links)

        # 孤儿页面：存在但未被任何页面引用的页面（排除 Home）
        orphans = sorted(
            p for p in all_pages 
            if p not in referenced and p != "home"
        )
        return orphans

    def _check_seed_pages(self) -> list[str]:
        """检测标记为 seed 或内容过短的页面。"""
        wiki_path = Path(self.config.compiler.wiki_dir)
        seeds = []

        if not wiki_path.exists():
            return seeds

        for md_file in wiki_path.rglob("*.md"):
            if md_file.name.startswith("."):
                continue
            content = md_file.read_text(encoding="utf-8")
            
            # 检查 front matter 中的 status: seed
            if "status: seed" in content.lower():
                seeds.append(str(md_file.relative_to(wiki_path)))
            elif len(content.strip()) < 150:
                seeds.append(str(md_file.relative_to(wiki_path)))

        return seeds

    async def _detect_conflicts(self) -> dict:
        """
        检测知识库中的冲突描述，包含三类检测：
        1. 重复概念页：同一概念以不同文件名存在
        2. 定义冲突：同义概念页中给出矛盾的定义
        3. 数值矛盾：不同页面引用同一概念时给出不同的数值

        纯确定性分析（无需 LLM），适合在 CI 中定期执行。
        """
        import re as _re

        wiki_path = Path(self.config.compiler.wiki_dir)
        concepts_path = wiki_path / "concepts"

        if not concepts_path.exists():
            return {"count": 0, "items": [], "message": "No concepts directory"}

        conflict_items: list[dict] = []

        # ── 1. 收集每个概念页的定义、数值和交叉引用 ──────────────
        concept_data: dict[str, dict] = {}

        for md_file in concepts_path.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")

            # 分离 front matter 和正文
            fm_match = _re.match(r"^---\n(.*?)\n---\n(.*)", content, _re.DOTALL)
            if fm_match:
                _fm = fm_match.group(1)
                body = fm_match.group(2)
            else:
                _fm = ""
                body = content

            concept_name = md_file.stem

            # 提取定义句（"**XX** 是..." 或加粗词后跟"是"的句型）
            definitions = _re.findall(
                r"\*\*([^*]+)\*\*\s*是[^。\n]{5,200}", body
            )

            # 提取关键数值（含单位的数字，如 28.4 BLEU, 97.2%, 4096）
            numbers = set(
                _re.findall(
                    r"(\d+\.?\d*)\s*"
                    r"(?:%|BLEU|AP|mAP|TFLOPS|GFLOPS|MB|GB|TB|KB|"
                    r"fps|ms|B|G|M|K|dB|层|亿|万|个|张|篇)",
                    body,
                )
            )

            # 提取交叉引用
            links = set(
                _re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", body)
            )

            concept_data[concept_name] = {
                "file": str(md_file.relative_to(wiki_path)),
                "definitions": definitions,
                "numbers": numbers,
                "links": links,
                "body_preview": body[:500],
            }

        # ── 2. 检测重复概念页（名称归一化后匹配）──────────────────
        # 归一化策略：
        #   key1 = 去分隔符后拼接（捕获 IOGan_Zhi_She_Ji / IO_Gan_Zhi_She_Ji）
        #   key2 = 按空格拆分后排序再拼接（捕获 Ren_Shaoqing / Shaoqing_Ren）
        normalized_map: dict[str, list[str]] = {}
        for name in concept_data:
            lower = name.lower()
            no_sep = lower.replace("_", "").replace("-", "")
            tokens = sorted(lower.replace("_", " ").replace("-", " ").split())
            sorted_key = "".join(tokens)
            for key in (no_sep, sorted_key):
                normalized_map.setdefault(key, []).append(name)

        # 去重同一 key 下的重复条目
        reported_pairs: set[tuple[str, ...]] = set()
        for _norm, aliases in normalized_map.items():
            if len(aliases) < 2:
                continue
            uniq = sorted(set(aliases))
            if len(uniq) < 2:
                continue
            pair_key = tuple(uniq)
            if pair_key in reported_pairs:
                continue
            reported_pairs.add(pair_key)

            files = [concept_data[a]["file"] for a in uniq]
            conflict_items.append({
                "type": "duplicate_concept",
                "concepts": uniq,
                "files": files,
                "message": (
                    f"可能为同一概念的不同命名: {', '.join(uniq)}"
                ),
                "severity": "high",
            })

        # ── 3. 检测定义冲突：同名概念在不同页面有矛盾定义 ──────────
        # 收集每个概念被引用时给出的定义
        cross_defs: dict[str, list[tuple[str, str]]] = {}  # concept -> [(source_page, definition)]
        for concept_name, data in concept_data.items():
            for link in data["links"]:
                if link in concept_data:
                    # 在引用方页面中搜索被引用概念的定义
                    link_defs = _re.findall(
                        rf"\*\*{link.replace('_', ' ')}\**\s*是([^。\n]{{5,200}})",
                        data["body_preview"],
                        _re.IGNORECASE,
                    )
                    for d in link_defs:
                        cross_defs.setdefault(link, []).append(
                            (concept_name, d.strip())
                        )

        # 检查同一概念的多处定义是否矛盾（简单启发式：前 20 字不同视为潜在冲突）
        for concept_name, defs in cross_defs.items():
            if len(defs) < 2:
                continue
            seen_snippets: list[tuple[str, str, str]] = []
            for source, definition in defs:
                snippet = definition[:20]
                for prev_source, prev_snip, prev_def in seen_snippets:
                    if snippet and prev_snip and snippet != prev_snip:
                        conflict_items.append({
                            "type": "definition_conflict",
                            "concept": concept_name,
                            "source1": prev_source,
                            "definition1": prev_def[:120],
                            "source2": source,
                            "definition2": definition[:120],
                            "severity": "medium",
                        })
                seen_snippets.append((source, snippet, definition))

        # ── 4. 检测数值矛盾：同一指标在不同页面有不同数值 ──────────
        # 收集每个概念页中出现的"指标名+数值"对
        metric_pattern = _re.compile(
            r"(BLEU|AP|mAP|Top-?\d|Accuracy|Error|FLOPS|GFLOPS|"
            r"parameters|params|layers|hidden|heads|"
            r"WMT|ImageNet|COCO|CIFAR)[^\d]{0,30}"
            r"(\d+\.?\d*)",
            _re.IGNORECASE,
        )

        metric_values: dict[str, dict[str, set[str]]] = {}  # metric -> {value -> {pages}}
        for concept_name, data in concept_data.items():
            for match in metric_pattern.finditer(data["body_preview"]):
                metric_name = match.group(1).lower()
                value = match.group(2)
                metric_values.setdefault(metric_name, {}).setdefault(
                    value, set()
                ).add(concept_name)

        # 如果同一指标出现 2+ 个不同数值，且来源页面不同，报告冲突
        for metric_name, value_map in metric_values.items():
            if len(value_map) < 2:
                continue
            # 检查不同数值是否来自不同页面
            all_pages: set[str] = set()
            for pages in value_map.values():
                all_pages.update(pages)
            if len(all_pages) < 2:
                continue
            values_sorted = sorted(value_map.keys())
            conflict_items.append({
                "type": "numeric_conflict",
                "metric": metric_name,
                "values": values_sorted,
                "pages": sorted(all_pages),
                "message": (
                    f"指标 '{metric_name}' 存在不同数值: "
                    f"{', '.join(values_sorted)}"
                ),
                "severity": "high",
            })

        total_concepts = len(concept_data)
        duplicates = sum(
            1 for c in conflict_items if c["type"] == "duplicate_concept"
        )
        def_conflicts = sum(
            1 for c in conflict_items if c["type"] == "definition_conflict"
        )
        num_conflicts = sum(
            1 for c in conflict_items if c["type"] == "numeric_conflict"
        )

        return {
            "count": len(conflict_items),
            "items": conflict_items[:50],
            "total_concepts": total_concepts,
            "duplicates": duplicates,
            "definition_conflicts": def_conflicts,
            "numeric_conflicts": num_conflicts,
            "message": (
                f"Scanned {total_concepts} concepts, "
                f"found {len(conflict_items)} potential conflicts "
                f"({duplicates} duplicates, "
                f"{def_conflicts} definition conflicts, "
                f"{num_conflicts} numeric conflicts)"
            ),
        }

    def _calculate_health_score(self, report: dict) -> float:
        """计算知识库健康分数 (0-100)。"""
        score = 100.0

        checks = report.get("checks", {})

        # 断链扣分
        broken_count = checks.get("broken_links", {}).get("count", 0)
        score -= min(broken_count * 2, 30)

        # 孤儿页面扣分
        orphan_count = checks.get("orphan_pages", {}).get("count", 0)
        score -= min(orphan_count * 1, 15)

        # 种子页面轻微扣分（说明有增长空间，不算坏事）
        seed_count = checks.get("seed_pages", {}).get("count", 0)
        score -= min(seed_count * 0.5, 5)

        # 冲突扣分（严重）
        conflict_count = checks.get("conflicts", {}).get("count", 0)
        score -= min(conflict_count * 10, 40)

        return max(0, min(100, round(score, 1)))

    async def _generate_suggestions(self, report: dict) -> list[str]:
        """根据体检结果生成探索建议。"""
        suggestions = []
        
        checks = report.get("checks", {})

        # 基于断链建议
        broken = checks.get("broken_links", {}).get("items", [])
        if broken:
            unique_targets = set(b["link"] for b in broken)
            for target in sorted(unique_targets)[:3]:
                suggestions.append(f"📄 创建缺失页面: [[{target}]]")

        # 基于孤儿页面建议
        orphans = checks.get("orphan_pages", {}).get("items", [])
        for orphan in orphans[:2]:
            suggestions.append(f"🔗 为 [[{orphan}]] 创建入口链接")

        # 基于种子页面建议
        seeds = checks.get("seed_pages", {})
        if isinstance(seeds, list):
            for seed in seeds[:2]:
                suggestions.append(f"🌱 充实页面: {seed}")

        return suggestions

    def _print_report_panel(self, report: dict) -> None:
        """打印格式化的体检报告面板。"""
        score = report.get("health_score", 0)

        if score >= 90:
            status = "[bold green]🟢 极佳[/bold green]"
        elif score >= 70:
            status = "[bold yellow]🟡 良好[/bold yellow]"
        elif score >= 50:
            status = "[bold red]🟠 需关注[/bold red]"
        else:
            status = "[bold red]🔴 需修复[/bold red]"

        panel_content = f"""\
状态: {status}
健康分数: **{score}/100**

| 检查项 | 结果 |
|--------|------|
| 断链接 | {report['checks'].get('broken_links', {}).get('count', 0)} 个 |
| 孤儿页 | {report['checks'].get('orphan_pages', {}).get('count', 0)} 个 |
| 种子页 | {report['checks'].get('seed_pages', {}).get('count', 0)} 个 |
| 冲突项 | {report['checks'].get('conflicts', {}).get('count', 0)} 个 |

建议 ({len(report.get('suggestions', []))} 条):\
"""

        for sug in report.get("suggestions", [])[:5]:
            panel_content += f"\n• {sug}"

        panel = Panel(panel_content, title="Lumina Health Report", border_style="cyan")
        console.print(panel)

    def _save_report(self, report: dict) -> None:
        """保存体检报告为 JSON 文件。"""
        wiki_path = Path(self.config.compiler.wiki_dir)
        wiki_path.mkdir(parents=True, exist_ok=True)
        report_path = wiki_path / ".health-report.json"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


async def main():
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Lumina Wiki - Knowledge Lint")
    parser.add_argument("--token", help="GitHub Token")
    parser.add_argument("--config", "-c", help="lumina.toml 路径")
    args = parser.parse_args()

    if args.token:
        import os
        os.environ["GITHUB_TOKEN"] = args.token

    config = load_config(args.config)
    linter = KnowledgeLinter(config)
    await linter.run_full_check()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
