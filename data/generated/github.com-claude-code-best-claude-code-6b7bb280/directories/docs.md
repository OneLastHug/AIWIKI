# 目录：docs

## 它负责什么

根据当前片段推断，`docs` 是这个仓库的文档站内容目录，承载的是 Claude Code 的架构白皮书、功能说明、内部机制说明和一些设计/测试/任务类文档，而不是运行时业务代码本身。它更像“知识地图”而不是源码目录。

从 `docs.json` 和 `mint.json` 看，这里是一个 Mintlify 文档站：目录内容按主题分组，面向读者从“Claude Code 是什么”一路读到“对话如何运转、工具如何工作、上下文如何管理、多 Agent 如何协作、安全边界在哪里、隐藏功能和内部机制如何实现”。这说明 `docs` 的职责不是补充注释，而是把整个系统的主链路讲清楚。

## 直接子目录地图

`docs` 下的子目录按主题切得很清楚，可以把它理解成一张分层知识图。

- `docs/introduction`：总览入口，负责定义 Claude Code、说明整体架构和白皮书定位。
- `docs/conversation`：讲核心对话循环、流式输出、多轮交互。
- `docs/tools`：讲工具系统，覆盖文件、shell、搜索、任务管理等基础能力。
- `docs/context`：讲系统提示词、项目记忆、压缩和 token 预算。
- `docs/agent`：讲子 Agent、worktree 隔离、协调器与 swarm。
- `docs/extensibility`：讲 MCP、hooks、skills、自定义 agents 等扩展面。
- `docs/safety`：讲权限模型、sandbox、plan mode、auto mode 的安全边界。
- `docs/internals`：讲 feature flags、分层 gating、GrowthBook、Sentry、隐藏特性等内部机制。
- `docs/features`：讲具体能力和隐藏功能，范围很广，偏实现说明和能力说明。
- `docs/design`：设计类文档，偏界面/交互/方案说明。
- `docs/testing`：测试检查清单和测试规范相关。
- `docs/test-plans`：测试计划、验证基线。
- `docs/task`：任务型设计记录，适合追踪某个能力的拆解和演进。
- `docs/diagrams`：流程图、架构图等 Mermaid 图。
- `docs/images`、`docs/logo`：站点静态资源。
- `docs/auto-updater.md`、`docs/lsp-integration.md`、`docs/external-dependencies.md`、`docs/performance-reporter.md`、`docs/memory-*`、`docs/telemetry-*`：更偏横切能力、依赖和审计材料。

## 关键入口

最关键的站点入口是根部配置文件 `docs.json` 和 `mint.json`。它们定义了站点名、主题、导航分组、Logo、搜索、SEO、重定向和主页跳转。两份配置同时存在，**根据当前片段推断**它们在扮演相近甚至重叠的 Mintlify 配置角色，具体以实际启动命令读取哪一份为准。

内容入口上，最重要的是 `docs/introduction/what-is-claude-code.mdx`、`docs/introduction/architecture-overview.mdx` 和 `docs/introduction/why-this-whitepaper.mdx`。其中 `architecture-overview` 明确把源码主链路挂到了 `src/entrypoints/cli.tsx`、`src/main.tsx`、`src/screens/REPL.tsx`、`src/QueryEngine.ts`、`src/query.ts`、`src/tools.ts`、`src/services/api/claude.ts` 这些位置上。

另一个隐性入口是 `docs.json` 里的重定向：`/docs/introduction` 会跳到 `docs/introduction/what-is-claude-code`，说明“介绍页”就是这个目录最自然的第一落点。

## 主流程位置

如果把 `docs` 当成一条学习主线，它的主流程大致是：

1. 先从 `introduction` 建立认知，知道 Claude Code 是终端原生的 agentic coding system。
2. 再进 `conversation`，理解它如何形成“输入、响应、工具调用、继续循环”的交互闭环。
3. 接着读 `tools` 和 `context`，把“能做什么”与“凭什么能做”连起来。
4. 然后看 `agent` 与 `extensibility`，理解能力如何扩展到多 Agent、MCP、hooks、skills。
5. 最后看 `safety` 和 `internals`，补上权限、沙箱、feature flag、隐藏功能这些边界条件。

如果你是按“源码对应关系”去读，这个目录最核心的主流程实际上是在讲一条从入口到执行的链：`src/entrypoints/cli.tsx` -> `src/main.tsx` -> `src/screens/REPL.tsx` -> `src/QueryEngine.ts` -> `src/query.ts` -> `src/tools.ts` -> `src/services/api/claude.ts`。`docs/introduction/architecture-overview.mdx` 已经把这条链作为总纲写出来了。

## 推荐阅读顺序

- `docs/introduction/what-is-claude-code.mdx`
- `docs/introduction/architecture-overview.mdx`
- `docs/conversation/the-loop.mdx`
- `docs/tools/what-are-tools.mdx`
- `docs/context/system-prompt.mdx`
- `docs/agent/sub-agents.mdx`
- `docs/extensibility/mcp-protocol.mdx`
- `docs/safety/permission-model.mdx`
- `docs/internals/feature-flags.mdx`
- 再回头看 `docs/features/` 里的具体能力页

这个顺序的好处是先搭骨架，再补能力，再看边界，不容易把隐藏功能、实验功能和主流程混在一起。

## 常见误区

- 把 `docs` 当成代码实现目录。它主要是知识与设计说明，源码在 `src/` 和 `packages/`。
- 看到 `docs/features` 就以为里面每个功能都默认可用。实际上很多内容和 feature flag、隐藏能力、分层 gating 绑定，不能直接按“已启用功能清单”理解。
- 只看单页不看导航。这个目录是按主题编排的，脱离 `docs.json` / `mint.json` 很容易失去全局脉络。
- 把 `docs/introduction` 里的概念当成抽象介绍。这里其实和源码链路绑得很紧，经常直接指向 `src/main.tsx`、`src/query.ts` 这种主入口。
- 以为 `docs` 里只有面向用户的文档。实际上这里还混有设计记录、测试计划、审计材料和任务拆解，阅读时要先分清“说明文档”和“过程文档”。
