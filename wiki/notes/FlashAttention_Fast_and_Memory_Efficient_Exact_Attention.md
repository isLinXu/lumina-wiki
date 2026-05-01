---
title: "FlashAttention: Fast and Memory-Efficient Exact Attention"
type: note
created: 2026-04-06T03:52:06Z
source: raw/2026-04-06/FlashAttention_Paper.md
status: seed
---

# FlashAttention: Fast and Memory-Efficient Exact Attention

> 💡 **摘要**
> # FlashAttention: Fast and Memory-Efficient Exact Attention

## 原始内容

FlashAttention 是一种 IO 感知的精确注意力算法，通过分块计算（tiling）和重计算（recomputation）策略，显著降低了标准 Self-Attention 的内存占用，同时保持数学等价性。

### 核心思想

1. **IO 感知 (IO-Aware)**：注意力计算的瓶颈不在 FLOPs，而在 GPU 内存层级之间的数据搬运（HBM ↔ SRAM）。FlashAttention 最小化了 HBM 读写次数。

2. **分块...

| 属性 | 值 |
|------|-----|
| 类型 | note |
| 来源 | `raw/2026-04-06/FlashAttention_Paper.md` |
| 编译时间 | 2026-04-06 |

---

*由 **Lumina Compiler** 于 2026-04-06T03:52:06Z 自动生成*
*来源: `raw/2026-04-06/FlashAttention_Paper.md`*

---

**▸ 更新于 2026-04-27T00:51:33Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: # FlashAttention: Fast and Memory-Efficient Exact Attention

## 原始内容

FlashAttention 是一种 IO 感知的精确注意力算法，通过分块计算（tiling）和重计算（recomputation）策略，显著降低了标准 Self-Attention 的内存占用，同时保持数学等价性。

### 核心思想

1. **IO 感知 (IO-Aware)**：注意力计算的瓶颈不在 FLOPs，而在 GPU 内存层级之间的数据搬运（HBM ↔ SRAM）。FlashAttention 最小化了 HBM 读写次数。

2. **分块...



---

**▸ 更新于 2026-04-28T00:53:39Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: # FlashAttention: Fast and Memory-Efficient Exact Attention

## 原始内容

FlashAttention 是一种 IO 感知的精确注意力算法，通过分块计算（tiling）和重计算（recomputation）策略，显著降低了标准 Self-Attention 的内存占用，同时保持数学等价性。

### 核心思想

1. **IO 感知 (IO-Aware)**：注意力计算的瓶颈不在 FLOPs，而在 GPU 内存层级之间的数据搬运（HBM ↔ SRAM）。FlashAttention 最小化了 HBM 读写次数。

2. **分块...



---

**▸ 更新于 2026-04-29T00:54:43Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: # FlashAttention: Fast and Memory-Efficient Exact Attention

## 原始内容

FlashAttention 是一种 IO 感知的精确注意力算法，通过分块计算（tiling）和重计算（recomputation）策略，显著降低了标准 Self-Attention 的内存占用，同时保持数学等价性。

### 核心思想

1. **IO 感知 (IO-Aware)**：注意力计算的瓶颈不在 FLOPs，而在 GPU 内存层级之间的数据搬运（HBM ↔ SRAM）。FlashAttention 最小化了 HBM 读写次数。

2. **分块...



---

**▸ 更新于 2026-04-30T00:54:33Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: # FlashAttention: Fast and Memory-Efficient Exact Attention

## 原始内容

FlashAttention 是一种 IO 感知的精确注意力算法，通过分块计算（tiling）和重计算（recomputation）策略，显著降低了标准 Self-Attention 的内存占用，同时保持数学等价性。

### 核心思想

1. **IO 感知 (IO-Aware)**：注意力计算的瓶颈不在 FLOPs，而在 GPU 内存层级之间的数据搬运（HBM ↔ SRAM）。FlashAttention 最小化了 HBM 读写次数。

2. **分块...



---

**▸ 更新于 2026-05-01T00:58:17Z**
> 来源: `raw/2026-04-06/FlashAttention_Paper.md`

**补充摘要**: # FlashAttention: Fast and Memory-Efficient Exact Attention

## 原始内容

FlashAttention 是一种 IO 感知的精确注意力算法，通过分块计算（tiling）和重计算（recomputation）策略，显著降低了标准 Self-Attention 的内存占用，同时保持数学等价性。

### 核心思想

1. **IO 感知 (IO-Aware)**：注意力计算的瓶颈不在 FLOPs，而在 GPU 内存层级之间的数据搬运（HBM ↔ SRAM）。FlashAttention 最小化了 HBM 读写次数。

2. **分块...

