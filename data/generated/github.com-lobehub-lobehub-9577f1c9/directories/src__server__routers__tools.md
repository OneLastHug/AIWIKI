# 目录：src/server/routers/tools

## 它负责什么

`src/server/routers/tools` 是 LobeHub 后端里“工具能力”的 TRPC 路由聚合目录。它不是某一个单独工具的实现，而是把多类工具调用入口统一挂到 `toolsRouter` 下，供前端、Agent 运行时或其他客户端通过 `/trpc/tools/...` 访问。

从当前目录能看到它主要负责四类能力：

1. `mcp`：直连 MCP Server，包括 `http` / `stdio` 两类连接参数，支持读取 manifest、列出 tools/resources/prompts、调用 MCP tool。
2. `market`：调用 LobeHub Market 相关工具能力，包括 Cloud MCP Gateway、沙箱内置工具执行、文件导出上传、LobeHub Skill provider 连接和调用。
3. `search`：搜索与网页抓取能力的后端封装，转发到 `searchService`。
4. `klavis`：接入 Klavis Strata MCP 服务，列出工具、查询 server 工具、调用 Klavis tool。
5. `_helpers`：目前主要是 `scheduleToolCallReport`，用于工具调用后异步上报调用统计。

目录入口是 `src/server/routers/tools/index.ts`，它导出：

```ts
export const toolsRouter = router({
  healthcheck: publicProcedure.query(() => "i'm live!"),
  klavis: klavisRouter,
  market: marketRouter,
  mcp: mcpRouter,
  search: searchRouter,
});
```

因此外部看到的是一个命名空间式 API：`tools.mcp.*`、`tools.market.*`、`tools.search.*`、`tools.klavis.*`。

## 关键组成

`index.ts` 是聚合入口。它从 `@/libs/trpc/lambda` 引入 `router` 和 `publicProcedure`，再把四个子 router 合并为 `toolsRouter`。`healthcheck` 是无需登录的健康检查接口，用来验证 tools TRPC 服务是否在线。

`mcp.ts` 负责普通 MCP 调用。它定义了两种 MCP client 参数：

- `httpParamsSchema`：包含 `type: 'http'`、`url`、`name`、`auth`、可选 `headers`。
- `stdioParamsSchema`：包含 `type: 'stdio'`、`command`、`name`、可选 `args`。

两者通过 `mcpClientParamsSchema` 合并。`checkStdioEnvironment` 会阻止 Web 环境调用 `stdio` MCP，因为 `stdio` 只适合桌面端或本地进程环境。`mcpProcedure` 使用 `authedProcedure`，并叠加 `serverDatabase`、`telemetry` 中间件，同时把 `FileService` 注入 `ctx`，用于处理工具返回内容中的文件或图片块。

`mcpRouter` 暴露的核心接口包括：

- `getStreamableMcpServerManifest`：调用 `mcpService.getStreamableMcpServerManifest` 获取 streamable MCP manifest。
- `listTools`：列出 MCP 工具。
- `listResources`：列出 MCP resources。
- `listPrompts`：列出 MCP prompts。
- `callTool`：调用指定 MCP tool，并通过 `processContentBlocks` 处理返回内容；最后用 `scheduleToolCallReport` 异步上报调用记录。

`market.ts` 是这个目录里最复杂的文件。它先构造了 `marketToolProcedure`，叠加登录、数据库、telemetry、Market 用户信息等中间件，并向 `ctx` 注入：

- `DiscoverService`
- `FileService`
- `MarketService`
- `UserModel`

它还定义了两类 LobeHub Skill procedure：

- `lobehubSkillBaseProcedure`：带 `marketSDK`，但不强制 Market 授权。
- `lobehubSkillAuthProcedure`：在 base 基础上叠加 `requireMarketAuth`，要求授权后才能调用。

`marketRouter` 的主要接口包括：

- `callCloudMcpEndpoint`：通过 `DiscoverService.callCloudMcpEndpoint` 调用云端 MCP Gateway。
- `execInSandbox`：通过 Market 的 `plugins.runBuildInTool` 在沙箱中执行内置工具，如 `execScript`、`runCommand`。
- `callCodeInterpreterTool`：旧接口，标记为 deprecated，内部复用 `execInSandboxHandler`。
- `exportAndUploadFile`：从沙箱导出文件，上传到 S3，再通过 `FileService.createFileRecord` 创建持久文件记录。
- `connectListProviders` / `connectListTools`：列出 LobeHub Skill provider 和 provider 下的 tools。
- `connectGetAuthorizeUrl` / `connectGetStatus` / `connectRefresh` / `connectRevoke` / `connectGetAllHealth` / `connectListConnections`：处理 provider 授权、连接状态、刷新、撤销、健康检查。
- `connectCallTool`：调用某个 provider 下的 LobeHub Skill tool。

`search.ts` 是轻量封装，`searchRouter` 只有三个接口：

- `query`：调用 `searchService.query(query, optionalParams)`。
- `webSearch`：调用 `searchService.webSearch(input)`。
- `crawlPages`：调用 `searchService.crawlPages(input)`，支持指定 `browserless`、`exa`、`firecrawl`、`jina`、`naive`、`search1api`、`tavily` 等实现。

