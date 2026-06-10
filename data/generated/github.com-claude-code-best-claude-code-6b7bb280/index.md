# Claude Code Best 源码学习索引

这组文档面向第一次接触本仓库的中文读者，目标是先建立项目地图，再进入关键源码。内容依据仓库中的 `README.md`、`package.json`、`build.ts`、`vite.config.ts`、`scripts/defines.ts`、`src/entrypoints/cli.tsx`、`src/main.tsx`、`src/query.ts`、`src/QueryEngine.ts`、`src/tools.ts`、`src/Tool.ts`、`src/context.ts`、`src/state/*`、`packages/*/package.json` 等文件整理。仓库元信息中出现的外部地址在本文档中均不展开，统一视为 `[URL已移除]`。

## 推荐阅读顺序

1. [00-overview.md](00-overview.md) - 先了解项目要解决的问题、核心能力、主要模块，以及初学者最容易进入的切入点。
2. [01-tech-stack.md](01-tech-stack.md) - 再看运行环境、包管理、构建方式、TypeScript/React/Ink/Bun/MCP/API SDK 等技术信号。
3. [02-architecture.md](02-architecture.md) - 接着理解目录分层、模块边界、依赖方向和扩展点，避免一开始就陷入大文件细节。
4. [03-runtime-flow.md](03-runtime-flow.md) - 然后沿着启动、配置加载、REPL 输入、模型请求、工具调用、结果回流的路径读代码。
5. [04-reading-guide.md](04-reading-guide.md) - 最后按阶段下钻，区分 P0 必读、可后读、暂时可跳过的目录和文件。

## 后续最值得看的目录

- `src/entrypoints/`：CLI 启动入口、初始化逻辑、特殊运行模式分发。
- `src/main.tsx`：Commander 命令定义与主启动路径，是理解 CLI 表面能力的中心文件。
- `src/screens/REPL.tsx`：交互式终端界面的主组件，连接输入、状态、消息、权限、工具执行。
- `src/query.ts` 与 `src/QueryEngine.ts`：对话生命周期、流式消息、工具回合、压缩、预算、会话持久化的核心。
- `src/services/api/`：Anthropic SDK 请求、OpenAI/Gemini/Grok 等兼容层、错误与日志处理。
- `src/services/tools/` 与 `src/tools.ts`：工具池装配、权限过滤、并发/串行执行。
- `packages/builtin-tools/src/tools/`：文件、Shell、Web、Agent、任务、MCP 等内置工具的实际实现。
- `src/state/` 与 `src/bootstrap/state.ts`：React AppState 与会话级全局状态。
- `src/commands/`、`src/skills/`、`src/plugins/`：斜杠命令、技能和插件扩展面。
- `src/services/mcp/` 与 `packages/mcp-client/`：MCP 客户端连接、工具转换、资源与认证处理。
- `src/bridge/`、`src/services/acp/`、`packages/acp-link/`、`packages/remote-control-server/`：远程控制与 ACP 相关能力，建议在主循环理解后再读。

## 后续最值得看的文件

- `package.json`：确认 Bun 版本、workspace、scripts、依赖和发布入口。
- `scripts/defines.ts`：理解 `MACRO.*` 和默认 feature flags。
- `build.ts` 与 `vite.config.ts`：理解两套构建路径和产物形态。
- `src/entrypoints/cli.tsx`：所有快速路径与默认入口的第一站。
- `src/entrypoints/init.ts`：配置、遥测、代理、证书、Langfuse、Sentry、清理钩子的初始化。
- `src/main.tsx`：完整 CLI 命令树、主 action 和 REPL/headless 分发。
- `src/replLauncher.tsx`：从 CLI 进入 Ink App 与 `REPL` 的轻量桥。
- `src/Tool.ts`：工具接口、权限上下文、工具执行上下文的类型定义。
- `src/tools.ts`：内置工具注册、feature-gated 工具、MCP 工具合并。
- `src/context.ts`：系统上下文与用户上下文如何注入 git 状态、`CLAUDE.md` 和日期。
- `src/services/api/claude.ts`：模型请求参数、stream 事件处理、provider 分流。
- `src/services/tools/toolOrchestration.ts`：工具调用批处理、并发安全判断、串行执行策略。
- `src/utils/model/providers.ts`：API provider 选择优先级。
- `src/state/AppStateStore.ts`：交互 UI 的状态结构。
- `src/bootstrap/state.ts`：会话 ID、cwd、成本、token、模型等模块级状态。

阅读时建议先按调用链读，不要按目录字母序读。这个仓库有大量 feature gate、反编译残留和兼容路径；先掌握主干，之后再读远程控制、语音、Computer Use、ACP、插件市场等分支模块，会更容易判断哪些代码是核心路径，哪些代码是可选能力。
