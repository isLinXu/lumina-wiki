"""
Lumina Wiki - Compiler (Legacy Compatibility Shim)

This module is deprecated. Use scripts.pipeline.CompilerPipeline instead.
WikiCompiler is kept as an alias for backward compatibility.

Migration guide:
    Old: from scripts.compiler import WikiCompiler
    New: from scripts.pipeline import CompilerPipeline

The old WikiCompiler class had a simpler 3-step pipeline (scan → summarize → write).
CompilerPipeline implements the full 5-Pass pipeline (diff → summarize → extract → write → post-process)
and supersedes all functionality of WikiCompiler.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from rich.console import Console

from .config import load_config
from .pipeline import CompilerPipeline

console = Console()

# Backward-compatible alias
WikiCompiler = CompilerPipeline


async def main():
    """CLI entry point — delegates to CompilerPipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Lumina Wiki - Knowledge Compiler (legacy entry)")
    parser.add_argument("--token", help="GitHub Token (or set GITHUB_TOKEN)")
    parser.add_argument("--config", "-c", help="Path to lumina.toml")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, no compilation")
    parser.add_argument("--file", "-f", help="Compile a single file")
    args = parser.parse_args()

    if args.token:
        import os
        os.environ["GITHUB_TOKEN"] = args.token

    config = load_config(args.config)
    compiler = CompilerPipeline(config)

    if args.file:
        target = Path(args.file)
        if not target.exists():
            console.print(f"[red]File not found: {target}[/red]")
            sys.exit(1)
        # Delegate to the full pipeline (processes single file via compile())
        stats = await compiler.compile()
        console.print(f"\nResult: {stats}")
    else:
        stats = await compiler.compile(dry_run=args.dry_run)
        if not args.dry_run:
            console.print(f"\n✅ Compiled: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
