# 目录：src/server/services/toolExecution/serverRuntimes

## 它负责什么

`src/server/services/toolExecution/serverRuntimes` 是服务端内置工具的运行时注册与实现目录。它不直接负责所有工具执行，而是承担“builtin tool identifier 到服务端 runtime 对象”的映射，以及各类内置工具在服务端真正被调用时的处理逻辑。

从邻近上下文看，整体工具执行入口在 `src/server/services/toolExecution/index.ts` 的 `ToolExecutionService.executeTool`。当工具类型是 `builtin` 时，会交给 `src/server/services/toolExecution/builtin.ts` 中的 `BuiltinToolsExecutor.execute`。`BuiltinToolsExecutor` 再根据工具来源决定走市场服务、Klavis 服务，或进入本目录的 server runtime registry。因此，本目录可以理解为：LobeHub 自家内置工具在服务端落地执行的 runtime 集合。

这里的 runtime 覆盖的能力很广，包括网页浏览、云沙箱、计算器、知识库、文档、记忆、任务、消息、远程设备、本地系统、技能管理、用户交互、Agent 管理、Agent 执行等。它们共同暴露一种形态：按工具 `identifier` 注册 runtime，然后在执行时用 `apiName` 选择 runtime 上的具体方法。

## 直接子目录地图

当前目录的直接子目录很少，主体是扁平的 runtime 文件：

`src/server/services/toolExecution/serverRuntimes/__tests__`：运行时单元测试目录。这里按功能放置测试，例如 `memory.test.ts`、`message.test.ts`、`notebook.test.ts`、`remoteDevice.test.ts`、`skillManagement.test.ts` 等。它主要用于验证各 runtime 的参数处理、服务调用、错误分支和返回结构。

`src/server/services/toolExecution/serverRuntimes/message`：消息类工具的独立子模块。相比其他 runtime 的单文件实现，`message` 被拆成目录，说明其内部流程更复杂。该目录包含 `index.ts`、`MessageDispatcherService.ts`、`PlatformUnsupportedError.ts`，以及 `adapters/`。根据当前片段推断，`message` runtime 需要根据不同平台分发消息，因此抽出了 dispatcher、平台错误和 adapter 类型。

`src/server/services/toolExecution/serverRuntimes/message/adapters`：消息平台适配层，目前从文件树可见有 `types.ts`。它不是主入口，而是给 `message` runtime 内部提供平台适配抽象。

除此之外，大部分文件直接位于 `serverRuntimes` 根下，例如 `webBrowsing.ts`、`cloudSandbox.ts`、`calculator.ts`、`agentDocuments.ts`、`memory.ts`、`task.ts`、`lobeAgent.ts`、`knowledgeBase.ts` 等。这种结构表示每类工具 runtime 是相对独立的服务端适配模块。

## 关键入口

最重要的入口是 `src/server/services/toolExecution/serverRuntimes/index.ts`。它维护了一个 `serverRuntimeFactories`，类型是 `Map<string, ServerRuntimeFactory>`，用于把工具 `identifier` 映射到 runtime factory。文件里通过 `registerRuntimes([...])` 一次性注册所有 runtime，包括 `webBrowsingRuntime`、`cloudSandboxRuntime`、`calculatorRuntime`、`agentDocumentsRuntime`、`agentManagementRuntime`、`skillManagementRuntime`、`notebookRuntime`、`skillStoreRuntime`、`skillsRuntime`、`memoryRuntime`、`activatorRuntime`、`messageRuntime`、`localSystemRuntime`、`remoteDeviceRuntime`、`briefRuntime`、`taskRuntime`、`topicReferenceRuntime`、`userInteractionRuntime`、`credsRuntime`、`knowledgeBaseRuntime`、`webOnboardingRuntime`、`lobeAgentRuntime`、`selfFeedbackIntentRuntime`。

该入口对外暴露三个核心 API：

`getServerRuntime(identifier, context)`：按 `identifier` 获取 runtime。它调用对应 factory，并把 `ToolExecutionContext` 传进去。注释里明确说明它既支持预实例化 runtime，也支持依赖请求上下文的 runtime，例如需要 `topicId`、`userId` 的场景。

`hasServerRuntime(identifier)`：检查某个内置工具是否存在服务端 runtime。

`getServerRuntimeIdentifiers()`：返回所有已注册 runtime 的 identifier 列表，通常用于检查或调试注册状态。

另一个关键类型入口是 `src/server/services/toolExecution/serverRuntimes/types.ts`。它定义 `ServerRuntimeFactory` 和 `ServerRuntimeRegistration`。其中 `ServerRuntimeFactory` 接收 `ToolExecutionContext` 并返回 runtime；`ServerRuntimeRegistration` 包含 `identifier` 和 `factory`。这个类型很小，但定义了本目录所有 runtime 文件应遵循的注册协议。

## 主流程位置

主流程从本目录外部开始：

