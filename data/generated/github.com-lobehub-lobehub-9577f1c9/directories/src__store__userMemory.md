# 目录：src/store/userMemory

## 它负责什么

`src/store/userMemory` 是前端“用户记忆”模块的 Zustand store。它不直接定义页面 UI，也不直接实现数据库逻辑，而是作为用户记忆功能在客户端的状态中枢：负责把记忆列表、记忆检索结果、编辑态、首页概览数据、聊天上下文注入缓存等状态统一组织起来，并向页面、全局初始化逻辑、聊天服务暴露可复用的 hook 和 action。

从当前代码片段看，这个 store 覆盖的记忆类型主要包括 `activity`、`context`、`experience`、`identity`、`preference`。其中 `activity/context/experience/identity/preference` 更偏向记忆管理页的列表、分页、搜索、排序、删除和更新；`agent` 更偏向聊天时按 topic 注入记忆；`base` 负责跨类型的通用能力，例如设置当前检索上下文、刷新用户记忆、拉取详情、编辑记忆、清空记忆等；`home` 则服务记忆首页的 persona、tags、roles 概览数据。

这个目录的核心外部入口是 `useUserMemoryStore`，页面组件通过它选择状态和调用 action；非 React 场景可以通过 `getUserMemoryStoreState` 读取当前 store 状态。公共 selector 集中在 `selectors.ts`，用于从缓存 map 中按当前参数或指定参数取出记忆结果。

## 直接子目录地图

`src/store/userMemory/slices` 是业务切片目录。每个子目录代表一组相对独立的状态和动作，最后在 `store.ts` 中通过 `flattenActions` 合并成一个 store。

`src/store/userMemory/slices/activity` 管理活动记忆列表。状态包括 `activities`、分页页码、总数、是否初始化、是否还有更多、查询词和排序字段。动作包括拉取列表、加载更多、重置列表、删除活动记忆等。

`src/store/userMemory/slices/context` 管理上下文记忆列表。它与 activity 类似，但数据类型和排序字段面向 context，例如 `scoreImpact`、`scoreUrgency`。

`src/store/userMemory/slices/experience` 管理经验记忆列表。它维护 `experiences` 列表、分页、搜索、排序等状态，排序字段包含 `capturedAt`、`scoreConfidence`。

`src/store/userMemory/slices/identity` 管理身份记忆。除了列表页状态外，它还维护 `globalIdentities`、`globalIdentitiesFetchedAt`、`globalIdentitiesInit`，用于聊天上下文注入时的全局身份数据。它也是少数包含创建、更新、删除完整 CRUD action 的 slice。

`src/store/userMemory/slices/preference` 管理偏好记忆列表。它维护 preferences 列表、分页、搜索、排序和删除逻辑，排序字段包含 `capturedAt`、`scorePriority`。

`src/store/userMemory/slices/agent` 管理 agent/chat 侧的记忆缓存。它的关键状态是 `topicMemoriesMap`，以 `topicId` 为 key 缓存某个会话主题可注入的记忆结果。

`src/store/userMemory/slices/base` 是通用动作层，不对应单一记忆类型。它处理跨层数据刷新、当前记忆检索参数、编辑弹窗状态、详情查询、通用更新、清空全部记忆，以及初始化 identity 注入数据。

`src/store/userMemory/slices/home` 服务用户记忆首页。它拉取 persona、tags、roles，并写入 `persona`、`personaInit`、`tags`、`roles`、`tagsInit` 等顶层状态。

`src/store/userMemory/utils` 是工具目录。`cacheKey.ts` 根据 `RetrieveMemoryParams` 生成缓存 key；`searchParams.ts` 把聊天上下文类输入转换成记忆检索参数；`searchParams.test.ts` 覆盖这个转换工具的基本行为。

## 关键入口

`src/store/userMemory/store.ts` 是 store 组合入口。它定义 `UserMemoryStore` 类型，把 `UserMemoryStoreState`、各 slice action、`ResetableStore` 合并在一起；然后用 `createWithEqualityFn` 创建 `useUserMemoryStore`。这里还挂了 devtools 名称 `userMemory`，并通过 `expose('userMemory', useUserMemoryStore)` 暴露调试入口。

`src/store/userMemory/index.ts` 是对外导出入口，只导出 `selectors` 和 `store`。其他模块通常不直接 import 某个 slice，而是从 `@/store/userMemory` 取 `useUserMemoryStore` 或 selector。

`src/store/userMemory/initialState.ts` 是总状态入口。它把各 slice 的 initialState 合并，并补充跨切片共享状态，例如 `activeParams`、`activeParamsKey`、`memoryMap`、`memoryFetchedAtMap`、`editingMemoryId`、`editingMemoryContent`、`editingMemoryLayer`、`persona`、`roles`、`tags` 等。

