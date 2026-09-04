"""
Lumina Wiki - Unified Ingest Engine
统一摄入引擎：支持 GitHub Issue、URL、本地文件三种输入源。

工作流程：
1. GitHub Issue 模式：查找带 lumina label 的 open issue，提取内容归档到 raw/
2. URL 模式：智能识别 arXiv / GitHub / 通用网页，抓取内容归档到 raw/
3. 本地文件模式：支持 PDF / Markdown / 图片 / 二进制文件，复制并归档到 raw/
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from .config import LuminaConfig, get_token, load_config
from .llm_client import LLMClient

from rich.console import Console
from rich.table import Table

console = Console()


class IngestResult:
    """单次摄入的结果。"""

    def __init__(
        self,
        source: str,
        source_path: str = "",
        doc_type: str = "other",
        size: int = 0,
        success: bool = True,
        error_message: str = "",
    ):
        self.source = source
        self.source_path = source_path
        self.doc_type = doc_type
        self.size = size
        self.success = success
        self.error_message = error_message

    def __str__(self) -> str:
        if self.success:
            return f"✅ Ingested: {self.source} (type: {self.doc_type}, {self.size:,} bytes) -> {self.source_path}"
        else:
            return f"❌ Failed: {self.source} -- {self.error_message}"


class IngestEngine:
    """统一摄入引擎：GitHub Issue + URL + 本地文件。"""

    def __init__(self, config: LuminaConfig | None = None):
        self.config = config or load_config()
        self.raw_path = Path(self.config.ingest.raw_dir)
        # GitHub 客户端懒加载（URL/文件摄入不需要 token）
        self._gh = None
        self._repo = None
        self._token = None
        # LLM 客户端（可选，用于图片描述）
        try:
            self.llm = LLMClient(self.config)
        except Exception:
            self.llm = None

    # ─── GitHub 懒加载属性 ──────────────────────────────────────

    @property
    def gh(self):
        """懒加载 GitHub 客户端，仅在 Issue 摄入时初始化。"""
        if self._gh is None:
            from github import Github
            self._token = get_token()
            self._gh = Github(self._token)
        return self._gh

    @property
    def repo(self):
        """懒加载仓库对象。"""
        if self._repo is None:
            self._repo = self.gh.get_repo(
                f"{self.config.repository.owner}/{self.config.repository.name}"
            )
        return self._repo

    # ═══════════════════════════════════════════════════════════
    #  GitHub Issue 摄入
    # ═══════════════════════════════════════════════════════════

    def find_issues(self, issue_number: int | None = None) -> list:
        """
        查找待处理的 Issue。

        策略（按优先级）：
        1. 如果指定了 issue_number -> 直接获取该 Issue
        2. 查找带 lumina label 的 open issues
        3. 如果没有 label 匹配 -> 查找标题含 [Lumina] 的 open issues
        """
        # 策略 1：直接获取指定 Issue
        if issue_number:
            console.print(f"🔍 直接获取 Issue #{issue_number}...")
            try:
                issue = self.repo.get_issue(issue_number)
                if issue.state == "open":
                    console.print(f"   ✅ 找到: #{issue.number} {issue.title}")
                    return [issue]
                else:
                    console.print(f"   ⚠️  Issue #{issue_number} 已关闭")
                    return []
            except Exception as e:
                console.print(f"   ❌ 获取 Issue #{issue_number} 失败: {e}")
                return []

        # 策略 2：按 label 过滤
        label = self.config.ingest.label
        console.print(f"🔍 查找带 [bold]{label}[/bold] 标签的 open issues...")
        try:
            issues = list(self.repo.get_issues(state="open", labels=[label]))
            if issues:
                console.print(f"   找到 {len(issues)} 个待处理 issue\n")
                return issues
        except Exception:
            pass

        # 策略 3：fallback -- 查找标题含 [Lumina] 的 Issues
        console.print(f"   未找到带 '{label}' 标签的 issue，尝试标题匹配...")
        try:
            all_issues = list(self.repo.get_issues(state="open"))
            matched = [
                i for i in all_issues
                if "[lumina]" in i.title.lower()
                or "lumina" in (i.body or "").lower()[:200]
            ]
            if matched:
                console.print(f"   📌 通过标题/内容匹配到 {len(matched)} 个 issue\n")
                return matched
        except Exception as e:
            console.print(f"   ❌ 查询失败: {e}")

        console.print("   未找到任何待处理的 issue\n")
        return []

    async def ingest_all(self, issue_number: int | None = None) -> list[Path]:
        """处理所有待处理 issue，返回保存的文件路径列表。"""
        issues = self.find_issues(issue_number=issue_number)

        if not issues:
            console.print("[yellow]⚠️  没有需要处理的 issue。[/yellow]")
            return []

        saved_files: list[Path] = []

        # 显示摘要表
        table = Table(title="待摄入 Issues", show_lines=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("标题", style="green", min_width=30)
        table.add_column("作者", style="blue")
        table.add_column("创建时间", style="dim")

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
                console.print(f"  ✅ 保存了 {len(paths)} 个文件:")
                for p in paths:
                    console.print(f"     📄 {p} ({p.stat().st_size:,} bytes)" if p.exists() else f"     ❌ {p} (不存在!)")

                # 可选：关闭已摄入的 issue
                if self.config.ingest.close_after_ingest:
                    try:
                        issue.create_comment(
                            "✅ **Lumina 已摄入**\n\n"
                            f"内容已归档至 `raw/` 目录，等待编译。\n"
                            f"_由 Lumina Compiler 自动处理于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_"
                        )
                        issue.edit(state="closed")
                        console.print(f"  🔒 已关闭 #{issue.number}")
                    except Exception as close_err:
                        console.print(f"  ⚠️ 关闭 Issue 失败 (不影响摄入): {close_err}")
            except Exception as e:
                console.print(f"[red]  ❌ 处理 #{issue.number} 失败: {e}[/red]")
                import traceback
                traceback.print_exc()

        return saved_files

    async def ingest_issue(self, issue) -> list[Path]:
        """
        处理单个 Issue，保存到 raw/ 目录。
        - 智能文件命名：从 body 中提取实际标题/URL 生成有意义的名称
        - 自动抓取 URL 内容（arXiv、网页等）
        - 不输出 .meta.json（仅生成 .md）
        """
        now = datetime.now().strftime(self.config.ingest.date_format)
        raw_dir = Path(self.config.ingest.raw_dir) / now
        raw_dir.mkdir(parents=True, exist_ok=True)

        body = issue.body or ""
        console.print(f"\n📥 处理 [bold cyan]#{issue.number}: {issue.title}[/bold cyan]")

        # ── 1. 从 body 中提取 URL ──
        urls = re.findall(r'(https?://[^\s\)]+)', body)
        fetched_content = ""
        resolved_title = ""

        for url in urls:
            console.print(f"  🔗 发现 URL: {url[:80]}")
            try:
                if httpx is not None:
                    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            html = resp.text

                            # 提取页面标题
                            title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
                            if title_match:
                                resolved_title = title_match.group(1).strip()[:100]
                                console.print(f"  📖 页面标题: {resolved_title}")

                            # arXiv 特殊处理
                            if "arxiv.org" in url:
                                ct = re.search(r'<meta name="citation_title" content="([^"]+)"', html)
                                if ct:
                                    resolved_title = ct.group(1)
                                ca = re.findall(r'<meta name="citation_author" content="([^"]+)"', html)
                                ab = re.search(r'<meta name="citation_abstract" content="([^"]+)"', html)
                                fetched_content = f"## {resolved_title or 'arXiv Paper'}\n\n"
                                if ca:
                                    fetched_content += f"**Authors**: {', '.join(ca)}\n\n"
                                if ab:
                                    fetched_content += f"### Abstract\n\n{ab.group(1)}\n\n"
                                fetched_content += f"**arXiv URL**: {url}\n"
                            else:
                                # 通用网页：提取纯文本
                                text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
                                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                                text = re.sub(r'<[^>]+>', ' ', text)
                                text = re.sub(r'\s+', ' ', text).strip()
                                fetched_content = f"## {resolved_title or url}\n\n{text[:5000]}\n"

                            console.print(f"  ✅ 内容已抓取 ({len(fetched_content)} 字)")
            except Exception as e:
                console.print(f"  ⚠️ URL 抓取失败: {e}")

        # ── 2. 智能文件命名 ──
        name_candidates = []

        title_in_body = re.search(r'(?:标题|title)[：:]\s*(.+)', body, re.IGNORECASE)
        if title_in_body:
            name_candidates.append(title_in_body.group(1).strip())

        if resolved_title:
            name_candidates.append(resolved_title)

        arxiv_id = re.search(r'(\d{4}\.\d{4,5})', body)
        if arxiv_id:
            name_candidates.append(f"arXiv_{arxiv_id.group(1)}")

        clean_title = re.sub(r'\[.*?\]\s*', '', issue.title).strip()
        if clean_title:
            name_candidates.append(clean_title)

        best_name = name_candidates[0] if name_candidates else f"issue_{issue.number}"
        safe_name = _slugify(best_name)
        md_path = raw_dir / f"{safe_name}.md"

        console.print(f"  📛 文件命名: {safe_name}.md")

        # ── 3. 提取元数据 ──
        metadata = {
            "source": "github-issue",
            "issue_number": issue.number,
            "title": resolved_title or clean_title or issue.title,
            "author": issue.user.login if issue.user else "unknown",
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "url": issue.html_url,
            "labels": [label.name for label in issue.labels],
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        # ── 4. 提取图片 ──
        images_info = await self._extract_images(body, raw_dir, safe_name)
        if self.config.ingest.process_images and images_info and self.llm:
            for img_info in images_info:
                desc = await self._describe_and_save(img_info, raw_dir)
                img_info["description"] = desc

        # ── 5. 构建最终 Markdown ──
        content = self._build_markdown(metadata, body, images_info)

        if fetched_content:
            content += f"\n\n## 抓取内容\n\n{fetched_content}\n"

        # ── 6. 写入文件 ──
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

        console.print(f"  💾 保存到: {md_path} ({md_path.stat().st_size:,} bytes)")
        return [md_path]

    async def _extract_images(
        self, body: str, output_dir: Path, prefix: str
    ) -> list[dict]:
        """从 Markdown 正文提取图片链接并下载到本地。"""
        image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        matches = re.findall(image_pattern, body)

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
        """下载单张图片到本地。"""
        if httpx is None:
            console.print(f"  ⚠️ httpx 未安装，跳过图片下载 [{url[:50]}...]")
            return None

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            ext_map = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "image/svg+xml": ".svg",
            }
            ext = ext_map.get(content_type, ".png")

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
        if not self.llm:
            console.print(f"  ⚠️ 跳过图片描述（LLM 未配置）")
            return ""
        try:
            description = await self.llm.describe_image(img_info["local_path"])

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

        if body.strip():
            lines.append("## 原始内容\n")
            lines.append(body)
            lines.append("")

        if images:
            lines.append("\n## 附件/图片\n")
            for img in images:
                lines.append(f"- **{img.get('alt', img['filename'])}**: `![[{img['filename']}]]`")
                if img.get("description"):
                    lines.append(f"  > {img['description'][:100]}...")
            lines.append("")

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    #  URL / 本地文件 摄入（原 EnhancedIngestEngine）
    # ═══════════════════════════════════════════════════════════

    async def ingest(self, target: str) -> IngestResult:
        """
        智能识别输入类型并执行对应的摄入策略。

        Args:
            target: URL 或本地文件路径
        """
        if target.startswith(("http://", "https://")):
            return await self._ingest_url(target)
        else:
            return await self._ingest_path(Path(target).expanduser())

    async def ingest_multiple(self, targets: list[str]) -> list[IngestResult]:
        """批量摄入多个目标。"""
        results = []
        for t in targets:
            try:
                result = await self.ingest(t)
                results.append(result)
            except Exception as e:
                results.append(IngestResult(
                    source=t,
                    success=False,
                    error_message=str(e),
                ))
        return results

    async def _ingest_url(self, url: str) -> IngestResult:
        """从 URL 摄入内容。"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if "arxiv.org" in domain:
            return await self._ingest_arxiv(url)
        if "github.com" in domain:
            return await self._ingest_github_url(url)
        return await self._ingest_webpage(url)

    async def _ingest_arxiv(self, url: str) -> IngestResult:
        """摄入 arXiv 论文。"""
        arxiv_match = re.search(r'(\d{4}\.\d{4,5})', url)
        if not arxiv_match:
            arxiv_match = re.search(r'abs/(\d+)', url)

        arxiv_id = arxiv_match.group(1) if arxiv_match else "unknown"
        title = f"arXiv-{arxiv_id}"

        content = f"# {title}\n\n> 来源: {url}\n\n## arXiv ID\n{arxiv_id}\n\n## 原始链接\n{url}\n"

        try:
            if httpx is not None:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(f"https://arxiv.org/abs/{arxiv_id}")
                    if resp.status_code == 200:
                        html = resp.text
                        title_match = re.search(r'<meta name="citation_title" content="([^"]+)"', html)
                        if title_match:
                            title = title_match.group(1)
                        abs_match = re.search(r'<meta name="citation_abstract" content="([^"]+)"', html)
                        if abs_match:
                            content = f"# {title}\n\n> 来源: [{url}]({url})\n\n## Abstract\n{abs_match.group(1)}\n"
                        authors_match = re.findall(r'<meta name="citation_author" content="([^"]+)"', html)
                        if authors_match:
                            content += f"\n## Authors\n{', '.join(authors_match)}\n"
        except Exception as e:
            content += f"\n> ⚠️ 获取元数据失败: {e}\n"

        output_file = await self._save_raw(content, title, source_type="arxiv")

        return IngestResult(
            source=url,
            source_path=str(output_file),
            doc_type="paper",
            size=output_file.stat().st_size if output_file.exists() else 0,
            success=True,
        )

    async def _ingest_github_url(self, url: str) -> IngestResult:
        """摄入 GitHub 仓库或文件 URL。"""
        content = f"# GitHub Source\n\n> 来源: [{url}]({url})\n\n"

        raw_base = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

        try:
            if httpx is not None:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(raw_base)
                    if resp.status_code == 200:
                        content += resp.text
                    else:
                        content += f"> ⚠️ 无法直接访问原始内容 ({resp.status_code})"
        except Exception as e:
            content += f"> ⚠️ 获取失败: {e}"

        title = Path(urlparse(url).path).name or "github-source"
        output_file = await self._save_raw(content, title, source_type="github")

        return IngestResult(
            source=url,
            source_path=str(output_file),
            doc_type="other",
            size=output_file.stat().st_size if output_file.exists() else 0,
            success=True,
        )

    async def _ingest_webpage(self, url: str) -> IngestResult:
        """通用网页摄入（保存为 Markdown）。"""
        content = f"# Web Page\n\n> 来源: [{url}]({url})\n\n"

        try:
            if httpx is not None:
                async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        html_text = resp.text
                        text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL)
                        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                        text = re.sub(r'<[^>]+>', ' ', text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        content += f"## 页面内容\n\n{text[:5000]}"
                    else:
                        content += f"> ⚠️ HTTP {resp.status_code}"
        except Exception as e:
            content += f"> ⚠️ 获取失败: {e}"

        title = urlparse(url).netloc.replace(".", "-")
        output_file = await self._save_raw(content, title, source_type="webpage")

        return IngestResult(
            source=url,
            source_path=str(output_file),
            doc_type="note",
            size=output_file.stat().st_size if output_file.exists() else 0,
            success=True,
        )

    async def _ingest_path(self, path: Path) -> IngestResult:
        """从本地文件路径摄入。"""
        if not path.exists():
            return IngestResult(source=str(path), success=False, error_message=f"文件不存在: {path}")

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return await self._ingest_pdf(path)
        if suffix in (".md", ".markdown", ".txt", ".rst"):
            return await self._ingest_text_file(path)
        if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            return await self._ingest_image(path)
        return await self._ingest_binary(path)

    async def _ingest_pdf(self, pdf_path: Path) -> IngestResult:
        """摄入 PDF 文件。"""
        today = datetime.now().strftime(self.config.ingest.date_format)
        dest_dir = self.raw_path / today
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_pdf = dest_dir / pdf_path.name
        shutil.copy2(pdf_path, dest_pdf)

        text_content = ""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages[:10]):
                    page_text = page.extract_text()
                    if page_text:
                        text_content += f"\n### Page {i+1}\n{page_text}\n"
        except ImportError:
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(pdf_path))
                for i, page in enumerate(reader.pages[:10]):
                    text_content += f"\n### Page {i+1}\n{page.extract_text() or ''}\n"
            except ImportError:
                text_content = f"\n> PDF 文件已归档，但缺少 PDF 解析库。\n>\n> 安装: pip install pdfplumber 或 pypdf\n"

        md_name = pdf_path.stem
        md_content = (
            f"# {md_name}\n\n"
            f"> 来源: `{pdf_path.name}` (本地文件)\n"
            f"> 投喂时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"> 类型: paper\n\n"
            f"## PDF 内容提取\n{text_content[:8000]}\n\n"
            f"## 附件\n- ![[{pdf_path.name}]]\n"
        )

        md_path = dest_dir / f"{md_name}.md"
        md_path.write_text(md_content, encoding="utf-8")

        total_size = dest_pdf.stat().st_size + md_path.stat().st_size
        return IngestResult(
            source=str(pdf_path),
            source_path=str(md_path),
            doc_type="paper",
            size=total_size,
            success=True,
        )

    async def _ingest_text_file(self, text_path: Path) -> IngestResult:
        """摄入文本/Markdown 文件。"""
        content = text_path.read_text(encoding="utf-8")
        title = text_path.stem

        output_file = await self._save_raw(
            content + f"\n\n---\n\n> 来源文件: `{text_path.name}`",
            title,
            source_type="local-text",
        )

        return IngestResult(
            source=str(text_path),
            source_path=str(output_file),
            doc_type=self._guess_doc_type(content),
            size=output_file.stat().st_size if output_file.exists() else 0,
            success=True,
        )

    async def _ingest_image(self, img_path: Path) -> IngestResult:
        """摄入图片文件（复制 + 创建描述占位）。"""
        today = datetime.now().strftime(self.config.ingest.date_format)
        dest_dir = self.raw_path / today
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_img = dest_dir / img_path.name
        shutil.copy2(img_path, dest_img)

        desc_content = (
            f"# 图片: {img_path.stem}\n\n"
            f"> 来源: `{img_path.name}` (本地图片)\n"
            f"> 投喂时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"![{img_path.stem}]({img_path.name})\n\n"
            f"*待 LLM 视觉描述处理*\n"
        )
        desc_md = dest_dir / f"{img_path.stem}.desc.md"
        desc_md.write_text(desc_content, encoding="utf-8")

        return IngestResult(
            source=str(img_path),
            source_path=str(dest_img),
            doc_type="other",
            size=dest_img.stat().st_size,
            success=True,
        )

    async def _ingest_binary(self, bin_path: Path) -> IngestResult:
        """摄入其他二进制文件（直接复制）。"""
        today = datetime.now().strftime(self.config.ingest.date_format)
        dest_dir = self.raw_path / today
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / bin_path.name
        shutil.copy2(bin_path, dest)

        return IngestResult(
            source=str(bin_path),
            source_path=str(dest),
            doc_type="other",
            size=dest.stat().st_size,
            success=True,
        )

    # ─── 通用工具方法 ────────────────────────────────────────────

    async def _save_raw(
        self, content: str, title: str, source_type: str = "unknown"
    ) -> Path:
        """保存内容到 raw/YYYY-MM-DD/ 目录。"""
        today = datetime.now().strftime(self.config.ingest.date_format)
        dest_dir = self.raw_path / today
        dest_dir.mkdir(parents=True, exist_ok=True)

        safe_name = _slugify(title)[:80]
        if not safe_name:
            safe_name = "untitled"
        output_file = dest_dir / f"{safe_name}.md"

        now_utc = datetime.now(timezone.utc).isoformat()
        full_content = (
            f"---\n"
            f'title: "{title}"\n'
            f"source: {source_type}\n"
            f"ingested_at: {now_utc}\n"
            f"---\n\n"
            f"{content}"
        )

        if output_file.exists():
            existing = output_file.read_text(encoding="utf-8")
            output_file.write_text(existing + "\n\n---\n\n" + content, encoding="utf-8")
        else:
            output_file.write_text(full_content, encoding="utf-8")

        return output_file

    @staticmethod
    def _guess_doc_type(content: str) -> str:
        """根据内容猜测文档类型。"""
        lower = content.lower()
        if any(kw in lower for kw in ["abstract", "introduction", "methodology", "arxiv", "@article"]):
            return "paper"
        if any(kw in lower for kw in ["# ", "## ", "笔记", "学习笔记", "reading note"]):
            return "note"
        return "other"


