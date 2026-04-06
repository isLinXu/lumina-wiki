"""Lumina Wiki — Deep Code Audit"""
import ast, sys, importlib, os, re, json
from pathlib import Path

os.chdir("/Users/gatilin/PycharmProjects/lumina-wiki-git")
sys.path.insert(0, ".")
issues = []

def warn(f, m): issues.append((f, m)); print(f"  ⚠️  {f}: {m}")
def ok(f, m=""): print(f"  ✅ {f}" + (f" ({m})" if m else ""))

print("═"*60 + "\nLumina Wiki — Deep Code Audit\n" + "═"*60)

# 1. Syntax
print("\n━━━ 1. Syntax & AST ━━━")
for py in sorted(Path("scripts").glob("*.py")):
    try:
        ast.parse(py.read_text())
        ok(py.name)
    except SyntaxError as e:
        warn(py.name, f"SyntaxError L{e.lineno}")

# 2. Import chain
print("\n━━━ 2. Imports ━━━")
for m in ["config","llm_client","linker","search","init_cmd","watcher","pipeline",
          "compiler","ingest","ingest_enhanced","query_engine","status_cmd","linter","cli"]:
    try:
        importlib.import_module(f"scripts.{m}")
        ok(m)
    except Exception as e:
        warn(m, str(e)[:80])

# 3. Config
print("\n━━━ 3. Config ━━━")
from scripts.config import load_config
cfg = load_config()
for n,v,e in [("owner",cfg.repository.owner,"isLinXu"),("name",cfg.repository.name,"lumina-wiki"),
              ("wiki_dir",cfg.compiler.wiki_dir,"wiki"),("raw_dir",cfg.ingest.raw_dir,"raw")]:
    ok(n,v) if v==e else warn("config",f"{n}={v!r} expected {e!r}")
try:
    [getattr(cfg,p) for p in ["raw_path","wiki_path","concepts_path","papers_path","notes_path"]]
    ok("config properties")
except AttributeError as e:
    warn("config", str(e))

# 4. Pipeline
print("\n━━━ 4. Pipeline ━━━")
src = Path("scripts/pipeline.py").read_text()
for method in ["pass1_diff","pass2_summarize","pass3_extract","pass4_write","pass5_postprocess","compile"]:
    ok(f"pipeline.{method}") if f"async def {method}" in src or f"def {method}" in src else warn("pipeline",f"Missing {method}")
from scripts.pipeline import _slugify
assert _slugify("Hello World") != "" and len(_slugify("a"*200)) <= 80
ok("_slugify")

# 5. Legacy compiler
print("\n━━━ 5. compiler.py ━━━")
src_c = Path("scripts/compiler.py").read_text()
warn("compiler","Still has 'if not dry_run' bug") if "if not dry_run:" in src_c else ok("compiler","dry_run OK")

# 6. Linter
print("\n━━━ 6. linter.py ━━━")
src_l = Path("scripts/linter.py").read_text()
warn("linter","imports get_token") if "get_token" in src_l else ok("linter","no get_token")
m = re.search(r"self\.wiki_path\s*=\s*Path\(self\.config\.compiler\.(\w+)\)", src_l)
if m:
    ok(f"linter wiki_path=config.compiler.{m.group(1)}") if m.group(1)=="wiki_dir" else warn("linter",f"uses {m.group(1)}")

# 7. Linker
print("\n━━━ 7. linker.py ━━━")
from scripts.linker import _normalize_page_name, find_broken_links
for inp,exp in [("Self-Attention","self_attention"),("BERT","bert"),(" X ","x")]:
    ok(f"norm({inp!r})") if _normalize_page_name(inp)==exp else warn("linker",f"norm({inp!r})!={exp!r}")
broken = find_broken_links(Path("wiki"))
ok(f"broken links: {len(broken)}")

# 8. Search
print("\n━━━ 8. search.py ━━━")
from scripts.search import BM25Engine, WikiSearcher
eng = BM25Engine()
eng.add_document("d1","hello world",{"title":"T1","tags":[]})
r = eng.search("hello")
ok("BM25 basic") if r and r[0].path=="d1" else warn("search","BM25 fail")
ok("BM25 empty") if not eng.search("") else warn("search","empty query")
ws = WikiSearcher(Path("wiki"))
wr = ws.search("Transformer")
ok(f"WikiSearcher: {len(wr.results)} results") if wr.results else warn("search","no wiki results")

# 9. CLI
print("\n━━━ 9. CLI ━━━")
src_cli = Path("scripts/cli.py").read_text()
for cmd in ["init","ingest","compile","search","query","lint","link","status","doctor","serve","full"]:
    ok(f"CLI:{cmd}") if f'"{cmd}"' in src_cli else warn("cli",f"missing {cmd}")
warn("cli",'nargs="." bug') if 'nargs="."' in src_cli else ok("cli nargs fix")

# 10. Actions
print("\n━━━ 10. Actions ━━━")
for wf in ["compile.yml","deploy-pages.yml"]:
    p = Path(f".github/workflows/{wf}")
    if not p.exists(): warn(wf,"missing"); continue
    ok(wf)

# 11. Wiki quality
print("\n━━━ 11. Wiki Output ━━━")
wiki = Path("wiki")
for md in sorted(wiki.rglob("*.md")):
    c = md.read_text(); rel=str(md.relative_to(wiki))
    probs = []
    if not c.startswith("---") and rel not in ["index.md","log.md"]: probs.append("no frontmatter")
    if len(c.strip())<50 and rel!="index.md": probs.append(f"short({len(c.strip())}c)")
    warn(f"wiki/{rel}","; ".join(probs)) if probs else ok(f"wiki/{rel}")

# 12. JSON
print("\n━━━ 12. JSON ━━━")
for jf in [".compiled.json",".backlinks.json",".compile-stats.json"]:
    p = wiki/jf
    if not p.exists(): warn(jf,"missing"); continue
    try: json.loads(p.read_text()); ok(jf)
    except: warn(jf,"invalid JSON")

# 13. HTML Dashboard
print("\n━━━ 13. Dashboard ━━━")
html = Path("docs/index.html").read_text()
for name,check in [("tabs","nav-tabs"),("dashboard","panel-dashboard"),("wiki","panel-wiki"),
    ("ingest","panel-ingest"),("manage","panel-manage"),("upload","upload-zone"),
    ("graph","graph"),("modal","modal"),("md render","renderMarkdown"),("issue link","issues/new"),
    ("repo url","isLinXu/lumina-wiki")]:
    ok(f"HTML:{name}") if check in html else warn("HTML",f"missing {name}")

# Summary
print("\n"+"═"*60)
if not issues:
    print("🎉 ZERO ISSUES — Project is clean!")
else:
    print(f"⚠️  {len(issues)} issues found:")
    for f,m in issues: print(f"  • {f}: {m}")
print("═"*60)
