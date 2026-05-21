# 目录：src/libs/trpc/client

## 它负责什么

这个目录是前端侧 tRPC client 的统一出口，作用是把项目里几类不同的后端 RPC 访问方式收口成可直接调用的客户端对象。它不是业务层本身，而是“通信层适配器”：把 `@trpc/client`、`@trpc/react-query`、`superjson`、Electron 协议修正、认证 header 注入、错误分流这些细节封装起来，供上层服务和工具直接调用。

从导出结构看，[`index.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/libs/trpc/client/index.ts) 只是聚合出口：`asyncClient` 单独导出，`lambda.ts` 和 `tools.ts` 的内容整体透出。

## 关键组成

- [`async.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/libs/trpc/client/async.ts)：创建 `asyncClient`，只连到 `/trpc/async`，用 `httpBatchLink` 和 `superjson`，并通过 `withElectronProtocolIfElectron` 兼容桌面端协议。
- [`lambda.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/libs/trpc/client/lambda.ts)：这是最重的客户端。它同时导出 `lambdaClient`、`lambdaQuery`、`lambdaQueryClient`，用于普通业务 RPC 与 React Query 集成。
- [`tools.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/libs/trpc/client/tools.ts)：面向工具/市场相关接口，重点是 `toolsClient`，带有市场 401 事件分发逻辑。
- `index.ts`：只做 re-export，没有额外逻辑。

其中 `lambda.ts` 的核心特征有三点：一是 `errorHandlingLink` 会拦截 401 和 abort；二是 `splitLink` 按 procedure 名决定是否跳过 batching；三是 `headers` 和 `fetch` 都做了动态 import，避免循环依赖。

## 上下游关系

上游主要来自认证、环境判断和各类 store/service：

- `withElectronProtocolIfElectron` 负责把相对路径改成桌面端可用的协议形式。
- `createHeaderWithAuth` 提供带认证信息的请求头。
- `isDesktop` 决定是否绕开桌面端的一些 web 登录逻辑。
- `marketAuthEvents`、`useUserStore`、`useToolStore`、`image store` 等，是错误处理和 header 生成时的动态依赖。

下游则是具体业务服务和工具执行器：

- [`src/services/message/index.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/services/message/index.ts) 直接用 `lambdaClient.message.*` 处理消息 CRUD、统计、更新等。
- [`packages/builtin-tool-creds/src/executor/index.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/packages/builtin-tool-creds/src/executor/index.ts) 同时使用 `toolsClient.market.*` 和 `lambdaClient.market.*`，分别处理市场授权和凭据写入。
- 其他服务层、页面层、工具包也普遍以 `lambdaClient` 作为默认 RPC 入口。

根据当前片段推断，`asyncClient` 更像是专用异步通道；我在仓库里没有看到它的真实业务调用点，只看到测试里的 mock 片段。

## 运行/调用流程

典型流程是：

1. 上层 service 或 executor 从 `@/libs/trpc/client` 导入对应 client。
2. 调用 `.query()` / `.mutate()` 时，link 链开始工作。
3. `headers` 动态注入认证信息；`fetch` 默认加 `credentials: 'include'`。
4. 请求被发到 `/trpc/lambda`、`/trpc/tools` 或 `/trpc/async`。
5. `lambda.ts` 和 `tools.ts` 的 error link 统一处理 401、abort、市场授权事件等。
6. 返回值由 `superjson` 反序列化，交给上层 service 继续封装成业务结果。

`lambda.ts` 里还专门把 `user.getUserState`、`config.getGlobalConfig`、`market.getAssistantList` 放进跳过 batching 的白名单，说明它考虑了首屏加载和慢接口的体验。

## 小白阅读顺序

1. 先看 [`index.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/libs/trpc/client/index.ts)，确认这个目录只负责导出。
2. 再看 [`async.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/libs/trpc/client/async.ts)，理解最简单的 tRPC 客户端长什么样。
3. 接着看 [`tools.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/libs/trpc/client/tools.ts)，重点看市场 401 如何转成事件。
4. 然后看 [`lambda.ts`](/data/project/AIWIKI/data/repos/github.com-lobehub-lobehub-9577f1c9/source/src/libs/trpc/client/lambda.ts)，这是整个目录里最关键、也最容易看漏细节的文件。
5. 最后回到调用方，比如 `src/services/message/index.ts` 和 `packages/builtin-tool-creds/src/executor/index.ts`，把“客户端封装”映射回业务场景。

## 常见误区

- 把它当成业务模块。实际上这里是 RPC 客户端层，不负责业务规则本身。
- 只看 `lambdaClient`，忽略 `toolsClient` 和 `asyncClient`。这三个 client 服务的调用场景不同。
- 以为 401 都会走同一种处理。`lambda.ts` 里区分了 market API 和普通会话失效，两条路径的后果不同。
- 忽略 `splitLink`。它不是性能装饰，而是明确把首屏/慢接口从 batch 中拆出去。
- 误读 `headers` 的动态 import。这里是为了避免循环依赖，不是随手写法。
- 在桌面端忘记 `withElectronProtocolIfElectron`。这会导致 `/trpc/*` 访问协议不兼容。
