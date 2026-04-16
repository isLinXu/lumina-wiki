---
title: "重计算策略"
type: method
created: 2026-04-16T00:50:16Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [method]
---

# 重计算策略

**重计算策略** 是一种通过重新计算而非存储中间结果来节省内存的方法。  
该策略在计算过程中选择性地丢弃某些中间状态，在后续需要时重新进行计算，从而减少内存占用，特别适用于内存受限的场景。这种方法在保持计算精度的同时，优化了资源利用效率。  
重计算策略被广泛应用于深度学习和高效注意力机制中，例如在 FlashAttention 论文中，通过重计算优化了自注意力的内存使用，提升了大规模模型的训练效率。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
