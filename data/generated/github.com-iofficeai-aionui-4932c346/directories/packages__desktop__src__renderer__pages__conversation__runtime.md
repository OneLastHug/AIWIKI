# 子系统：packages/desktop/src/renderer/pages/conversation/runtime

## 解决什么问题
这个目录负责“会话运行态”的前端同步层。根据当前片段推断，它不是承载消息内容本身，而是把一次 conversation 在前端需要立即知道的运行状态抽成统一视图：当前是否正在处理、能不能继续发消息、是否有活跃 turn、是否存在本地发送中/停止中的临时门闩、是否已经完成 hydration，以及这些状态变化对应的日志事件。

它的价值在于把来自三个来源的信息合并起来：初始从本地会话缓存读取的 runtime 摘要、后续来自 `ipcBridge.conversation.turnCompleted` 和 `ipcBridge.conversation.listChanged` 的事件、以及发送/停止等本地交互过程。这样 `ChatConversation`、`AcpSendBox`、`AionrsSendBox` 只需要消费一个统一的 `useConversationRuntimeView()`，不用各自处理复杂的竞态和状态回填。

## 相关目录和文件
- `packages/desktop/src/renderer/pages/conversation/runtime/conversationRuntimeViewStore.ts`：核心状态仓库，维护按 `conversation_id` 分桶的 runtime view、metadata、订阅者和日志。
- `packages/desktop/src/renderer/pages/conversation/runtime/useConversationRuntimeView.ts`：React hook 封装，负责 hydration、监听 IPC 事件、暴露发送/停止相关的标记方法。
- `packages/desktop/src/renderer/pages/conversation/components/ChatConversation.tsx`：页面级消费方，创建 `useConversationRuntimeView(conversation.id)`，用于模型切换时判断是否需要先停掉运行中的 turn。
- `packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpSendBox.tsx`、`packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsSendBox.tsx`：发送框消费方，用 runtime view 判断 busy 状态、驱动发送流程。
- `packages/desktop/src/renderer/pages/conversation/platforms/*/use*Message.ts`：消息流处理侧会调用 `logStreamTerminalObserved()`，帮助记录流终止点。
- `packages/desktop/src/renderer/pages/conversation/utils/conversationCache.ts`：hydration 的数据来源之一，hook 会从这里读取会话及其 runtime。

## 核心对象
- `ConversationRuntimeView`：目录的核心数据结构，字段包括 `state`、`isProcessing`、`canSendMessage`、`activeTurnId`、`pendingConfirmations`、`hasBackendRuntime`、`localSubmitting`、`localStopping`、`hydrated`。
- `ConversationRuntimeViewLogEntry`：状态变化日志，带 `level`、`event` 和合并后的上下文数据。
- `ConversationRuntimeMetadata`：内部辅助态，记录 `pendingLocalSendSeq`、`pendingStopTurnId`、`lastCompletedTurnId`，用于处理竞态和过期回包。
- `runtimeViews`、`fallbackSnapshots`、`runtimeMetadata`：三个按 `conversation_id` 索引的内存容器，分别存主状态、兜底快照和辅助元数据。
- 一组状态转换函数：`hydrateStarted`、`hydrateSucceeded`、`turnCompleted`、`localSendStarted`、`localSendAccepted`、`localSendFailed`、`localStopRequested`、`localStopAcknowledged`、`conversationDeleted`、`resetLocalGate`。

## 运行流程
1. 页面或发送框调用 `useConversationRuntimeView(conversation_id)`。
2. hook 先通过 `useSyncExternalStore` 订阅 store，再在 `useEffect` 中触发 `hydrateStarted()`，让视图进入“正在初始化”的状态。
3. 随后它从 `getConversationOrNull(conversation_id)` 读取会话缓存；成功则调用 `hydrateSucceeded()`，失败则调用 `hydrateFailed()`。
4. hook 再监听 `ipcBridge.conversation.turnCompleted` 和 `ipcBridge.conversation.listChanged`。前者更新 turn 收尾状态，后者在会话被删除时清空对应 runtime view。
5. 当用户本地开始发送、发送成功、发送失败、请求停止或停止确认时，组件调用对应的 `markSend*`、`markStop*` 方法，本质上都是写回 store 并刷新订阅者。
6. store 在每次状态切换时生成日志，hook 会把这些日志通过 `ipcBridge.application.writeRendererLog` 写入渲染进程日志通道。

## 上下游依赖
上游主要依赖两类数据源：一是 `@/common/config/storage` 里的 `TConversationRuntimeSummary` 和 `TConversationRuntimeStateKind`，这是 runtime 摘要的结构来源；二是 `ipcBridge`，尤其是 `conversation.turnCompleted`、`conversation.listChanged` 和 `application.writeRendererLog`。

下游则是会话页内多个交互面板。`ChatConversation.tsx` 利用 `activeTurnId` 在切换模型时决定是否先调用 stop；`AcpSendBox.tsx`、`AionrsSendBox.tsx` 利用 `isProcessing` 和 `canSendMessage` 控制发送框是否可用；消息解析侧通过 `logStreamTerminalObserved()` 给运行态补充流终止证据。根据当前片段推断，这里是 conversation 页面里最接近“状态中枢”的一层。

## 修改时最容易踩的坑
- 只改 UI，不改 store 里的竞态处理，容易让“本地发送中”或“停止中”卡死。
- 忽略 `pendingLocalSendSeq`、`pendingStopTurnId`、`lastCompletedTurnId`，会把过期回包当成新状态，尤其在快速连续发送、停止、切模型时最明显。
- 直接绕过 `hydrateStarted` / `hydrateSucceeded` / `hydrateFailed`，会让订阅者拿不到一致的 hydrated 生命周期。
- 删除会话时如果不走 `conversationDeleted()`，内存里的 `runtimeViews` 和 `fallbackSnapshots` 可能残留旧状态。
- 新增日志事件时如果不同步 `ConversationRuntimeViewLogEvent`，`logConversationRuntimeView()` 的上报语义会变得不完整。
- 这个目录完全在 renderer 侧，不能引入 Node.js 依赖；同时也不应该把 IPC 细节散落到页面组件里。

## 推荐阅读顺序
1. 先看 `packages/desktop/src/renderer/pages/conversation/runtime/conversationRuntimeViewStore.ts`，理解状态模型和转换规则。
2. 再看 `packages/desktop/src/renderer/pages/conversation/runtime/useConversationRuntimeView.ts`，理解它如何把 store 接到 React 和 IPC。
3. 接着看 `packages/desktop/src/renderer/pages/conversation/components/ChatConversation.tsx`，确认 runtime view 在页面层如何影响交互。
4. 再看 `packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpSendBox.tsx`、`packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsSendBox.tsx`，理解发送框如何消费这些状态。
5. 最后回看 `packages/desktop/src/renderer/pages/conversation/platforms/*/use*Message.ts` 和 `packages/desktop/src/renderer/pages/conversation/utils/conversationCache.ts`，把 runtime 的输入输出链路补完整。
