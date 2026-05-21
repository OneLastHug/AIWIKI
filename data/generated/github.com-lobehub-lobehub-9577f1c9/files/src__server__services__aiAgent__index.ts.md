# 文件：src/server/services/aiAgent/index.ts

## 它负责什么

`src/server/services/aiAgent/index.ts` 定义并导出核心类 `AiAgentService`。它是服务端发起 AI Agent 执行的总入口，负责把一次“用户让某个 Agent 处理一段 prompt”的请求，转换成数据库消息、话题、工具集、上下文、运行时 operation，并交给 `AgentRuntimeService` 真正执行。

可以把它理解成 Agent 执行链路里的“编排器”：

- 从数据库读取 Agent 配置：模型、provider、systemRole、plugins、chatConfig、knowledgeBases 等。
- 根据运行场景补充运行时配置：内置 Agent、页面 Agent、任务 Agent、群组 Agent、子 Agent。
- 创建或复用 `topic`、`thread`、`message` 等会话数据。
- 处理附件：外部文件上传、图片/视频识别、普通文件解析成文档内容。
- 构建工具系统：builtin tools、LobeHub Skills、Klavis tools、client function tools、设备工具、agent management 工具。
- 做设备访问控制：判断当前调用方是否可以访问 `local-system` / `remote-device` 这类可能触碰用户机器的工具。
- 构建 memory、persona、agent management context、device system info、operation skill set。
- 创建 `AgentRuntimeService.createOperation(...)`，把所有准备好的上下文交给运行时。
- 支持中断任务、群组 Agent、SubAgent 隔离线程、人工审批恢复、异构 Agent 执行。

文件里的主出口只有一个：

```ts
export class AiAgentService
```

但这个类承担的职责非常多，是 `server/services` 层里连接路由、数据库、工具引擎、运行时、设备网关、任务系统和 Bot 系统的关键节点。

## 关键组成

### 1. 顶部工具函数

文件开头有几个小工具函数：

`formatErrorForMetadata(error)`  
用于把 `Error` 或其他异常对象转换成可以安全写入 thread metadata 的普通对象。因为原生 `Error` 直接 `JSON.stringify` 时不会完整序列化。

`getVisualAvailabilityFromFileTypes(fileTypes)`  
根据 MIME 类型判断本轮输入里是否有图片或视频。

`getVisualAvailabilityFromMessages(messages)`  
扫描历史消息里的 `imageList` / `videoList`，判断历史上下文是否包含视觉内容。

`isVisualUnderstandingConfigured()`  
检查 `toolsEnv.VISUAL_UNDERSTANDING_PROVIDER` 和 `toolsEnv.VISUAL_UNDERSTANDING_MODEL` 是否配置，用于决定是否自动启用视觉理解工具。这里包了 `try/catch`，因为某些 client-like runtime 读取 server-only env 可能会被 env proxy 拒绝。

### 2. `InternalExecAgentParams`

`InternalExecAgentParams` 扩展了公共类型 `ExecAgentParams`，加入了服务端内部专用参数。它说明 `execAgent` 不只是给普通聊天用，还要兼容很多入口：

- `additionalPluginIds`：额外注入插件，比如任务执行时注入任务工具。
- `botContext` / `botPlatformContext` / `discordContext`：Bot 或 IM 平台上下文。
- `cronJobId` / `taskId` / `trigger`：定时任务、任务系统、触发来源。
- `disableTools` / `disableLocalSystem`：禁用工具或禁用本地系统工具。
- `files` / `fileIds`：外部上传文件或已上传文件。
- `functionTools`：Response API 传入的 client-side function tools。
- `hooks`：运行时生命周期 hooks。
- `resume` / `resumeApproval` / `parentMessageId`：恢复执行、人工审批继续。
- `signal`：启动前或准备阶段中止执行。
- `userInterventionConfig`：人工干预配置，默认是 `{ approvalMode: 'headless' }`。

这个类型本身就是阅读 `execAgent` 的导航图：参数越多，说明这个服务要适配的调用场景越复杂。

