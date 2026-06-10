# 技术栈与运行环境

## 运行时与语言

本项目的首要技术信号来自 `package.json`：`type` 是 `module`，`engines.bun` 要求 `>=1.3.0`，脚本主要通过 `bun run` 执行，`devDependencies` 中也包含 `@types/bun`。因此源码阅读时应默认它是 Bun-first 的 TypeScript/TSX 项目，而不是传统 Node.js CLI。`tsconfig.json` 使用 `target: ESNext`、`module: ESNext`、`moduleResolution: bundler`、`jsx: react-jsx`、`strict: true`、`noEmit: true`，并包含 `src/**/*.ts`、`src/**/*.tsx`、`packages/**/*.ts`、`packages/**/*.tsx`。这说明代码直接依赖现代 ESM、TS 严格类型和 TSX 组件编译。

需要注意的是，构建产物兼顾 Bun 和 Node。`build.ts` 使用 `Bun.build()`，入口是 `src/entrypoints/cli.tsx`，输出到 `dist/`，开启 `splitting: true`，并在构建后替换 Bun-only 的 `import.meta.require`，同时生成 `cli-bun.js` 和 `cli-node.js` 两个可执行入口。`package.json` 的 `bin` 字段也把 `ccb` 和 `claude-code-best` 指向 `dist/cli-node.js`，把 `ccb-bun` 指向 `dist/cli-bun.js`。所以运行时优先 Bun，但发布形态考虑了 Node 执行。

## 包管理与 monorepo

`package.json` 的 `workspaces` 包含 `packages/*`、`packages/@ant/*`、`packages/@anthropic-ai/*`。实际仓库中可见 `packages/builtin-tools`、`packages/agent-tools`、`packages/mcp-client`、`packages/acp-link`、`packages/remote-control-server`、`packages/weixin`，以及 `packages/@ant/ink`、`packages/@ant/model-provider`、`packages/@ant/computer-use-mcp`、`packages/@ant/computer-use-input`、`packages/@ant/computer-use-swift`、`packages/@ant/claude-for-chrome-mcp` 等。根 `tsconfig.json` 配置了 `src/*`、`@claude-code-best/builtin-tools/*`、`@claude-code-best/mcp-client/*`、`@claude-code-best/agent-tools/*`、`@claude-code-best/weixin/*` 的路径别名。

从 workspace 角色看，根 `src/` 是 CLI 应用主体；`packages/builtin-tools` 是工具实现包；`packages/@ant/ink` 是终端 UI 框架，包名导出为 `@anthropic/ink`；`packages/@ant/model-provider` 提供模型 provider 抽象；`packages/mcp-client` 提供 MCP 客户端辅助能力；`packages/acp-link` 是可执行的 ACP proxy server；`packages/remote-control-server` 是带 Web UI 的远程控制服务；本地能力由 `audio-capture-napi`、`image-processor-napi`、`color-diff-napi`、`modifiers-napi`、`url-handler-napi` 等包提供。初学者读源码时，应把 `packages/` 看成“可复用底座和扩展包”，不要把所有目录都当成同一层应用逻辑。

## 构建系统

项目有两条构建路径。第一条是 `bun run build`，实际执行 `build.ts`。该脚本清理 `dist/`，合并 `DEFAULT_BUILD_FEATURES` 和环境变量中的 `FEATURE_*`，调用 `Bun.build()` 做 code splitting，并注入 `getMacroDefines()` 返回的 `MACRO.VERSION`、`MACRO.BUILD_TIME` 等编译期常量。构建结束后，它会复制 `vendor/audio-capture` 和 `src/utils/vendor/ripgrep` 到 `dist/vendor/`，并写入 `cli-bun.js`、`cli-node.js`。

第二条是 `bun run build:vite`，由 `vite.config.ts` 描述。它是 SSR/Node 目标的 Rollup 构建，入口同样是 `src/entrypoints/cli.tsx`，输出 `dist/cli.js` 和 `chunks/[name]-[hash].js`。配置中有 `rawAssetPlugin` 用于把 `.md`、`.txt`、`.html`、`.css` 作为 raw string 加载，有 `featureFlagsPlugin()` 处理 feature gate，有 `importMetaRequirePlugin()` 兼容 `import.meta.require`。根据当前文件推断，Bun build 是主要发布路径，Vite build 是替代构建管线或用于更细粒度兼容验证。

## Feature flags 与编译期常量

`scripts/defines.ts` 是理解项目条件编译的关键文件。`getMacroDefines()` 从根 `package.json` 读取版本号，生成 `MACRO.VERSION` 等常量。`DEFAULT_BUILD_FEATURES` 列出默认启用的 feature，例如 `BUDDY`、`BRIDGE_MODE`、`VOICE_MODE`、`TOKEN_BUDGET`、`AGENT_TRIGGERS`、`ULTRATHINK`、`DAEMON`、`ACP`、`WORKFLOW_SCRIPTS`、`MONITOR_TOOL`、`KAIROS`、`COORDINATOR_MODE`、`BG_SESSIONS`、`TEMPLATES`、`POOR`、`SSH_REMOTE`、`AUTOFIX_PR` 等。

