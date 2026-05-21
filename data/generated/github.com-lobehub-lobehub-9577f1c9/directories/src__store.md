# 目录：src/store

## 它负责什么

`src/store` 是 LobeHub 前端 SPA 的客户端状态管理层，核心基于 `zustand`。它不只是“全局变量仓库”，而是把聊天、用户、全局 UI、工具、文件、页面、知识库、任务、模型基础设施等业务域拆成多个独立 store，再通过 `useXxxStore` hook 供 `src/features` 和 `src/routes` 消费。

从抽样文件看，每个业务域通常遵循同一套结构：`store.ts` 创建 Zustand store，`initialState.ts` 定义初始状态，`selectors.ts` 导出派生读取逻辑，`slices/` 拆分业务动作和子状态，`index.ts` 对外暴露类型与 hook。复杂 store 会再引入 reducer、helpers、utils、测试文件等。

这个目录的主要职责包括：

- 管理客户端 UI 状态，例如侧边栏展开、弹窗状态、分页、搜索关键字。
- 管理业务缓存，例如聊天消息、话题、会话、文件、页面、任务、模型、工具。
- 封装业务动作，例如 `createNewPage`、`refreshMessages`、`switchTopic`、`updateSystemStatus`。
- 提供 selectors，避免组件直接理解复杂状态结构。
- 为开发环境暴露调试入口，例如 `window.__LOBE_STORES`。
- 统一 store 创建、DevTools、reset、class action 扁平化等基础能力。

## 关键组成

`src/store/types.ts` 定义了通用 `StoreSetter<TStore>`，给 action class 使用，目的是让 `set` 支持 Zustand 的 partial 更新、replace 更新和 devtools action name。

`src/store/utils/flattenActions.ts` 是一个关键工具。仓库里很多 action 已经迁移成 class，例如 `new ChatTopicActionImpl(...params)`。普通对象展开无法复制 class prototype 上的方法，所以 `flattenActions` 会沿 prototype chain 扫描公开方法，并 bind 到原 action 实例，最后合并成 Zustand store 可直接挂载的 plain object。

`src/store/utils/resetableStore.ts` 提供 `ResetableStoreAction` 抽象类。具体 store 继承后只要声明 `resetActionName`，就能通过 `api.getInitialState()` 恢复初始状态，例如 `ChatStoreResetAction`、`UserStoreResetAction`、`PageStoreResetAction`。

`src/store/middleware/createDevtools.ts` 封装 Zustand devtools。它会检查 URL query 中的 `debug` 是否包含 store 名称，只有命中时才启用 devtools，并把名称格式化成 `Lobe_${name}`，开发环境追加 `_DEV`。

`src/store/middleware/expose.ts` 在开发环境把 store 注册到 `window.__LOBE_STORES[name]`，值是一个返回当前 `store.getState()` 的 getter，方便调试。

代表性业务域包括：

- `chat`：聊天核心 store，聚合 message、topic、thread、aiChat、plugin、builtinTool、portal、operation、aiAgent 等 slice。
- `user`：用户认证、设置、偏好、onboarding 等状态。
- `global`：全局 UI 和工作区状态，例如导航、侧边栏、系统状态。
- `page`：页面/文档列表、选择、创建、重命名、分页等状态。
- `tool`：插件、内置工具、MCP、skills、Klavis 等工具系统状态。
- `file`、`library`、`task`、`image`、`video`、`eval` 等：分别服务文件、知识库、任务、生成、多媒体和评测场景。

## 上下游关系

上游主要是 UI 组件、路由页面和服务层。

组件通常从 `src/features` 或 `src/routes` 中调用 `useXxxStore`。例如抽样调用点里，`src/features/DataImporter/index.tsx` 通过 `useChatStore` 取 `refreshMessages`、`refreshTopics`；`src/routes/(main)/home/_layout/hooks/useCreateMenuItems.tsx` 通过 `usePageStore` 取 `createNewPage`；`src/features/HotkeyHelperPanel/index.tsx` 通过 `useGlobalStore` 读取弹窗状态并更新系统状态。

store 的 action 下游通常会调用服务层，例如 `src/services`、TRPC service、数据库同步服务或业务 service。虽然本次只抽样了 store 目录，未完整展开所有 service 调用，但根据 `src/store` 的 action 命名和 LobeHub 约定可推断：public action 负责给 UI 调用，internal action 负责具体业务流，`internal_dispatch*` 负责把 reducer 结果写回 Zustand。