### 3. `AiAgentService` 构造函数

构造函数接收：

```ts
constructor(
  db: LobeChatDatabase,
  userId: string,
  options?: { runtimeOptions?: AgentRuntimeServiceOptions },
)
```

内部初始化了大量模型和服务：

- `AgentModel`
- `AgentService`
- `MessageModel`
- `PluginModel`
- `TaskModel`
- `ThreadModel`
- `TopicModel`
- `AgentDocumentsService`
- `AgentRuntimeService`
- `MarketService`
- `KlavisService`

其中最关键的是：

```ts
this.agentRuntimeService = new AgentRuntimeService(db, userId, {
  ...options?.runtimeOptions,
  execSubAgentTask: this.execSubAgentTask.bind(this),
});
```

这表示运行时在执行过程中如果需要调用 SubAgent，会回调当前服务的 `execSubAgentTask`。因此 `AiAgentService` 不只是 operation 的创建者，也参与 Agent 调 Agent 的递归式协作。

### 4. `execAgent(params)`

这是文件最核心的方法。

它的职责是：根据 `agentId` 或 `slug` 找到 Agent，准备完整运行环境，创建消息和 operation，然后启动或排队执行。

主要阶段如下：

1. 校验 `agentId` / `slug`。
2. 解析任务 ID，处理 abort signal。
3. 读取 Agent 配置。
4. 合并内置 Agent runtime config。
5. 根据 `appContext.scope` 注入 page-agent 或 task-agent 能力。
6. 处理 resume / resumeApproval。
7. 创建或复用 topic。
8. 判断是否是异构 Agent，如 `claude-code` / `codex`。
9. 读取用户设置、memory、timezone。
10. 构建工具、manifest、executor、source map。
11. 处理设备访问策略。
12. 处理附件上传和文件解析。
13. 创建 user message 和 assistant placeholder message。
14. 构建 `initialContext`。
15. 构建 `operationSkillSet`。
16. 调用 `AgentRuntimeService.createOperation(...)`。
17. 写入 topic metadata 的 `runningOperation`。
18. 返回 operation 创建结果。

其中普通 Agent 和异构 Agent 有明显分支：

普通 Agent 走：

```ts
this.agentRuntimeService.createOperation(...)
```

异构 Agent 走：

- 创建 user message
- 创建 assistant placeholder
- 签发 operation JWT
- 构建 cloud hetero context
- 如果有 `requestedDeviceId`，走 `deviceProxy.dispatchAgentRun(...)`
- 否则走 `spawnHeteroSandbox(...)`
- 返回 operation 信息

这里的异构 Agent 指 `claude-code` / `codex` 这类不是直接由服务端 LLM runtime 执行的 Agent，而是交给设备网关或云沙箱执行，再通过 `heteroIngest` / `heteroFinish` 回写事件。

### 5. 工具系统构建

`execAgent` 中的工具构建是最复杂的部分之一。

它从多个来源收集工具：

- 已安装插件：`pluginModel.query()`
- 内置工具：`builtinTools`
- LobeHub Skills：`marketService.getLobehubSkillManifests()`
- Klavis tools：`klavisService.getKlavisManifests()`
- Response API client function tools：`functionTools`
- 根据上下文动态注入的工具：
  - `lobe-topic-reference`
  - `MessageToolIdentifier`
  - `LobeAgentManifest.identifier`
  - `LocalSystemManifest.identifier`
  - `RemoteDeviceManifest.identifier`
  - self-feedback intent tool

它会构造几个核心结构：

`tools`  
真正传给模型的 function tools 列表。

`toolManifestMap`  
工具 identifier 到 manifest 的映射，供 activator、context engine、runtime 使用。

`toolSourceMap`  
记录工具来源，如 `lobehubSkill`、`klavis`、`client`。

`toolExecutorMap`  
记录某些工具应该由 client 执行，比如 desktop 本地工具或 stdio MCP 插件。

