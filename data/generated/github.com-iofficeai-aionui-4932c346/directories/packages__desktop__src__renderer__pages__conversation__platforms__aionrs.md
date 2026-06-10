# 子系统：packages/desktop/src/renderer/pages/conversation/platforms/aionrs

## 解决什么问题

`packages/desktop/src/renderer/pages/conversation/platforms/aionrs` 是桌面端 renderer 里专门承接 `aionrs` 类型会话的页面子系统。它解决的是：当一个会话由 Aion CLI / AionCore 后端驱动时，前端如何渲染消息流、选择模型、发送输入、处理附件、展示工具执行状态、切换权限模式，以及把后端流式事件转成统一的对话 UI。

这个目录不是独立页面入口，而是 conversation 平台适配层的一部分。上层根据 `TChatConversation.type === 'aionrs'` 路由到这里；这里再复用通用的 `MessageList`、`SendBox`、`ThoughtDisplay`、命令队列、文件选择、预览面板、运行时状态等能力。它和 `platforms/acp` 并列，但 `aionrs` 的一个显著差异是模型是会话顶层字段 `model`，创建和更新时通过 `ipcBridge.conversation` 传给后端，而不是完全放在 `extra` 中。

## 相关目录和文件

核心文件集中在目标目录下：

`AionrsChat.tsx` 是会话容器组件，负责组装上下文、消息列表、artifact provider、图片根目录以及发送框。它把 `conversation_id`、`workspace`、`cron_job_id`、已加载 skills 和 MCP 状态写入 `ConversationContext`，供消息区和发送框读取。

`AionrsSendBox.tsx` 是交互最重的文件，承接输入框、附件、slash commands、模型必选校验、运行时 warmup、命令队列、停止生成、权限模式切换、移动端 action sheet 等逻辑。

`useAionrsMessage.ts` 负责监听 `ipcBridge.conversation.responseStream`，把后端事件转换为消息列表更新和本地运行状态：例如 `start`、`finish`、`thought`、`tool_group`、`permission`、`config_changed`、`error` 等。

`useAionrsModelSelection.ts` 封装 Aionrs 的模型选择状态。它读取 provider 列表，过滤掉 `gemini-with-google-auth` 平台，并在用户选择模型后调用上层 `onSelectModel` 持久化。

`AionrsModelSelector.tsx` 是模型选择按钮和下拉菜单组件，主要用于头部或移动端紧凑 UI 的模型展示和切换。

`localCronCommands.ts` 处理 assistant 回复里夹带的本地定时任务标签展示问题：它会剥离 `<think>` 和 `[CRON_*]` 标签，实际创建、更新、删除定时任务的动作根据注释由后端中间层处理。

邻近依赖主要在 `packages/desktop/src/renderer/pages/conversation/platforms/useConversationCommandQueue.ts`、`packages/desktop/src/renderer/pages/conversation/Messages/`、`packages/desktop/src/renderer/pages/conversation/runtime/`、`packages/desktop/src/renderer/pages/conversation/Workspace/`、`packages/desktop/src/renderer/pages/team/components/TeamChatView.tsx`。

## 核心对象

`AionrsChat` 是最外层的 Aionrs 会话组件。它通过 `ConversationProvider` 标记当前会话 `type: 'aionrs'`，并用 `MessageListProvider`、`MessageListLoadingProvider`、`LocalImageView.Provider` 包装，说明消息缓存、加载态和本地图片解析都是通用能力，但在这里绑定到当前 workspace。

`AionrsSendBox` 是发送控制器。它内部维护 `workspacePath`、`dynamicModes`、`currentMode`、移动端面板状态，以及草稿中的 `content`、`atPath`、`uploadFile`。发送前会调用 `warmupConversation` 和团队权限里的 `warmupSession`，再用 `ipcBridge.conversation.sendMessage.invoke` 发起请求。

`useAionrsMessage` 是流式消息状态机。它返回 `thought`、`running`、`setActiveMsgId`、`setWaitingResponse`、`resetState` 等值，供发送框展示思考状态和停止按钮。它使用 `activeMsgIdRef` 过滤旧请求的 thought，使用 `messageBufferRef` 累积文本，用于完成后处理 cron 标签。

`AionrsModelSelection` 是模型选择协议对象，包含 `current_model`、`providers`、`getAvailableModels`、`handleSelectModel` 和 `getDisplayModelName`。上层如 `TeamChatView.tsx` 会把 `onSelectModel` 实现为更新 `conversation.model`，并保存默认模型。

## 运行流程

进入 Aionrs 会话时，上层 `TeamChatView.tsx` 根据 `conversation.type` 懒加载 `AionrsChat`，同时创建 `useAionrsModelSelection`。`AionrsChat` 初始化消息缓存和确认恢复逻辑，并把 workspace 注入本地图片查看器，使消息中的本地图片可以按工作区解析。

