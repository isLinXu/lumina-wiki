---
title: "FlashAttention: Fast and Memory-Efficient Exact Attention"
source: github-issue
issue_number: 2
author: gatilin
url: https://github.com/gatilin/Lumina-Wiki/issues/2
ingested_at: 2026-04-06T09:30:00Z
labels: ["lumina", "paper"]
---

# FlashAttention: Fast and Memory-Efficient Exact Attention

## 原始内容

FlashAttention 是一种 IO 感知的精确注意力算法，通过分块计算（tiling）和重计算（recomputation）策略，显著降低了标准 Self-Attention 的内存占用，同时保持数学等价性。

### 核心思想

1. **IO 感知 (IO-Aware)**：注意力计算的瓶颈不在 FLOPs，而在 GPU 内存层级之间的数据搬运（HBM ↔ SRAM）。FlashAttention 最小化了 HBM 读写次数。

2. **分块计算 (Tiling)**：将 Q, K, V 矩阵分成小块，在 SRAM 中完成 softmax 的分块计算，避免 O(N²) 的中间矩阵写回 HBM。

3. **在线 Softmax (Online Softmax)**：采用 Milakov & Gimelshein 的在线统计量更新技巧，使 softmax 可以分块增量计算。

4. **反向传播重计算 (Recomputation)**：前向传播不保存 O(N²) 的注意力矩阵，反向传播时按需重新计算，用计算换内存。

### 性能数据

- 内存从 O(N²) 降到 O(N)
- 在 GPT-2 训练中加速 3x
- 支持的最大序列长度从 1K 提升到 64K
- 在 BERT-large 上训练时间缩短 15%
- Wall-clock speedup: 1.5-3x on A100 GPU

### 后续发展
- FlashAttention-2: 优化了 warp-level 并行度
- FlashAttention-3: 适配 Hopper 架构 (H100) 的异步特性
- 已被 PyTorch (SDPA)、xFormers、Triton 等框架集成
