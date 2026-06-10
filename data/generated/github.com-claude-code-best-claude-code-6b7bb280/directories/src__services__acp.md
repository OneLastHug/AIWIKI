# 子系统：src/services/acp

## 解决什么问题
`src/services/acp` 是 Claude Code 内部逻辑对外暴露 ACP（Agent Client Protocol）能力的适配层。它把外部 ACP 客户端发来的会话、提示词、权限请求、模式切换和历史恢复，转换成仓库内部的 `QueryEngine`、工具系统和会话状态更新。简单说，这个目录负责“让外部宿主像在控制一个 ACP agent 一样控制 Claude Code”，同时保持内部仍然走原有的对话、工具调用和权限管线。根据当前片段推断，它主要服务于外部 IDE/宿主集成场景，而不是普通 REPL 主路径。

## 相关目录和文件
核心文件是 `src/services/acp/entry.ts`、`src/services/acp/agent.ts`、`src/services/acp/bridge.ts`、`src/services/acp/permissions.ts`、`src/services/acp/utils.ts`、`src/services/acp/promptConversion.ts`。

`entry.ts` 负责把 Node 流包装成 ACP stream，并启动 `AcpAgent`。`agent.ts` 是主控制器，管理 session 生命周期、恢复、取消、模式/模型设置、历史回放。`bridge.ts` 负责把内部 `SDKMessage` 流翻译成 ACP 的 `SessionUpdate`。`permissions.ts` 专门处理工具权限桥接。`utils.ts` 提供权限模式解析、路径显示、标题清理、`Pushable` 等辅助能力。测试主要在 `src/services/acp/__tests__/`，覆盖 agent、bridge、permissions 和 prompt 转换。

## 核心对象
最关键的是 `AcpAgent`。它实现了 ACP 的 `Agent` 接口，内部维护 `sessions: Map<string, AcpSession>`。`AcpSession` 里装着 `QueryEngine`、当前 cwd、权限模式、模型列表、`toolUseCache`、待处理提示队列、`AppState` 和 commands。

另一个核心对象是 `forwardSessionUpdates()`。它消费 `QueryEngine.submitMessage()` 产生的 `SDKMessage` 异步流，把 system/result/assistant/stream_event/progress 等消息转成 ACP 通知。`toolInfoFromToolUse()`、`toolUpdateFromToolResult()` 和 `toAcpNotifications()` 则是消息翻译层的关键函数。

## 运行流程
入口在 `runAcpAgent()`：先启用配置，再把安全环境变量注入进进程，然后把 stdin/stdout 包装成 ACP stream，创建 `AgentSideConnection` 和 `AcpAgent`。连接关闭或收到 SIGINT/SIGTERM 时，会清理所有 session。

当客户端 `initialize/newSession/resumeSession/loadSession` 时，`AcpAgent` 会创建或复用 session：切换全局 session id、设置 cwd、加载工具和命令、构建 `QueryEngine`、初始化模式与模型状态，并把可用命令异步推给客户端。`prompt()` 时先把 ACP prompt 转成纯文本/资源说明，再交给 `QueryEngine.submitMessage()`；随后由 `forwardSessionUpdates()` 持续把流式消息转回 ACP。`cancel()` 会同时标记 session 取消、清空队列并中断查询引擎。

## 上下游依赖
上游依赖主要是 ACP SDK 和外部客户端：`@agentclientprotocol/sdk` 提供协议类型、连接、通知和 stream。另一个上游是配置与会话持久化：`src/utils/settings/settings.js`、`src/utils/sessionStorage.ts`、`src/utils/conversationRecovery.ts`。`agent.ts` 还依赖 `src/commands.ts`、`src/tools.ts`、`src/bootstrap/state.ts`、`src/state/AppStateStore.ts`。

下游则是 Claude Code 的内部主干：`QueryEngine` 才是真正执行对话和工具调用的引擎，`src/services/acp/bridge.ts` 把它的输出翻译给 ACP 客户端，`src/services/acp/permissions.ts` 则把内部权限决策反向交给 ACP 宿主确认。整体链路是“ACP 客户端 -> `AcpAgent` -> `QueryEngine`/工具系统 -> `bridge.ts` -> ACP 客户端”。

## 修改时最容易踩的坑
第一，session 状态有双写问题：`modes`、`models`、`configOptions`、`appState.toolPermissionContext` 必须同步更新，否则客户端看到的模式和真正执行的不一致。

第二，`toolUseCache` 不能随便清空。`bridge.ts` 依赖它把同一个 tool_use 的首次展示、后续结果和历史回放串起来。

第三，权限流很敏感。`permissions.ts` 里既有内部 `hasPermissionsToUseTool()` 结果，又有 ACP 客户端交互决策；`ExitPlanMode` 还是特殊分支，改错很容易破坏“计划模式退出”体验。

第四，历史恢复和当前会话不能混。`getOrCreateSession()` 会根据 fingerprint 决定是复用还是重建，改动 cwd 或 mcpServers 时尤其容易出现旧状态残留。

## 推荐阅读顺序
先读 `src/services/acp/entry.ts`，确认启动方式；再读 `src/services/acp/agent.ts`，把 session 生命周期和主流程串起来；然后读 `src/services/acp/bridge.ts`，理解消息如何被翻译成 ACP 事件；接着看 `src/services/acp/permissions.ts`，补齐权限路径；最后看 `src/services/acp/promptConversion.ts` 和 `src/services/acp/utils.ts`，把输入规范、路径显示和辅助逻辑补完。测试文件 `src/services/acp/__tests__/` 适合用来验证你对行为边界的理解。
