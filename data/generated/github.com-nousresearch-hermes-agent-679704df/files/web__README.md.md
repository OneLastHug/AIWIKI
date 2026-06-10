# 文件：web/README.md

## 一句话定位

`web/README.md` 是 Hermes Agent Web Dashboard 的前端开发入口说明和 UI 设计约束文档，用来告诉贡献者如何在本地启动、构建 `web/` React 应用，以及修改仪表盘样式时必须遵守哪些排版、对比度、字体和颜色规则。

## 它暴露/定义了什么

这个文件不暴露运行时代码，也不定义 TypeScript/Python API；它定义的是开发约定和维护边界。核心内容包括：前端技术栈为 Vite、React 19、TypeScript、Tailwind CSS v4 和手写的 shadcn/ui 风格组件；开发模式下需要先启动 Python FastAPI 后端，再启动 Vite dev server；生产模式下 `npm run build` 会把构建产物输出到 `hermes_cli/web_dist/`；`hermes dashboard` 服务的是构建后的静态 SPA，而不是 `web/src/` 的热更新版本。

它还定义了 `web/src/` 的高层目录职责：`components/ui/` 放通用 UI 原语，`lib/api.ts` 负责后端 API fetch 封装，`pages/` 放 Dashboard 页面，`App.tsx` 管主布局与导航，`main.tsx` 是 React 入口，`index.css` 放 Tailwind 和主题变量。

更重要的是，它把 Dashboard 的视觉规范写成了可执行的评审标准：正文最小字号不得低于 `text-xs`，文本透明度不得低于 0.7，品牌大写使用 `text-display` 而不是裸 `uppercase`，字体要按 Brand chrome、Themed body、Page chrome、Wordmark、Technical 分层使用，颜色优先使用语义 token。

## 谁调用它

运行时没有代码调用 `web/README.md`。根据当前片段推断，它的实际“调用者”是开发者、评审者和 AI 编码代理：当需要改 `web/src/`、调试 Dashboard、构建前端包或评审 UI 样式时，应先读取这个文件。依据是 README 明确写了开发命令、构建输出位置、目录结构和“Read before adding or editing UI styles”的样式规则。

间接相关的工程入口包括 `hermes_cli/main.py` 中的 `cmd_dashboard`，它在启动 `hermes dashboard` 时会构建或检查 `hermes_cli/web_dist/`；`hermes_cli/web_server.py` 则读取并服务该构建目录中的静态文件。

## 它调用谁

`web/README.md` 本身不调用任何模块。它描述的工作流会让开发者使用几个系统组件：前端侧通过 `web/package.json` 中的 `npm run dev`、`npm run build` 调用 Vite、TypeScript 和 Tailwind；开发服务器由 `web/vite.config.ts` 配置，把 `/api` 和 `/dashboard-plugins` 代理到 Python Dashboard 后端；生产构建输出到 `hermes_cli/web_dist/`，再由 `hermes_cli/web_server.py` 的静态文件服务逻辑加载。

在应用内部，README 提到的 `src/main.tsx` 会挂载 React 根节点，并包裹 `BrowserRouter`、`I18nProvider`、`ThemeProvider`、`SystemActionsProvider` 后渲染 `App`。`App.tsx` 再组织导航、路由、页面组件和插件页签。`src/lib/api.ts` 是前端访问 `/api/*` 的集中通道，负责附加 Dashboard session token、处理认证失效、构造 WebSocket 鉴权参数等。

## 核心流程

开发流程是两段式：先在仓库根目录启动 Dashboard 后端，使 FastAPI API、认证 token 注入、插件静态资源和 WebSocket/PTY 端点可用；再在 `web/` 下启动 Vite dev server，利用 HMR 快速调试前端。Vite 通过代理把 API 请求转发给后端，并在开发 HTML 中注入后端生成的 session token，避免受保护的 `/api/*` 请求返回 401。

构建流程是：执行 `npm run build`，先进行 TypeScript 构建检查，再由 Vite 生成静态资源，输出到 `hermes_cli/web_dist/`。随后 `hermes dashboard` 或 `python -m hermes_cli.main web` 这类后端入口会服务该目录。`pyproject.toml` 还把 `hermes_cli/web_dist/**/*` 纳入 Python 包数据，说明构建产物是 Dashboard 分发的一部分。

