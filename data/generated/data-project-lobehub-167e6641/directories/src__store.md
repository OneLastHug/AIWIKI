# `src/store` 目录说明

## 这个目录在项目中的位置

- 仓库位置：`/data/project/lobehub/src/store`
- 它位于前端业务层中枢，主要承载 Zustand 状态管理

## 它负责什么

`src/store` 负责保存和组织前端状态。

这里不只是“几个全局变量”：

- 它保存页面状态
- 保存聊天消息状态
- 保存 Agent / Group / Page / Task / Resource 等业务域状态
- 保存服务端下发的能力开关
- 保存桌面端同步状态

当前目录里能看到很多业务域 store，例如：

- `global`
- `chat`
- `agent`
- `agentGroup`
- `serverConfig`
- `electron`
- `page`
- `task`
- `tool`
- `user`

## 初学者应该先看哪些文件

推荐顺序：

1. `src/store/global/store.ts`
   看最基础的 store 装配模式。
2. `src/store/global/initialState.ts`
   看它保存哪些 UI 级状态。
3. `src/store/chat/store.ts`
   看一个重量级业务 store 如何由多个 slice 拼起来。
4. `src/store/chat/initialState.ts`
5. `src/store/agent/store.ts`
   看 Agent 配置相关状态如何拆。
6. `src/store/serverConfig/store.ts`
   看服务端配置如何进入前端状态。
7. `src/store/serverConfig/action.ts`
   看 SWR 初始化如何和 store 配合。
8. `src/store/electron/store.ts`
   看桌面端状态如何接到前端。

## 它和其他目录如何交互

典型关系如下：

```text
src/features/*
-> useXxxStore(selector)
-> store action / selector / state
-> 需要时再调用 src/services/*
```

也就是说：

- `features` 读写 store
- `services` 负责发请求或调桥接能力
- store 接住结果并让 UI 重渲染

某些初始化链还会反过来这样走：

```text
SPAGlobalProvider
-> StoreInitialization
-> useInitServerConfig / useInitUserState
-> service 请求
-> store 写入
```

## 这个目录最常见的组织模式

很多业务域都会长成类似结构：

```text
store/<domain>/
├─ initialState.ts
├─ store.ts
├─ selectors.ts
├─ action.ts 或 actions/*
└─ slices/*
```

你可以这样理解这些文件：

- `initialState.ts`
  这个业务域默认有哪些状态
- `store.ts`
  真正创建 Zustand store，并把 actions / slices 拼起来
- `selectors.ts`
  给组件提供更稳定、更语义化的读取方式
- `action.ts` / `actions/*`
  组织业务动作
- `slices/*`
  把大 store 按子域切开

## 常见概念解释

### `slice`

一个大 store 里的子模块。

比如 `chat` store 不会把所有动作和状态全写一个文件，而是拆成：

- `message`
- `thread`
- `topic`
- `builtinTool`
- `portal`
- `operation`
- `aiAgent`

这样读起来更像分章，而不是一整本没目录的书。

### `selector`

一个专门负责“从大状态树里拿某个小结果”的函数。

好处：

- 组件代码更干净
- 选择逻辑可复用
- 以后状态结构改了，受影响面更小

### `flattenActions`

这是这个仓库 store 装配里很常见的辅助模式。

作用是把多个 action/slice 产出的对象摊平，最后合成一个 store API。

### `ResetableStoreAction`

一些 store 会挂一个统一的 reset 能力，方便离开页面或重建上下文时清空状态。

### 为什么有的 store 用 class action，有的用函数 action

这是实现风格问题，不代表层级不同。

你会同时看到：

- `createXxxSlice(...)`
- `new XxxActionImpl(...)`

本质上都是在往 store 里装“动作”。

## 这个目录里几个特别重要的 store

### `serverConfig`

这是“服务端能力和前端 UI 之间的桥”。

它保存：

- serverConfig
- featureFlags
- billboard
- `isMobile`

而且它既吃首屏注入的配置，也会再发请求拿新配置。

### `chat`

这是聊天主链的核心 store。

它非常重，承载消息、主题、线程、工具状态等多个切片。

### `global`

更偏 UI 框架级状态，例如：

- 当前侧边栏状态
- 面板开合
- 一些系统偏好
- 导航引用

### `electron`

桌面端特有状态，例如：

- 远端服务同步
- 导航历史
- 最近页面
- 桌面设置

## 需要暂时跳过的内容

初学者建议先别一口气通读所有 store：

- `eval`
- `library`
- `userMemory`
- `tree`
- `video`
- `image`
- 各类测试文件

先把 `global`、`chat`、`agent`、`serverConfig` 读明白，很多模式就会自动套用到别的 store。

## 一句话阅读建议

这个目录最重要的不是背下每个 store 的字段，而是先看懂它们共同的装配套路。
