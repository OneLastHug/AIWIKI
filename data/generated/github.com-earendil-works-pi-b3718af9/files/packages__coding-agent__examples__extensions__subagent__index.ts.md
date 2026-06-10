# 文件：packages/coding-agent/examples/extensions/subagent/index.ts
## 一句话定位
这是一个给 `pi` 编码代理扩展使用的 `subagent` 工具实现：它把一次任务拆成一个或多个独立子代理进程执行，并把执行过程、工具调用和最终结果重新汇总回主会话。

## 它暴露/定义了什么
它默认导出一个扩展安装函数 `default function (pi: ExtensionAPI)`，在里面注册了名为 `subagent` 的工具。这个工具接受三种输入模式：单任务 `agent + task`、并行 `tasks`、链式 `chain`。  
文件内还定义了结果结构 `SingleResult`、聚合结构 `SubagentDetails`、参数 schema，以及若干辅助函数：`discoverAgents` 负责找可用 agent，`runSingleAgent` 负责真正拉起子进程，`getFinalOutput`、`getResultOutput`、`getDisplayItems`、`formatUsageStats` 等负责整理展示信息。

## 谁调用它
根据当前片段推断，它由 `pi-coding-agent` 的扩展加载器调用：运行时把 `ExtensionAPI` 传进默认导出函数，然后由 `pi.registerTool` 挂到工具系统里。  
真正触发执行的是上层模型/会话在调用工具 `subagent` 时进入 `execute`。

## 它调用谁
它主要调用 `discoverAgents` 读取用户级或项目级 agent 定义，调用 `spawn` 启动外部 `pi` 进程，调用 `withFileMutationQueue` 安全写入临时 system prompt，调用 `getMarkdownTheme`、`Container`、`Markdown`、`Text`、`Spacer` 生成 TUI 展示内容。  
还会用 `ctx.ui.confirm` 在启用项目本地 agent 时做确认。

## 核心流程
1. 解析参数并判断模式是否唯一。  
2. 按 `agentScope` 发现可用 agent。  
3. 若请求项目内 agent，且界面存在，就弹确认框，避免无意执行仓库控制的配置。  
4. 单任务模式直接调用 `runSingleAgent`；并行模式用 `mapWithConcurrencyLimit` 限流执行；链式模式把前一步输出替换进 `{previous}` 再继续下一步。  
5. 子进程通过 JSON 行流回传消息，工具会把 assistant 消息、tool result、usage、stopReason、errorMessage 逐步累积到 `currentResult`，并通过 `onUpdate` 做流式刷新。  
6. 最终返回文本内容和 `details`，供主界面折叠/展开展示。

## 关键函数的高层作用
`runSingleAgent` 是核心执行器：校验 agent 是否存在，拼接 `pi --mode json -p --no-session` 参数，必要时追加 system prompt 临时文件，然后 spawn 子进程，解析 stdout 的 JSON 事件流并收集结果。  
`getPiInvocation` 负责判断当前环境应直接调用当前 Node/Bun 进程，还是退回到 `pi` 命令。  
`truncateParallelOutput` 只是在并行结果过长时截断，避免展示面板爆炸。  
其余格式化函数主要服务于 UI 呈现，不改变业务语义。

## 修改风险
这个文件改动的风险偏高，因为它同时碰工具协议、子进程执行、并发控制和结果展示。最容易出问题的点有：参数 schema 改动导致上层调用失败，JSON 事件解析和 `pi` 协议不一致导致结果丢失，临时 prompt 文件清理不完整导致泄漏，并行限流或 abort 处理不当导致任务悬挂，项目级 agent 的确认逻辑变化带来安全边界变化。  
如果要改功能，优先保持 `execute` 返回结构、`SingleResult` 字段和子进程 JSON 协议稳定。
