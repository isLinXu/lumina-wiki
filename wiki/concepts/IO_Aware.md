---
title: "IO-Aware"
type: concept
created: 2026-04-21T00:48:46Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [concept]
---

# IO-Aware

**IO-Aware** 是一种关注输入输出操作效率的计算设计原则。  
IO-Aware 旨在通过优化数据在内存与处理器之间的传输方式，减少 I/O 操作的开销，从而提升整体系统性能。它通常涉及数据布局、缓存利用和数据预取等策略，以降低延迟并提高吞吐量。  

在深度学习和高性能计算中，IO-Aware 设计有助于减少模型训练和推理过程中的数据搬运时间，使计算资源更高效地被利用。这种理念在处理大规模数据时尤为重要，能够显著改善系统的响应速度和资源利用率。  

FlashAttention 是一项典型的 IO-Aware 相关工作，它通过重新组织注意力机制的计算流程，减少了对显存的频繁访问，实现了更快且更节省内存的注意力计算。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
