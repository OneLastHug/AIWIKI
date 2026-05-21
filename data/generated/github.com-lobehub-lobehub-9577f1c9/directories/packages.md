# 目录：packages

## 它负责什么

`packages` 是这个仓库的 workspace 包集合，承担“可复用基础能力层”的角色。主应用代码在 `src/`、桌面端在 `apps/desktop/`，而 `packages/*` 把跨端、跨服务、跨功能域会重复使用的能力拆成独立包，通过 `@lobechat/*` 或少数特殊包名被主应用引用。

从根 `package.json` 看，workspace 范围包含 `packages/*`、`packages/business/*`、`e2e`、`apps/desktop/src/main`。也就是说，`packages` 既是普通共享包目录，也是 monorepo 内部依赖解析的核心来源。这里的包覆盖模型运行时、数据库、内置工具、Agent 能力、桌面 IPC、聊天平台适配、文件解析、观测、类型、常量和通用工具等。

## 关键组成

`packages` 下面的包数量很多，适合按职责分组阅读：

1. **模型与 Provider 层**

   `model-runtime` 是模型调用运行时，入口 `packages/model-runtime/src/index.ts` 导出 `ModelRuntime`、`BaseAI`、`RouterRuntime`、OpenAI 兼容工厂、各家 provider runtime，例如 `LobeOpenAI`、`LobeAnthropicAI`、`LobeGoogleAI`、`LobeDeepSeekAI` 等。它更偏“怎么调用模型”。

   `model-bank` 保存模型和 provider 的静态定义，目录里有 `src/aiModels/*` 与 `src/modelProviders/*`。它更偏“有哪些模型、哪些供应商、每个供应商的元信息是什么”。

   `business/model-runtime`、`business/model-bank` 是商业/云版本覆盖或扩展区域，根据当前片段推断，它们与开源包形成同名能力的业务差异层。

2. **数据库层**

   `database` 是服务端数据访问核心包。`packages/database/src/index.ts` 导出 `core/db-adaptor`、`repositories/compression`、`idGenerator` 等；`packages/database/src/schemas/index.ts` 汇总导出大量 Drizzle schema，例如 `agent`、`message`、`topic`、`user`、`rag`、`aiInfra`、`task`、`userMemories`。目录结构还包含 `models`、`repositories`、`migrations`、`tests`，说明它不仅定义表结构，也封装仓储查询和迁移。

3. **Agent 与工具层**

   `agent-runtime`、`agent-manager-runtime`、`agent-signal`、`agent-tracing`、`agent-templates`、`agent-mock` 提供 Agent 执行、管理、信号、追踪、模板和测试模拟能力。

   `builtin-tool-*` 是一组内置工具包，例如 `builtin-tool-web-browsing`、`builtin-tool-memory`、`builtin-tool-knowledge-base`、`builtin-tool-cloud-sandbox`、`builtin-tool-agent-builder`、`builtin-tool-message` 等。每个工具通常有自己的 `manifest`、`client`、`executor`、`executionRuntime` 导出。

   `builtin-tools` 是聚合注册表。`packages/builtin-tools/src/index.ts` 导入各个 `builtin-tool-*` 的 `Manifest`，再导出 `defaultToolIds`、`alwaysOnToolIds`、`chatModeAllowedToolIds`、`runtimeManagedToolIds` 和 `builtinTools`。这说明单个工具包负责实现，`builtin-tools` 负责集中声明“哪些工具存在、默认启用哪些、哪些由运行时控制”。

4. **跨端和桌面层**

   `desktop-bridge`、`electron-client-ipc`、`electron-server-ipc`、`local-file-shell`、`device-gateway-client`、`agent-gateway-client` 服务桌面端、本地文件、设备网关和 Agent Gateway 通信。`apps/desktop` 会消费这些包。

5. **平台适配和辅助能力**

   `chat-adapter-feishu`、`chat-adapter-line`、`chat-adapter-qq`、`chat-adapter-wechat` 是聊天平台适配器。`file-loaders`、`web-crawler`、`fetch-sse`、`ssrf-safe-fetch`、`python-interpreter`、`markdown-patch` 提供文件、网页、流式请求、安全 fetch、Python 执行和 Markdown 修改等基础能力。

