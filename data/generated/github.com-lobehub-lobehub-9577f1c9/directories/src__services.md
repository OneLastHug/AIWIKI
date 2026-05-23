# 目录：src/services

## 它负责什么

`src/services` 是前端侧的“服务层”目录，核心职责是把页面、store、交互逻辑和后端 `lambdaClient` / 流式接口连接起来。根据当前片段推断，这里不是数据库访问层，也不是纯工具库，而是面向业务动作的客户端服务封装：例如创建聊天流、获取模型/用户/插件数据、提交文档历史、处理导入导出、刷新缓存等。

它的典型特点有两个：

1. 大多数实现直接调用 `@/libs/trpc/client` 下的 `lambdaClient`，说明它主要是对 tRPC 接口的前端封装。
2. 少数模块会再叠加本地状态、请求取消、缓存失效、流式连接等横切能力，例如 `chat`、`document`、`agentRuntime`、`utils/abortableRequest`。

整体上，`src/services` 是页面与服务端之间的一层“业务 API 适配器”。

## 直接子目录地图

这个目录下面主要是按业务域拆分的子目录，不是单一的大文件堆叠。

- `src/services/chat/`：聊天主链路，包含 `index.ts`、`helper.ts`、`mecha/`、`types.ts`、测试文件；这是最核心的目录之一。
- `src/services/agentRuntime/`：异步 agent 运行时相关，包含 `client.ts`、`index.ts`、`type.ts` 和测试。
- `src/services/document/`：文档读取、历史版本、失效刷新相关，包含 `index.ts`、`invalidation.ts`、`swrKeys.ts`。
- `src/services/userMemory/`：用户记忆的 CRUD 与抽取，包含 `crud.ts`、`extraction.ts`、`index.ts`。
- `src/services/electron/`：桌面端能力封装，围绕更新、系统、开发者工具、本地文件、远程服务等。
- `src/services/tableViewer/`：表格查看器相关，既有服务入口也有 client 适配。
- `src/services/home/`、`plugin/`、`session/`、`thread/`、`topic/`、`message/`、`user/`、`file/`、`import/`、`export/`、`aiProvider/`、`aiModel/`、`recent/`、`resource/`、`skill/`、`chatGroup/`、`onboardingFeedback/`、`onboardingMetrics/`：这些更像是单域服务入口，通常以 `index.ts` 为主。
- `src/services/utils/`：通用请求工具，目前能看到 `abortableRequest.ts`。
- 根层杂项文件如 `_auth.ts`、`_url.ts`、`_header.ts`、`config.ts`、`global.ts`、`trace.ts`、`debug.ts`、`search.ts`、`upload.ts`、`generation.ts`、`message.ts`、`task.ts`、`social.ts`、`webBrowsing.ts` 等，属于横向能力或独立服务入口。

## 关键入口

最值得先看的入口是这些：

- `src/services/chat/index.ts`：聊天生成和消息流的总入口，串起 agent 配置、模型参数、工具、记忆、搜索、trace、headers 和 SSE 请求。
- `src/services/chat/mecha/index.ts`：聊天执行的核心子模块聚合层，集中导出配置解析、上下文工程、模型参数、记忆管理、工具组装。
- `src/services/agentRuntime/client.ts`：agent 运行时的 SSE 连接客户端，直接连到 `/api/agent/stream`。
- `src/services/agentRuntime/index.ts`：对外暴露 `agentRuntimeClient` 和 `handleHumanIntervention`。
- `src/services/document/index.ts`：文档创建、查询、历史记录、版本比较、更新等入口。
- `src/services/document/invalidation.ts`：文档相关 SWR 缓存失效的统一入口。
- `src/services/user/index.ts`：用户状态、 onboarding、偏好和设置相关入口。
- `src/services/aiProvider/index.ts`、`plugin/index.ts`、`home/index.ts`、`export/index.ts`：分别对应模型供应商、插件、首页、导出数据等业务能力。

## 主流程位置

如果只看主流程，建议把 `src/services` 理解成一条从 UI 到后端的业务调用链：

`页面/Store -> 服务层 -> lambdaClient/TRPC -> 服务端路由`

其中最复杂的是聊天链路：

- `src/services/chat/index.ts` 负责组装聊天请求；
- 它会借助 `src/services/chat/mecha/` 里的能力先解析 agent 配置、工具、上下文、记忆和模型扩展参数；
- `src/services/chat/helper.ts` 会从 `aiInfra` store 读取模型能力和 provider 配置，用来判断 vision/video、部署名、客户端直连能力；
- 请求过程中还会用到 `src/services/_auth.ts`、`src/services/_url.ts`、`src/services/trace.ts` 之类的基础设施。

文档链路也很典型：

- `src/services/document/index.ts` 负责文档和历史版本读写；
- `src/services/utils/abortableRequest.ts` 提供按 key 取消旧请求的能力；
- `src/services/document/invalidation.ts` 统一刷新 `documentSWRKeys`、`agentDocumentSWRKeys`、`notebookSWRKeys` 对应缓存，避免编辑态和列表态不同步。

agent 运行时则是另一条主线：

- `src/services/agentRuntime/client.ts` 负责长连接流；
- `src/services/agentRuntime/index.ts` 负责把人类介入动作回写到 `lambdaClient.aiAgent.processHumanIntervention`。

## 推荐阅读顺序

1. 先看 `src/services/_url.ts`、`_auth.ts`、`_header.ts`，弄清楚服务层通用请求约定。
2. 再看 `src/services/chat/mecha/index.ts`，建立聊天主链路的模块边界感。
3. 接着看 `src/services/chat/index.ts`，理解一次聊天请求如何被拼装和发出。
4. 然后看 `src/services/agentRuntime/client.ts`、`src/services/agentRuntime/index.ts`，补齐流式 agent 运行时。
5. 再看 `src/services/document/index.ts`、`document/invalidation.ts`、`utils/abortableRequest.ts`，理解编辑与缓存策略。
6. 最后按业务需要看 `user/`、`plugin/`、`aiProvider/`、`home/`、`export/` 等单域入口。

## 常见误区

- 容易把 `src/services` 当成服务端代码；实际上它主要是前端服务封装，常见实现是调用 `lambdaClient`。
- 容易把 `chat/mecha/` 误认成 UI 目录；它是聊天执行的核心逻辑层，不是页面组件。
- 容易忽略请求取消机制；`src/services/utils/abortableRequest.ts` 是解决竞态覆盖的关键。
- 容易忘记缓存失效；`src/services/document/invalidation.ts` 决定了编辑后哪些 SWR key 要刷新。
- 容易把 `src/services` 和 `src/server/services` 混淆；前者偏客户端业务适配，后者才是可直接访问 DB 的服务端实现。
- 容易只看 `index.ts` 而忽略辅助模块；像 `helper.ts`、`type.ts`、`swrKeys.ts` 往往决定服务层的真实行为边界。
