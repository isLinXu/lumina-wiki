---
title: "在线 Softmax"
type: algorithm
created: 2026-04-07T00:45:05Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [algorithm]
---

# 在线 Softmax

**在线 Softmax** 是一种在计算过程中逐步处理输入并实时生成输出的 Softmax 算法，适用于大规模或流式数据场景。  
该方法通过优化内存访问和计算顺序，在保持数值稳定性的同时提升计算效率，特别适合需要低延迟和高吞吐量的应用。它与传统 Softmax 的区别在于无需一次性加载全部数据，而是按需处理。  
在线 Softmax 被广泛应用于注意力机制中，如 FlashAttention 论文中提到的高效注意力计算，显著降低了内存占用并提升了训练速度。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
