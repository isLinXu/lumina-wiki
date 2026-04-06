"""
Lumina Wiki - Query System (问答系统)
基于 Wiki 内容的带引用问答功能。

参考 sage-wiki 的 query 命令和 Karpathy LLM Wiki 的 Query 规范：
- 基于 Wiki 内容回答（非凭空生成）
- 每个论断必须注明来源页面
- 有价值的答案应归档回 Wiki
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import LuminaConfig, load_config
from .llm_client import LLMClient
from .search import WikiSearcher, SearchResponse


class QueryEngine:
    """
    Lumina Wiki 问答引擎。
    
    工作流程：
    1. 搜索相关 Wiki 页面
    2. 将上下文 + 问题发送给 LLM
    3. 返回带引用的回答
    4. （可选）将答案归档到 Wiki
    """

    def __init__(self, config: LuminaConfig | None = None):
        self.config = config or load_config()
        self.llm = LLMClient(self.config)
        self.wiki_path = Path(self.config.compiler.wiki_dir)
        self.comparisons_path = self.wiki_path / "comparisons"

    async def ask(
        self,
        question: str,
        top_k: int = 5,
        archive: bool = False,
        output_mode: str = "terminal",
    ) -> QueryResult:
        """
        对 Wiki 提问并返回引用式回答。
        
        Args:
            question: 自然语言问题
            top_k: 检索的相关页面数
            archive: 是否将答案归档到 wiki/comparisons/
            output_mode: terminal | json | quiet
        """
        # Step 1: 检索相关内容
        searcher = WikiSearcher(self.wiki_path)
        search_result = searcher.search(question, limit=top_k)

        if not search_result.results:
            return QueryResult(
                question=question,
                answer=f"⚠️ 在 Wiki 中未找到与「{question}」相关的内容。\n\n建议：先通过 Issue 投喂相关素材。",
                sources=[],
                archived=False,
            )

        # Step 2: 构建上下文
        context_parts = []
        source_refs = []
        for i, r in enumerate(search_result.results, 1):
            try:
                full_content = (self.wiki_path / r.path).read_text(encoding="utf-8")
            except FileNotFoundError:
                full_content = r.content

            # 截断过长内容
            context_parts.append(
                f"[{i}] {r.title} (来源: {r.path})\n"
                f"{full_content[:3000]}"
            )
            source_refs.append({"path": r.path, "title": r.title})

        context_text = "\n\n---\n\n".join(context_parts)

        # Step 3: LLM 生成回答
        prompt = f"""你是 Lumina Wiki 的知识问答助手。请**仅基于提供的 Wiki 内容**回答用户的问题。

## 重要规则
1. **严格基于给定内容回答**，不要使用你的外部知识
2. 每个关键论断必须标注来源 `[编号]`
3. 如果内容不足以完整回答，明确说明哪些信息缺失
4. 使用中文回答
5. 保持客观、专业、准确

## Wiki 内容（参考材料）
{context_text}

## 用户问题
{question}

## 输出格式
### 回答
（你的详细回答）

### 来源引用
- [1] [[页面名]]: 相关说明...
- ...

### 💡 建议（可选）
如果这个答案值得长期保存，可以归档到 wiki/comparisons/
"""

        answer = await self.llm.chat([{"role": "user", "content": prompt}])

        # Step 4: 可选归档
        archived_path = ""
        if archive:
            archived_path = await self._archive_answer(question, answer, source_refs)

        result = QueryResult(
            question=question,
            answer=answer,
            sources=source_refs,
            archived=bool(archived_path),
            archive_path=str(archived_path),
            pages_searched=len(search_result.results),
        )

        # 输出
        if output_mode == "terminal":
            print(result.format_terminal())
        elif output_mode == "json":
            print(result.to_json())

        return result

    async def _archive_answer(
        self, question: str, answer: str, sources: list[dict],
    ) -> Path:
        """将有价值的问答归档到 comparisons/ 目录。"""
        self.comparisons_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        safe_q = question[:40].replace(" ", "_").replace("/", "_")
        filename = f"{timestamp}_{safe_q}.md"
        filepath = self.comparisons_path / filename

        content = f"""---
type: comparison
created: {timestamp}
source_question: "{question}"
sources: {[s['path'] for s in sources]}
tags: [auto-generated]
---

# Q: {question}

## 回答

{answer}

## 来源
"""
        for i, src in enumerate(sources, 1):
            content += f"- [{src['title']}]({src['path']})\n"

        content += "\n---\n*由 Lumina Query 自动归档*\n"

        filepath.write_text(content, encoding="utf-8")
        return filepath


class QueryResult:
    """问答结果。"""

    def __init__(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        archived: bool = False,
        archive_path: str = "",
        pages_searched: int = 0,
    ):
        self.question = question
        self.answer = answer
        self.sources = sources
        self.archived = archived
        self.archive_path = archive_path
        self.pages_searched = pages_searched

    def format_terminal(self) -> str:
        """格式化为终端输出。"""
        parts = []
        parts.append(f"\n{'='*60}")
        parts.append(f"❓ {self.question}")
        parts.append(f"{'='*60}\n")
        parts.append(self.answer)

        if self.archive_path:
            parts.append(f"\n💾 已归档至: `{self.archive_path}`")

        parts.append(f"\n📚 参考了 {len(self.sources)} 个 Wiki 页面")
        return "\n".join(parts)

    def to_json(self) -> str:
        """序列化为 JSON。"""
        return json.dumps({
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources,
            "archived": self.archived,
            "archive_path": self.archive_path,
            "pages_searched": self.pages_searched,
        }, ensure_ascii=False, indent=2)
