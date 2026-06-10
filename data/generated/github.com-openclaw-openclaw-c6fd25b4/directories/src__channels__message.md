# 目录：src/channels/message

## 它负责什么

`src/channels/message` 是 OpenClaw 核心里专门处理“消息通道消息层”的实现目录，作用不是承载某一种具体 channel，而是把消息发送、接收、回执、回复链路、持久化接收、直播预览态这些通用能力抽成一组可复用的核心模块。根据当前片段推断，它更像一个消息编排层：上层调用者先拿到消息发送/接收所需的上下文，这里再把 outbound、ack/nack、receipt、live preview、durable journal 这些环节串起来。

这个目录下的核心特点是“入口聚合 + 分工明确”。`index.ts` 把外部需要的能力统一导出，`runtime.ts` 提供运行时入口，其他文件分别负责发送、接收、回执、状态、能力证明和桥接适配。整体上，它服务的是 channel 之上的消息主流程，而不是单个协议或单个插件。

## 直接子目录地图

这个目录下没有再分层的子目录，当前看到的是单层文件集合。也就是说，它的“地图”主要是文件职责分区，而不是树状子目录。

可按功能块理解为：

- 入口聚合：`index.ts`
- 运行时入口：`runtime.ts`
- 发送主链路：`send.ts`
- 接收与 ack 逻辑：`receive.ts`
- 回复链路编排：`reply-pipeline.ts`
- 持久化接收：`durable-receive.ts`
- 直播预览与最终化：`live.ts`
- 回执构造与归一化：`receipt.ts`
- 状态记录：`state.ts`
- 能力证明与约束：`contracts.ts`、`capabilities.ts`
- 外部 outbound 适配：`outbound-bridge.ts`
- 渲染批次模型：`rendered-batch.ts`
- 类型定义：`types.ts`

测试文件同目录分布，说明这里的行为边界是用单元测试直接护住的，典型有 `send.test.ts`、`receive.test.ts`、`receipt.test.ts`、`live.test.ts`、`contracts.test.ts`、`capabilities.test.ts`、`outbound-bridge.test.ts`、`durable-receive.test.ts`、`lifecycle.test.ts`。

## 关键入口

最关键的入口是 `index.ts`。它是这个目录对外的聚合面，把消息层能力统一导出，包括：

- `send` 相关的持久化/耐久发送上下文
- `receive` 相关的消息接收上下文与 ack 判定
- `reply-pipeline` 相关的回复前缀、typing、reply payload 变换
- `live` 相关的预览态与最终化
- `receipt` 相关的回执解析
- `contracts` 和 `capabilities` 相关的证明与约束

`runtime.ts` 则是较轻的运行时出口，只重导出 `send.ts` 的运行时 API，说明它偏向热路径的调用入口，而不是一把把所有实现都拉进来。

从函数命名看，真正的编排核心分别是：

- `withDurableMessageSendContext`：把一次 durable 消息发送包装成上下文驱动的执行过程
- `createMessageReceiveContext`：构造接收态上下文并封装 ack/nack
- `createChannelReplyPipeline`：把回复前缀、typing、payload transform 串成可用流水线
- `createDurableInboundReceiveJournal`：处理持久化接收记录
- `createMessageReceiptFromOutboundResults`：把 outbound 结果归一为回执

## 主流程位置

如果按消息主流程看，这个目录的主干大致是：

1. 回复或发送前，`reply-pipeline.ts` 先准备回复前缀、typing callbacks，以及可选的 reply payload 变换。
2. `send.ts` 接管真正的发送编排：先把 payload 变成 `rendered-batch`，再调用底层 outbound deliver 逻辑，最后生成 receipt，并根据 live state 更新预览态。
3. `receipt.ts` 负责把 platform 返回结果统一成消息回执，给上层一个稳定的结果形状。
4. `live.ts` 管理 preview/finalized/cancelled 之类的 live message 状态，适合需要边发边更新的场景。
5. `receive.ts` 和 `durable-receive.ts` 则走入站路径：前者处理 ack policy、ack/nack 状态机，后者负责 durable inbound journal。
6. `contracts.ts`、`capabilities.ts` 把这些能力包起来做证明，避免不满足条件的适配器进入主流程。
7. `outbound-bridge.ts` 提供从 outbound 世界进入 message 世界的桥接层。

如果要定位“消息从哪进、到哪出”，通常先看 `send.ts` 和 `receive.ts`；如果要理解“为什么要有这个目录”，先看 `index.ts`，再看 `contracts.ts`、`receipt.ts`、`live.ts` 这三个配套层。

## 推荐阅读顺序

1. `index.ts`：先看整体导出面，建立概念地图。
2. `types.ts`：再看数据结构和核心类型名。
3. `receive.ts`、`send.ts`：抓住入站与出站两条主线。
4. `receipt.ts`、`live.ts`：理解发送后的结果与状态演化。
5. `reply-pipeline.ts`：看回复链路如何组装。
6. `durable-receive.ts`、`state.ts`：补上持久化与恢复语义。
7. `contracts.ts`、`capabilities.ts`、`outbound-bridge.ts`：最后看约束和桥接。

## 常见误区

- 把这里当成某个具体 channel 的实现目录。它更像消息层公共能力集合，而不是单一 channel 适配器。
- 只看 `send.ts` 就以为理解了全部发送语义。实际上 receipt、live preview、capability proof 都是同一条链路的一部分。
- 忽略 `receive.ts` 的 ack policy。消息接收不是“收到就完了”，这里还定义了何时 ack、何时 nack、何时进入 durable send 阶段。
- 把 `index.ts` 当成业务代码。它主要是对外聚合层，真正的行为在各个功能文件里。
- 认为测试只是附属。这个目录的测试文件密度很高，说明它属于行为敏感区，改动很容易牵动主流程与兼容约束。

如果你把它当成一张地图，记住一句话就够了：`reply-pipeline.ts` 负责“怎么组织要发的话”，`send.ts` 负责“怎么发出去”，`receive.ts` 负责“怎么接进来”，`receipt.ts` 和 `live.ts` 负责“怎么把结果稳定下来”。
