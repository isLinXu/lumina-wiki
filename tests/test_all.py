"""
Lumina Wiki v1.1.0 — Comprehensive Test Suite
"""
import asyncio
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import AsyncMock
from datetime import datetime

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def record(test_name, passed, detail=""):
    results.append((test_name, passed, detail))
    status = PASS if passed else FAIL
    print(f"  {status}  {test_name}" + (f"  ({detail})" if detail else ""))


print("╔" + "═" * 58 + "╗")
print("║   Lumina Wiki v1.1.0 — Comprehensive Test Suite          ║")
print("║   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "                                      ║")
print("╚" + "═" * 58 + "╝")

# ═══ 1. Module Import ═══
print("\n━━━ 1. Module Import Tests ━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
modules = [
    "scripts.config", "scripts.llm_client", "scripts.linker", "scripts.search",
    "scripts.init_cmd", "scripts.watcher", "scripts.pipeline", "scripts.compiler",
    "scripts.ingest", "scripts.ingest_enhanced", "scripts.query_engine",
    "scripts.status_cmd", "scripts.linter", "scripts.cli",
]
for m in modules:
    try:
        __import__(m)
        record(f"import {m.split('.')[-1]}", True)
    except Exception as e:
        record(f"import {m.split('.')[-1]}", False, str(e)[:50])

# ═══ 2. Config ═══
print("\n━━━ 2. Config Management ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
from scripts.config import load_config
cfg = load_config()
record("load lumina.toml", cfg is not None)
record("repository.owner", cfg.repository.owner == "gatilin")
record("compiler.wiki_dir", cfg.compiler.wiki_dir == "wiki")
record("llm.provider valid", cfg.llm.provider in ["github-copilot", "openai", "azure", "ollama"])

# ═══ 3. Pipeline Pass 1: Diff ═══
print("\n━━━ 3. Pipeline Pass 1: Diff ━━━━━━━━━━━━━━━━━━━━━━━━━━")
from scripts.pipeline import CompilerPipeline

compiler = CompilerPipeline()
compiler._compiled_index = {"compiled": {}, "concepts": {}, "last_run": None}
diff = asyncio.get_event_loop().run_until_complete(compiler.pass1_diff())
record("diff detects files", len(diff.added) == 2, f"{len(diff.added)} added")

# ═══ 4. Pipeline Full (Mock LLM) ═══
print("\n━━━ 4. Pipeline Full Run (Mock LLM) ━━━━━━━━━━━━━━━━━━━")
# Clean
for d in ["wiki/concepts", "wiki/papers", "wiki/notes", "wiki/comparisons"]:
    p = Path(d)
    if p.exists():
        shutil.rmtree(p)
for f in ["wiki/.compiled.json", "wiki/.backlinks.json", "wiki/.compile-stats.json", "wiki/log.md", "wiki/index.md"]:
    p = Path(f)
    if p.exists():
        p.unlink()

mock_summary = json.dumps({
    "summary": "Transformer 架构论文摘要",
    "key_points": ["Self-Attention", "Multi-Head Attention"],
    "authors": "Vaswani", "methodology": "Attention",
    "results": "28.4 BLEU", "limitations": "O(n²)", "doc_type": "paper"
})
mock_entities = json.dumps({
    "entities": [
        {"name": "Transformer", "type": "model", "confidence": 0.98},
        {"name": "Self-Attention", "type": "algorithm", "confidence": 0.95},
    ]
})


async def mock_chat(messages, **kw):
    c = messages[-1]["content"] if messages else ""
    # 优先匹配更具体的关键词
    if "提取核心概念" in c or "分类体系" in c:
        return mock_entities
    if "结构化摘要" in c or "生成一个简洁的摘要" in c:
        return mock_summary
    if "百科条目" in c or "一句话定义" in c:
        return "**Transformer** 是基于注意力机制的模型架构。"
    return "**Transformer** 是基于注意力机制的模型架构。"


async def mock_json(messages, **kw):
    c = messages[-1]["content"] if messages else ""
    # 精确匹配 prompt 中的关键词来区分 pass2 vs pass3
    if "提取核心概念" in c or "分类体系" in c:
        return json.loads(mock_entities)
    if "结构化摘要" in c:
        return json.loads(mock_summary)
    return json.loads(mock_entities)


compiler3 = CompilerPipeline()
compiler3.llm.chat = mock_chat
compiler3.llm.extract_json = mock_json
compiler3.llm.summarize = AsyncMock(return_value="摘要")

stats = asyncio.get_event_loop().run_until_complete(compiler3.compile(fresh=True))
record("pipeline completes", stats.errors == 0, f"err={stats.errors}")
record("pass2: summarized", stats.summarized == 2, f"{stats.summarized}")
record("pass3: entities", stats.concepts_extracted > 0, f"{stats.concepts_extracted}")
record("pass4: articles", stats.articles_written == 2, f"{stats.articles_written}")
record("pass5: .compiled.json", Path("wiki/.compiled.json").exists())
record("pass5: log.md", Path("wiki/log.md").exists())
record("pass5: index.md", Path("wiki/index.md").exists())
record("pass5: .backlinks.json", Path("wiki/.backlinks.json").exists())

# Incremental
stats2 = asyncio.get_event_loop().run_until_complete(compiler3.compile())
record("incremental skip", stats2.summarized == 0, "0 re-summarized")

# ═══ 5. BM25 Search ═══
print("\n━━━ 5. BM25 Search ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
from scripts.search import WikiSearcher
searcher = WikiSearcher(Path("wiki"))
r = searcher.search("Transformer attention", limit=5)
record("search returns results", len(r.results) > 0, f"{len(r.results)}")
record("scores sorted", all(
    r.results[i].score >= r.results[i + 1].score
    for i in range(len(r.results) - 1)
))
record("empty query → 0", len(searcher.search("xyznonexistent").results) == 0)

# ═══ 6. Linker ═══
print("\n━━━ 6. Linker & Backlinks ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
from scripts.linker import AutoLinker, find_broken_links, _normalize_page_name
record("normalize -→_", _normalize_page_name("Self-Attention") == "self_attention")
record("normalize space→_", _normalize_page_name("Flash Attention") == "flash_attention")
bl = AutoLinker().scan_all_wikilinks()
record("backlinks indexed", len(bl) > 0, f"{len(bl)} targets")
broken = find_broken_links(Path("wiki"))
record("broken links ≈ 0", len(broken) <= 2, f"{len(broken)}")

# ═══ 7. Status ═══
print("\n━━━ 7. Status Panel ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
from scripts.status_cmd import get_status
info = get_status("wiki")
record("total pages > 0", info["total_pages"] > 0, f"{info['total_pages']}")
record("last_compile set", info["last_compile"] is not None)
record("health_score set", info["health_score"] is not None, f"{info['health_score']}")

# ═══ 8. CLI ═══
print("\n━━━ 8. CLI Commands ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
from scripts.cli import main
commands = ["init", "ingest", "compile", "search", "query",
            "lint", "link", "status", "doctor", "serve", "full"]
for cmd in commands:
    sys.argv = ["lumina", cmd, "--help"]
    try:
        main()
    except SystemExit as e:
        record(f"CLI: {cmd}", e.code == 0)
    except:
        record(f"CLI: {cmd}", False)

# ═══ 9. Output Quality ═══
print("\n━━━ 9. Output Quality ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
papers = list(Path("wiki/papers").glob("*.md"))
record("papers count", len(papers) == 2, f"{len(papers)}")
for p in papers:
    content = p.read_text()
    record(f"  {p.stem[:30]}: front matter", content.startswith("---"))
    record(f"  {p.stem[:30]}: wikilinks", "[[" in content)
concepts = list(Path("wiki/concepts").glob("*.md"))
record("concepts count", len(concepts) >= 2, f"{len(concepts)}")

# ═══ SUMMARY ═══
print("\n" + "═" * 60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f"  总测试: {total}")
print(f"  通过:   {passed} ✅")
print(f"  失败:   {failed} {'❌' if failed else ''}")
print(f"  通过率: {passed / total * 100:.1f}%")
print("═" * 60)

if failed:
    print("\n失败项目:")
    for name, ok, detail in results:
        if not ok:
            print(f"  ❌ {name}: {detail}")
else:
    print("\n🎉 ALL TESTS PASSED!")
