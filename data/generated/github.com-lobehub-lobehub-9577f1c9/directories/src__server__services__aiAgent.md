# 目录：src/server/services/aiAgent

## 它负责什么

`src/server/services/aiAgent` 是服务端“启动一次 Agent 执行”的编排层。它不只是把一段 `prompt` 发给模型，而是把一次 Agent 对话所需的上下文、消息、工具、附件、设备权限、记忆、子 Agent 线程、运行时操作全部准备好，然后交给 `AgentRuntimeService.createOperation(...)` 真正运行。

核心类是 `AiAgentService`，位于 `src/server/services/aiAgent/index.ts`。它的职责可以概括为：

1. 根据 `agentId` 或 `slug` 读取 Agent 配置。
2. 创建或复用 `topic`、`message`、`thread` 等数据库记录。
3. 组装模型参数、系统提示词、历史消息、用户记忆、附件内容。
4. 发现并过滤可用工具，包括 builtin tools、LobeHub Skills、Klavis tools、客户端函数工具。
5. 处理设备工具权限，防止外部 Bot 消息越权访问用户本机或远程设备。
6. 对接异构 Agent，例如 `claude-code`、`codex`，将执行分发到本地设备或云沙箱。
7. 创建 Agent Runtime operation，并返回 `operationId`、消息 ID、topic ID、Gateway token 等给调用方。
8. 支持 Group Agent、SubAgent 任务、任务中断、人类审批恢复、文件上传摄入等复杂执行场景。

从分层看，它位于服务端业务服务层，向上被 tRPC、REST API、Bot、任务系统、评测系统调用；向下依赖数据库模型、工具引擎、运行时服务、文件服务、设备代理、异构 Agent 服务等。

## 关键组成

### `index.ts`

这是目录的主入口，导出 `AiAgentService`。文件很长，因为它承担的是一次 Agent 运行的总调度。

构造函数会初始化多种模型和服务：

- `AgentModel`、`AgentService`：读取 Agent 配置和 Agent 列表。
- `MessageModel`：创建用户消息、助手占位消息、工具消息更新。
- `TopicModel`：创建或更新话题，保存 `runningOperation` 元数据。
- `ThreadModel`：为 SubAgent 创建隔离线程并更新状态。
- `PluginModel`：读取已安装插件。
- `TaskModel`：解析任务 ID。
- `AgentRuntimeService`：真正创建、启动、中断 operation。
- `AgentDocumentsService`、`DocumentService`、`FileService`：处理知识文档和附件。
- `MarketService`、`KlavisService`：加载 LobeHub Skills、Klavis 工具。
- `HeterogeneousAgentService`：处理 `claude-code` / `codex` 这类异构 Agent。

最重要的方法是 `execAgent(params)`。它接收 `ExecAgentParams` 的增强版 `InternalExecAgentParams`，额外支持服务端内部参数，例如 `hooks`、`files`、`functionTools`、`resumeApproval`、`disableTools`、`botContext`、`evalContext`、`maxSteps`、`userInterventionConfig` 等。

另外还有三个重要公开方法：

- `execGroupAgent(params)`：Group Agent 的入口，先处理 `groupId` 和 topic，再委托给 `execAgent`。
- `execSubAgentTask(params)`：被 Supervisor 或普通 Agent 调用，用隔离 `Thread` 运行子 Agent 任务。
- `interruptTask(params)`：根据 `threadId` 或 `operationId` 中断正在运行的任务，并更新线程状态。

### `deviceAccessPolicy.ts`

这个文件定义设备工具访问策略，是判断“当前这次执行能不能碰用户设备”的唯一权威位置。

核心函数：

```ts
resolveDeviceAccessPolicy(input)
```

输入主要是 `botContext`，输出：

```ts
{
  canUseDevice: boolean;
  reason: DeviceAccessReason;
}
```

策略大意：

