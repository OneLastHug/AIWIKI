# 目录：src/server/runtimeConfig/providers

## 它负责什么

`src/server/runtimeConfig/providers` 是服务端 Runtime Config 的“配置来源适配层”。它不定义具体业务配置是什么，也不直接决定 feature flag 的业务含义，而是把“从哪里读取一份运行时配置快照”抽象成统一接口。

这个目录围绕 `RuntimeConfigProvider<T>` 工作。根据 `src/server/runtimeConfig/types.ts`，一个 provider 需要提供：

- `domain`：当前配置域的元信息，例如 `key`、`schema`、`cacheTtlMs`、`getStorageKey`
- `isEnabled()`：这个配置来源当前是否可用
- `getSnapshot(selector?)`：读取一份 `VersionedSnapshot<T> | null`

`VersionedSnapshot<T>` 包含三部分：

```ts
{
  data: T;
  updatedAt: string;
  version: number;
}
```

因此，这个目录的核心职责可以理解为：把 Redis、环境变量、组合回退等不同来源，统一包装成“可读取版本化配置快照”的对象。

当前实际调用方主要是 `src/server/featureFlags/index.ts`。feature flags 通过这里的 provider 优先读 Redis 中的动态配置，读不到时回退到环境变量配置。

## 关键组成

`index.ts` 是导出入口：

```ts
export * from './CompositeRuntimeConfigProvider';
export * from './EnvRuntimeConfigProvider';
export * from './RedisRuntimeConfigProvider';
```

也就是说，外部通过 `@/server/runtimeConfig` 或该目录入口使用三个 provider。

`EnvRuntimeConfigProvider<T>` 负责从环境变量派生出的配置中读取快照。它本身不解析环境变量，而是在构造时接收：

```ts
getSnapshotData: (selector?: RuntimeConfigSelector) => T | null
```

调用 `getSnapshot()` 时，它执行 `getSnapshotData(selector)`。如果没有数据就返回 `null`；如果有数据，则包装成固定版本快照：

```ts
version: 0
updatedAt: '1970-01-01T00:00:00.000Z'
```

这说明 Env provider 是静态兜底来源，不表达真实更新时间，也不承担版本推进职责。

`RedisRuntimeConfigProvider<T>` 是动态配置来源。它通过 `getRedisConfig().enabled` 判断 Redis 是否启用，通过 `initializeRedis(getRedisConfig())` 获取 Redis 客户端，再用 `domain.getStorageKey(selector)` 得到 Redis key 并读取内容。

它有几个关键逻辑：

- 内部维护 `Map<string, CacheRecord<T>>` 做本地进程缓存
- 缓存 key 根据 selector 生成：
  - 无 selector 或 `scope: 'global'` 时为 `global`
  - 用户级 selector 为 `${scope}:${id}`，例如 `user:user-1`
- 缓存 TTL 来自 `domain.cacheTtlMs`
- `null` 结果也会被缓存，避免 Redis 中没有配置时每次都打 Redis
- 会通过 `nextExpiredEntryAt` 做过期缓存的主动清理
- Redis 内容会先 `JSON.parse`
- 如果内容是 `{ data, updatedAt, version }` 这种 envelope，就校验 `data`
- 如果内容不是 envelope，就按旧格式直接把整个 parsed 值当作 data，并补 `updatedAt: new Date().toISOString()` 和 `version: 0`

`RedisRuntimeConfigProvider.test.ts` 覆盖了几个重要边界：版本化 envelope 解析、Redis disabled 判断、`null` 快照缓存、不同 selector 缓存过期清理。

`CompositeRuntimeConfigProvider<T>` 是组合 provider。它接收 `primary` 和 `fallback` 两个 provider：

```ts
new CompositeRuntimeConfigProvider(primary, fallback)
```

调用时逻辑是：

1. 如果 `primary.isEnabled()`，先读 primary
2. primary 返回非空 snapshot，就直接返回
3. primary 不可用或返回 `null`，再看 fallback 是否启用
4. fallback 启用则返回 fallback 的 `getSnapshot(selector)`
5. fallback 不启用则返回 `null`

它的 `domain` 直接取自 primary，因此组合 provider 在类型和业务域上以 primary 为准。

## 上下游关系

上游抽象来自 `src/server/runtimeConfig/types.ts`。该文件定义了：

