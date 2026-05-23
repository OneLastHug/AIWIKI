# 文件：src/server/routers/lambda/index.ts
## 一句话定位
这是 LobeHub Lambda 侧 tRPC 后端的总入口路由文件，负责把各业务子 router 汇总成一个统一的 `lambdaRouter`，并向外导出它的类型 `LambdaRouter`，供 HTTP 入口、内部 caller 和客户端类型推导共同使用。

## 它暴露/定义了什么
这里核心只定义了两个东西：`lambdaRouter` 和 `LambdaRouter`。前者是由 `router({ ... })` 组装出来的顶层路由对象，后者是 `typeof lambdaRouter` 的类型别名，给前端/CLI/测试环境做类型绑定。

从当前片段看，它挂载了大量领域路由，例如 `agent`、`message`、`session`、`market`、`plugin`、`upload`、`user` 等；同时也包含少量“跨域”或业务型能力路由，比如 `accountDeletion`、`subscription`、`topUp`、`referral`、`spend`、`taskTemplate`，这些来自 `@/business/server/lambda-routers/*`。另外它还单独暴露了一个 `healthcheck` 公共接口，直接返回 `"i'm live!"`。

## 谁调用它
直接调用者主要有两类：

1. Next.js 的 tRPC HTTP 入口 `src/app/(backend)/trpc/lambda/[trpc]/route.ts`，它把 `lambdaRouter` 传给 `fetchRequestHandler`，因此外部请求最终都会落到这个总路由上。
2. 内部服务调用入口 `src/app/(backend)/webapi/create-image/comfyui/route.ts`，它通过 `createCallerFactory(lambdaRouter)` 直接在进程内创建 caller，再调用 `caller.comfyui.createImage(...)`，绕过 HTTP 层。

间接使用者也很明确：`apps/cli/src/api/client.ts`、`src/libs/trpc/client/lambda.ts`、`src/libs/trpc/mock.ts` 都依赖 `LambdaRouter` 或 `lambdaRouter`，用于生成类型安全客户端、React hooks 或测试 caller。根据当前片段推断，这些地方依赖的是同一个 API 面，而不是另一套平行协议。

## 它调用谁
它本身不做复杂业务计算，主要是“组装”和“转发”：

- 调用 `router` 与 `publicProcedure`，构建顶层 tRPC 结构。
- 引入并注册各个子 router，例如 `./agent`、`./message`、`./market` 等。
- 其中 `healthcheck` 直接使用 `publicProcedure.query(...)`，不依赖其他子模块。
- 业务路由里真正的数据库访问、模型调用、外部服务交互，大多发生在各子 router 内部，而不是这个文件里。

## 核心流程
这个文件的流程很短，但它是整条链路的“总装配台”：

1. 导入所有 Lambda 域路由。
2. 通过 `router({ ... })` 将这些域路由挂到一个统一命名空间下。
3. 提供一个公共健康检查入口，便于探活和基础连通性确认。
4. 导出 `LambdaRouter` 类型，让客户端、CLI、mock caller 都能获得完整的端到端类型推导。
5. 上层 HTTP route `src/app/(backend)/trpc/lambda/[trpc]/route.ts` 把请求交给它，再由 tRPC 按 path 分发到具体子 router。
6. 内部 WebAPI 则可以直接创建 caller，跳过网络层，复用同一套路由与权限上下文。

## 关键函数的高层作用
- `lambdaRouter`：整套 Lambda tRPC API 的聚合入口。它的价值不在于实现业务，而在于定义 API 边界、统一命名空间和集中注册。
- `healthcheck`：最轻量的公开探活接口，通常用于判断服务是否可用。
- `LambdaRouter`：纯类型导出，给客户端侧、CLI、测试辅助工具提供一致的接口签名，减少手写类型和接口漂移。

## 修改风险
这个文件是高影响面聚合层，改动风险比单个业务 router 更高。

- 新增、删除或重命名子 router，会直接影响外部 API 路径，可能让 CLI、前端客户端、内部 caller 一起失效。
- 如果把某个路由从 `publicProcedure` 改成带鉴权的 procedure，可能会影响现有公开探活或匿名访问场景。
- 忘记把新子 router 注册进这个文件，会导致实现已经存在，但外部无法访问，表现为“接口找不到”。
- 这里的导出类型被很多地方复用，签名变化会扩散到 `apps/cli`、`src/libs/trpc/client/lambda.ts`、`src/libs/trpc/mock.ts` 这类依赖方。
- 由于它聚合了大量业务域，任何命名冲突、路径错配、导入循环或顺序性问题，都更容易在这里被放大。