- 没有 `botContext`：认为是一方 UI 调用，例如 Web / Desktop / Mobile，允许使用设备工具，原因是 `first-party`。
- `botContext.isOwner` 为真：Bot 消息来自绑定用户本人，允许，原因是 `bot-owner`。
- 某些个人作用域平台，例如当前代码中的 `wechat`：允许，原因是 `bot-personal-platform`。
- Bot 调用但无法确认发送者或发送者不是 owner：拒绝，原因可能是 `bot-owner-not-configured` 或 `bot-external-sender`。

这个文件的重点不是“方便启用工具”，而是“集中封锁设备能力”。下游不应该重新根据 `botContext` 自己推断权限，而是使用这个函数的结果。

### `deviceToolRegistry.ts`

这个文件定义“哪些工具属于设备工具”。

核心常量：

- `DEVICE_TOOL_MANIFESTS`
- `DEVICE_TOOL_IDENTIFIERS`
- `isDeviceToolIdentifier(identifier)`
- `buildAllowedBuiltinTools(params)`

当前设备工具来自：

- `LocalSystemManifest`
- `RemoteDeviceManifest`

`buildAllowedBuiltinTools` 会根据 `canUseDevice` 和 `disableLocalSystem` 物理过滤 `builtinTools`。这里的“物理过滤”很重要：不是只在执行时拦一下，而是在传给工具引擎、工具发现、activator 之前就把不允许的 manifest 移除，避免模型通过显式激活绕过规则层。

### `deviceToolAudit.ts`

这是设备工具调用审计日志模块。

核心函数：

```ts
logDeviceToolAudit(params)
```

它不会记录工具参数、文件内容、命令输出等敏感 payload，只记录身份和决策元数据，例如：

- `toolIdentifier`
- `apiName`
- `userId`
- `topicId`
- `operationId`
- `platform`
- `senderExternalUserId`
- `isOwner`
- `reason`
- `canUseDevice`

根据当前片段推断，审计主要用于事后排查“谁触发了设备工具”，而不是实时风控；依据是代码注释明确说明它使用 `debug` logger 而不是 DB 表。

### `ingestAttachment.ts`

这是外部附件摄入模块。它把来自 Bot、平台适配层或外部 URL 的附件统一转成 LobeHub 文件系统中的记录。

核心函数：

```ts
ingestAttachment(source, fileService, userId)
```

处理流程：

1. 从 `buffer` 或 `url` 得到二进制内容。
2. 根据 HTTP header 或文件名修正 MIME type。
3. 对 `image/jpeg`、`image/png`、`image/webp` 做压缩。
4. 上传到文件存储。
5. 为图片和视频生成可访问 URL。
6. 返回 `fileId`、`key`、`resolvedUrl`、`isImage`、`isVideo`。

它和 `execAgent` 的关系是：`execAgent` 收到 `files` 参数后，会调用 `ingestAttachment` 上传附件；图片放入 `imageList`，视频放入 `videoList`，普通文档会进一步通过 `DocumentService.parseFile(...)` 解析文本内容，放入 `fileList` 供上下文处理器注入给模型。

### `__tests__`

测试覆盖面能反映这个服务的关键风险点。目录中有大量 `execAgent.*.test.ts`，主题包括：

- builtin runtime 合并。
- 设备工具权限和管线。
- 禁用工具。
- 文件处理。
- headless 默认审批。
- memory。
- model override。
- resume 和 resumeApproval。
- threadId。
- topic history。
- Group / SubAgent task。

这说明 `aiAgent` 目录虽然文件少，但行为复杂，测试重点集中在执行编排、权限边界、恢复流程和上下文组装。

## 上下游关系

### 上游调用方

从调用方搜索结果看，`AiAgentService` 主要被这些模块使用：

