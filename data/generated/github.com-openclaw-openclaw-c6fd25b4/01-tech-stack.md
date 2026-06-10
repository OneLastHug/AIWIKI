# 技术栈与运行环境

本页解释 OpenClaw 仓库的技术栈信号、构建/包管理方式和读源码前需要知道的概念。依据主要来自 `package.json`、`pnpm-workspace.yaml`、`openclaw.mjs`、`src/entry.ts`、`ui/package.json`、`apps/**` 和根 README。仓库元数据里包含真实主页、仓库和文档链接，本文统一不输出真实网址。

## Node、TypeScript 与 ESM

根 `package.json` 写明 `"type": "module"`，`main` 指向 `dist/index.js`，`bin.openclaw` 指向 `openclaw.mjs`，`engines.node` 要求 `>=22.19.0`。`openclaw.mjs` 顶部也有 Node 版本检查：低于 22.19 会输出错误并退出。README 进一步说明 Node 24 recommended、Node 22.19+ supported。因此读者应把这个项目理解为现代 Node ESM 项目，不是 CommonJS 项目。

源码主体是 TypeScript。证据包括 `src/**/*.ts`、`tsconfig.core.json`、`tsconfig.projects.json`、`tsconfig.plugin-sdk.dts.json`、`tsx`、`typescript`、`@typescript/native-preview`、`tsdown`、大量 `tsgo:*` 脚本。开发时 `pnpm openclaw ...` 通过 `scripts/run-node.mjs` 直接运行 TypeScript；构建时 `pnpm build` 走 `scripts/build-all.mjs`，再由 `tsdown`、runtime postbuild、plugin SDK d.ts、build stamp 等脚本生成 `dist/`。这是从 `README.md` 的 From source 段落和 `package.json` scripts 推断出的常规流程。

## 包管理和 workspace

仓库使用 `pnpm`。`package.json` 有 `packageManager: pnpm@11.2.2...`，`pnpm-workspace.yaml` 声明 packages 包括根包、`ui`、`packages/*`、`extensions/*`。根 README 也明确说明 source checkout 使用 `pnpm`，根目录不支持普通 `npm install` 作为源码开发方式。`pnpm-workspace.yaml` 还配置了 `nodeLinker: hoisted`、`minimumReleaseAge`、`overrides`、`allowBuilds`、`patchedDependencies` 等安全和依赖控制策略。

这意味着读源码时不要只看根 `dependencies`。许多插件在 `extensions/<id>/package.json` 有自己的依赖、构建配置和 shrinkwrap，例如某些插件有 `npm-shrinkwrap.json`。共享包在 `packages/**` 下，例如 `packages/plugin-sdk`、`packages/plugin-package-contract`、`packages/memory-host-sdk`。Control UI 是 `ui` 子包，有自己的 `package.json` 和 Vite/Vitest 脚本。

## 核心依赖信号

根依赖中，`commander` 说明 CLI 命令框架；`express`、`ws`、`undici`、`ipaddr.js` 与 Gateway HTTP/WebSocket/网络请求有关；`zod`、`typebox`、`ajv`、`json5`、`yaml` 与配置、schema、协议校验有关；`openai`、`@google/genai`、`@agentclientprotocol/sdk`、`@modelcontextprotocol/sdk` 与模型、ACP、MCP 能力有关；`grammy` 和 `@grammyjs/*` 表明 Telegram 或 bot runner 相关能力存在；`kysely`、`sqlite-vec` 相关依赖在 lock/workspace 信号中出现，说明部分存储/检索能力可能涉及数据库或向量能力；`playwright-core`、`pdfjs-dist`、`@mozilla/readability`、`linkedom`、`markdown-it`、`tree-sitter-bash`、`rastermill` 说明浏览器、文档解析、媒体/渲染和代码/命令分析能力是项目的一部分。

需要注意：依赖只能说明能力可能存在，具体行为必须回到源码。比如 `express` 不等于所有 HTTP 路由都由 Express 定义，Gateway 里还存在原生 HTTP server、WebSocket upgrade、plugin route registry 等代码。`openai` 依赖也不代表模型调用只走 OpenAI；`extensions/**` 下有大量 provider 插件，`src/agents/model-selection.ts`、`src/model-catalog/**`、`src/provider-runtime/**` 才是理解模型路由的关键。

## UI 与 App 技术栈

