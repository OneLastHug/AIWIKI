# 目录：src/server/runtimeConfig

## 它负责什么

`src/server/runtimeConfig` 是服务端“运行期配置”的读取抽象层。它本身不定义某个具体业务配置，而是提供一组通用类型和 provider，让上层模块可以用统一方式从不同来源读取配置快照，例如：

- 从 Redis 读取线上动态发布的配置；
- 从环境变量或代码计算出的默认配置兜底；
- 对读取到的数据做 `zod` schema 校验；
- 为读取结果增加 `version`、`updatedAt` 这样的版本快照元信息；
- 在服务进程内做短 TTL 缓存，避免频繁访问 Redis。

根据当前片段看，直接使用它的主要模块是 `src/server/featureFlags/index.ts`。`featureFlags` 会引入 `RuntimeConfigDomain`、`RuntimeConfigProvider`、`CompositeRuntimeConfigProvider`、`EnvRuntimeConfigProvider`、`RedisRuntimeConfigProvider`，定义 feature flags 相关 domain，然后组合 Redis 与 env fallback。

这个目录的定位可以理解为：**server 侧动态配置读取基础设施**，目前至少服务于 feature flag 体系。

## 关键组成

`index.ts` 是公共出口：

```ts
export * from './providers';
export * from './types';
```

它把类型定义和 provider 实现统一导出，调用方只需要从 `@/server/runtimeConfig` 引入即可。

`types.ts` 定义核心协议：

- `RuntimeConfigSelector`：配置选择器，目前有两类：
  - `{ scope: 'global' }`：全局配置；
  - `{ scope: 'user', id: string }`：用户级配置。
- `VersionedSnapshot<T>`：配置快照包装，包含：
  - `data`：实际配置数据；
  - `updatedAt`：更新时间字符串；
  - `version`：版本号。
- `RuntimeConfigDomain<T>`：某类配置的领域描述，包含：
  - `key`：领域标识；
  - `schema`：用于校验数据的 `ZodSchema<T>`；
  - `cacheTtlMs`：缓存时间；
  - `getStorageKey(selector?)`：生成存储 key；
  - `getVersionKey?(selector?)`：版本 key，目前在已读实现中没有被 provider 使用。
- `RuntimeConfigProvider<T>`：统一 provider 接口：
  - `domain`；
  - `isEnabled()`；
  - `getSnapshot(selector?)`。

`providers/index.ts` 继续聚合导出三个 provider：

- `EnvRuntimeConfigProvider`
- `RedisRuntimeConfigProvider`
- `CompositeRuntimeConfigProvider`

`EnvRuntimeConfigProvider<T>` 是兜底型 provider。构造时接收一个 `domain` 和 `getSnapshotData(selector?)`。它的 `isEnabled()` 永远返回 `true`。调用 `getSnapshot()` 时，如果 `getSnapshotData` 返回空值，就返回 `null`；否则包装为固定版本快照：

- `version: 0`
- `updatedAt: '1970-01-01T00:00:00.000Z'`

这说明 env provider 的语义更像“静态默认值”，不是实时发布的配置版本。

`RedisRuntimeConfigProvider<T>` 是动态配置 provider。它依赖：

- `@/envs/redis` 的 `getRedisConfig()` 判断 Redis 是否启用；
- `@/libs/redis` 的 `initializeRedis()` 初始化客户端；
- `debug('lobe:runtime-config')` 输出调试日志；
- `domain.schema.safeParse()` 校验配置结构。

它内部维护一个 `Map<string, CacheRecord<T>>` 缓存。缓存 key 不是 Redis key，而是 selector 维度的进程内 key：

- 无 selector 或 `global`：`global`
- user selector：`user:${id}`

读取 Redis 时才会调用 `domain.getStorageKey(selector)` 生成真正的 Redis key。

Redis 中的 payload 支持两种格式：

1. 标准 envelope：

```json
{
  "data": {},
  "updatedAt": "2026-04-23T00:00:00.000Z",
  "version": 12
}
```

2. 旧式或简化格式：直接存实际配置对象。

如果是 envelope，它校验 `parsed.data`；如果是直接对象，它校验整个 `parsed`，并补上当前时间作为 `updatedAt`、`version: 0`。解析失败、schema 校验失败、Redis 读取异常都会返回 `null`。

