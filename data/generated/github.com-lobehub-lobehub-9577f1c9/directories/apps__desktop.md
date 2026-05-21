# 目录：apps/desktop

## 它负责什么

`apps/desktop` 是 LobeHub 的 Electron 桌面端应用工程。它不是一个完全独立于 Web 的前端，而是把仓库主应用的 renderer 代码接入 Electron 壳层，同时补上桌面端才有的能力：窗口管理、系统菜单、托盘、通知、更新、文件访问、本地命令、MCP、CLI 嵌入、屏幕捕获、网络代理、异构 Agent 运行等。

从 `apps/desktop/package.json` 看，这个包的主入口是 `./dist/main/index.js`，开发命令是 `electron-vite dev`，构建命令是 `electron-vite build`，打包交给 `electron-builder`。也就是说，这个目录承担两类职责：

1. Electron 运行时职责：主进程、preload、安全 IPC、窗口与系统 API。
2. 桌面发行职责：构建、打包、更新渠道、native modules、图标、资源、CLI 二进制嵌入。

`apps/desktop` 的 renderer 侧并不只服务一个页面。`electron.vite.config.ts` 中配置了三个 HTML 入口：`index.html`、`popup.html`、`overlay.html`，分别对应主窗口、弹出窗口和屏幕捕获 overlay 这类桌面专用界面。renderer 的 `root` 指向仓库根目录，因此它会复用主仓库 `src/` 下的 SPA、组件、服务和状态逻辑，只是在 Electron 环境中注入桌面能力。

## 关键组成

顶层文件里，`package.json` 是这个桌面包的脚本和依赖入口。关键依赖包括 `electron`、`electron-vite`、`electron-builder`、`electron-updater`、`electron-store`、`electron-log`，以及工作区内部包如 `@lobechat/electron-client-ipc`、`@lobechat/electron-server-ipc`、`@lobechat/desktop-bridge`、`@lobechat/heterogeneous-agents` 等。这说明桌面端的 IPC 协议、桥接层和异构 Agent 能力都被拆到了 workspace package 中维护。

`electron.vite.config.ts` 是三端构建的核心配置。它把 Electron 工程拆成 `main`、`preload`、`renderer` 三个构建目标：

- `main` 输出到 `dist/main`，别名 `@` 指向 `apps/desktop/src/main`，主要运行 Electron 主进程逻辑。
- `preload` 输出到 `dist/preload`，同样可以访问主进程侧别名，但实际运行在 renderer 页面加载前的隔离脚本环境。
- `renderer` 输出到 `dist/renderer`，入口是 `index.html`、`popup.html`、`overlay.html`，并通过 `sharedRendererConfig` 复用主仓库的 Vite renderer 配置。

`electron.vite.config.ts` 里有两个值得特别注意的插件。`forceAbsoluteBasePlugin()` 强制 renderer 使用 `base: '/'`，避免深层 SPA 路由例如 `/popup/agent/:aid/:tid` 下相对资源路径解析错误。`electronDesktopHtmlPlugin()` 在开发服务器中把 `/popup/*` 重写到 `apps/desktop/popup.html`，把 `/overlay` 重写到 `overlay.html`，其余主入口走 `index.html`。这说明桌面端开发时的路由入口不是靠 Next.js，而是靠 electron-vite dev server 的 HTML 重写。

`electron-builder.mjs` 是发行配置。它根据 `UPDATE_CHANNEL` 区分 `stable`、`nightly`、`canary`，根据 `UPDATE_SERVER_URL` 选择 generic 更新源，否则回退到 GitHub provider。它还在 `beforePack` 阶段复制 native modules、复制 external runtime modules、下载 `agent-browser`、构建并嵌入 `apps/cli` 的产物到 `resources/bin/lobe-cli.js`。在 `afterPack` 阶段，它会把 native modules 放进 `app.asar.unpacked`，并在 macOS 上处理 `Assets.car` 图标和 Electron Framework 本地化资源裁剪。

