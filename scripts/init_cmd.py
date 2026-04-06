"""
Lumina Wiki - Init Command
初始化 Lumina Wiki 项目结构。
"""

from __future__ import annotations

from pathlib import Path


def run_init(target_path: Path) -> None:
    """在目标路径初始化 Lumina Wiki 项目结构。"""
    target = target_path.resolve()

    # 创建目录结构
    dirs = [
        "raw",
        "wiki/concepts",
        "wiki/papers", 
        "wiki/notes",
        "scripts",
        ".github/workflows",
    ]

    for d in dirs:
        p = target / d
        p.mkdir(parents=True, exist_ok=True)
        print(f"  📁 {d}/")

    # 创建 Home 页面
    home_content = """---
title: "Lumina Wiki Home"
type: index
created: 2026-01-01
---

# 🌙 Lumina Wiki

> **Read-only for Humans, Write-only for LLMs.**

## 📖 关于

这是你的个人知识编译器。通过 GitHub Issues 投喂素材，LLM 自动将其编译为结构化的知识库。

## 🗂️ 知识图谱入口

### 概念 (Concepts)
{待编译后自动填充}

### 论文 (Papers)
{待编译后自动填充}

### 笔记 (Notes)
{待编译后自动填充}

## 📊 统计
<!-- 由 Linter 自动更新 -->
| 指标 | 数值 |
|------|------|
| 总页面数 | 0 |
| 概念数 | 0 |
| 健康度 | -- |

---
*Lumina Compiler v1.1.0*
"""

    (target / "wiki" / "Home.md").write_text(home_content, encoding="utf-8")
    print("  📄 wiki/Home.md")

    # 创建 .gitkeep 保持空目录被跟踪
    for d in ["raw", "wiki/concepts", "wiki/papers", "wiki/notes"]:
        (target / d / ".gitkeep").touch()

    # 复制配置文件模板（如果不存在）
    config_template = target / "lumina.toml"
    if not config_template.exists():
        default_config = """[repository]
owner = "your-github-username"
name = "Lumina-Wiki"
branch = "main"

[ingest]
label = "lumina"
raw_dir = "raw"
process_images = true
close_after_ingest = true

[compiler]
wiki_dir = "wiki"
auto_link = true
summary_max_tokens = 500

[llm]
provider = "github-copilot"
model = "gpt-4o"
temperature = 0.3

[linking]
auto_link = true

[linting]
conflict_threshold = 0.2
suggest_issues = true
"""
        config_template.write_text(default_config, encoding="utf-8")
        print("  ⚙️  lumina.toml")

    print(f"\n✅ Lumina Wiki 已初始化于: {target}")
    print("\n下一步:")
    print("  1. 编辑 lumina.toml 配置仓库信息")
    print("  2. 设置 GITHUB_TOKEN 环境变量")
    print("  3. 运行: lumina ingest && lumina compile")
