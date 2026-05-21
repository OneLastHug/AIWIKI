# 目录：src/server/routers/lambda/config

## 它负责什么

`src/server/routers/lambda/config` 是 LobeHub 后端 tRPC Lambda 路由里专门负责“运行时配置下发”的小目录。它把服务端配置、功能开关、默认 Agent 配置，以及可选的全局公告牌信息整理成前端可消费的数据。

这个目录不是配置定义本身，而是配置的 API 出口。真正的配置来源在更下游，例如：

- `@/server/globalConfig`：读取服务端全局配置、默认 Agent 配置、模型供应商配置、上传能力、遥测配置等。
- `@/server/featureFlags`：读取服务端 feature flags，并可按 `userId` 计算用户相关的功能开关。
- `@lobechat/edge-config`：读取 Edge Config 中的 billboard 公告配置。
- `@/business/server/lambda-routers/config`：注入商业版或云端业务扩展配置接口。

从前端视角看，它提供的是“启动应用时必须知道的服务端能力清单”：哪些模型供应商可用、哪些功能入口展示、哪些实验功能开启、是否有公告等。

## 关键组成

该目录当前直接包含：

- `index.ts`
- `index.test.ts`
- `__snapshots__/index.test.ts.snap`

核心代码都在 `index.ts`。

`index.ts` 的主要导入包括：

- `EdgeConfig` from `@lobechat/edge-config`：用于读取边缘配置里的公告牌数据。
- `debug`：创建 `config-router` 日志命名空间。
- `businessConfigEndpoints` from `@/business/server/lambda-routers/config`：业务侧扩展的 config 端点。
- `publicProcedure`, `router` from `@/libs/trpc/lambda`：构建 tRPC router 和公开 query。
- `getServerFeatureFlagsStateFromRuntimeConfig` from `@/server/featureFlags`：生成服务端 feature flags 状态。
- `getServerDefaultAgentConfig`, `getServerGlobalConfig` from `@/server/globalConfig`：读取默认 Agent 配置和全局服务端配置。
- `GlobalBillboard`, `GlobalBillboardItem`, `GlobalRuntimeConfig` from `@/types/serverConfig`：约束返回数据类型。

它唯一导出的核心对象是：

```ts
export const configRouter = router({
  getDefaultAgentConfig: publicProcedure.query(async () => {
    return getServerDefaultAgentConfig();
  }),

  getGlobalConfig: publicProcedure.query(async ({ ctx }): Promise<GlobalRuntimeConfig> => {
    ...
  }),

  ...businessConfigEndpoints,
});
```

也就是说，这个目录对外提供一个 `configRouter`，里面至少包含两个基础公开接口：

- `getDefaultAgentConfig`
- `getGlobalConfig`

同时通过 `...businessConfigEndpoints` 合并业务扩展接口。根据当前片段推断，开源版和云端/商业版可以通过 `@/business/server/lambda-routers/config` 对配置路由做差异化扩展，主路由不需要关心具体业务实现。

目录里还有几个内部辅助函数：

- `isObject(value)`：判断输入是不是普通对象，排除 `null` 和数组。
- `normalizeBillboardItem(raw)`：校验单个公告条目，要求至少有字符串类型的 `title` 和 `description`。
- `normalizeBillboard(raw)`：校验整个 billboard，要求有非空 `slug`、字符串 `title`、字符串 `startAt` / `endAt`，以及数组类型 `items`。
- `getActiveBillboard()`：如果 `EdgeConfig.isEnabled()` 为真，就从 Edge Config 读取公告牌；读取失败或格式不合法时返回 `null`。

这里的 `normalizeBillboard*` 逻辑很关键：Edge Config 是外部动态配置源，不能直接信任。路由会先做轻量结构校验，避免坏数据污染前端全局状态。

测试文件 `index.test.ts` 主要覆盖两类行为：

- `getGlobalConfig` 中模型供应商环境变量解析结果，例如 `OPENAI_MODEL_LIST`、`OPENROUTER_MODEL_LIST` 的模型添加、删除、重命名、隐藏模型展示等。
- `getDefaultAgentConfig` 对 `DEFAULT_AGENT_CONFIG` 环境变量的解析，例如 `model`、`provider`、`plugins`、`params.max_tokens` 等字段。

