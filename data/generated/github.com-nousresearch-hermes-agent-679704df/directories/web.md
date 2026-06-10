# 目录：web

## 它负责什么

`web` 是 Hermes Agent 的浏览器 Dashboard 前端工程。它不是 Python 后端，也不是核心 agent loop，而是一个独立的 Vite + React + TypeScript 单页应用，用来展示和管理 Hermes 的会话、配置、模型、日志、计划任务、技能、插件、Profile、API key 等运维型界面。

从 `web/README.md` 和 `web/package.json` 看，它的开发方式是前后端分离：开发时运行 Vite dev server，`/api` 请求代理到 Hermes 的 FastAPI dashboard 后端；构建时执行 `npm run build`，产物输出到 `../hermes_cli/web_dist/`，再由 Python 侧静态托管。也就是说，`web/src` 的修改不会直接影响 `hermes dashboard` 已经托管的构建产物，必须重新 build。

这个目录还承载一个重要设计约束：Dashboard 的 `/chat` 页面嵌入真实的 `hermes --tui` PTY 终端，而不是在 React 里重写聊天 transcript 和 composer。根据仓库说明，React 可以做侧栏、状态、选择器、面板等辅助 UI，但主聊天体验属于 Ink TUI，经由 `hermes_cli/pty_bridge.py` 和 `hermes_cli/web_server.py` 的 WebSocket/PTY 桥接进入浏览器。

## 直接子目录地图

`web/public` 放静态资源，当前主要包含 `favicon.ico`、`fonts`、`fonts-terminal`。这些资源由 Vite 直接服务或打包引用，适合放不需要经过 TypeScript import pipeline 的公共文件。

`web/src` 是前端源码主体。它下面按角色分层：`components` 放跨页面复用组件，例如认证、侧栏状态、主题/语言切换、模型选择、工具调用展示、Markdown 渲染等；`pages` 放一级路由页面；`lib` 放 API client、格式化、嵌入开关、slash 执行和工具函数；`contexts` 放页面标题和系统动作等 React Context；`hooks` 放局部复用 hook；`i18n` 放多语言翻译表和 provider；`themes` 放主题 preset 与主题上下文；`plugins` 放 Dashboard 插件系统的前端注册、slot、类型和插件页面承载逻辑。

根目录文件是工程壳：`index.html` 是 Vite HTML 入口，`package.json` 定义脚本和依赖，`vite.config.ts` 是构建与代理配置，`tsconfig*.json` 是 TypeScript 配置，`eslint.config.js` 是 lint 配置，`README.md` 说明开发和构建方式。

## 关键入口

前端启动入口是 `web/src/main.tsx`。它创建 React root，挂载 `BrowserRouter`，并依次包裹 `I18nProvider`、`ThemeProvider`、`SystemActionsProvider`，最后渲染 `App`。这里还会先调用 `exposePluginSDK()`，把前端插件 SDK 暴露给通过 `<script>` 加载的 dashboard 插件。

应用主壳是 `web/src/App.tsx`。它负责路由表、侧边栏导航、插件导航合并、页面布局、移动端侧栏、全局 header/action，以及 `/chat` 的特殊持久化宿主。内置路由核心包括 `/sessions`、`/analytics`、`/models`、`/logs`、`/cron`、`/skills`、`/plugins`、`/profiles`、`/config`、`/env`、`/docs`，根路径重定向到 `/sessions`。`/chat` 不是普通卸载式页面：代码注释说明嵌入聊天开启时，`ChatPage` 会在 `Routes` 外保持持久挂载，只通过显示隐藏切换，以保证 PTY child、WebSocket 和 xterm 实例在切换 tab 时不被销毁。

页面入口集中在 `web/src/pages`。例如 `SessionsPage.tsx` 对应会话管理，`ConfigPage.tsx` 对应动态配置编辑，`EnvPage.tsx` 对应密钥管理，`LogsPage.tsx` 对应日志查看，`ModelsPage.tsx` 对应模型信息，`PluginsPage.tsx` 与 `web/src/plugins` 协作展示插件能力。