`toolsResult.enabledToolIds`  
最终启用的工具 ID 列表。

这里特别重要的是设备工具的安全过滤。文件通过同目录的 `deviceAccessPolicy.ts` 和 `deviceToolRegistry.ts` 做两层控制：

- `resolveDeviceAccessPolicy({ botContext })` 决定当前调用方是否可以使用设备工具。
- `buildAllowedBuiltinTools({ canUseDevice, disableLocalSystem })` 从物理层过滤 `builtinTools`，避免工具 manifest 仍被 activator 发现。

代码注释里明确提到这是为了防止外部 Bot sender 通过显式激活绕过 enable gate，触达 `lobe-remote-device` 或 `local-system`。

### 6. 附件处理

附件处理分两类：

`files`  
外部平台传入的新文件，可能有 `buffer` 或 `url`。通过同目录的 `ingestAttachment(...)` 处理：

- 下载或读取 buffer。
- 修正 MIME 类型。
- 压缩图片。
- 上传到文件服务。
- 生成 file record。
- 对图片/视频生成可访问 URL。
- 对普通文档调用 `DocumentService.parseFile(...)` 提取文本内容。

`fileIds`  
客户端已经上传好的文件 ID。服务会读取文件记录，解析 URL，分类成：

- `imageList`
- `videoList`
- `fileList`

最终这些列表会进入 user message，让 `MessageContentProcessor` 或视觉模型可以看到附件内容。

### 7. `execGroupAgent(params)`

`execGroupAgent` 是群组 Agent 的便捷封装。

它做的事情很薄：

1. 必要时创建带 `groupId` 的 topic。
2. 调用 `execAgent(...)`。
3. 在 `appContext` 中传入 `groupId` 和 `topicId`。
4. 返回 `assistantMessageId`、`operationId`、`topicId`、`userMessageId` 等结果。

所以群组 Agent 的核心执行仍然复用 `execAgent`。

### 8. `execSubAgentTask(params)`

`execSubAgentTask` 用于 Supervisor 或普通 Agent 把任务委派给子 Agent。

它的关键区别是会创建隔离线程：

```ts
type: ThreadType.Isolation
```

流程是：

1. 如果有父 operation，派发 `beforeCallAgent` hook。
2. 创建 `Thread`，状态设为 `Processing`。
3. 创建 thread hooks，用于在子 Agent 执行期间更新 thread metadata。
4. 读取父 operation 的 trigger，传递给子任务。
5. 调用 `execAgent(...)`，并在 `appContext` 中传入 `threadId`。
6. 把子 operationId 写入 thread metadata。
7. 根据启动结果更新 thread 状态。
8. 派发 `afterCallAgent` 或 `onCallAgentError` hook。

这说明 SubAgent 的“隔离”主要依靠 `Thread` 实体：同一个 topic 下可以有多个隔离 thread，每个 thread 代表一个子任务执行上下文。

### 9. `createThreadHooks(...)`

这是给 SubAgent 线程用的生命周期 hook。

它返回两个 hook：

`afterStep`  
每一步后更新 thread metadata，包括：

- `operationId`
- `startedAt`
- `totalMessages`
- `totalTokens`
- `totalToolCalls`

`onComplete`  
执行完成后更新：

- thread 状态：`Completed`、`Failed`、`Cancel`、`InReview`
- `completedAt`
- `duration`
- `error`
- `totalCost`
- `totalMessages`
- `totalTokens`
- `totalToolCalls`

它还会把最后一条 assistant 消息内容写回 `sourceMessageId`，作为任务摘要。

文件里还保留了 `createThreadMetadataCallbacks(...)`，但实际 `execSubAgentTask` 使用的是新的 `createThreadHooks(...)`。根据当前片段推断，前者可能是旧版 callback 机制遗留，后者是替代后的 hook 系统。

### 10. `interruptTask(params)`

`interruptTask` 用于中断运行中的 SubAgent task。

它支持两种入口：

- 传 `threadId`
- 直接传 `operationId`

