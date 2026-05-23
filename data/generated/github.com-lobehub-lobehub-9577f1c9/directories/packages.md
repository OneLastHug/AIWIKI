# 目录：packages

## 它负责什么

`packages` 是这个仓库里最核心的 monorepo 工作区之一，承载大量可复用的基础能力包。根据当前片段推断，它不是单一业务模块，而是一组围绕“模型、Agent、工具、数据库、基础类型、跨端桥接、云端覆盖层”组织起来的共享包集合。

这层目录的职责可以概括为三类：

1. 提供底层能力，例如 `@lobechat/database`、`@lobechat/model-runtime`、`@lobechat/utils`。
2. 提供可组装的 Agent 与工具生态，例如 `@lobechat/agent-runtime`、`@lobechat/builtin-tools`、大量 `packages/builtin-tool-*`。
3. 提供云端或产品差异化覆盖，例如 `packages/business`，它看起来是对开源核心能力的云端扩展或替换层。

从仓库根的 workspace 配置看，`packages/*` 是直接被纳入构建和依赖解析的主工作区之一，说明这里的包不是孤立存放，而是整个应用和服务端代码的共同供应层。

## 直接子目录地图

下面按角色分组看，不逐个叶子包展开。

- `packages/agent-*`：Agent 运行时与配套能力，包括 `agent-runtime`、`agent-signal`、`agent-tracing`、`agent-manager-runtime`、`agent-gateway-client`、`agent-mock`、`agent-templates`。
- `packages/builtin-tool-*`、`packages/builtin-tools`、`packages/builtin-agents`、`packages/builtin-skills`：内置工具、内置 Agent、技能与注册表。这里明显是“可插拔能力层”。
- `packages/database`：数据库模型、schema、repository、migration、测试工具，是持久化主干。
- `packages/model-runtime`、`packages/model-bank`、`packages/prompts`、`packages/context-engine`、`packages/conversation-flow`：模型调用、模型目录、提示词、上下文编排与会话流。
- `packages/utils`、`packages/types`、`packages/const`、`packages/config`、`packages/edge-config`：基础类型、常量、通用工具和配置。
- `packages/business`：云端覆盖包，目录下可见 `config`、`const`、`model-bank`、`model-runtime`，这很像对开源核心包的定制层。
- `packages/chat-adapter-*`：对接外部聊天平台的适配器，例如飞书、Line、QQ、微信。
- `packages/desktop-bridge`、`packages/electron-client-ipc`、`packages/electron-server-ipc`、`packages/device-gateway-client`：桌面端和设备网关相关桥接层。
- `packages/file-loaders`、`packages/local-file-shell`、`packages/web-crawler`、`packages/ssrf-safe-fetch`、`packages/python-interpreter`：文件、网络、执行环境与安全访问相关能力。
- `packages/observability-otel`、`packages/openapi`、`packages/eval-*`、`packages/memory-user-memory`、`packages/shared-tool-ui`：可观测、接口定义、评测、记忆与共享 UI 组件。

## 关键入口

最值得先看的入口，不是每个包的内部实现，而是各包对外暴露的 `src/index.ts` 与少量多入口导出。

- `packages/database/package.json` 里导出了 `./src/index.ts`、`./src/schemas/index.ts`、`./tests/test-utils.ts`，说明数据库包不只提供主入口，还显式暴露 schema 与测试辅助。
- `packages/model-runtime/package.json` 导出 `./src/index.ts` 和 `./src/providers/vertexai/index.ts`，说明它是统一 runtime 入口加少量 provider 子入口的结构。
- `packages/builtin-tools/package.json` 将 `src/index.ts` 作为主入口，同时导出 `renders.ts`、`inspectors.ts`、`interventions.ts`、`placeholders.ts`、`portals.ts`、`streamings.ts`、`identifiers.ts`、`dynamicInterventionAudits.ts`，这是一个明显的“注册中心”型包。
- `packages/utils/package.json` 导出 `src/index.ts`，并额外提供 `src/server/index.ts`、`src/client/index.ts` 和通配子路径，说明它是通用工具底座。
- `packages/agent-runtime/package.json` 以 `src/index.ts` 为主入口，表明 Agent 运行时的公共 API 也被集中封装。

## 主流程位置

如果只看 `packages` 目录里的“主流程”，优先关注这些位置：

- 数据持久化主流程：`packages/database/src/schemas`、`packages/database/src/models`、`packages/database/src/repositories`，以及 `packages/database/migrations`。
- 模型调用主流程：`packages/model-runtime/src/core`、`packages/model-runtime/src/providers`、`packages/model-runtime/src/helpers`。
- Agent 编排主流程：`packages/agent-runtime/src/core`、`packages/agent-runtime/src/agents`、`packages/agent-runtime/src/groupOrchestration`、`packages/agent-runtime/src/audit`。
- 工具注册与分发主流程：`packages/builtin-tools/src` 下的一组 registry 文件，以及各个 `packages/builtin-tool-*` 的 `src`。
- 云端差异化主流程：`packages/business/config/src`、`packages/business/const/src`、`packages/business/model-bank/src`、`packages/business/model-runtime/src`。

把它们串起来看，这个目录更像“平台能力层”而不是业务页面层。上层应用通常会通过这些包完成“模型选择、上下文组织、工具调用、数据库读写、跨端桥接”的整条链路。

## 推荐阅读顺序

1. 先看 `packages/database`，因为它最接近真实数据结构和持久化边界。
2. 再看 `packages/model-runtime`，理解模型请求如何被抽象成统一 runtime。
3. 然后看 `packages/agent-runtime`，把 Agent 执行和编排流程串起来。
4. 接着看 `packages/builtin-tools` 与若干 `packages/builtin-tool-*`，理解工具注册、渲染和干预机制。
5. 最后看 `packages/business`，确认云端覆盖层与开源核心包之间的分工。

## 常见误区

- 不要把 `packages` 当成单个库，它是多个 workspace 包的集合。
- 不要默认 `package.json` 里的 `main` 就是唯一入口，很多包实际还通过 `exports` 暴露多个子路径。
- 不要把 `packages/business` 视为普通公共包；根据当前片段推断，它更像云端定制覆盖层，和核心开源包的角色不同。
- 不要在读数据库相关逻辑时忽略 `migrations`，schema 变化通常会牵连迁移文件和测试工具。
- 不要把 `builtin-tool-*` 理解成杂乱散包，它们更像按能力域拆分后的工具插件集合，主入口通常由 `packages/builtin-tools` 统一汇总。
