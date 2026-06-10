# 目录：web/src

## 它负责什么

`web/src` 是 Hermes dashboard 的前端源码目录，整体是一个基于 React、React Router、Vite 风格入口组织的单页应用。它不实现核心 Agent 对话逻辑，也不直接运行模型调用；它负责把 Python 后端暴露的 dashboard API、TUI/PTY WebSocket、配置管理、日志、会话、模型、插件、主题和多语言界面组织成浏览器里的管理台。

从当前片段看，`web/src` 的定位更像“dashboard 外壳 + 管理页面集合 + 插件宿主”。其中 `App.tsx` 负责应用级布局、侧边栏、路由、插件 tab 合并、移动端导航和持久化嵌入聊天页；`main.tsx` 负责把 React 根组件挂载到 DOM，并包上 `BrowserRouter`、`I18nProvider`、`ThemeProvider`、`SystemActionsProvider` 等全局 Provider；`lib/api.ts` 负责统一封装 `/api/...` 请求、session token、OAuth gate、WebSocket ticket 等与后端的通信细节。

这个目录还包含一个特殊重点：`pages/ChatPage.tsx` 并不是重新写一个 Web 聊天 UI，而是把真实的 `hermes --tui` 通过 xterm.js 嵌入 dashboard。根据代码注释和实现，浏览器端通过 `/api/pty` WebSocket 连接后端 PTY，后端再启动 TUI 进程，键盘输入、终端 resize、输出字节都通过这个链路转发。因此 `web/src` 的 chat 页面只是终端容器和浏览器集成层，不是对话引擎本身。

## 直接子目录地图

`components` 存放跨页面复用的 UI 组件。它覆盖认证、侧边栏状态、模型选择、Markdown 渲染、工具调用展示、OAuth provider 卡片、平台卡片、语言和主题切换等界面单元。这里的组件通常被 `App.tsx` 或各个 `pages/*Page.tsx` 组合使用，不承担顶层路由职责。

`contexts` 存放 React Context 相关代码。目前能看到 `PageHeaderProvider`、`SystemActions` 以及对应 hook。它们用于在不同页面和应用外壳之间传递页面头部扩展区、系统动作等横切状态，避免每个页面直接操纵顶层布局。

`hooks` 存放较小的自定义 hook，例如 `useModalBehavior`、`useSidebarStatus`。它们封装页面组件中会重复出现的浏览器行为或状态获取逻辑。

`i18n` 是多语言资源与国际化上下文。目录下有 `en.ts`、`zh.ts`、`ja.ts`、`ko.ts`、`fr.ts` 等多个语言文件，`context.tsx` 提供 `I18nProvider` 和 `useI18n`，`types.ts` 定义翻译结构。`App.tsx` 通过 `useI18n()` 读取侧边栏、按钮、页面文案等显示文本。

`lib` 是前端通用工具层。`api.ts` 是最关键文件，封装后端 API、认证 token 注入、401 处理、WebSocket 鉴权参数构造等；`dashboard-flags.ts` 控制 dashboard 功能开关；`format.ts`、`utils.ts`、`nested.ts` 等负责格式化、样式 class 合并、嵌套数据处理等辅助能力；`gatewayClient.ts` 和 `slashExec.ts` 根据命名推断与网关状态或 slash 命令执行有关，具体细节需要继续读对应文件确认。

`pages` 是 dashboard 的页面层。每个 `*Page.tsx` 基本对应一个路由页面，例如 `SessionsPage.tsx`、`AnalyticsPage.tsx`、`ModelsPage.tsx`、`LogsPage.tsx`、`CronPage.tsx`、`SkillsPage.tsx`、`PluginsPage.tsx`、`ProfilesPage.tsx`、`ConfigPage.tsx`、`EnvPage.tsx`、`DocsPage.tsx`、`ChatPage.tsx`。这些页面通常通过 `lib/api.ts` 读取后端数据，再用 `components` 中的通用组件渲染。

