---
title: "反向传播重计算"
type: method
created: 2026-04-07T00:45:08Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [method]
---

# 反向传播重计算

**反向传播重计算** 是一种在训练神经网络时通过重新计算中间激活值来节省内存的优化方法。  
该方法在反向传播过程中避免存储所有中间结果，而是根据需要重新计算所需部分，从而减少显存占用，提升训练效率。这种方式在处理大规模模型时尤其重要，能够有效缓解内存瓶颈。  
反向传播重计算被广泛应用于深度学习框架中，例如在 FlashAttention 论文中，它被用来优化注意力机制的计算与内存使用，实现更高效的大规模模型训练。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