这些测试说明：虽然模型列表解析逻辑不在本目录实现，但本目录是它们面向客户端的聚合出口，所以快照测试放在这里能验证最终下发结构。

## 上下游关系

上游注册关系：

`configRouter` 被注册进两个根路由：

- `src/server/routers/lambda/index.ts`
- `src/server/routers/mobile/index.ts`

在 `lambdaRouter` 中，它被挂到：

```ts
config: configRouter
```

在 `mobileRouter` 中，它同样被挂到：

```ts
config: configRouter
```

因此 Web/桌面侧的 Lambda tRPC 路由和移动端 tRPC 路由都复用了同一套 config 接口。这个设计保证移动端和主应用拿到的服务端配置口径一致。

下游依赖关系：

`getGlobalConfig` 会并行读取三类数据：

```ts
const [serverConfig, serverFeatureFlags, billboard] = await Promise.all([
  getServerGlobalConfig(),
  getServerFeatureFlagsStateFromRuntimeConfig(ctx.userId || undefined),
  getActiveBillboard(),
]);
```

返回结构是：

```ts
{
  billboard,
  serverConfig,
  serverFeatureFlags,
}
```

其中：

- `serverConfig` 来自 `getServerGlobalConfig()`，包含 AI provider、telemetry、认证能力、上传能力、业务能力等全局服务端配置。
- `serverFeatureFlags` 来自 `getServerFeatureFlagsStateFromRuntimeConfig()`，用于控制功能入口、实验能力、知识库、市场、Agent 编辑等行为。
- `billboard` 来自 Edge Config，表示全局公告牌；不存在、未开启、读取失败或格式非法时为 `null`。

前端消费关系：

`src/store/serverConfig/action.ts` 中的 `useInitServerConfig` 会调用：

```ts
globalService.getGlobalConfig()
```

成功后写入 `serverConfig` store：

```ts
{
  billboard: data.billboard ?? null,
  featureFlags: data.serverFeatureFlags,
  serverConfig: data.serverConfig,
  serverConfigInit: true,
}
```

随后前端通过：

- `featureFlagsSelectors`
- `serverConfigSelectors`
- `useServerConfigStore`

读取这些配置。比如是否显示市场、是否启用知识库、是否启用 STT、是否启用业务能力、是否允许 Agent 编辑等，都会间接依赖这个路由下发的数据。

另外，`src/app/spa/[variants]/[[...path]]/route.ts` 也会直接读取 `getServerGlobalConfig()` 和 feature flags，用于 SPA HTML 模板阶段的服务端注入。它和本目录不是直接调用关系，但属于同一类“启动配置注入”链路。

## 运行/调用流程

典型前端启动流程可以理解为：

1. 应用初始化 `serverConfig` store。
2. `useInitServerConfig` 通过 SWR 发起一次性请求。
3. 请求进入 `globalService.getGlobalConfig()`。
4. 根据当前片段推断，`globalService.getGlobalConfig()` 会通过 tRPC 调用后端的 `config.getGlobalConfig`。
5. tRPC 根路由 `lambdaRouter` 或 `mobileRouter` 找到 `config: configRouter`。
6. `configRouter.getGlobalConfig` 开始执行，并记录 debug 日志。
7. 后端并行读取：
   - `getServerGlobalConfig()`
   - `getServerFeatureFlagsStateFromRuntimeConfig(ctx.userId || undefined)`
   - `getActiveBillboard()`
8. `getActiveBillboard()` 如果发现 `EdgeConfig` 未启用，直接返回 `null`；如果启用，则读取 `getBillboards()`，再做结构校验。
9. 三类数据聚合成 `GlobalRuntimeConfig` 返回给前端。
10. 前端 store 写入：
    - `serverConfig`
    - `featureFlags`
    - `billboard`
    - `serverConfigInit: true`
11. 各 UI 组件通过 selector 读取配置，决定功能入口、按钮、菜单、模型供应商、公告展示等行为。

`getDefaultAgentConfig` 的流程更简单：

1. 客户端调用 `config.getDefaultAgentConfig`。
2. 路由执行 `getServerDefaultAgentConfig()`。
3. 该函数解析服务端默认 Agent 环境配置。
4. 返回默认模型、供应商、插件、历史设置、参数等。

测试里的例子显示，`DEFAULT_AGENT_CONFIG` 支持类似下面的字符串：

