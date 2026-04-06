"""
Lumina Wiki - Hybrid Search Engine
实现 BM25 关键词搜索 + 语义搜索（可选向量）的混合检索。

参考 sage-wiki 的 RRF (Reciprocal Rank Fusion) 策略。
当前版本：BM25 + 标签加权（Phase 2 可扩展为 BM25+Vector）。
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    console = Console()
except ImportError:
    console = None  # type: ignore


# ─── 数据结构 ────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """单条搜索结果。"""
    path: str           # wiki 内的相对路径
    title: str          # 页面标题
    content: str        # 匹配的内容片段
    score: float = 0.0  # 综合评分
    rrf_score: float = 0.0  # RRF 融合分数
    tags: list[str] = field(default_factory=list)
    match_type: str = ""  # bm25 | tag | title


@dataclass
class SearchResponse:
    """搜索响应。"""
    query: str
    results: list[SearchResult]
    total_hits: int
    search_time_ms: float = 0.0


# ─── BM25 引擎 ──────────────────────────────────────────────────────

class BM25Engine:
    """轻量级 BM25 搜索引擎，无需外部依赖。"""

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avg_dl = 0.0
        # doc_id -> {term: tf}
        self.doc_tf: dict[str, dict[str, int]] = {}
        # doc_id -> document length
        self.doc_lengths: dict[str, int] = {}
        # term -> df (文档频率)
        self.df: dict[str, int] = {}
        # doc_id -> full text
        self.doc_texts: dict[str, str] = {}
        # doc_id -> metadata
        self.doc_meta: dict[str, dict] = {}

    def add_document(self, doc_id: str, text: str, meta: dict | None = None) -> None:
        """添加文档到索引。"""
        terms = self._tokenize(text)
        self.doc_count += 1
        
        # TF
        tf: dict[str, int] = {}
        for t in terms:
            tf[t] = tf.get(t, 0) + 1

        self.doc_tf[doc_id] = tf
        self.doc_lengths[doc_id] = len(terms)
        self.doc_texts[doc_id] = text
        if meta:
            self.doc_meta[doc_id] = meta

        # DF
        for t in set(terms):
            self.df[t] = self.df.get(t, 0) + 1

        # 更新平均文档长度
        self.avg_dl = sum(self.doc_lengths.values()) / max(self.doc_count, 1)

    def search(
        self,
        query: str,
        top_k: int = 10,
        tag_boost: float = 2.0,
        title_boost: float = 1.5,
        required_tags: list[str] | None = None,
    ) -> list[SearchResult]:
        """
        执行 BM25 搜索。
        
        Args:
            query: 查询文本
            top_k: 返回结果数
            tag_boost: 匹配标签时的权重加成
            title_boost: 标题匹配的权重加成
            required_tags: 必须包含的标签过滤
        """
        query_terms = self._tokenize(query)

        if not query_terms or not self.doc_count:
            return []

        scores: list[tuple[str, float]] = []

        for doc_id, tf in self.doc_tf.items():
            score = 0.0
            has_required_tags = True

            for qt in query_terms:
                if qt not in self.df:
                    continue

                idf = math.log(
                    (self.doc_count - self.df[qt] + 0.5) / (self.df[qt] + 0.5) + 1.0
                )
                
                term_freq = tf.get(qt, 0)
                dl = self.doc_lengths.get(doc_id, 0)
                tf_component = (
                    (term_freq * (self.k1 + 1)) /
                    (term_freq + self.k1 * (1 - self.b + self.b * dl / max(self.avg_dl, 1)))
                )
                score += idf * tf_component

            # 标签加权
            meta = self.doc_meta.get(doc_id, {})
            doc_tags = [t.lower() for t in meta.get("tags", [])]

            if required_tags:
                req_lower = [t.lower() for t in required_tags]
                if not all(r in doc_tags or any(r in dt for dt in doc_tags) for r in req_lower):
                    has_required_tags = False

            for qt in query_terms:
                qt_lower = qt.lower()
                # 标签匹配
                if any(qt_lower in dt or dt in qt_lower for dt in doc_tags):
                    score *= tag_boost
                    break
                # 标题匹配
                title = meta.get("title", "")
                if qt_lower in title.lower():
                    score *= title_boost

            if has_required_tags and score > 0:
                scores.append((doc_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc_id, score in scores[:top_k]:
            text = self.doc_texts.get(doc_id, "")
            meta = self.doc_meta.get(doc_id, {})
            
            # 提取匹配片段
            snippet = self._extract_snippet(query_terms, text)

            results.append(SearchResult(
                path=doc_id,
                title=meta.get("title", doc_id),
                content=snippet,
                score=round(score, 4),
                tags=meta.get("tags", []),
            ))

        return results

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单分词器（支持中英文）。"""
        # 小写化 + 提取字母数字和中文
        tokens = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", text.lower())
        return tokens

    def _extract_snippet(self, query_terms: list[str], text: str, max_length: int = 200) -> str:
        """提取包含查询词的文本片段。"""
        lines = text.split("\n")
        best_line = ""
        best_score = 0

        for line in lines:
            line_lower = line.lower()
            score = sum(1 for qt in query_terms if qt.lower() in line_lower)
            if score > best_score:
                best_score = score
                best_line = line

        if best_line and len(best_line) > max_length:
            return best_line[:max_length] + "..."
        return best_line or (text[:max_length] + "..." if len(text) > max_length else text)


