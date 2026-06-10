# 目录：extensions/diffs

## 它负责什么

`extensions/diffs` 是 OpenClaw 内置的 `diffs` plugin，职责是给 agent 提供一个只读 diff 查看与渲染能力。它暴露一个同名工具 `diffs`，可以接收两类输入：一类是 `before` / `after` 文本对比，另一类是 unified patch。输出也分两类：通过 gateway 托管的 viewer URL，或者渲染成 PNG/PDF 文件；`mode=both` 时两者都生成。

这个目录不是通用 diff 算法库，而是 plugin 包装层：它把 `@pierre/diffs` 的 diff 渲染能力接入 OpenClaw plugin SDK，补上工具 schema、plugin 配置、HTTP viewer 路由、临时 artifact 存储、浏览器截图/PDF 导出、安全访问控制、prompt guidance 和技能目录。核心目标是让 agent 在会话中能把代码差异以可读页面或附件形式展示给用户。

从边界上看，它遵循 `extensions/AGENTS.md` 的 plugin 规则：生产代码主要通过 `openclaw/plugin-sdk/*` 与宿主交互，不直接依赖 core 内部路径；对外入口集中在 `index.ts`、`api.ts`、`runtime-api.ts` 和 manifest。

## 直接子目录地图

`extensions/diffs/src` 是主要实现目录。它包含 plugin 注册、工具执行、配置解析、diff HTML 渲染、artifact 存储、HTTP 服务、浏览器截图、viewer 前端 payload 与测试。这个目录是理解主流程的重点，但 overview 层面不需要逐个测试文件展开。

`extensions/diffs/assets` 存放浏览器端 viewer runtime，目前关键产物是 `assets/viewer-runtime.js`。它由 `package.json` 中的 `build:viewer` 脚本从 `src/viewer-client.ts` 打包生成，并在 plugin build 配置里声明为 static asset。

`extensions/diffs/skills` 存放随 plugin 分发的 agent skill。manifest 通过 `"skills": ["./skills"]` 声明它。这里的 `skills/diffs/SKILL.md` 面向 agent 使用场景，和工具的 prompt guidance 一起帮助模型稳定调用 `diffs`。

根层文件也很重要：`openclaw.plugin.json` 是 plugin 发现、配置 UI、工具契约与 schema 的静态元数据；`package.json` 是 npm 包、依赖、打包和 OpenClaw 安装信息；`README.md` 是用户视角说明；`npm-shrinkwrap.json` 锁定该 plugin 包依赖。

## 关键入口

`extensions/diffs/index.ts` 是 plugin 的代码入口。它调用 `definePluginEntry`，声明 `id: "diffs"`、名称、描述、`diffsPluginConfigSchema`，并把实际注册函数指向 `registerDiffsPlugin`。宿主加载 plugin 时主要从这里进入。

`extensions/diffs/openclaw.plugin.json` 是静态发现入口。它声明 plugin id、启动激活、工具契约 `contracts.tools: ["diffs"]`、技能目录、配置 schema 和 UI hints。这里可以直接看到 `viewerBaseUrl`、`defaults.*`、`security.allowRemoteViewer` 等配置面，也能看到历史兼容字段如 `format`、`imageFormat`、`imageQuality`。

`extensions/diffs/src/plugin.ts` 是运行时注册入口。`registerDiffsPlugin` 创建 `DiffArtifactStore`，解析当前 plugin 配置，注册 `diffs` 工具，注册 `/plugins/diffs` 前缀 HTTP 路由，并在 `before_prompt_build` hook 中注入 `DIFFS_AGENT_GUIDANCE`。如果只想知道 plugin 怎样挂到 OpenClaw 生命周期，这个文件优先读。

`extensions/diffs/src/tool.ts` 是 agent 工具入口。`createDiffsTool` 定义工具名称、说明、TypeBox 参数 schema 和 `execute` 主体。它负责归一化输入、模式、主题、布局、TTL、文件格式和质量参数，然后调用渲染、存储、URL 构造和截图导出逻辑，最终返回 `content` 与 `details`。

`extensions/diffs/api.ts`、`extensions/diffs/runtime-api.ts` 是本 plugin 暴露和复用 SDK 能力的本地 barrel。它们不是业务主流程，但体现 plugin 边界：外部或本目录内部通过这些入口拿到 `definePluginEntry`、plugin 类型、临时目录解析、请求 IP 解析等能力，避免深层依赖 core 内部实现。

## 主流程位置

工具调用主流程集中在 `extensions/diffs/src/tool.ts`。调用 `diffs` 后，`execute` 先用 `normalizeDiffInput` 识别 `before` / `after` 或 `patch` 输入，并校验大小限制；然后解析 `mode`，把 `image` 旧别名归一到文件输出语义；再合并显式参数与 plugin defaults，形成 `DiffRenderOptions` 和 `DiffRenderTarget`。

