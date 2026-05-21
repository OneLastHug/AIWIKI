# 文件：src/server/runtimeConfig/providers/index.ts

## 它负责什么

这个文件本身不承载业务逻辑，它是 `runtimeConfig/providers` 目录的入口出口文件，作用很单纯：把三个 provider 实现统一导出，方便上层只通过 `@/server/runtimeConfig` 一次性拿到所有实现。

它导出的三个类分别是：

- `CompositeRuntimeConfigProvider`
- `EnvRuntimeConfigProvider`
- `RedisRuntimeConfigProvider`

根据当前片段推断，这个 barrel file 的设计目的是让“运行时配置”模块对外保持稳定 API，而内部实现可以继续拆分、替换或扩展。

## 关键组成

这里没有函数体，核心信息都在导出项上。

- `CompositeRuntimeConfigProvider`  
  负责把两个 provider 组合起来，先读主来源，失败或无数据时回退到备用来源。

- `EnvRuntimeConfigProvider`  
  从环境变量或进程内函数计算结果中生成一个 `VersionedSnapshot<T>`，适合作为只读默认值来源。

- `RedisRuntimeConfigProvider`  
  从 Redis 读取持久化配置，并带有本地缓存、JSON 解析、Zod 校验和失效清理。

它们都实现同一个接口 `RuntimeConfigProvider<T>`，这个接口来自 `src/server/runtimeConfig/types.ts`，要求提供：

- `domain`
- `isEnabled()`
- `getSnapshot(selector?)`

## 上下游关系

上游是 `src/server/runtimeConfig/index.ts`，它把 `./providers` 和 `./types` 再次统一导出，因此外部通常不会直接深路径导入单个 provider，而是通过 `@/server/runtimeConfig` 使用。

真实调用方里，`src/server/featureFlags/index.ts` 是一个典型例子：

- 用 `RedisRuntimeConfigProvider` 作为主来源
- 用 `EnvRuntimeConfigProvider` 作为 fallback
- 再用 `CompositeRuntimeConfigProvider` 包起来

这说明 `providers/index.ts` 是一个“实现集合入口”，它服务的不是单一模块，而是整个 runtime config 体系。`featureFlags` 只是当前最典型的消费者。

## 运行/调用流程

1. 上层模块导入 `@/server/runtimeConfig`。
2. `src/server/runtimeConfig/index.ts` 继续转出 `providers/index.ts` 和 `types.ts`。
3. 调用方实例化某个 provider，或用 `CompositeRuntimeConfigProvider` 组合两个 provider。
4. 调用 `getSnapshot(selector)` 时：
   - `RedisRuntimeConfigProvider` 先查本地缓存，再查 Redis，再做 JSON 解析和 schema 校验；
   - `EnvRuntimeConfigProvider` 直接调用 `getSnapshotData()`，如果有值就包成固定版本的 snapshot；
   - `CompositeRuntimeConfigProvider` 先尝试 primary，拿不到再尝试 fallback。
5. 返回 `VersionedSnapshot<T> | null`，供上层做合并或覆盖。

这里的关键点是：`index.ts` 不参与运行流程本身，它只是让这条流程可被外部稳定引用。

## 小白阅读顺序

1. 先看 `src/server/runtimeConfig/types.ts`，弄清 `RuntimeConfigDomain`、`RuntimeConfigProvider`、`VersionedSnapshot` 是什么。
2. 再看 `src/server/runtimeConfig/providers/RedisRuntimeConfigProvider.ts`，理解主数据源怎么读、怎么缓存、怎么校验。
3. 接着看 `src/server/runtimeConfig/providers/EnvRuntimeConfigProvider.ts`，理解 fallback 如何把内存值包装成 snapshot。
4. 再看 `src/server/runtimeConfig/providers/CompositeRuntimeConfigProvider.ts`，理解“主来源 + 备用来源”的拼接策略。
5. 最后回到 `src/server/featureFlags/index.ts`，看真实业务如何把这些 provider 组装起来。

## 常见误区

- 误以为 `providers/index.ts` 有业务逻辑。实际上它只是出口文件，真正逻辑都在三个实现类里。
- 误以为 `CompositeRuntimeConfigProvider` 会合并两个来源的数据。它不会合并，只做“先主后备”的回退。
- 误以为 `EnvRuntimeConfigProvider` 读取的是固定环境变量名。根据当前代码片段推断，它实际依赖外部传入的 `getSnapshotData()`，所以数据源可以是任意计算结果。
- 误以为 `RedisRuntimeConfigProvider` 每次都会打 Redis。它有本地内存缓存，并且会缓存 `null` 结果。
- 误以为 `RuntimeConfigDomain.getVersionKey` 一定会被用到。当前看到的 provider 里没有直接使用它，至少在这组实现中它更像预留字段。
