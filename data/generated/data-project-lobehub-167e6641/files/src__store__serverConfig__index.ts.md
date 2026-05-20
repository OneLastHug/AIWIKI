# `src/store/serverConfig/index.ts` 文件说明

## 文件职责

路径：`/data/project/lobehub/src/store/serverConfig/index.ts`

这个文件是 `serverConfig` 前端状态模块的公共入口。

源码很短：

```ts
export { featureFlagsSelectors, serverConfigSelectors } from './selectors';
export { getServerConfigStoreState, useServerConfigStore } from './store';
```

它的核心作用是：

- 对外暴露最常用的读取入口
- 隐藏内部更多实现细节

## 它为什么存在

如果没有这个文件，外部代码可能到处这样 import：

- `@/store/serverConfig/selectors`
- `@/store/serverConfig/store`
- 甚至更深层的内部文件

这会带来两个问题：

1. 外部代码会越来越依赖内部结构
2. 以后 `serverConfig` 模块重构时，改动面会变得很大

所以这个文件的存在，本质上是在定义：

- `serverConfig` 这个 store 模块“推荐别人怎么用我”

## 主要导入 / 依赖代表什么

这个文件本身没有显式 `import`，它直接 re-export 了两个内部模块：

- `./selectors`
  负责把原始状态包装成更好读的选择器
- `./store`
  负责真正创建和暴露 Zustand store

你可以把它理解成：

- `selectors` 像“查询目录”
- `store` 像“仓库本体”

## 主要导出 / 函数 / 类 / 组件逐个解释

### `featureFlagsSelectors`

这是一个快捷选择器入口。

它让调用方可以直接拿到：

- 当前 feature flags 状态

在 UI 层里，经常会看到类似：

```ts
const flags = useServerConfigStore(featureFlagsSelectors);
```

这样的代码比手写一长串状态路径更清楚。

### `serverConfigSelectors`

这是一组语义化选择器。

从同目录 `selectors.ts` 可以直接看到，它封装了很多高频布尔判断和字段读取，例如：

- `enableBusinessFeatures`
- `enableKlavis`
- `enableLobehubSkill`
- `enableVisualUnderstanding`
- `disableEmailPassword`
- `oAuthSSOProviders`
- `isMobile`

这意味着页面代码不需要自己反复写：

- `s.serverConfig.xxx || false`

而是可以直接说：

- “我需要这个能力是否启用”

### `useServerConfigStore`

这是 React 组件里最重要的读取入口。

它是一个 Zustand hook，用来：

- 读 `serverConfig`
- 读 `featureFlags`
- 调用 store action，例如初始化拉取配置

很多前端页面和 hook 都直接依赖它，例如：

- `StoreInitialization`
- `InboxButton`
- `useGatewayReconnect`
- `useHotkeys`
- `ChatInput` 某些 feature

### `getServerConfigStoreState`

这是非 React 场景下的同步读取入口。

适合：

- 在普通函数里读当前 store 状态
- 不方便使用 React hook 的地方

它和 `useServerConfigStore` 的区别可以简单记成：

- 组件里用 `useServerConfigStore`
- 组件外、普通逻辑里用 `getServerConfigStoreState`

## 输入 / 输出 / 副作用

### 输入

这个文件本身没有函数参数输入。

但它对外暴露的两个主要入口会间接依赖：

- `ServerConfigStoreProvider` 注入的 store 实例
- `store.ts` 里创建的 Zustand store

### 输出

它输出的是“稳定公共 API”：

- selectors
- hook
- 非 hook 的读状态函数

### 副作用

这个文件本身没有副作用。

它不会主动发请求，也不会主动创建 provider。

真正的初始化发生在更下游：

- `src/layout/SPAGlobalProvider/index.tsx`
- `src/store/serverConfig/Provider.tsx`
- `src/store/serverConfig/store.ts`
- `src/store/serverConfig/action.ts`

## 它被谁使用或可能被谁使用

当前仓库里，`useServerConfigStore` 的使用非常广。

从现有代码能直接看到，使用者分布在：

- 主布局与首页
- 设置页
- 聊天输入区
- Onboarding
- Community 相关页面
- 移动端导航
- 桌面端某些适配 hook

这也从侧面证明：

- `serverConfig` 不是一个冷门 store
- 它实际上是“前端判断系统能力开关”的中心入口

## 小白阅读建议

读这个文件时，建议不要停留在“只有两行导出”。

更好的阅读顺序是：

1. 先看本文件，知道公共入口长什么样
2. 再看 `selectors.ts`
3. 再看 `store.ts`
4. 再看 `action.ts`
5. 最后把它和 `src/layout/SPAGlobalProvider/index.tsx`、`src/app/spa/[variants]/[[...path]]/route.ts` 串起来

这样你会明白一整条链：

```text
服务端注入 window.__SERVER_CONFIG__
-> ServerConfigStoreProvider 建 store
-> useInitServerConfig 再请求一次最新配置
-> 页面通过 useServerConfigStore / selectors 读取
```

这条链正是理解 LobeHub 前后端配置协作方式的最佳样本之一。
