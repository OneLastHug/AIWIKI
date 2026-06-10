# 文件：packages/coding-agent/src/core/compaction/index.ts

## 一句话定位

`packages/coding-agent/src/core/compaction/index.ts` 是 `coding-agent` 压缩与摘要能力的统一导出入口，本身不承载业务逻辑，而是把会话压缩、分支摘要和序列化工具集中暴露给上层模块使用。

## 它暴露/定义了什么

这个文件只做三类 re-export：

`./branch-summarization.ts`：分支摘要相关能力。根据当前片段推断，它服务于会话树、分支切换或历史路径重建场景，因为 `session-manager.ts` 中有 “branch summaries along the path” 的处理逻辑。

`./compaction.ts`：会话压缩的核心能力。调用侧明确使用了 `shouldCompact`、`compact`、`generateSummary`、`CompactionPreparation`、`CompactionResult` 等导出，说明这里包含判断是否需要压缩、准备压缩输入、调用模型生成摘要、返回压缩结果的主流程。

`./utils.ts`：压缩辅助工具。测试中直接从 `core/compaction/utils.ts` 引入 `serializeConversation`，说明它负责把会话消息或条目转换成适合摘要模型消费的文本形式。

因此，`index.ts` 的价值是稳定导出边界：外部通常不需要关心压缩能力分散在哪个内部文件，只从 `core/compaction/index.ts` 取类型、函数和工具。

## 谁调用它

主要调用方是 `packages/coding-agent/src/core/agent-session.ts`。它从 `./compaction/index.ts` 导入 `shouldCompact` 等能力，用于手动压缩、自动压缩、上下文溢出后的压缩，以及压缩开始/结束事件的编排。

`packages/coding-agent/src/index.ts` 也从该入口再导出压缩能力，说明这些 API 不只给内部使用，也可能作为 `coding-agent` 包的外部公开能力。

RPC 层的 `packages/coding-agent/src/modes/rpc/rpc-client.ts`、`packages/coding-agent/src/modes/rpc/rpc-types.ts` 引入 `CompactionResult` 类型，用于 RPC 协议中的压缩结果建模。

测试侧大量依赖该入口，包括 `packages/coding-agent/test/compaction.test.ts`、`packages/coding-agent/test/compaction-summary-reasoning.test.ts`、`packages/coding-agent/test/agent-session-auto-compaction-queue.test.ts` 等，用来验证压缩阈值、摘要生成、重复压缩、压缩后上下文重建和队列恢复行为。

## 它调用谁

`index.ts` 自身没有运行时调用关系，不执行函数、不创建对象、不读取状态。它只通过 `export * from ...` 把三个邻近模块的导出向外转发：

`packages/coding-agent/src/core/compaction/branch-summarization.ts`、`packages/coding-agent/src/core/compaction/compaction.ts`、`packages/coding-agent/src/core/compaction/utils.ts`。

需要注意的是，TypeScript/ESM 的 re-export 会建立模块依赖边界：任何从 `core/compaction/index.ts` 导入的调用方，都间接依赖这三个模块的可解析性和导出稳定性。即使 `index.ts` 本身没有业务分支，改动它仍可能影响整个压缩功能的公共 API。

## 核心流程

从系统行为看，压缩流程不是在 `index.ts` 内完成，而是由它导出的能力被 `AgentSession` 串起来。

典型路径是：`AgentSession` 在模型响应后或用户手动触发时检查当前上下文使用量；通过 `shouldCompact(contextTokens, contextWindow, settings)` 判断是否达到压缩阈值；若需要压缩，则基于当前 `SessionManager` 分支准备压缩输入；调用 `compact` 或相关摘要函数生成 `CompactionResult`；随后把结果作为 `compaction` entry 写入会话树；再通过 `buildSessionContext` 一类逻辑把新的上下文重建为“摘要消息 + 保留的最近消息 + 压缩之后的新消息”。

自动压缩时还会围绕该流程发出 `compaction_start` 和 `compaction_end` 事件。交互模式会在压缩期间暂存用户输入，压缩结束后恢复队列；RPC 模式则通过类型定义暴露压缩结果。扩展系统还可以在 `before_compact` 阶段取消压缩或提供自定义压缩内容，根据测试文件推断，这也是 `AgentSession` 在调用核心压缩能力前后处理的，而不是 `index.ts` 自身处理的。

## 关键函数的高层作用

`shouldCompact`：判断是否需要触发压缩。它综合当前 token 数、模型上下文窗口和 `compaction` 设置，避免每次响应都无条件生成摘要。

`compact`：执行一次完整压缩。根据当前片段推断，它接收准备好的压缩输入、模型信息和认证/信号等参数，产出包含 `summary`、`firstKeptEntryId`、`tokensBefore` 等字段的结果，供 `SessionManager` 持久化为 `compaction` entry。

`generateSummary`：更聚焦于摘要生成本身。测试 `compaction-summary-reasoning.test.ts` 关注摘要输出 token 上限，说明它处理模型输出约束和摘要 prompt 的生成细节。

`prepareCompaction`：根据测试名称推断，它决定哪些历史需要总结、哪些最近消息需要保留，并在已有 compaction 的情况下避免丢失仍应保留的上下文。

`serializeConversation`：把会话消息序列化成可读文本，供摘要 prompt 使用。它属于辅助函数，核心风险在于消息类型覆盖是否完整。

分支摘要相关函数：根据当前片段推断，它们处理会话树分叉时的路径摘要，和普通 compaction 一起参与 `SessionManager` 的上下文重建。

## 修改风险

最大风险是把 `index.ts` 当成“无逻辑文件”随意改导出。由于 `agent-session.ts`、RPC 类型、包级 `src/index.ts` 和多组测试都经由这个入口消费压缩 API，删除或改名任意 re-export 都会造成跨层编译失败或公共 API 断裂。

第二类风险是导出边界污染。如果把内部实现细节也从这里导出，外部调用方可能开始依赖不稳定结构，后续重构 `compaction.ts`、`branch-summarization.ts` 或 `utils.ts` 会更困难。

第三类风险是循环依赖。`index.ts` 聚合三个模块，如果这些模块反向从 `core/compaction/index.ts` 导入彼此，会形成 barrel 文件常见的循环依赖问题。修改邻近模块时应优先使用直接相对导入，而不是在同一目录内部绕回 `index.ts`。

第四类风险是类型导出与运行时导出的混用。RPC 和包入口依赖这里的类型；如果调整为仅类型导出或改变 `.ts`/`.js` 解析形式，需要确认 Node strip-only TypeScript、测试 mock 路径和包构建方式都能继续工作。

实际修改建议是：如果只是新增压缩能力，先在对应实现文件中添加并测试，再从 `index.ts` 明确导出；如果要移除或重命名导出，必须同步检查 `agent-session.ts`、`src/index.ts`、RPC 类型文件和压缩相关测试。
