# 架构分层与模块边界

## 总体分层

从当前目录结构和入口文件看，本项目可以分成七层：入口分发层、CLI 命令层、交互 UI 层、会话主循环层、服务与集成层、工具与扩展层、workspace 支撑包层。入口分发层是 `src/entrypoints/cli.tsx` 和 `src/entrypoints/init.ts`；CLI 命令层是 `src/main.tsx` 与 `src/commands.ts`、`src/commands/`；交互 UI 层是 `src/replLauncher.tsx`、`src/screens/REPL.tsx`、`src/components/`、`src/hooks/`、`src/state/`；会话主循环层是 `src/QueryEngine.ts`、`src/query.ts`、`src/context.ts`、`src/utils/messages.ts` 等；服务与集成层是 `src/services/`；工具与扩展层是 `src/Tool.ts`、`src/tools.ts`、`packages/builtin-tools/src/tools/`、`src/skills/`、`src/plugins/`、`src/services/mcp/`；workspace 支撑包层是 `packages/` 下的 Ink、MCP client、model provider、ACP link、remote-control server、本地 NAPI 能力等。

这个分层不是严格的洋葱架构。由于项目是 CLI agent，UI、状态、工具、会话和服务之间存在大量回调和上下文对象传递。例如 `REPL.tsx` 既管理输入和渲染，也组装 `ToolUseContext`，并通过 `handlePromptSubmit()` 进入查询；`QueryEngine` 同时依赖 commands、tools、MCP clients、AppState getter/setter、file cache、model 设置和权限函数；工具执行时又可能回写 AppState、追加系统消息、发通知、请求用户权限。读代码时更适合把它理解为“以会话为中心的协作架构”，而不是纯函数管线。

## 入口与命令边界

`src/entrypoints/cli.tsx` 是最外层入口。它的边界职责很清楚：做极少量同步初始化，解析 `process.argv`，对特殊路径使用动态 import 快速退出。它处理 `--version`、`--dump-system-prompt`、Chrome MCP、Computer Use MCP、`--acp`、`weixin`、`--daemon-worker`、remote-control/bridge、daemon、autonomy 等路径；如果没有命中特殊路径，才进入完整 CLI。这个文件不应该承载业务细节，它主要是启动性能和模式分发。

`src/main.tsx` 是完整 CLI 的命令注册和启动编排层。它引入 Commander，注册 `mcp`、`auth`、`plugin`、`agents`、`doctor`、`update`、`server`、`ssh`、`open`、`auto-mode`、`autonomy` 等命令，同时也负责主 action 中的配置、认证、MCP、插件、skills、REPL/headless 分发。`src/commands.ts` 与 `src/commands/` 则负责 REPL 内部 slash commands 的集合。两者的边界是：`main.tsx` 处理进程级 CLI 子命令，`commands.ts` 处理会话内命令和 skills/plugin/workflow 命令聚合。它们都叫 command，但处在不同层级。

## UI 与状态边界

交互 UI 的根路径是 `src/replLauncher.tsx` 动态加载 `src/components/App.tsx`、`SentryErrorBoundary` 和 `src/screens/REPL.tsx`，再通过 `renderAndRun()` 挂载。`src/components/App.tsx` 结合 `AppStateProvider`、Stats、FPS 等上下文；`src/screens/REPL.tsx` 是主工作台，负责读取输入、显示消息、处理 prompt submit、权限请求、MCP elicitation、通知、远程会话、背景任务和各种面板。

状态分两种。第一种是 React AppState，定义在 `src/state/AppStateStore.ts`，通过 `src/state/AppState.tsx` 的 store provider 暴露给组件。它包含 settings、verbose、model、permission context、MCP clients/tools/resources、plugin 状态、agentDefinitions、fileHistory、todos、notifications、elicitation、sessionHooks、远程桥接状态、语音/任务/浏览器面板等。第二种是模块级会话状态，集中在 `src/bootstrap/state.ts`，包括 original cwd、project root、session id、成本、API duration、token、模型覆盖、telemetry providers、last API request、cached CLAUDE.md、session-only flags 等。根据当前文件推断，AppState 更偏 UI 和可响应状态，bootstrap state 更偏进程级、会话级、跨组件共享的单例状态。

## 会话主循环边界

会话主循环的最重要边界是 `QueryEngine` 和 `query()`。`src/QueryEngine.ts` 的注释明确说它是“one QueryEngine per conversation”，`submitMessage()` 每次调用代表同一 conversation 中的新 turn。它持有 mutable messages、read file cache、usage、permission denials、discovered skills 等状态，并把用户 prompt、commands、tools、MCP clients、AppState、model 设置、json schema、task budget 等配置传入底层查询。