`plugins` 是 dashboard 前端插件系统。`registry.ts` 会把插件 SDK 暴露到 `window.__HERMES_PLUGIN_SDK__` 和 `window.__HERMES_PLUGINS__`，插件脚本可调用 `register(name, Component)` 注册自己的页面组件，也可注册 slot 内容。`PluginPage.tsx` 负责渲染插件页面，`slots.ts` 管理插件插槽，`usePlugins.ts` 根据当前片段推断负责从后端加载插件 manifest 并驱动 `App.tsx` 合并导航和路由。

`themes` 是 dashboard 主题系统。`context.tsx` 中可以看到主题会转成 CSS variables，包括 palette、typography、layout、assets、component styles 等；`presets.ts` 提供内置主题；`types.ts` 定义主题结构。`main.tsx` 用 `ThemeProvider` 包住整个应用，`App.tsx` 根据 `theme.layoutVariant` 设置布局变体。

## 关键入口

`main.tsx` 是浏览器入口。它先调用 `exposePluginSDK()`，确保外部插件脚本在 React 应用渲染前就能访问 Hermes 暴露的 SDK；随后用 `createRoot(document.getElementById("root")!)` 挂载应用。Provider 包装顺序是 `BrowserRouter`、`I18nProvider`、`ThemeProvider`、`SystemActionsProvider`、`App`。其中 `BrowserRouter` 的 `basename` 来自 `HERMES_BASE_PATH`，说明 dashboard 支持被部署到反向代理的子路径下。

`App.tsx` 是应用壳入口。它定义内置路由表 `BUILTIN_ROUTES_CORE`，默认把 `/` 重定向到 `/sessions`，并注册 sessions、analytics、models、logs、cron、skills、plugins、profiles、config、env、docs 等页面。`/chat` 有特殊处理：当 embedded chat 功能开启时，导航里加入 chat 项，但真正的 `ChatPage` 会以持久宿主形式渲染在 `Routes` 外部，路由里只用 `ChatRouteSink` 占位，避免切换页面时销毁 PTY、WebSocket 和 xterm 实例。

`lib/api.ts` 是前后端通信入口。所有常规 API 请求走 `fetchJSON()`，它会拼上 `HERMES_BASE_PATH`，注入 `X-Hermes-Session-Token`，并在 gated OAuth 模式下使用 cookie。它还集中处理 401：OAuth gate 下跳转登录，loopback 模式下尝试刷新页面以获取新的注入 token。WebSocket 鉴权由 `buildWsAuthParam()` 完成：普通本地模式使用 `token`，OAuth gate 模式先请求 `/api/auth/ws-ticket` 获取一次性 `ticket`。

`pages/ChatPage.tsx` 是嵌入式 TUI 的前端入口。它初始化 xterm.js `Terminal`，加载 `FitAddon`、`Unicode11Addon`、`WebLinksAddon`，宽屏时尝试启用 `WebglAddon`；同时处理复制粘贴、OSC 52、终端滚动、窗口 resize、移动端侧栏和 `/chat?resume=<id>` 会话恢复参数。

## 主流程位置

应用启动主流程在 `main.tsx` 到 `App.tsx`。浏览器加载 `index.html` 后，`main.tsx` 挂载 React；`App.tsx` 读取插件 manifest、主题、i18n 文案、dashboard 配置，并组合侧边栏导航和路由。路由页面通过 `Routes` 渲染，未知路由在插件加载完成后回退到 `/sessions`。

普通管理页面的数据流大致是：页面组件调用 `api.*` 方法，`lib/api.ts` 统一发起请求，后端返回 JSON，页面用本地 state 和共享组件渲染。例如 sessions、logs、models、config、env、skills 等页面的具体字段和交互应分别到 `pages/*Page.tsx` 查看。

插件加载主流程在 `main.tsx`、`plugins/registry.ts`、`App.tsx` 之间。`main.tsx` 先暴露 SDK；插件脚本随后可向全局 registry 注册组件或 slot；`usePlugins()` 提供 manifest 给 `App.tsx`；`App.tsx` 的 `buildNavItems()`、`partitionSidebarNav()`、`buildRoutes()` 会把插件 tab 插入导航、允许插件覆盖内置页面，或注册隐藏路由。插件页面最终由 `PluginPage` 渲染。

