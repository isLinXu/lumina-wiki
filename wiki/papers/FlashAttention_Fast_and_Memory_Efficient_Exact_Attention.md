---
title: "[[FlashAttention]]: Fast and Memory-Efficient Exact Attention"
type: paper
created: 2026-04-06T02:27:42Z
source: raw/2026-04-06/FlashAttention_Paper.md
status: seed
tags: ["[[Transformer]]", "[[Self-Attention]]"]
author: "[[Vaswani]]"
---

# [[FlashAttention]]: Fast and Memory-Efficient Exact Attention

> 💡 **摘要**
> [[Transformer]] 架构论文摘要

| 属性 | 值 |
|------|-----|
| 作者 | [[Vaswani]] |
| 方法论 | Attention |
| 关键结果 | 28.4 [[BLEU]] |
| 类型 | paper |
| 来源 | `raw/2026-04-06/FlashAttention_Paper.md` |
| 编译时间 | 2026-04-06 |

## 关键要点

1. [[Self-Attention]]
2. [[Multi-Head Attention]]

## 方法论

Attention

## 关键结果

28.4 [[BLEU]]

## 局限性

O(n²)

## 相关实体

- **[[Transformer]]** (`model`) — 置信度: 98%
- **[[Self-Attention]]** (`algorithm`) — 置信度: 95%

---

*由 **[[Lumina]] Compiler** 于 2026-04-06T02:27:42Z 自动生成*
*来源: `raw/2026-04-06/FlashAttention_Paper.md`*

---

**▸ 更新于 2026-04-07T00:44:55Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低自注意力机制的内存占用，同时保持数学等价性。该方法在保持精度的前提下提升了计算效率，支持更长的序列长度，并已在多个框架中集成。

**相关实体**: [[FlashAttention]] | [[IO 感知设计]] | [[分块计算]] | [[重计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]] | [[PyTorch]] | [[xFormers]] | [[Triton]]


---

**▸ 更新于 2026-04-08T00:44:27Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低自注意力机制的内存占用，同时保持数学等价性。该方法在多个基准测试中表现出色，提升了大规模模型训练效率。

**相关实体**: [[FlashAttention]] | [[Tiling]] | [[Recomputation]] | [[Online Softmax]] | [[GPT-2]] | [[BERT-large]] | [[A100]] | [[Hopper]] | [[PyTorch]] | [[SDPA]]


---

**▸ 更新于 2026-04-09T00:37:30Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低自注意力机制的内存占用，同时保持数学等价性。该方法在多个基准测试中表现出色，提升了大规模模型训练效率。

**相关实体**: [[FlashAttention]] | [[IO 感知]] | [[分块计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]]


---

**▸ 更新于 2026-04-10T00:44:34Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低自注意力机制的内存占用，同时保持数学等价性。该方法优化了GPU内存访问效率，在多个基准测试中表现出色。

**相关实体**: [[FlashAttention]] | [[IO 感知]] | [[分块计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]]


---

**▸ 更新于 2026-04-11T00:42:05Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低自注意力机制的内存占用，同时保持数学等价性。该方法在保持精度的前提下，提升了大规模序列处理能力，并在多个基准测试中实现了显著加速。

**相关实体**: [[FlashAttention]] | [[IO 感知]] | [[分块计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]] | [[PyTorch]]


---

**▸ 更新于 2026-04-12T00:47:50Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低自注意力机制的内存占用，同时保持数学等价性。该方法优化了GPU内存访问效率，在多个基准测试中表现出色。

**相关实体**: [[FlashAttention]] | [[IO感知设计]] | [[分块计算策略]] | [[在线Softmax技术]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]]


---

**▸ 更新于 2026-04-13T00:48:26Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低Self-Attention的内存占用，同时保持数学等价性。该方法在多个基准测试中展现出显著的加速效果，已广泛集成到主流深度学习框架中。

**相关实体**: [[FlashAttention]] | [[IO 感知]] | [[分块计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]] | [[PyTorch]]


---

**▸ 更新于 2026-04-13T09:02:30Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出FlashAttention算法，通过分块计算和重计算策略显著降低自注意力机制的内存占用，同时保持数学等价性。该方法在多个基准测试中表现出色，提升了大规模模型训练效率。

**相关实体**: [[FlashAttention]] | [[IO感知设计]] | [[分块计算]] | [[重计算]] | [[在线Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]]


---

**▸ 更新于 2026-04-14T00:49:12Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出 [[FlashAttention]] 算法，通过分块计算和重计算策略显著降低 [[Self-Attention]] 的内存占用，同时保持数学等价性。该方法在多个任务中实现了显著的加速和扩展性提升。

**相关实体**: [[FlashAttention]] | [[IO 感知]] | [[分块计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]] | [[PyTorch]] | [[xFormers]] | [[Triton]]


---

**▸ 更新于 2026-04-15T00:48:46Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出 [[FlashAttention]] 算法，通过分块计算和重计算策略显著降低 [[Self-Attention]] 的内存占用，同时保持数学等价性。该方法在多个任务中实现了显著的加速和扩展性提升。

**相关实体**: [[FlashAttention]] | [[IO 感知]] | [[分块计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]] | [[PyTorch]]


---

**▸ 更新于 2026-04-16T00:50:16Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出 [[FlashAttention]]，一种 IO 感知的精确注意力算法，通过分块计算和重计算策略显著降低内存占用并提升计算效率。该方法在保持数学等价性的前提下优化了 GPU 内存访问模式，提升了大规模序列处理能力。

**相关实体**: [[FlashAttention]] | [[IO 感知设计]] | [[分块计算]] | [[重计算策略]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]]


---

**▸ 更新于 2026-04-17T00:48:21Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: 本文提出 [[FlashAttention]] 算法，通过分块计算和重计算策略显著降低 [[Self-Attention]] 的内存占用，同时保持数学等价性。该方法在多个任务中实现了显著的加速和扩展性提升。

**相关实体**: [[FlashAttention]] | [[IO 感知设计]] | [[分块计算]] | [[在线 Softmax]] | [[反向传播重计算]] | [[FlashAttention-2]] | [[FlashAttention-3]]
