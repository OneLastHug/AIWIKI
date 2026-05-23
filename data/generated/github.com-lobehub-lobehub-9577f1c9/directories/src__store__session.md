# 目录：src/store/session

## 它负责什么

`src/store/session` 是会话列表层的 Zustand store，负责维护“会话导航侧边栏”相关的前端状态和动作。这里的 session 不是单条聊天消息本身，而是更偏上层的会话入口：普通 agent 会话、group 类型会话、置顶会话、自定义分组、当前选中会话、搜索状态、抽屉和面板固定状态等。

从 `store.ts` 可以看到，这个目录把两个核心 slice 聚合成一个 `SessionStore`：`session` slice 处理会话列表、当前会话、搜索、创建/复制/删除/置顶/切换等行为；`sessionGroup` slice 处理会话分组的增删改、排序和本地派发。最终通过 `useSessionStore` 给 UI 使用，并通过 `getSessionStoreState` 提供非 React 场景的直接读取。

它的定位可以概括为：把后端 `sessionService` 返回的会话与分组数据，整理成适合侧边栏展示和交互的数据结构，例如 `sessions`、`defaultSessions`、`pinnedSessions`、`sessionGroups`、`customSessionGroups`。其中 `internal_processSessions` 是重要的数据归并点，会把原始会话列表拆成默认分组、置顶分组和自定义分组 children。

## 直接子目录地图

`src/store/session` 的直接结构比较集中：

`src/store/session/store.ts` 是 store 聚合入口，创建 `useSessionStore`，组合 `initialState`、`createSessionSlice`、`createSessionGroupSlice` 和 reset action。

`src/store/session/index.ts` 是对外导出入口，只暴露 `SessionStore` 类型、`useSessionStore` 和 `getSessionStoreState`。

`src/store/session/initialState.ts` 是总初始状态组合层，把 `slices/session/initialState.ts` 和 `slices/sessionGroup/initialState.ts` 合并成 `SessionStoreState`。

`src/store/session/selectors.ts` 是 selector 汇总出口，转发 session、session meta 和 sessionGroup 的 selector。

`src/store/session/helpers.ts` 是 helper 汇总出口，继续导出 `slices/session/helpers` 中的工具方法。

`src/store/session/slices/session` 是会话主体 slice，包含会话状态、动作、reducer、helper、selector 和对应测试。它关心会话列表、当前激活会话、搜索、置顶、复制、删除、创建、刷新后的分组加工等。

`src/store/session/slices/sessionGroup` 是分组 slice，包含分组状态、动作、reducer、selector 和测试。它关心自定义会话分组的创建、删除、重命名、排序，以及排序时的本地乐观更新。

`src/store/session/slices/session/selectors` 是 session selector 的细分目录，目前按 `list.ts`、`meta.ts` 拆开，再由 `index.ts` 汇总。

## 关键入口

最关键入口是 `src/store/session/store.ts`。这里定义 `SessionStore`：

`SessionStore` 同时继承 `SessionAction`、`SessionGroupAction`、`ResetableStore` 和 `SessionStoreState`。也就是说，组件拿到的 `useSessionStore` 同时包含状态字段和动作方法。

`createStore` 是聚合函数，先展开 `initialState`，再用 `flattenActions` 合并 `createSessionSlice(...)`、`createSessionGroupSlice(...)`、`new SessionStoreResetAction(...)`。这符合仓库内 Zustand class-based action 的迁移风格：slice action 由 class 实现，聚合时不能直接 spread class instance，而是用 `flattenActions` 绑定方法。

对外使用入口是 `src/store/session/index.ts`。一般业务代码不应从深层 slice 直接拿 store，而应优先使用：

`useSessionStore`：React 组件中订阅状态或 action。

`getSessionStoreState`：非 React 流程中读取当前 store，例如服务回调、跨 store 协作等。

selector 入口是 `src/store/session/selectors.ts`。它导出 `sessionSelectors`、`sessionMetaSelectors`、`sessionGroupSelectors`。UI 层若只是读取派生数据，应优先通过这些 selector，而不是在组件中重复过滤 `sessions`。

## 主流程位置

会话列表加载主流程位于 `src/store/session/slices/session/action.ts` 的 `useFetchSessions`。它使用 `useClientDataSWR`，以 `sessionService.getGroupedSessions()` 获取数据。成功后会判断是否已经首轮加载且数据未变化；如果需要更新，则调用 `internal_processSessions(data.sessions, data.sessionGroups)`。

`internal_processSessions` 是会话数据进入本地 store 后的核心整理流程。它会把 `sessionGroups` 映射成 `customSessionGroups`，并为每个自定义分组补上 `children`；同时把没有分组或属于 `default` 的会话整理为 `defaultSessions`，把 `pinned` 会话整理为 `pinnedSessions`，最后一起写入 `sessions`、`sessionGroups` 等字段。

