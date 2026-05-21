# 文件：src/server/runtimeConfig/index.ts

```ts
export * from './providers';
export * from './types';
```

## 它负责什么

`src/server/runtimeConfig/index.ts` 是 `runtimeConfig` 模块的统一出口文件，也就是常说的 **barrel file**。

它本身不实现业务逻辑、不读取 Redis、不解析环境变量，也不定义具体的运行时配置规则。它的职责很单一：

把 `src/server/runtimeConfig/` 目录下对外需要使用的类型和 Provider 统一导出，方便其他模块通过一个稳定路径导入。

例如调用方可以这样写：

```ts
import {
  CompositeRuntimeConfigProvider,
  EnvRuntimeConfigProvider,
  RedisRuntimeConfigProvider,
  type RuntimeConfigDomain,
  type RuntimeConfigProvider,
  type RuntimeConfigSelector,
} from '@/server/runtimeConfig';
```

而不需要分别写成：

```ts
import type { RuntimeConfigDomain } from '@/server/runtimeConfig/types';
import { RedisRuntimeConfigProvider } from '@/server/runtimeConfig/providers/RedisRuntimeConfigProvider';
```

所以，这个文件的核心作用是：

1. 统一模块边界。
2. 隐藏内部文件结构。
3. 给上层业务提供稳定的导入入口。
4. 让 `runtimeConfig` 看起来像一个完整的小模块，而不是一堆零散文件。

## 关键组成

这个文件只有两行，但每一行都代表一组能力。

### `export * from './providers';`

这一行导出 `providers` 目录的统一出口。

`src/server/runtimeConfig/providers/index.ts` 又继续导出了三个 Provider：

```ts
export * from './CompositeRuntimeConfigProvider';
export * from './EnvRuntimeConfigProvider';
export * from './RedisRuntimeConfigProvider';
```

也就是说，通过 `@/server/runtimeConfig` 可以拿到这些类：

| 导出项 | 作用 |
| --- | --- |
| `RedisRuntimeConfigProvider` | 从 Redis 读取运行时配置，并带本地短缓存和 schema 校验 |
| `EnvRuntimeConfigProvider` | 从环境变量或服务端配置函数中读取运行时配置，通常作为兜底 |
| `CompositeRuntimeConfigProvider` | 组合两个 Provider，优先读 primary，失败或无数据时读 fallback |

这三个 Provider 都实现同一个接口：

```ts
RuntimeConfigProvider<T>
```

它们的目标不是绑定某一种业务，而是提供一套通用的“运行时配置读取机制”。

### `export * from './types';`

这一行导出运行时配置系统的基础类型。

主要包括：

| 类型 | 作用 |
| --- | --- |
| `RuntimeConfigSelector` | 表示读取配置的范围，可以是全局配置，也可以是用户级配置 |
| `RuntimeConfigGlobalSelector` | 全局配置选择器，形如 `{ scope: 'global' }` |
| `RuntimeConfigUserSelector` | 用户配置选择器，形如 `{ scope: 'user', id: string }` |
| `VersionedSnapshot<T>` | 带版本号和更新时间的配置快照 |
| `RuntimeConfigDomain<T>` | 描述一个配置领域，比如 key、Redis key 生成方式、schema、缓存时间 |
| `RuntimeConfigProvider<T>` | 所有配置读取器必须实现的统一接口 |

其中最核心的是这两个：

```ts
export interface RuntimeConfigDomain<T> {
  cacheTtlMs: number;
  getStorageKey: (selector?: RuntimeConfigSelector) => string;
  getVersionKey?: (selector?: RuntimeConfigSelector) => string;
  key: string;
  schema: ZodSchema<T>;
}
```

`RuntimeConfigDomain<T>` 描述“这类配置长什么样、放在哪里、怎么校验”。

```ts
export interface RuntimeConfigProvider<T> {
  domain: RuntimeConfigDomain<T>;
  getSnapshot: (selector?: RuntimeConfigSelector) => Promise<VersionedSnapshot<T> | null>;
  isEnabled: () => boolean;
}
```

