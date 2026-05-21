---
title: "Residual Function"
type: concept
created: 2026-05-21T01:02:47Z
status: seed
first_seen_in: Deep_Residual_Learning_for_Image_Recognition
tags: [concept]
---

# Residual Function

**Residual Function** 是深度神经网络中用于解决梯度消失问题的一种核心机制，其核心思想是让网络学习输入与输出之间的残差。通过引入跳跃连接（skip connection），网络可以直接学习残差映射，而非从头开始学习整个映射，从而提升了训练效率和模型性能。这种设计使得网络能够更稳定地进行深层训练，避免信息在传递过程中丢失。

Residual Function 的关键在于将原始输入直接加到网络的输出上，形成“残差块”。这样做的好处是，即使在网络较深的情况下，也能保持信息的完整性，使模型更容易优化。这种方法有效缓解了深度网络中的退化问题，使得训练更深层次的网络成为可能。

该概念首次在论文《Deep Residual Learning for Image Recognition》中提出，随后广泛应用于计算机视觉领域，如ResNet等经典模型均基于此思想。它不仅提高了图像识别的准确率，也推动了深度学习在多个领域的快速发展。

## 来源
- [[Deep_Residual_Learning_for_Image_Recognition]] — 首次发现

---
*由 Lumina Compiler 自动创建*