如果传了 `threadId`，会先找 thread，再从 thread metadata 中解析 operationId。之后调用：

```ts
this.agentRuntimeService.interruptOperation(resolvedOperationId)
```

只有运行时确认中断后，才把 thread 状态更新为 `ThreadStatus.Cancel`。这避免 UI 或数据库状态提前显示取消，但实际 operation 仍在运行。

## 上下游关系

### 上游调用方

这个文件被多个入口调用，说明它是服务端 Agent 执行的统一业务层。

主要上游包括：

`src/server/routers/lambda/aiAgent.ts`  
tRPC 路由入口。里面的 `execAgent`、`execAgents`、`execGroupAgent`、`execSubAgentTask` 都会调用 `AiAgentService`。这是前端 SPA 最常见的调用路径。

`src/server/agent-hono/handlers/execAgent.ts`  
REST/Hono 风格入口，接收 `{ userId, agentId | slug, prompt, appContext?, autoStart?, existingMessageIds? }`，创建 `AiAgentService` 后调用 `execAgent`。适合 API key 或 QStash 等非 tRPC 场景。

`src/server/services/taskRunner/index.ts`  
任务系统执行入口。它会给 `execAgent` 注入任务插件、任务模型快照、hooks、`taskId`、`trigger`、`userInterventionConfig` 等。

`src/server/services/bot/AgentBridgeService.ts`  
Bot / IM 平台桥接服务。它会把外部消息转换成 Agent 执行请求，并传入 bot 上下文、平台上下文、hooks 等。

`src/server/services/agentEvalRun/index.ts`  
评测运行服务。它用 `execAgent` 执行 eval 场景，并可能传入 eval 相关上下文、禁用工具等参数。

`src/server/services/task/index.ts`、`BotMessageRouter.ts`、`MessengerRouter.ts`  
这些服务主要调用 `interruptTask` 来中断正在执行的 operation 或 thread。

### 下游依赖

`AiAgentService` 下游非常多，可以按职责分组理解。

数据库模型：

- `AgentModel`
- `MessageModel`
- `PluginModel`
- `TaskModel`
- `ThreadModel`
- `TopicModel`
- `AiModelModel`
- `FileModel`
- `AgentSkillModel`
- `UserModel`
- `UserPersonaModel`
- `AgentOperationModel`

服务层：

- `AgentService`
- `AgentDocumentsService`
- `AgentRuntimeService`
- `DocumentService`
- `FileService`
- `HeterogeneousAgentService`
- `MarketService`
- `KlavisService`

工具和上下文：

- `createServerAgentToolsEngine`
- `SkillEngine`
- `builtinTools`
- `builtinSkills`
- `getAgentRuntimeConfig`
- `buildTaskManagerDefaultsPrompt`

设备和异构执行：

- `deviceProxy`
- `resolveDeviceAccessPolicy`
- `buildAllowedBuiltinTools`
- `HeterogeneousAgentService`
- `spawnHeteroSandbox`
- `buildCloudHeteroContext`

运行时 hooks 和信号：

- `hookDispatcher`
- `enqueueAgentSignalSourceEvent`
- `isAgentSignalEnabledForUser`
- `resolveAgentSelfIterationCapability`

同目录辅助模块：

`deviceAccessPolicy.ts`  
提供设备访问策略。非 Bot 场景默认允许设备工具；Bot 场景只有 owner 或个人作用域平台等情况允许。

`deviceToolRegistry.ts`  
定义哪些工具算设备工具，并提供 `buildAllowedBuiltinTools` 做物理过滤。

`ingestAttachment.ts`  
统一处理外部附件：下载、MIME 修正、图片压缩、上传、生成 file record 和 URL。

## 运行/调用流程

以普通前端聊天调用 `ctx.aiAgentService.execAgent(...)` 为例，流程可以这样理解：

