# 子系统：packages/desktop/src/renderer/pages/conversation/platforms

## 解决什么问题
这个目录负责把“会话页”拆成不同平台的运行壳。表面上它们都在展示消息列表和发送框，实际上每个平台的交互协议、模型切换方式、历史兼容策略都不一样，所以需要这一层做适配。  
从当前代码看，这里主要覆盖三类场景：`acp` 的可交互会话、`aionrs` 的模型选择和消息发送、以及 `legacy` 旧类型会话的只读回放。它们统一接到上层的 `ChatConversation` 和 `ChatLayout`，让页面入口只需要关心“当前会话是什么类型”，不用把协议细节散落到页面各处。

## 相关目录和文件
核心文件是 `useConversationCommandQueue.ts`、`assertBridgeSuccess.ts`，以及三个平台子目录：`acp/`、`aionrs/`、`legacy/`。其中 `acp/AcpChat.tsx`、`acp/AcpSendBox.tsx` 负责 ACP 会话壳和输入区，`aionrs/AionrsChat.tsx`、`aionrs/AionrsSendBox.tsx` 负责 Aionrs 会话，`gemini/GoogleModelSelector.tsx` 和 `aionrs/AionrsModelSelector.tsx` 负责头部模型选择器。  
上层最直接的调用点在 `packages/desktop/src/renderer/pages/conversation/components/ChatConversation.tsx`，它根据会话 `type` 选择渲染哪个平台壳；兼容分支判断则依赖 `packages/desktop/src/renderer/pages/conversation/utils/conversationRuntime.ts`。

## 核心对象
`useConversationCommandQueue` 是这一层最像“基础设施”的对象。它维护会话级命令队列，带有 `MAX_QUEUED_COMMANDS`、输入长度、文件数和序列化体积上限，并通过 `sessionStorage` 做恢复。根据当前片段推断，它的目标是让发送命令在页面刷新、短暂中断后还能续上，同时避免队列失控。  
`AcpChat`、`AionrsChat`、`LegacyReadOnlyConversation` 是三个平台壳：前两者都包着 `ConversationProvider`、`MessageListProvider`、`ConversationArtifactProvider`，差别在于是否渲染发送框、是否注入实时流、是否更新本地图片根目录。  
`assertBridgeSuccess` 是一个很薄的 IPC 结果校验器，用来把桥接返回值统一成“成功就拿数据，失败就抛错”的语义。

## 运行流程
页面上层拿到 `TChatConversation` 后，先判断类型：`aionrs` 走专用面板，legacy 类型直接只读展示，`acp` 进入可交互会话壳。  
进入平台壳后，公共部分基本一致：先用 `useMessageLstCache`、`usePendingConfirmationsRecovery` 恢复消息和待确认状态，再通过 `ConversationProvider` 把 `conversation_id`、`workspace`、`cron_job_id`、`loadedSkills` 等上下文注入子树，消息区统一由 `MessageList` 渲染。  
差异部分主要在发送框和模型切换：`AcpSendBox`、`AionrsSendBox` 会接入 `useConversationCommandQueue` 或各自的消息 hook；`Aionrs` 还会在切换模型时停止当前 turn，并保存默认模型。`legacy` 则明确关闭发送框，只保留历史消息浏览。

## 上下游依赖
上游输入主要是 `TChatConversation`、`ConversationContext`、`LayoutContext`、`usePresetAssistantInfo`、`useConversationRuntimeView`，以及 `ipcBridge.conversation.*` 提供的创建、更新、停止、关联会话等能力。  
下游依赖则集中在 `MessageList`、`ConversationArtifactProvider`、`ChatLayout`、`CronJobManager`、`LocalImageView` 和各平台发送框。也就是说，这一层本质上是“会话数据模型 + IPC 能力”到“统一聊天 UI”之间的适配器。

## 修改时最容易踩的坑
第一，别把平台类型判断改散。`ChatConversation.tsx` 里已经把 `acp`、`aionrs`、legacy 兼容类型分开处理，新增平台时必须同步这几个分支，否则会出现能进页面但没发送框、没头部按钮或直接空白的情况。  
第二，命令队列有硬限制。`useConversationCommandQueue.ts` 不只是缓存，它还检查输入长度、文件数、状态字节数，超限会直接拒绝或截断。  
第三，`AionrsChat` 会更新 `LocalImageView` 的根目录，改动 workspace 相关逻辑时容易漏掉图片预览路径。  
第四，legacy 会话是只读语义，不能因为复用壳组件就顺手加回发送能力。

## 推荐阅读顺序
1. `packages/desktop/src/renderer/pages/conversation/components/ChatConversation.tsx`，先看平台分流总入口。  
2. `packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpChat.tsx`、`packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsChat.tsx`，理解两种主会话壳。  
3. `packages/desktop/src/renderer/pages/conversation/platforms/useConversationCommandQueue.ts`，看发送命令如何排队和持久化。  
4. `packages/desktop/src/renderer/pages/conversation/platforms/legacy/LegacyReadOnlyConversation.tsx`，看兼容层如何降级。  
5. `packages/desktop/src/renderer/pages/conversation/platforms/gemini/GoogleModelSelector.tsx`、`packages/desktop/src/renderer/pages/conversation/utils/conversationRuntime.ts`，补齐模型选择和旧类型判定。
