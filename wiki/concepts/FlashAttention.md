---
title: "FlashAttention"
type: algorithm
created: 2026-04-07T00:44:55Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [algorithm]
---

# FlashAttention

**FlashAttention** 是一种高效且内存优化的注意力算法，专为大规模深度学习模型设计。  
它通过重新组织计算流程，减少内存访问次数，从而在保持精度的同时提升计算速度，特别适用于长序列的注意力机制。该算法在不牺牲准确性的前提下，显著降低了显存占用，使得更大规模的模型训练成为可能。  
FlashAttention 被广泛应用于自然语言处理和视觉Transformer模型中，相关工作包括其优化版本 FlashAttention-2，进一步提升了性能和可扩展性。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
