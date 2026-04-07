---
title: "Multi-Head Attention"
type: algorithm
created: 2026-04-07T00:43:55Z
status: seed
first_seen_in: Attention_Is_All_You_Need
tags: [algorithm]
---

# Multi-Head Attention

**Multi-Head Attention** 是一种在深度学习中用于捕捉不同语义关系的注意力机制，通过并行计算多个注意力头来增强模型对输入信息的多角度理解。  
该机制将输入分成多个子空间，每个子空间独立计算注意力权重，再将结果拼接并线性变换，从而提升模型对复杂模式的感知能力。它能够同时关注不同位置的信息，提高模型的表达能力。  
Multi-Head Attention 首次在论文《Attention Is All You Need》中被提出，广泛应用于Transformer模型，是现代自然语言处理任务的核心组件之一。

## 来源
- [[Attention_Is_All_You_Need]] — 首次发现

---
*由 Lumina Compiler 自动创建*