`RuntimeConfigProvider<T>` 描述“配置读取器应该具备什么能力”。

## 上下游关系

虽然 `index.ts` 自己没有业务逻辑，但它处在一个很重要的位置：**它是 runtimeConfig 模块对外暴露的门面**。

### 上游：它从哪里拿东西

`index.ts` 的上游只有两个相邻模块：

```ts
export * from './providers';
export * from './types';
```

也就是：

```text
src/server/runtimeConfig/
├── index.ts
├── types.ts
└── providers/
    ├── index.ts
    ├── CompositeRuntimeConfigProvider.ts
    ├── EnvRuntimeConfigProvider.ts
    └── RedisRuntimeConfigProvider.ts
```

它从 `types.ts` 导出抽象定义，从 `providers/index.ts` 导出具体实现。

可以把它理解为：

```text
types.ts                  定义协议
providers/*.ts            实现协议
runtimeConfig/index.ts    对外统一暴露协议和实现
```

### 下游：谁在使用它

一个典型下游是：

```ts
src/server/featureFlags/index.ts
```

该文件从 `@/server/runtimeConfig` 导入这些内容：

```ts
import type {
  RuntimeConfigDomain,
  RuntimeConfigProvider,
  RuntimeConfigSelector,
} from '@/server/runtimeConfig';

import {
  CompositeRuntimeConfigProvider,
  EnvRuntimeConfigProvider,
  RedisRuntimeConfigProvider,
} from '@/server/runtimeConfig';
```

它用这些能力构建了 feature flags 的运行时配置读取逻辑。

大致关系是：

```text
src/server/featureFlags/index.ts
        │
        │ import
        ▼
src/server/runtimeConfig/index.ts
        │
        ├── exports types.ts
        │
        └── exports providers/index.ts
```

也就是说，`featureFlags` 不需要知道 `RedisRuntimeConfigProvider` 的真实文件路径，它只依赖 `@/server/runtimeConfig` 这个模块入口。

### 业务层如何使用 runtimeConfig

以 feature flags 为例，它会定义一个具体配置领域：

```ts
const FEATURE_FLAGS_DOMAIN: RuntimeConfigDomain<IFeatureFlags> = {
  cacheTtlMs: 5000,
  getStorageKey: () => 'runtime-config:feature-flags:published',
  getVersionKey: () => 'runtime-config:feature-flags:version',
  key: 'feature-flags',
  schema: FeatureFlagsSchema,
};
```

然后组装 Provider：

```ts
new CompositeRuntimeConfigProvider(
  new RedisRuntimeConfigProvider(FEATURE_FLAGS_DOMAIN),
  new EnvRuntimeConfigProvider(FEATURE_FLAGS_DOMAIN, {
    getSnapshotData: () => getServerFeatureFlagsValue(),
  }),
);
```

含义是：

1. 优先从 Redis 读取线上运行时配置。
2. 如果 Redis 不可用或没有配置，则从环境变量配置兜底。
3. 返回统一的 `VersionedSnapshot<T> | null`。

这里 `index.ts` 的价值就体现出来了：调用方只需要依赖一个入口，不需要关心内部文件拆分。

## 运行/调用流程

`src/server/runtimeConfig/index.ts` 在运行时没有主动流程，它不会自己执行读取配置的动作。

真正的调用流程发生在下游业务模块中。以 feature flags 为例，可以按这个顺序理解：

```text
业务代码需要读取 feature flags
        │
        ▼
调用 getServerFeatureFlagsFromRuntimeConfig(userId?)
        │
        ▼
创建或复用 CompositeRuntimeConfigProvider
        │
        ▼
CompositeRuntimeConfigProvider.getSnapshot(selector)
        │
        ├── 先问 RedisRuntimeConfigProvider 是否可用
        │       │
        │       ├── Redis 可用：从 Redis key 读取配置
        │       ├── JSON.parse
        │       ├── 用 domain.schema 做 zod 校验
        │       ├── 包装成 VersionedSnapshot<T>
        │       └── 写入短期内存缓存
        │
        └── Redis 没有结果时，问 EnvRuntimeConfigProvider
                │
                ├── 调用 getSnapshotData(selector)
                └── 包装成 version = 0 的 VersionedSnapshot<T>
```