1. 前端通过 tRPC 调用 `aiAgent.execAgent`，传入 `agentId` 或 `slug`、`prompt`、`appContext`、附件信息等。
2. tRPC router 创建或复用 `AiAgentService`，把参数转给 `execAgent`。
3. `execAgent` 校验参数，读取 Agent 配置。
4. 如果 Agent 是内置 Agent，根据 slug 合并运行时 systemRole 和 plugins。
5. 如果是 page/task scope，额外注入 page-agent 或 task-agent 的 systemRole 和工具。
6. 如果是 resume 或 human approval resume，校验 parent message、topic、thread、session，并写入审批结果。
7. 创建或复用 topic。
8. 如果是 `claude-code` / `codex` 异构 Agent，提前进入 hetero 分支，创建消息后交给设备或云沙箱。
9. 普通 Agent 继续读取用户设置、memory、timezone。
10. 查询安装插件、模型能力、LobeHub Skills、Klavis manifests。
11. 根据 botContext 计算设备访问策略，决定是否允许 local-system / remote-device。
12. 创建 `toolsEngine`，生成 function tools、manifest map、source map、executor map。
13. 根据模型视觉能力和输入附件决定是否注入视觉理解工具。
14. 根据 agent-management 工具启用情况，构建可用 Agent、provider、plugin 上下文。
15. 读取用户 persona，作为 memory 注入。
16. 加载历史消息。
17. 上传或解析附件，构建 `imageList`、`videoList`、`fileList`。
18. 创建 user message。
19. 创建 assistant placeholder message，内容是 `LOADING_FLAT`。
20. 构建 `initialContext`，包含 assistant message ID、parent message ID、tools、message payload 等。
21. 构建 `operationId`。
22. 用 `SkillEngine` 生成 `operationSkillSet`。
23. 调用 `AgentRuntimeService.createOperation(...)`，传入 Agent 配置、模型配置、工具集、消息历史、hooks、memory、device context 等。
24. 如果创建成功，把 `runningOperation` 写入 topic metadata，返回 operation 信息。
25. 如果创建失败，更新 assistant message 的 error 字段，并返回 `status: 'error'`。

SubAgent 流程是在这个基础上多了一层 `Thread`：

1. 父 Agent 调用 `callAgent` 之类的工具。
2. runtime 通过构造函数注入的 `execSubAgentTask` 回调进入 `AiAgentService`。
3. `execSubAgentTask` 创建 isolation thread。
4. 再调用 `execAgent`，但 `appContext` 带上 `threadId`。
5. 子 Agent 的消息和运行状态绑定到这个 thread。
6. hooks 持续更新 thread metadata 和最终状态。

群组 Agent 流程则更简单：

1. `execGroupAgent` 创建带 `groupId` 的 topic。
2. 调用 `execAgent`。
3. 所有核心执行逻辑仍由 `execAgent` 完成。

中断流程：

1. 上游调用 `interruptTask({ threadId })` 或 `interruptTask({ operationId })`。
2. 服务解析 operationId。
3. 调用 `AgentRuntimeService.interruptOperation(...)`。
4. 成功后更新 thread 为 `Cancel`。

## 小白阅读顺序

建议不要从第一行 import 开始硬读，因为依赖太多。可以按下面顺序：

1. 先读类注释和构造函数  
   重点看 `AiAgentService` 初始化了哪些 model/service，特别是 `AgentRuntimeService`。

2. 读 `execAgent` 的方法注释  
   注释里已经写了核心架构：

   ```txt
   execAgent
     → AgentModel.getAgentConfig
     → ServerMechaModule.AgentToolsEngine
     → ContextEngineering
     → AgentRuntimeService.createOperation
   ```

3. 跳读 `execAgent` 前 1/3  
   重点理解 Agent 配置、builtin runtime config、page/task scope、resume、topic 创建。

4. 单独读 hetero 分支  
   搜索 `HETERO_AGENT_MODELS`。理解为什么 `claude-code` / `codex` 不走普通 LLM runtime，而是走设备或云沙箱。

