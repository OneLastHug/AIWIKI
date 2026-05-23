# 子系统：src/server/services

## 解决什么问题

`src/server/services` 是服务器侧的业务服务层，总体职责是把“路由/工作流/定时任务”里零散的业务步骤收拢成可复用的流程对象。这里不直接承担 HTTP 路由，也不做纯数据库模型层的细粒度 CRUD，而是负责把 `db`、`userId`、外部 SDK、缓存、文件存储、队列、模型调用等能力组合起来，形成稳定的应用服务。

从当前代码可以看出，它覆盖了几类核心问题：代理执行与工具编排、任务与子任务生命周期、文档与虚拟文件系统、消息平台接入、发现页和首页数据、OIDC / OAuth 授权、评测运行、用户初始化，以及若干后台流程的支撑。根据当前片段推断，这里是 `src/server` 中“业务规则最密集”的一层，很多上层入口只是把请求转给这些服务处理。

## 相关目录和文件

最直接的消费者来自 `src/server/agent-hono`、`src/server/workflows-hono`、`src/server/routers/lambda`、`src/server/routers/async`。例如 `src/server/agent-hono/handlers/execAgent.ts` 调用 `AiAgentService`，`src/server/workflows-hono/task/handlers/onTopicComplete.ts` 调用 `TaskLifecycleService`，`src/server/routers/lambda/agentDocument.ts` 依赖 `AgentDocumentVfsService`。

目录内部按业务域拆分得很清楚，代表性入口有：`src/server/services/aiAgent/index.ts`、`task/index.ts`、`agentDocumentVfs/index.ts`、`document/index.ts`、`messenger/index.ts`、`discover/index.ts`、`home/index.ts`、`oidc/index.ts`、`oauthDeviceFlow/index.ts`、`followUpAction/index.ts`、`agentEvalRun/index.ts`、`sandbox/index.ts`、`user/index.ts`、`onboarding/index.ts`。

另外，很多服务会继续依赖更底层的模型层和模块层，比如 `src/database/models/*`、`src/server/modules/Mecha`、`src/server/modules/S3`、`src/libs/redis`、`src/libs/oidc-provider`、`src/server/services/agentRuntime`、`src/server/services/file`、`src/server/services/market`。

## 核心对象

最核心的对象不是某一个类，而是一组“服务对象”：

- `AiAgentService`：最重的编排层，负责 agent 运行、工具注入、视觉能力、附件处理、子代理、信号触发等。
- `TaskService`：把任务创建、状态流转、topic 中断、review、下游解锁这些动作串起来。
- `AgentDocumentVfsService`：把普通 agent 文档和挂载目录统一成类似文件系统的视图。
- `DocumentService`：围绕文档创建、批量创建、历史版本、文件关联进行封装。
- `MessengerRouter` 与各平台 binder：把 Slack、Discord、Telegram 等平台消息统一进系统。
- `DiscoverService`：对接市场与发现页，处理客户端注册、M2M token、云端 MCP 调用。
- `OIDCService`：管理交互详情、grant、client metadata，支撑登录授权流。
- `OAuthDeviceFlowService`：封装 device code / token polling。
- `FollowUpActionService`：从最近的 assistant 回复里提取后续建议。
- `AgentEvalRunService`：创建、终止、重试评测运行，并管理相关 topic。
- `HomeService`：读取首页 brief 这种缓存型数据。
- `ServerSandboxService`：把云端 sandbox 能力包成服务器侧实现。
- `UserService`：做用户初始化、审计与头像读取。

## 运行流程

典型流程是：请求先进入 `src/server/agent-hono`、`src/server/workflows-hono` 或 `src/server/routers/*`，再实例化对应 service，最后由 service 组合模型层和外部能力完成业务。

比如 `AiAgentService` 会读取 agent、topic、message、file、task、market 等数据，构建 system prompt 和工具集，必要时触发 `agentSignal` 或调用 `AgentRuntimeService`。`TaskService` 会在创建任务时校验 assignee，必要时快照 agent 配置；在取消或删除 topic 时，会先中断运行中的远程操作，再回写任务和 topic 状态。`AgentDocumentVfsService` 会先规范化路径，再区分普通文档、`./lobe` 这种合成目录、技能挂载目录，返回统一的节点、统计和读取结果。`HomeService` 则更轻，只负责从 Redis 读缓存，失败时退化成空数据。

## 上下游依赖

上游主要是 API 路由、Hono handler、workflow 任务、lambda router、cron 任务。它们决定“什么时候调用服务”。

下游主要是三类依赖：

1. 数据层：`src/database/models/*` 和 `src/database/schemas`，负责读写业务表。
2. 基础设施：S3、Redis、OIDC provider、Market SDK、QStash、外部 OAuth / 消息平台。
3. 其他服务与模块：`agentRuntime`、`file`、`message`、`taskRunner`、`agentSignal`、`agentDocuments`、`skill`、`market`、`toolExecution` 等。

这层依赖关系很明显地体现了“服务层互相编排，但尽量不直接暴露底层表结构给上层”。

## 修改时最容易踩的坑

第一，很多服务是强用户隔离的，构造函数里必须正确传 `db` 和 `userId`，否则会出现权限串读或写错归属的问题。

第二，服务之间存在较深的链式依赖，修改时要注意不要引入循环引用，尤其是 `aiAgent`、`agentRuntime`、`task`、`agentDocumentVfs`、`document` 这几组。

第三，不同服务对失败策略不同：`HomeService` 会静默降级为空，`FollowUpActionService` 遇到 LLM/schema 失败也会返回空结果，而 `TaskService`、`OIDCService` 更倾向于抛 `TRPCError`。改动时不要把这些容错语义混掉。

第四，`AgentDocumentVfsService` 不是普通目录读取，它有合成根路径、挂载路径和大小限制，直接改路径规则很容易让 CLI 或路由层出现“看起来像文件系统，实际不是”的偏差。

第五，像 `DiscoverService`、`OAuthDeviceFlowService`、`ServerSandboxService` 这类依赖外部平台的服务，环境变量、设备标识、认证头和返回字段都很敏感，改接口前最好先看测试。

## 推荐阅读顺序

1. `src/server/services/task/index.ts`
2. `src/server/services/aiAgent/index.ts`
3. `src/server/services/agentDocumentVfs/index.ts`
4. `src/server/services/document/index.ts`
5. `src/server/services/messenger/index.ts`
6. `src/server/services/discover/index.ts`
7. `src/server/services/oidc/index.ts`
8. `src/server/services/agentEvalRun/index.ts`

这条顺序能先建立“任务与 agent 编排”的主线，再看文档、消息、发现与授权等外围能力，最后补后台评测与缓存型服务。
