"""
Lumina Wiki - Issue Ingest Script
将 GitHub Issue 内容归档到 raw/ 目录，为后续编译做准备。

工作流程：
1. 查找带 lumina label 的 open issue
2. 提取 Issue 的标题、正文、附件
3. 保存到 raw/YYYY-MM-DD/ 目录
4. （可选）关闭已处理的 Issue
"""

from __future__ import annotations

import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from github import Github, Issue
except ImportError:
    print("❌ 缺少依赖: pip install PyGithub")
    sys.exit(1)

from rich.console import Console
from rich.table import Table

from .config import LuminaConfig, get_token, load_config
from .llm_client import LLMClient

console = Console()


class IngestEngine:
    """Issue 摄入引擎。"""

    def __init__(self, config: LuminaConfig | None = None):
        self.config = config or load_config()
        self.token = get_token()
        self.gh = Github(self.token)
        self.repo = self.gh.get_repo(
            f"{self.config.repository.owner}/{self.config.repository.name}"
        )
        self.llm = LLMClient(self.config)

    def find_issues(self) -> list[Issue.Issue]:
        """查找待处理的 lumina Issue。"""
        label = self.config.ingest.label
        console.print(f"🔍 查找带 [bold]{label}[/bold] 标签的 open issues...")
        issues = self.repo.get_issues(state="open", labels=[label])
        issue_list = list(issues)
        console.print(f"   找到 {len(issue_list)} 个待处理 issue\n")
        return issue_list

    async def ingest_all(self) -> list[Path]:
        """
        处理所有待处理 issue，返回保存的文件路径列表。
        """
        issues = self.find_issues()

        if not issues:
            console.print("[yellow]⚠️  没有需要处理的 issue。[/yellow]")
            return []

        saved_files: list[Path] = []

        # 显示摘要表
        table = Table(title="待摄入 Issues", show_lines=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("标题", style="green", min_width=30)
        table.add_column("作者", style="blue")
        table.add_column("创建时间", dim=True)

        for i, issue in enumerate(issues, 1):
            table.add_row(
                str(i),
                issue.title,
                issue.user.login if issue.user else "unknown",
                issue.created_at.strftime("%Y-%m-%d %H:%M") if issue.created_at else "?",
            )
        console.print(table)
        console.print()

        for issue in issues:
            try:
                paths = await self.ingest_issue(issue)
                saved_files.extend(paths)

                # 可选：关闭已摄入的 issue
                if self.config.ingest.close_after_ingest:
                    issue.create_comment(
                        "✅ **Lumina 已摄入**\n\n"
                        f"内容已归档至 `raw/` 目录，等待编译。\n"
                        f"_由 Lumina Compiler 自动处理于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_"
                    )
                    issue.edit(state="closed")
                    console.print(f"  🔒 已关闭 #{issue.number}")
            except Exception as e:
                console.print(f"[red]  ❌ 处理 #{issue.number} 失败: {e}[/red]")

        return saved_files

    async def ingest_issue(self, issue: Issue.Issue) -> list[Path]:
        """
        处理单个 Issue，保存到 raw/ 目录。
        返回保存的文件路径列表。
        """
        now = datetime.now().strftime(self.config.ingest.date_format)
        raw_dir = Path(self.config.ingest.raw_dir) / now
        raw_dir.mkdir(parents=True, exist_ok=True)

        safe_name = _slugify(issue.title)
        md_path = raw_dir / f"{safe_name}.md"

        console.print(f"\n📥 处理 [bold cyan]#{issue.number}: {issue.title}[/bold cyan]")

        # 提取元数据
        metadata = {
            "source": "github-issue",
            "issue_number": issue.number,
            "title": issue.title,
            "author": issue.user.login if issue.user else "unknown",
            "created_at": (
                issue.created_at.isoformat() if issue.created_at else None
            ),
            "url": issue.html_url,
            "labels": [label.name for label in issue.labels],
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        # 提取正文内容（支持 Markdown）
        body = issue.body or ""

        # 提取图片并下载
        images_info = await self._extract_images(body, raw_dir, safe_name)

        # 如果配置了图片描述生成，对每张图生成 .desc.md
        if self.config.ingest.process_images and images_info and len(images_info) > 0:
            for img_info in images_info:
                desc = await self._describe_and_save(img_info, raw_dir)
                img_info["description"] = desc

        # 构建 Markdown 文件
        content = self._build_markdown(metadata, body, images_info)

        # 写入文件
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

        console.print(f"  💾 保存到: {md_path}")

        # 同时导出 JSON 元数据
        meta_path = raw_dir / f"{safe_name}.meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata | {"images": images_info}, f, ensure_ascii=False, indent=2)

        return [md_path, meta_path]

    async def _extract_images(
        self, body: str, output_dir: Path, prefix: str
    ) -> list[dict]:
        """
        从 Markdown 正文提取图片链接并下载到本地。
        返回图片信息列表。
        """
        # 匹配 Markdown 图片语法 ![alt](url)
        image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        matches = re.findall(image_pattern, body)
        
        # 也匹配裸 URL（GitHub 会自动渲染）
        url_pattern = r"(https?://[^\s\)]+\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?[^\s]*)?)"
        urls = re.findall(url_pattern, body, re.IGNORECASE)

        images: list[dict] = []
        seen_urls: set[str] = set()

        for i, (alt_text, url) in enumerate(matches, 1):
            if url in seen_urls:
                continue
            seen_urls.add(url)

            img_data = await self._download_image(url, output_dir, f"{prefix}_img{i}")
            if img_data:
                img_data["alt"] = alt_text
                images.append(img_data)

        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)

            img_data = await self._download_image(url, output_dir, f"{prefix}_img{len(images)+1}")
            if img_data:
                img_data["alt"] = ""
                images.append(img_data)

        return images

    async def _download_image(
        self, url: str, output_dir: Path, filename_prefix: str
    ) -> dict | None:
        """
        下载单张图片到本地。
        返回图片信息字典或 None。
        """
        import httpx
        from urllib.parse import urlparse

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            # 确定文件扩展名
            content_type = resp.headers.get("content-type", "")
            ext_map = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "image/svg+xml": ".svg",
            }
            ext = ext_map.get(content_type, ".png")

            # 从 URL 路径尝试获取扩展名
            parsed = urlparse(url.path if not isinstance(url, str) else url)
            path_str = url if isinstance(url, str) else url.path
            
            # 简化：直接从 content-type 判断
            local_filename = f"{filename_prefix}{ext}"
            local_path = output_dir / local_filename

            local_path.write_bytes(resp.content)

            return {
                "original_url": url,
                "local_path": str(local_path),
                "filename": local_filename,
                "size": len(resp.content),
                "content_type": content_type,
                "description": "",
            }

        except Exception as e:
            console.print(f"  ⚠️ 图片下载失败 [{url[:50]}...]: {e}")
            return None

    async def _describe_and_save(self, img_info: dict, output_dir: Path) -> str:
        """调用多模态 LLM 生成图片描述并保存为 .desc.md 文件。"""
        try:
            description = await self.llm.describe_image(img_info["local_path"])

            # 保存描述文件
            desc_path = Path(img_info["local_path"]).with_suffix(".desc.md")
            desc_path.write_text(
                f"# 图片描述: {img_info['filename']}\n\n"
                f"> 来源: {img_info['original_url']}\n\n"
                f"{description}\n",
                encoding="utf-8",
            )

            console.print(f"  🖼️ 已生成图片描述: {desc_path.name}")
            return description

        except Exception as e:
            console.print(f"  ⚠️ 图片描述生成失败: {e}")
            return ""

    def _build_markdown(
        self, metadata: dict, body: str, images: list[dict]
    ) -> str:
        """构建原始归档的 Markdown 文件。"""
        lines: list[str] = []

        # Front matter (YAML)
        lines.append("---")
        lines.append(f"title: \"{metadata.get('title', 'untitled')}\"")
        lines.append(f"source: {metadata.get('source', 'unknown')}")
        lines.append(f"issue_number: {metadata.get('issue_number', '?')}")
        lines.append(f"author: {metadata.get('author', 'unknown')}")
        lines.append(f"url: {metadata.get('url', '')}")
        lines.append(f"ingested_at: {metadata.get('ingested_at', '')}")
        lines.append(f"labels: {json.dumps(metadata.get('labels', []), ensure_ascii=False)}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {metadata.get('title', 'Untitled')}\n")

        # 原始正文
        if body.strip():
            lines.append("## 原始内容\n")
            lines.append(body)
            lines.append("")

        # 图片清单
        if images:
            lines.append("\n## 附件/图片\n")
            for img in images:
                lines.append(f"- **{img.get('alt', img['filename'])}**: `![[{img['filename']}]]`")
                if img.get("description"):
                    lines.append(f"  > {img['description'][:100]}...")
            lines.append("")

        return "\n".join(lines)


def _slugify(text: str) -> str:
    """将文本转换为安全的文件名。"""
    from slugify import slugify
    result = slugify(text, separator="_", lowercase=False)
    # 截断过长的文件名
    return result[:80] if len(result) > 80 else result


# ─── CLI 入口 ──────────────────────────────────────────────────────────────
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Lumina Wiki - Issue Ingest")
    parser.add_argument("--token", help="GitHub Token（或设置 GITHUB_TOKEN 环境变量）")
    parser.add_argument("--config", "-c", help="lumina.toml 路径")
    parser.add_argument("--dry-run", action="store_true", help="只显示将要处理的 Issue，不实际执行")
    args = parser.parse_args()

    if args.token:
        import os
        os.environ["GITHUB_TOKEN"] = args.token

    config = load_config(args.config)
    engine = IngestEngine(config)

    if args.dry_run:
        issues = engine.find_issues()
        if not issues:
            print("没有待处理的 Issue。")
            return
        for issue in issues:
            print(f"  #{issue.number}: {issue.title} (@{issue.user.login})")
        return

    files = await engine.ingest_all()
    console.print(f"\n✅ 摄入完成！共处理 {len(files)} 个文件")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
