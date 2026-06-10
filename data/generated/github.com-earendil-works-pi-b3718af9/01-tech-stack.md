# 技术栈与运行环境

## Monorepo 与包管理信号

根目录 `package.json` 说明这是 npm workspaces monorepo：`workspaces` 包含 `packages/*` 以及若干 `packages/coding-agent/examples/extensions/...` 示例扩展。根包 `private: true`，`type: "module"`，版本字段为 `0.0.3`，但四个发布包在各自 `package.json` 中是 `0.79.1`。根脚本 `build` 按顺序进入 `packages/tui`、`packages/ai`、`packages/agent`、`packages/coding-agent` 构建，说明依赖方向至少在构建层是 `tui/ai/agent` 先于 `coding-agent`。根脚本 `check` 会运行 `biome check --write --error-on-warnings .`、依赖 pin 检查、TypeScript 相对 import 检查、coding-agent shrinkwrap 检查、`tsgo --noEmit` 和 browser smoke 检查。

根 `package.json` 的 `engines` 要求 `node >=22.19.0`。`tsconfig.base.json` 使用 `target: ES2022`、`module: Node16`、`moduleResolution: Node16`、`strict: true`、`erasableSyntaxOnly: true`、`allowImportingTsExtensions: true`、`rewriteRelativeImportExtensions: true`。这些信号很重要：源码里大量使用 `.ts` 扩展名 import，构建时会重写相对 import；同时 “erasable syntax only” 表示项目避免需要 TypeScript emit 才能运行的语法。`pi-test.sh` 使用 `node_modules/.bin/tsx --tsconfig tsconfig.json packages/coding-agent/src/cli.ts` 从源码直接启动 CLI，适合本地开发调试。

## TypeScript、ESM 与构建工具

所有主要包都是 `type: "module"`。包构建脚本大多使用 `tsgo -p tsconfig.build.json`，根依赖中 `@typescript/native-preview` 提供 `tsgo`。`packages/coding-agent/package.json` 的 `build` 先执行 `tsgo`，再复制 theme、assets、export-html 模板。它还有 `build:binary`，会先构建 `tui`、`ai`、`agent`、`coding-agent`，再用 `bun build --compile` 生成 `dist/pi`，说明 CLI 支持 Node 包安装和 Bun 编译二进制两种形态。`packages/coding-agent/src/config.ts` 中的 `isBunBinary`、`isBunRuntime`、`getPackageDir()`、`getThemesDir()`、`getExportTemplateDir()` 都是在处理 Node dist、tsx 源码和 Bun binary 三种资源路径差异。

格式与 lint 使用 Biome。`biome.json` 规定 formatter 使用 tab、lineWidth 120，linter 使用 recommended，并打开 `useConst`、关闭若干不适合当前项目的规则。测试方面，各包 package 脚本使用 `vitest --run` 或 Node test；根 `test.sh` 会临时移走 `~/.pi/agent/auth.json`、清空大量 provider API key 环境变量并运行 `npm test`，避免默认测试误打真实 provider。源码中还存在 `packages/coding-agent/test/suite/harness.ts` 和多条 issue 回归测试，说明核心行为大量靠测试固化。

## 运行时依赖与外部库

`packages/coding-agent` 依赖本仓库三个包：`@earendil-works/pi-agent-core`、`@earendil-works/pi-ai`、`@earendil-works/pi-tui`。外部依赖包括 `chalk`、`cross-spawn`、`diff`、`glob`、`highlight.js`、`ignore`、`jiti`、`minimatch`、`proper-lockfile`、`typebox`、`undici`、`yaml`、`@silvia-odwyer/photon-node`。从源码看，`jiti` 用于加载扩展，`proper-lockfile` 用于 settings/auth/trust 文件锁，`glob`、`ignore`、`minimatch` 用于包资源解析，`typebox` 用于工具参数 schema，`photon-node` 用于图片处理。

`packages/ai` 依赖各 provider SDK：`openai`、`@anthropic-ai/sdk`、`@google/genai`、`@mistralai/mistralai`、AWS Bedrock SDK 相关包、HTTP/HTTPS proxy agent、`partial-json`、`typebox`。但 provider 实现并不会在启动时全部加载；`packages/ai/src/providers/register-builtins.ts` 用 lazy import 包装具体 provider module，再通过 `registerApiProvider()` 注册统一 API 名称。这个设计减少启动成本，也允许 Bun binary 针对 Node-only provider 做特殊处理。

`packages/tui` 依赖 `get-east-asian-width` 和 `marked`，README 说明它支持 East Asian width、Markdown、inline images、组件化 UI、差分渲染和 synchronized output。`packages/tui/native` 下还有 Darwin 和 Win32 native modifier/console 相关预编译 `.node` 文件，说明终端输入/平台能力不是纯文本层面的简单 readline。

