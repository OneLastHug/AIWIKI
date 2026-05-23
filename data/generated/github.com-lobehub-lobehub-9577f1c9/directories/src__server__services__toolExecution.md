# 目录：src/server/services/toolExecution

## 它负责什么

`src/server/services/toolExecution` 是服务端工具执行层，负责把 Agent 运行过程中产生的 `ChatToolPayload` 转成真正的服务端调用结果。它位于 `src/server/services` 下，属于后端服务层：上游通常是 Agent Runtime 的执行模块，下游则可能是内置工具运行时、MCP 服务、Market 服务、Klavis 服务、设备网关或其他业务服务。

这个目录的核心职责可以概括为三类。第一，统一执行入口：`ToolExecutionService.executeTool` 根据工具类型分发到 `mcp` 或 `builtin` 路径，并统一补充 `executionTime`、错误结构、结果截断等通用行为。第二，内置工具分发：`BuiltinToolsExecutor` 负责解析参数、识别工具来源，并把调用转到 Market、Klavis 或 `serverRuntimes` 注册表。第三，运行时集合：`serverRuntimes` 下面承载一组服务端可执行的 builtin tool runtime，例如浏览网页、计算器、记忆、任务、知识库、设备代理、agent 管理等。

根据当前片段推断，这里不是“工具定义中心”，也不是 UI 工具面板。工具 manifest、客户端展示、builtin tool 包、MCP 配置可能分散在 `packages/builtin-tool-*`、`packages/builtin-tools`、`src/tools`、`src/server/services/mcp` 等位置；本目录更像“工具调用落到服务端后的执行中枢”。

## 直接子目录地图

`src/server/services/toolExecution/__tests__` 存放该服务层的单元测试，覆盖主入口、内置工具执行、设备代理、错误分类、结果归档、`lh` 命令预处理等行为。它是理解边界条件和失败语义的好入口。

`src/server/services/toolExecution/serverRuntimes` 是内置服务端工具 runtime 的注册和实现区。根部的 `index.ts` 维护 runtime 注册表，其他文件按工具域拆分，例如 `webBrowsing.ts`、`calculator.ts`、`memory.ts`、`agentManagement.ts`、`knowledgeBase.ts`、`remoteDevice.ts`、`localSystem.ts`、`skills.ts`、`task.ts`、`lobeAgent.ts` 等。

`src/server/services/toolExecution/serverRuntimes/__tests__` 是 runtime 级测试，主要验证具体工具域的参数处理、上下文依赖和代理调用。

`src/server/services/toolExecution/serverRuntimes/message` 是消息发送类 runtime 的子域。它下面还有 `adapters`，从邻近引用看，`src/server/services/bot/platforms/*/service.ts` 会使用这里的 adapter 类型或错误类，因此它承担跨平台消息工具与 bot 平台服务之间的适配角色。

## 关键入口

最重要的入口是 `src/server/services/toolExecution/index.ts`。这里导出 `ToolExecutionService`，核心方法是 `executeTool(payload, context)`。它读取 `payload.identifier`、`payload.apiName`、`payload.type`，当 `type` 是 `mcp` 时走 `executeMCPTool`，其他情况默认走 `BuiltinToolsExecutor.execute`。执行完成后，它会统一计算耗时、按 `context.toolResultMaxLength` 截断结果，并通过 `classifyToolError` 规范化失败信息。

`src/server/services/toolExecution/builtin.ts` 是 builtin 分发入口。`BuiltinToolsExecutor.execute` 先解析 `payload.arguments`，如果 JSON 损坏或疑似截断，会返回明确的 `INVALID_JSON_ARGUMENTS` 或 `TRUNCATED_ARGUMENTS`，避免把空对象传给工具造成误导。随后它根据 `payload.source` 分流：`lobehubSkill` 交给 `MarketService.executeLobehubSkill`，`klavis` 交给 `KlavisService.executeKlavisTool`，普通 builtin 则进入 `serverRuntimes` 注册表。

`src/server/services/toolExecution/serverRuntimes/index.ts` 是 runtime 注册入口。它导入所有 runtime registration，通过 `registerRuntimes` 放入 `serverRuntimeFactories`，并暴露 `getServerRuntime`、`hasServerRuntime`、`getServerRuntimeIdentifiers`。新增一个服务端 builtin runtime 时，通常需要在这里注册。

`src/server/services/toolExecution/types.ts` 定义执行上下文和结果契约，例如 `ToolExecutionContext`、`ToolExecutionResult`、`ToolExecutionResultResponse`、`IToolExecutor`。阅读任何 runtime 前都应先了解这些类型，因为 runtime 方法最终都要返回统一的结果形状。