`src/main/index.ts` 是主进程源码入口，内容很短：创建 `App` 实例，调用 `fixPath()`，再执行 `app.bootstrap()`。`fix-path` 通常用于修复 macOS GUI 应用启动时缺失 shell PATH 的问题。根据当前片段推断，真正的生命周期、协议注册、窗口创建、IPC 注册等逻辑集中在 `src/main/core/App.ts` 中，因为入口只负责把控制权交给 `App.bootstrap()`。

`src/main/controllers/registry.ts` 是桌面 IPC controller 注册表。它收集了 `AuthCtr`、`BrowserWindowsCtr`、`CliCtr`、`DevtoolsCtr`、`GatewayConnectionCtr`、`GitCtr`、`HeterogeneousAgentCtr`、`LocalFileCtr`、`McpCtr`、`McpInstallCtr`、`MenuCtr`、`NetworkProxyCtr`、`NotificationCtr`、`OpenInAppCtr`、`RemoteServerConfigCtr`、`RemoteServerSyncCtr`、`ScreenCaptureCtr`、`ShellCommandCtr`、`ShortcutCtr`、`SystemCtr`、`ToolDetectorCtr`、`TrayMenuCtr`、`UpdaterCtr`。这些类共同组成 renderer 可调用的桌面能力表。`DesktopIpcServices` 类型通过 `CreateServicesResult` 和 `MergeIpcService` 从 controller 构造器推导出来，说明这里不仅注册运行时对象，也产出类型安全的 IPC service 形状。

`src/preload/index.ts` 是 preload 入口。它调用 `setupElectronApi()` 暴露 Electron API，再在 `DOMContentLoaded` 后调用 `setupRouteInterceptors()`。这符合 Electron 的安全模型：renderer 不直接拿 Node/Electron 全能力，而是通过 preload 暴露受控 API，再通过 IPC 调主进程 controller。

`src/overlay` 是屏幕选择或窗口捕获相关的专用 renderer。目录里有 `ScreenCaptureOverlay.tsx`、`ChatPanel.tsx`、`WindowTag.tsx`、`useDragSelection.ts`、`useWindowHighlight.ts`、`overlaySelectionState.ts` 等文件，还配有测试文件。结合 `WindowOverlayCapture.md` 和 `overlay.html`，可以判断它负责桌面端屏幕/窗口捕获时的覆盖层 UI。

`resources` 和 `build` 分别放运行资源与打包素材。`resources` 包含 `splash.html`、`error.html`、tray 图标、本地化资源等；`build` 包含 `.icns`、`.ico`、`.png`、`Assets.car`、macOS entitlements、NSIS 图片等安装包素材。

## 上下游关系

上游方面，`apps/desktop` 依赖仓库根部的构建插件、主应用 renderer、workspace packages 和桌面专用 native/runtime 依赖。

`electron.vite.config.ts` 从 `../../plugins/vite/sharedRendererConfig` 引入 `sharedOptimizeDeps`、`sharedRendererDefine`、`sharedRendererPlugins`、`sharedRollupOutput`，说明 renderer 构建不是另起一套，而是和 Web SPA 保持共享配置。它还通过 `loadEnv(mode, ROOT_DIR, '')` 从仓库根目录加载环境变量，因此桌面构建会继承根项目环境配置。

主进程侧通过 `@lobechat/electron-server-ipc`、`@lobechat/electron-client-ipc` 这类包建立 IPC 类型和通信协议。`controllers/registry.ts` 的类型推导表明 controller 注册表会影响 renderer 能看到的桌面服务类型。技能说明中还提到，新增桌面功能通常要同时改：

- `apps/desktop/src/main/controllers/`：新增 controller。
- `apps/desktop/src/main/controllers/registry.ts`：注册 controller。
- `packages/electron-client-ipc/src/types.ts`：补 IPC 类型。
- `src/services/electron/`：在主应用 renderer 侧封装调用。
- `src/store/`：必要时接入 Zustand action。

