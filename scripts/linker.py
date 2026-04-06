"""
Lumina Wiki - Auto Linker & Backlink Manager
管理 Wiki 页面间的反向链接关系。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .config import load_config, LuminaConfig


class AutoLinker:
    """自动链接管理器。"""

    def __init__(self, config: Optional[LuminaConfig] = None):
        self.config = config or load_config()
        self.wiki_path = Path(self.config.compiler.wiki_dir)
        # 反向链接索引文件
        self.backlink_index_path = self.wiki_path / ".backlinks.json"

    def scan_all_wikilinks(self) -> dict[str, list[str]]:
        """
        扫描所有 Wiki 页面的 [[wikilink]]，构建反向索引。
        Returns: {target_page: [source_page1, source_page2, ...]}
        """
        backlinks: dict[str, list[str]] = {}

        if not self.wiki_path.exists():
            return backlinks

        for md_file in self.wiki_path.rglob("*.md"):
            # 跳过隐藏文件和索引文件
            if md_file.name.startswith("."):
                continue
            
            source_name = md_file.stem
            content = md_file.read_text(encoding="utf-8")

            # 提取所有 [[link]]
            links = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]", content)

            for target in links:
                target = target.strip()
                if not target:
                    continue
                backlinks.setdefault(target.lower(), []).append(source_name)

        # 去重并保存索引
        for k in backlinks:
            backlinks[k] = list(dict.fromkeys(backlinks[k]))

        self._save_backlink_index(backlinks)
        return backlinks

    def get_backlinks(self, page_name: str) -> list[str]:
        """获取指向某页面的所有来源页面。"""
        index = self._load_backlink_index()
        return index.get(page_name.lower(), [])

    def update_page_backlinks(self, page_path: Path) -> str:
        """
        更新指定页面的反向链接区域。
        返回更新后的内容。
        """
        page_name = page_path.stem
        backlinks = self.get_backlinks(page_name)

        if not backlinks:
            return page_path.read_text(encoding="utf-8")

        content = page_path.read_text(encoding="utf-8")
        
        # 查找或创建反向链接区域
        backlink_section = "\n\n## 🔗 链入此页\n\n"
        for bl_source in sorted(set(backlinks)):
            if bl_source.lower() != page_name.lower():
                backlink_section += f"- [[{bl_source}]]\n"

        # 如果已有反向链接区域，替换；否则追加到末尾
        if "## 🔗 链入此页" in content:
            content = re.sub(
                r"## 🔗 链入此页.*",
                backlink_section,
                content,
                flags=re.DOTALL,
            )
        else:
            content = content.rstrip("\n") + "\n\n---\n" + backlink_section

        return content

    def _load_backlink_index(self) -> dict:
        """加载反向链接索引。"""
        if self.backlink_index_path.exists():
            return json.loads(self.backlink_index_path.read_text(encoding="utf-8"))
        return {}

    def _save_backlink_index(self, index: dict) -> None:
        """保存反向链接索引。"""
        self.wiki_path.mkdir(parents=True, exist_ok=True)
        self.backlink_index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _normalize_page_name(name: str) -> str:
    """规范化页面名称：统一大小写和分隔符。"""
    return name.strip().lower().replace("-", "_").replace(" ", "_").strip("_")


def find_broken_links(wiki_path: Path) -> list[dict]:
    """
    扫描 Wiki 中所有断链（[[link]] 指向不存在的页面）。
    返回 [{source, link, line}] 列表。
    
    名称匹配策略：
    - 大小写不敏感
    - `-` `_` ` ` 视为等价分隔符
    """
    broken: list[dict] = []

    if not wiki_path.exists():
        return broken

    # 收集所有存在的页面名称（规范化后）
    existing_pages: set[str] = set()
    for md_file in wiki_path.rglob("*.md"):
        if not md_file.name.startswith("."):
            existing_pages.add(_normalize_page_name(md_file.stem))

    # 检查每个页面的链接
    for md_file in wiki_path.rglob("*.md"):
        if md_file.name.startswith("."):
            continue

        content = md_file.read_text(encoding="utf-8")
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            matches = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", line)
            for link in matches:
                normalized = _normalize_page_name(link)
                if normalized and normalized not in existing_pages:
                    broken.append({
                        "source": str(md_file.relative_to(wiki_path)),
                        "link": link.strip(),
                        "line": i,
                    })

    return broken