5. 读工具构建部分  
   搜索 `Tool discovery`、`createServerAgentToolsEngine`、`generateToolsDetailed`。重点看 `toolManifestMap`、`toolSourceMap`、`toolExecutorMap` 是怎么来的。

6. 配合同目录读设备安全模块  
   先读 `deviceAccessPolicy.ts`，再读 `deviceToolRegistry.ts`。这样能理解为什么代码里多次强调 `canUseDevice` 和“物理过滤”。

7. 读附件处理  
   搜索 `ingestAttachment` 和 `attachedFileIds`。再去看 `ingestAttachment.ts`，理解文件如何变成 message 的 `imageList` / `videoList` / `fileList`。

8. 读 operation 创建  
   搜索 `createOperation`。这是所有准备工作汇总的地方，参数基本就是 Agent 运行所需的完整世界状态。

9. 最后读 `execGroupAgent`、`execSubAgentTask`、`interruptTask`  
   这几个方法相对独立，都是围绕 `execAgent` 的封装或控制方法。

## 常见误区

1. 误以为 `AiAgentService` 只负责调用模型  
   实际模型调用不在这里直接发生。这里主要负责准备上下文、消息、工具和 operation；真正执行由 `AgentRuntimeService` 和更底层 runtime 完成。

2. 误以为 `execAgent` 每次都会创建新 topic  
   不一定。如果 `appContext.topicId` 存在，它会复用现有 topic。只有没有 topicId 时才创建新 topic。

3. 误以为 resume 会创建新的 user message  
   `effectiveResume` 为真时不会创建新的 user message，而是基于 `parentMessageId` 和历史消息继续。

4. 误以为 `resumeApproval.rejected` 和 `rejected_continue` 服务端逻辑完全不同  
   当前代码里两者都会把拒绝信息写入 tool message，并把拒绝作为上下文反馈给 LLM。注释说明二者的差异主要是客户端 UX 和乐观写入层面的区别。

5. 误以为工具只看 Agent 配置里的 plugins  
   实际最终工具集还会合并 builtin tools、LobeHub Skills、Klavis tools、动态注入工具、client function tools、视觉理解工具、self-feedback 工具等。

6. 误以为禁用设备工具只要在 enableChecker 里返回 false  
   代码特别强调还必须从 manifest 发现路径中“物理过滤”。否则 activator 仍可能通过 manifest map 找到设备工具并尝试激活。

7. 误以为 Bot 场景和普通 Web 场景权限一样  
   Bot 场景会通过 `resolveDeviceAccessPolicy` 判断调用者是否是 owner、是否个人作用域平台、是否外部 sender。外部 sender 默认不能访问设备工具，也不能看到设备列表 prompt。

8. 误以为图片/视频附件都直接交给当前模型  
   如果当前模型没有 vision/video 能力，并且配置了视觉理解 provider/model，服务可能动态注入 `LobeAgentManifest.identifier` 这样的视觉理解工具来补能力。

9. 误以为异构 Agent 也走 `AgentRuntimeService.createOperation`  
   `claude-code` / `codex` 这类异构 Agent 在 `execAgent` 中提前分支，走 `deviceProxy.dispatchAgentRun` 或 `spawnHeteroSandbox`，通过后续 ingest/finish 回写结果。

10. 误以为 SubAgent 只是普通消息  
   SubAgent 会创建 `ThreadType.Isolation` 的 thread，并用 hooks 维护 thread 状态、token、tool calls、cost 和最终摘要。它是隔离线程执行，不只是普通 assistant 消息。

11. 误以为 `assistantMessageRecord` 是模型返回后才创建  
   实际是在 operation 开始前就创建 placeholder，内容为 `LOADING_FLAT`。这样 UI 可以立刻显示 assistant 正在生成；如果 operation 启动失败，也会把错误写回这条 assistant message。

12. 误以为 `interruptTask` 只是改数据库状态  
   它先调用 `agentRuntimeService.interruptOperation`，运行时确认中断后才更新 thread 为取消。这避免数据库状态和真实运行状态不一致。