下游方面，`apps/desktop` 产出 Electron 可运行应用和安装包。开发时执行 `dev` 启动 Electron + Vite；构建时产出 `dist/main`、`dist/preload`、`dist/renderer`；打包时 `electron-builder` 生成 macOS、Windows、Linux 对应产物。它还会把 `apps/cli` 构建结果嵌进桌面 app 的 `resources/bin/lobe-cli.js`，因此 CLI 是桌面发行包的一个下游运行组件，但源码构建上又是 `apps/desktop` 的上游依赖。

从业务调用链看，renderer 页面中的桌面功能通常不会直接 import `apps/desktop/src/main`。更合理的路径是：renderer 调 `src/services/electron/*`，service 调 preload 暴露的 IPC client，IPC 进入主进程 controller，controller 再访问 Electron API、文件系统、系统命令、MCP、CLI 或其他本地服务。

## 运行/调用流程

开发启动的大致流程是：执行 `apps/desktop` 的 `dev` 脚本，`electron-vite dev` 同时处理 main、preload、renderer。main 入口来自 `src/main/index.ts`，它创建 `App`，修复 PATH，然后 `bootstrap()`。根据当前片段推断，`App.bootstrap()` 内部会完成 Electron app 生命周期监听、协议注册、窗口创建、IPC controller 初始化、菜单/托盘/更新等启动动作；依据是入口只实例化 `App`，而 controller 注册表、协议常量、菜单目录、服务目录都集中在 `src/main` 下。

renderer 入口由 `electron.vite.config.ts` 的 `renderer.build.rolldownOptions.input` 决定。主窗口加载 `index.html`，popup 窗口加载 `popup.html`，overlay 加载 `overlay.html`。开发阶段，如果访问 `/popup/agent/...` 这样的深层路径，`electronDesktopHtmlPlugin()` 会把请求改写到 `popup.html`，让 React Router 接管后续路由。生产阶段，`forceAbsoluteBasePlugin()` 确保打包后的资源路径是 `/assets/...`，由 app 自定义协议处理，而不是在深层路径下错误解析成 `/popup/assets/...`。

IPC 调用流程可以按四层理解：

1. Renderer 中的业务代码触发桌面功能，比如读取本地文件、打开窗口、调用 CLI、检查更新。
2. `src/services/electron/` 这类服务层通过 preload 暴露的 API 发起 IPC 请求。
3. `src/preload/index.ts` 中的 `setupElectronApi()` 把安全封装后的接口挂给页面，`setupRouteInterceptors()` 处理 Electron 内的路由行为。
4. 主进程 controller 接收请求。controller 列表来自 `src/main/controllers/registry.ts`，具体能力由各 `*Ctr.ts` 实现。

打包流程则由 `electron-builder.mjs` 控制。它先判断更新渠道和签名环境，然后在 `beforePack` 准备 native modules、external runtime modules、`agent-browser` 和 CLI bundle；在 `afterPack` 处理平台相关资源，尤其是 macOS 的 `Assets.car` 和本地化裁剪。最终安装包根据 `package:*` 脚本生成，例如 `package:mac`、`package:win`、`package:linux`。

## 小白阅读顺序

建议先从 `apps/desktop/package.json` 开始，看懂这个包有哪些命令：`dev`、`build:main`、`package:*`、`type-check`、`test` 分别对应开发、构建、打包、类型检查和测试。这里能先建立“这是一个 Electron 子应用，不是普通网页目录”的基本认识。

第二步读 `apps/desktop/electron.vite.config.ts`。重点看 `main`、`preload`、`renderer` 三段配置，以及 `index.html`、`popup.html`、`overlay.html` 三个入口。读到这里要形成一个关键概念：桌面端 renderer 复用仓库根部 SPA，但 Electron 壳层提供额外入口和环境变量。

第三步读 `apps/desktop/src/main/index.ts` 和 `apps/desktop/src/main/core/App.ts`。当前片段只看到 `index.ts` 很薄，所以 `App.ts` 应该是理解启动流程的核心文件。阅读时关注 Electron 生命周期、窗口创建、自定义协议、IPC 注册、菜单/托盘/更新初始化等。

