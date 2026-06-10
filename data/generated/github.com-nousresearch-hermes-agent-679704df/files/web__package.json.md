# 文件：web/package.json

## 一句话定位

`web/package.json` 是 Hermes Agent Web Dashboard 的前端包清单，负责定义这个 React/Vite 单页应用的本地开发、类型检查构建、静态预览入口，以及运行 dashboard UI 所需的 npm 依赖边界。

## 它暴露/定义了什么

它定义了一个私有 npm 包：`name` 为 `web`，`private: true`，`type: module`，说明该目录按 ESM 方式组织前端代码，且不是面向 npm registry 发布的独立库。核心暴露面是 `scripts`：

`dev` 启动 Vite 开发服务器，用于热更新开发；`build` 先执行 `tsc -b` 做 TypeScript project build，再执行 `vite build` 生成生产静态资源；`lint` 运行 ESLint；`preview` 运行 Vite 的本地预览服务器。

依赖上，它把 dashboard 的主要技术栈固定为 React 19、React Router 7、Vite 7、Tailwind CSS 4、`@nous-research/ui`、`lucide-react`、`motion`、`gsap`、`@xterm/*`、`@react-three/fiber`、`@observablehq/plot` 等。由此可以看出它不只是普通配置页，而是包含主题化 UI、图表、动画、3D/可视化、终端嵌入能力的浏览器 dashboard。

## 谁调用它

直接调用者是开发者或 CI/发布流程中的 npm 命令，例如在 `web/README.md` 中记录的 `npm install`、`npm run dev`、`npm run build`。仓库的 Python CLI 侧也会依赖构建产物：`hermes_cli/main.py` 中有 `_web_ui_build_needed`、`_build_web_ui`、`cmd_dashboard` 等 dashboard 相关逻辑；根据当前片段推断，`hermes dashboard` 会检查或使用 `web` 构建出的静态资源，而不是直接运行 Vite dev server。

生产运行时的调用链不是浏览器读取 `package.json`，而是 `npm run build` 先把资源输出到 `hermes_cli/web_dist`，再由 `hermes_cli/web_server.py` 服务该目录下的 SPA。`pyproject.toml` 又把 `hermes_cli/web_dist/**/*` 纳入 package data，使构建后的 dashboard 能随 Python 包分发。

## 它调用谁

从脚本层看，`package.json` 调用的是工具链命令：`vite`、`tsc -b`、`eslint .`、`vite preview`。这些命令进一步读取 `web/vite.config.ts`、`web/tsconfig*.json`、`web/eslint.config.js`、`web/index.html` 和 `web/src/main.tsx`。

从依赖层看，运行时主要调用 React 渲染体系、`react-router-dom` 路由、`@nous-research/ui` 设计系统、Tailwind/Vite 样式集成、`@xterm/*` 终端组件、图表和动画库。开发构建时则依赖 `@vitejs/plugin-react`、`@tailwindcss/vite`、TypeScript、ESLint 及相关类型包。

## 核心流程

开发流程是：先启动 Python dashboard 后端，例如 `python -m hermes_cli.main web --no-open` 或同类 dashboard 命令；再进入 `web/` 执行 `npm run dev`。Vite dev server 负责 HMR，并通过 `web/vite.config.ts` 将 `/api` 和 `/dashboard-plugins` 代理到后端。配置中的 `hermesDevToken` 插件还会在 dev 模式读取后端注入到 HTML 的 session token，再注入到 Vite 页面，避免受保护 API 在开发环境中全部 401。

构建流程是：`npm run build` 先用 `tsc -b` 做类型层面的项目构建校验，再由 Vite 打包。`vite.config.ts` 将 `outDir` 设置为 `../hermes_cli/web_dist`，所以产物不落在常见的 `web/dist`，而是直接进入 Python 服务端期望的静态资源目录。随后 `hermes_cli/web_server.py` 挂载该 SPA，处理 `index.html` token/base path 注入、静态 assets、插件资源和 API 路由。

## 关键函数的高层作用

`package.json` 本身没有 JavaScript 函数，关键“函数性入口”体现为 scripts。`dev` 是开发入口，聚合 Vite、React 插件、Tailwind 插件和后端代理；`build` 是发布入口，承担类型检查和生产打包；`lint` 是代码质量入口；`preview` 是本地检查已构建应用行为的入口。

与它强相关的核心函数在 `web/vite.config.ts`：`hermesDevToken()` 是开发环境专用 Vite 插件，用来从运行中的 dashboard 后端同步 session token 和嵌入式 chat 标志；`defineConfig(...)` 组织插件、路径别名、依赖去重、构建输出目录和代理规则。`web/src/main.tsx` 中的 `createRoot(...).render(...)` 是浏览器运行时入口，负责挂载 `BrowserRouter`、`I18nProvider`、`ThemeProvider`、`SystemActionsProvider` 和 `App`。辅助配置如 `resolve.alias`、`dedupe`、`server.proxy` 属于构建/开发支撑，不是业务逻辑中心。

## 修改风险

最大风险是脚本或输出目录变更。`build` 当前输出到 `hermes_cli/web_dist`，Python 端、打包配置和 `hermes dashboard` 都围绕这个目录工作；如果改回 `web/dist` 或调整构建命令，dashboard 可能启动但找不到 `index.html` 或加载旧资源。

依赖版本也有较高风险。React、Vite、Tailwind、`@nous-research/ui`、`@xterm/*`、`@react-three/fiber` 这类包会影响全局渲染、样式 token、终端嵌入和插件 SDK。升级时必须同步 `package-lock.json`，并重点验证 `npm run build`、`npm run lint`、dashboard 页面、`/chat` 终端、主题切换和 dashboard 插件加载。

另一个风险是开发代理和鉴权 token 机制。`vite.config.ts` 依赖后端 dashboard 的 HTML 注入格式；如果后端变量名或认证方式变化，而 `package.json` 仍只启动普通 Vite dev server，开发环境会出现 API 401，但生产环境可能正常，容易造成误判。

最后，`type: module` 影响配置文件和工具链的模块解析方式。随意改成 CommonJS 或混用旧插件版本，可能让 Vite、ESLint、TypeScript 配置加载失败。对于新增依赖，应确认它是运行时依赖还是 devDependency，避免把构建工具带入运行依赖，或把浏览器运行所需包错误放到 devDependencies。
