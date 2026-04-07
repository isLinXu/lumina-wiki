---
title: "IO 感知设计"
type: concept
created: 2026-04-07T00:44:57Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [concept]
---

# IO 感知设计

**IO 感知设计** 是一种在算法和系统设计中考虑输入输出（I/O）效率，以减少数据搬运开销、提升整体性能的设计方法。  
IO 感知设计通过优化数据访问模式、减少不必要的数据读写，使计算过程更贴近存储结构，从而降低延迟并提高吞吐量。这种设计在大规模数据处理和高性能计算中尤为重要。  
典型应用包括高效注意力机制的实现，如 FlashAttention，它通过 IO 感知设计显著提升了自注意力计算的内存效率和速度，适用于大规模语言模型训练与推理。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