- `RuntimeConfigSelector`
- `VersionedSnapshot<T>`
- `RuntimeConfigDomain<T>`
- `RuntimeConfigProvider<T>`

其中 `RuntimeConfigSelector` 当前支持两种范围：

```ts
{ scope: 'global' }
{ scope: 'user'; id: string }
```

`RuntimeConfigDomain<T>` 是 provider 和业务之间的桥梁。provider 并不知道“feature flags”是什么，只依赖 domain 提供的信息：

- `key`：配置域名称
- `schema`：Zod schema，用于校验 Redis 中读出的数据
- `cacheTtlMs`：本地缓存 TTL
- `getStorageKey(selector?)`：把 selector 映射成 Redis key
- `getVersionKey?(selector?)`：可选版本 key，当前 providers 目录内没有直接使用它

下游主要是 `src/server/featureFlags/index.ts`。

该文件定义了两个 Runtime Config domain：

`FEATURE_FLAGS_DOMAIN` 用于全局 feature flags：

```ts
{
  cacheTtlMs: 5000,
  getStorageKey: () => 'runtime-config:feature-flags:published',
  getVersionKey: () => 'runtime-config:feature-flags:version',
  key: 'feature-flags',
  schema: FeatureFlagsSchema,
}
```

`FEATURE_FLAG_OVERRIDE_DOMAIN` 用于用户级覆盖：

```ts
{
  cacheTtlMs: 30_000,
  getStorageKey: selector => {
    if (!selector || selector.scope !== 'user')
      return 'runtime-config:feature-flags:user:anonymous';

    return `runtime-config:feature-flags:user:${selector.id}`;
  },
  key: 'feature-flags-user-overrides',
  schema: z.record(z.string(), z.boolean()),
}
```

全局 feature flags 使用组合 provider：

```ts
new CompositeRuntimeConfigProvider(
  new RedisRuntimeConfigProvider(FEATURE_FLAGS_DOMAIN),
  new EnvRuntimeConfigProvider(FEATURE_FLAGS_DOMAIN, {
    getSnapshotData: () => getServerFeatureFlagsValue(),
  }),
)
```

含义是：优先从 Redis 读已发布的运行时 feature flags；如果 Redis 不可用或 Redis 没有配置，就回退到服务端环境变量配置。

用户级 override 只使用 Redis：

```ts
new RedisRuntimeConfigProvider(FEATURE_FLAG_OVERRIDE_DOMAIN)
```

这表示用户覆盖是动态配置能力，不从环境变量兜底。

## 运行/调用流程

以 `getServerFeatureFlagsStateFromRuntimeConfig(userId)` 为例，整体流程如下。

第一步，调用 `getServerFeatureFlagsFromRuntimeConfig(userId)`，内部进入 `getMergedFeatureFlags(userId)`。

第二步，读取全局配置：

```ts
getFeatureFlagsProvider().getSnapshot({ scope: 'global' })
```

`getFeatureFlagsProvider()` 会懒加载并缓存一个 `CompositeRuntimeConfigProvider`。第一次调用时创建，后续复用同一个 provider 实例。

第三步，组合 provider 先尝试 Redis：

```ts
new RedisRuntimeConfigProvider(FEATURE_FLAGS_DOMAIN)
```

Redis provider 会检查 Redis 是否启用。如果启用，就按 domain 的 `getStorageKey()` 读取：

```ts
runtime-config:feature-flags:published
```

读到字符串后解析 JSON，再用 `FeatureFlagsSchema` 校验。校验成功则返回版本化快照；校验失败或解析失败返回 `null`。

第四步，如果 Redis 没返回有效快照，组合 provider 回退到 Env provider。Env provider 调用：

```ts
getServerFeatureFlagsValue()
```

然后包装为 `version: 0` 的静态快照。

第五步，业务层把全局配置与默认值合并：

```ts
merge(DEFAULT_FEATURE_FLAGS, globalSnapshot?.data || {})
```

所以即使 Redis 和环境变量都没有给出完整配置，最终仍有 `DEFAULT_FEATURE_FLAGS` 兜底。

第六步，如果传入了 `userId`，再读取用户级 override：

```ts
getFeatureFlagOverrideProvider().getSnapshot({
  id: userId,
  scope: 'user',
})
```

对应 Redis key 类似：

```ts
runtime-config:feature-flags:user:<userId>
```

