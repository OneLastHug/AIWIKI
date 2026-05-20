# `src/server` 目录说明

## 这个目录在项目中的位置

- 仓库位置：`/data/project/lobehub/src/server`
- 它位于 Next.js 后端入口 `src/app/(backend)` 的下游，是服务端业务核心层

## 它负责什么

`src/server` 负责的远不止“写几个接口”。

从当前结构看，它主要承接：

- tRPC router
- Agent 相关 Hono 路由
- 服务端业务 service
- 运行时配置
- Feature Flag 读取
- Agent Runtime 协调
- 工具启用规则
- webhook / workflow / 异步任务等

所以它更像“后端业务平台层”，不是单薄的 controller 目录。

## 初学者应该先看哪些文件和子目录

推荐顺序：

1. `src/server/routers/lambda/index.ts`
   看整个主 tRPC router 暴露了哪些业务域。
2. `src/server/routers/lambda/config/index.ts`
   这是很好的入门示例，复杂度适中。
3. `src/server/globalConfig/index.ts`
   看服务端如何把环境变量整理成前端可读的全局配置。
4. `src/server/runtimeConfig/index.ts`
   看运行时配置抽象的公共出口。
5. `src/server/featureFlags/index.ts`
   看 runtimeConfig 如何被具体业务消费。
6. `src/server/services/agentRuntime/AgentRuntimeService.ts`
   看重量级执行链路长什么样。
7. `src/server/modules/AgentRuntime/AgentRuntimeCoordinator.ts`
   看 service 和 module 的边界。
8. `src/server/agent-hono/index.ts`
   看 Agent 相关的 Hono 路径如何组织。

## 它和其他目录如何交互

最典型的链路是：

```text
src/app/(backend)/trpc/*/route.ts
-> src/server/routers/*
-> src/server/services/*
-> src/server/modules/* 或 packages/*
-> 数据库 / 模型运行时 / 队列 / Redis
```

也就是说：

- `src/app/(backend)` 负责挂入口
- `src/server` 负责真业务
- `packages/*` 负责底层共享能力

## 目录里的主要分层

### `routers`

这里是对外接口层。

当前能直接看到几条主线：

- `routers/lambda`
  主应用 tRPC 接口
- `routers/mobile`
  移动端裁剪版接口
- `routers/async`
  偏异步任务接口
- `routers/tools`
  工具相关接口

如果你想知道“前端到底能调哪些服务端能力”，先看这里。

### `services`

这里是业务用例层。

它的职责通常是：

- 组织多个 model / repo / module
- 做业务流程编排
- 把复杂逻辑从 router 里抽出来

比如：

- `agent`
- `agentGroup`
- `agentRuntime`
- `task`
- `knowledgeBase`
- `messenger`

### `modules`

这里更像“服务端内部基础模块”。

和 `services` 的区别可以这样抓：

- `service` 更像“业务动作”
- `module` 更像“可复用机制”

例如：

- `AgentRuntime`
  状态保存、流事件、协调器等运行机制
- `Mecha/AgentToolsEngine`
  工具启用规则与工具引擎装配
- `ModelRuntime`
  模型运行相关服务端封装

### `runtimeConfig`

这是运行时配置抽象层。

它定义了：

- 配置 domain
- provider 接口
- Redis provider
- 环境变量 fallback provider
- 组合 provider

这让“配置从 Redis 读，或者从 env 兜底”这类逻辑能被统一描述。

### `agent-hono`

这是另一条非 tRPC 的接口链。

主要覆盖：

- Agent 执行入口
- step 运行
- tool result 回调
- gateway / bot webhook

## 常见概念解释

### `router` 和 `service` 的区别

在这个项目里，可以先这样理解：

- `router`
  暴露接口、做 procedure 装配、收参数、回结果
- `service`
  真正处理业务流程

如果一个 router 文件开始同时做数据库访问、状态协调、第三方调用，通常说明它变重了，后续适合继续下沉到 service。

### `service` 和 `module` 的区别

可以这样抓边界：

- `service`
  面向业务场景，例如“执行一个 Agent 任务”
- `module`
  面向机制复用，例如“保存 Agent 运行状态并发流事件”

`AgentRuntimeService` 和 `AgentRuntimeCoordinator` 这一组就是很好的例子。

### `lambda`、`async`、`mobile`、`tools` 这些 router 名字是什么意思

- `lambda`
  主 tRPC 路由集合
- `async`
  偏任务型、异步型接口
- `mobile`
  给移动端裁剪出来的接口集合
- `tools`
  给工具体系暴露的接口集合

这些名字不必神化，先当作“不同入口分组”即可。

## 需要暂时跳过的内容

初学者建议先跳过：

- `workflows-hono`
- 很多 webhook 平台细节
- `messenger` 各平台深度适配
- `AgentTracing`、OTel 观测细节
- 很多非常垂直的 service 子目录

不是因为它们不重要，而是它们适合在你已经理解主链路后按需进入。

## 一句话阅读建议

先把 `src/server` 看成“接口层 + 业务层 + 机制层”的三段式结构，再去读单个文件会容易很多。
