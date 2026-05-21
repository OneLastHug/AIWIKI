# 目录：src/server/services

## 它负责什么

`src/server/services` 是 LobeHub 服务端的“业务服务层”。它位于 `src/server/routers/*`、`src/app/(backend)/*` 这些 API 入口之下，位于 `src/database/models/*`、`@lobechat/database`、第三方 SDK、队列、存储、Agent Runtime 等基础能力之上。

可以把它理解成后端业务用例的承载层：路由层负责鉴权、参数校验和组织响应，数据库 Model 负责具体表读写，而 `services` 负责把多个 Model、外部服务、运行时模块组合成一个完整动作。例如：

- `AgentService` 读取和合并 Agent 配置，组合默认配置、用户默认配置、内置 Agent 信息和 Redis 中的欢迎语。
- `MessageService` 封装消息创建、删除、更新、工具状态更新、压缩分组等“写入后重新查询”的业务模式。
- `FileService` 统一文件存储实现，处理上传、预签名 URL、全局文件去重、文件代理 URL、临时文件下载。
- `AiChatService` 聚合消息和话题查询，并通过 `FileService` 后处理文件 URL。
- `ToolExecutionService` 统一执行 builtin tool 与 MCP tool，并做错误归一化、结果截断、Cloud MCP 调用。
- `TaskRunnerService` 编排一次任务运行：解析任务、处理并发状态、构造 prompt、调用 `AiAgentService.execAgent`、登记 topic 和 heartbeat。

这个目录不是一个单一服务，而是一组按业务域切分的服务集合。

## 关键组成

从直接子目录看，`services` 大致可以分为几类：

第一类是聊天与 Agent 主链路：

- `agent`：Agent 配置读取、内置 Agent 兜底、默认配置合并。
- `aiAgent`：执行 Agent，会关联 Agent 配置、文档、文件、Market、Klavis、异构 Agent、Agent Signal、工具代理等能力。
- `aiChat`：聊天页面所需的消息和话题聚合查询。
- `message`：消息增删改、工具消息更新、文件关联、压缩消息分组。
- `agentRuntime`：Agent 执行运行时相关服务，入口导出 `AgentRuntimeService`、`AbandonOperationService`、runtime 类型等。
- `toolExecution`：工具调用执行层，区分 `builtin` 与 `mcp`，并处理 Cloud MCP、错误分类和结果截断。

第二类是文件、知识库和文档：

- `file`：文件存储抽象，底层通过 `impls` 选择具体实现；同时维护用户文件记录和 `globalFiles` 去重记录。
- `document`、`chunk`、`knowledgeBase`：文档、分块、知识库检索相关服务。
- `agentDocuments`、`agentDocumentVfs`：Agent 文档和虚拟文件系统，包含技能挂载目录等逻辑。
- `skill`、`skillManagement`、`skillMaintainer`：技能解析、导入、资源、管理和维护。

第三类是任务与自动化：

- `task`、`taskRunner`、`taskLifecycle`、`taskScheduler`、`taskGraph`、`taskReview`、`taskTemplate`：任务定义、运行、生命周期、调度、依赖图、审核和模板。
- `queue`：队列抽象，支持本地 `setTimeout` 风格执行和生产环境 QStash 类执行。
- `agentSignal`：后台信号管线，包含 source、policy、processor、runtime、store、observability 等子模块。

第四类是外部集成和平台能力：

- `bot`、`messenger`、`gateway`：聊天平台 bot、消息路由、平台连接和运行状态。
- `mcp`、`klavis`、`discover`、`market`：插件/市场/MCP/云端能力发现与调用。
- `oauthDeviceFlow`、`oidc`、`webhookUser`、`user`：认证、用户和 webhook 相关能力。
- `generation`、`comfyui`：图片/视频生成、ComfyUI 工作流和后台轮询。
- `desktopRelease`、`changelog`、`usage`、`riskControl`、`sandbox` 等：分别处理桌面版本、更新日志、用量、风控、沙箱等横向能力。

很多子目录只有 `index.ts` 作为服务入口；复杂模块会继续拆分 `types.ts`、`impls/`、`core/`、`providers/`、`__tests__/` 等。

## 上下游关系

上游主要是 API 和工作流入口：

- `src/server/routers/lambda/*` 会大量实例化服务，例如 `agent.ts` 使用 `AgentService`，`message.ts` 使用 `MessageService` 和 `FileService`，`aiChat.ts` 使用 `AiChatService`，`task.ts` 使用 `TaskRunnerService`。
- `src/app/(backend)/*` 的 route handler 也会直接调用服务，例如 `/f/[id]/route.ts` 使用 `FileService` 读取和代理文件。
- workflow API 入口会调用任务、评测、后台轮询等服务，例如 agent eval、task lifecycle、generation polling。

下游主要是：

- `src/database/models/*` 和 `@lobechat/database`：服务层通常构造 `new XxxModel(db, userId)`，把数据访问委托给 Model。
- `packages/*`：如 `@lobechat/types`、`@lobechat/utils`、`@lobechat/const`、`@lobechat/builtin-*` 提供类型、工具函数、默认配置、内置技能和工具定义。
- 基础设施模块：Redis、S3/local file storage、QStash、MCP client、Market API、Agent Runtime、异构 Agent sandbox 等。
- 其他服务：服务之间可以组合调用，例如 `AiChatService` 内部使用 `FileService`；`TaskRunnerService` 调用 `AiAgentService` 和 `TaskLifecycleService`；`ToolExecutionService` 调用 `MCPService` 与 `DiscoverService`。

这个目录的依赖方向通常是“路由调用 service，service 调用 model/infra/其他 service”。不要把它理解成纯工具函数目录，它是业务编排层。