`src/query.ts` 更接近 agent loop 的执行器。它接收 messages、system prompt、user/system context、canUseTool、ToolUseContext、querySource、budget 等参数，处理 auto compact、token warning、skill/search prefetch、消息规范化、流式 API、工具调用、tool result、stop hooks、tool use summary、cache warning、错误恢复等。`src/services/api/claude.ts` 是主循环和模型服务之间的边界：上游传来内部消息和工具定义，下游返回 Anthropic 风格的 assistant/system/error/stream event 消息。OpenAI/Gemini/Grok 等兼容层在这个边界内适配，避免影响上游 `query()` 的主结构。

## 工具边界

工具接口在 `src/Tool.ts`，其中 `ToolPermissionContext` 描述权限模式、allow/deny/ask rules、附加工作目录、bypass 可用性、auto mode 等；`ToolUseContext` 描述工具执行时能访问的 options、abortController、file cache、AppState getter/setter、通知、OS notification、MCP resources、agent definitions、hooks、Langfuse span 等。这个类型文件是理解工具为何能影响 UI、权限和会话状态的关键。

`src/tools.ts` 是工具池装配边界。`getAllBaseTools()` 声明所有可能内置工具，`getTools()` 根据 simple mode、REPL mode、feature flag、env、权限 deny rules 和 `isEnabled()` 过滤，`assembleToolPool()` 再把内置工具与 MCP tools 合并、排序、去重。工具实际执行由 `src/services/tools/toolOrchestration.ts` 负责。它会把模型返回的 tool_use blocks 切成并发安全批次：连续 read-only 且 `isConcurrencySafe()` 为真的工具可并发执行，非并发安全工具串行执行。这个设计说明工具实现需要正确声明 schema、权限和并发安全属性。

## 服务层边界

`src/services/` 下是外部系统和跨领域服务的集合，不是单一抽象层。`src/services/api/` 管模型 API、provider、错误和请求日志；`src/services/mcp/` 管 MCP transport、tools、resources、prompts、OAuth 和 elicitation；`src/services/compact/` 管上下文压缩；`src/services/acp/` 管 Agent Client Protocol；`src/services/langfuse/` 管观测；`src/services/lsp/` 管 LSP；`src/services/plugins/` 管插件服务；`src/services/policyLimits/` 和 `remoteManagedSettings/` 管远端策略与配置；`src/services/tools/` 管工具执行编排。初学者不要把 `services` 误解为“所有业务逻辑都在这里”，它更像一组外部能力适配器和横切能力。

## 扩展点

项目的显式扩展点至少有五个。第一是新增 CLI 子命令：进程级命令加在 `src/main.tsx`，会话内 slash command 加在 `src/commands/` 并由 `src/commands.ts` 聚合。第二是新增内置工具：在 `packages/builtin-tools/src/tools/` 增加实现，再在 `src/tools.ts` 注册，并考虑权限、feature flag、并发安全和 MCP 合并规则。第三是新增 skill：`src/skills/bundled/index.ts` 注释说明创建 `src/skills/bundled/<name>.ts` 并调用 `registerBundledSkill()`；用户/插件 skills 则由 `src/skills/loadSkillsDir.ts` 和插件命令加载路径处理。第四是新增 provider：需要关注 `src/utils/model/providers.ts`、`src/services/api/client.ts`、`src/services/api/claude.ts` 和具体兼容目录。第五是新增远程/协议能力：ACP 在 `src/services/acp/` 和 `packages/acp-link/`，Remote Control 在 `src/bridge/` 和 `packages/remote-control-server/`，MCP 在 `src/services/mcp/` 与 `packages/mcp-client/`。

## 依赖方向

根据当前文件推断，主依赖方向大致是：入口层调用命令层；命令层准备 UI 或 headless 参数；UI 层调用输入处理和 QueryEngine；QueryEngine 调用 query；query 调用 API 服务和工具编排；工具编排调用具体工具；具体工具通过 ToolUseContext 回写状态或结果。反向依赖主要通过回调、context 和 store 完成，而不是直接 import 上层模块。例如工具不会直接控制 REPL 渲染，而是通过 `setToolJSX`、`appendSystemMessage`、`addNotification`、`setAppState` 等上下文能力影响 UI。理解这一点能帮助读者避免在大型文件中迷路。
