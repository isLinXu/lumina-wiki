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
        使用 LLM 检测不同文档中对同一概念/参数的描述冲突。
        这是一个较重的操作，只在定时任务中执行。
        """
        # 收集所有包含数值/参数描述的页面片段
        # 这里实现一个简化版本：检查同名概念的多个定义
        
        wiki_path = Path(self.config.compiler.wiki_dir)
        concepts_path = wiki_path / "concepts"
        
        if not concepts_path.exists():
            return {"count": 0, "items": [], "message": "No concepts directory"}

        conflict_items: list[dict] = []

        # TODO: 实现基于语义相似度的冲突检测
        # 当前版本先返回基础统计
        
        concept_files = list(concepts_path.glob("*.md"))
        total_concepts = len(concept_files)

        return {
            "count": len(conflict_items),
            "items": conflict_items,
            "total_concepts": total_concepts,
            "message": f"Scanned {total_concepts} concepts",
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