## 配置、认证与状态文件

`packages/coding-agent/src/config.ts` 规定默认配置目录来自包 `piConfig.configDir`，当前为 `.pi`；全局 agent 目录是 `~/.pi/agent`，也可通过环境变量 `PI_CODING_AGENT_DIR` 覆盖。session 目录默认在 `~/.pi/agent/sessions` 下按 cwd 编码，或由 `PI_CODING_AGENT_SESSION_DIR`、`--session-dir`、settings 中 `sessionDir` 指定。认证文件是 `auth.json`，模型配置是 `models.json`，设置是 `settings.json`，trust 决策是 `trust.json`。

`packages/coding-agent/src/core/settings-manager.ts` 说明 settings 有 global 与 project 两层：全局在 `agentDir/settings.json`，项目在 `cwd/.pi/settings.json`。`deepMergeSettings()` 合并时项目覆盖全局；如果项目未被 trust，project settings 为空。`packages/coding-agent/src/core/trust-manager.ts` 和 `project-trust.ts` 说明只要项目有 `.pi` 或祖先目录有 `.agents/skills` 等 trust 输入，就可能触发 trust 判断。非交互模式没有 UI 时，默认不会弹窗，而是按 `defaultProjectTrust` 或 CLI override 处理。

`packages/coding-agent/src/core/auth-storage.ts` 使用 `auth.json` 存储 API key 或 OAuth credential，文件写入权限为 `0o600`，并用 `proper-lockfile` 锁住并发刷新。它还支持 runtime API key override、环境变量 API key、fallback resolver。`packages/coding-agent/src/core/model-registry.ts` 会把 `authStorage`、`models.json` 中 provider config、OAuth provider、内置模型和扩展注册 provider 组合起来。

## LLM 与工具相关概念

读源码前需要先区分 `AgentMessage` 和 LLM `Message`。`packages/agent/README.md` 说明 agent 内部使用 `AgentMessage[]`，可以包含 UI-only 或自定义消息；在调用 LLM 前通过 `transformContext()` 和 `convertToLlm()` 转成 provider 能理解的 `Message[]`。`packages/coding-agent/src/core/messages.ts` 与 `AgentSession` 负责这个转换。这个设计解释了为什么 session 里可以保存 `custom_message`、`bashExecution`、`compactionSummary` 等不一定原样发给模型的内容。

工具使用 TypeBox schema。`packages/coding-agent/src/core/tools/read.ts` 的 `readSchema`、`bash.ts` 的 `bashSchema` 说明内置工具有结构化参数，并在 `packages/agent/src/agent-loop.ts` 中通过 `validateToolArguments()` 校验。工具调用事件流大致是 `tool_execution_start`、可选 `tool_execution_update`、`tool_execution_end`、`toolResult` message。`agent-loop.ts` 支持 parallel 或 sequential 工具执行；如果任何工具声明 sequential，整批工具就顺序执行。

## TUI 与交互概念

interactive mode 不是普通 stdout 打印。`packages/coding-agent/src/modes/interactive/interactive-mode.ts` 创建并管理 `TUI`、`ProcessTerminal`、`CustomEditor`、footer、selector、overlay、消息组件、工具组件、扩展 UI。`packages/tui/README.md` 说明每个组件实现 `render(width): string[]`，必要时实现 `handleInput()` 和 `invalidate()`；渲染层要求行宽不能超过给定 width。读交互代码时要把 “业务状态在 AgentSession” 与 “屏幕状态在 InteractiveMode/TUI 组件” 分开。

## 供应链和发布信号

根 README 的 supply-chain hardening 部分和脚本说明：直接外部依赖应 pin exact versions；`.npmrc` 和检查脚本控制 npm release age；`package-lock.json` 是依赖事实来源；发布 CLI 包含 `packages/coding-agent/npm-shrinkwrap.json`；发布前会有 local release smoke test。`scripts/generate-coding-agent-shrinkwrap.mjs`、`scripts/check-pinned-deps.mjs`、`scripts/release.mjs`、`scripts/local-release.mjs` 是维护发布质量的重要脚本。读功能代码时可以暂时跳过它们，但改依赖或发布流程必须回来读。

## 依据文件

本文依据 `package.json`、`tsconfig.json`、`tsconfig.base.json`、`biome.json`、`test.sh`、`pi-test.sh`、四个包的 `package.json`、`packages/coding-agent/src/config.ts`、`packages/coding-agent/src/core/settings-manager.ts`、`packages/coding-agent/src/core/auth-storage.ts`、`packages/coding-agent/src/core/model-registry.ts`、`packages/ai/src/providers/register-builtins.ts`、`packages/tui/README.md`。外部链接没有用于补充正文。