聊天主流程在 `App.tsx` 和 `pages/ChatPage.tsx`。`App.tsx` 判断当前路径是否 `/chat`，并在 embedded chat 开启且未被插件覆盖时持久挂载 `ChatPage`。`ChatPage` 创建终端实例，调用 `buildWsAuthParam()` 构造鉴权参数，再连接 `${HERMES_BASE_PATH}/api/pty`。用户输入通过 xterm `onData` 发往 WebSocket，后端 PTY 输出通过 `onmessage` 写回终端。resize 会发送形如 `\x1b[RESIZE:cols;rows]` 的控制消息，让后端 TUI 同步布局。

主题主流程在 `themes/context.tsx`。主题对象被转换为 CSS variables，写到 document root 或相关样式节点中；字体 URL、主题资产、组件级样式和 custom CSS 也在这里处理。页面和组件主要消费 CSS 变量，而不是在每个组件里硬编码完整视觉风格。

## 推荐阅读顺序

1. 先读 `main.tsx`，理解全局 Provider、`BrowserRouter` basename 和插件 SDK 暴露时机。
2. 再读 `App.tsx`，重点看 `BUILTIN_ROUTES_CORE`、`BUILTIN_NAV_REST`、`buildRoutes()`、`buildNavItems()`、持久化 `ChatPage` 的注释和渲染逻辑。
3. 读 `lib/api.ts`，掌握 dashboard 与后端 API、session token、OAuth gate、WebSocket ticket 的边界。
4. 读 `pages/SessionsPage.tsx`、`pages/ConfigPage.tsx`、`pages/ModelsPage.tsx`、`pages/LogsPage.tsx` 中任意两三个，建立普通页面的数据请求和状态管理模式。
5. 专门读 `pages/ChatPage.tsx`，把它当作“xterm + WebSocket + PTY 桥接层”来理解，不要按普通表单页面阅读。
6. 最后读 `plugins/registry.ts`、`plugins/slots.ts`、`plugins/usePlugins.ts` 和 `themes/context.tsx`，理解扩展点和换肤机制。

## 常见误区

第一个误区是把 `pages/ChatPage.tsx` 当作 Hermes 聊天逻辑本体。它实际上只是浏览器终端宿主，真实聊天界面来自 `hermes --tui`，后端通过 PTY 和 WebSocket 把 TUI 嵌进页面。要改 transcript、composer、slash command 等核心交互，通常应去 TUI/后端相关目录，而不是在这里重写一套 React chat。

第二个误区是认为路由只由 `BUILTIN_ROUTES_CORE` 决定。`App.tsx` 会合并插件 manifest，插件可以新增 tab、隐藏 tab、指定插入位置，甚至通过 `tab.override` 覆盖内置路径。因此排查某个页面来源时，要同时看内置 routes 和插件 routes。

第三个误区是直接写死 `/api/...` 或根路径资源。`lib/api.ts` 明确支持 `HERMES_BASE_PATH`，用于 dashboard 被反向代理到子路径的场景。新增请求或 WebSocket 地址时应复用这里的封装，否则在非根路径部署下容易失效。

第四个误区是忽略认证模式差异。loopback 模式依赖注入的 `window.__HERMES_SESSION_TOKEN__`，OAuth gate 模式下 WebSocket 使用一次性 ticket。`ChatPage` 中“没有 token 不一定是错误”的逻辑就是为 gated 模式准备的。

第五个误区是把主题当成普通 CSS 文件。当前主题系统会动态注入 CSS variables、字体、assets、component styles 和 custom CSS；组件样式很多依赖这些变量。改视觉表现时应先理解 `themes/context.tsx` 和 `themes/presets.ts`，避免在页面局部写死颜色后破坏主题切换。

第六个误区是把 `components` 下的组件都看成页面入口。这个目录主要是复用 UI 单元，真正决定页面装配和业务流的位置通常在 `pages`、`App.tsx` 和 `lib/api.ts`。
