"""
Lumina Wiki - Enhanced Ingest Engine
扩展摄入能力：支持 URL、本地文件路径、GitHub Issue 多种输入源。

对应 sage-wiki 的 `ingest <url|path>` 命令。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from .config import load_config, LuminaConfig


class EnhancedIngestEngine:
    """增强版摄入引擎。"""

    def __init__(self, config: LuminaConfig | None = None):
        self.config = config or load_config()
        self.raw_path = Path(self.config.ingest.raw_dir)

    async def ingest(self, target: str) -> IngestResult:
        """
        智能识别输入类型并执行对应的摄入策略。
        
        Args:
            target: URL 或本地文件路径
            
        Returns:
            摄入结果
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
                    source=target,
                    success=False,
                    error_message=str(e),
                ))
        return results

    async def _ingest_url(self, url: str) -> IngestResult:
        """从 URL 摄入内容。"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # arXiv URL 特殊处理
        if "arxiv.org" in domain:
            return await self._ingest_arxiv(url)

        # GitHub URL 特殊处理
        if "github.com" in domain:
            return await self._ingest_github_url(url)

        # 通用网页抓取
        return await self._ingest_webpage(url)

    async def _ingest_arxiv(self, url: str) -> IngestResult:
        """摄入 arXiv 论文。"""
        # 提取 arXiv ID
        arxiv_match = re.search(r'(\d{4}\.\d{4,5})', url)
        if not arxiv_match:
            arxiv_match = re.search(r'abs/(\d+)', url)
        
        arxiv_id = arxiv_match.group(1) if arxiv_match else "unknown"
        title = f"arXiv-{arxiv_id}"

        # 尝试获取摘要信息
        abstract_url = f"https://arxiv.org/abs/{arxiv_id}"
        content = f"# {title}\n\n> 来源: {url}\n\n## arXiv ID\n{arxiv_id}\n\n## 原始链接\n{url}\n"

        try:
            if httpx is not None:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(abstract_url)
                    if resp.status_code == 200:
                        html = resp.text
                        # 提取标题
                        title_match = re.search(r'<meta name="citation_title" content="([^"]+)"', html)
                        if title_match:
                            title = title_match.group(1)
                        # 提取摘要
                        abs_match = re.search(r'<meta name="citation_abstract" content="([^"]+)"', html)
                        if abs_match:
                            content = f"# {title}\n\n> 来源: [{url}]({url})\n\n## Abstract\n{abs_match.group(1)}\n"
                        # 提取作者
                        authors_match = re.findall(r'<meta name="citation_author" content="([^"]+)"', html)
                        if authors_match:
                            content += f"\n## Authors\n{', '.join(authors_match)}\n"
        except Exception as e:
            content += f"\n> ⚠️ 获取元数据失败: {e}\n"

        # 保存到 raw/
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

        # 尝试读取 README 或文件内容
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
                        # 简单 HTML → 文本转换
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

        # PDF 文件
        if suffix == ".pdf":
            return await self._ingest_pdf(path)

        # Markdown / 文本文件
        if suffix in (".md", ".markdown", ".txt", ".rst"):
            return await self._ingest_text_file(path)

        # 图片文件
        if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            return await self._ingest_image(path)

        # 其他二进制文件：复制到 raw/
        return await self._ingest_binary(path)

    async def _ingest_pdf(self, pdf_path: Path) -> IngestResult:
        """摄入 PDF 文件。"""
        # 复制 PDF 到 raw/
        today = datetime.now().strftime(self.config.ingest.date_format)
        dest_dir = self.raw_path / today
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        dest_pdf = dest_dir / pdf_path.name
        shutil.copy2(pdf_path, dest_pdf)

        # 尝试用 PyPDF2/pdfplumber 提取文本（如果可用）
        text_content = ""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages[:10]):  # 前10页
                    page_text = page.extract_text()
                    if page_text:
                        text_content += f"\n### Page {i+1}\n{page_text}\n"
        except ImportError:
            # 尝试 pypdf
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(pdf_path))
                for i, page in enumerate(reader.pages[:10]):
                    text_content += f"\n### Page {i+1}\n{page.extract_text() or ''}\n"
            except ImportError:
                text_content = f"\n> PDF 文件已归档，但缺少 PDF 解析库。\n>\n> 安装: pip install pdfplumber 或 pypdf\n"

        # 创建配套 MD
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
            source=str(path),
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

    # ─── 工具方法 ────────────────────────────────────────────────

    async def _save_raw(
        self, content: str, title: str, source_type: str = "unknown"
    ) -> Path:
        """保存内容到 raw/YYYY-MM-DD/ 目录。"""
        from slugify import slugify

        today = datetime.now().strftime(self.config.ingest.date_format)
        dest_dir = self.raw_path / today
        dest_dir.mkdir(parents=True, exist_ok=True)

        safe_name = slugify(title, separator="_")[:80]
        output_file = dest_dir / f"{safe_name}.md"

        # 构建完整的 front matter
        now_utc = datetime.now(timezone.utc).isoformat()
        full_content = (
            f"---\n"
            f'title: "{title}"\n'
            f"source: {source_type}\n"
            f"ingested_at: {now_utc}\n"
            f"---\n\n"
            f"{content}"
        )

        # 如果文件存在则追加
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
            return f"✅ Ingested: {self.source} (type: {self.doc_type}, {self.size:,} bytes) → {self.source_path}"
        else:
            return f"❌ Failed: {self.source} — {self.error_message}"