对应到 `runtimeConfig/index.ts` 的角色：

```text
业务模块
  import {...} from '@/server/runtimeConfig'
                  │
                  ▼
          runtimeConfig/index.ts
                  │
        统一转发 types 和 providers
```

所以它不是“执行者”，而是“入口”。

更准确地说：

| 文件 | 角色 |
| --- | --- |
| `runtimeConfig/index.ts` | 模块门面，统一导出 |
| `runtimeConfig/types.ts` | 定义运行时配置协议 |
| `runtimeConfig/providers/*.ts` | 实现不同来源的配置读取 |
| `server/featureFlags/index.ts` | 使用 runtimeConfig 构建具体业务配置 |

## 小白阅读顺序

建议不要从 `index.ts` 本身停留太久，因为它只有两行。它更像目录地图。推荐按下面顺序读：

### 1. 先读 `src/server/runtimeConfig/index.ts`

目的：确认它只是统一出口。

你只需要记住：

```ts
export * from './providers';
export * from './types';
```

这说明真正内容在 `providers` 和 `types` 里。

### 2. 再读 `src/server/runtimeConfig/types.ts`

这是理解整个模块的关键。

重点看三个概念：

```ts
RuntimeConfigDomain<T>
RuntimeConfigProvider<T>
VersionedSnapshot<T>
```

可以这样理解：

```text
RuntimeConfigDomain<T>      描述配置属于哪个领域、怎么取 key、怎么校验
RuntimeConfigProvider<T>    描述一个配置读取器必须提供什么方法
VersionedSnapshot<T>        描述读取出来的配置快照
```

如果你理解了这三个类型，后面的 Provider 就很好读。

### 3. 再读 `src/server/runtimeConfig/providers/EnvRuntimeConfigProvider.ts`

这是最简单的 Provider。

它不连接外部存储，只调用传入的函数：

```ts
getSnapshotData(selector)
```

然后把结果包装成：

```ts
{
  data,
  updatedAt: '1970-01-01T00:00:00.000Z',
  version: 0,
}
```

它适合当兜底配置来源。

### 4. 再读 `src/server/runtimeConfig/providers/RedisRuntimeConfigProvider.ts`

这是实际线上动态配置的主要读取器。

重点看：

```ts
isEnabled()
getSnapshot()
resolveEnvelopeData()
```

它做了几件事：

1. 判断 Redis 是否启用。
2. 根据 `domain.getStorageKey(selector)` 得到 Redis key。
3. 从 Redis 读字符串。
4. 解析 JSON。
5. 用 `domain.schema` 做 zod 校验。
6. 包装成 `VersionedSnapshot<T>`。
7. 用 `cacheTtlMs` 做短期内存缓存。

### 5. 再读 `src/server/runtimeConfig/providers/CompositeRuntimeConfigProvider.ts`

这个文件解释了为什么系统可以“Redis 优先，环境变量兜底”。

核心逻辑是：

```ts
if (this.primary.isEnabled()) {
  const snapshot = await this.primary.getSnapshot(selector);
  if (snapshot) return snapshot;
}

if (!this.fallback.isEnabled()) return null;

return this.fallback.getSnapshot(selector);
```

也就是：

```text
先读 primary
primary 没数据，再读 fallback
```

### 6. 最后读调用方，例如 `src/server/featureFlags/index.ts`

这一步是为了看 runtimeConfig 如何落到具体业务。

你会看到 feature flags 定义了自己的 `RuntimeConfigDomain`，然后把 Redis Provider 和 Env Provider 组合起来使用。

## 常见误区

### 误区一：以为 `index.ts` 里有运行时配置逻辑

没有。

这个文件只有导出逻辑：

```ts
export * from './providers';
export * from './types';
```

真正的读取、缓存、校验、兜底都在相邻文件里。

### 误区二：以为 `runtimeConfig` 只服务 feature flags