`klavis.ts` 负责 Klavis 集成。它用 `getKlavisClient()` 构造客户端，并在 `klavisProcedure` 里注入 `ctx.klavisClient`。核心接口包括：

- `getTools`：公开接口，根据 `serverName` 获取 Klavis server 的工具列表。
- `listTools`：登录后根据 `serverUrl` 列出 Strata server 可用工具。
- `callTool`：调用 Klavis Strata server 上的工具，并用 `MCPService.processToolCallResult` 转成统一的 MCP 工具调用结果格式。

`_helpers/scheduleToolCallReport.ts` 是工具调用统计上报工具。它通过 `next/server` 的 `after()` 在响应发送后执行上报，避免阻塞主请求。它会记录调用耗时、请求大小、响应大小、是否成功、错误码、错误信息、工具名、插件标识、MCP 类型、App 版本等，然后调用 `DiscoverService.reportCall(reportData)`。

## 上下游关系

上游入口是 Next.js TRPC route。当前片段中可以看到 `src/app/(backend)/trpc/tools/[trpc]/route.ts` 引用了 `toolsRouter`，并把它作为 `/trpc/tools/[trpc]` 的后端 router。也就是说，这个目录本身不直接处理 HTTP 请求，而是提供给 TRPC handler 挂载。

中游是 `@/libs/trpc/lambda` 提供的过程和中间件体系：

- `router`：组合 TRPC router。
- `publicProcedure`：无需登录的 procedure。
- `authedProcedure`：需要登录用户上下文的 procedure。
- `serverDatabase`：把服务端数据库注入上下文。
- `telemetry`：注入 telemetry 开关、Market access token 等上报相关上下文。
- `marketUserInfo` / `marketSDK` / `requireMarketAuth`：处理 LobeHub Market SDK 和用户授权信息。

下游主要是服务层、模型层和外部系统：

- `mcpService`：实际执行 MCP list/call/manifest 逻辑。
- `MCPService.processToolCallResult`：把外部工具返回结果转成统一结构。
- `processContentBlocks` / `contentBlocksToString`：处理工具返回的 text/image/file 等 content block。
- `searchService`：执行搜索和网页抓取。
- `DiscoverService`：调用 Market Discover / Cloud MCP Gateway / 上报调用记录。
- `MarketService`：访问 Market 插件和沙箱工具能力。
- `FileService`、`FileModel`、`FileS3`：处理文件上传、S3 元数据、持久文件记录。
- `AgentSkillModel`：根据已激活 skill 查找 zip 包文件 hash，用于给沙箱执行注入 `skillZipUrls`。
- `getKlavisClient`：连接 Klavis 外部 API。
- `UserModel`：读取用户 Market access token 等状态。

根据当前片段推断，前端或 Agent 运行时调用工具时，多数不会直接接触 service/model，而是通过 TRPC client 调用 `tools.mcp.callTool`、`tools.market.execInSandbox`、`tools.search.webSearch` 等接口，由这里完成鉴权、参数校验、上下文注入、错误转换和上报。

## 运行/调用流程

一个普通 MCP tool 调用大致是：

1. 客户端调用 `tools.mcp.callTool`，传入 `params`、`toolName`、`args`、可选 `meta`。
2. `mcpProcedure` 确认用户已登录，注入数据库、telemetry 和 `FileService`。
3. `checkStdioEnvironment` 判断如果是 `stdio` 类型，当前必须是 desktop 环境。
4. router 构造 `boundProcessContentBlocks`，把 `FileService` 绑定到内容处理函数。
5. 调用 `mcpService.callTool`，由 service 层实际连接 MCP server 并执行 tool。
6. 成功时返回结果；失败时记录 `CALL_FAILED` 和错误信息后继续抛出错误。
7. `finally` 中调用 `scheduleToolCallReport`，在响应之后异步上报调用统计。

一个 Market 沙箱工具调用大致是：

1. 客户端调用 `tools.market.execInSandbox`，传入 `toolName`、`params`、`topicId`、可选 `userId`。
2. `marketToolProcedure` 注入 `DiscoverService`、`MarketService`、`FileService`、`UserModel`。
3. `execInSandboxHandler` 检查是否是 `execScript` 或 `runCommand`，如果命令里有 LobeHub CLI 相关命令，会动态导入 `preprocessLhCommand` 做预处理。
4. 如果是 `execScript` 且带 `activatedSkills`，会通过 `AgentSkillModel` 和 `FileModel` 查找 skill zip 文件，再用 `FileService.getFullFileUrl` 转成可访问 URL，注入到 `skillZipUrls`。
5. 调用 `ctx.marketService.market.plugins.runBuildInTool(...)`。
6. 如果 Market 返回 token 过期、未授权等错误，会转换成 `TRPCError({ code: 'UNAUTHORIZED' })`，让前端触发重新授权流程。
7. 成功时返回 `{ success: true, result, sessionExpiredAndRecreated }`；普通失败时返回 `{ success: false, error, result: null }`。