发送框挂载后先读取会话缓存中的 `extra.workspace`，随后执行 `prepareRuntimeSync`：团队场景会先 warmup session，再 warmup 当前 conversation。warmup 成功后，`useSlashCommands` 才以 `conversation_type: 'aionrs'` 和 active 状态拉取 slash command 列表。

用户输入消息时，`onSendHandler` 会收集上传文件和工作区选择项，清空附件状态。如果当前运行时忙或已有排队命令，则进入 `useConversationCommandQueue`；否则直接执行 `executeCommand`。`executeCommand` 会校验 `current_model.use_model`，调用 `runtimeView.markSendStarted()`，拼装带文件上下文的展示消息，随后通过 `ipcBridge.conversation.sendMessage.invoke` 发送。成功后记录 `msg_id`、`turn_id` 和 runtime 状态，并触发历史刷新；如果带文件，还触发 `aionrs.workspace.refresh`。

后端响应通过 `responseStream` 推回。`useAionrsMessage` 按事件类型更新 `streamRunning`、`waitingResponse`、`hasActiveTools` 和 `thought`，并把消息交给通用 `transformMessage`、`useAddOrUpdateMessage` 渲染。`finish` 时还会读取 token usage，写回会话 `extra.last_token_usage`，并处理本地 cron 标签清理。

## 上下游依赖

上游入口主要是会话创建和路由。`packages/desktop/src/common/utils/buildAgentConversationParams.ts` 中 `getConversationTypeForBackend` 会把 `backend === 'aionrs'` 映射成 `type: 'aionrs'`；`packages/desktop/src/common/adapter/ipcBridge.ts` 中会话创建逻辑明确说明顶层 `model` 是 aionrs-only。团队聊天入口 `TeamChatView.tsx` 则在运行时把 `aionrs` 会话交给 `AionrsChat`。

下游依赖主要是后端 REST / WS 桥：`ipcBridge.conversation.sendMessage`、`stop`、`update`、`responseStream` 负责发送、停止、持久化模型或 token usage、接收流式事件。权限模式切换复用了 `ipcBridge.acpConversation.getMode/setMode`，说明 Aionrs 在模式协议上和 ACP 有兼容层。文件和工作区侧依赖 `FileAttachButton`、`useOpenFileSelector`、`useSendBoxFiles`、workspace 事件 `aionrs.selected.file`、`aionrs.workspace.refresh`。模型侧依赖 provider 配置、`useModelProviderList`、`TProviderWithModel` 和 `aionrs.defaultModel` 配置键。

## 修改时最容易踩的坑

第一，不能绕过模型校验。`AionrsSendBox` 在发送前必须确认 `current_model?.use_model`，否则后端无法知道本轮使用哪个 provider/model。Aionrs 的模型属于会话顶层 `model`，不要误放到 `extra` 里。

第二，流式状态不能只看 `finish`。Aionrs 会有工具执行、确认、thought、content 交错到达的情况，`hasActiveTools` 和 `waitingResponse` 的组合用于避免工具完成后 UI 过早解除 loading。

第三，`acp_permission` 在这里会被重标记为 `permission` 再交给 `transformMessage`。如果改消息协议，要注意这个兼容逻辑，否则确认卡片可能走错渲染分支。

第四，移动端和桌面端的模式切换路径不同。桌面走 `AgentModeSelector`，移动端走 `MobileActionSheet` 里的 `handleSheetModeChange`，两边都要保持 warmup、保存 preferred mode、传播 `propagateMode` 的行为一致。

第五，cron 标签只做前端展示清理。`localCronCommands.ts` 注释显示实际任务处理在后端 middleware，前端不要在这里重复创建任务。

第六，附件状态同时来自上传文件和 workspace 选择项，还通过 emitter 与 workspace 面板同步。修改清空、编辑队列、追加文件逻辑时，要同步处理 `aionrs.selected.file.clear` 和 `aionrs.selected.file` 事件。

## 推荐阅读顺序

建议先读 `packages/desktop/src/renderer/pages/team/components/TeamChatView.tsx`，了解 Aionrs 会话如何被路由进来，以及模型选择如何持久化。然后读 `AionrsChat.tsx`，建立容器、上下文、消息列表和发送框的整体关系。第三步读 `AionrsSendBox.tsx`，重点看 warmup、发送、队列、停止、附件和模式切换。第四步读 `useAionrsMessage.ts`，理解后端流式事件如何落到 UI 状态和消息列表。最后读 `useAionrsModelSelection.ts`、`AionrsModelSelector.tsx`、`localCronCommands.ts`，补齐模型选择和 cron 展示清理这些局部规则。
