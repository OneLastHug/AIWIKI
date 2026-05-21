# LobeHub 中文学习文档

## 解析范围与进度
本轮重解析覆盖核心代码树：`src`、`packages`、`apps`。为了避免被 `.agents`、`.github`、构建缓存、海量配置和文档噪声淹没，本轮优先解析最能解释项目架构和运行链路的 260 个目录与 420 个文件。

## 推荐阅读顺序
1. [项目整体介绍](00-overview.md)
2. [技术栈与预备知识](01-tech-stack.md)
3. [架构与目录关系](02-architecture.md)
4. [运行链路 / 数据流](03-runtime-flow.md)
5. 从左侧 `源码结构` 展开 `src`、`packages`、`apps`，点击目录名读目录说明，点击文件名读文件说明。

## 完全小白路线
先读 `src`，再读 `src/server`、`src/store`、`src/features`、`packages`，最后按兴趣进入具体文件。
