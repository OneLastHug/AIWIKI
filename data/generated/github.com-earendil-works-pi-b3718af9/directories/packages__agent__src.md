# 目录：packages/agent/src

## 它负责什么

`packages/agent/src` 是 `@earendil-works/pi-agent-core` 的核心源码目录，定位是“通用 Agent 核心层”。它不直接等同于命令行产品或 TUI，而是提供可复用的 Agent 状态机、LLM 流式调用循环、工具调用执行、会话树存储、上下文压缩、技能与 prompt template 加载等基础能力。

从 `packages/agent/package.json` 看，这个包的描述是 general-purpose agent with transport abstraction, state management, and attachment support；源码也符合这个边界：`agent.ts` 管状态与对外 API，`agent-loop.ts` 管单轮或连续轮次的模型响应与工具执行，`harness/` 管更完整的运行外壳，包括资源、会话、压缩、环境抽象和事件钩子。它依赖 `@earendil-works/pi-ai` 来做模型、消息、流式接口和 provider transport 抽象，因此这里不是 provider 实现层，而是 provider 之上的 agent orchestration 层。

## 直接子目录地图

`packages/agent/src` 顶层文件较少，主体在 `harness/` 下。

`harness/` 是高层运行框架目录，围绕 `AgentHarness` 组织。它把底层 `Agent` 包成更适合应用使用的运行外壳：管理 resources、hooks、session、compaction、branch summary、skills、prompt templates、stream options patch、队列事件和错误归一化。

`harness/compaction/` 负责上下文压缩与分支摘要。`compaction.ts` 包含 token 估算、压缩触发判断、cut point 选择、摘要生成和 `compact` 主函数；`branch-summarization.ts` 处理从会话树分支中收集条目并生成分支摘要；`utils.ts` 处理文件读写痕迹提取和对话序列化。

`harness/env/` 是运行环境适配层，目前看到 `nodejs.ts`，导出 `NodeExecutionEnv`。它实现文件系统与 shell 执行相关接口，包括路径解析、文件信息、命令执行、shell 配置和进程终止等。根据当前片段推断，浏览器或其他运行时若要接入，需要实现 `harness/types.ts` 中的 `ExecutionEnv`、`FileSystem`、`Shell` 等接口。

`harness/session/` 是会话树与持久化目录。`session.ts` 定义 `Session` 和 `buildSessionContext`；`memory-storage.ts`、`memory-repo.ts` 是内存实现；`jsonl-storage.ts`、`jsonl-repo.ts` 是 JSONL 文件实现；`repo-utils.ts` 提供 session id、timestamp、fork entries 等辅助；`uuid.ts` 生成 `uuidv7`。这里的会话不是简单线性日志，而是带 parent/leaf/label 的树状结构，支持 fork、branch summary、compaction 等上层能力。

`harness/utils/` 是通用工具目录。`shell-output.ts` 提供 shell 执行结果捕获与二进制输出清洗；`truncate.ts` 提供按行数、字节数、grep 风格长行等规则截断输出的能力，用于控制模型上下文或终端输出大小。

## 关键入口

包主入口是 `packages/agent/src/index.ts`。它集中 re-export 顶层 Agent、loop、harness、compaction、messages、prompt templates、session、skills、system prompt、proxy 和 types。多数使用方应从包根入口导入。

Node 专用入口是 `packages/agent/src/node.ts`。它额外导出 `NodeExecutionEnv`，再导出 `index.ts` 的全部内容。也就是说，需要真实 Node 文件系统和 shell 能力时，应走 `./node` 入口；只需要通用 agent 核心类型与逻辑时，走默认入口即可。

核心类入口是 `packages/agent/src/agent.ts` 中的 `Agent`。它维护 `AgentState`，提供 `prompt()`、`continue()`、`steer()`、`followUp()`、`abort()`、`waitForIdle()`、`reset()`、`subscribe()` 等 API。它还持有 `streamFn`、`getApiKey`、`beforeToolCall`、`afterToolCall`、`prepareNextTurn`、`thinkingBudgets`、`transport`、`toolExecution` 等配置，把外部模型调用、工具拦截、下一轮准备和事件监听串起来。

底层循环入口是 `packages/agent/src/agent-loop.ts`，主要导出 `agentLoop`、`agentLoopContinue`、`runAgentLoop`、`runAgentLoopContinue`。其中 `runAgentLoop` 和 `runAgentLoopContinue` 更像面向 `Agent` 类内部使用的 async 主流程；`agentLoop` 和 `agentLoopContinue` 返回事件流，适合需要手动消费事件的场景。

高层外壳入口是 `packages/agent/src/harness/agent-harness.ts` 中的 `AgentHarness`。它负责把模型、工具、会话、skills、prompt templates、resources、hooks 和 stream options 组合成完整运行单元，是应用层更可能接触的入口。

## 主流程位置

