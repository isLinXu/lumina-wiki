---
title: "Online Softmax"
type: method
created: 2026-04-08T00:44:32Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [method]
---

# Online Softmax

**Online Softmax** 是一种在在线学习或流数据处理中高效计算Softmax函数的方法。  
它通过逐步更新概率分布，避免一次性处理整个数据集，从而降低计算和存储开销。相比传统Softmax，Online Softmax 更适合实时或大规模数据场景。  
该方法被应用于注意力机制的优化中，如FlashAttention，以提升计算效率并减少内存占用，广泛用于自然语言处理和深度学习模型的加速。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
