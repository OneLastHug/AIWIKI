# 目录：packages/coding-agent/src/core/compaction

## 它负责什么

这个目录负责 coding agent 的“上下文压缩”相关能力，核心目标是让长会话在接近上下文窗口上限时，仍能保留可用信息并继续对话。它不是 UI 层，也不是 session 存储层，而是纯逻辑层，主要做三类事情：

1. 估算当前上下文还剩多少可用空间，判断是否需要压缩。
2. 把一段历史消息压缩成结构化摘要，并保留文件读写痕迹。
3. 在分支切换时，生成 branch summary，避免切到别的路径后丢失之前的上下文。

根据当前片段推断，这个目录是“会话管理器”之下的策略模块：`agent-session.ts` 负责触发，`compaction` 目录负责计算、整理和生成摘要。

## 直接子目录地图

这里没有更深的子目录，直接子项只有 4 个文件，角色很清晰：

- `index.ts`：统一导出入口，给外部按目录级别引用。
- `compaction.ts`：主压缩逻辑，包含 token 估算、触发条件、摘要生成所需的核心类型与函数。
- `branch-summarization.ts`：分支切换场景下的摘要生成逻辑，负责从旧分支收集条目并准备摘要输入。
- `utils.ts`：两条主流程共用的基础工具，包含文件操作追踪、消息序列化、摘要提示词等。

这意味着该目录不是“很多模块并列”的结构，而是一个以 `compaction.ts` 为中心、`branch-summarization.ts` 为旁路、`utils.ts` 为共享底座的小功能区。

## 关键入口

最外层入口是 `index.ts`，它把 `branch-summarization.ts`、`compaction.ts`、`utils.ts` 全部 re-export 出去。外部代码通常不直接依赖单个文件，而是通过这个目录入口拿到能力。

从调用关系看，真正的业务入口在 `agent-session.ts`：

- `estimateContextTokens(...)`：用于会话级上下文估算。
- `shouldCompact(...)`：决定是否进入压缩。
- `compact(...)`：执行实际压缩。
- `collectEntriesForBranchSummary(...)`：分支切换时收集待摘要条目。
- `prepareBranchEntries(...)`：准备 branch summary 的消息和文件操作信息。

另外，`interactive-mode.ts` 和 `rpc-mode.ts` 也会通过 session 间接触发 `compact()`，说明这个目录的逻辑是被多种运行模式共享的，而不是只服务单一入口。

## 主流程位置

主流程基本都集中在 `compaction.ts` 和 `branch-summarization.ts` 两个文件里。

`compaction.ts` 这条线偏“会话压缩”：

- 先定义 `CompactionSettings`、`DEFAULT_COMPACTION_SETTINGS`。
- 再通过 `calculateContextTokens()`、`getLastAssistantUsage()`、`estimateContextTokens()` 估算会话上下文。
- `shouldCompact()` 判断是否接近阈值。
- 后半段的 `compact()` 才是实际执行压缩的入口。根据 `rg` 结果，它在文件靠后位置，说明前半部分多是准备工作和辅助函数。

`branch-summarization.ts` 这条线偏“分支切换摘要”：

- `collectEntriesForBranchSummary()` 先找旧位置和目标位置的最近公共祖先。
- `prepareBranchEntries()` 再按 token 预算从新到旧筛消息，同时累计文件操作。
- 它还会把 `branch_summary`、`compaction` 这类历史摘要再转回消息上下文，保证摘要链条不断裂。

`utils.ts` 则是两条线共同依赖的底层支撑：

- `createFileOps()`、`extractFileOpsFromMessage()`、`computeFileLists()`、`formatFileOperations()` 负责文件读写痕迹。
- `serializeConversation()` 把 LLM 消息转成可摘要文本。
- `SUMMARIZATION_SYSTEM_PROMPT` 是摘要模型的系统提示词。

## 推荐阅读顺序

1. 先看 `index.ts`，确认这个目录对外暴露了什么。
2. 再看 `utils.ts`，先建立文件操作追踪和消息序列化的基础概念。
3. 接着看 `compaction.ts` 的前半段，理解上下文估算、触发条件和关键类型。
4. 然后看 `branch-summarization.ts`，理解分支切换时如何收集条目并做摘要输入准备。
5. 最后回到 `agent-session.ts` 里看调用点，把“谁触发、何时触发、触发后如何保存”串起来。

## 常见误区

- 把这个目录理解成“只有压缩”，其实它同时覆盖了 compaction 和 branch summarization 两条相关但不同的流程。
- 只盯着 `compact()`，忽略前面的上下文估算和触发判断。真实行为往往先由 `estimateContextTokens()` 和 `shouldCompact()` 决定。
- 只看消息内容，不看文件操作。这里的设计很重视 `readFiles`、`modifiedFiles` 这类元信息，摘要里会保留这些痕迹。
- 以为 `branch_summary` 和 `compaction` 只是普通消息。实际上它们是可回灌上下文的结构化摘要节点。
- 忽略 `agent-session.ts`。这个目录本身不负责 I/O，真正的会话重载、保存、触发时机都在上层，`compaction` 只是核心算法层。
