---
title: "Recomputation"
type: method
created: 2026-04-08T00:44:30Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [method]
---

# Recomputation

**Recomputation** 是一种通过重新计算中间结果来节省内存的方法。  
在深度学习中，为了减少显存占用，Recomputation 会在需要时重新执行某些计算步骤，而不是将所有中间结果都存储起来。这种方法可以在不显著增加计算时间的情况下，有效降低内存消耗。  

该技术常用于优化注意力机制等计算密集型操作，尤其适用于大规模模型训练。FlashAttention 等工作通过巧妙设计，实现了高效且精确的重计算策略。  

Recomputation 广泛应用于模型压缩、分布式训练以及资源受限环境下的深度学习任务，是提升系统效率的重要手段之一。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
