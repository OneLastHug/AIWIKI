# 目录：ui

## 它负责什么

`ui` 是 OpenClaw 的 Control UI 前端工程目录。根据 `ui/package.json` 和 `ui/AGENTS.md`，它是一个独立的 Vite 应用包，包名为 `openclaw-control-ui`，主要负责浏览器端控制界面的构建、开发预览、前端测试、静态资源和本地化文案管线。它不是核心运行时、插件加载器或 CLI 的实现位置，而是面向用户的控制界面层。

从依赖看，这个目录的 UI 技术栈偏轻量：`vite` 负责开发与构建，`lit` 很可能承担 Web Components 或组件渲染，`markdown-it`、`marked`、`highlight.js`、`dompurify`、`@create-markdown/preview` 说明界面里有 Markdown 渲染、代码高亮和内容净化相关能力；`@noble/ed25519` 暗示某些前端流程可能涉及签名、校验或身份相关的轻量加密操作。测试侧使用 `vitest`、`jsdom`、`@vitest/browser-playwright` 和 `playwright`，说明既有 DOM/单元测试，也可能有浏览器级交互测试。

`ui/AGENTS.md` 特别强调 i18n 归属：非英文 locale bundle 属于生成产物，默认不手改；英文文案和生成/运行时管线才是维护入口。这意味着阅读或修改 Control UI 文案时，应先从 `ui/src/i18n/locales/en.ts` 和相关生成脚本理解数据流，而不是直接从某个翻译文件下手。

## 直接子目录地图

`ui/config`：Control UI 构建或运行相关的配置补充目录。当前可见关键文件是 `ui/config/control-ui-chunking.ts`，从命名看用于 Vite 构建分包或 chunk 策略配置。根据当前片段推断，它服务于前端构建产物组织，而不是业务组件本身。

`ui/public`：静态公开资源目录。包含 `favicon.ico`、`favicon.svg`、`favicon-32.png`、`apple-touch-icon.png`、`manifest.webmanifest`、`sw.js`。这类文件通常由 Vite 原样拷贝到构建输出，用于浏览器图标、PWA manifest 和 service worker。这里是静态外壳资源，不是主要业务逻辑入口。

`ui/src`：Control UI 的源码主体。当前可见一级文件有 `ui/src/main.ts`、`ui/src/styles.css`、`ui/src/local-storage.ts`、`ui/src/css.d.ts`、`ui/src/markdown-it-task-lists.d.ts`，以及子目录 `ui/src/i18n`、`ui/src/styles`、`ui/src/test-helpers`、`ui/src/types`、`ui/src/ui`。其中 `ui/src/ui` 很可能是主要组件和界面组织层，`ui/src/i18n` 是本地化系统，`ui/src/styles` 是样式模块，`ui/src/types` 放共享类型，`ui/src/test-helpers` 放测试辅助设施。

## 关键入口

`ui/package.json` 是工程级入口，定义了 `build`、`dev`、`preview`、`test` 四个脚本：构建走 `vite build`，开发走 `vite`，预览走 `vite preview`，测试走 `vitest run --config vitest.config.ts`。阅读这个目录时应先把它当成一个前端子项目看，而不是从根 CLI 命令直接切入。

`ui/index.html` 是浏览器页面外壳入口。Vite 应用一般从这里挂载脚本和根节点；根据当前片段推断，它会间接加载 `ui/src/main.ts`，完成 Control UI 的初始化。

`ui/src/main.ts` 是前端源码入口。虽然当前任务只读取到文件列表，没有展开内容，但在 Vite + TypeScript 应用中，`main.ts` 通常负责注册根组件、初始化全局样式、挂载应用状态或连接浏览器事件。后续精读应从这里进入运行路径。

`ui/vite.config.ts` 是构建工具入口，负责 Vite 配置、插件、别名、构建输出和开发服务器行为。`ui/config/control-ui-chunking.ts` 很可能被它引用，用于把较大的 Markdown、渲染器或 UI 模块拆成合理 chunk。

`ui/vitest.config.ts` 和 `ui/vitest.node.config.ts` 是测试入口。前者对应默认 UI 测试脚本，后者从命名看用于 Node 环境或非浏览器环境测试配置。`ui/src/test-helpers` 则是测试支撑代码所在位置。

`ui/AGENTS.md` 是本目录的维护规则入口，尤其是 i18n。它指出英文源文案位于 `ui/src/i18n/locales/en.ts`，生成与运行时相关位置包括 `scripts/control-ui-i18n.ts`、`ui/src/i18n/lib/types.ts`、`ui/src/i18n/lib/registry.ts`。

