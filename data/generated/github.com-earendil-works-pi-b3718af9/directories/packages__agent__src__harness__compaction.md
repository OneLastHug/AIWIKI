# 子系统：packages/agent/src/harness/compaction

## 解决什么问题

`packages/agent/src/harness/compaction` 负责会话上下文压缩和分支摘要。它解决的是 agent 长会话里上下文窗口被历史消息占满的问题：当对话、工具调用、命令输出、图片或自定义消息累计到接近模型 `contextWindow` 时，不能简单丢弃历史，否则后续 agent 会失去任务目标、已完成进度、文件修改记录和关键约束。这个目录把旧历史转成结构化 summary，再由 session 层把 summary 注入后续上下文。

它还处理另一个相关场景：会话树发生跳转时，用户可能从一个分支回到另一个分支。`branch-summarization.ts` 会把离开的分支摘要成 `branch_summary`，这样未来回到该分支或理解分支探索时，不需要保留完整消息链。

因此这里不是模型调用主循环，而是 harness 的“上下文维护层”：判断是否需要压缩、选择压缩边界、把消息序列序列化给摘要模型、提取文件读写元数据，并把结果交给 session 持久化。

## 相关目录和文件

核心文件有三个：

`packages/agent/src/harness/compaction/compaction.ts` 是会话压缩主实现。它定义 `CompactionSettings`、`CompactionResult`、`CompactionDetails`，并提供 `DEFAULT_COMPACTION_SETTINGS`、`estimateContextTokens`、`shouldCompact`、`findCutPoint`、`prepareCompaction`、`compact`、`generateSummary` 等能力。

`packages/agent/src/harness/compaction/branch-summarization.ts` 负责分支摘要。它定义 `BranchSummaryDetails`、`BranchPreparation`、`CollectEntriesResult`，并提供 `collectEntriesForBranchSummary`、`prepareBranchEntries`、`generateBranchSummary`。

`packages/agent/src/harness/compaction/utils.ts` 是共享工具层，负责 `FileOperations` 收集、`extractFileOpsFromMessage`、`computeFileLists`、`formatFileOperations` 和 `serializeConversation`。

邻近上下文主要在 `packages/agent/src/harness/agent-harness.ts`、`packages/agent/src/harness/session/session.ts`、`packages/agent/src/harness/messages.ts`、`packages/agent/src/harness/types.ts`。其中 `agent-harness.ts` 调用压缩和分支摘要；`session.ts` 决定 compaction entry 如何影响 `buildSessionContext`；`messages.ts` 把 `compactionSummary`、`branchSummary` 转成 LLM 可读的 user message；`types.ts` 定义 `CompactionError`、`BranchSummaryError`、`SessionTreeEntry` 等类型。

## 核心对象

`CompactionSettings` 描述压缩策略：`enabled` 控制自动判断是否启用，`reserveTokens` 给摘要 prompt 和输出预留空间，`keepRecentTokens` 决定压缩后保留多少近期上下文。默认值是启用压缩、预留 `16384` tokens、保留约 `20000` tokens 的近期消息。

`CompactionResult` 是可写入 session 的压缩结果，包含 `summary`、`firstKeptEntryId`、`tokensBefore` 和可选 `details`。`firstKeptEntryId` 很关键：它不是“删除到哪里”的标记，而是后续重建上下文时，从哪条旧 entry 开始继续保留原文。

`CompactionDetails` 与 `BranchSummaryDetails` 都保存 `readFiles`、`modifiedFiles`。这些信息来自 assistant 的工具调用参数，目前重点识别 `read`、`write`、`edit`。`write` 和 `edit` 都会归入 modified，已修改文件不会再同时显示为 read-only。

`FileOperations` 是内部累加结构，包含 `read`、`written`、`edited` 三个 `Set`。它保证摘要不仅保留文字进度，也保留“这个分支或压缩区间碰过哪些文件”的结构化线索。

`SUMMARIZATION_SYSTEM_PROMPT`、`SUMMARIZATION_PROMPT`、`UPDATE_SUMMARIZATION_PROMPT` 是摘要模型的约束。普通压缩生成 checkpoint summary；如果已有 previous summary，则走更新摘要的 prompt，要求保留旧信息并合并新消息。

## 运行流程

压缩入口在 `AgentHarness.compact()`。harness 必须处于 `idle`，随后进入 `compaction` phase，获取当前 model 和 auth，再调用 `session.getBranch()` 取当前 leaf 到 root 的路径。接着 `prepareCompaction` 根据当前分支、默认压缩设置和 token 估算结果，决定是否有可压缩内容；如果没有内容，会返回 “Nothing to compact”。