源码中通过 `import { feature } from 'bun:bundle'` 使用这些开关，常见模式是 `if (feature('ACP')) { ... }` 或条件 `require()`。例如 `src/entrypoints/cli.tsx` 中 ACP、Daemon、Bridge、Computer Use MCP 等快速路径受 feature 控制；`src/tools.ts` 中大量工具受 feature 或环境变量控制；`src/commands.ts` 中部分 slash command 动态加载。读代码时要特别留意：某段源码存在不代表运行时一定可用，它可能被 feature gate、环境变量、用户类型、权限规则或 settings 共同控制。

## UI 技术栈

交互式终端界面基于 React 19 与自定义 Ink。`package.json` 中有 `react`、`react-reconciler`、`react-compiler-runtime`；`packages/@ant/ink/package.json` 的包名是 `@anthropic/ink`，依赖 `chalk`、`figures`、`wrap-ansi`、`strip-ansi`、`supports-hyperlinks`、`get-east-asian-width` 等终端渲染相关库。`src/screens/REPL.tsx` 大量引入 `Box`、`Text`、`useInput`、`useTerminalTitle`、`useTheme` 等 Ink API；`src/components/` 下则是消息、输入框、权限弹窗、通知、主题、设计系统等 UI 组件。

这不是浏览器 UI，但仍使用 React 状态和组件模型。`src/state/AppState.tsx` 通过 `AppStateProvider` 创建 store，并用 `useSyncExternalStore` 实现选择器订阅。`src/components/App.tsx`、`src/replLauncher.tsx`、`src/screens/REPL.tsx` 共同组成 TUI 的挂载路径。读 UI 代码时要接受一个事实：组件文件里可能混合终端输入、异步请求、权限弹窗、背景任务和渲染逻辑，不能用常规 Web 页面组件的分层预期去套。

## API 与模型兼容层

根依赖中包含 `@anthropic-ai/sdk`、`@anthropic-ai/bedrock-sdk`、`@anthropic-ai/vertex-sdk`、`@anthropic-ai/foundry-sdk`、`openai`、`google-auth-library`、AWS SDK、Azure identity 等。`src/utils/model/providers.ts` 定义 provider 类型：`firstParty`、`bedrock`、`vertex`、`foundry`、`openai`、`gemini`、`grok`，选择优先级是 settings 中的 `modelType`，再看 `CLAUDE_CODE_USE_BEDROCK`、`CLAUDE_CODE_USE_VERTEX`、`CLAUDE_CODE_USE_FOUNDRY`、`CLAUDE_CODE_USE_OPENAI`、`CLAUDE_CODE_USE_GEMINI`、`CLAUDE_CODE_USE_GROK` 等环境变量，最后默认 `firstParty`。`src/services/api/client.ts` 创建 Anthropic SDK 客户端，并按 Bedrock、Foundry、Vertex 等环境分支返回不同 client；`src/services/api/claude.ts` 在请求层继续分流 OpenAI/Gemini/Grok 的流式适配。

因此读模型调用不要只看一个 SDK 调用点。真正链路是：settings/env 决定 provider，client 层处理认证、headers、代理、超时和云厂商客户端，`claude.ts` 层负责消息格式、工具 schema、betas、streaming/non-streaming、错误转换、usage/cost 记录和兼容层适配。

## 工具、MCP 与扩展概念

工具系统的类型在 `src/Tool.ts`，注册和过滤在 `src/tools.ts`，执行编排在 `src/services/tools/toolOrchestration.ts`，具体工具在 `packages/builtin-tools/src/tools/`。工具不是简单函数，而是带 `name`、schema、权限判断、并发安全判断、上下文修改、渲染进度、tool_result 生成等能力的结构。MCP 工具来自 `src/services/mcp/client.ts`，它使用 `@modelcontextprotocol/sdk` 的 stdio、SSE、streamable HTTP、WebSocket transport，与本地工具合并后发给模型。

Slash commands、skills、plugins 是另一组扩展概念。`src/commands.ts` 把内置命令、skills 目录、bundled skills、plugin commands、workflow commands、MCP skills 聚合为命令列表。`src/skills/bundled/index.ts` 注册随 CLI 发布的 skills。`src/plugins/bundled/index.ts` 目前注册微信内置插件。根据这些文件可以推断，项目把“用户手动输入的 `/command`”和“模型可调用的 skill prompt”都纳入同一个 command 体系，只是通过字段控制是否 immediate、是否 model-invocable、是否来自 plugin/MCP/bundled。

## 开发质量信号

根脚本提供 `bun run typecheck`、`bun test`、`bun run lint`、`bun run format`、`bun run health`、`bun run check:unused` 等命令。测试框架是 `bun:test`，仓库中有 `tests/integration/`、`tests/mocks/` 和各模块就近的 `__tests__`。`biome.json` 表示 lint/format 使用 Biome。`AGENTS.md` 强调 TypeScript strict 模式必须零错误，并提醒生产代码禁止随意 `as any`。这些信号说明，虽然项目来源包含逆向还原和大量 feature gate，但维护目标仍是可类型检查、可测试、可构建的工程项目。