## 主流程位置

启动与构建主流程在 `ui/package.json`、`ui/index.html`、`ui/src/main.ts`、`ui/vite.config.ts` 一线。可以按“npm script -> Vite 配置 -> HTML 外壳 -> TypeScript 入口 -> UI 组件”的顺序理解。根据当前片段推断，真实界面布局和交互主体应集中在 `ui/src/ui`，而全局样式入口在 `ui/src/styles.css`，更细的样式组织在 `ui/src/styles`。

本地状态或浏览器持久化相关流程的入口是 `ui/src/local-storage.ts`。它应当封装 Control UI 使用 `localStorage` 的读写规则，避免组件到处直接访问浏览器存储。若要理解用户偏好、最近选择、界面状态恢复等行为，应把它列入早期阅读范围。

国际化主流程在 `ui/src/i18n`，但维护源头不是所有 locale 文件等价。规则明确说 `ui/src/i18n/locales/en.ts` 是源文案，非英文 locale bundle 和 `ui/src/i18n/.i18n/*` 多数是生成结果。生成命令相关入口是根部脚本 `scripts/control-ui-i18n.ts`，常用命令包括 `pnpm ui:i18n:sync`、`pnpm ui:i18n:report`、`pnpm ui:i18n:check`。阅读时应区分“运行时 registry/types”和“生成产物”。

Markdown 显示主流程根据依赖推断分布在 `ui/src/ui` 或其下组件，并依赖 `markdown-it`、`marked`、`markdown-it-task-lists`、`highlight.js`、`dompurify`。如果要追踪消息、文档、日志或富文本预览的渲染链路，应从组件中搜索 Markdown 渲染器，再回看类型和样式。

## 推荐阅读顺序

第一步读 `ui/AGENTS.md`，先掌握本目录最容易踩错的 i18n 规则，尤其是哪些文件不能手改、哪些命令用于同步和检查。

第二步读 `ui/package.json`，确认这是独立 Vite 前端包，并理解开发、构建、预览、测试命令的边界。

第三步读 `ui/index.html` 和 `ui/src/main.ts`，建立浏览器加载到应用初始化的主线。这里是从“静态页面外壳”进入“TypeScript 应用”的切口。

第四步读 `ui/vite.config.ts` 和 `ui/config/control-ui-chunking.ts`，理解构建配置、chunk 策略、测试/开发环境可能的特殊处理。遇到懒加载、动态导入或构建产物问题时，这一步尤其重要。

第五步进入 `ui/src/ui` 看组件结构，再配合 `ui/src/styles.css`、`ui/src/styles` 看视觉和布局规则。overview 阶段只需要识别主容器、页面区域和共享组件，不必逐个叶子文件展开。

第六步按需求补读 `ui/src/i18n`、`ui/src/local-storage.ts`、`ui/src/types`、`ui/src/test-helpers`。文案问题看 i18n，持久化问题看 local-storage，类型契约看 types，测试写法看 test-helpers 和 vitest 配置。

## 常见误区

不要把 `ui` 当成 OpenClaw 核心运行时目录。核心插件、渠道、网关、协议和 CLI 逻辑主要在 `src/`、`packages/`、`extensions/` 等位置；`ui` 主要承担 Control UI 的前端展示和浏览器侧交互。

不要手工维护非英文 locale bundle。`ui/AGENTS.md` 明确说外语 locale 和 `.i18n` 元数据通常是生成输出；默认应改 `ui/src/i18n/locales/en.ts` 和生成/注册管线，再通过同步命令再生。

不要只看 `ui/public` 就判断应用能力。`public` 里多是图标、manifest、service worker 等静态资源；业务界面和交互逻辑应在 `ui/src`，尤其是 `ui/src/main.ts` 与 `ui/src/ui`。

不要把 Markdown 渲染当成普通字符串拼接。依赖里存在 `dompurify`、高亮库和 Markdown 解析库，说明内容渲染可能涉及安全净化和格式扩展；追踪相关问题时应找完整渲染链路，而不是只改展示组件里的文本。

不要绕过目录自己的测试配置。`ui/package.json` 的默认测试脚本使用 `ui/vitest.config.ts`，另有 `ui/vitest.node.config.ts`。如果要验证 UI 改动，应优先沿用这些配置和仓库测试约定，而不是随意新增一套测试命令。
