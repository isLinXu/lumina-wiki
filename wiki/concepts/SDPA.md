---
title: "SDPA"
type: tool
created: 2026-04-08T00:44:44Z
status: seed
first_seen_in: FlashAttention_Fast_and_Memory_Efficient_Exact_Attention
tags: [tool]
---

# SDPA

**SDPA** 是一种用于加速注意力计算的工具，全称为 Scaled Dot-Product Attention。  
SDPA 通过优化矩阵运算和内存访问模式，提高了自注意力机制的效率，尤其在处理长序列时表现优异。它通过缩放点积来计算注意力权重，是现代Transformer模型的核心组件之一。  
SDPA 被广泛应用于各种自然语言处理任务中，如机器翻译和文本生成，在FlashAttention等高效实现中得到了进一步优化和推广。

## 来源
- [[FlashAttention_Fast_and_Memory_Efficient_Exact_Attention]] — 首次发现

---
*由 Lumina Compiler 自动创建*
