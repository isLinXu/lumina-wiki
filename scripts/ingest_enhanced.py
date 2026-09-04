"""
Lumina Wiki - Enhanced Ingest (Compatibility Shim)

功能已合并到 ingest.py 的 IngestEngine 中。
本文件保留以向后兼容，EnhancedIngestEngine = IngestEngine 的别名。

迁移说明：
- 原 EnhancedIngestEngine 的所有方法（ingest, ingest_multiple, _ingest_url,
  _ingest_arxiv, _ingest_github_url, _ingest_webpage, _ingest_path, _ingest_pdf,
  _ingest_text_file, _ingest_image, _ingest_binary, _save_raw, _guess_doc_type）
  已全部移入 IngestEngine。
- IngestResult 类也移入 ingest.py。
- 请使用：from .ingest import IngestEngine, IngestResult
"""

from __future__ import annotations

from .ingest import IngestEngine, IngestResult

# 向后兼容别名
EnhancedIngestEngine = IngestEngine

__all__ = ["EnhancedIngestEngine", "IngestResult"]
