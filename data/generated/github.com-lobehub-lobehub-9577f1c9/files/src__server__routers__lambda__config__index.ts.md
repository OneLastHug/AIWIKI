# 文件：src/server/routers/lambda/config/index.ts

## 它负责什么

这个文件定义了 `configRouter`，也就是 tRPC 的“配置读取”路由。它提供两类核心能力：

1. `getDefaultAgentConfig`：读取系统默认的 Agent 配置。
2. `getGlobalConfig`：一次性返回前端启动或刷新时需要的全局配置，包括服务端配置、特性开关状态，以及可选的公告横幅 `billboard`。

从职责上看，它不是做业务计算，而是做“配置聚合层”：
- 把分散在 `globalConfig`、`featureFlags`、`EdgeConfig`、业务扩展路由里的配置统一拼装成一个接口。
- 对外部配置做基本校验和兜底，避免脏数据直接进入前端。

## 关键组成

### 1. `configRouter`
文件最终导出的就是：

```ts
export const configRouter = router({
  getDefaultAgentConfig: ...,
  getGlobalConfig: ...,
  ...businessConfigEndpoints,
});
```

这表示它既包含本文件内定义的两个标准接口，也把 `businessConfigEndpoints` 里的业务扩展接口直接合并进来。

### 2. `getDefaultAgentConfig`
```ts
getDefaultAgentConfig: publicProcedure.query(async () => {
  return getServerDefaultAgentConfig();
}),
```

它只做一件事：调用 `getServerDefaultAgentConfig()`，把默认 Agent 配置返回给调用方。  
从测试看，这个配置会受环境变量 `DEFAULT_AGENT_CONFIG` 影响，支持类似：
- `plugins=...`
- `enableHistoryCount=true`
- `model=...`
- `provider=...`
- `params.max_tokens=...`

### 3. `getGlobalConfig`
```ts
getGlobalConfig: publicProcedure.query(async ({ ctx }): Promise<GlobalRuntimeConfig> => {
  const [serverConfig, serverFeatureFlags, billboard] = await Promise.all([
    getServerGlobalConfig(),
    getServerFeatureFlagsStateFromRuntimeConfig(ctx.userId || undefined),
    getActiveBillboard(),
  ]);

  return { billboard, serverConfig, serverFeatureFlags };
}),
```

它并行拉取三份数据：
- `serverConfig`：服务端全局配置
- `serverFeatureFlags`：基于用户态或匿名态解析出的特性开关状态
- `billboard`：来自 EdgeConfig 的公告信息

然后打包成 `GlobalRuntimeConfig` 返回。

### 4. `getActiveBillboard`
这是一个内部辅助函数，负责从 `@lobechat/edge-config` 读取公告数据：

- 先判断 `EdgeConfig.isEnabled()`
- 再调用 `new EdgeConfig().getBillboards()`
- 最后做结构校验和字段过滤

如果数据不合法，直接忽略，不让脏数据扩散到全局配置里。

### 5. 数据校验函数
- `isObject`
- `normalizeBillboardItem`
- `normalizeBillboard`

这组函数是一个轻量的“防御式解析层”。  
它们保证：
- `billboard` 必须是对象
- `slug`、`title`、`startAt`、`endAt` 等字段类型正确
- `items` 必须是数组
- `item.title`、`item.description` 必须是字符串

如果任一条件不满足，就返回 `null`。

### 6. 日志
```ts
const log = debug('config-router');
```

这里用 `debug` 做低侵入日志记录，主要用于：
- 记录全局配置读取过程
- 记录 EdgeConfig 读取失败
- 记录 billboard 校验失败

## 上下游关系

### 上游依赖

这个文件直接依赖了几类东西：

- `@/libs/trpc/lambda`
  - 提供 `router` 和 `publicProcedure`
  - 说明这里是标准 tRPC lambda 路由

- `@/server/globalConfig`
  - 提供 `getServerDefaultAgentConfig`
  - 提供 `getServerGlobalConfig`

- `@/server/featureFlags`
  - 提供 `getServerFeatureFlagsStateFromRuntimeConfig`

- `@lobechat/edge-config`
  - 提供外部配置读取能力
  - 这里专门用于 `billboard`

- `@/business/server/lambda-routers/config`
  - 提供 `businessConfigEndpoints`
  - 说明这个路由不是纯“基础设施层”，还会挂载一些业务相关的配置接口