运行流程是：浏览器加载后端返回的 `index.html`，后端注入 `window.__HERMES_SESSION_TOKEN__`、`window.__HERMES_BASE_PATH__`、`window.__HERMES_AUTH_REQUIRED__` 等启动变量；`main.tsx` 初始化前端；`App.tsx` 根据内置页面和插件 manifest 生成导航与路由；各页面通过 `api.ts` 调用后端接口；如果启用内嵌 chat，`ChatPage` 还会通过 WebSocket/PTY 与后端桥接。

## 关键函数的高层作用

`web/README.md` 没有函数。与它描述内容直接相关的关键函数主要在邻近代码中。

`hermesDevToken` 位于 `web/vite.config.ts`，作用是在 Vite 开发模式下从运行中的 Dashboard 后端 HTML 中提取 session token 和嵌入 chat 标志，再注入开发页面，使本地热更新前端也能访问受保护 API。

`fetchJSON` 位于 `web/src/lib/api.ts`，是 Dashboard 前端的通用 JSON 请求封装。它负责拼接 base path、附加 `X-Hermes-Session-Token`、启用 cookie credentials，并统一处理 401：认证网关模式跳转登录，loopback token 过期时触发一次页面刷新。

`buildWsAuthParam` 和 `getWsTicket` 负责 WebSocket 鉴权差异：认证网关模式使用一次性 ticket，loopback 模式使用注入的 session token。它们支撑 `/api/pty` 和 `/api/ws` 这类浏览器无法自定义 Authorization header 的连接。

`cmd_dashboard` 位于 `hermes_cli/main.py`，是 `hermes dashboard` 的命令入口。它处理 `--status`、`--stop`，检查 fastapi/uvicorn，必要时构建 Web UI，发现插件，然后调用后端 `start_server`。

`serve_index`、`serve_css`、`serve_spa` 相关逻辑位于 `hermes_cli/web_server.py`。它们负责返回 SPA HTML、注入启动脚本、在反向代理 prefix 下重写资源路径，并把 `hermes_cli/web_dist/assets` 挂成静态资源。

## 修改风险

第一类风险是开发/生产路径混淆。README 明确指出 Vite dev server 和 `hermes dashboard` 服务的不是同一份前端：前者读 `web/src/` 并热更新，后者读 `hermes_cli/web_dist/`。如果改了 README 的启动说明或构建路径，可能导致开发者以为源码修改会立即出现在 Dashboard 端口，实际却需要重新 `npm run build` 并重启服务。

第二类风险是认证说明过期。当前 Vite 配置已经有 session token 注入、base path、认证网关和 WebSocket ticket 逻辑；如果 README 简化成“只代理 `/api`”而不提后端必须运行，开发者会遇到大量 401 或 WebSocket 连接失败。反过来，如果后端认证变量变化，README 也需要同步更新。

第三类风险是 UI 规范被削弱。Typography 与 contrast rules 是 Dashboard 视觉一致性和可访问性的硬约束。放宽最小字号、透明度、语义颜色 token 或字体分层，会让不同主题下出现低对比度、不可读文本、品牌字形滥用、页面局部风格漂移等问题。

第四类风险是目录结构描述滞后。实际 `web/src/pages/` 已包含 `AnalyticsPage`、`ModelsPage`、`ProfilesPage`、`SkillsPage`、`PluginsPage`、`ChatPage` 等，README 的结构示例只列了部分旧页面。修改时应避免把示例当作完整清单；更适合写成“代表性目录职责”，否则新贡献者会低估 Dashboard 的页面范围。

第五类风险是外部依赖和设计系统边界。README 提到使用手写 shadcn/ui 风格组件，但当前 `package.json` 也依赖 `@nous-research/ui`，实际代码大量使用该设计系统组件。若 README 不同步说明，会导致新 UI 在本地组件、设计系统组件和 Tailwind token 之间选型混乱。