最核心的主流程在 `packages/agent/src/agent.ts` 与 `packages/agent/src/agent-loop.ts` 之间。

一次普通调用大致是：使用方调用 `Agent.prompt()`，输入字符串会被规范化成 `AgentMessage`；`Agent` 设置运行生命周期、更新状态、发出事件，然后调用 `runAgentLoop`。`runAgentLoop` 内部会把当前消息转换成 LLM 可理解的 `Message[]`，调用 `streamFn` 流式获取 assistant response，并在过程中发出 streaming、payload、response 等相关事件。模型返回包含 tool call 时，循环进入工具执行阶段。

工具调用主流程位于 `agent-loop.ts` 的 `executeToolCalls` 一组函数。它支持 `ToolExecutionMode` 的 `"parallel"` 与 `"sequential"`，会先根据工具定义准备参数，再调用 `beforeToolCall`，执行工具函数，随后调用 `afterToolCall`，最后生成 `toolResult` 消息并继续下一轮。`shouldTerminateToolBatch`、`createErrorToolResult`、`createToolResultMessage` 等函数负责异常与终止语义。

连续对话和自动跟进由 `Agent.continue()`、`steer()`、`followUp()` 以及 `prepareNextTurn` 共同驱动。`steer` 是当前 assistant turn 后注入的队列，`followUp` 是 agent 本来要停止时再继续的队列；两者的 drain 策略由 `QueueMode` 控制，可选 `"all"` 或 `"one-at-a-time"`。

如果使用 `AgentHarness`，主流程会再外包一层：harness 先处理 resources、session writes、hook events、prompt template / skill 载入和上下文构建，再启动底层 `Agent`。涉及长会话时，`harness/compaction/compaction.ts` 会根据 usage 或估算 token 判断是否压缩，选择 cut point，调用摘要模型生成 summary，并把压缩结果写回 session tree。

## 推荐阅读顺序

1. 先读 `packages/agent/src/types.ts`。这里定义 `AgentMessage`、`AgentState`、`AgentTool`、`AgentEvent`、`AgentLoopConfig`、hook context、session tree entry 等核心类型。理解这些类型后，其他文件会清晰很多。

2. 再读 `packages/agent/src/agent.ts`。重点看 `AgentOptions`、`Agent` 类、队列方法、生命周期方法和 `prompt()` / `continue()` 如何进入 loop。

3. 接着读 `packages/agent/src/agent-loop.ts`。重点看 `runLoop`、`streamAssistantResponse`、`executeToolCalls`、并行/顺序工具执行、tool result message 的生成逻辑。

4. 然后读 `packages/agent/src/harness/types.ts` 和 `packages/agent/src/harness/agent-harness.ts`。前者是 harness 的扩展类型面，后者是完整应用级编排层。

5. 如果关注持久化和恢复，读 `packages/agent/src/harness/session/session.ts`、`packages/agent/src/harness/session/jsonl-storage.ts`、`packages/agent/src/harness/session/jsonl-repo.ts`。

6. 如果关注长上下文能力，读 `packages/agent/src/harness/compaction/compaction.ts`，再看 `branch-summarization.ts`。

7. 最后按需读 `packages/agent/src/harness/skills.ts`、`prompt-templates.ts`、`system-prompt.ts`、`proxy.ts` 和 `harness/env/nodejs.ts`。

## 常见误区

不要把 `Agent` 和 `AgentHarness` 混为一谈。`Agent` 是状态机和 loop wrapper，负责 transcript、stream、tool execution、queue 和 events；`AgentHarness` 是更高层的运行框架，负责资源、会话、hooks、skills、templates、压缩等应用级事务。

不要以为 `packages/agent/src` 直接实现所有模型 provider。实际模型调用来自 `@earendil-works/pi-ai`，这里通过 `streamFn`、`Transport`、`Model`、`Message` 等类型和函数接入。`proxy.ts` 只是代理流式请求的工具，不是完整 provider 层。

不要把 session 当成普通数组日志。`harness/session/` 的数据模型是 session tree，条目包含 parent、leaf、label、compaction、branch summary 等语义；这解释了为什么压缩和分支摘要代码都围绕 `SessionTreeEntry` 工作。

不要只看 `index.ts` 判断复杂度。`index.ts` 只是导出面，真正主流程在 `agent.ts`、`agent-loop.ts` 和 `harness/agent-harness.ts`。

不要忽略 `node.ts` 与默认入口的差异。默认入口导出通用核心，`node.ts` 额外暴露 `NodeExecutionEnv`。如果代码需要读写文件或执行 shell，通常会用 Node 专用入口或自行提供符合 `ExecutionEnv` 的实现。

不要把 compaction 理解成简单截断。`compaction.ts` 会估算上下文、寻找 turn 边界 cut point、序列化对话、生成结构化摘要，并保留文件操作信息；它服务的是可恢复的长会话，而不只是减少 prompt 长度。
