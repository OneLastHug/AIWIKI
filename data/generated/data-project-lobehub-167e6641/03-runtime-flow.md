# 03. 运行 / 请求 / 数据流

这一页不追求把所有实现细节讲满，而是帮助你建立“数据到底怎么流动”的脑内动画。

## 1. 浏览器第一次打开页面时发生什么

最重要的一条链路是：

```text
浏览器访问 URL
-> Next.js 命中 src/app/spa/[variants]/[[...path]]/route.ts
-> route.ts 读取 serverConfig、featureFlags、analyticsConfig、clientEnv
-> 把这些数据注入到 window.__SERVER_CONFIG__
-> 返回 desktop 或 mobile 的 HTML 模板
-> 浏览器加载 Vite 产出的 SPA bundle
-> src/spa/entry.* 运行
-> createAppRouter(...) 创建 React Router
-> SPAGlobalProvider 读取 window.__SERVER_CONFIG__
-> ServerConfigStoreProvider 创建 serverConfig store
-> StoreInitialization 初始化用户、全局状态、内置 Agent 等
-> 页面真正可交互
```

这里有三个很关键的文件：

- `src/app/spa/[variants]/[[...path]]/route.ts`
  负责“吐 HTML 并塞初始配置”
- `src/spa/entry.web.tsx` / `entry.mobile.tsx` / `entry.desktop.tsx` / `entry.popup.tsx`
  负责“真正启动 React”
- `src/layout/SPAGlobalProvider/index.tsx`
  负责把配置、主题、认证、Query、Store 初始化都挂上去

## 2. `window.__SERVER_CONFIG__` 为什么重要

这个对象是服务端在返回 HTML 时直接塞进页面的。

它包含至少这几类信息：

- `config`
  服务端整理好的全局能力开关，例如 Provider 是否启用、是否允许上传、是否启用某些认证方式
- `featureFlags`
  功能开关
- `analyticsConfig`
  埋点相关配置
- `clientEnv`
  某些前端需要知道的公共环境信息
- `isMobile`
  当前是否是 mobile 变体

所以前端不是“完全空白启动后再去问服务器自己是谁”，而是先拿到一份首屏配置，再继续增量初始化。

## 3. 前端路由是怎么切换的

LobeHub 的 SPA 路由流大致是：

```text
src/spa/entry.*
-> src/utils/router.tsx 的 createAppRouter(...)
-> src/spa/router/*.config.tsx 注册 RouteObject[]
-> React Router 命中某个 src/routes/* 页面段
-> 该页面段再去组合 src/features/*
-> feature 连接 store / service / component
```

比如桌面主路由会走：

```text
desktopRoutes
-> /agent/:aid
-> src/routes/(main)/agent/_layout
-> src/routes/(main)/agent/index.tsx
-> 其中再挂 Conversation、PageTitle、Telemetry 等业务实现
```

而 `/page` 这组路由更能体现“routes 薄、features 厚”的方向：

```text
src/routes/(main)/page/_layout/index.tsx
-> 直接 re-export src/features/Pages/PageLayout
```

## 4. 普通数据请求是怎么走到后端的

前端到后端的常见链路如下：

```text
组件点击 / 页面初始化
-> 调 store action 或 service
-> service 使用 lambdaClient / asyncClient / toolsClient
-> 请求进入 /trpc/lambda 或 /trpc/async 或 /trpc/tools
-> Next.js route.ts 调 fetchRequestHandler
-> createLambdaContext / createAsyncRouteContext 创建请求上下文
-> 命中 src/server/routers/* 下某个 router / procedure
-> procedure 调 src/server/services/* 业务服务
-> service 再调 database / model runtime / 其他模块
-> 返回结果
-> 前端 store 更新
-> UI 重渲染
```

如果你只记一条最通用的路径，可以记成：

```text
Feature -> Store/Service -> tRPC Client -> Router -> Service -> Package/DB -> 回来更新 Store
```

## 5. `serverConfig` 这条链为什么值得单独看

这是一个非常典型、也非常适合入门的链路：

