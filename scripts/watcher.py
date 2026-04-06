"""
Lumina Wiki - File Watcher
监控 raw/ 目录变化并自动触发编译。

参考 sage-wiki 的 `compile --watch` 功能。
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

try:
    from rich.console import Console
    console = Console()
except ImportError:
    console = None  # type: ignore

from .config import load_config, LuminaConfig
from .pipeline import CompilerPipeline


class FileWatcher:
    """文件系统监控器，检测 raw/ 目录变化后触发编译。"""

    # 检测间隔（秒）
    POLL_INTERVAL = 3.0
    # 防抖延迟：文件变更后等待 N 秒再触发编译（避免频繁触发）
    DEBOUNCE_SECONDS = 5.0

    def __init__(self, config: LuminaConfig | None = None):
        self.config = config or load_config()
        self.raw_path = Path(self.config.ingest.raw_dir)
        self._last_snapshot: dict[str, int] = {}
        self._compiler: CompilerPipeline | None = None
        self._running = False
        self._compile_count = 0

    async def watch(self) -> None:
        """
        开始监控 raw/ 目录。
        
        使用轮询模式（跨平台兼容，无需 fsevents/inotify 依赖）。
        按 sage-wiki 风格，支持 Ctrl+C 优雅停止。
        """
        if not self.raw_path.exists():
            print(f"⚠️  raw/ 目录不存在: {self.raw_path}")
            print("   请先创建目录或运行 `lumina init`")
            return

        self._running = True
        self._compiler = CompilerPipeline(self.config)

        console.print(f"\n[bold cyan]👁️  监控模式[/bold cyan]")
        console.print(f"   监控目录: {self.raw_path}")
        console.print(f"   检测间隔: {self.POLL_INTERVAL}s")
        console.print(f"   防抖延迟: {self.DEBOUNCE_SECONDS}s")
        console.print("   按 Ctrl+C 停止\n")

        # 初始快照
        self._last_snapshot = await self._take_snapshot()

        last_compile_time = 0.0
        pending_changes = False

        try:
            while self._running:
                current_snapshot = await self._take_snapshot()

                if current_snapshot != self._last_snapshot:
                    if not pending_changes:
                        pending_changes = True
                        change_time = time.time()
                        console.print("[yellow]  📝 检测到文件变化...[/yellow]")

                    # 检查防抖是否到期
                    if pending_changes and (time.time() - change_time >= self.DEBOUNCE_SECONDS):
                        console.print("\n[bold green]▶ 触发自动编译...[/bold green]\n")
                        
                        try:
                            stats = await self._compiler.compile()
                            self._compile_count += 1
                            self._last_snapshot = current_snapshot
                            last_compile_time = time.time()
                            
                            console.print(
                                f"\n[dim]💤 继续监控... (已自动编译 {self._compile_count} 次)"
                                f" | 按 Ctrl+C 停止[/dim]\n"
                            )
                        except Exception as e:
                            console.print(f"[red]  ❌ 自动编译失败: {e}[/red]")
                        
                        pending_changes = False

                elif pending_changes and (time.time() - change_time >= self.DEBOUNCE_SECONDS):
                    # 快照一致但之前有 pending 变化（可能被外部回滚了）
                    pending_changes = False
                
                await asyncio.sleep(self.POLL_INTERVAL)

        except KeyboardInterrupt:
            self._running = False
            console.print(f"\n\n[yellow]⚠️  停止监控。共触发了 {self._compile_count} 次自动编译。[/yellow]")

    async def _take_snapshot(self) -> dict[str, int]:
        """获取当前 raw/ 目录的文件快照（路径 -> mtime_ns）。"""
        snapshot: dict[str, int] = {}
        if not self.raw_path.exists():
            return snapshot
        
        for item in self.raw_path.rglob("*"):
            if item.is_file() and not item.name.startswith("."):
                rel = str(item.relative_to(self.raw_path))
                snapshot[rel] = item.stat().st_mtime_ns
        
        return snapshot


async def run_watch(poll_interval: float | None = None) -> None:
    """CLI 入口：启动 Watch 模式。"""
    watcher = FileWatcher()
    
    if poll_interval is not None:
        watcher.POLL_INTERVAL = poll_interval
    
    await watcher.watch()
