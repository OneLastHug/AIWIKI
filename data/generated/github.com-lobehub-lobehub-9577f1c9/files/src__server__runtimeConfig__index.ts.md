# 文件：src/server/runtimeConfig/index.ts

## 它负责什么

这个文件是 `runtimeConfig` 模块的**统一出口**，本身不实现业务逻辑，只做两件事：

1. 把 `./providers` 里的三种 provider 实现重新导出。
2. 把 `./types` 里的 runtime config 类型重新导出。

所以外部代码只要 import `@/server/runtimeConfig`，就能拿到这套运行时配置系统的核心接口和实现入口，而不用关心具体文件分布。

## 关键组成

当前文件内容非常短，实际暴露的是下面两类东西：

- `providers`
  - `CompositeRuntimeConfigProvider`
  - `EnvRuntimeConfigProvider`
  - `RedisRuntimeConfigProvider`
- `types`
  - `RuntimeConfigSelector`
  - `RuntimeConfigDomain`
  - `RuntimeConfigProvider`
  - `VersionedSnapshot`

结合同目录实现文件，可以把这套系统理解成三层：

- `types.ts` 定义抽象协议
- `providers/*` 提供具体读取策略
- `index.ts` 提供统一对外入口

其中几个关键概念是：

- `RuntimeConfigDomain<T>`：描述一个配置域，包含 `key`、`schema`、`cacheTtlMs`、`getStorageKey` 等信息。
- `RuntimeConfigSelector`：区分 `global` 和 `user` 两种作用域。
- `RuntimeConfigProvider<T>`：统一 provider 接口，必须提供 `isEnabled()` 和 `getSnapshot()`。
- `VersionedSnapshot<T>`：runtime config 的标准返回包，带 `data`、`updatedAt`、`version`。

## 上下游关系

上游是需要“按运行时读取配置”的服务层。当前检索到的直接消费者是：

- `src/server/featureFlags/index.ts`

这个文件会从 `@/server/runtimeConfig` 引入：

- `RuntimeConfigDomain`
- `RuntimeConfigProvider`
- `RuntimeConfigSelector`
- `CompositeRuntimeConfigProvider`
- `EnvRuntimeConfigProvider`
- `RedisRuntimeConfigProvider`

然后为 feature flags 构造两套 domain：

- 全局 feature flags
- 用户级 feature flags override

下游则是具体 provider 实现：

- `CompositeRuntimeConfigProvider`：主提供者失败时回退到 fallback
- `EnvRuntimeConfigProvider`：从环境变量派生 snapshot
- `RedisRuntimeConfigProvider`：从 Redis 读取、校验、缓存 snapshot

换句话说，这个 `index.ts` 是“门面”，真正执行读写策略的是 `providers` 子目录。

## 运行/调用流程

根据当前片段推断，典型调用链如下：

1. 业务方 import `@/server/runtimeConfig`。
2. 业务方先定义一个 `RuntimeConfigDomain<T>`，描述某个配置域的 key、schema 和存储 key 规则。
3. 业务方实例化 provider，例如：
   - `new RedisRuntimeConfigProvider(domain)`
   - `new EnvRuntimeConfigProvider(domain, { getSnapshotData })`
   - `new CompositeRuntimeConfigProvider(primary, fallback)`
4. 调用 `provider.getSnapshot(selector)`。
5. `RedisRuntimeConfigProvider` 会先查内存缓存，再查 Redis，再做 schema 校验。
6. `EnvRuntimeConfigProvider` 直接从回调拿数据，包装成固定版本的 snapshot。
7. `CompositeRuntimeConfigProvider` 先尝试 primary，primary 没结果时再走 fallback。
8. 上层业务把 snapshot 的 `data` 合并进最终配置，例如 feature flags 场景里会先拿全局配置，再叠加用户级 override。

在 `src/server/featureFlags/index.ts` 里，这条链路很清楚：

- 全局 flags：`RedisRuntimeConfigProvider` + `EnvRuntimeConfigProvider` 组成 `CompositeRuntimeConfigProvider`
- 用户 override：直接用 `RedisRuntimeConfigProvider`
- 最后按 `global -> user` 的顺序 merge

## 小白阅读顺序

1. 先看 [src/server/runtimeConfig/index.ts](src/server/runtimeConfig/index.ts)，确认它只是出口文件。
2. 再看 [src/server/runtimeConfig/types.ts](src/server/runtimeConfig/types.ts)，搞清楚 `domain / selector / snapshot / provider` 四个概念。
3. 然后看 [src/server/runtimeConfig/providers/EnvRuntimeConfigProvider.ts](src/server/runtimeConfig/providers/EnvRuntimeConfigProvider.ts)，理解最简单的 provider。
4. 再看 [src/server/runtimeConfig/providers/RedisRuntimeConfigProvider.ts](src/server/runtimeConfig/providers/RedisRuntimeConfigProvider.ts)，理解缓存、Redis 读取和 schema 校验。
5. 最后看 [src/server/runtimeConfig/providers/CompositeRuntimeConfigProvider.ts](src/server/runtimeConfig/providers/CompositeRuntimeConfigProvider.ts)，理解回退策略。
6. 用 [src/server/featureFlags/index.ts](src/server/featureFlags/index.ts) 作为真实调用样例，把抽象和业务串起来。

## 常见误区

- 误以为 `index.ts` 自己实现了配置逻辑。实际上它只是 re-export，没有任何运行时代码。
- 误以为 `CompositeRuntimeConfigProvider` 会合并两个 provider 的结果。它不会，只是“主 provider 优先，失败后回退”。
- 误以为 `EnvRuntimeConfigProvider` 只在开发环境可用。它的 `isEnabled()` 恒为 `true`，只是 `getSnapshotData()` 可能返回 `null`。
- 误以为 Redis provider 一定命中。它有本地缓存、Redis 读取、JSON 解析、schema 校验，任何一步失败都可能返回 `null`。
- 误以为 selector 只有用户 id。实际上它还区分 `scope: 'global' | 'user'`，很多 key 生成逻辑都依赖这个字段。
- 误以为新增 provider 只要写实现类就够了。通常还需要同步更新 `providers/index.ts`，并确保根入口 `src/server/runtimeConfig/index.ts` 继续 re-export 到位。