`src/store/userMemory/selectors.ts` 是读取缓存的入口。`userMemorySelectors.activeMemories`、`activeUserMemories`、`memoriesByParams`、`memoryFetchedAtByParams` 都围绕 `memoryMap` 和 `memoryFetchedAtMap` 工作。它还转导出 `agentMemorySelectors` 和 `identitySelectors`，方便调用方从同一个 selector 模块取数据。

`src/store/userMemory/types.ts` 当前只定义 `IdentityForInjection`，表示注入聊天上下文所需的 identity 子集。根据当前片段推断，这里没有放完整业务模型，因为完整类型多来自 `@lobechat/types` 或数据库 repository 类型。

## 主流程位置

记忆管理页的主流程在各列表 slice 中：页面调用 `useFetchActivities`、`useFetchContexts`、`useFetchExperiences`、`useFetchIdentities`、`useFetchPreferences` 之类 hook 拉取数据；成功后 slice 写入对应列表、分页、总数和初始化标记；滚动加载更多时调用对应 `loadMore*`；搜索或排序变化时调用 `reset*List` 重置页码和查询条件。

跨类型编辑流程集中在 `slices/base/action.ts`。列表项菜单会调用 `setEditingMemory` 写入当前编辑的 id、内容和 layer；编辑弹窗读取 `editingMemoryId`、`editingMemoryContent`、`editingMemoryLayer`；保存时调用 `updateMemory`，内部根据 layer 分发到 `memoryCRUDService.updateActivity`、`updateContext`、`updateExperience`、`updateIdentity` 或 `updatePreference`，然后重置对应列表以刷新数据。

聊天记忆注入流程分两条。第一条是 topic 级缓存：`slices/agent/action.ts` 的 `useFetchMemoriesForTopic` 调用 `userMemoryService.retrieveMemoryForTopic`，成功后写入 `topicMemoriesMap`。外部使用点包括 `src/hooks/useFetchMemoryForTopic.ts` 和 `src/services/chat/mecha/memoryManager.ts`。第二条是主动上下文检索：聊天生命周期代码会调用 `setActiveMemoryContext`，`base` 通过 `createMemorySearchParams` 生成 `RetrieveMemoryParams` 和缓存 key，随后 `useFetchUserMemory` 按参数拉取并写入 `memoryMap`、`memoryFetchedAtMap`。

全局初始化流程也经过这个 store。`src/layout/GlobalProvider/DeferredStoreInitialization.tsx` 使用 `useFetchPersona` 初始化 persona；`base` 中的 `useInitIdentities` 在登录态下拉取全局 identities，供上下文注入使用。

## 推荐阅读顺序

1. 先看 `src/store/userMemory/store.ts`，理解这个目录如何用 `flattenActions` 把多个 slice 合并成 `useUserMemoryStore`。
2. 再看 `src/store/userMemory/initialState.ts`，把顶层状态字段和各 slice 状态边界建立起来。
3. 阅读 `src/store/userMemory/selectors.ts`，理解 `activeParamsKey`、`memoryMap`、`memoryFetchedAtMap` 的缓存读取方式。
4. 阅读 `src/store/userMemory/slices/base/action.ts`，这是跨类型主流程最多的地方，包括检索、详情、编辑、刷新和清空。
5. 选择一个列表 slice 横向理解即可，例如 `slices/activity/action.ts`；再对照 `context`、`experience`、`preference`，它们结构相似。
6. 最后看 `slices/agent/action.ts` 和 `slices/identity/action.ts`，理解聊天上下文注入为什么需要 topic memories 和 global identities。

## 常见误区

不要把这个目录理解成后端记忆系统。它只是前端 store，真正的数据读取和写入由 `userMemoryService`、`memoryCRUDService` 以及更下层的服务、数据库 repository 完成。

不要认为每个 slice 都完全独立。列表数据由各 slice 管理，但编辑、详情、全量刷新、删除后的缓存失效等跨类型行为集中在 `base`，页面上看到的一个操作可能会同时影响 SWR 缓存、列表状态和顶层编辑状态。

不要把 `memoryMap` 和各类型列表混为一谈。`activities`、`contexts` 等是管理页列表；`memoryMap` 是按 `RetrieveMemoryParams` 缓存的检索结果，主要服务当前上下文的用户记忆检索。

不要绕过 `useUserMemoryStore` 直接引用 slice。项目现有用法是从 `@/store/userMemory` 读取统一 store 和 selector，slice 目录更像内部组织方式。

不要忽略 `agent` 与 `identity` 的注入场景。`identity` 不只是记忆管理页列表，它还维护 `globalIdentities`；`agent` 也不服务页面列表，而是服务聊天 topic 的记忆缓存。
