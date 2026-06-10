# 文件：web/src/pages/ChatPage.tsx

## 一句话定位

`web/src/pages/ChatPage.tsx` 是 Dashboard 的 `/chat` 页面主体，它不重新实现聊天 UI，而是把真实的 `hermes --tui` 嵌入到浏览器中的 xterm.js 终端里，并在旁边挂接结构化侧栏用于模型切换和工具调用状态展示。

## 它暴露/定义了什么

该文件默认导出 React 组件 `ChatPage({ isActive = true })`。`isActive` 用来支持 Dashboard 将聊天页“持久挂载”：页面切到别的 tab 时组件仍存在，PTY 会话不被销毁，但视觉上隐藏，并暂停一些 header、focus、移动端面板副作用。

文件内还定义了几个关键辅助：

`buildWsUrl` 负责生成连接 `/api/pty` 的 WebSocket 地址，带上认证参数、`resume` 会话参数和 `channel`。

`generateChannelId` 为当前聊天页实例生成事件通道 ID，用来把 PTY 子进程发布的事件和 `ChatSidebar` 订阅的事件对应起来。

`terminalTierWidthPx`、`terminalFontSizeForWidth`、`terminalLineHeightForWidth` 负责根据真实容器宽度调整 xterm 字体和行高，重点处理移动端和 DevTools 设备模式下 `window.innerWidth` 不可靠的问题。

`TERMINAL_THEME` 定义嵌入终端的外观基调。

## 谁调用它

主要调用方是 `web/src/App.tsx`。`App.tsx` 根据当前路径判断 `isChatRoute`，在启用 embedded chat 且没有插件覆盖 `/chat` 时渲染 `<ChatPage isActive={isChatRoute} />`。这里的设计重点是：`/chat` 路由本身仍由 React Router 管理，但真正的 `ChatPage` 被放在路由区域外的持久容器中，非聊天路由时用 `hidden` 隐藏，而不是卸载。

`web/src/pages/SessionsPage.tsx` 不直接调用 `ChatPage`，但会导航到 `/chat?resume=<session_id>`，触发 `ChatPage` 根据查询参数恢复会话。

此外，插件系统可以通过 manifest 的 `tab.override: "/chat"` 覆盖内置 chat 页面；这种情况下 `App.tsx` 会抑制内置 `ChatPage` 挂载，避免同时启动两个聊天界面。

## 它调用谁

最核心的依赖是 xterm 生态：`Terminal` 提供终端模拟器，`FitAddon` 负责按容器计算行列，`Unicode11Addon` 处理宽字符宽度，`WebLinksAddon` 支持终端内链接识别，`WebglAddon` 在宽屏下启用 WebGL 渲染。

后端交互上，它通过 `buildWsAuthParam` 获取 WebSocket 认证参数。普通 loopback 模式使用 `window.__HERMES_SESSION_TOKEN__` 作为 `token`；gated/OAuth 模式通过 `/api/auth/ws-ticket` 换取一次性 `ticket`。随后连接 `/api/pty`，把浏览器终端输入转发到后端 PTY，把后端字节流写入 xterm。

它还调用 `api.getSessionLatestDescendant`，用于处理 `/chat?resume=<id>`：如果目标会话已有更新的 descendant，会把 URL 替换到最新会话。

UI 侧调用 `ChatSidebar` 展示模型与工具状态，调用 `PluginSlot` 暴露 `chat:top`、`chat:bottom` 插件插槽，调用 `usePageHeader` 在移动端 header 右侧放置“模型/工具”按钮。

## 核心流程

组件挂载后，先读取 `resume` 查询参数，并基于它生成新的 `channel`。`resume` 变化会被视为 PTY 身份变化，因此终端和 WebSocket 会重建；普通页面切换不会重建。

主 effect 在拿到 `hostRef` 后创建 xterm `Terminal`，配置字体、主题、滚动缓冲、选择行为、剪贴板行为和滚轮滚动。随后加载 `FitAddon`、Unicode、链接识别和可选 WebGL 渲染器，并把终端打开到 DOM 容器中。

接着组件建立尺寸同步机制：`ResizeObserver`、`window.resize`、`visualViewport.resize` 和双 `requestAnimationFrame` 都会触发 `fit.fit()`，并通过特殊控制串 `\x1b[RESIZE:cols;rows]` 把终端行列通知后端 PTY。这个流程是关键，因为 Ink/TUI 需要准确的终端尺寸才能布局。

WebSocket 打开后，前端把初始尺寸发给后端；收到后端消息时直接 `term.write`；用户输入通过 `term.onData` 发回 WebSocket。代码中特意过滤 SGR mouse report，避免鼠标控制序列被误当作用户输入进入 TUI。

渲染层面，桌面端是终端主面板加右侧 `ChatSidebar`；移动端侧栏通过 `createPortal` 挂到 `document.body`，作为右侧抽屉显示，并用 `usePageHeader` 在 header 中提供打开按钮。

## 关键函数的高层作用

`ChatPage` 是总控组件，负责终端生命周期、PTY WebSocket 生命周期、尺寸同步、剪贴板桥接、移动端侧栏、恢复会话和插件插槽。

`handleCopyLast` 不直接读终端内容，而是向 TUI 输入 `/copy` 加回车，依赖 Ink 内部命令输出 OSC 52，再由本文件注册的 OSC 52 handler 写入浏览器剪贴板。

`buildWsUrl` 只拼接连接参数，但它承载了关键协议约定：`channel` 用于事件广播关联，`resume` 用于恢复会话，认证参数在 token/ticket 两种模式间切换。

`terminalTierWidthPx` 一类函数是响应式终端的保护层，避免移动端选择到桌面字体尺寸，也避免 `display:none` 或设备模拟导致测量错误。

激活状态 effect 负责在 `isActive` 从 false 变回 true 时重新 fit 终端并有条件恢复焦点，解决持久挂载下隐藏容器不会触发 `ResizeObserver` 的问题。

## 修改风险

最高风险是 PTY 生命周期。`ChatPage` 被设计为持久挂载，随意把它放回普通路由卸载流程，或让 `resume`、`channel` 的依赖关系变化，都会导致聊天会话意外重启、侧栏事件串线或工具状态丢失。

第二类风险是终端尺寸同步。`fit.fit()`、双 rAF、`ResizeObserver`、`RESIZE` 控制串看起来繁琐，但它们共同保证浏览器 xterm、后端 PTY 和 Ink 布局一致。删掉其中一环可能只在移动端、隐藏后恢复、字体加载后或窗口动画期间暴露问题。

第三类风险是认证路径。`buildWsAuthParam` 同时支持 loopback token 和 gated ticket；如果只测试本地 token 模式，容易破坏 OAuth/gated 部署下的 WebSocket 连接。

第四类风险是剪贴板和键盘处理。OSC 52、Ctrl/Cmd 组合键、浏览器 Clipboard API、TUI 内部复制命令互相配合。改动时要确认选择复制、复制最后回复、粘贴、Ctrl+C 中断这几条路径没有互相覆盖。

第五类风险是不要在这里重写聊天体验。根据当前片段和仓库说明推断，Dashboard 的主聊天 transcript、composer、slash command 行为属于嵌入的 `hermes --tui`，React 侧只负责承载终端和提供辅助面板。若要改主聊天交互，应优先改 Ink/TUI，而不是在 `ChatPage.tsx` 另做一套 React 聊天 UI。