- `src/server/routers/lambda/aiAgent.ts`：tRPC lambda 路由，提供前端调用的 `aiAgent.execAgent` 等能力。
- `src/server/agent-hono/handlers/execAgent.ts`：REST / Hono handler，可能用于 `/api/agent` 类接口。
- `src/server/routers/lambda/agentNotify.ts`：通知或继续执行相关入口，会调用 `execAgent`。
- `src/server/services/bot/AgentBridgeService.ts`、`BotMessageRouter.ts`：Bot 平台消息进入 Agent 执行。
- `src/server/services/taskRunner/index.ts`：定时任务或任务执行入口。
- `src/server/services/agentEvalRun/index.ts`：评测运行入口。
- 测试文件：直接实例化 `AiAgentService` 验证各种场景。

所以它是多个触发源共用的“统一执行入口”。无论用户从 Web 聊天、Bot 消息、任务、评测、REST API 进入，最终都要走这里进行上下文和 operation 创建。

### 下游依赖

`AiAgentService` 往下依赖的系统很多：

- 数据库模型：`AgentModel`、`MessageModel`、`TopicModel`、`ThreadModel`、`PluginModel`、`TaskModel`、`UserModel` 等。
- Agent Runtime：`AgentRuntimeService.createOperation(...)` 是标准 LLM Agent 执行路径的最后交接点。
- Mecha / 工具引擎：`createServerAgentToolsEngine(...)` 负责根据 Agent 配置、模型能力、插件、设备状态生成工具集合。
- 文件与文档服务：`FileService`、`DocumentService`、`AgentDocumentsService`。
- 设备网关：`deviceProxy` 查询在线设备、系统信息，或分发异构 Agent 到本地设备。
- 异构 Agent：`HeterogeneousAgentService`、`spawnHeteroSandbox`、`cloudHeteroContext`。
- Agent Signal：`enqueueAgentSignalSourceEvent(...)` 用作反馈、自迭代治理侧通道。
- hooks：`hookDispatcher` 和 operation hooks 用于子 Agent 生命周期、调用前后事件、完成回调等。

换句话说，`aiAgent` 不是模型适配层，也不是 UI 层；它是服务端 Agent 执行的“大脑前置编排器”。

## 运行/调用流程

一次普通 `execAgent` 的主流程可以按下面顺序理解：

1. **校验入口参数**

   必须有 `agentId` 或 `slug`。如果是恢复执行，还要求有 `parentMessageId`、`appContext.topicId`，并校验父消息属于当前 topic / thread / session。

2. **读取 Agent 配置**

   通过 `AgentService.getAgentConfig(identifier)` 读取配置。随后可能应用 `model`、`provider` 覆盖，例如任务配置临时指定模型。

3. **合并 builtin agent runtime config**

   如果 Agent 是内置 Agent slug，会通过 `getAgentRuntimeConfig(...)` 合并运行时 `systemRole` 和 plugins。页面场景会注入 `PageAgentIdentifier`，任务场景会注入 `TaskIdentifier`。

4. **创建或复用 topic**

   如果 `appContext.topicId` 不存在，就创建新 topic。topic metadata 可能包含 `cronJobId`、`taskId`、`botContext`、`boundDeviceId`、初始仓库或工作目录等信息。

5. **异构 Agent 早退路径**

   如果模型或配置表明这是 `claude-code` / `codex`，它不会继续走标准 LLM 工具运行管线，而是：

   - 创建用户消息和助手占位消息。
   - 生成 operation JWT。
   - 读取 topic 中的 repo 信息。
   - 尝试解析 GitHub token。
   - 构造云端异构 Agent system context。
   - 如果指定了 `deviceId`，通过 `deviceProxy.dispatchAgentRun(...)` 发到用户设备。
   - 否则通过 `spawnHeteroSandbox(...)` 启动云沙箱。
   - 返回 `operationId`、消息 ID、topic ID、Gateway token。

6. **读取用户设置和记忆开关**

   加载用户 settings，确定 memory 是否启用，并读取 timezone。Agent 级 memory 配置优先于用户级设置。