第四步读 `apps/desktop/src/main/controllers/registry.ts`。先不要急着逐个 controller 深挖，先把 controller 名字当作能力地图：`LocalFileCtr` 管本地文件，`UpdaterCtr` 管更新，`ScreenCaptureCtr` 管捕获，`McpCtr` 和 `McpInstallCtr` 管 MCP，`HeterogeneousAgentCtr` 管异构 Agent，`CliCtr` 管 CLI，`TrayMenuCtr` 管托盘菜单。

第五步读 `apps/desktop/src/preload/index.ts`、`electronApi.ts`、`invoke.ts`、`streamer.ts`。这一步重点理解 renderer 为什么不能直接访问主进程能力，以及 preload 如何把 IPC 封装成安全 API。

第六步按功能抽样读 controller。例如想理解文件能力，就读 `LocalFileCtr.ts` 和相关 service；想理解截图，就读 `ScreenCaptureCtr.ts` 与 `src/overlay`；想理解更新，就读 `UpdaterCtr.ts` 和 `electron-builder.mjs` 的 publish 配置；想理解菜单，就读 `MenuCtr.ts`、`TrayMenuCtr.ts`、`src/main/menus`。

最后再读 `electron-builder.mjs`。这个文件细节较多，适合在理解运行时之后再看，否则容易被签名、渠道、native modules、asar、CLI 嵌入这些打包问题干扰。

## 常见误区

第一个误区是把 `apps/desktop` 当成完整前端应用。实际上它的 renderer 大量复用仓库根目录 `src/` 的 SPA 能力，`apps/desktop` 更像 Electron 外壳、桌面 API 层和发行工程。改 UI 页面时不一定在 `apps/desktop/src` 下找，很多页面和状态仍在主仓库 `src/routes`、`src/features`、`src/store`、`src/services` 中。

第二个误区是绕过 IPC，试图让 renderer 直接访问 Node 或 Electron API。这个项目有清晰的 main/preload/renderer 分层：主进程 controller 负责系统能力，preload 负责安全暴露，renderer 通过 service 调用。新增桌面能力应沿着 controller、IPC 类型、renderer service、store action 这条链路做，而不是在页面里直接访问系统 API。

第三个误区是只改一个入口。桌面端至少有主窗口、popup、overlay 三类入口，`electron.vite.config.ts` 还专门处理了 `/popup/*` 和 `/overlay` 的 HTML 重写。改构建、路由或资源路径时，要确认三个入口是否都受影响，尤其是 popup 深层路由下的资源路径问题。

第四个误区是忽略 `UPDATE_CHANNEL`。`electron-builder.mjs` 中 stable、nightly、canary 会影响更新地址、协议 scheme、图标选择和发布配置。桌面打包问题常常不是业务代码问题，而是渠道环境变量、签名环境或更新源配置不一致导致的。

第五个误区是低估 native modules 和外部运行时依赖。`electron.vite.config.ts` 明确 externalize Electron、native dependencies 和若干 runtime modules；`electron-builder.mjs` 又在 pack 前后复制 native modules。这类依赖如果被错误 bundle、遗漏到 asar，可能开发环境正常、打包后失败。

第六个误区是把 `src/overlay` 当普通页面。它服务屏幕捕获/窗口选择这类桌面专用交互，和主 SPA 页面不同，涉及覆盖层、拖拽选择、窗口高亮、聊天面板定位等逻辑。读它时应结合 `overlay.html`、`ScreenCaptureCtr` 和 `WindowOverlayCapture.md`，不要只按普通 React 页面理解。

第七个误区是认为 `package.json` 里的 `build:main` 只构建 main。脚本名叫 `build:main`，但实际命令是 `electron-vite build`，配置里同时包含 main、preload、renderer 三端构建。真正的打包还要再经过 `electron-builder` 的 `package:*` 脚本。
