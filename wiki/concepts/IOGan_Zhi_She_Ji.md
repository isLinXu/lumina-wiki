---
title: "IO感知设计"
type: concept
created: 2026-04-12T00:47:50Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [concept]
---

# IO感知设计

IO感知设计 是一种优化计算任务中输入/输出（IO）操作效率的设计方法，旨在减少数据搬运带来的性能瓶颈。  
该设计通过分析数据访问模式和存储结构，合理安排数据在不同存储层级间的流动，从而提升整体系统性能。它特别适用于需要频繁读写数据的场景，如大规模机器学习和高性能计算。  
典型应用包括高效注意力机制的实现，如 FlashAttention 中所采用的 IO 优化策略，显著降低了内存带宽需求并提高了计算效率。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