7. **工具发现与过滤**

   如果没有 `disableTools`，会读取已安装插件、模型能力、LobeHub Skills、Klavis manifests，然后创建 `toolsEngine`。

   这里会动态加入一些工具：

   - prompt 中出现 `refer_topic` 时加入 `lobe-topic-reference`。
   - Bot 会话加入 `MessageToolIdentifier`。
   - 模型不支持 vision/video 但输入或历史里有图片/视频，且配置了 visual understanding provider 时，加入 `LobeAgentManifest.identifier`。
   - 自迭代能力开启时可能注入 self-feedback intent 工具。
   - Response API 传入的 `functionTools` 会作为 `lobe-client-fn` 注入。

8. **设备权限判定**

   调用 `resolveDeviceAccessPolicy({ botContext })` 得到 `canUseDevice` 和 `reason`。这个结果会影响多个位置：

   - `createServerAgentToolsEngine` 的 enable gate。
   - `buildAllowedBuiltinTools` 对 builtin tools 的物理过滤。
   - `toolManifestMap` ingest 过程是否允许设备工具 manifest 进入。
   - 是否向 `RemoteDeviceManifest` 注入在线设备列表 system prompt。
   - 是否设置 `activeDeviceId`。
   - 最终传给 `AgentRuntimeService.createOperation` 的 `deviceAccessPolicy`。

   这是一条贯穿始终的安全链路。

9. **加载历史消息**

   如果提供 `existingMessageIds`，只取这些消息；如果是已有 topic 的后续消息，则加载该 topic 下历史；否则历史为空。读取时会用 `postProcessUrl` 把文件路径转换为可访问 URL。

10. **处理附件**

   外部 `files` 会通过 `ingestAttachment` 上传。已有 `fileIds` 会查表解析。图片、视频、普通文件分别进入 `imageList`、`videoList`、`fileList`。普通文件还会通过 `DocumentService.parseFile(...)` 解析文本内容。

11. **创建消息记录**

   非 resume 场景创建用户消息。随后创建助手消息占位，内容为 `LOADING_FLAT`，用于 UI 立刻显示执行中状态。

12. **构造 runtime initialContext**

   包含：

   - `assistantMessageId`
   - `parentMessageId`
   - 当前用户输入
   - tools
   - session 信息
   - 页面文档上下文
   - task manager 默认 assignee 上下文
   - resumeApproval 对应的 `human_approved_tool` 或继续反馈状态

13. **构造 operationSkillSet**

   使用 `SkillEngine` 合并 builtin skills 和用户 DB skills，再根据 Agent 已启用插件生成 operation 级技能集合。

14. **创建 operation**

   调用：

   ```ts
   this.agentRuntimeService.createOperation({...})
   ```

   传入 Agent 配置、模型配置、初始消息、工具集合、hooks、用户记忆、设备策略、Bot 上下文、eval 上下文等。成功后会把 `runningOperation` 写入 topic metadata，并返回执行结果。失败时会把助手占位消息更新为错误消息，避免 UI 卡在 loading。

15. **Group / SubAgent 特殊流程**

   `execGroupAgent` 先创建带 `groupId` 的 topic，再调用 `execAgent`。

   `execSubAgentTask` 会先创建 `ThreadType.Isolation` 线程，把状态设为 `Processing`，然后以 `threadId` 放进 `appContext` 调用 `execAgent`。它还注册 hooks，在每一步和完成时更新 thread metadata、token、工具调用数、成本、错误、完成时间等。

## 小白阅读顺序

1. 先读 `deviceAccessPolicy.ts`

   这个文件短，而且能快速理解本目录非常重视的安全边界：Bot 调用和一方 UI 调用在设备工具权限上是不一样的。

2. 再读 `deviceToolRegistry.ts`

   理解“设备工具”具体指什么，以及为什么要在 manifest 进入工具发现前就过滤掉。

