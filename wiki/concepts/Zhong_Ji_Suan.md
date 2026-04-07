---
title: "重计算"
type: method
created: 2026-04-07T00:45:03Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [method]
---

# 重计算

**重计算** 是一种通过重新计算中间结果来节省内存的方法。  
在深度学习中，重计算技术通过牺牲额外的计算时间来减少对显存的占用，适用于内存受限的场景。它通常在反向传播过程中重新生成前向计算的中间值，而非全程存储。  
该方法被广泛应用于高效注意力机制中，如 FlashAttention，以提升模型训练的效率和可扩展性。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
