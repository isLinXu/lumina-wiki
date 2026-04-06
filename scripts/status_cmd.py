"""
Lumina Wiki - Status & Doctor Commands
Wiki 统计信息和配置验证工具。

对应 sage-wiki 的 status 和 doctor 命令。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
except ImportError:
    console = None  # type: ignore


from .config import load_config, LuminaConfig
from .linter import KnowledgeLinter
from .linker import AutoLinker, find_broken_links
from .search import WikiSearcher


def get_status(wiki_path: str | Path, verbose: bool = False) -> dict:
    """
    获取 Wiki 统计状态信息。
    对应 sage-wiki 的 `status` 命令。
    
    Returns:
        包含各类统计信息的字典
    """
    wiki = Path(wiki_path)

    info = {
        "project_name": "",
        "wiki_exists": wiki.exists(),
        "last_compile": None,
        "total_pages": 0,
        "concepts": 0,
        "papers": 0,
        "notes": 0,
        "comparisons": 0,
        "raw_files": 0,
        "total_size_kb": 0,
        "broken_links": 0,
        "orphan_pages": 0,
        "seed_pages": 0,
        "health_score": None,
        "index_size": 0,
        "log_entries": 0,
    }

    if not wiki.exists():
        return info

    # 各目录统计
    subdirs = {
        "concepts": ("concepts", "concepts"),
        "papers": ("papers", "papers"),
        "notes": ("notes", "notes"),
        "comparisons": ("comparisons", "comparisons"),
    }

    for key, (subdir_name, _) in subdirs.items():
        subdir = wiki / subdir_name
        if subdir.exists():
            count = len(list(subdir.glob("*.md")))
            info[key] = count
            info["total_pages"] += count
            for f in subdir.glob("*.md"):
                info["total_size_kb"] += f.stat().st_size / 1024
    info["total_size_kb"] = round(info["total_size_kb"], 1)

    # Raw 文件统计
    raw_dir = wiki.parent / "raw" if (wiki.name == "wiki") else wiki / ".." / "raw"
    # 更可靠的方式：从 config 获取 raw 路径
    try:
        cfg = load_config()
        raw_dir = Path(cfg.ingest.raw_dir)
    except Exception:
        pass
    
    if raw_dir.exists():
        info["raw_files"] = len(list(raw_dir.rglob("*.md")))

    # 编译状态
    compiled_json = wiki / ".compiled.json"
    if compiled_json.exists():
        try:
            compiled_data = json.loads(compiled_json.read_text(encoding="utf-8"))
            info["last_compile"] = compiled_data.get("last_run")
            info["index_size"] = len(compiled_data.get("compiled", {}))
        except Exception:
            pass

    # 链接健康
    broken = find_broken_links(wiki)
    info["broken_links"] = len(broken)

    # 反向链接索引大小
    backlinks_json = wiki / ".backlinks.json"
    if backlinks_json.exists():
        try:
            bl = json.loads(backlinks_json.read_text(encoding="utf-8"))
            linked_pages = len(bl)
            total_with_links = sum(len(v) for v in bl.values())
            unlinked = info["total_pages"] - linked_pages
            info["orphan_pages"] = max(0, unlinked)
        except Exception:
            pass

    # 日志条目数
    log_md = wiki / "log.md"
    if log_md.exists():
        log_content = log_md.read_text(encoding="utf-8")
        info["log_entries"] = log_content.count("## [")

    # 种子页检测
    seed_count = 0
    concepts_dir = wiki / "concepts"
    if concepts_dir.exists():
        for md in concepts_dir.glob("*.md"):
            content = md.read_text(encoding="utf-8")
            if "status: seed" in content or len(content.strip()) < 150:
                seed_count += 1
    info["seed_pages"] = seed_count

    # 健康度（简化计算）
    if info["total_pages"] > 0:
        score = 100.0
        score -= min(info["broken_links"] * 2, 30)
        score -= min(info["orphan_pages"] * 1, 15)
        score -= min(info["seed_pages"] * 0.5, 5)
        info["health_score"] = round(max(0, score), 1)

    return info


def format_status(info: dict) -> str:
    """格式化状态输出（终端友好）。"""
    if not info.get("wiki_exists"):
        return "[red]❌ Wiki 目录不存在。请先运行 `lumina init` 和 `lumina compile`。[/red]"

    health = info.get("health_score")
    if health is not None:
        if health >= 90:
            health_icon = "🟢"
        elif health >= 70:
            health_icon = "🟡"
        elif health >= 50:
            health_icon = "🟠"
        else:
            health_icon = "🔴"
        health_str = f"{health_icon} {health}/100"
    else:
        health_str = "-- (尚未编译)"

    last_c = info.get("last_compile") or "从未"
    
    table_content = f"""\
