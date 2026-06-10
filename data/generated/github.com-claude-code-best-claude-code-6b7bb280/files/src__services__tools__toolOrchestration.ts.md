# 文件：src/services/tools/toolOrchestration.ts
## 一句话定位
这是 Claude Code 在一轮 assistant 回复里“批量执行工具调用”的编排层。它不负责具体工具实现，而是决定哪些工具可以并发、哪些必须串行，随后把执行结果和上下文变更按顺序回传给上层对话循环。

## 它暴露/定义了什么
对外真正可用的是 `runTools(...)`，返回一个 `AsyncGenerator<MessageUpdate>`。`MessageUpdate` 里带两类信息：当前产生的 `message`，以及更新后的 `newContext`。其余函数如 `partitionToolCalls`、`runToolsSerially`、`runToolsConcurrently`、`markToolUseAsComplete`、`getMaxToolUseConcurrency` 都是内部辅助，不直接暴露给外部调用者。

## 谁调用它
根据当前片段推断，主要调用方是 `src/query.ts` 和 `src/utils/queryHelpers.ts`。前者是主对话循环，负责把模型生成的 `tool_use` 块交给这里执行；后者看起来用于一些查询辅助流程，也需要同一套工具编排逻辑。也就是说，这个文件处在“模型输出”到“真实工具执行”之间的中间层。

## 它调用谁
它会调用 `findToolByName` 从工具注册表里找出具体工具，再根据工具的 `inputSchema` 和 `isConcurrencySafe(...)` 判断能否并发；真正执行工具时委托给 `runToolUse`。并发批次用 `all(...)` 做受限并发，速率上限来自环境变量 `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY`，默认 10。埋点上还会创建和结束 Langfuse 的批次 span：`createToolBatchSpan`、`endToolBatchSpan`。

## 核心流程
1. 进入 `runTools` 后，先为这一轮工具调用创建一个批次级的 Langfuse span。  
2. 通过 `partitionToolCalls(...)` 把 `tool_use` 切成若干批：要么是单个非只读工具，要么是连续的只读工具组。这里的“只读/并发安全”并不是凭名字猜，而是基于工具定义里的 `isConcurrencySafe`，并且对 schema 解析失败、异常抛出都保守地视为不可并发。  
3. 对安全批次走 `runToolsConcurrently`，对非安全批次走 `runToolsSerially`。  
4. 并发执行时会先把每个工具标记进 `inProgressToolUseIDs`，工具返回的 `contextModifier` 不会立刻改全局上下文，而是按 `toolUseID` 收集起来，等这一批全部结束后再统一应用，避免并发更新互相覆盖。  
5. 串行执行时则是每个工具跑完就立刻把 `contextModifier` 合并到当前上下文。  
6. 每个工具结束后都会从 `inProgressToolUseIDs` 中移除。整轮完成后结束 batch span，并把最后的上下文状态交回上层。

## 关键函数的高层作用
`runTools` 是总调度器，决定执行模式和上下文流转。`partitionToolCalls` 负责把输入切成“可并发”和“必须串行”的批次，是这里最关键的策略点。`runToolsConcurrently` 负责受限并发执行，并延迟合并上下文。`runToolsSerially` 负责严格顺序执行，适合有副作用或依赖前序结果的工具。`markToolUseAsComplete` 只是收尾清理。`getMaxToolUseConcurrency` 则把并发上限外置到环境变量，方便调参。

## 修改风险
这个文件的风险主要不在语法，而在执行语义。改错并发判定会把有副作用的工具放进并发批次，可能导致文件写入、权限状态、会话上下文或工具结果顺序出问题。改错 `contextModifier` 的合并时机，会让后续工具看到错误上下文，或者让并发批次的结果互相覆盖。调整 `inProgressToolUseIDs` 也会影响 UI 状态、取消逻辑和远程会话的进度显示。最后，修改批次 span 的创建/结束位置，会直接污染工具链路的观测数据。
