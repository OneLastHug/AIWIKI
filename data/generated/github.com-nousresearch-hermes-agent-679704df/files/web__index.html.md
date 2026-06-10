# 文件：web/index.html

## 一句话定位

`web/index.html` 是 Hermes Dashboard 前端 SPA 的 HTML 壳文件：它不承载业务逻辑，只负责定义浏览器文档的最小结构、挂载 React 根节点，并把执行权交给 Vite 入口 `web/src/main.tsx`。

## 它暴露/定义了什么

这个文件定义了 Dashboard 页面最外层的 HTML 文档骨架，主要包括四类内容。

第一是基础文档信息：`<!doctype html>`、`<html lang="en">`、`<meta charset="UTF-8" />`，保证浏览器以标准模式和 UTF-8 编码解析页面。`lang="en"` 只说明默认文档语言，不代表应用没有国际化；实际 UI 语言由 `web/src/i18n` 体系处理。

第二是移动端视口设置：`viewport` 同时设置 `width=device-width`、`initial-scale=1.0` 和 `viewport-fit=cover`。这使 Dashboard 能适配移动宽度，也允许内容使用安全区域之外的完整视口空间，和后续 React/CSS 布局相关。

第三是页面标识：`<title>Hermes Agent - Dashboard</title>` 和 favicon 引用 `/favicon.ico`。注意源码里 favicon 写成 `type="image/svg+xml"`，但路径是 `.ico`，这是一个轻微不一致点；通常不影响多数浏览器加载，但如果严格处理 MIME 或图标类型，可能需要核对。

第四是 SPA 挂载点和模块入口：`<div id="root"></div>` 是 React 渲染根节点，`<script type="module" src="/src/main.tsx"></script>` 是开发态下 Vite 识别的 TypeScript/React 入口。生产构建后，Vite 会把这个入口改写为构建产物中的 JS/CSS asset 引用。

## 谁调用它

开发环境中，`web/index.html` 由 Vite dev server 直接读取并作为页面入口。`web/package.json` 的 `dev` 脚本执行 `vite`，`build` 脚本执行 `tsc -b && vite build`，所以该文件既是本地开发入口，也是生产构建模板。

生产环境中，根据当前片段推断，`hermes dashboard` 启动的 Python Web 服务不会直接服务 `web/index.html`，而是服务 Vite 构建后的 `hermes_cli/web_dist/index.html`。依据是 `web/vite.config.ts` 中 `build.outDir` 指向 `../hermes_cli/web_dist`，并且 `hermes_cli/web_server.py` 的 `mount_spa()` 从 `WEB_DIST / "index.html"` 读取构建后的 HTML。

此外，`hermes_cli/main.py` 中 Dashboard 命令会检查 `hermes_cli/web_dist/index.html` 是否存在，并在需要时提示或触发前端构建。因此调用链可以理解为：开发态是 Vite 调用 `web/index.html`，构建态是 Vite 以它为模板生成 dist HTML，运行态是 Python Dashboard 服务读取 dist HTML 并返回给浏览器。

## 它调用谁

严格说，HTML 文件本身没有函数调用，但它通过 `<script type="module" src="/src/main.tsx">` 把控制权交给 `web/src/main.tsx`。

`web/src/main.tsx` 继续调用 `createRoot(document.getElementById("root")!).render(...)`，把 React 应用挂载到 `#root`。它包裹了 `BrowserRouter`、`I18nProvider`、`ThemeProvider`、`SystemActionsProvider`，最后渲染 `App`。这意味着 `index.html` 的 `id="root"` 是硬约束：如果这个节点被删除或改名，React 启动会直接失败。

它还间接依赖 `web/src/lib/api.ts` 中读取的运行时全局变量，例如 `window.__HERMES_BASE_PATH__`、`window.__HERMES_SESSION_TOKEN__`、`window.__HERMES_AUTH_REQUIRED__`。这些变量不是在源码版 `web/index.html` 中写死的，而是由服务端在生产返回 HTML 时注入；开发环境下，`web/vite.config.ts` 的 `hermesDevToken()` 插件会尝试从后端 Dashboard HTML 中提取 token 和嵌入聊天标志，再注入到 dev HTML。

## 核心流程

开发流程是：浏览器访问 Vite dev server；Vite 返回 `web/index.html`；浏览器发现 `/src/main.tsx` 模块脚本；Vite 编译并提供 React/TypeScript 模块；`main.tsx` 查找 `#root`；React 渲染 `App`；`App` 再根据路由加载 `SessionsPage`、`AnalyticsPage`、`ModelsPage`、`ChatPage` 等页面。

生产构建流程是：`npm run build` 以 `web/index.html` 为模板；Vite 分析 `/src/main.tsx` 及其依赖；产出 `hermes_cli/web_dist/index.html` 和 `assets`。构建后的 HTML 通常不再引用 `/src/main.tsx`，而是引用打包后的静态资源。

