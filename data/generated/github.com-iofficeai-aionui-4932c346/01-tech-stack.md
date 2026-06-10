# 技术栈与运行环境

本项目是 Bun workspace + Electron/Vite + React/TypeScript 的多包仓库。根 `package.json` 的 `workspaces` 指向 `packages/*`，主要包包括 `@aionui/desktop`、`@aionui/web-host`、`@aionui/web-cli`、`@aionui/shared-scripts`。桌面应用由 `electron-vite` 构建，入口配置是 `packages/desktop/electron.vite.config.ts`；WebUI CLI 是 `packages/web-cli`；移动端在 `mobile`，使用 Expo 与 React Native。依赖和脚本显示，这个仓库同时面向桌面端、本地 WebUI/远程 WebUI、移动客户端、扩展生态和自动化测试。

## 包管理和脚本信号

根目录有 `bun.lock`，`package.json` 的脚本大量使用 `bun`、`bunx`、`tsx`、`electron-vite`、`vitest`、`playwright`，说明日常开发入口以 Bun 为主。常用脚本包括 `bun start` 或 `bun run dev` 启动 Electron 开发模式，`bun run webui` 启动浏览器 WebUI，`bun run package` 构建 main/preload/renderer 到 `out/`，`bun run dist` 通过 `scripts/build-with-builder.js` 调用 Electron Builder 打包。质量工具是 `oxlint`、`oxfmt`、`tsc --noEmit`、`vitest`、`playwright`，贡献文档 `docs/contributing/development.md` 还要求 Node.js 22+、Bun、Python 3.11+ 和 `prek`。

需要注意，`packages/desktop/package.json` 的版本是 `0.0.0`，但 `electron.vite.config.ts` 明确注释：桌面包版本只是 workspace 内部占位，用户可见版本来自根 `package.json`。因此读版本逻辑时不要误以为 desktop 包版本就是产品版本。

## Electron 与 Vite

`packages/desktop/electron.vite.config.ts` 把应用拆成三个构建目标：`main`、`preload`、`renderer`。`main` 的入口是 `packages/desktop/src/index.ts`，并使用 `externalizeDepsPlugin`，但排除了 `fix-path` 和 `@aionui/web-host`，原因是后者在 workspace 中以 TS 源码形式存在，需要被打进 main bundle。`preload` 的入口包括 `main.ts` 和桌面宠物相关 preload。`renderer` 的 root 是 `packages/desktop/src/renderer`，采用多页应用配置：`index.html`、`pet/pet.html`、`pet-hit.html`、`pet-confirm.html`。Vite 插件包括 UnoCSS、Sentry source map、图标转换插件和静态资源复制。

这个构建配置透露了几个读源码前必须知道的概念：main 可以使用 Node/Electron API；renderer 是浏览器环境；preload 是两者之间的最小安全桥；项目用路径别名 `@`、`@common`、`@renderer`、`@process`；renderer 里不能直接依赖 Node 能力，而是通过 `ipcBridge`、HTTP 或 preload 暴露的能力访问。

## UI、状态和样式

renderer 使用 React 19、React Router 7、SWR、Arco Design、UnoCSS、CSS Modules、CodeMirror、Monaco、react-markdown、KaTeX、Mermaid、diff2html 等。`packages/desktop/src/renderer/main.tsx` 导入 `@arco-design/web-react`、`@arco-design/web-react/es/_util/react-19-adapter`、`uno.css`、`styles/arco-override.css`、`styles/themes/index.css` 和 `styles/markdown.css`。路由定义在 `packages/desktop/src/renderer/components/layout/Router.tsx`，用 `HashRouter` 管理 `/guid`、`/conversation/:id`、`/team/:id`、`/settings/*`、`/scheduled` 等页面。

样式方面，`uno.config.ts` 和 `packages/desktop/src/renderer/styles` 是全局样式信号。`docs/theming/tokens.md` 与 `packages/desktop/src/renderer/styles/themes/README.md` 说明项目有主题 token 和主题文件。组件库以 Arco 为主，图标依赖 `@icon-park/react`，并在 Vite 中通过自定义 `iconParkPlugin` 包一层 `IconParkHOC`。

## 后端进程、HTTP 和 WebSocket

AionUi 的业务后端不是纯前端实现。`packages/desktop/src/index.ts` 创建 `BackendLifecycleManager`，通过 `packages/desktop/src/process/backend/binaryResolver.ts` 查找 `aioncore` 二进制：优先查 `resourcesPath/bundled-aioncore/<platform>-<arch>/aioncore[.exe]`，再查系统 PATH。`packages/web-host/src/backend-launcher.ts` 负责实际 spawn、端口选择、健康检查、崩溃重启、进程树关闭和环境变量注入。`buildSpawnArgs` 会传入 `--port`、`--data-dir`、`--log-level`、`--app-version`、`--managed-resources-mode bundled`、`--log-dir`、`--work-dir`、`--local` 等参数。

前端业务调用主要走 `packages/desktop/src/common/adapter/ipcBridge.ts`。虽然文件名叫 IPC bridge，但文件头明确说明多数业务调用已经替换为 HTTP REST 与 WebSocket，只有窗口控制、原生对话框、自动更新、devtools、zoom、CDP、深链等 Electron 原生操作继续走 IPC。`conversation.create` 映射到 `POST /api/conversations`，`conversation.sendMessage` 映射到 `POST /api/conversations/:id/messages`，`responseStream` 是 `message.stream` WebSocket emitter。`packages/desktop/src/common/adapter/httpBridge.ts` 是这些 HTTP/WS helper 的底层。

## 数据与配置

本地数据有两层。旧层在 `packages/desktop/src/process/utils/initStorage.ts`，通过 base64 编码的 JSON 文件保存配置、环境、历史消息，并包含旧目录迁移和旧数据清理逻辑。新层由后端 API 与 SQLite 支撑，`packages/desktop/src/process/services/database/schema.ts` 定义了用户、会话、消息、团队、团队邮箱和团队任务表，当前 `CURRENT_DB_VERSION` 是 26。renderer 的 `configService` 从 `/api/settings/client` 获取客户端配置，缓存到内存并提供订阅；写入配置时再 `PUT /api/settings/client`。这种设计意味着 UI 读写设置并不直接操作本地文件，而是以 API 为主，旧文件逻辑主要服务迁移和主进程早期启动。

## 移动端与扩展

`mobile/package.json` 显示移动端使用 Expo Router、React Native 0.83、React 19、axios、AsyncStorage、SecureStore、FlashList、react-native-markdown-display 等。`mobile/src/services/api.ts`、`mobile/src/services/websocket.ts`、`mobile/src/context/ConnectionContext.tsx`、`WebSocketContext.tsx` 表明它更像连接 AionUi 后端的移动客户端，而不是复制桌面端 Electron 逻辑。

扩展生态的信号在 `examples/*/aion-extension.json` 和 `examples/hello-world-extension/contributes/*`。示例覆盖 agent、assistant、MCP server、settings tab、skill、theme、channel 等贡献点。源码中设置页、能力页和 `common/config/storage.ts` 的类型也出现了 assistants、skills、MCP、channels、remote agents、custom agents 等字段。阅读扩展功能时应先从示例 manifest 入手，再回到 renderer settings 和后端 API 映射。