`src/server/services/toolExecution/index.ts` 的 `ToolExecutionService.executeTool` 接收 `ChatToolPayload` 和 `ToolExecutionContext`。它先根据 `payload.type` 区分工具类型：`mcp` 会走 `executeMCPTool`；`builtin` 或默认情况会走 `BuiltinToolsExecutor.execute`。执行完成后，这里还会统一计算 `executionTime`、截断过长结果、归一化错误结构。

进入 builtin 分支后，核心逻辑在 `src/server/services/toolExecution/builtin.ts` 的 `BuiltinToolsExecutor.execute`。它先解析 `payload.arguments`，如果 JSON 无效或被截断，会直接返回专门的错误结果，避免把空对象传给工具造成误导。然后按 `source` 分流：`lobehubSkill` 走 `MarketService.executeLobehubSkill`，`klavis` 走 `KlavisService.executeKlavisTool`。这两个分支不会进入本目录的 runtime registry。

当工具不是上述特殊来源时，`BuiltinToolsExecutor` 会调用 `hasServerRuntime(identifier)` 判断本目录是否注册了对应 runtime。如果没有，就抛出 `Builtin tool "... " is not implemented`。如果存在，则 `await getServerRuntime(identifier, context)` 获取 runtime，再检查 `runtime[apiName]` 是否存在，最后执行 `runtime[apiName](args, context)`。

因此，本目录的主流程可以概括为：

`ToolExecutionService.executeTool` 接收工具调用；
`BuiltinToolsExecutor.execute` 处理 builtin 工具；
`serverRuntimes/index.ts` 根据 `identifier` 找到 runtime factory；
runtime factory 生成 runtime 对象；
通过 `apiName` 调用 runtime 上的具体方法；
结果回到 `ToolExecutionService` 统一包装、截断和错误归一化。

具体业务主流程散落在各 runtime 文件中。根据当前文件名推断，`cloudSandbox.ts` 处理云沙箱执行，`webBrowsing.ts` 处理浏览能力，`memory.ts` 处理记忆工具，`task.ts` 处理任务工具，`agentDocuments.ts` 处理 Agent 文档，`lobeAgent.ts` 和 `lobeAgentPlan.ts` 与 Agent 调用及规划相关，`message/` 负责消息发送或分发类流程。

## 推荐阅读顺序

建议先读 `src/server/services/toolExecution/index.ts`，理解工具执行服务的总入口、`mcp` 与 `builtin` 的分流、执行结果如何被包装。

第二步读 `src/server/services/toolExecution/builtin.ts`，这里能看清 builtin 工具如何解析参数、如何处理 `lobehubSkill` 与 `klavis` 特殊来源，以及如何进入 server runtime registry。

第三步读 `src/server/services/toolExecution/serverRuntimes/types.ts` 和 `src/server/services/toolExecution/serverRuntimes/index.ts`。这两处定义了本目录的注册模型：每个 runtime 文件导出一个 `ServerRuntimeRegistration`，由中心 registry 汇总。

第四步按功能挑 runtime 读，不需要逐个展开。想理解简单模式，可以先看 `calculator.ts`、`webBrowsing.ts`、`memory.ts` 这类单文件 runtime；想理解上下文依赖和复杂服务调用，可以看 `cloudSandbox.ts`、`agentDocuments.ts`、`knowledgeBase.ts`、`lobeAgent.ts`；想理解多平台分发结构，再看 `message/index.ts` 和 `message/MessageDispatcherService.ts`。

最后读 `src/server/services/toolExecution/serverRuntimes/__tests__`。测试目录适合反向确认 runtime 的输入输出契约，尤其是错误返回、上下文依赖、服务 mock 和边界条件。

## 常见误区

不要把 `serverRuntimes` 当成所有工具的总入口。真正总入口是 `ToolExecutionService.executeTool`，本目录只负责一部分 builtin 工具的服务端 runtime。`mcp` 工具、`lobehubSkill` 来源工具、`klavis` 来源工具都有各自分支，不一定会进入这里。

不要以为每个文件都会被自动发现。当前注册是显式的，必须在 `src/server/services/toolExecution/serverRuntimes/index.ts` 的 `registerRuntimes([...])` 中加入对应 runtime，否则 `hasServerRuntime(identifier)` 会返回 false。

不要混淆 `identifier` 和 `apiName`。`identifier` 用来在 registry 中找到 runtime；`apiName` 用来在 runtime 对象上选择具体方法。缺 runtime 会报工具未实现，缺方法会报该工具的某个 API 未实现。

不要忽略 `ToolExecutionContext`。注释明确说明有些 runtime 是预实例化的，有些 runtime 需要按请求上下文创建。涉及 `userId`、`topicId`、工具 manifest、结果截断配置、用户态信息的能力，通常都要依赖这个 context。

不要只看 runtime 文件而跳过 `builtin.ts`。参数 JSON 解析、截断参数识别、特殊 source 分流、错误捕获都发生在进入 runtime 前。很多“工具为什么没调用到 runtime”的问题，原因其实在 `BuiltinToolsExecutor.execute` 的前置分支里。