如果用户覆盖存在，就再合并到全局 flags 上：

```ts
merge(globalFlags, userOverrideSnapshot.data as Partial<IFeatureFlags>)
```

最后，`getServerFeatureFlagsStateFromRuntimeConfig(userId)` 会把 merged flags 交给 `mapFeatureFlagsEnvToState(flags, userId)`，转换成客户端/状态层需要的 feature flag state。

根据当前片段推断，这套 runtimeConfig provider 目前主要服务 feature flags，但抽象本身是泛型的，可以继续扩展到其他服务端运行时配置域。依据是 provider 和 domain 都是泛型设计，且 `src/server/runtimeConfig/index.ts` 只导出通用 provider 与 types，没有绑定 feature flags。

## 小白阅读顺序

1. 先读 `src/server/runtimeConfig/types.ts`

   重点看 `RuntimeConfigProvider<T>`、`RuntimeConfigDomain<T>`、`RuntimeConfigSelector`。这里决定了所有 provider 的共同协议。

2. 再读 `src/server/runtimeConfig/providers/index.ts`

   这个文件很短，只是确认当前有哪些 provider 对外暴露。

3. 读 `EnvRuntimeConfigProvider.ts`

   它最简单，适合理解 provider 的最小实现：拿到 data，包装成 snapshot，返回。

4. 读 `CompositeRuntimeConfigProvider.ts`

   理解 primary/fallback 的回退机制。这个文件能解释为什么 feature flags 可以“Redis 优先，环境变量兜底”。

5. 读 `RedisRuntimeConfigProvider.ts`

   重点看四块：`isEnabled()`、cache key 生成、Redis 读取、JSON/schema 解析。不要一开始陷入缓存清理细节，先抓住“读 Redis 并校验成 snapshot”的主线。

6. 最后读 `src/server/featureFlags/index.ts`

   这是最直接的业务调用方。看它如何定义 domain、如何创建 provider、如何合并默认配置、全局配置和用户覆盖。

7. 有余力再读 `RedisRuntimeConfigProvider.test.ts`

   测试比实现更容易暴露作者关心的边界：版本化 envelope、Redis disabled、缓存空结果、selector 级缓存过期。

## 常见误区

1. 误以为 `providers` 定义了 feature flag 的字段

   实际字段定义在 `FeatureFlagsSchema`、`DEFAULT_FEATURE_FLAGS` 等 feature flag 配置模块中。`providers` 只负责读取和包装，不关心业务字段含义。

2. 误以为 Env provider 会读取 `process.env`

   `EnvRuntimeConfigProvider` 不直接访问环境变量。它只接收 `getSnapshotData` 回调。当前 feature flags 场景下，真正读取/转换环境变量的是 `getServerFeatureFlagsValue()`。

3. 误以为 Redis provider 返回的都是 Redis 原始值

   Redis 中读出的字符串必须经过 JSON parse 和 Zod schema 校验。校验失败时返回 `null`，不会把脏数据继续传给业务层。

4. 误以为 Redis 没值时每次都会重新查 Redis

   `RedisRuntimeConfigProvider` 会缓存 `null` 快照。也就是说，“没有配置”也是一种缓存结果，在 `cacheTtlMs` 内不会重复访问 Redis。

5. 误以为 `CompositeRuntimeConfigProvider.isEnabled()` 表示 primary 可用

   它返回的是 `primary.isEnabled() || fallback.isEnabled()`。只要任一来源可用，组合 provider 就被认为可用。真正读取时仍然遵循 primary 优先、fallback 兜底。

6. 误以为 `version` 一定代表真实配置版本

   Redis envelope 中的 `version` 可以代表发布版本；但 Env provider 固定返回 `version: 0`，旧格式 Redis 数据也会补 `version: 0`。所以使用版本号前要确认数据来源。

7. 误以为 `selector` 只是参数透传

   `selector` 会影响 Redis key 和本地缓存 key。全局配置和用户级配置会被分开缓存，用户级 selector 形如 `user:<id>`。

8. 误以为 `getVersionKey` 已经被 Redis provider 使用

   当前 `RedisRuntimeConfigProvider.ts` 没有读取 `domain.getVersionKey`。它只用 `getStorageKey` 获取数据 key。`getVersionKey` 可能是为其他模块或后续扩展准备的，不能假设这里已经实现版本 key 查询逻辑。