## 运行/调用流程

典型聊天查询流程是：

1. 前端通过 client service 调用 tRPC。
2. `src/server/routers/lambda/aiChat.ts` 创建 `new AiChatService(ctx.serverDB, ctx.userId)`。
3. `AiChatService.getMessagesAndTopics` 并行查询 `MessageModel` 和 `TopicModel`。
4. 查询消息时传入 `postProcessUrl`，由 `FileService.getFullFileUrl` 把存储路径转换为可访问 URL。
5. 返回 `{ messages, topics }` 给路由层，再返回给前端。

典型消息更新流程是：

1. 路由层调用 `MessageService.updateMessage`、`removeMessage`、`updateToolMessage` 等。
2. `MessageService` 先调用 `MessageModel` 完成写操作。
3. 如果调用方传入 `agentId/sessionId/topicId` 等上下文，就重新查询当前消息列表。
4. 返回 `{ success, messages? }`。这类“mutation + conditional query”是该目录里很常见的模式，用来减少前端额外刷新。

典型文件上传流程是：

1. 服务拿到 base64、Buffer 或外部 URL。
2. `FileService` 通过具体 `impl` 上传到存储。
3. 计算 hash、size、mime type 等元数据。
4. 检查 `globalFiles` 是否已有相同 hash，必要时复用或刷新全局记录。
5. 创建用户文件记录，返回统一代理 URL：`${APP_URL}/f/:id`。

典型 Agent/任务运行流程是：

1. `TaskRunnerService.runTask` 解析 task，检查是否已有 running topic。
2. 必要时补齐 assignee agent、模型快照、任务状态和 heartbeat。
3. 使用 `buildTaskPrompt` 生成任务 prompt。
4. 调用 `AiAgentService.execAgent`，挂载任务技能或 brief 工具，并注册 `onComplete` hook。
5. Agent 执行完成后由 `TaskLifecycleService` 处理 topic 完成、brief 合成、后续调度等生命周期动作。

典型工具执行流程是：

1. Agent Runtime 产生工具调用 payload。
2. `ToolExecutionService.executeTool` 根据 `payload.type` 分发到 builtin executor 或 MCP。
3. MCP 分支再区分普通 MCP 与 Cloud MCP。
4. 执行结果会被 `truncateToolResult` 截断，避免塞爆上下文。
5. 错误会通过 `classifyToolError` 归一化为包含 `code`、`kind`、`message` 的结构。

## 小白阅读顺序

建议不要从目录树最复杂的 `aiAgent`、`agentSignal` 开始。更适合的顺序是：

1. 先看 `src/server/routers/lambda/message.ts` 和 `src/server/services/message/index.ts`，理解“路由层调用服务层，服务层调用 Model”的基本模式。
2. 再看 `src/server/services/file/index.ts`，它展示了一个较完整的服务：存储实现抽象、数据库记录、去重、错误处理、代理 URL。
3. 接着看 `src/server/services/aiChat/index.ts`，它很短，适合理解服务层如何聚合多个 Model，并用 `Promise.all` 做并行查询。
4. 然后看 `src/server/services/agent/index.ts`，重点理解默认配置合并顺序：硬编码默认值、服务端默认值、用户默认值、数据库 Agent 配置。
5. 再看 `src/server/services/toolExecution/index.ts`，学习服务层如何封装外部执行器、MCP、错误归一化和结果保护。
6. 最后看 `src/server/services/taskRunner/index.ts`、`agentRuntime`、`aiAgent`、`agentSignal`，这些属于复杂编排层，需要先理解前面的基础服务模式。

如果只想快速建立地图，可以优先关注这些入口文件：`agent/index.ts`、`aiChat/index.ts`、`message/index.ts`、`file/index.ts`、`toolExecution/index.ts`、`queue/QueueService.ts`、`taskRunner/index.ts`。

## 常见误区

误区一：把 `services` 当成数据库访问层。  
实际数据库访问主要在 `src/database/models/*` 或 `@lobechat/database` 中，`services` 更偏业务编排。它会调用 Model，但不应该只被理解为 CRUD wrapper。

误区二：认为每个 service 都是独立的。  
很多服务会组合其他服务。例如 `AiChatService` 依赖 `FileService`；`TaskRunnerService` 依赖 `AiAgentService` 和 `TaskLifecycleService`；`ToolExecutionService` 依赖 MCP 与 builtin executor。阅读时要沿调用链看上下游。

误区三：忽略 `userId` 和 `db` 的传递。  
大多数服务构造函数是 `new XxxService(db, userId)`，这意味着服务天然绑定当前用户上下文。跨用户读写、共享链接、管理员场景通常会显式使用目标 owner 的 `userId`，不能随意复用当前用户。

误区四：把文件 URL 当成真实存储地址。  
`FileService` 会返回 `/f/:id` 代理 URL，而数据库里可能保存的是 S3 key、本地路径或其他实现相关路径。读取文件时通常要通过 `FileService` 再解析，不要直接拼接存储地址。

误区五：忽略“写后查”的返回约定。  
`MessageService`、`AgentService` 等服务常常在 mutation 后立即 query，直接返回更新后的业务对象或列表。前端调用方可能依赖这个返回值刷新 UI，改动时不能只看写入是否成功。

误区六：低估任务、Agent Runtime、Agent Signal 的复杂度。  
这些模块不是普通 CRUD，而是异步执行、hook、队列、topic 生命周期、工具调用和后台信号的组合。根据当前片段推断，它们是服务层中最容易产生并发和状态一致性问题的部分，阅读时要特别关注 status、heartbeat、operationId、hook 回调和重试逻辑。