辅助入口还包括 `archiveToolResult.ts`、`deviceProxy.ts`、`preprocessLhCommand.ts`、`errorClassification.ts`。其中 `archiveToolResultIfNeeded` 被 Agent Runtime 和 `src/server/routers/lambda/aiChat.ts` 调用，用于必要时归档工具结果；`deviceProxy` 负责把工具调用转发到设备网关；`preprocessLhCommand` 用于处理特定 `lh` 命令；`errorClassification` 为工具失败提供可重试性或错误类别判断的基础。

## 主流程位置

服务端工具执行的主链路大致是：

Agent 运行层在 `src/server/services/agentRuntime/AgentRuntimeService.ts` 中创建 `ToolExecutionService` 和 `BuiltinToolsExecutor`，并把它们交给运行模块。真正触发工具执行的位置在 `src/server/modules/AgentRuntime/RuntimeExecutors.ts`。这里会构造 `chatToolPayload`，调用 `toolExecutionService.executeTool(chatToolPayload, context)`，并围绕失败类型做重试、流式事件写入、结果归档等处理。

进入 `ToolExecutionService.executeTool` 后，主流程先按工具类型分流。`mcp` 类型调用 `executeMCPTool`：普通 MCP 走 `mcpService.callTool`，cloud MCP 会通过 `DiscoverService.callCloudMcpEndpoint` 调云端网关，并用 `contentBlocksToString` 把 MCP content blocks 转成字符串结果。`builtin` 类型进入 `BuiltinToolsExecutor.execute`：先解析参数，再按 source 或 identifier 分发到 Market、Klavis 或 `serverRuntimes`。

普通 builtin 的核心落点是 `serverRuntimes/index.ts` 的 `getServerRuntime(identifier, context)`。runtime factory 可能是预实例化对象，也可能根据本次 `ToolExecutionContext` 创建实例。拿到 runtime 后，执行器按 `apiName` 调用对应方法，即 `runtime[apiName](args, context)`。因此 `identifier` 负责定位工具域，`apiName` 负责定位工具域里的具体动作。

设备相关还有一条旁路。`src/server/services/toolExecution/deviceProxy.ts` 被 `localSystem.ts`、`skills.ts`、`src/server/services/aiAgent/index.ts`、`src/server/routers/lambda/device.ts` 等使用，用于把某些工具调用转给远端或本地设备能力执行。根据当前片段推断，这类调用仍返回 `ToolExecutionResult` 风格的数据，以便上游 Agent 流程继续处理。

## 推荐阅读顺序

1. 先读 `src/server/services/toolExecution/types.ts`，掌握 `ToolExecutionContext` 和返回值结构。
2. 再读 `src/server/services/toolExecution/index.ts`，理解 `ToolExecutionService.executeTool` 的统一分流、截断和错误规范化。
3. 继续读 `src/server/services/toolExecution/builtin.ts`，看 builtin 工具如何解析参数、识别 source，并进入 runtime 注册表。
4. 然后读 `src/server/services/toolExecution/serverRuntimes/index.ts`，建立 identifier 到 runtime factory 的地图。
5. 选择一两个代表性 runtime 阅读即可，例如 `calculator.ts` 适合理解简单工具，`webBrowsing.ts` 或 `cloudSandbox.ts` 适合理解外部能力，`remoteDevice.ts`、`localSystem.ts` 适合理解设备代理。
6. 最后回到调用方 `src/server/modules/AgentRuntime/RuntimeExecutors.ts`，把工具执行放回 Agent loop、重试、流式消息和归档流程中理解。

## 常见误区

不要把 `serverRuntimes` 理解成所有工具的定义来源。它只是“服务端可执行 runtime 注册区”，工具 manifest、插件市场、MCP 配置、客户端工具展示可能在其他目录。

不要忽略 `payload.source`。同样是 builtin，`lobehubSkill`、`klavis` 和普通 server runtime 的执行路径不同；直接按 `identifier` 去 `serverRuntimes` 查，可能会漏掉 Market 或 Klavis 工具。

不要把 `apiName` 当成文件名。执行器最终调用的是 runtime 对象上的方法：`runtime[apiName]`。一个 runtime 文件可能提供多个工具动作。

不要绕过 `ToolExecutionService.executeTool` 直接调用 runtime，除非是非常明确的内部场景。主入口统一处理耗时、错误分类、结果截断和 MCP/builtin 分流，绕过它容易导致上游 Agent 收到不一致的结果结构。

不要把工具失败都看成异常抛出。很多失败会被包装成 `{ success: false, content, error }` 返回，Agent Runtime 再根据错误类别决定是否重试或继续。阅读测试时也应关注返回对象，而不只是 `throw`。

不要忽略 `context`。`ToolExecutionContext` 中的 `userId`、`topicId`、`agentId`、`toolManifestMap`、`toolResultMaxLength`、设备信息和运行时依赖会影响多个 runtime 的行为；很多工具不是纯函数式调用。