│ 📊 Lumina Wiki 状态面板                          │
├────────────────────────────────────────────────────┤
│ 总页面数     │ {info['total_pages']:>6} │ 概念 │ {info['concepts']:>5} │ 论文 │ {info['papers']:>5} │ 笔记 │ {info['notes']:>5} │
│ Raw 文件     │ {info['raw_files']:>6} │ 对比 │ {info['comparisons']:>5} │ 大小 │ {info['total_size_kb']:>5}KB │
├────────────────────────────────────────────────────┤
│ 健康度       │ {health_str:>20} │ 断链 │ {info['broken_links']:>5} │ 孤儿 │ {info['orphan_pages']:>5} │ 种子 │ {info['seed_pages']:>5} │
│ 最后编译     │ {str(last_c)[:22]:>22} │ 日志 │ {info['log_entries']:>5} │ 索引 │ {info['index_size']:>5} │
└────────────────────────────────────────────────────┘"""

    # 也用 Rich Table 格式化
    if console:
        table = Table(title="Lumina Wiki — Status", show_lines=True)
        table.add_column("指标", style="cyan", width=16)
        table.add_column("值", style="green", width=12)
        table.add_column("指标", style="cyan", width=16)
        table.add_column("值", style="green", width=12)

        rows = [
            ("总页面数", str(info["total_pages"]), "概念", str(info["concepts"])),
            ("论文", str(info["papers"]), "笔记", str(info["notes"])),
            ("Raw 文件", str(info["raw_files"]), "对比分析", str(info["comparisons"])),
            ("总大小", f"{info['total_size_kb']} KB", "最后编译", str(info.get("last_compile") or "从未")[:19]),
            ("健康度", health_str, "断链接", str(info["broken_links"])),
            ("孤儿页", str(info["orphan_pages"]), "种子页", str(info["seed_pages"])),
            ("日志条目", str(info["log_entries"]), "已索引文件", str(info["index_size"])),
        ]
        for r in rows:
            table.add_row(*r)

        console.print(table)
        return ""

    return table_content


async def run_doctor(config: LuminaConfig | None = None) -> DoctorResult:
    """
    运行诊断检查。
    对应 sage-wiki 的 `doctor` 命令。
    
    检查项：
    1. 配置文件有效性
    2. 目录结构完整性
    3. API 连通性
    4. 索引一致性
    """
    cfg = config or load_config()
    checks: list[dict] = []
    errors = []
    warnings = []

    # 1. 配置检查
    checks.append(_check("配置文件", cfg.config_path.exists(),
                           f"找到: {cfg.config_path}", "⚠️ lumina.toml 不存在"))

    # 2. 目录结构检查
    dirs_to_check = [
        ("raw/", cfg.raw_path),
        ("wiki/", cfg.wiki_path),
        ("wiki/concepts/", cfg.concepts_path),
        ("wiki/papers/", cfg.papers_path),
        ("wiki/notes/", cfg.notes_path),
    ]
    for label, p in dirs_to_check:
        exists = p.exists()
        checks.append(_check(label, exists,
                             f"✅ {p}" if exists else f"⚠️ 缺失: {p}"))
        if not exists:
            warnings.append(f"{label} 不存在")

    # 3. Schema 文件检查
    schema_file = cfg.config_path.parent / "CLAUDE.md"
    schema_ok = schema_file.exists()
    checks.append(_check("Schema (CLAUDE.md)", schema_ok,
                         "✅ Schema 文件存在", "⚠️ CLAUDE.md 不存在"))

    # 4. 索引文件检查
    compiled_idx = Path("wiki/.compiled.json")
    idx_valid = False
    if compiled_idx.exists():
        try:
            data = json.loads(compiled_idx.read_text(encoding="utf-8"))
            idx_valid = isinstance(data, dict) and "compiled" in data
            checks.append(_check("编译索引", idx_valid, f"✅ 已记录 {len(data.get('compiled', {}))} 个文件",
                                 "⚠️ 索引格式异常"))
        except Exception:
            checks.append(_check("编译索引", False, "", "❌ 索引文件损坏"))
    else:
        checks.append(_check("编译索引", False, "", "ℹ️ 尚未运行过编译"))

    # 5. LLM API 连通性（快速测试）
    try:
        from .llm_client import LLMClient
        llm = LLMClient(cfg)
        # 发送一个极简请求测试连通性
        import asyncio
        test_resp = await llm.chat(
            [{"role": "user", "content": "Reply with only the word OK"}],
            temperature=0,
            max_tokens=5,
        )
        api_ok = "ok" in test_resp.lower() or len(test_resp) < 10
        checks.append(_check("LLM API", api_ok, f"✅ {cfg.llm.provider}/{cfg.llm.model}",
                              f"❌ API 无响应 ({cfg.llm.provider})"))
    except Exception as e:
        checks.append(_check("LLM API", False, "", f"❌ API 错误: {str(e)[:50]}"))
        errors.append(f"LLM API 连接失败: {e}")

    # 6. Git 状态检查
    try:
        import subprocess
        result = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                               capture_output=True, text=True, timeout=5)
        git_ok = result.returncode == 0
        checks.append(_check("Git 仓库", git_ok, "✅ 在 Git 仓库内", "⚠️ 非 Git 仓库"))
    except Exception:
        checks.append(_check("Git 仓库", False, "", "⚠️ 无法检测 Git"))

    # 输出
    result = DoctorResult(checks=checks, errors=errors, warnings=warnings)

    if console:
        table = Table(title="🩺 Lumina Doctor — 诊断报告", show_lines=True)
        table.add_column("检查项", width=24)
        table.add_column("状态", width=8)
        table.add_column("详情", width=45)

        for c in checks:
            status_style = "green" if c["passed"] else ("yellow" if "⚠️" in c["message"] else "red")
            icon = "✅" if c["passed"] else "❌"
            table.add_row(c["name"], f"[{status_style}]{icon}[/{status_style}]", c["message"])

        console.print(table)

        if errors:
            console.print(f"\n[bold red]❌ 发现 {len(errors)} 个错误[/bold red]")
            for e in errors:
                console.print(f"   • {e}")
        elif warnings:
            console.print(f"\n[yellow]⚠️  {len(warnings)} 个警告[/yellow]")
        else:
            console.print("\n[bold green]✅ 所有检查通过！[/bold green]")

    return result


def _check(name: str, passed: bool, ok_message: str, fail_message: str) -> dict:
    """创建一条检查记录。"""
    return {
        "name": name,
        "passed": passed,
        "message": ok_message if passed else fail_message,
    }


class DoctorResult:
    """诊断结果。"""

    def __init__(self, checks: list[dict], errors: list[str], warnings: list[str]):
        self.checks = checks
        self.errors = errors
        self.warnings = warnings

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def to_json(self) -> str:
        return json.dumps({
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
            "has_errors": self.has_errors,
        }, ensure_ascii=False, indent=2)