- `@/types/serverConfig`
  - 提供 `GlobalBillboard`、`GlobalBillboardItem`、`GlobalRuntimeConfig`
  - 这些类型定义了最终返回结构

### 下游被谁用

根据 `src/server/routers/lambda/index.ts`，它被挂到根 lambda router 的 `config` 节点下：

```ts
config: configRouter,
```

也就是说，外部调用链大致是：

`lambdaRouter.config.getGlobalConfig()`  
或  
`lambdaRouter.config.getDefaultAgentConfig()`

从测试文件 `src/server/routers/lambda/config/index.test.ts` 看，这个路由还会被本地 caller 直接调用，说明它是一个典型的后端配置接口单元，比较适合用 `createCallerFactory` 做无 HTTP 测试。

## 运行/调用流程

### `getDefaultAgentConfig` 的流程
1. 前端或调用方请求 `config.getDefaultAgentConfig`
2. tRPC 进入 `publicProcedure.query`
3. 后端调用 `getServerDefaultAgentConfig()`
4. 返回默认 Agent 配置对象

这个流程很短，核心价值在于把默认配置读取逻辑集中到服务端。

### `getGlobalConfig` 的流程
1. 调用方请求 `config.getGlobalConfig`
2. 后端记录日志，标记当前用户是匿名还是已登录
3. 并行执行三项任务：
   - 读取 `serverConfig`
   - 根据 `ctx.userId` 读取 `serverFeatureFlags`
   - 尝试从 EdgeConfig 读取 `billboard`
4. `billboard` 先经过结构校验
5. 校验失败或读取失败时，直接返回 `null`
6. 组装成 `{ billboard, serverConfig, serverFeatureFlags }`

这里的关键点是“并行 + 容错”：
- `Promise.all` 提高读取效率
- `billboard` 失败不会影响 `serverConfig` 和 `featureFlags`
- 外部配置脏数据被隔离在最小范围内

### `billboard` 处理流程
1. 检查 `EdgeConfig.isEnabled()`
2. 调用 `getBillboards()`
3. 若为空或抛错，返回 `null`
4. 若结构不合法，记录日志并忽略
5. 若合法，返回标准化后的 `GlobalBillboard`

根据当前片段推断，这意味着前端拿到的公告数据会更稳定，避免因为某一条坏数据导致首页或全局配置渲染失败。

### 测试验证的流程
测试文件主要验证两件事：
- `getGlobalConfig` 会正确反映环境变量对模型列表和默认 provider 的影响
- `getDefaultAgentConfig` 会正确解析 `DEFAULT_AGENT_CONFIG`

这说明这个路由不仅是“静态配置读取”，还承担了“环境变量配置编译结果输出”的职责。

## 小白阅读顺序

1. 先看 `src/server/routers/lambda/index.ts`  
   了解 `configRouter` 是怎么被挂到总路由里的。

2. 再看本文件顶部 import  
   先认识它的数据来源：`globalConfig`、`featureFlags`、`EdgeConfig`、`businessConfigEndpoints`。

3. 重点读 `getGlobalConfig`  
   这是这个文件最核心的对外接口，理解它就理解了 80% 的用途。

4. 再看 `getActiveBillboard` 和 `normalizeBillboard*`  
   这部分体现了它对外部数据的容错策略。

5. 最后看 `src/server/routers/lambda/config/index.test.ts`  
   用测试反推环境变量如何影响返回结果，这样最容易理解实际行为。

## 常见误区

1. 以为它只是“读取配置”  
   实际上它还在做“配置整合”和“数据校验”，尤其是 `getGlobalConfig`。

2. 忽略 `businessConfigEndpoints`
   这个展开运算符会把别的配置接口一起挂进来，不是只有文件里显式写出来的两个方法。

3. 误以为 `billboard` 是强依赖
   不是。这里是可选增强项，读不到或校验失败都会降级成 `null`。

4. 以为 `getGlobalConfig` 只返回服务端配置
   它返回的是一个组合对象：`serverConfig`、`serverFeatureFlags`、`billboard` 三部分。

5. 忽略 `ctx.userId` 的作用
   `getServerFeatureFlagsStateFromRuntimeConfig(ctx.userId || undefined)` 说明特性开关状态可能和用户身份相关，匿名和登录用户返回值可能不同。

6. 把测试当成纯单测看
   这些测试其实在验证“环境变量 -> 服务端配置输出”的链路，很适合用来理解这个路由的真实用途。