`CompositeRuntimeConfigProvider<T>` 是组合 provider。它接收 `primary` 和 `fallback`：

- `domain` 使用 `primary.domain`；
- `isEnabled()` 只要任一 provider enabled 就返回 `true`；
- `getSnapshot()` 会先尝试 primary；
- primary enabled 且返回非空 snapshot 时直接使用 primary；
- primary 没数据时，如果 fallback enabled，则读取 fallback；
- fallback disabled 时返回 `null`。

这正好适合“Redis 动态配置优先，环境默认配置兜底”的模式。

`RedisRuntimeConfigProvider.test.ts` 覆盖了几个关键行为：

- 能从 versioned envelope 中解析 `data`、`updatedAt`、`version`；
- Redis disabled 时 `isEnabled()` 返回 `false`；
- `null` 快照也会被缓存，第二次不会重复请求 Redis；
- selector 级缓存会按 TTL 主动清理过期条目。

## 上下游关系

上游依赖主要有三类。

第一类是数据源：

- Redis：由 `getRedisConfig()` 和 `initializeRedis()` 提供；
- env/static config：由调用方传入 `getSnapshotData()` 提供。

第二类是结构约束：

- `RuntimeConfigDomain.schema` 使用 `zod` 校验配置形状；
- provider 不信任 Redis 中的 JSON，必须经过 schema 才会返回。

第三类是领域定义：

- provider 不知道业务配置是什么；
- 业务方需要提供 `RuntimeConfigDomain<T>`，包括 `key`、`schema`、`cacheTtlMs`、`getStorageKey()`。

下游调用方中，`src/server/featureFlags/index.ts` 是明确的直接调用方。根据搜索结果，它定义了：

- `FEATURE_FLAGS_DOMAIN: RuntimeConfigDomain<IFeatureFlags>`
- `FEATURE_FLAG_OVERRIDE_DOMAIN: RuntimeConfigDomain<Record<string, boolean>>`
- `featureFlagsProvider: RuntimeConfigProvider<IFeatureFlags> | null`
- `featureFlagsOverrideProvider: RuntimeConfigProvider<Record<string, boolean>> | null`

并且会构造：

```ts
new CompositeRuntimeConfigProvider(
  new RedisRuntimeConfigProvider(FEATURE_FLAGS_DOMAIN),
  new EnvRuntimeConfigProvider(FEATURE_FLAGS_DOMAIN, ...)
)
```

同时，feature flag override 使用 `new RedisRuntimeConfigProvider(FEATURE_FLAG_OVERRIDE_DOMAIN)`。根据当前片段推断，普通 feature flags 有 env 兜底，而 override 更偏向 Redis 动态覆盖，不一定有 env fallback。

搜索结果中还出现了很多 `runtimeConfig` 命名，例如 `packages/database/src/repositories/aiInfra`、`src/server/services/agentSignal/runtime`、`src/services/chat/mecha/agentConfigResolver.ts` 等。但这些只是同名业务概念，并没有从 `@/server/runtimeConfig` 导入当前目录的 provider。阅读时不要把所有 `runtimeConfig` 都误认为这一套 provider。

## 运行/调用流程

典型流程如下：

1. 业务模块定义一个 `RuntimeConfigDomain<T>`，声明配置类型、Redis key 生成方式、缓存 TTL 和 `zod` schema。
2. 业务模块创建 provider，例如：
   - Redis provider：读取动态配置；
   - Env provider：提供静态默认值；
   - Composite provider：把 Redis 放 primary，env 放 fallback。
3. 调用方执行 `provider.getSnapshot(selector)`。
4. 如果是 `CompositeRuntimeConfigProvider`：
   - 先判断 primary 是否 enabled；
   - primary enabled 时读取 primary；
   - primary 返回非空 snapshot 就结束；
   - primary 返回 `null` 时再尝试 fallback。
5. 如果进入 `RedisRuntimeConfigProvider`：
   - 先用 selector 查进程内缓存；
   - 缓存命中时直接返回，包括缓存的 `null`；
   - 缓存过期时清理；
   - 初始化 Redis；
   - 用 `domain.getStorageKey(selector)` 获取 Redis key；
   - `redis.get(key)` 读取原始字符串；
   - 没有值则缓存 `null` 并返回；
   - 有值则 JSON parse；
   - 判断是否是 `{ data, updatedAt, version }` envelope；
   - 用 `domain.schema.safeParse()` 校验；
   - 成功后缓存并返回 `VersionedSnapshot<T>`。
