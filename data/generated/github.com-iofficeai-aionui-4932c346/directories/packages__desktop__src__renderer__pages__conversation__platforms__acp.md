# 子系统：packages/desktop/src/renderer/pages/conversation/platforms/acp

## 解决什么问题
这个目录负责 ACP 会话在 renderer 侧的整套交互壳层：把会话消息流、输入框、附件、模式切换、停止响应、初始消息自动发送、以及调试用的 E2E 流注入串起来。根据当前片段推断，它是 `conversation` 页面里“ACP/Codex 类会话”的专用平台实现，既承担正常聊天，也承担把后端 `ipcBridge.acpConversation` 的响应流转换成页面消息状态的任务。

## 相关目录和文件
核心入口是 `AcpChat.tsx`，它被 `conversation/components/ChatConversation.tsx` 选中并渲染。`AcpSendBox.tsx` 是输入区主逻辑，`useAcpMessage.ts` 负责订阅 `responseStream` 并维护运行态，`useAcpInitialMessage.ts` 处理从 `sessionStorage` 注入的首条消息，`buildSendFailureError.ts` 则把发送失败转换成页面可消费的错误结构。`AcpE2EStreamInjector.tsx` 只服务于端到端测试或调试场景。

它还强依赖父级的消息体系与运行态：`conversation/Messages/*`、`conversation/runtime/useConversationRuntimeView`、`conversation/utils/warmupConversation`、`renderer/hooks/context/ConversationContext`。`LegacyReadOnlyConversation.tsx` 是同一套消息展示框架的只读变体，可作为对照理解。

## 核心对象
`AcpChat` 是平台容器，负责注入 `ConversationProvider`、`ConversationArtifactProvider`，并把 `MessageList` 与 `AcpSendBox` 组合起来。  
`AcpSendBox` 是最复杂的控制器，包含草稿缓存、文件附件、MCP 状态展示、技能快捷注入、模式选择器、移动端 action sheet、发送与停止。  
`useAcpMessage` 返回 `UseAcpMessageReturn`，里面有 `running`、`aiProcessing`、`thought`、`tokenUsage`、`slashCommands` 等状态。  
`useAcpInitialMessage` 是副作用 hook，只在挂载时尝试读取并发送一次初始消息。  
`AcpE2EStreamInjector` 提供测试控制器，向全局 `window.__AIONUI_E2E_MESSAGE_STREAM__` 注册流式消息工具。

## 运行流程
入口通常从 `ChatConversation.tsx` 进入：当 `conversation.type === 'acp'` 时渲染 `AcpChat`。`AcpChat` 先预热消息缓存与挂起确认恢复，再调用 `useAcpMessage(conversation_id)` 监听后端流，最后把页面分成消息列表和发送框两部分。

发送时，`AcpSendBox` 会先整理草稿、附件和工作区路径，再调用 `ipcBridge.acpConversation.sendMessage.invoke(...)`。成功后更新 runtime view，并触发 `chat.history.refresh`。失败时走 `buildSendFailureError`，必要时把认证错误转换成一条 `responseStream.emit(...)` 的错误消息，保证消息流和 UI 状态一致。

接收侧由 `useAcpMessage` 统一处理：它订阅 `ipcBridge.acpConversation.responseStream.on(...)`，根据 `start`、`thinking`、`finish`、`error tip` 等消息更新 `running`、`turnFinished`、`hasThinkingMessage` 和思考态消息。`useAcpInitialMessage` 则在首屏时检查 `sessionStorage` 里的 `acp_initial_message_${conversation_id}`，用于从引导页或跳转动作自动补发首条内容。

## 上下游依赖
上游主要是会话元数据和运行时上下文：`conversation.extra.workspace`、`session_mode`、`backend`、`skills`、`mcp_servers`、`mcp_statuses`、`agent_name`，以及 team 场景下的 `TeamPermissionContext`。这些数据决定是否显示模式选择、是否要 warmup、以及 MCP/技能菜单内容。

下游主要是 IPC 和消息系统：`ipcBridge.acpConversation.getMode`、`setMode`、`sendMessage`、`responseStream`、`conversation.stop`，还有 `MessageListProvider`、`useAddOrUpdateMessage`、`useConversationRuntimeView`、`usePreviewContext`。`ChatConversation.tsx` 是上层分发点，`LegacyReadOnlyConversation.tsx` 和 `aionrs` 平台目录是横向对照实现。

## 修改时最容易踩的坑
最容易出问题的是状态同步。`useAcpMessage` 同时维护 `runningRef`、`turnFinishedRef`、`activeThinkingRef`，改动时很容易出现“消息已经结束但 UI 还在转”或“下一轮被误判为旧轮次”的问题。`AcpSendBox` 里 mobile sheet 的模式同步也比较脆弱，尤其是 team 场景下的 warmup 与 `propagateMode`。

另一个高风险点是重复发送。`useAcpInitialMessage` 依赖 `sessionStorage` 立即清除键值，不能把清理挪到异步发送成功之后，否则重挂载会重复发。文件附件、工作区选择和 `sendbox.fill` 事件也共享同一份草稿状态，改动时要注意不要打破 `useLatestRef` 的注册方式。

如果新增错误分支，要同时检查 `buildSendFailureError` 和 `AcpSendBox` 的 catch 逻辑，否则页面提示、消息流和 runtime 状态会分叉。E2E 注入器只应在特定 `sessionStorage` 开关打开时生效，否则会污染正常会话。

## 推荐阅读顺序
1. `conversation/components/ChatConversation.tsx`
2. `conversation/platforms/acp/AcpChat.tsx`
3. `conversation/platforms/acp/useAcpMessage.ts`
4. `conversation/platforms/acp/AcpSendBox.tsx`
5. `conversation/platforms/acp/useAcpInitialMessage.ts`
6. `conversation/platforms/acp/buildSendFailureError.ts`
7. `conversation/platforms/acp/AcpE2EStreamInjector.tsx`
