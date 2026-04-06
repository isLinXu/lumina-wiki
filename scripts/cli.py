"""
Lumina Wiki - CLI Entry Point (Enhanced v2)
统一命令行入口，对标 sage-wiki 的完整命令集。

命令列表（与 sage-wiki 对应）:
  init       → 初始化项目
  ingest     → 摄入素材 (URL/Path/Issue)     [sage: ingest <url|path>]
  compile    → 编译 raw/ → wiki/             [sage: compile [--watch] [--fresh]]
  search     → 混合搜索                       [sage: search "query"]
  query      → 带引用问答                     [sage: query "question"]
  lint       → 知识体检                       [sage: lint [--fix]]
  link       → 反向链接管理                   [内置]
  status     → 统计状态面板                   [sage: status]
  doctor     → 配置诊断                       [sage: doctor]
  watch      → 监控模式 (持续编译)            [sage: compile --watch]
  serve      → MCP Server (Phase 3)           [sage: serve]
  full       → 完整流水线                     [自定义组合]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


# ─── 命令处理器 ────────────────────────────────────────────────────

async def cmd_init(args: argparse.Namespace):
    """初始化项目。"""
    from .init_cmd import run_init
    target = Path(args.path).resolve()
    run_init(target)


async def cmd_ingest(args: argparse.Namespace):
    """摄入素材（支持 URL、本地路径）。"""
    from .ingest_enhanced import EnhancedIngestEngine

    if not args.target:
        # 无参数时：回退到 Issue 摄入模式
        from .ingest import IngestEngine, main as ingest_main
        sys.argv = ["lumina-ingest"]
        if args.dry_run:
            sys.argv.append("--dry-run")
        await ingest_main()
        return

    engine = EnhancedIngestEngine()

    if args.target == "-":
        # 从 stdin 读取
        content = sys.stdin.read()
        print(f"从 stdin 读取了 {len(content)} 字符")
        # TODO: 处理 stdin 内容
        return

    result = await engine.ingest(args.target)

    if result.success:
        print(f"\n{result}")
        if args.auto_compile:
            print("\n🔧 自动触发编译...")
            from .pipeline import CompilerPipeline
            compiler = CompilerPipeline()
            await compiler.compile()
    else:
        print(f"\n{result}", file=sys.stderr)
        sys.exit(1)


async def cmd_compile(args: argparse.Namespace):
    """编译 raw/ → wiki/。"""
    from .config import load_config
    from .pipeline import CompilerPipeline

    cfg = load_config(args.config)

    if args.watch:
        # Watch 模式
        from .watcher import FileWatcher
        watcher = FileWatcher(cfg)
        if args.poll_interval:
            watcher.POLL_INTERVAL = args.poll_interval
        await watcher.watch()
        return

    if args.re_embed:
        # 仅重新生成向量嵌入
        from .search import WikiSearcher
        searcher = WikiSearcher(Path(cfg.compiler.wiki_dir))
        searcher._build_index()
        print(f"✅ 索引已重建，共 {len(searcher._bm25.doc_texts)} 个文档")
        return

    if args.re_extract:
        # 从已有摘要重新提取概念和文章
        compiler = CompilerPipeline(cfg)
        result = await compiler.re_extract()
        print(f"✅ Re-extract complete: {result['concepts_extracted']} concepts, "
              f"{result['articles_written']} articles, {result['errors']} errors")
        return

    compiler = CompilerPipeline(cfg)
    stats = await compiler.compile(dry_run=args.dry_run, fresh=args.fresh)


async def cmd_search(args: argparse.Namespace):
    """搜索 Wiki 内容。"""
    from .config import load_config
    from .search import WikiSearcher

    cfg = load_config(args.config)
    wiki_path = Path(cfg.compiler.wiki_dir)

    if not wiki_path.exists():
        print("❌ wiki/ 目录不存在，请先运行 `lumina compile`")
        sys.exit(1)

    searcher = WikiSearcher(wiki_path)
    
    tags = args.tags.split(",") if args.tags else None
    response = searcher.search(query=" ".join(args.query), limit=args.limit, tags=tags)

    print(searcher.format_results(response))


async def cmd_query(args: argparse.Namespace):
    """对 Wiki 提问（带引用的问答）。"""
    from .config import load_config
    from .query_engine import QueryEngine

    cfg = load_config(args.config)
    engine = QueryEngine(cfg)

    question = " ".join(args.question)
    result = await engine.ask(
        question,
        top_k=args.top_k,
        archive=args.archive,
        output_mode=args.format or "terminal",
    )

    if not args.archive and result.sources:
        print(f"\n💡 使用 --archive 可将此答案归档到 wiki/comparisons/")


async def cmd_lint(args: argparse.Namespace):
    """知识库体检。"""
    from .config import load_config
    from .linter import KnowledgeLinter

    cfg = load_config(args.config)
    linter = KnowledgeLinter(cfg)
    await linter.run_full_check()


async def cmd_link(args: argparse.Namespace):
    """反向链接管理。"""
    from .linker import AutoLinker
    linker = AutoLinker()

    backlinks = linker.scan_all_wikilinks()
    linked_pages = len(backlinks)
    total_refs = sum(len(v) for v in backlinks.values())

    print(f"🔗 反向链接索引已构建:")
    print(f"   被引用页面: {linked_pages}")
    print(f"   总入链数: {total_refs}")

    if args.fix:
        wiki_path = linker.wiki_path
        fixed_count = 0
        for md_file in wiki_path.rglob("*.md"):
            if md_file.name.startswith("."):
                continue
            updated = linker.update_page_backlinks(md_file)
            md_file.write_text(updated, encoding="utf-8")
            fixed_count += 1
        print(f"✅ 已更新 {fixed_count} 个页面的反向链接区域")


async def cmd_status(args: argparse.Namespace):
    """显示统计状态面板。"""
    from .config import load_config
    from .status_cmd import get_status, format_status

    cfg = load_config(args.config)
    info = get_status(cfg.compiler.wiki_dir, verbose=args.verbose)
    
    if args.json_output:
        import json
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        output = format_status(info)
        if output:
            print(output)


async def cmd_doctor(args: argparse.Namespace):
    """运行配置诊断。"""
    from .config import load_config
    from .status_cmd import run_doctor

    cfg = load_config(args.config)
    result = await run_doctor(cfg)
    
    if args.json_output:
        print(result.to_json())
    elif result.has_errors:
        sys.exit(1)


async def cmd_serve(args: argparse.Namespace):
    """启动 MCP Server（Phase 3 预留接口）。"""
    print("🔌 MCP Server 功能将在 Phase 3 实现")
    print("   当前版本支持: stdio 和 sse 传输模式")
    print("   参考 sage-wiki MCP 实现 (14 个工具)")
    print("\n可用工具预览:")
    tools = [
        ("read", "读取 Wiki 页面内容"),
        ("write", "写入/更新 Wiki 页面"),
        ("search", "混合搜索"),
        ("query", "带引用问答"),
        ("status", "获取统计状态"),
        ("list_concepts", "列出所有概念页"),
        ("get_backlinks", "获取反向链接"),
        ("ingest", "添加源文件"),
        ("compile", "触发编译"),
        ("lint", "运行体检"),
        ("log", "查看编译日志"),
        ("health", "获取健康度评分"),
        ("create_comparison", "创建对比分析页"),
        ("list_orphans", "列出孤儿页面"),
    ]
    for name, desc in tools:
        print(f"  • {name}: {desc}")


async def cmd_full(args: argparse.Namespace):
    """完整流水线：ingest + compile + lint。"""
    from .config import load_config

    cfg = load_config(args.config)

    if args.dry_run:
        print("=== Dry Run Mode ===")
        
        # 检查 raw 文件
        from .pipeline import CompilerPipeline
        compiler = CompilerPipeline(cfg)
        files = (await compiler.pass1_diff()).needs_processing
        print(f"\n待编译文件: {len(files)}")
        for f in files:
            rel = f.relative_to(cfg.ingest.raw_dir)
            size = f.stat().st_size
            print(f"  📄 {rel} ({size:,} bytes)")

        # 检查状态
        from .status_cmd import get_status, format_status
        info = get_status(cfg.compiler.wiki_dir)
        print(f"\n当前状态:\n{format_status(info)}")
        return

    print("\n" + "=" * 60)
    print("🌙 Lumina Wiki — Full Pipeline")
    print("=" * 60 + "\n")

    # Step 1: Ingest (如果有指定目标或自动检测 Issues)
    if hasattr(args, 'target') and args.target:
        from .ingest_enhanced import EnhancedIngestEngine
        ingest = EnhancedIngestEngine(cfg)
        result = await ingest.ingest(args.target)
        print(f"📥 Ingest: {result}")

    # Step 2: Compile
    print("\n📋 Step 2/3: Compiling...")
    from .pipeline import CompilerPipeline
    compiler = CompilerPipeline(cfg)
    stats = await compiler.compile()

    # Step 3: Lint
    print("\n🩺 Step 3/3: Health Check...")
    from .linter import KnowledgeLinter
    linter = KnowledgeLinter(cfg)
    await linter.run_full_check()

    print("\n" + "=" * 60)
    print("✅ Pipeline Complete!")
    print("=" * 60)


# ─── CLI 入口 ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="lumina",
        description="🌙 Lumina Wiki — GitHub-native 个人知识编译器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  lumina init                        初始化项目结构
  lumina ingest https://arxiv.org/abs/1706.03762   摄入 arXiv 论文
  lumina ingest ./paper.pdf          摄入本地 PDF
  lumina compile                     编译 raw → wiki
  lumina compile --watch             监控模式（自动编译）
  lumina compile --fresh             完全重新编译
  lumina search "attention mechanism"  搜索 Wiki
  lumina query "MoE routing策略差异"   带引用问答
  lumina lint                        知识体检
  lumina status                      状态面板
  lumina doctor                      诊断检查
  lumina link --fix                  修复反向链接
  lumina full                        完整流水线

参考项目:
  - Karpathy LLM Wiki: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
  - sage-wiki: https://github.com/xoai/sage-wiki
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ─── init ──────────────────────────────────────────────
    p = subparsers.add_parser("init", help="初始化项目")
    p.add_argument("path", nargs="?", default=".", help="目标路径")
    p.set_defaults(func=cmd_init)

    # ─── ingest ───────────────────────────────────────────
    p = subparsers.add_parser("ingest", help="摄入素材 (URL|Path|Issue)")
    p.add_argument("target", nargs="?", help="URL 或本地文件路径（省略则走Issue模式）")
    p.add_argument("--auto-compile", action="store_true", help="摄入后自动编译")
    p.add_argument("--dry-run", action="store_true", help="只扫描不执行")
    p.set_defaults(func=cmd_ingest)

    # ─── compile ──────────────────────────────────────────
    p = subparsers.add_parser("compile", help="编译 raw → wiki")
    p.add_argument("--dry-run", action="store_true", help="只扫描")
    p.add_argument("--fresh", action="store_true", help="忽略索引完全重编")
    p.add_argument("--watch", "-w", action="store_true", help="监控模式")
    p.add_argument("--poll-interval", type=float, default=None, help="监控检测间隔(秒)")
    p.add_argument("--re-embed", action="store_true", help="仅重建搜索索引")
    p.add_argument("--re-extract", action="store_true", help="重新提取概念+文章")
    p.add_argument("--file", "-f", help="编译单个文件")
    p.add_argument("-c", "--config", dest="config", help="配置文件路径")
    p.set_defaults(func=cmd_compile)

    # ─── search ──────────────────────────────────────────
    p = subparsers.add_parser("search", help="混合搜索 Wiki")
    p.add_argument("query", nargs="+", help="搜索关键词")
    p.add_argument("--tags", help="标签过滤(逗号分隔)")
    p.add_argument("--limit", type=int, default=10, help="最大结果数")
    p.add_argument("-c", "--config", dest="config", help="配置文件路径")
    p.set_defaults(func=cmd_search)

    # ─── query ───────────────────────────────────────────
    p = subparsers.add_parser("query", help="带引用的 Wiki 问答")
    p.add_argument("question", nargs="+", help="问题")
    p.add_argument("--top-k", type=int, default=5, help="检索相关页面数")
    p.add_argument("--archive", action="store_true", help="归档答案到 comparisons/")
    p.add_argument("--format", choices=["terminal", "json"], default="terminal", help="输出格式")
    p.add_argument("-c", "--config", dest="config", help="配置文件路径")
    p.set_defaults(func=cmd_query)

    # ─── lint ────────────────────────────────────────────
    p = subparsers.add_parser("lint", help="知识库健康体检")
    p.add_argument("-c", "--config", dest="config", help="配置文件路径")
    p.set_defaults(func=cmd_lint)

    # ─── link ────────────────────────────────────────────
    p = subparsers.add_parser("link", help="反向链接管理")
    p.add_argument("--fix", action="store_true", help="修复反向链接区域")
    p.set_defaults(func=cmd_link)

    # ─── status ──────────────────────────────────────────
    p = subparsers.add_parser("status", help="Wiki 统计状态面板")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--json", dest="json_output", action="store_true", help="JSON 格式输出")
    p.add_argument("-c", "--config", dest="config", help="配置文件路径")
    p.set_defaults(func=cmd_status)

    # ─── doctor ──────────────────────────────────────────
    p = subparsers.add_parser("doctor", help="配置诊断与验证")
    p.add_argument("--json", dest="json_output", action="store_true")
    p.add_argument("-c", "--config", dest="config", help="配置文件路径")
    p.set_defaults(func=cmd_doctor)

    # ─── serve (MCP) ─────────────────────────────────────
    p = subparsers.add_parser("serve", help="MCP Server (Phase 3)")
    p.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    p.add_argument("--port", type=int, default=3333)
    p.set_defaults(func=cmd_serve)

    # ─── full ────────────────────────────────────────────
    p = subparsers.add_parser("full", help="完整流水线 (ingest→compile→lint)")
    p.add_argument("target", nargs="?", help="可选：先摄入此目标")
    p.add_argument("--dry-run", action="store_true", help="只扫描不执行")
    p.add_argument("-c", "--config", dest="config", help="配置文件路径")
    p.set_defaults(func=cmd_full)

    # 解析
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        # 显示简短的 ASCII art banner
        print("""
    ╔══════════════════════════════════╗
   ║     🌙 Lumina Wiki v1.1.0        ║
    ║  Read-only for Humans            ║
    ║  Write-only for LLMs             ║
    ╚══════════════════════════════════╝

基于 Karpathy LLM Wiki 理念 | 参考 sage-wiki 架构
""")
        return

    # 运行对应命令
    try:
        asyncio.run(args.func(args))
    except KeyboardInterrupt:
        print("\n⚠️ 操作被中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
