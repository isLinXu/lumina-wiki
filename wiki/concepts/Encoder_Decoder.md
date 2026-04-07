---
title: "Encoder-Decoder"
type: architecture
created: 2026-04-07T00:44:00Z
status: seed
first_seen_in: Attention_Is_All_You_Need
tags: [architecture]
---

# Encoder-Decoder

**Encoder-Decoder** 是一种用于序列到序列任务的深度学习架构，通过编码器将输入序列转换为上下文相关的表示，再通过解码器生成输出序列。  
该结构通常由两个主要部分组成：编码器负责提取输入信息的特征，解码器则基于这些特征逐步生成目标序列。在现代模型中，如Transformer，自注意力机制被广泛用于增强模型对长距离依赖的捕捉能力。  
Encoder-Decoder 架构广泛应用于机器翻译、文本摘要和语音识别等领域，其核心思想在《Attention Is All You Need》论文中得到进一步优化和推广。

## 来源
- [[Attention_Is_All_You_Need]] — 首次发现

---
*由 Lumina Compiler 自动创建*
