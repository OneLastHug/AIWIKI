# 文件：src/store/session/store.ts

## 一句话定位

`src/store/session/store.ts` 是会话域的 Zustand store 聚合入口：它不承载具体会话业务细节，而是把 session、sessionGroup 两组状态与动作、reset 能力、devtools、订阅能力和默认浅比较策略组装成全局可用的 `useSessionStore`。

## 它暴露/定义了什么

这个文件定义了 `SessionStore` 接口，它继承 `SessionStoreState`、`SessionAction`、`SessionGroupAction` 和 `ResetableStore`，因此最终 store 同时包含会话列表状态、分组状态、会话操作、分组操作和 `reset()`。

它导出两个核心入口：`useSessionStore` 和 `getSessionStoreState`。前者是 React 组件和 hooks 使用的 Zustand hook，后者是非 React 场景下读取当前 store 快照的便捷函数。文件末尾还通过 `expose('session', useSessionStore)` 在开发环境把 session store 暴露到调试入口，便于排查状态。

内部的 `createStore` 是真正的 store 初始化函数：先展开 `initialState`，再用 `flattenActions` 聚合 `createSessionSlice`、`createSessionGroupSlice` 和 `SessionStoreResetAction`。`SessionStoreResetAction` 继承通用 `ResetableStoreAction`，只指定 reset action 名称为 `resetSessionStore`。

## 谁调用它

最主要的调用方是界面层和功能组件。桌面侧如 `src/features/NavPanel/components/SessionHydration.tsx`、`src/features/Conversation/*`、`src/features/ChatInput/*` 会读取当前会话、当前群组成员、会话列表或触发会话切换。移动侧如 `src/routes/(mobile)/(home)/_layout/SessionHydration.tsx`、`SessionSearchBar.tsx`、`SessionListContent/*` 使用它完成列表展示、搜索、创建会话、分组管理等。

还有一些跨 store 或系统级调用。`src/store/utils/userDataStores.ts` 把 `useSessionStore` 纳入全局可 reset 的用户数据 store 集合；`src/store/electron/actions/sync.ts` 在刷新用户数据时动态导入 session store 并调用 `refreshSessions()`；测试文件也直接使用 `useSessionStore.setState()` 或 `useSessionStore.getState()` 来构造状态和断言动作。

## 它调用谁

`store.ts` 本身调用的是基础设施和相邻 slice。Zustand 相关包括 `createWithEqualityFn`、`subscribeWithSelector`、`shallow`、`StateCreator`。项目内基础设施包括 `createDevtools`、`expose`、`flattenActions`、`ResetableStoreAction`。

业务能力来自 `src/store/session/slices/session/action.ts` 的 `createSessionSlice` 和 `src/store/session/slices/sessionGroup/action.ts` 的 `createSessionGroupSlice`。初始状态来自 `src/store/session/initialState.ts`，后者继续合并 `initialSessionState` 和 `initSessionGroupState`。实际服务调用并不发生在 `store.ts`，而是在 slice action 中调用 `sessionService`、`chatGroupService`、SWR `mutate/useSWR/useClientDataSWR`，以及少量跨 store 的 `getChatGroupStoreState`、`useUserStore` 等。

## 核心流程

初始化流程是：`initialState` 提供默认会话状态，例如 `activeId: 'inbox'`、空 `sessions`、空 `sessionGroups`、搜索和 loading 标记；`createStore` 把这些状态和所有 action 聚合成完整对象；`createWithEqualityFn` 创建 hook，并用 `shallow` 作为默认 equality function，降低组件选择多个字段时的无效渲染概率。

中间件流程是：`createStore` 先被 `devtools(createStore, { name: ... })` 包装，再被 `subscribeWithSelector` 包装。`subscribeWithSelector` 让调用方可以订阅局部 selector，例如 hydration 组件订阅 `activeId`，当会话变化时同步 URL query 并重置 topic。`createDevtools('session')` 根据 URL debug 参数决定是否启用 Zustand devtools，并在 dev 环境追加 `_DEV` 标记。

运行时更新流程通常不在 `store.ts` 里展开，而是经由 slice action。比如 `useFetchSessions` 拉取 `sessionService.getGroupedSessions()` 后调用 `internal_processSessions`，把原始 `sessions` 和 `sessionGroups` 派生为 `defaultSessions`、`pinnedSessions`、`customSessionGroups`；`internal_updateSession` 先通过 reducer 做本地更新，再调用后端服务并刷新列表；分组排序则先本地重排，再调用 `sessionService.updateSessionGroupOrder()`，最后刷新会话。

## 关键函数的高层作用

`createStore` 是本文件最关键的函数。它决定 session store 的组成边界：状态只从 `initialState` 来，动作只从两个 slice 和 reset action 来。新增会话域能力时，通常应先放进对应 slice，再在这里由 `flattenActions` 汇总，而不是把业务逻辑直接塞进 `store.ts`。

`useSessionStore` 是外部消费的主入口。它既是 React hook，也保留 Zustand store API，例如 `.getState()`、`.setState()`、`.subscribe()`。由于它使用 `createWithEqualityFn` 并默认 `shallow`，调用方常见写法是 `useSessionStore((s) => [s.createSession, s.refreshSessions])`。

`getSessionStoreState` 是非组件代码读取当前状态的短路径，本质上等价于 `useSessionStore.getState()`。它适合事件处理、路由 meta、列表虚拟化回调这类不能或不方便直接使用 hook 的场景，但也意味着调用者拿到的是即时快照，不会自动触发 React 更新。

`SessionStoreResetAction` 只是 reset 适配器。它复用通用 `ResetableStoreAction`，让全局 `stores.reset()` 可以把 session store 恢复到 `api.getInitialState()`，常见于退出、断开同步或刷新用户数据场景。

## 修改风险

最大风险是把 `store.ts` 从“组合层”改成“业务层”。会话创建、搜索、刷新、分组排序、乐观更新等逻辑已经在 `slices/session/action.ts` 和 `slices/sessionGroup/action.ts` 中分层；如果在这里直接写业务逻辑，会破坏 action 分层，也会让测试和 reset 行为变得不清晰。

第二个风险是中间件顺序和 equality 策略。`subscribeWithSelector` 支撑 hydration 对 `activeId` 的细粒度订阅；`shallow` 影响大量数组 selector 写法的渲染行为。随意移除或替换可能导致 URL 与 store 不同步、组件重复渲染，或订阅回调行为变化。

第三个风险是 action 聚合方式。当前使用 `flattenActions` 是为了兼容 class-based action，能正确绑定类字段和原型方法。把它改成对象 spread 可能丢失 class instance 方法或绑定关系，尤其是 `#get/#set` 私有字段依赖 `this` 的 action。

第四个风险是 reset 语义。`reset()` 会回到 store 创建时的初始状态，而不是重新从服务端拉取数据；调用方通常会在 reset 后再触发 `refreshSessions()` 或其他刷新。修改 `initialState`、`SessionStore` 继承关系或 `SessionStoreResetAction` 时，需要同时考虑 `src/store/utils/userDataStores.ts` 的全局 reset 场景。

最后，`SessionStore` 类型是多个 slice 的交汇点。新增同名字段或 action 很容易发生覆盖，因为最终对象是扁平合并；应避免 session slice、sessionGroup slice 和 reset action 暴露重复 key，并确保 selector、测试、hydration 组件对字段命名的假设仍然成立。
