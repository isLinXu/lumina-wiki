---
title: "Attention Is All You Need"
source: github-issue
issue_number: 1
author: gatilin
url: https://github.com/gatilin/Lumina-Wiki/issues/1
ingested_at: 2026-04-06T09:00:00Z
labels: ["lumina", "paper"]
---

# Attention Is All You Need

## 原始内容

本文提出了一种全新的网络架构——Transformer，完全基于注意力机制（Attention Mechanism），摒弃了传统的循环（Recurrence）和卷积（Convolution）结构。

### 核心贡献

1. **Self-Attention 机制**：允许模型在处理序列中的每个位置时，关注序列中所有其他位置的信息。计算复杂度为 O(n²·d)，其中 n 为序列长度，d 为维度。

2. **Multi-Head Attention**：将注意力机制并行执行多次（通常为 8 或 16 个 head），每个 head 关注不同的表示子空间。

3. **Positional Encoding**：由于模型不包含循环或卷积结构，使用正弦/余弦函数编码位置信息。

4. **Encoder-Decoder 架构**：编码器由 6 层相同的层堆叠而成，每层包含 Multi-Head Attention 和 Feed-Forward 网络；解码器类似但增加了 Cross-Attention。

### 实验结果

- 在 WMT 2014 英德翻译任务上达到 28.4 BLEU，超过此前最佳结果 2 个 BLEU 点
- 在 WMT 2014 英法翻译任务上达到 41.0 BLEU
- 训练速度比基于循环的模型快 10-100 倍
- 模型参数量约 65M（base）和 213M（big）

### 影响

Transformer 架构成为了后续 BERT、GPT、T5 等大语言模型的基础，开创了现代 NLP 的新纪元。FlashAttention 等后续工作进一步优化了 Self-Attention 的计算效率。

### 参考文献
- Vaswani et al., "Attention Is All You Need", NeurIPS 2017
- arXiv: https://arxiv.org/abs/1706.03762