```text
src/app/spa/.../route.ts
-> 注入 window.__SERVER_CONFIG__
-> SPAGlobalProvider 用 ServerConfigStoreProvider 建立 store
-> StoreInitialization 调 useInitServerConfig()
-> globalService.getGlobalConfig()
-> lambdaClient.config.getGlobalConfig.query()
-> /trpc/lambda
-> src/server/routers/lambda/config/index.ts
-> getServerGlobalConfig() + getServerFeatureFlagsStateFromRuntimeConfig()
-> 前端拿到最新配置并写回 store
```

这条链能同时帮你理解：

- 服务端首屏注入
- 前端 store 初始化
- tRPC 请求
- server router 和 global config 的关系

## 6. 后端配置是怎么拼出来的

服务端不是简单把 `.env` 原样发给前端，而是做了一次“整理和筛选”：

```text
envs/*
-> src/server/globalConfig/index.ts
-> 生成 GlobalServerConfig
-> configRouter.getGlobalConfig 暴露给前端
-> 前端只拿到允许公开的那部分
```

比如：

- 哪些 Provider 启用
- 是否允许邮箱密码登录
- 是否开启 Klavis / LobeHub Skill
- 是否有视觉理解模型
- 是否暴露 Agent Gateway URL

这是一种“服务端先加工，再下发给前端”的模式。

## 7. Agent 长任务是怎么跑的

这一条比普通 CRUD 更重。

从当前代码能看到，大致链路是：

```text
前端发起 Agent / Task 执行
-> 服务端进入 src/server/services/agentRuntime/AgentRuntimeService
-> AgentRuntimeService 组装 Agent、队列、工具执行器、事件流管理器
-> AgentRuntimeCoordinator 负责保存状态和发布流事件
-> ToolExecutionService / BuiltinToolsExecutor / MCP 服务参与执行
-> 中途可能进入 waiting_for_human / done / error / interrupted 等状态
-> 事件流持续发给客户端或网关
```

你可以把它理解成：

- 普通接口像“问一次，答一次”
- Agent Runtime 像“启动一个会持续推进的流程”

这也是为什么这里除了 tRPC 外，还会有：

- `src/server/agent-hono`
- `QueueService`
- `StreamEventManager`
- `AgentSignal`

这些看起来更像流程编排系统的东西。

## 8. `/api/agent/*` 这条 Hono 链在做什么

除了 tRPC，Agent 相关还有一套基于 Hono 的入口：

```text
/api/agent
-> src/server/agent-hono/index.ts
-> 不同 path 进不同 handler
-> 例如 execAgent / runStep / toolResult / gatewayCallback / webhook
```

这套路径主要覆盖：

- 启动 Agent 操作
- 执行单步
- 工具结果回传
- Gateway / webhook / bot callback

也就是说，Agent 执行这件事已经重到不适合只看成“普通页面接口”。

## 9. 桌面端多了一条什么链

在 Electron 里，前端还能调用本地能力：

```text
React 页面
-> window.electronAPI.invoke(...)
-> preload 暴露安全桥
-> Electron main process controller
-> 系统 API / 文件系统 / Git / Shell / 截图 / 窗口管理
-> 结果再回到 renderer
```

所以桌面端又多了一层边界：

- 浏览器世界的 React 代码
- Electron 提供的受控本地能力

这就是为什么桌面端需要：

- `apps/desktop/src/main`
- `apps/desktop/src/preload`
- `packages/electron-client-ipc`
- `packages/electron-server-ipc`

## 10. 读运行流时要有的心智模型

建议把整个项目看成四条并行但相互连接的流：

1. 页面流
   `entry -> router -> routes -> features`
2. 状态流
   `store init -> selectors -> actions -> rerender`
3. 请求流
   `service -> tRPC client -> server router -> server service`
4. 执行流
   `agent runtime / queue / stream / tools / gateway`

只要分清这四条线，你在任何一个文件里基本都能先判断：

- 它属于哪一层
- 它上游是谁
- 它下游又会把数据交给谁