不是。

`featureFlags` 只是当前代码里一个典型调用方。`runtimeConfig` 模块本身是通用机制，理论上任何“服务端运行时可变配置”都可以用它。

比如只要定义一个新的：

```ts
RuntimeConfigDomain<MyConfig>
```

再选择合适的 Provider，就可以接入这套机制。

### 误区三：以为 Redis 里的数据可以随便写

不可以。

`RedisRuntimeConfigProvider` 会用 `domain.schema.safeParse(...)` 校验数据。

也就是说，Redis 里即使有值，如果不符合对应 domain 的 zod schema，也会被视为无效，最终返回 `null`。

### 误区四：以为 `EnvRuntimeConfigProvider` 真的读取 `process.env`

不一定。

它本身不直接读 `process.env`，而是调用构造时传入的函数：

```ts
getSnapshotData: (selector?: RuntimeConfigSelector) => T | null
```

在 feature flags 里，这个函数是：

```ts
getSnapshotData: () => getServerFeatureFlagsValue()
```

所以它更准确的名字含义是：用“环境派生出来的服务端静态配置”作为来源，而不是 Provider 内部硬编码读取环境变量。

### 误区五：以为 `CompositeRuntimeConfigProvider` 会合并两个配置

不会。

它不是 merge provider。

它的逻辑是：

```text
primary 有 snapshot：直接返回 primary
primary 没 snapshot：返回 fallback
```

它不会把 Redis 的部分字段和环境变量的部分字段自动深合并。

真正的合并逻辑如果需要，通常在业务层完成。比如 feature flags 会把默认值和读取到的配置进行 merge：

```ts
const globalFlags = merge(DEFAULT_FEATURE_FLAGS, globalSnapshot?.data || {});
```

### 误区六：以为 `selector` 只是普通参数，没有设计意义

`selector` 是 runtimeConfig 支持“全局配置”和“用户级配置”的关键。

它可能是：

```ts
{ scope: 'global' }
```

也可能是：

```ts
{ scope: 'user', id: userId }
```

Redis Provider 会根据 selector 区分缓存 key；业务 domain 也可以根据 selector 生成不同 Redis storage key。

例如用户级 feature flag override 会根据用户 ID 生成不同 key：

```ts
runtime-config:feature-flags:user:${selector.id}
```

### 误区七：以为 `VersionedSnapshot<T>` 的版本一定来自 Redis

不一定。

Redis 中如果存的是完整 envelope：

```ts
{
  data,
  updatedAt,
  version,
}
```

Provider 会使用里面的版本信息。

但如果 Redis 中存的是裸配置对象，Provider 会兼容处理，把它包装成：

```ts
{
  data,
  updatedAt: new Date().toISOString(),
  version: 0,
}
```

而 Env Provider 永远返回固定版本：

```ts
version: 0
updatedAt: '1970-01-01T00:00:00.000Z'
```

这表示它是静态兜底来源，不代表真实发布时间。

### 误区八：以为这个 `runtimeConfig` 和前端状态里的 `runtimeConfig` 是同一个概念

不一定。

当前文件属于：

```text
src/server/runtimeConfig/
```

它是服务端运行时配置读取机制。

代码库里其他地方也可能出现变量名 `runtimeConfig`，例如 AI provider runtime state、agent runtime config 等。那些未必和这个模块有关。判断是否有关，关键看是否从这里导入：

```ts
@/server/runtimeConfig
```

### 误区九：以为 barrel file 没价值

在小项目里，barrel file 可能显得多余。但在这个仓库里它有实际价值：

1. 稳定导入路径。
2. 降低调用方对内部目录结构的耦合。
3. 方便未来调整 Provider 文件组织。
4. 让 `runtimeConfig` 作为一个模块被使用，而不是暴露一堆内部路径。

这个文件虽然短，但它定义了模块边界。它告诉读代码的人：`runtimeConfig` 对外公开的东西，就是 `types` 和 `providers`。

---

> 本页已由独立 Codex agent 使用 gpt-5.5 medium 读取 LobeHub 真实源码后增强。