会话更新主流程位于 `internal_updateSession`。它先通过 `internal_dispatchSessions` 调用 `sessionsReducer` 做本地状态更新，然后调用 `sessionService.updateSession(id, data)` 持久化，最后 `refreshSessions()` 重新拉取以保证一致性。这个流程体现了本目录的常见模式：先更新本地交互状态，再通过 service 与后端同步，最后 refresh 统一收敛。

会话删除流程在 `removeSession`。它调用 `sessionService.removeSession(sessionId)` 后刷新列表，如果删除的是当前激活会话，会切回 `INBOX_SESSION_ID`。

会话分组排序主流程在 `src/store/session/slices/sessionGroup/action.ts` 的 `updateSessionGroupSort`。它先把传入分组列表转成 `{ id, sort }` 的 `sortMap`，再用 `internal_dispatchSessionGroups` 进行本地排序更新，随后调用 `sessionService.updateSessionGroupOrder(sortMap)`，完成后刷新会话列表。

跨 store 同步位置也在 `useFetchSessions`。当拉到的 session 中存在 `type === 'group'` 的 group session 时，会根据这些 session 构造 chat group 数据，并调用 `getChatGroupStoreState().internal_updateGroupMaps(chatGroups)`。根据当前片段推断，这是为了让会话侧边栏中的 group session 与 `agentGroup` store 保持基本信息同步，依据是该逻辑明确把 session 字段映射成 chat group item 字段。

## 推荐阅读顺序

建议先读 `src/store/session/store.ts`，确认这个目录如何创建 `useSessionStore`、如何组合两个 slice、如何接入 devtools 和 reset。

第二步读 `src/store/session/initialState.ts`，再分别看 `src/store/session/slices/session/initialState.ts` 与 `src/store/session/slices/sessionGroup/initialState.ts`。这样能先建立状态字段地图：哪些字段属于会话，哪些字段属于分组。

第三步读 `src/store/session/slices/session/action.ts`。重点看 `useFetchSessions`、`internal_processSessions`、`internal_updateSession`、`switchSession`、`removeSession`、`updateSessionGroupId`。这些方法基本覆盖会话列表从加载、整理、更新、删除到切换的主路径。

第四步读 `src/store/session/slices/sessionGroup/action.ts`。重点看 `addSessionGroup`、`removeSessionGroup`、`updateSessionGroupName`、`updateSessionGroupSort` 和 `internal_dispatchSessionGroups`，理解分组动作如何委托给 `sessionService` 并回流到 session store。

第五步读 selector：`src/store/session/selectors.ts`、`src/store/session/slices/session/selectors/list.ts`、`src/store/session/slices/session/selectors/meta.ts`、`src/store/session/slices/sessionGroup/selectors.ts`。selector 能帮助理解 UI 实际消费哪些派生数据。

最后再看 reducer 和测试：`src/store/session/slices/session/reducers.ts`、`src/store/session/slices/sessionGroup/reducer.ts` 以及相邻的 `.test.ts`。它们不是入口，但能验证本地状态变更的边界。

## 常见误区

第一个误区是把 `activeId` 和 `activeAgentId` 混为一谈。`initialState` 中 `activeId` 默认是 `inbox`，而 `switchSession` 实际更新的是 `activeAgentId`。从当前片段看，selector 的 `currentSession` 读取的是 `activeId`，因此这两个字段可能服务于不同历史阶段或不同 UI 语义。阅读调用方时需要确认具体消费的是哪个字段，不能只看名字判断。

第二个误区是认为 `sessions` 就是最终展示列表。实际上展示侧边栏时通常还会使用 `defaultSessions`、`pinnedSessions`、`customSessionGroups`。这些字段不是后端直接返回，而是 `internal_processSessions` 根据 `sessions` 和 `sessionGroups` 重新整理出来的派生结构。

第三个误区是绕过 action 直接改 store 字段。这个目录明显采用 public action、internal action、dispatch/reducer 的分层习惯。比如更新会话应走 `internal_updateSession` 或对应 public action，因为它同时处理本地更新、service 调用和刷新收敛。直接 `set({ sessions })` 容易漏掉 `defaultSessions`、`pinnedSessions`、`customSessionGroups` 的同步。

第四个误区是把 group session 和 session group 当成同一概念。`type === 'group'` 的 session 是一种会话类型，会在 `useFetchSessions` 中同步到 chat group store；而 `sessionGroups`、`customSessionGroups` 是侧边栏分组结构，用于组织 session。二者名字接近，但职责不同。

第五个误区是只改 `sessionGroup` slice 而忘记 session 列表刷新。分组创建、删除、重命名、排序后都会调用 `refreshSessions()`，说明后端返回的 grouped sessions 是最终权威来源。本地 reducer 更多用于交互即时反馈，最终仍要靠刷新后的数据统一。
