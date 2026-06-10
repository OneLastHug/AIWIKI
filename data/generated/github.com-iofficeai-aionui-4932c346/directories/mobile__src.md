# 目录：mobile/src

## 它可能负责什么
这个目录包含 49 个被抽样展示的文件。请从文件命名、子目录和关键源码入手理解它在项目中的职责。

## 文件列表节选
```text
mobile/src/components/conversation/NewConversationModal.tsx
mobile/src/components/conversation/ConversationList.tsx
mobile/src/components/conversation/ConversationItem.tsx
mobile/src/components/ui/ThemedView.tsx
mobile/src/components/ui/ThemedText.tsx
mobile/src/components/ui/ConnectionBanner.tsx
mobile/src/components/files/WorkspaceFilesSidebar.tsx
mobile/src/components/files/MobileFileTabHeader.tsx
mobile/src/components/files/FileContentView.tsx
mobile/src/components/chat/ChatEmptyState.tsx
mobile/src/components/chat/WorkspaceGroup.tsx
mobile/src/components/chat/ModePickerSheet.tsx
mobile/src/components/chat/MessageBubble.tsx
mobile/src/components/chat/ToolCallSummary.tsx
mobile/src/components/chat/PendingChatScreen.tsx
mobile/src/components/chat/FilePickerSheet.tsx
mobile/src/components/chat/ChatScreen.tsx
mobile/src/components/chat/ConfirmationCard.tsx
mobile/src/components/chat/WorkspacePickerSheet.tsx
mobile/src/components/chat/ModelPickerSheet.tsx
mobile/src/components/chat/ChatInputBar.tsx
mobile/src/components/chat/ChatSidebar.tsx
mobile/src/components/chat/ToolCallBlock.tsx
mobile/src/components/chat/MarkdownContent.tsx
mobile/src/hooks/useThemeColor.ts
mobile/src/hooks/useProcessedMessages.ts
mobile/src/services/bridge.ts
mobile/src/services/api.ts
mobile/src/services/pendingInitialMessages.ts
mobile/src/services/websocket.ts
mobile/src/utils/groupingHelpers.ts
mobile/src/utils/jwt.ts
mobile/src/utils/uuid.ts
mobile/src/utils/timeline.ts
mobile/src/utils/messageAdapter.ts
mobile/src/utils/workspace.ts
mobile/src/constants/theme.ts
mobile/src/constants/agentModes.ts
mobile/src/i18n/index.ts
mobile/src/i18n/locales/ru-RU.json
mobile/src/i18n/locales/en-US.json
mobile/src/i18n/locales/zh-CN.json
mobile/src/i18n/locales/uk-UA.json
mobile/src/context/ConnectionContext.tsx
mobile/src/context/ConversationContext.tsx
mobile/src/context/WorkspaceContext.tsx
mobile/src/context/FilesTabContext.tsx
mobile/src/context/ChatContext.tsx
mobile/src/context/WebSocketContext.tsx
```

## 小白阅读建议
- 先看项目说明、`index` 入口、路由、业务服务、类型/结构定义等文件。英文文件名只是代码命名，不要求先理解英文语义。
- 暂时跳过构建产物、测试快照和重复样板。
- 如果这里是业务目录，优先找“谁调用它”和“它调用谁”。