一个 Cloud MCP 调用大致是：

1. 客户端调用 `tools.market.callCloudMcpEndpoint`。
2. 如果启用了 trusted client，就不需要用户 access token；否则从 `UserModel.getUserState` 里读取 `settings.market.accessToken`。
3. 调用 `DiscoverService.callCloudMcpEndpoint`。
4. 对返回的 content block 做文件/图片处理，并转成字符串内容。
5. 返回 `{ content, state, success: true }`。
6. 最后同样通过 `scheduleToolCallReport` 异步上报。

一个搜索调用更简单：

1. 客户端调用 `tools.search.query`、`tools.search.webSearch` 或 `tools.search.crawlPages`。
2. router 只做 zod 参数校验。
3. 直接转发给 `searchService`。
4. 返回 service 层结果。

Klavis 工具调用流程是：

1. 客户端调用 `tools.klavis.callTool`，传入 `serverUrl`、`toolName`、可选 `toolArgs`。
2. `klavisProcedure` 注入 `getKlavisClient()`。
3. 调用 `ctx.klavisClient.mcpServer.callTools`。
4. 如果失败，返回统一的 `{ success: false, content, state }`。
5. 如果成功，用 `MCPService.processToolCallResult` 转成统一 MCP 结果。

## 小白阅读顺序

1. 先看 `src/server/routers/tools/index.ts`。这个文件最短，能快速建立“toolsRouter 是四个子 router 的聚合”的整体印象。
2. 再看 `src/server/routers/tools/search.ts`。它几乎没有复杂业务，只展示了 TRPC router 的基本模式：`procedure.input(z.object(...)).query/mutation(...)`。
3. 接着看 `src/server/routers/tools/mcp.ts`。重点理解 `mcpClientParamsSchema`、`checkStdioEnvironment`、`mcpProcedure`、`callTool` 四块。这里能学到工具调用中的参数校验、环境限制、文件内容处理和调用上报。
4. 然后看 `src/server/routers/tools/_helpers/scheduleToolCallReport.ts`。理解为什么上报放在 `after()` 里，以及上报数据有哪些字段。
5. 再看 `src/server/routers/tools/klavis.ts`。它是外部工具平台适配的一个简单例子，能看到如何把第三方 API 的返回统一成 MCP tool result。
6. 最后看 `src/server/routers/tools/market.ts`。这个文件业务最多，建议分段读：先看 procedure 和 schema，再看 `execInSandboxHandler`，然后看 `callCloudMcpEndpoint`，最后看一组 `connect*` 接口和 `exportAndUploadFile`。

如果只想理解“工具调用主链路”，优先读 `mcp.ts` 的 `callTool` 和 `market.ts` 的 `execInSandboxHandler`。如果只想理解“工具调用统计”，优先读 `scheduleToolCallReport.ts` 以及 `mcp.ts` / `market.ts` 中的 `finally` 块。

## 常见误区

1. 不要把 `toolsRouter` 理解成工具实现本身。它主要是 API 编排层，真正执行逻辑大多在 `server/services/*`、Market SDK、MCP service、Klavis client 或 S3 模块里。
2. `mcp.callTool` 和 `market.callCloudMcpEndpoint` 都是“调用工具”，但路径不同。前者直接连 MCP client 参数指定的 server；后者走 LobeHub Market / Discover 的 Cloud MCP Gateway。
3. `stdio` MCP 不能在 Web 环境使用。`checkStdioEnvironment` 明确在非 desktop 环境抛 `BAD_REQUEST`，所以调试 stdio MCP 时要关注运行环境。
4. `callCodeInterpreterTool` 仍然存在，但已经标记 deprecated。新代码应理解为它只是兼容旧调用，实际逻辑复用 `execInSandboxHandler`。
5. `scheduleToolCallReport` 不会阻塞当前请求。它使用 `after()` 在响应后执行；因此调用成功返回给客户端，不代表上报一定成功。
6. `market.ts` 里的 `UNAUTHORIZED` 不只是普通登录失败，也可能表示 Market token 过期、provider 未连接、需要重新授权。前端通常要据此触发授权流程。
7. `searchRouter` 看起来像普通查询接口，但 `crawlPages` 是 `mutation`。这是因为它会触发抓取动作，不只是读取缓存数据。
8. `connectListProviders` 使用的是 `lobehubSkillBaseProcedure`，注释说 provider 列表这类接口可以不强制 Market 授权；而 `connectCallTool`、`connectGetStatus`、`connectRefresh` 等使用 `lobehubSkillAuthProcedure`，需要授权。
9. `exportAndUploadFile` 不是简单生成下载链接。它会生成 S3 预签名上传 URL，让沙箱执行 `exportFile` 上传，再创建持久文件记录，最后返回永久 `/f/:id` 风格 URL。
10. `processContentBlocks` 很关键。工具返回里可能包含图片、文件等内容块，router 会借助 `FileService` 做上传或转换；如果只看返回字符串，容易忽略文件持久化这一层。