`ui/package.json` 显示 Control UI 使用 Vite、Lit、Vitest、Playwright browser test、DOMPurify、Markdown 渲染相关包。根脚本里有 `ui:build`、`ui:dev`、`ui:i18n:*`、`test:ui`、`test:ui:e2e`。Gateway 侧有 `src/gateway/control-ui.ts`、`src/gateway/control-ui-routing.ts`、`src/gateway/control-ui-csp.ts`，说明 UI 不是独立无关应用，而是被 Gateway 作为控制面资源或路由的一部分服务。

`apps/macos/Package.swift`、`apps/ios/project.yml` 和大量 Swift 文件说明 macOS/iOS 使用 Swift/SwiftUI/XcodeGen 风格工程；`apps/android/build.gradle.kts`、`settings.gradle.kts`、Android README 说明 Android 使用 Gradle/Kotlin 构建。根 `package.json` 有 `mac:*`、`ios:*`、`android:*` 脚本。初学核心后再看这些 app，因为它们依赖 Gateway protocol、device pairing、node registry、canvas/voice/talk 等基础概念。

## 构建、测试和质量工具

根脚本数量很多，但可以按类别理解。构建类包括 `build`、`build:docker`、`build:strict-smoke`、`build:plugin-sdk:dts`、`ui:build`、`plugins:assets:*`。测试类包括 `test:unit`、`test:gateway`、`test:extensions`、`test:e2e`、`test:live`、`test:docker:*`、`test:ui`。类型检查类包括 `tsgo:*` 和 `check:test-types`，仓库规则也强调使用 `tsgo` lanes。格式和 lint 使用 `oxfmt`、`oxlint`，文档有 `docs:list`、`docs:check-mdx`、`docs:check-links`、`format:docs:check`、`lint:docs`。

本次环境中 `pnpm` 不在 PATH，`pnpm docs:list` 无法执行，因此本文没有依赖命令输出，而是读取静态文件。读者在正常开发环境中应以仓库脚本为准，不要把本页当作测试命令替代品。

## 读源码前的关键概念

第一个概念是 Gateway。Gateway 是本地运行的控制面，它提供 HTTP/WebSocket、Control UI、RPC/method registry、channel/node/plugin 接入、session event broadcast、配置热重载和后台任务。入口文件是 `src/gateway/server.ts`，实现主体是 `src/gateway/server.impl.ts`。

第二个概念是 agent。agent 不是单个函数，而是会话、模型、provider、auth profile、workspace、skills、tools、sandbox、ACP runtime、delivery policy 的组合。`src/agents/agent-command.ts` 是一次 agent run 的核心聚合点。

第三个概念是 channel。channel 表示 Telegram/Slack/Discord/WhatsApp 等消息入口或出口的抽象。`src/channels/**` 提供通用策略和 contract，真实平台多由 `extensions/**` 插件实现。DM 配对、allowlist、group policy、message ack、thread binding 都属于这一层。

第四个概念是 plugin。插件通过 `openclaw.plugin.json` 和 SDK 注册 provider、channel、tool、HTTP route、gateway method、node capability 等能力。Core 通过 `src/plugins/**`、`src/gateway/server-startup-plugins.ts`、`src/gateway/server-plugin-bootstrap.ts` 加载和绑定插件。

第五个概念是配置与运行快照。`src/config/**` 负责 config IO、paths、validation、runtime snapshot、mutation 和 recovery。Gateway 启动会先读配置快照，再准备 auth/secrets/runtime config，并把配置放入 runtime snapshot。配置变更会影响插件、channel、auth、cron、hooks 等运行面，因此源码里存在大量 config reload 和 compatibility 测试。

第六个概念是 protocol/method。`src/gateway/protocol/**` 定义 Gateway 协议 schema，`src/gateway/methods/registry.ts` 把 core 和 plugin gateway method 变成带 scope 的 registry。WebSocket 连接通过 `src/gateway/server-ws-runtime.ts` 和 `src/gateway/server/ws-connection.ts` 接入请求上下文。

第七个概念是 lazy loading。`src/entry.ts`、`src/cli/gateway-cli/register.ts`、`src/agents/agent-command.ts`、`src/gateway/server.ts` 大量使用动态导入或 `createLazyImportLoader`。这说明启动性能和模块边界是设计重点，读调用链时要习惯“入口文件只是薄包装，真正实现稍后导入”。
