---
title: "FlashAttention-3"
type: algorithm
created: 2026-04-07T00:45:14Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [algorithm]
---

# FlashAttention-3

**FlashAttention-3** 是一种优化的注意力计算算法，旨在提升Transformer模型中自注意力机制的效率和内存利用率。  
FlashAttention-3 在前两代基础上进一步优化了计算流程和内存访问模式，通过分块计算和精确的内存调度，显著降低了计算复杂度和显存占用，同时保持了计算精度。它特别适用于大规模语言模型和长序列处理任务。  
该算法被广泛应用于现代大模型的训练与推理中，如优化Transformer架构、提升推理速度以及支持更长的输入序列，是当前高效注意力机制研究的重要进展之一。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
