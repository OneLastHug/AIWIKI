# 目录：mobile

## 它负责什么

`mobile` 是这个仓库的移动端应用目录，整体看起来是一个基于 `Expo` + `expo-router` 的 React Native 客户端。它承担的核心职责有三层：第一是设备端的连接入口和鉴权恢复，第二是连接后围绕聊天、文件、设置的主界面，第三是把 API、WebSocket、工作区、会话等状态集中到 `src/context` 和 `src/services` 里统一管理。

根据当前片段推断，这个目录基本就是“手机端前台应用本体”，而不是一个纯组件库或纯测试目录。`package.json` 里的 `main: "expo-router/entry"`、`start/android/ios/web/build` 等脚本也说明这里是独立运行和打包的应用单元。

## 直接子目录地图

`mobile` 下面的直接子目录主要可以分成几类：

- `app`：路由层和页面入口，`expo-router` 的实际页面组织都在这里。
- `src`：业务实现层，包含 `components`、`context`、`hooks`、`services`、`utils`、`i18n`、`constants` 等。
- `__tests__`：移动端自己的测试目录，按 `services`、`utils` 等方向拆分。
- `assets`：静态资源，当前能看到 `images` 子目录。
- `scripts`：构建脚本入口，核心是 `scripts/build.js`。
- `versions`：版本数据或发行信息，`versions/version.json` 看起来是这里的主数据文件。

如果只看职责边界，`app` 负责“路由怎么走”，`src` 负责“页面背后怎么工作”，`__tests__` 负责“这些工作是否被验证”。

## 关键入口

最重要的入口是 `package.json`，因为它直接定义了这个目录如何启动、测试和构建。`main` 指向 `expo-router/entry`，说明路由入口不是传统 `App.tsx`，而是由 `expo-router` 接管。

路由级关键入口有这些：

- `app/_layout.tsx`：全局根布局，包了一层 `ConnectionProvider`、`WebSocketProvider`、`ConversationProvider`、`WorkspaceProvider`、`FilesTabProvider`，并且在这里初始化 `i18n`、处理 splash screen。
- `app/index.tsx`：首屏分流点，负责根据连接配置和恢复状态跳转到 `connect` 或 `/(tabs)/chat`。
- `app/connect.tsx`：连接建立页，支持扫码和手动粘贴二维码登录链接，是首次接入和重新接入的关键入口。
- `app/(tabs)/_layout.tsx`：连接成功后的主框架，负责底部标签页和连接状态横幅。

从流程上说，`mobile` 的“真正首页”不是视觉首页，而是 `index.tsx` 里的条件跳转。

## 主流程位置

主流程基本可以概括成“连接建立 -> 状态恢复 -> 进入标签页 -> 在聊天或文件工作区内继续操作”。

连接链路的核心位置在 `src/context/ConnectionContext.tsx` 和 `src/context/WebSocketContext.tsx`。前者负责从 `expo-secure-store` 恢复保存的连接配置、配置 API、连接 WebSocket，并处理 token 刷新和重连；后者负责应用回到前台时的重连逻辑。`app/connect.tsx` 则是这个链路的前端入口，它通过扫码或粘贴 URL 解析出 `host`、`port`、`qrToken`，再调用后端 `/api/auth/qr-login`，拿到 JWT 后交给 `connect()`。

进入主界面后，聊天和文件是两条最重要的用户路径：

- 聊天主线在 `app/(tabs)/chat/index.tsx`，它根据 `ConversationContext` 里的 `activeConversationId` 和 `pendingAgent` 决定显示空态、等待态，还是挂载 `ChatProvider` 与 `ChatScreen`。
- 文件主线在 `app/(tabs)/files/index.tsx`，它依赖 `FilesTabContext` 和 `WorkspaceContext`，根据当前工作区和打开的文件标签决定显示空态或 `FileContentView`。

再往下看，`src/services/api.ts`、`src/services/websocket.ts`、`src/services/bridge.ts`、`src/services/pendingInitialMessages.ts` 这些文件是状态和通信的底座；`src/components/chat`、`src/components/files`、`src/components/ui` 则是页面表现层。根据当前片段推断，`ConversationContext`、`WorkspaceContext`、`ChatContext` 是把这些底座组织成可用业务状态的核心中间层。

## 推荐阅读顺序

建议按这个顺序看：

1. `package.json`：先确认这个目录怎么启动、测试、构建。
2. `app/_layout.tsx`：看全局 provider 和路由壳子。
3. `app/index.tsx`：看首屏如何分流。
4. `app/connect.tsx`：看连接建立和鉴权恢复。
5. `src/context/ConnectionContext.tsx`、`src/context/WebSocketContext.tsx`：看连接态和重连机制。
6. `app/(tabs)/_layout.tsx`：看进入主界面后的标签页结构。
7. `app/(tabs)/chat/index.tsx`、`app/(tabs)/files/index.tsx`：看两条主业务线如何落到具体页面。
8. 再补 `src/services`、`src/context`、`src/components` 的对应实现。

## 常见误区

一个常见误区是把 `mobile` 当成“只有页面”的目录。实际上这里的主逻辑更多藏在 `src/context` 和 `src/services`，页面只是状态机的外壳。

第二个误区是忽略 `app/index.tsx`。很多人会先找“首页 UI”，但这里首页实际上是一个路由分发器，真正的用户入口会被重定向到 `connect` 或 `/(tabs)/chat`。

第三个误区是把连接恢复当成一次性动作。`ConnectionContext` 里不仅有启动恢复，还包含 token 刷新、心跳检查、前台回切重连，这意味着连接状态是贯穿整个应用生命周期的。

第四个误区是只看 `chat` 页面不看 `files` 页面。这个移动端不是单一聊天应用，文件工作区也是核心主线之一，尤其 `WorkspaceContext` 和 `FilesTabContext` 会影响文件页的实际行为。