```txt
plugins=search-engine,lobe-image-designer;enableHistoryCount=true;model=gemini-pro;provider=google;
```

解析后会变成结构化对象：

```ts
{
  enableHistoryCount: true,
  model: 'gemini-pro',
  plugins: ['search-engine', 'lobe-image-designer'],
  provider: 'google',
}
```

## 小白阅读顺序

建议按下面顺序阅读：

1. 先看 `src/server/routers/lambda/config/index.ts`

   重点看 `configRouter` 的导出结构。先理解它只做“聚合和下发”，不是所有配置逻辑的实现地。

2. 再看 `getGlobalConfig`

   关注这段并行调用：

   ```ts
   Promise.all([
     getServerGlobalConfig(),
     getServerFeatureFlagsStateFromRuntimeConfig(ctx.userId || undefined),
     getActiveBillboard(),
   ])
   ```

   这是整个目录的核心：把服务端全局配置、功能开关和公告牌合并成一次响应。

3. 然后看 `getActiveBillboard`

   理解为什么外部配置要先校验。这里的 `normalizeBillboard` 和 `normalizeBillboardItem` 是防御式编程，不是业务复杂度。

4. 接着看 `src/server/routers/lambda/index.ts`

   找到：

   ```ts
   config: configRouter
   ```

   明白它如何挂到主 tRPC 路由上。

5. 再看 `src/server/routers/mobile/index.ts`

   同样找到：

   ```ts
   config: configRouter
   ```

   理解移动端为什么也能复用这套配置接口。

6. 最后看 `src/store/serverConfig/action.ts` 和 `src/store/serverConfig/store.ts`

   这里能看到后端返回的数据如何进入前端 Zustand store，以及前端后续如何通过 selector 使用。

7. 如果想理解模型列表、默认 Agent 配置的细节，再看 `src/server/routers/lambda/config/index.test.ts`

   测试虽然不是实现，但它很好地展示了环境变量如何影响最终下发结果。

## 常见误区

1. 误以为这个目录定义了所有配置

   实际上它主要是 tRPC API 聚合层。真正的配置读取和解析在 `@/server/globalConfig`、`@/server/featureFlags`、`@/business/server/lambda-routers/config` 等模块里。

2. 误以为 `serverFeatureFlags` 是静态常量

   `getServerFeatureFlagsStateFromRuntimeConfig(ctx.userId || undefined)` 会接收当前请求上下文里的 `userId`。这意味着 feature flags 可能和用户有关，不一定是全局固定值。

3. 误以为 billboard 一定存在

   `getActiveBillboard()` 有多个返回 `null` 的情况：`EdgeConfig` 未启用、没有数据、数据结构非法、读取异常。前端必须按可空值处理。

4. 误以为 Edge Config 数据可信

   代码专门用 `normalizeBillboard` 做结构校验，说明外部动态配置可能出错。新增字段可以透传，但关键字段必须满足基本类型要求。

5. 误以为测试里的模型解析逻辑在本目录

   `index.test.ts` 大量测试 `OPENAI_MODEL_LIST`、`OPENROUTER_MODEL_LIST`，但解析逻辑来自 `getServerGlobalConfig()` 背后的模块。本目录只是最终出口，所以测试在这里验证“客户端最终会看到什么”。

6. 误以为 Web 和 Mobile 有两套 config 逻辑

   `lambdaRouter` 和 `mobileRouter` 都复用同一个 `configRouter`。如果修改 `configRouter` 的返回结构，会同时影响主应用和移动端。

7. 误以为 `businessConfigEndpoints` 可忽略

   `...businessConfigEndpoints` 是扩展点。阅读开源基础逻辑时可以先跳过，但排查云端或商业功能配置时必须检查它，否则可能漏掉实际暴露的 config 接口。

8. 误以为 `getGlobalConfig` 失败会自动阻断整个应用

   从当前目录看，`getActiveBillboard()` 内部吞掉 Edge Config 错误并返回 `null`，避免公告系统影响主配置加载。但 `getServerGlobalConfig()` 或 feature flags 如果抛错，仍可能导致整个 `getGlobalConfig` 请求失败；前端 `useInitServerConfig` 的 `onError` 会把 `serverConfigInit` 置为 `true` 作为降级处理。
