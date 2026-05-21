# 文件：src/server/routers/tools/index.ts

## 它负责什么

这个文件是 `tools` 这组 tRPC 接口的总入口。它本身不直接实现复杂业务，而是把 `klavis`、`market`、`mcp`、`search` 四个子路由组装成一个命名空间 `toolsRouter`，再额外提供一个轻量的 `healthcheck`。

从职责上看，它更像“路由目录”而不是“服务实现”。真正的工具调用逻辑分散在同目录下的 `klavis.ts`、`market.ts`、`mcp.ts`、`search.ts` 中。

## 关键组成

1. `publicProcedure` 和 `router`
   - 来自 `@/libs/trpc/lambda`
   - `router({...})` 用来把多个子 router 合并成一个嵌套 API 树
   - `publicProcedure` 用来声明不需要登录的接口，这里只用于 `healthcheck`

2. `healthcheck`
   - `publicProcedure.query(() => "i'm live!")`
   - 作用是快速确认该 router 路径可用，属于最小可用性探针

3. 子路由挂载
   - `klavis: klavisRouter`
   - `market: marketRouter`
   - `mcp: mcpRouter`
   - `search: searchRouter`

4. 类型导出
   - `export type ToolsRouter = typeof toolsRouter`
   - 这个类型会被客户端类型定义直接引用，用于保证前后端 API 形状一致

## 上下游关系

上游是 tRPC 的后端路由系统。这个文件被挂到后端 HTTP 入口 `src/app/(backend)/trpc/tools/[trpc]/route.ts`，也就是说外部请求并不是直接进到 `toolsRouter`，而是先进入 Next.js 的 route handler，再转交给这个 router。

下游主要是四个子路由和它们依赖的 service 层：

- `searchRouter` -> `searchService`
- `mcpRouter` -> `mcpService`、`FileService`
- `klavisRouter` -> `getKlavisClient()`、`MCPService`
- `marketRouter` -> 市场相关的认证、数据库、文件、上报逻辑

客户端也依赖这里的类型。`src/libs/trpc/client/tools.ts` 会引用 `ToolsRouter`，用它生成或约束 tools 命名空间的前端调用类型。

根据当前片段推断，这个文件不是 `src/server/routers/lambda/index.ts` 的一部分，因为后者只聚合 `lambda` 命名空间；`toolsRouter` 是单独暴露给 `/trpc/tools` 的另一条路由线。

## 运行/调用流程

1. 客户端通过 tRPC 调用 `tools.xxx.yyy`
2. 请求进入 `src/app/(backend)/trpc/tools/[trpc]/route.ts`
3. 该 route 把请求分发到 `toolsRouter`
4. `toolsRouter` 根据命名空间路由到 `klavis`、`market`、`mcp` 或 `search`
5. 子路由再调用具体 service：
   - 搜索接口走 `searchService`
   - MCP 接口走 `mcpService`
   - Klavis 接口走外部 Klavis 客户端和 `MCPService`
   - Market 接口走数据库、市场 SDK、文件服务、遥测和任务上报
6. 返回结果再沿 tRPC 链路回到前端

其中 `healthcheck` 是最短路径：不经过认证、不进子服务，只返回固定字符串。

## 小白阅读顺序

1. 先看 `src/server/routers/tools/index.ts`
   - 先建立“这个命名空间下面有什么”的整体印象

2. 再看 `src/app/(backend)/trpc/tools/[trpc]/route.ts`
   - 理解它是怎样被暴露成 HTTP API 的

3. 再按需要深入子路由
   - `search.ts`：最容易理解，直接调用 `searchService`
   - `mcp.ts`：看参数校验、桌面环境限制、工具调用上报
   - `klavis.ts`：看外部 MCP server 交互
   - `market.ts`：这是最重的一块，包含认证、数据库、文件和遥测

4. 最后看 `src/libs/trpc/client/tools.ts`
   - 理解前端是如何依赖 `ToolsRouter` 类型的

## 常见误区

1. 把这个文件当成业务实现文件
   - 它主要是聚合路由，不是核心逻辑本体

2. 以为 `healthcheck` 代表整套 tools 服务已经可用
   - 它只能说明这个路由树挂载成功，不能代表外部依赖都正常

3. 忽略子路由的边界
   - `toolsRouter` 只是入口，真正复杂逻辑在 `search.ts`、`mcp.ts`、`klavis.ts`、`market.ts`

4. 以为它和 `lambdaRouter` 是同一层挂载
   - 不是。`lambdaRouter` 是另一棵更大的路由树，这个文件属于独立的 `tools` 命名空间

5. 只看运行时逻辑，不看类型导出
   - `ToolsRouter` 对前端 tRPC 类型推导很关键，很多调用方其实是通过类型在消费它