后端通信入口主要在 `web/src/lib/api.ts`，根据当前片段推断，它封装 dashboard 后端 `/api` 的 typed fetch 调用；依据是 README 明确说 Vite 代理 `/api`，而 `App.tsx` 也从 `@/lib/api` 导入 `api`、`StatusResponse`、`HERMES_BASE_PATH`。

## 主流程位置

普通页面访问流程是：浏览器加载 `web/index.html`，Vite 进入 `web/src/main.tsx`，创建全局 provider，进入 `web/src/App.tsx`，根据 `react-router-dom` 当前路径选择 `web/src/pages/*Page.tsx`。页面再通过 `web/src/lib/api.ts` 请求 Python dashboard 后端，通过 `web/src/components` 组合展示 UI。

导航生成流程位于 `App.tsx`。内置导航先由 `BUILTIN_NAV_REST` 和可选 `CHAT_NAV_ITEM` 定义；插件 manifest 会通过 `buildNavItems`、`partitionSidebarNav` 合并进侧边栏。插件可以隐藏 tab、覆盖 tab，或声明 `before:`、`after:` 位置提示。插件页面路由则通过 `buildRoutes` 与 `PluginPage`、`PluginSlot`、`usePlugins` 协同生成。

嵌入聊天流程的关键位置是 `web/src/pages/ChatPage.tsx`、`web/src/lib/gatewayClient.ts`、`web/src/lib/dashboard-flags.ts`、`web/src/lib/slashExec.ts`，以及 Python 邻近上下文中的 `hermes_cli/pty_bridge.py`、`hermes_cli/web_server.py`。根据当前片段和仓库说明推断，React 页面侧负责 xterm 容器、WebSocket 连接、尺寸适配、辅助侧栏，真正的终端会话生命周期由 Python PTY 桥接和 `hermes --tui` 子进程负责。

主题和国际化流程分别从 `main.tsx` 的 `ThemeProvider`、`I18nProvider` 开始。翻译文本分散在 `web/src/i18n/*.ts`，主题 preset 和类型在 `web/src/themes`。组件样式依赖 Tailwind CSS v4、`@nous-research/ui`、`lucide-react` 等依赖，基础 CSS 在 `web/src/index.css`。

## 推荐阅读顺序

1. 先读 `web/README.md`，理解开发、构建、Vite 代理、构建产物托管位置，以及字体、颜色、大小写等 Dashboard UI 约束。
2. 再读 `web/package.json` 和 `web/vite.config.ts`，确认脚本、依赖、路径 alias、构建输出和 `/api` 代理。
3. 读 `web/src/main.tsx`，把 provider、router、plugin SDK 暴露顺序看清楚。
4. 读 `web/src/App.tsx`，重点看内置路由、导航合并、插件路由、`/chat` 持久化宿主。
5. 按功能选读 `web/src/pages`，例如要理解配置编辑就看 `ConfigPage.tsx`，要理解会话列表就看 `SessionsPage.tsx`，要理解终端嵌入就看 `ChatPage.tsx`。
6. 最后读 `web/src/lib/api.ts`、`web/src/plugins`、`web/src/themes`、`web/src/i18n`，补齐数据来源、扩展机制、主题和文案体系。

## 常见误区

不要把 `web` 当成完整后端。它只负责浏览器 UI，数据和执行能力来自 Hermes Python 侧的 dashboard API、PTY bridge、TUI gateway 等模块。

不要在 React 里重写主聊天体验。仓库说明明确要求 dashboard 的 `/chat` 嵌入真实 `hermes --tui`，主 transcript、composer、slash-command 行为应该扩展 Ink TUI，而不是另做一套 React chat。

不要以为运行 `hermes dashboard` 会实时读取 `web/src`。README 说明 dashboard 服务的是 `hermes_cli/web_dist/` 构建产物；开发时应使用 Vite dev server，发布或本地 dashboard 验证前再 `npm run build`。

不要过度相信 README 中的旧结构示例。当前实际文件显示没有 `src/components/ui/` 目录，大量 UI primitive 来自 `@nous-research/ui`，所以判断结构时应以当前 filesystem 和 import 为准。

不要把插件系统理解为后端插件页面的硬编码列表。`web/src/plugins` 和 `App.tsx` 的 manifest 合并逻辑说明前端 dashboard 支持插件 tab、slot 和覆盖行为，导航和路由会随 manifest 动态扩展。