3. 再读 `ingestAttachment.ts`

   这个文件逻辑线性，适合理解附件从外部平台进入 LobeHub 文件系统的过程。

4. 然后读 `index.ts` 的构造函数和 `execAgent` 开头

   重点看它初始化了哪些 model / service，以及 `InternalExecAgentParams` 支持哪些输入。不要一开始就陷入所有分支。

5. 接着按注释编号读 `execAgent`

   代码里有很多步骤注释，例如获取 Agent 配置、topic 创建、工具发现、文件处理、消息创建、operation 创建。建议把它当成“流水线”读，而不是当成普通函数逐行硬啃。

6. 最后读 `execGroupAgent`、`execSubAgentTask`、`interruptTask`

   这些方法都是围绕 `execAgent` 扩展出来的特殊场景。理解普通执行后，再看它们会轻松很多。

7. 需要验证行为时看 `__tests__`

   测试文件名已经按场景命名，例如 `execAgent.resumeApproval.test.ts`、`execAgent.deviceToolPipeline.test.ts`、`execAgent.files.test.ts`。想理解某个边界条件时，直接找对应测试比从大文件里定位更快。

## 常见误区

1. **误以为 `AiAgentService` 只是调用模型**

   实际上它并不直接做模型请求。它准备上下文、消息、工具和运行参数，最后交给 `AgentRuntimeService`。模型调用细节在更下游的 runtime / model runtime 中。

2. **误以为工具权限只在执行时判断**

   设备工具不是只靠执行时拦截。`deviceToolRegistry.ts` 会在工具 manifest 暴露给工具引擎和 activator 前做物理过滤。这样可以防止模型通过显式激活绕过 enable checker。

3. **误以为 Bot 消息天然能使用本机工具**

   Bot 场景必须经过 `resolveDeviceAccessPolicy`。外部发送者默认不能访问用户设备。只有 owner、特定个人作用域平台或一方 UI 调用才会允许。

4. **误以为 `RemoteDeviceManifest` 的 system prompt 总会注入设备列表**

   不会。只有 `canUseDevice` 为真且 manifest 存在时，才会把在线设备列表注入 systemRole。否则外部 Bot 发送者甚至不应该看到设备清单。

5. **误以为 `files` 和 `fileIds` 是一回事**

   `files` 是外部传入的新附件，可能是 buffer 或 URL，需要上传和建记录；`fileIds` 是已经存在于文件表中的附件引用，需要查表、解析 URL、补充内容。两条路径最后都会合并到 `imageList`、`videoList`、`fileList`。

6. **误以为 resume 会创建新的用户消息**

   `effectiveResume` 为真时不会创建新的用户消息，而是基于已有父消息继续。`resumeApproval` 还会先更新目标工具消息的审批状态，再构造特殊的 initialContext。

7. **误以为 Group Agent 和 SubAgent 是独立执行系统**

   它们最终仍然委托给 `execAgent`。区别在于 Group Agent 会带 `groupId`，SubAgent 会创建隔离 `Thread`，并通过 hooks 持续更新线程状态。

8. **误以为异构 Agent 也走标准 runtime**

   `claude-code`、`codex` 这类异构 Agent 会在 `execAgent` 中提前分流，走设备网关或云沙箱。它仍然创建 topic 和消息，但不会继续走标准工具引擎与 `AgentRuntimeService.createOperation` 的普通路径。

9. **误以为 `disableTools` 只禁用插件**

   `disableTools` 会跳过整个工具发现流程，包括插件、系统 manifest、技能工具等。它常用于评测或基准场景，不等同于只禁用某一个插件。

10. **误以为错误只会抛给调用方**

   operation 创建失败时，服务会更新助手占位消息的 `error` 字段，让前端对话里能看到失败原因。这是为了避免用户界面只留下一个永远 loading 的助手消息。
