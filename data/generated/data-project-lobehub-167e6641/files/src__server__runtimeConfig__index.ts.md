# `src/server/runtimeConfig/index.ts` 文件说明

## 文件职责

路径：`/data/project/lobehub/src/server/runtimeConfig/index.ts`

这个文件本身非常短，但角色很明确：

- 它不是业务实现文件
- 它是 `runtimeConfig` 子系统的公共出口文件

源码只有两行：

```ts
export * from './providers';
export * from './types';
```

## 它为什么存在

如果没有这个文件，其他模块在使用运行时配置能力时，就得分别写：

- `@/server/runtimeConfig/providers`
- `@/server/runtimeConfig/types`

有了这个公共出口之后，调用方只需要写：

```ts
import { CompositeRuntimeConfigProvider, RuntimeConfigDomain } from '@/server/runtimeConfig';
```

好处有三个：

1. import 路径更短
2. `runtimeConfig` 对外暴露的边界更清晰
3. 以后内部目录调整时，调用方受影响更小

## 主要导入 / 依赖代表什么

这个文件没有 `import`。

这恰恰说明它的角色不是“做事”，而是“转发公开接口”。

它依赖的是两个同目录下的模块边界：

- `./providers`
  放具体 provider 实现
- `./types`
  放运行时配置抽象类型

## 主要导出 / 函数 / 类 / 组件逐个解释

虽然这个文件没有函数和类，但它导出了两个很关键的出口。

### `export * from './providers'`

这条语句把 provider 相关能力统一导出。

从同目录文件可以确认，当前主要 provider 有：

- `CompositeRuntimeConfigProvider`
  先问主 provider，拿不到再问 fallback provider
- `EnvRuntimeConfigProvider`
  直接从环境配置派生快照
- `RedisRuntimeConfigProvider`
  从 Redis 读取运行时配置，并带缓存与 schema 校验

这三者组合起来，表达的是一个很典型的策略：

- 优先读动态配置
- 没有动态配置时，回退到环境默认值

### `export * from './types'`

这条语句把抽象类型统一导出。

其中最值得先认识的概念有：

- `RuntimeConfigSelector`
  说明“要取全局配置，还是某个用户维度配置”
- `VersionedSnapshot<T>`
  配置快照长什么样
- `RuntimeConfigDomain<T>`
  一个配置域需要提供哪些规则，例如 key、schema、cache TTL
- `RuntimeConfigProvider<T>`
  一个 provider 至少要实现什么接口

换句话说：

- `types` 定义游戏规则
- `providers` 提供具体玩家

## 输入 / 输出 / 副作用

### 输入

这个文件没有函数输入。

它的“输入”可以理解成同目录下两个子模块：

- `providers`
- `types`

### 输出

它向外输出一个稳定的模块入口，让调用方能从一个地方拿到：

- provider 实现
- provider 抽象类型

### 副作用

没有副作用。

这个文件不会读 Redis、不会读 env、不会注册任何监听器。它只做导出汇总。

## 它被谁使用或可能被谁使用

当前代码里一个非常直接的使用者是：

- `src/server/featureFlags/index.ts`

这个文件会从 `@/server/runtimeConfig` 里同时拿：

- `RuntimeConfigDomain`
- `RuntimeConfigProvider`
- `RuntimeConfigSelector`
- `CompositeRuntimeConfigProvider`
- `EnvRuntimeConfigProvider`
- `RedisRuntimeConfigProvider`

也就是说，这个入口文件的价值不是“自己有逻辑”，而是让 `featureFlags` 这种调用者不用关心内部文件拆分。

未来任何新的运行时配置域，例如：

- 用户级开关
- 灰度配置
- 某类系统能力开关

都可以继续复用这一出口。

## 小白阅读建议

读这个文件时，不要因为它只有两行就觉得“没有内容”。

正确读法是：

1. 先看这两行，理解它是 barrel export
2. 立刻跳到 `types.ts`
3. 再看 `providers/CompositeRuntimeConfigProvider.ts`
4. 最后回头看 `src/server/featureFlags/index.ts`

这样你才能真正理解：

- 为什么需要这个公共入口
- 它把哪些概念打包成一个完整子系统
