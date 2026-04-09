---
title: "IO 感知"
type: concept
created: 2026-04-09T00:37:30Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [concept]
---

# IO 感知

**IO 感知** 是指在算法设计中考虑输入输出（I/O）操作效率，以减少数据搬运带来的性能瓶颈。  
IO 感知的核心在于优化数据访问模式，使计算过程尽可能减少对主存或外部存储的频繁读写，从而提升整体运行效率。这种设计思路在大规模数据处理和高性能计算中尤为重要。  
在 FlashAttention 的研究中，IO 感知被用于优化注意力机制的实现，通过减少中间结果的存储和传输，显著提升了模型的训练速度和内存利用率。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