store 与类型层也有关系。按照仓库技能说明，store 中业务数据类型应优先来自 `@lobechat/types` 或 `src/types`，不要直接依赖数据库类型，以避免前端状态和数据库 schema 强耦合。

## 运行/调用流程

以 `chat` 为例，`src/store/chat/store.ts` 先定义 `ChatStoreAction`，它由 `ChatMessageAction`、`ChatThreadAction`、`ChatAIChatAction`、`ChatTopicAction`、`ChatPluginAction` 等多个 action 类型交叉组成；再定义 `ChatStore = ChatStoreAction & ChatStoreState`。

随后 `createStore` 返回：

```ts
{
  ...initialState,
  ...flattenActions([
    chatMessage(...params),
    new ChatThreadActionImpl(...params),
    chatAiChat(...params),
    new ChatTopicActionImpl(...params),
    ...
    new ChatStoreResetAction(...params),
  ])
}
```

最后通过：

```ts
createWithEqualityFn<ChatStore>()(
  subscribeWithSelector(devtools(createStore)),
  shallow,
)
```

生成 `useChatStore`。这说明组件层读取 store 时默认使用 `shallow` 比较，并且支持 selector 订阅。`chat`、`user`、`global` 等 store 都采用类似模式；部分 store 如 `page` 没有包 `subscribeWithSelector`，但仍使用 `createWithEqualityFn` 和 `shallow`。

典型调用链是：

组件调用 `useChatStore(selector)` 或 `usePageStore((s) => s.createNewPage)`；selector/action 从 store 中取状态或触发动作；action 内部可能更新本地状态、调用 service、做乐观更新；复杂列表或详情数据通过 reducer / map 结构维护；状态变化后组件按 selector 重新渲染。

## 小白阅读顺序

1. 先看一个简单 store：`src/store/page/store.ts`、`src/store/page/initialState.ts`、`src/store/page/selectors.ts`。它能展示“状态 + slices + hook 暴露”的基本形态。
2. 再看公共工具：`src/store/utils/flattenActions.ts`、`src/store/utils/resetableStore.ts`、`src/store/middleware/createDevtools.ts`、`src/store/middleware/expose.ts`。理解这些后，再读大型 store 会轻松很多。
3. 再看 `src/store/user/store.ts` 和 `src/store/global/store.ts`。它们代表用户设置与全局 UI 状态，是 UI 组件中最常见的依赖。
4. 最后读 `src/store/chat/store.ts` 和 `src/store/chat/initialState.ts`。这是高复杂度样本，聚合了消息、话题、线程、工具、插件、AI Agent 等多个 slice。
5. 阅读调用方时，从 `rg "useChatStore\\(" src/features src/routes` 这类搜索开始，看组件如何只取自己需要的字段或 action。
6. 如果要深入数据结构，再看带 `reducers`、`internal_dispatch`、`messagesMap`、`topic`、`detailMap` 的 slice，理解 map + reducer + optimistic update 的模式。

## 常见误区

不要把 `src/store` 理解成一个单体全局 store。它是多个业务域 store 的集合，`useChatStore`、`useUserStore`、`useGlobalStore`、`usePageStore` 彼此独立，只是在 UI 层可能被同一个组件同时使用。

不要在组件里随意读取整个 store。正确方式是用 selector 读取最小状态，例如 `useGlobalStore(systemStatusSelectors.sidebarItems)` 或 `useChatStore((s) => s.activeTopicId)`，避免无关状态变化导致组件重渲染。

不要用对象展开直接合并 class action。仓库已经用 `flattenActions` 解决 class prototype 方法无法被普通 spread 复制的问题；新增 class-based slice 时应继续使用这个模式。

不要把所有状态都塞进一个 slice。大型域如 `chat` 会拆成 message、topic、thread、plugin、tool 等 slice；`initialState.ts` 再统一聚合。这种拆分是为了降低业务边界复杂度。

不要混淆 list 和 detail 数据结构。根据当前仓库约定，列表适合数组，详情缓存适合 `Record<string, Detail>`，需要乐观更新的复杂实体再配 reducer 和 `internal_dispatch*`。

不要以为 `reset` 只是手写清空字段。这里的 reset 通过 `api.getInitialState()` 回到 store 初始化快照，并带有 devtools action name，便于调试和保持一致性。

不要在 store 中直接依赖数据库层类型。前端 store 面向 UI 和业务缓存，应使用前端类型或 `@lobechat/types`，否则数据库 schema 改动容易把 UI 状态层一起拖动。
