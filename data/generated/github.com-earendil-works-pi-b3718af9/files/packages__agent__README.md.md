# 文件：packages/agent/README.md
## 一句话定位
这是 `@earendil-works/pi-agent-core` 的对外说明文档，核心作用是告诉使用者：如何创建一个带状态、能执行工具、还能持续流式输出事件的 Agent。根据当前片段推断，它对应的是 `packages/agent` 这个包的入口说明，而不是单纯的示例页，因为 README 同时覆盖了安装、API、事件序列和运行时语义。

## 它暴露/定义了什么
README 主要定义了这个包的公共心智模型：`Agent` 类、`AgentState`、消息类型 `AgentMessage`、事件类型 `AgentEvent`，以及与工具执行、上下文转换、持续对话相关的配置项。它还说明了几个关键能力：`prompt()`、`continue()`、`subscribe()`、`state` 访问、`toolExecution` 模式、`beforeToolCall` / `afterToolCall` 钩子。结合 `src/index.ts` 可以看出，这个包对外不仅导出 `Agent`，还导出一整套 loop、harness、compaction、proxy 和类型工具。

## 谁调用它
直接调用者是使用这个库的应用代码，通常从 `@earendil-works/pi-agent-core` 导入 `Agent` 后实例化，再通过 `prompt()` 发起一次对话，或者通过 `subscribe()` 接收状态变化。更上层一点，UI、CLI、服务端编排层都会把它当成一个会“自己推进轮次”的会话引擎来用。根据 README 的事件流描述，调用者最常关心的是把 `message_update` 接到界面流式渲染，把 `tool_execution_*` 接到工具面板或日志。

## 它调用谁
从实现痕迹看，README 背后的实现依赖 `src/agent.ts` 和 `src/agent-loop.ts`。`Agent` 内部会调用 `runAgentLoop`、`runAgentLoopContinue`，而 loop 逻辑再借助 `@earendil-works/pi-ai` 的 `streamSimple`、`EventStream`、`validateToolArguments`、消息与工具结果类型完成真正的 LLM 请求与工具执行。README 也说明它依赖 `convertToLlm()` 把 `AgentMessage[]` 适配成模型可理解的 `Message[]`。

## 核心流程
典型流程是：调用者创建 `Agent`，传入初始状态和可选配置；随后调用 `prompt()` 追加用户消息；Agent 先发 `agent_start`、`turn_start`，再发用户消息事件，然后流式接收助手消息；如果助手产出 tool call，就进入工具执行分支，依次或并发执行工具，再把 tool result 写回上下文，最后进入下一轮 LLM 调用，直到 `agent_end`。README 还强调了一个关键点：`message_end` 之后才进入工具预检，这保证了 `beforeToolCall` 看到的是已经包含助手消息的状态。

## 关键函数的高层作用
`Agent` 是主入口，负责状态、队列、订阅和运行控制。`prompt()` 用来启动一次新回合，`continue()` 用来在已有上下文上继续，适合重试或恢复。`subscribe()` 让外部消费生命周期事件。`agentLoop()` 和 `agentLoopContinue()` 是更底层的循环入口，通常服务于高级封装。`convertToLlm()` 负责消息裁剪和格式转换，`transformContext()` 负责在送入模型前做上下文整理，`beforeToolCall` / `afterToolCall` 负责拦截、审计或终止工具链路。

## 修改风险
这个 README 虽然不影响运行时，但它直接定义了使用者对 API 的理解，改错会造成文档与实现漂移。高风险点是事件顺序、`toolExecution` 语义、`state` 的可变性、`continue()` 的前置条件，以及 `convertToLlm()` 对自定义消息的过滤规则。因为 README 同时承载安装说明和公共行为说明，一旦 `src/agent.ts`、`src/agent-loop.ts` 或 `src/index.ts` 的导出面变化而这里没同步，用户很容易按旧语义接入，导致调试成本上升。