生产运行流程是：`hermes_cli/web_server.py` 的 `mount_spa()` 读取 `hermes_cli/web_dist/index.html`；内部 `_serve_index()` 在 `</head>` 前注入 bootstrap script；这个脚本设置会话 token、Dashboard 嵌入聊天开关、base path、认证模式等运行时变量；浏览器加载构建后的 JS；`web/src/lib/api.ts` 读取这些变量，决定 REST API、WebSocket、插件资源的路径和认证方式。

反向代理路径前缀也是核心流程的一部分。`mount_spa()` 会根据 `X-Forwarded-Prefix` 注入 `window.__HERMES_BASE_PATH__`，并重写构建 HTML 中以 `/assets/`、`/favicon.ico`、`/fonts/`、`/ds-assets/` 开头的资源路径。前端随后用 `HERMES_BASE_PATH` 拼接 `/api`、`/api/pty`、`/dashboard-plugins` 等路径，避免部署在子路径时资源或接口请求打到错误位置。

## 关键函数的高层作用

`web/index.html` 自身没有函数。真正关键的是它交出的几个邻近入口函数。

`web/src/main.tsx` 中的 `exposePluginSDK()` 会在 React 渲染前暴露插件 SDK，使通过 `<script>` 加载的 Dashboard 插件能尽早访问 React、组件和注册能力。这是插件体系启动顺序的关键点。

`createRoot(...).render(...)` 是前端应用启动点。它把路由、国际化、主题、系统动作上下文统一挂到 `App` 外层，因此 `index.html` 只需要提供一个稳定的 `#root`。

`web/src/lib/api.ts` 的 `readBasePath()` 读取服务端注入的 `window.__HERMES_BASE_PATH__`，并规范化前缀格式。它影响所有 API 和插件资源路径，是 Dashboard 支持反向代理子路径部署的基础。

`fetchJSON()` 负责给 API 请求附加 `X-Hermes-Session-Token`，同时处理 cookie 认证模式下的 401 跳转、loopback 模式下 token 过期后的自动刷新。它依赖服务端注入到 HTML 的认证变量，因此 `index.html` 及服务端 HTML 改写逻辑不能随意破坏这些全局变量的注入位置。

`hermes_cli/web_server.py` 的 `mount_spa()` 和内部 `_serve_index()` 是生产态调用构建 HTML 的核心。它们负责 SPA fallback、token/base path 注入、静态资源挂载、CSS 内部 URL 重写，以及未构建前端时返回错误信息。

`web/vite.config.ts` 的 `hermesDevToken()` 只在开发服务器生效。它通过 Vite 的 `transformIndexHtml()` 钩子给开发态 HTML 补上后端注入变量，使 dev server 下的 `/api/*` 请求也能通过认证。

## 修改风险

最大风险是破坏 React 挂载点。`web/src/main.tsx` 明确使用 `document.getElementById("root")!`，所以 `id="root"` 不能删除、改名或延迟生成。否则页面会在启动阶段失败，且错误会表现为整个 Dashboard 空白。

第二个风险是改变模块入口路径。`/src/main.tsx` 是 Vite 开发态入口，生产构建也以它为依赖图起点。改动脚本路径、去掉 `type="module"`，或把入口移动到其他文件但不更新配置，会直接影响开发服务器和构建产物。

第三个风险是资源路径前缀。源码中 favicon 使用绝对路径 `/favicon.ico`，构建后 asset 也可能是绝对路径；服务端 `mount_spa()` 对这些路径有显式 rewrite 逻辑。新增 `<link>`、`<script>`、字体或图片引用时，如果使用新的绝对目录但没有同步服务端 rewrite，部署在子路径反向代理后可能加载失败。

第四个风险是破坏服务端注入点。`_serve_index()` 通过 `html.replace("</head>", f"{bootstrap_script}</head>", 1)` 注入运行时变量。如果删除 `</head>`、改成异常结构，或把关键 CSP/脚本策略调整到阻止内联脚本，Dashboard 的 token、base path、认证模式和嵌入聊天开关都可能失效。

第五个风险是误以为这里适合放业务逻辑。该文件应保持为薄模板。认证、API 前缀、插件 SDK、主题、国际化、页面路由都已经在 `web/src/main.tsx`、`web/src/App.tsx`、`web/src/lib/api.ts` 和 `hermes_cli/web_server.py` 中分层处理。把复杂逻辑塞进 `index.html` 会绕开 TypeScript、测试和构建体系，也容易与生产注入逻辑冲突。

第六个风险是 SEO 或静态标题改动的收益有限。Dashboard 是登录/本地管理型 SPA，`title` 和 favicon 主要影响浏览器标签与基础品牌展示；页面级标题、导航和内容由 React 控制。修改这里通常是全局行为，不适合承载某个具体页面的状态。