6. 如果进入 `EnvRuntimeConfigProvider`：
   - 调用业务传入的 `getSnapshotData(selector)`；
   - 有数据则包装成 `version: 0` 的快照；
   - 没数据返回 `null`。

这里有一个重要细节：Redis provider 的 `isEnabled()` 只看 Redis 配置是否启用，不代表某个业务配置一定存在。Redis enabled 但 key 不存在时会返回 `null`，然后 composite 才会考虑 fallback。

## 小白阅读顺序

1. 先看 `src/server/runtimeConfig/types.ts`。这里是全目录的语义核心。重点理解 `RuntimeConfigDomain` 和 `RuntimeConfigProvider`，它们决定了“业务配置”和“读取方式”如何解耦。

2. 再看 `src/server/runtimeConfig/index.ts` 和 `src/server/runtimeConfig/providers/index.ts`。这两个文件没有业务逻辑，只是导出入口。看它们是为了知道外部 import 的路径为什么可以是 `@/server/runtimeConfig`。

3. 接着看 `EnvRuntimeConfigProvider.ts`。它最简单，可以帮助理解 `getSnapshot()` 必须返回 `VersionedSnapshot<T> | null`，以及 fallback provider 是怎么工作的。

4. 然后看 `RedisRuntimeConfigProvider.ts`。重点关注四段逻辑：
   - `isEnabled()` 如何判断 Redis 是否可用；
   - `getCacheKey()` 与 `domain.getStorageKey()` 的区别；
   - `resolveEnvelopeData()` 如何兼容 envelope 和直接对象；
   - `getSnapshot()` 如何串起缓存、Redis、解析和校验。

5. 再看 `CompositeRuntimeConfigProvider.ts`。它解释了为什么业务方可以把 Redis 和 env 组合成“动态优先、静态兜底”的读取策略。

6. 最后看 `RedisRuntimeConfigProvider.test.ts`。测试文件比实现更适合验证边界行为，尤其是“缓存 null”“TTL 清理”“envelope 解析”这些容易漏掉的点。

7. 如果继续追调用方，再读 `src/server/featureFlags/index.ts`。根据当前片段，它是当前目录最直接的业务落点，可以看到 provider 如何被真实 domain 使用。

## 常见误区

- 不要把 `src/server/runtimeConfig` 理解成“全局配置文件”。它不是配置内容本身，而是读取运行期配置的基础设施。

- 不要以为 `RedisRuntimeConfigProvider` 只缓存有值结果。它也会缓存 `null`，这是为了避免 Redis 中没有配置时被高频重复访问。

- 不要混淆两个 key：`getCacheKey()` 是进程内缓存 key，只区分 `global` 和 `user:id`；`domain.getStorageKey()` 才是真正访问 Redis 的存储 key。

- 不要认为 Redis 数据只支持 envelope。当前实现也兼容直接存配置对象的格式，只是直接对象会被包装成 `version: 0`，`updatedAt` 使用当前时间。

- 不要忽略 `schema.safeParse()`。Redis 中即使有 JSON，只要结构不符合 domain schema，就会被视为无效并返回 `null`。

- 不要把 `EnvRuntimeConfigProvider` 的固定 `updatedAt: 1970-01-01T00:00:00.000Z` 当成真实更新时间。它表达的是“静态兜底配置”，不是一次真实发布。

- 不要以为 `CompositeRuntimeConfigProvider.isEnabled()` 为 true 就一定能拿到配置。它只表示 primary 或 fallback 至少一个启用，最终 `getSnapshot()` 仍可能返回 `null`。

- 不要过度依赖 `getVersionKey`。虽然 `RuntimeConfigDomain` 类型里定义了它，但根据当前实现片段，现有 provider 没有使用这个字段。它可能是预留能力，或供其他未读上下文使用。

- 不要被仓库里其他 `runtimeConfig` 命名干扰。很多模块有自己的 `runtimeConfig` 业务字段，例如 AI provider、Agent Signal、chat resolver，但它们不一定使用当前目录的 provider 抽象。