6. **公共类型、常量、配置、UI**

   `types` 定义跨包共享类型；`const` 提供常量并有 `currency`、`desktopGlobalShortcuts`、`hotkeys` 等子导出；`config` 提供默认配置；`utils` 提供通用工具并区分 `server`、`client`、`object` 等子路径；`shared-tool-ui` 为工具渲染、检查器等提供共享 UI。

## 上下游关系

`packages` 的上游主要是外部 npm 依赖、数据库、模型供应商 API、桌面系统 API、聊天平台 API。它自身被 `src/`、`apps/desktop/`、各个 package 之间互相引用。

典型依赖关系是：

- `src/app/(backend)`、`src/server` 调用 `@lobechat/database`、`@lobechat/model-runtime`、`@lobechat/utils/server`。
- SPA 页面和 feature 调用 `@lobechat/types`、`@lobechat/const`、`@lobechat/builtin-tools` 等共享定义。
- `builtin-tools` 聚合 `builtin-tool-*`，而每个工具包又依赖 `@lobechat/types` 中的 `BuiltinToolManifest`、`BaseExecutor`、`BuiltinInspectorProps` 等类型和基类。
- `database` 的 schema 和 repository 使用 `@lobechat/types` 表达业务数据结构，也使用 `@lobechat/utils` 做对象清理等通用处理。
- `model-runtime` 与 `model-bank` 分工协作：前者执行请求，后者提供模型清单和 provider 元数据。

## 运行/调用流程

一个常见聊天请求链路可以这样理解：前端或服务端业务代码先读取用户配置、provider 配置和模型信息；模型相关信息来自 `model-bank`，实际发起模型调用由 `model-runtime` 的 `ModelRuntime` 或具体 `LobeXXXAI` provider 完成。请求过程中若需要工具，系统通过 `builtin-tools` 获得内置工具列表、默认工具、运行时管理工具，再按工具 manifest 找到对应 `builtin-tool-*` 的 executor 或 execution runtime 执行。

如果流程涉及持久化，服务端会经由 `@lobechat/database` 访问 schema、model 或 repository，把会话、消息、知识库、任务、用户设置等写入 PostgreSQL。桌面端场景则会额外经过 `desktop-bridge`、`electron-client-ipc`、`electron-server-ipc` 或 `local-file-shell` 访问本地能力。

## 小白阅读顺序

建议先从根 `package.json` 的 `workspaces` 和 `dependencies` 看起，确认 `packages/*` 如何被 monorepo 管理。然后读 `packages/types`、`packages/const`、`packages/utils`，因为很多包都依赖这些基础定义。

第二步看 `packages/model-bank` 和 `packages/model-runtime`：一个定义模型，一个执行模型调用，是理解 AI 供应商接入的主线。第三步看 `packages/database/src/schemas/index.ts` 与 `packages/database/src/repositories`，理解数据结构和服务端访问方式。

第四步读 `packages/builtin-tools/src/index.ts`，再挑一个具体 `builtin-tool-*`，例如 `builtin-tool-web-browsing` 或 `builtin-tool-memory`，观察 manifest、client、executor、executionRuntime 如何拆分。最后再按兴趣阅读 `agent-runtime`、`agent-signal`、`agent-tracing` 和桌面/聊天平台适配包。

## 常见误区

1. **不要把 `packages` 当成单一业务模块。** 它是共享能力集合，不是一个按页面组织的功能目录。

2. **不要只看 `builtin-tool-*` 而忽略 `builtin-tools`。** 单个工具包定义能力，`builtin-tools` 决定聚合、默认启用、聊天模式白名单和运行时托管规则。

3. **不要混淆 `model-bank` 和 `model-runtime`。** `model-bank` 偏静态模型元数据，`model-runtime` 偏真实调用和流式处理。

4. **不要绕过 `database` 的 repository/model 直接散落写 SQL。** 这个包已经承担 schema、model、repository、migration 的边界职责。

5. **不要假设所有包都只服务 Web。** `desktop-bridge`、`electron-*`、`local-file-shell`、`device-gateway-client` 明确服务桌面、本地和设备场景。

6. **不要忽略 `packages/business/*`。** 根 workspace 明确包含它们，根据当前片段推断，它们用于商业或云端能力覆盖，阅读同名能力时要同时留意业务扩展包。
