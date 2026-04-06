# 🌙 Lumina Wiki

> **GitHub-native 个人知识编译器** — Read-only for Humans, Write-only for LLMs.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/Version-1.1.0-blue)](https://github.com/isLinXu/lumina-wiki)
[![Pages](https://img.shields.io/badge/Dashboard-GitHub%20Pages-brightgreen)](https://islinxu.github.io/lumina-wiki/)
[![Reference](https://img.shields.io/badge/Inspired-Karpathy%20LLM%20Wiki-orange)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
[![Reference](https://img.shields.io/badge/Architecture-sage--wiki-green)](https://github.com/xoai/sage-wiki)

---

## ✨ 一句话

**把素材扔进 GitHub，LLM 自动编译成结构化知识库。你只负责投喂和调用。**

---

## 💡 核心理念

受 [Karpathy 的 LLM Wiki 模式](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 启发。

```
传统 RAG:  每次"检索+合成"，无积累
Lumina:   LLM 增量式编译 Wiki → 知识复利增长
```

| 你 (Human) | LLM (Compiler) |
|------------|-----------------|
| 选择信息源 | 阅读并理解 |
| 提出问题 | 总结、提取实体 |
| 浏览审核 | 编写 Wiki 页面 |
| 探索方向 | 维护一致性 |
| 最终决策 | 更新交叉引用 |

---

## 🏗️ 架构

```
┌──────────┐    ┌──────────────┐    ┌────────────┐
│  投喂入口  │───▶│  5遍编译流水线  │───▶│  wiki/     │
│          │    │              │    │  (只读)    │
│ Issue    │    │ Pass1: Diff  │    │            │
│ URL      │    │ Pass2: Summ  │    │ concepts/  │
│ 文件     │    │ Pass3: Extr  │    │ papers/    │
│ PDF      │    │ Pass4: Write │    │ notes/     │
└──────────┘    │ Pass5: Post  │    │ comparisons│
                └──────┬───────┘    └────────────┘
                       │
                 ┌─────┴─────┐
                 │  LLM API   │
                 │ (4种Provider)│
                 └───────────┘
```

### 设计对比

| 维度 | sage-wiki | Lumina Wiki |
|------|-----------|-------------|
| 语言 | Go (单一二进制) | Python (AI 生态原生) |
| 存储 | SQLite + FTS5 | **纯 Git + Markdown/JSON** |
| 向量搜索 | BLOB 内置向量 | BM25 (Phase 2: +Vector) |
| MCP | 14 工具完整实现 | Phase 3 预留框架 |
| 投入方式 | URL/Path/文件夹 | **Issue + URL + Path + PDF** |
| 运行方式 | 本地 CLI | **GitHub Actions + CLI 双模式** |
| 配置 | config.yaml | lumina.toml |
| 核心理念 | Karpathy LLM Wiki | 同上 + **GitHub-Native** |

---

## 📁 完整项目结构

```
Lumina-Wiki/
├── CLAUDE.md                    # ⭐ Schema / LLM "宪法"
├── README.md                    # 本文件
├── LICENSE                      # MIT
├── lumina.toml                  # 项目配置
├── pyproject.toml               # Python 包定义
├── requirements.txt             # 依赖列表
│
├── raw/                         # 原始数据层（LLM 只读）
│   └── YYYY-MM-DD/
│       ├── paper.md             # 原始内容 (+ YAML front matter)
│       ├── paper.meta.json      # 元数据
│       ├── image.png            # 附件图片
│       └── image.png.desc.md    # AI 图片描述
│
├── wiki/                        # 知识层（LLM 全权管理）
│   ├── Home.md                  # 首页仪表盘
│   ├── index.md                 # 全局实体索引
│   ├── log.md                   # 编译日志（追加式）
│   ├── .compiled.json           # 编译状态索引
│   ├── .backlinks.json          # 反向链接索引
│   ├── .health-report.json      # 体检报告
│   │
│   ├── concepts/                # 概念页面 (algorithm, model, concept...)
│   ├── papers/                  # 论文总结
│   ├── notes/                   # 笔记整理
│   └── comparisons/             # 对比分析（query 归档）
│
├── scripts/                     # 核心 Python 脚本
│   ├── __init__.py
│   ├── cli.py                   # ⭐ 统一 CLI 入口 (12个命令)
│   ├── config.py                # 配置管理 (lumina.toml)
│   ├── llm_client.py            # LLM 统一客户端 (Copilot/OpenAI/Azure/Ollama)
│   ├── ingest.py                # Issue 摄入引擎 (GitHub Issue → raw/)
│   ├── ingest_enhanced.py        # 增强摄入 (URL/Path/PDF → raw/)
│   ├── pipeline.py              # ⭐ 5-Pass 编译流水线核心
│   ├── compiler.py              # 原始编译器 (兼容保留)
│   ├── search.py                # ⭐ BM25 混合搜索引擎
│   ├── query_engine.py          # ⭐ 带引用的问答系统
│   ├── linker.py                # 反向链接管理 + 断链检测
│   ├── linter.py                # 知识库体检 (健康度评分)
│   ├── status_cmd.py            # ⭐ 状态面板 + Doctor 诊断
│   ├── watcher.py               # ⭐ 文件监控模式 (--watch)
│   └── init_cmd.py              # 项目初始化
│
└── .github/
    ├── workflows/
    │   └── compile.yml          # ⭐ 3阶段 CI/CD (ingest→compile→lint)
    └── ISSUE_TEMPLATE/
        └── lumina_ingest.yml   # Issue 投喂模板
```

---

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/isLinXu/lumina-wiki.git
cd Lumina-Wiki

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化项目结构
python -m scripts.cli init .

# 4. 编辑配置
# 编辑 lumina.toml：填入 GitHub 用户名和 API Key

# 5. 设置 Token
export GITHUB_TOKEN='your-github-token'
export OPENAI_API_KEY='your-openai-key'  # 可选

# 6. 开始使用！
```

---

## 📖 使用指南

### 全部命令一览（对标 sage-wiki）

```bash
# 项目初始化
lumina init                          # 初始化项目结构

# 摄入素材（多种方式）
lumina ingest https://arxiv.org/abs/1706.03762   # arXiv 论文 URL
lumina ingest https://github.com/xxx/repo         # GitHub 仓库 URL
lumia ingest ./paper.pdf              # 本地 PDF
lumina ingest ./note.md               # 本地 Markdown
lumia ingest                          # 无参数=走 GitHub Issue 模式

# 编译
lumina compile                        # 增量编译 raw → wiki
lumina compile --watch                # 监控模式（自动编译）
lumina compile --fresh                # 完全重新编译
lumina compile --dry-run              # 只扫描不执行
lumina compile --re-extract           # 从已有摘要重新提取概念

# 搜索 & 问答
lumina search "attention mechanism"   # BM25 关键词搜索
lumina search "MoE" --tags=paper      # 标签过滤搜索
lumina query "MoE routing策略差异"     # 带引用问答
lumina query "FlashAttention vs SDPA" --archive  # 问答并归档

# 体检 & 诊断
lumina lint                           # 知识体检（断链/孤儿/冲突...）
lumina status                         # 状态面板（统计概览）
lumina doctor                         # 诊断检查（配置/API/索引）
lumina link --fix                     # 修复反向链接

# 完整流水线
lumina full                           # ingest → compile → lint
lumina full --dry-run                 # 试运行

# MCP Server (Phase 3)
lumina serve                          # 启动 MCP Server
```

### 场景 A：从零开始

```bash
# 1. 初始化
lumina init .

# 2. 投入论文（URL 或本地文件）
lumina ingest https://arxiv.org/abs/1706.03762
lumina ingest ./my-paper.pdf

# 3. 编译（自动执行 5-pass 流水线）
lumina compile

# 4. 查看
open -a Obsidian .                    # Obsidian 中查看 Wiki

# 5. 问答
lumina query "Transformer 的核心创新是什么？"

# 6. 体检
lumina lint
lumina status
```

### 场景 B：覆盖现有 Obsidian Vault

```bash
cd ~/Documents/MyVault
lumina init .
# 编辑 lumina.toml 配置 source/ignore 目录
lumina compile --watch               # 监控 vault 变化自动编译
```

### 场景 C：GitHub Actions 全自动

1. 推送代码到 GitHub
2. 在 Settings → Secrets 配置 `GITHUB_TOKEN` 和 `OPENAI_API_KEY`
3. 创建带 `lumina` label 的 Issue 投喂素材
4. Actions 自动完成：**Ingest → Compile → Lint → Commit**

---

## 🔧 5-Pass 编译流水线

参考 sage-wiki 的架构设计：

| Pass | 名称 | 功能 | 输出 |
|------|------|------|------|
| **1** | Diff | 扫描变更（增量检测） | 待处理文件列表 |
| **2** | Summarize | 结构化摘要生成 | 标题/要点/方法/结果 |
| **3** | Extract | 概念/实体提取 | 实体列表(类型+置信度) |
| **4** | Write | 增量撰写文章 | Wiki 页面(新建或追加) |
| **5** | Post | 后处理 | 索引/日志/反链 |

### 增量策略（关键设计）

```
概念页已存在？
  ├─ 是 → 追加新信息块，标注来源，不覆盖原有内容
  └─ 否 → 创建 seed 页面（由 LLM 写初始定义）
```

---

## 🔍 搜索与问答

### 混合搜索 (BM25)

支持关键词搜索 + 标签加权 + 标题加成：

```bash
lumina search "flash attention" --limit=5
lumina search "MoE" --tags=algorithm,paper
```

### 带引用问答

基于 Wiki 内容回答，每个论断注明来源页面：

```
❓ MoE 和 Dense 模型在推理效率上的差异是什么？

### 回答
MoE（混合专家模型）在推理时只激活部分参数...
（详见以下来源）

### 来源引用
- [[Mixture-of-Experts]]: MoE 的核心原理是...
- [[SparseMOE]]: 在实际部署中...

💡 建议：此答案值得归档 → 使用 --archive 参数
```

---

## 🩺 知识体检 (Linting)

自动检测以下问题：

| 检查项 | 严重度 | 说明 |
|--------|--------|------|
| 断链检测 | P0 | `[[link]]` 指向不存在页面 |
| 冲突检测 | P0 | 不同页面对同一事实矛盾描述 |
| 孤儿页面 | P1 | 没有任何页面引用它 |
| 种子页面 | P2 | 内容过短或待充实 |
| 缺失交叉引用 | P2 | 提到某概念但未加 wikilink |

健康评分：🟢 ≥90 | 🟡 70-89 | 🟠 50-69 | 🔴 <50

---

## ⚙️ 配置说明

编辑 `lumina.toml`：

```toml
[repository]
owner = "gatilin"              # GitHub 用户名
name = "Lumina-Wiki"           # 仓库名
branch = "main"

[ingest]
label = "lumina"                # Issue 摄入标签
raw_dir = "raw"                 # 原始素材目录
process_images = true           # 多模态图片描述
close_after_ingest = true       # 摄入后关闭 Issue

[compiler]
wiki_dir = "wiki"               # Wiki 输出根目录
auto_link = true                # 自动 wikilink
summary_max_tokens = 500        # 摘要最大长度
entity_confidence = 0.7         # 实体提取阈值

[llm]
provider = "github-copilot"     # github-copilot | openai | azure | ollama
model = "gpt-4o"
temperature = 0.3

[linking]                       # 反向链接配置
auto_link = true

[linting]                       # 体检配置
conflict_threshold = 0.2
suggest_issues = true
```

### CLAUDE.md（Schema 文件）

这是 LLM 编译器的"宪法"，定义了：
- 目录结构和命名约定
- 5-pass 编译流程规范
- 页面模板格式（YAML front matter）
- 实体分类体系（10 类）
- 日志格式、健康评分公式
- 与 sage-wiki 的差异说明

> **重要**: 此文件会被 LLM Agent 读取以理解如何维护你的 Wiki。修改它会改变编译行为。

---

## 🗺️ 开发路线图

### ✅ Phase 1 (v1.1.0 - Current)
- [x] 项目骨架 + 12 个 CLI 命令
- [x] 5-Pass 编译流水线（Diff→Summ→Extract→Write→Post）
- [x] Issue / URL / Path / PDF 四种摄入方式
- [x] BM25 混合搜索 + 带引用问答系统
- [x] 反向链接管理 + 断链检测
- [x] 知识体检 + 健康评分
- [x] Status 面板 + Doctor 诊断
- [x] Watch 监控模式
- [x] GitHub Actions 三阶段 CI/CD
- [x] CLAUDE.md Schema 定义
- [x] 编译日志 (log.md) + Source Provenance

### 🔜 Phase 2 (v1.2.0)
- [ ] 向量嵌入 + 语义搜索（BM25+Vector RRF 融合）
- [ ] LaTeX 导出插件
- [ ] Marp Slides 幻灯片生成
- [ ] Mermaid 图表自动绘制
- [ ] MCP Server 实现（14 个工具）

### 🔮 Phase 3 (v2.0.0)
- [ ] GitHub Models API 对接优化
- [ ] 2.5D 可视化知识图谱面板
- [ ] 冲突检测增强（语义级矛盾发现）
- [ ] 灵感推荐引擎（知识图谱空隙发现）

---

## 📐 设计哲学

> **Vibe-coding 理念**（Karpathy 风格）：用最直接的代码解决最核心的问题。
> 不预先设计严苛工程架构，而是让系统在使用中自然生长。

### 核心约束
1. **无数据库**：所有数据在 Git + 文本文件中
2. **GitHub-Native**：让 GitHub 做基础设施工作
3. **增量编译**：每次新素材让 Wiki 变得更智能（而非重建）
4. **人类只读**：wiki/ 由 LLM 拥有，人通过 Obsidian 阅读
5. **可追溯**：每条知识都有 Source Provenance

---

## 🙏 致谢与参考

- **[Andrej Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)** — 核心理念起源
- **[sage-wiki (xoai/sage-wiki)](https://github.com/xoai/sage-wiki)** — 5-pass 流水线、CLI 设计、搜索/Query/Status/Doctor 命令集的直接参考
- **[DPC Messenger (mikhashev/dpc-messenger)](https://github.com/mikhashev/dpc-messenger)** — AI Agent 架构设计、Knowledge Commits 概念的启发

---

## 📄 License

MIT License © 2026 gatilin