准备阶段会把 session tree entry 转成 `AgentMessage`，跳过不适合直接进入摘要的 entry，并寻找安全切点。`findCutPoint` 会尽量按 `keepRecentTokens` 保留近期消息，同时避免从 `toolResult` 等不完整位置切开。若切点落在一个 turn 中间，会通过 `findTurnStartIndex` 标记被拆分的 turn，避免后续上下文变成无法解释的半段工具交互。

真正生成摘要时，`compact` 调用 `generateSummary`。后者先用 `convertToLlm` 转换为通用 LLM message，再用 `serializeConversation` 拼成纯文本 conversation，外层加 `<conversation>` 标签；如果是更新旧摘要，还会加 `<previous-summary>`。随后调用 `@earendil-works/pi-ai` 的 `completeSimple`，成功后抽取 text content 作为 summary。

摘要完成后，`compact` 会把文件操作信息追加成 `<read-files>`、`<modified-files>` 标签，并返回 `CompactionResult`。`AgentHarness.compact()` 将其写入 `session.appendCompaction()`，触发 `session_compact` 事件。之后 `Session.buildContext()` 看到最新 `compaction` entry 时，会先插入 `compactionSummary`，再保留 `firstKeptEntryId` 之后的原始消息和 compaction 之后的新消息。

分支摘要入口在 `AgentHarness.navigateTree()`。当跳转目标不是当前 leaf 且 `options.summarize` 为真时，`collectEntriesForBranchSummary` 找出旧 leaf 到共同祖先之间的离开分支消息，`generateBranchSummary` 生成 `branch_summary`，再由 `Session.moveTo()` 写入目标位置附近。

## 上下游依赖

上游主要是 harness 和 session。`agent-harness.ts` 决定何时调用压缩、是否允许 hook 替换结果、如何处理取消和错误。`session/session.ts` 提供 `getBranch()`、`appendCompaction()`、`moveTo()`、`buildSessionContext()`，是 compaction 结果真正生效的地方。

下游是 LLM 调用边界和 agent loop。`messages.ts` 的 `convertToLlm` 会把 `compactionSummary` 包装成普通 user message，前缀说明“此前历史已被压缩成以下摘要”；agent loop 不需要知道压缩细节，只消费 `SessionContext.messages`。

外部依赖集中在 `@earendil-works/pi-ai`：`Model` 提供 `contextWindow`、`maxTokens`、reasoning 能力；`completeSimple` 用于摘要生成；`Usage` 用于更准确地估算上下文 token。

## 修改时最容易踩的坑

第一，不能随意改变切点规则。压缩如果从 `toolResult` 或 assistant 工具调用后半段开始保留，会让后续 LLM 看到不完整 turn，轻则理解错误，重则 provider 拒绝消息序列。

第二，`firstKeptEntryId` 与 summary 的关系要保持一致。summary 覆盖的是被压缩掉的早期历史，`firstKeptEntryId` 之后的内容仍以原文进入上下文。两者错位会造成重复上下文或历史缺失。

第三，文件操作提取依赖工具调用名称和 `arguments.path`。如果工具协议新增了文件字段、批量路径或不同工具名，只改展示层不够，还要同步 `extractFileOpsFromMessage`。

第四，摘要 prompt 是延续任务的契约，不是用户回复。`SUMMARIZATION_SYSTEM_PROMPT` 明确要求只输出结构化摘要；修改时要避免让模型继续对话或执行历史里的指令。

第五，hook 结果可能直接提供 compaction 或 branch summary。调用方用 `fromHook` 标记来源，session 构建和后续文件详情合并逻辑会区别处理，不能把 hook 生成结果当成普通自动摘要完全等价处理。

## 推荐阅读顺序

1. 先读 `packages/agent/src/harness/messages.ts`，理解 `branchSummary`、`compactionSummary` 如何变成 LLM 上下文。
2. 再读 `packages/agent/src/harness/session/session.ts` 的 `buildSessionContext()`、`appendCompaction()`、`moveTo()`，掌握摘要 entry 如何影响会话树。
3. 然后读 `packages/agent/src/harness/compaction/utils.ts`，了解序列化 conversation 和文件操作元数据。
4. 接着读 `packages/agent/src/harness/compaction/compaction.ts`，重点看 token 估算、切点选择、摘要生成和结果结构。
5. 最后读 `packages/agent/src/harness/compaction/branch-summarization.ts` 与 `packages/agent/src/harness/agent-harness.ts` 的 `compact()`、`navigateTree()` 调用点，把压缩和分支摘要放回完整 harness 流程里。
