# Pi Mono 源码阅读入口

这组文档面向第一次接触本仓库的读者。建议先把它当作一个 TypeScript monorepo 来看：根目录负责工作区、检查、发布和脚本编排；真正的产品能力集中在 `packages/coding-agent`、`packages/agent`、`packages/ai`、`packages/tui` 四个包。仓库 README 将项目描述为 “Pi Agent Harness Mono Repo”，其中 `@earendil-works/pi-coding-agent` 是交互式 coding agent CLI，`@earendil-works/pi-agent-core` 是 agent runtime，`@earendil-works/pi-ai` 是多 provider LLM API，`@earendil-works/pi-tui` 是终端 UI 库。文档中的路径均来自当前仓库文件；外部链接已省略或脱敏为 `[URL已移除]`。

## 推荐阅读顺序

1. [00-overview.md](00-overview.md)：先理解项目解决什么问题、四个核心包各自负责什么，以及初学者应该从哪里进。
2. [01-tech-stack.md](01-tech-stack.md)：再看技术栈、运行环境、构建脚本、包管理和源码阅读前需要知道的概念。
3. [02-architecture.md](02-architecture.md)：接着看目录分层、模块边界、依赖方向、扩展点和存储边界。
4. [03-runtime-flow.md](03-runtime-flow.md)：然后跟启动、配置加载、会话创建、LLM 请求、工具调用和模式层输出的运行链路。
5. [04-reading-guide.md](04-reading-guide.md)：最后按入口、核心模块、可后读模块、可跳过模块继续下钻。

## 后续最值得看的目录

- `packages/coding-agent/src`：CLI 产品层，包含 `cli.ts`、`main.ts`、`core`、`modes`、`utils`，是理解 pi 命令实际行为的首选入口。
- `packages/coding-agent/src/core`：会话、配置、模型、资源、扩展、工具、系统 prompt、compaction 都在这里汇合。
- `packages/coding-agent/src/modes`：同一个 `AgentSessionRuntime` 被包装成 interactive、print/json、rpc 三种外部交互模式。
- `packages/agent/src`：底层 agent loop，负责事件流、消息队列、工具执行和公开 harness。
- `packages/ai/src`：provider registry、模型类型、stream/complete API、内置 provider、OAuth 和模型元数据。
- `packages/tui/src`：交互式终端 UI 的组件、渲染、输入、keybindings、markdown、image 支持。
- `packages/coding-agent/docs`：用户功能文档，适合把源码里的设置、sessions、extensions、skills、RPC 与对外行为对应起来。
- `packages/coding-agent/test`、`packages/agent/test`、`packages/ai/test`、`packages/tui/test`：回归和行为样例。读不懂实现时，先找同名测试。

## 后续最值得看的文件

- `package.json`：monorepo、Node 版本、构建/检查/发布脚本的总开关。
- `tsconfig.json`、`tsconfig.base.json`、`biome.json`：解释源码的 TypeScript 约束、路径别名和格式规则。
- `README.md`、`packages/coding-agent/README.md`：说明项目定位、包职责、交互模式、session、settings、trust、扩展能力。
- `packages/coding-agent/src/cli.ts`、`packages/coding-agent/src/main.ts`：`pi` CLI 的真实启动入口。
- `packages/coding-agent/src/core/sdk.ts`：CLI 与 SDK 共同使用的会话创建工厂。
- `packages/coding-agent/src/core/agent-session.ts`：coding agent 产品层的核心状态机。
- `packages/agent/src/agent-loop.ts`：最小运行循环，适合理解 LLM 响应、工具调用、toolResult 和下一轮的关系。
- `packages/ai/src/stream.ts`、`packages/ai/src/api-registry.ts`：理解模型请求如何从统一 API 分派到 provider。
- `packages/tui/src/tui.ts`、`packages/tui/src/components/editor.ts`：理解 interactive mode 的显示和输入基础。

## 阅读提醒

这个仓库不是只有一个 `src` 的单包项目，而是以包边界组织能力。不要从 generated model 文件或 provider 细节开始；先建立 “CLI 产品层调用 core session，core session 调用 agent loop，agent loop 调用 pi-ai stream，interactive mode 只是其中一种 I/O 壳” 的主线。`critical_paths.json` 只列架构种子路径，不穷举所有源码。
