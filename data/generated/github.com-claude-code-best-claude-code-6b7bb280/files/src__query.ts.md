# 文件：src/query.ts
## 一句话定位
`src/query.ts` 是整条 Claude Code 对话回路的核心调度器：它把一次用户输入推进为多轮 `query` 迭代，负责模型流式输出、工具执行、上下文压缩、错误恢复和收尾通知。根据当前片段推断，它是 REPL、SDK、任务运行器和子 agent 复用的同一条主链路。

## 它暴露/定义了什么
对外真正暴露的是 `export type QueryParams` 和 `export async function* query(...)`。文件内部还定义了少量辅助逻辑，例如 `yieldMissingToolResultBlocks`、`isWithheldMaxOutputTokens`、`getAutonomyTurnOutcome`，以及 `queryLoop` 这个承载主循环的内部生成器。整体上，它不是工具模块，而是“turn engine”。

## 谁调用它
从仓库搜索结果看，直接调用方包括 `src/screens/REPL.tsx`、`src/QueryEngine.ts`、`src/tasks/LocalMainSessionTask.ts`、`src/utils/hooks/execAgentHook.ts`、`src/utils/forkedAgent.ts`，以及 `src/services/acp/agent.ts`、`src/bridge/replBridge.ts` 等桥接路径。也就是说，凡是需要跑一次完整对话回合的地方，都会走到这里。

## 它调用谁
它会调用一批上层和底层服务：`deps.callModel` 负责真正请求模型；`deps.microcompact`、`deps.autocompact`、`reactiveCompact`、`contextCollapse`、`snipModule` 负责上下文压缩和溢出恢复；`runTools`、`StreamingToolExecutor` 负责工具执行；`handleStopHooks`、`executeStopFailureHooks` 负责停止钩子；`buildQueryConfig`、`productionDeps`、`createBudgetTracker` 负责配置与预算；还会接 `attachments`、`messages`、`analytics`、`langfuse`、`queue manager`、`memory prefetch` 等配套能力。

## 核心流程
1. `query()` 先建立 trace、收集自治命令状态，并把参数交给 `queryLoop()`。
2. `queryLoop()` 在每一轮先做上下文准备：裁剪消息、应用 tool result budget、可选 snip/microcompact/context collapse/autocompact，再补充内存/技能/额外工具预取。
3. 若上下文过大，会先走阻断判断；必要时直接产出 API error，或尝试预测性/反应式压缩。
4. 然后调用 `deps.callModel` 流式拉取 assistant 消息，边收边处理 `tool_use`，必要时启用 streaming tool execution。
5. 模型结束后，按场景处理 fallback、被隐藏的 `prompt too long`、`max_output_tokens`、图片/媒体错误、停止钩子、token budget 续跑。
6. 如果产生工具调用，会执行工具、补齐 `tool_result`、生成工具摘要、把队列中的命令和附件一起带入下一轮。
7. 只要还需要继续，就把新的 `State` 写回并 `continue`；最终返回 `Terminal`，`query()` 再统一做命令生命周期完成通知和 trace 收尾。

## 关键函数的高层作用
- `query`：对外入口，包装 trace、异常收口和自治命令清理。
- `queryLoop`：真正的状态机，控制每一次继续/终止。
- `yieldMissingToolResultBlocks`：当流或 fallback 失败时，补齐缺失的 `tool_result`，避免下一次请求因 tool_use/tool_result 不配对而报错。
- `isWithheldMaxOutputTokens`：识别被暂时压住的 `max_output_tokens` 错误，等待恢复逻辑决定是否真正上抛。
- `getAutonomyTurnOutcome`：把终局状态映射成自治队列的完成/取消/失败结果，供后续命令调度使用。

## 修改风险
这个文件改动风险很高，因为它处在“模型流、工具流、恢复流”的交汇点。最容易出问题的是：`tool_use` 和 `tool_result` 配对被破坏、压缩/回退顺序被改乱、`stop hooks` 和恢复逻辑互相触发死循环、`maxTurns` 或 token budget 的继续条件失真、以及 trace/队列清理遗漏导致长会话内存上涨或状态串线。由于它被 REPL、SDK、fork agent、后台任务和桥接层共用，任何一处行为变化都可能扩散到整套交互体验。
