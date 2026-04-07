---
title: "[[FlashAttention]]: Fast and Memory-Efficient Exact Attention"
type: paper
created: 2026-04-06T02:27:42Z
source: raw/2026-04-06/FlashAttention_Paper.md
status: seed
tags: ["[[Transformer]]", "[[Self-Attention]]"]
author: "[[Vaswani]]"
---

# [[FlashAttention]]: Fast and Memory-Efficient Exact Attention

> 💡 **摘要**
> [[Transformer]] 架构论文摘要

| 属性 | 值 |
|------|-----|
| 作者 | [[Vaswani]] |
| 方法论 | Attention |
| 关键结果 | 28.4 [[BLEU]] |
| 类型 | paper |
| 来源 | `raw/2026-04-06/FlashAttention_Paper.md` |
| 编译时间 | 2026-04-06 |

## 关键要点

1. [[Self-Attention]]
2. [[Multi-Head Attention]]

## 方法论

Attention

## 关键结果

28.4 [[BLEU]]

## 局限性

O(n²)

## 相关实体

- **[[Transformer]]** (`model`) — 置信度: 98%
- **[[Self-Attention]]** (`algorithm`) — 置信度: 95%

---

*由 **Lumina Compiler** 于 2026-04-06T02:27:42Z 自动生成*
*来源: `raw/2026-04-06/FlashAttention_Paper.md`*

---

**▸ 更新于 2026-04-07T00:44:55Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低自注意力机制的内存占用，同时保持数学等价性。该方法在保持精度的前提下提升了计算效率，支持更长的序列长度，并已在多个框架中集成。

**相关实体**: [[FlashAttention]] | [[IO 感知设计]] | [[分块计算]] | [[重计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]] | [[PyTorch]] | [[xFormers]] | [[Triton]]
