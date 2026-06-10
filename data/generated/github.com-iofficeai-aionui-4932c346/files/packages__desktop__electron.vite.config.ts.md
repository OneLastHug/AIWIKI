# 文件：packages/desktop/electron.vite.config.ts
## 一句话定位
这是桌面端 Electron 构建的总配置入口，专门给 `electron-vite` 使用，用来同时定义 `main`、`preload`、`renderer` 三个进程/页面的打包、开发服务路由、依赖外置、环境变量注入和输出分包策略。

## 它暴露/定义了什么
它默认导出一个 `defineConfig(...)` 结果，不是业务模块，而是一份构建蓝图。里面还定义了两个只在本文件内部使用的 Vite 插件：`forceAbsoluteBasePlugin()` 和 `electronDesktopHtmlPlugin()`。前者强制 renderer 的 `base` 为 `/`，后者在开发态重写 HTML 请求，把 SPA 深链接导向 `index.html`、`overlay.html` 或 `popup.html`。

## 谁调用它
根据当前片段推断，它主要被 `apps/desktop/package.json` 里的脚本调用，尤其是 `dev`、`build:main`、`start` 这些命令，它们都直接跑 `electron-vite dev/build/preview`。也就是说，真正的调用者不是应用运行时代码，而是构建/启动工具链。脚本入口见 `project/lobehub/apps/desktop/package.json`。

## 它调用谁
它直接依赖 `../../plugins/vite/sharedRendererConfig`，复用共享的 `sharedOptimizeDeps`、`sharedRendererDefine`、`sharedRendererPlugins`、`sharedRollupOutput`。它还读取 `./external-runtime-deps.config.mjs` 和 `./native-deps.config.mjs` 来决定哪些模块必须外置。构建时还会用到 `dotenv`、`vite` 的 `loadEnv`、以及本地 `package.json` 里的版本号作为 `__MAIN_VERSION__` 注入到 renderer。

## 核心流程
启动时先 `dotenv.config()`，再根据 `NODE_ENV` 决定 `mode` 和 `isDev`，然后用 `loadEnv(mode, ROOT_DIR, '')` 把环境变量灌进 `process.env`。接着读取桌面端 `package.json`，拿到版本号。之后配置三条管线：`main` 负责主进程打包并外置 Electron、原生模块和部分运行时代码；`preload` 只外置 Electron；`renderer` 负责三个入口页面 `index.html`、`overlay.html`、`popup.html` 的构建，并挂载共享插件和分包策略。

其中最关键的运行时修正有两个：一是 `forceAbsoluteBasePlugin()` 修正 `base`，避免生产环境把资源地址变成相对路径后，在 popup 这类深层路由下解析错位；二是 `electronDesktopHtmlPlugin()` 负责开发服务器的请求改写，让 `/popup/...` 这种 SPA 路由落到正确 HTML 页面，而不是误命中静态资源。

## 关键函数的高层作用
`forceAbsoluteBasePlugin()` 只做一件事：把 renderer 的 `base` 固定成 `/`，防止生产构建把资产路径“缩回”当前路由层级。`electronDesktopHtmlPlugin()` 只负责开发态路由改写，区分文档入口、overlay、popup，以及 `/popup/*` 深链接。除此之外，`sharedRendererDefine(...)` 和 `sharedRendererPlugins(...)` 虽然不在本文件定义，但这里是它们最重要的消费点：前者注入 `__ELECTRON__`、`__MOBILE__`、`process.env.*`，后者补齐 React、平台解析、开发调试等 renderer 插件。

## 修改风险
这个文件是桌面端构建的“总开关”，改动面很大。最容易出问题的是三类：第一，`base` 或 HTML 重写规则改错，会直接导致 popup、overlay 或主窗口在 dev/prod 下白屏、资源 404；第二，`rolldownOptions.external` 和 `manualChunks` 改错，会把原生依赖、共享依赖或 i18n 包进错误 chunk，触发运行时重入、模块缺失或 Electron 主进程重复初始化；第三，`define` 和 `loadEnv` 的处理如果变动，会影响更新通道、版本号和运行时条件分支，属于“看起来只是构建配置，实际能改坏启动链路”的文件。