def _slugify(text: str) -> str:
    """将文本转换为安全的文件名。"""
    from slugify import slugify
    result = slugify(text, separator="_", lowercase=False)
    return result[:80] if len(result) > 80 else result


# ─── CLI 入口 ──────────────────────────────────────────────────────────────
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Lumina Wiki - Unified Ingest")
    parser.add_argument("--token", help="GitHub Token")
    parser.add_argument("--config", "-c", help="lumina.toml 路径")
    parser.add_argument("--issue", type=int, help="直接处理指定 Issue 编号")
    parser.add_argument("--dry-run", action="store_true", help="只显示将要处理的 Issue，不实际执行")
    parser.add_argument("target", nargs="?", help="URL 或本地文件路径（不指定则走 Issue 模式）")
    args = parser.parse_args()

    if args.token:
        import os
        os.environ["GITHUB_TOKEN"] = args.token

    config = load_config(args.config)
    engine = IngestEngine(config)

    if args.target:
        # URL / 文件模式
        result = await engine.ingest(args.target)
        print(f"\n{result}")
    else:
        # GitHub Issue 模式
        if args.dry_run:
            issues = engine.find_issues(issue_number=args.issue)
            if not issues:
                print("没有待处理的 Issue。")
            else:
                for issue in issues:
                    print(f"  #{issue.number}: {issue.title} (@{issue.user.login})")
            return

        files = await engine.ingest_all(issue_number=args.issue)
        console.print(f"\n✅ 摄入完成！共处理 {len(files)} 个文件")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
