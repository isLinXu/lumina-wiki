"""
Lumina Wiki — Dashboard Data Generator
从 wiki/ 目录读取所有 Markdown 文件，生成 docs/wiki-data.js 供前端使用。
由 GitHub Actions 在编译后自动运行，或本地手动执行。

用法: python scripts/build_dashboard.py
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .linker import AutoLinker, find_broken_links


def build_dashboard_data(wiki_dir: str = "wiki", raw_dir: str = "raw", output: str = "docs/wiki-data.js") -> dict:
    """
    扫描 wiki/ 和 raw/ 目录，生成 Dashboard 前端所需的 JSON 数据。
    """
    wiki = Path(wiki_dir)
    raw = Path(raw_dir)
    out = Path(output)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {},
        "papers": [],
        "concepts": [],
        "notes": [],
        "raw": [],
        "backlinks": {},
        "log": "",
        "graph": {"nodes": [], "edges": []},
    }

    # ── Stats ──
    concepts_dir = wiki / "concepts"
    papers_dir = wiki / "papers"
    notes_dir = wiki / "notes"

    concept_count = len(list(concepts_dir.glob("*.md"))) if concepts_dir.exists() else 0
    paper_count = len(list(papers_dir.glob("*.md"))) if papers_dir.exists() else 0
    note_count = len(list(notes_dir.glob("*.md"))) if notes_dir.exists() else 0
    total = concept_count + paper_count + note_count

    raw_count = len(list(raw.rglob("*.md"))) if raw.exists() else 0

    # Backlinks
    bl_path = wiki / ".backlinks.json"
    backlinks = {}
    bl_count = 0
    if bl_path.exists():
        try:
            backlinks = json.loads(bl_path.read_text(encoding="utf-8"))
            bl_count = sum(len(v) for v in backlinks.values())
        except Exception:
            pass

    # Health
    broken = find_broken_links(wiki)
    health = 100.0
    health -= min(len(broken) * 2, 30)
    seed_count = 0
    if concepts_dir.exists():
        for md in concepts_dir.glob("*.md"):
            c = md.read_text(encoding="utf-8")
            if "status: seed" in c or len(c.strip()) < 150:
                seed_count += 1
    health -= min(seed_count * 0.5, 5)
    health = max(0, round(health, 1))

    # Last compile
    compiled_path = wiki / ".compiled.json"
    last_compile = ""
    if compiled_path.exists():
        try:
            cd = json.loads(compiled_path.read_text(encoding="utf-8"))
            last_compile = cd.get("last_run", "")[:19].replace("T", " ") + " UTC"
        except Exception:
            pass

    data["stats"] = {
        "total": total,
        "concepts": concept_count,
        "papers": paper_count,
        "notes": note_count,
        "raw_files": raw_count,
        "backlinks": bl_count,
        "health": health,
        "lastCompile": last_compile,
    }

    # ── Pages ──
    def parse_page(md_path: Path, page_type: str) -> dict:
        content = md_path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)

        title = meta.get("title", md_path.stem.replace("_", " "))
        excerpt = ""
        # 取摘要块或前 200 字
        bq = re.search(r"> 💡 \*\*摘要\*\*\s*\n> (.+)", body)
        if bq:
            excerpt = bq.group(1)[:200]
        elif body:
            clean = re.sub(r"\[?\[([^\]]+)\]\]?", r"\1", body)
            clean = re.sub(r"[#*|`>-]", "", clean).strip()
            excerpt = clean[:200]

        tags = meta.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = [t.strip() for t in tags.split(",")]
        # Clean wikilink syntax from tags
        tags = [re.sub(r"\[\[|\]\]", "", str(t)) for t in tags]

        return {
            "id": md_path.stem.lower().replace(" ", "_"),
            "title": title,
            "path": str(md_path),
            "type": page_type,
            "excerpt": excerpt,
            "tags": tags[:8],
            "author": meta.get("author", ""),
            "date": meta.get("created", "")[:10],
            "content": content,
        }

    if papers_dir.exists():
        for md in sorted(papers_dir.glob("*.md")):
            data["papers"].append(parse_page(md, "paper"))

    if concepts_dir.exists():
        for md in sorted(concepts_dir.glob("*.md")):
            data["concepts"].append(parse_page(md, "concept"))

    if notes_dir.exists():
        for md in sorted(notes_dir.glob("*.md")):
            data["notes"].append(parse_page(md, "note"))

    # ── Raw files ──
    if raw.exists():
        for md in sorted(raw.rglob("*.md")):
            if md.name.startswith(".") or md.name.endswith(".desc.md"):
                continue
            data["raw"].append({
                "name": md.name,
                "date": md.parent.name if re.match(r"\d{4}-\d{2}-\d{2}", md.parent.name) else "",
                "size": f"{md.stat().st_size / 1024:.1f} KB",
                "path": str(md),
            })

    # ── Backlinks ──
    data["backlinks"] = backlinks

    # ── Log ──
    log_path = wiki / "log.md"
    if log_path.exists():
        data["log"] = log_path.read_text(encoding="utf-8")

    # ── Knowledge Graph ──
    all_pages = data["papers"] + data["concepts"] + data["notes"]
    nodes = []
    edges_set = set()

    # Position nodes in a circle layout
    import math
    n = len(all_pages)
    for i, page in enumerate(all_pages):
        angle = (2 * math.pi * i) / max(n, 1)
        # Map to 15-85% range
        x = 50 + 35 * math.cos(angle)
        y = 50 + 35 * math.sin(angle)

        node_type = "paper" if page["type"] == "paper" else "algorithm" if page["type"] == "concept" else "model"
        nodes.append({
            "id": page["id"],
            "label": page["title"][:25],
            "type": node_type,
            "x": round(x, 1),
            "y": round(y, 1),
        })

    # Edges from wikilinks
    page_ids = {p["id"] for p in all_pages}
    for page in all_pages:
        links = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", page.get("content", ""))
        for link in links:
            target_id = link.strip().lower().replace("-", "_").replace(" ", "_")
            if target_id in page_ids and target_id != page["id"]:
                edge = tuple(sorted([page["id"], target_id]))
                edges_set.add(edge)

    data["graph"] = {"nodes": nodes, "edges": [list(e) for e in edges_set]}

    # ── Write output ──
    out.parent.mkdir(parents=True, exist_ok=True)
    js_content = f"// Auto-generated by build_dashboard.py at {data['generated_at']}\nconst WIKI_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};\n"
    out.write_text(js_content, encoding="utf-8")

    print(f"✅ Dashboard data generated: {out}")
    print(f"   Pages: {total} (📑{paper_count} 💡{concept_count} 📝{note_count})")
    print(f"   Raw: {raw_count}, Backlinks: {bl_count}, Health: {health}")

    return data


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 YAML front matter。"""
    meta = {}
    fm = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if fm:
        for line in fm.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                v = v.strip().strip('"').strip("'")
                if v.startswith("["):
                    try:
                        v = json.loads(v)
                    except Exception:
                        pass
                meta[k] = v
        return meta, fm.group(2)
    return meta, content


if __name__ == "__main__":
    build_dashboard_data()