# ─── 搜索管理器 ──────────────────────────────────────────────────────

class WikiSearcher:
    """Lumina Wiki 的统一搜索接口。"""

    def __init__(self, wiki_path: Path | str):
        self.wiki_path = Path(wiki_path)
        self._bm25: BM25Engine | None = None
        self._built = False

    def _build_index(self) -> BM25Engine:
        """从 wiki 目录构建 BM25 索引。"""
        engine = BM25Engine()

        if not self.wiki_path.exists():
            return engine

        for md_file in self.wiki_path.rglob("*.md"):
            if md_file.name.startswith("."):
                continue
            
            rel_path = str(md_file.relative_to(self.wiki_path))
            content = md_file.read_text(encoding="utf-8")

            # 解析元数据
            meta = {"title": md_file.stem}
            fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if fm_match:
                fm_text = fm_match.group(1)
                for line in fm_text.split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip().strip('"').strip("'")
                        if k == "title":
                            meta["title"] = v
                        elif k == "tags":
                            try:
                                meta["tags"] = json.loads(v)
                            except Exception:
                                meta["tags"] = []

            engine.add_document(rel_path, content, meta)

        self._built = True
        self._bm25 = engine
        return engine

    def search(
        self,
        query: str,
        limit: int = 10,
        tags: list[str] | None = None,
    ) -> SearchResponse:
        """
        执行混合搜索。
        
        Args:
            query: 搜索关键词或自然语言问题
            limit: 最大结果数
            tags: 标签过滤
        """
        import time
        start = time.time()

        engine = self._build_index()
        results = engine.search(query, top_k=limit, required_tags=tags)

        elapsed = (time.time() - start) * 1000

        return SearchResponse(
            query=query,
            results=results,
            total_hits=len(engine.search(query, top_k=len(engine.doc_texts), required_tags=tags)),
            search_time_ms=round(elapsed, 1),
        )

    def format_results(self, response: SearchResponse) -> str:
        """格式化搜索结果为可读文本。"""
        if not response.results:
            return f"🔍 未找到与「{response.query}」相关的页面。\n\n建议：尝试其他关键词或检查拼写。"

        lines = [
            f"🔍 搜索「{response.query}」— 共 **{response.total_hits}** 个结果 ({response.search_time_ms}ms):\n"
        ]

        for i, r in enumerate(response.results, 1):
            lines.append(f"**{i}.** [{r.title}]({r.path}) *(score: {r.score})*")
            if r.content:
                lines.append(f"   > {r.content}")
            if r.tags:
                tags_str = ", ".join(f"`{t}`" for t in r.tags[:5])
                lines.append(f"   🏷️ {tags_str}")
            lines.append("")

        return "\n".join(lines)