渲染流程在 `extensions/diffs/src/render.ts`。它使用 `@pierre/diffs` 的 `parsePatchFiles`、`preloadFileDiff`、`preloadMultiFileDiff` 做 SSR 预渲染，生成 viewer 用 HTML 和文件渲染用 HTML。这里还负责标题、文件名、语言提示、主题、布局、行号、wrap、背景、diff indicators 等展示选项。viewer 页面会嵌入 JSON payload，并引用 runtime 脚本来恢复交互能力。

viewer 托管流程在 `extensions/diffs/src/store.ts` 和 `extensions/diffs/src/http.ts`。`DiffArtifactStore` 在临时目录下创建 artifact id/token、写入 `viewer.html` 和 metadata，并设置 TTL 与过期清理。`createDiffsHttpHandler` 处理 `/plugins/diffs/view/<id>/<token>` 访问，同时服务 viewer runtime asset；它会校验本地/远程访问策略、请求方法、id/token 格式、过期状态，并设置 CSP、`no-store`、`nosniff` 等响应头。

文件输出流程跨 `tool.ts`、`browser.ts`、`store.ts`。当 `mode=file` 或 `mode=both` 需要 PNG/PDF 时，工具会通过 `PlaywrightDiffScreenshotter` 使用 Chromium 兼容浏览器打开渲染 HTML，按 `fileFormat`、`fileQuality`、`fileScale`、`fileMaxWidth` 等选项导出文件，再把文件路径写入 artifact metadata 或 standalone file metadata。

配置流程主要在 `extensions/diffs/src/config.ts` 与 `openclaw.plugin.json`。manifest 提供静态 schema 和 UI hints；运行时通过 `resolveLivePluginConfigObject` 读取当前配置，再由 `resolveDiffsPluginDefaults`、`resolveDiffsPluginSecurity`、`resolveDiffsPluginViewerBaseUrl` 变成工具和 HTTP handler 使用的结构。

## 推荐阅读顺序

先读 `extensions/diffs/README.md`，建立用户视角：工具输入、输出、mode、默认配置、安全选项和限制。然后读 `extensions/diffs/openclaw.plugin.json`，理解 plugin 如何被宿主发现，以及哪些配置是公开契约。

接着读 `extensions/diffs/index.ts` 和 `extensions/diffs/src/plugin.ts`，看 OpenClaw 如何注册工具、HTTP 路由和 prompt guidance。之后读 `extensions/diffs/src/tool.ts`，这是 agent 调用落点，也是参数归一化和分支决策最集中的地方。

再读 `extensions/diffs/src/render.ts`，理解 before/after 与 patch 如何变成 HTML。然后读 `extensions/diffs/src/store.ts`、`extensions/diffs/src/http.ts`，掌握 viewer artifact 的生命周期、token URL 和访问控制。最后根据兴趣补读 `extensions/diffs/src/browser.ts`、`extensions/diffs/src/viewer-client.ts`、`extensions/diffs/src/viewer-payload.ts`，分别对应文件导出和浏览器端交互。

## 常见误区

不要把 `diffs` 理解成会修改代码的工具。它是 read-only viewer/file renderer，只负责展示差异，不应用 patch，也不写回项目文件。

不要把 `mode=image` 当成新能力。代码和 README 都显示它是 deprecated alias，语义上等同于文件输出；新的调用应使用 `mode=file`，格式由 `fileFormat` 控制。

不要认为 viewer URL 天然可公网访问。默认逻辑偏向本地 loopback；远程访问受 `security.allowRemoteViewer`、gateway trusted proxy、client IP 解析和失败限流影响。共享 URL 时还要考虑 `viewerBaseUrl` 或工具参数 `baseUrl`。

不要把 artifact 当作长期存储。`DiffArtifactStore` 创建的是有 TTL 的临时 artifact，默认过期并会清理；`details.filePath` 和 viewer token 都适合当前会话交付，不适合作为持久文档地址。

不要绕过 plugin 边界去读 core 内部实现。这个目录的入口和运行时依赖已经通过 `api.ts`、`runtime-api.ts`、`openclaw/plugin-sdk/*` 收束；如果需要扩展能力，应优先看 SDK seam 和 manifest 契约，而不是从 `src/**` 深层路径偷取实现。

不要只看 `assets/viewer-runtime.js` 来理解前端逻辑。它是打包产物，源头在 `src/viewer-client.ts`，构建脚本在 `package.json` 的 `build:viewer`。对于源码学习，应优先看 TS 源文件和 render payload 结构。
