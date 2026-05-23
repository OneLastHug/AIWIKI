# 目录：src/store/agentGroup

## 它负责什么

`src/store/agentGroup` 是 LobeHub 中“Agent 群组 / Group Chat”相关的 Zustand store。它维护群组列表、当前激活群组、群组详情缓存、群组成员、群组配置、群组设置面板开关，以及系统提示词流式生成时的临时状态。

从命名上看，目录名是 `agentGroup`，但内部类型和 action 大量使用 `ChatGroup` 前缀，例如 `ChatGroupStore`、`ChatGroupState`、`ChatGroupCurdAction`。这说明它承载的是“由多个 agent 组成的聊天群组”状态，而不是普通单 agent 配置。它既服务于 `src/routes/(main)/group` 这类群组聊天页面，也被首页、移动端会话列表、社区 group agent 引入流程、聊天上下文工程等模块读取。

这个 store 的核心职责可以概括为三层：

第一层是本地状态容器：保存 `activeGroupId`、`activeThreadAgentId`、`groupMap`、`groups`、`groupsInit`、`router`、`showGroupSetting`、`streamingSystemPrompt` 等字段。

第二层是群组业务动作：创建群组、切换群组话题、更新群组基础信息和配置、添加/删除/排序成员、刷新群组详情等。

第三层是跨 store 同步：在拉取群组详情后，会把群组内 agent 同步到 `agentStore`，并把 supervisor agent 同步到 `agentStore` 和 `chatStore`，用于后续模型解析、工具注入和消息发送。

## 直接子目录地图

这个目录只有两个直接子目录，整体不算大。

`src/store/agentGroup/selectors` 负责派生读取逻辑。它把 state 中的 `groupMap`、`activeGroupId` 等基础数据转换为 UI 和服务层需要的视图，例如当前群组、当前群组配置、当前群组成员、按 ID 获取群组、按 supervisor agent ID 查找群组、成员数量等。

`src/store/agentGroup/slices` 负责动作分组。这里不是按页面拆分，而是按业务行为拆分为 `lifecycle`、`curd`、`member` 三类：生命周期和导航、群组信息更新、群组成员管理。

根目录文件承担 store 的装配和共享类型：`store.ts` 创建 Zustand store，`initialState.ts` 定义状态结构，`action.ts` 组合 action，`reducers.ts` 提供 reducer 式状态更新，`index.ts` 作为统一导出入口，`helpers.ts` 提供开发调试相关封装。测试文件分布在 `selectors` 和 `slices` 下，覆盖 selector 与关键 action 行为。

## 关键入口

最上层入口是 `src/store/agentGroup/index.ts`。业务代码通常从这里导入 `useAgentGroupStore`、`getChatGroupStoreState`、`agentGroupSelectors` 或相关类型，而不是直接依赖内部文件。

真正创建 store 的位置是 `src/store/agentGroup/store.ts`。这里定义 `ChatGroupStore = ChatGroupState & ChatGroupAction`，使用 `createWithEqualityFn` 创建 store，并接入 `createDevtools('agentGroup')`。同时通过 `expose('agentGroup', useAgentGroupStore)` 暴露调试入口。`getChatGroupStoreState` 是非 React 场景读取当前 store 状态的入口，服务层和其他 store 中会用它读取群组状态。

状态定义入口是 `src/store/agentGroup/initialState.ts`。这里能看到这个 store 的数据边界：它不只保存列表，也保存详情 map、当前路由绑定、设置 UI 状态，以及 GroupAgentBuilder 相关的流式 system prompt 状态。

动作组合入口是 `src/store/agentGroup/action.ts`。它定义内部 action `ChatGroupInternalAction`，并通过 `flattenActions` 把内部 action、`ChatGroupLifecycleAction`、`ChatGroupMemberAction`、`ChatGroupCurdAction` 合并成最终的 `ChatGroupAction`。

selector 汇总入口是 `src/store/agentGroup/selectors/index.ts`，对外统一暴露 `agentGroupSelectors` 和 `agentGroupByIdSelectors`。

## 主流程位置

群组列表加载主流程在 `src/store/agentGroup/action.ts` 的 `loadGroups` 和 `internal_updateGroupMaps` 附近。`loadGroups` 通过 `chatGroupService.getGroups()` 获取数据，再通过 `internal_dispatchChatGroup({ type: 'loadGroups' })` 更新 `groups` 和 `groupMap`。`internal_updateGroupMaps` 用于把外部传入的群组列表合并进 `groupMap`，并尽量保留已有详情中的 `agents` 和 `config`。

群组详情加载主流程也在 `action.ts`，重点是 `internal_fetchGroupDetail` 和 `useFetchGroupDetail`。它们调用 `chatGroupService.getGroupDetail(groupId)`，把完整详情写入 `groupMap`，然后同步群组内 agent 到 `agentStore`。如果详情包含 `supervisorAgentId`，还会设置 `agentStore.activeAgentId`，并同步 `chatStore.activeAgentId`。这一步是理解群组聊天为何能复用普通 agent 发送链路的关键。

创建群组主流程在 `src/store/agentGroup/slices/lifecycle.ts` 的 `createGroup`。它调用 `chatGroupService.createGroup` 创建群组；如果传入成员，则调用 `addAgentsToGroup`；随后本地 dispatch `addGroup`，再拉取完整详情，刷新首页 agent 列表，最后根据 `silent` 决定是否切换到新群组。

话题切换主流程在同一个文件的 `switchTopic`。它读取 `activeGroupId` 和 `router`，先调用 `useChatStore.getState().switchTopic` 更新聊天 store 的 active topic，再用 router 跳到 `/group/{activeGroupId}` 并写入 `topic` query。`router` 本身由 `src/routes/(main)/group/_layout/GroupIdSync.tsx` 注入到 store。

群组配置和元信息更新主流程在 `src/store/agentGroup/slices/curd.ts`。`updateGroup` 更新通用字段；`updateGroupConfig` 合并 `DEFAULT_CHAT_GROUP_CHAT_CONFIG`、当前配置和新增配置后写数据库，并立即更新本地 `groupMap`；`updateGroupMeta` 用于头像、标题、描述等元信息更新。`startStreamingSystemPrompt`、`appendStreamingSystemPrompt`、`finishStreamingSystemPrompt` 则围绕 system prompt 流式内容保存。

成员管理主流程在 `src/store/agentGroup/slices/member.ts`。`addAgentsToGroup`、`removeAgentFromGroup`、`reorderGroupMembers` 都通过 `chatGroupService` 持久化，之后调用 `refreshGroupDetail` 重新同步详情。`updateMemberAgentConfig` 则通过 `agentStore.updateAgentConfigById` 更新成员 agent 配置，再刷新群组详情。

## 推荐阅读顺序

建议先读 `src/store/agentGroup/initialState.ts`，建立这个 store 保存哪些状态的整体印象。重点看 `groupMap`、`groups`、`activeGroupId`、`activeThreadAgentId` 和 `router`。

第二步读 `src/store/agentGroup/store.ts` 和 `src/store/agentGroup/index.ts`，理解外部如何拿到 `useAgentGroupStore`，以及 action 与 state 如何组合成 `ChatGroupStore`。

第三步读 `src/store/agentGroup/action.ts`。这里是最重要的文件，包含内部 reducer 分发、群组详情拉取、SWR 同步、跨 `agentStore` / `chatStore` 的 active agent 同步。

第四步读 `src/store/agentGroup/slices/lifecycle.ts`、`src/store/agentGroup/slices/curd.ts`、`src/store/agentGroup/slices/member.ts`。按“创建/切换”“更新配置”“管理成员”的顺序读，会更贴近用户操作链路。

第五步读 `src/store/agentGroup/selectors/current.ts` 和 `src/store/agentGroup/selectors/byId.ts`。这能帮助理解 UI 为什么通常不直接读 `groupMap`，而是通过 `agentGroupSelectors.currentGroupConfig`、`getGroupMembers`、`currentGroupMeta` 这类派生 selector 获取数据。

最后结合调用方看主流程落点：`src/routes/(main)/group/_layout/GroupIdSync.tsx` 负责把路由参数同步到 store；`src/routes/(main)/group/profile` 和 `src/routes/(main)/group/_layout/Sidebar` 下的组件大量使用 selector 和 action；`src/services/chat/mecha/contextEngineering.ts`、`src/services/chat/mecha/agentConfigResolver.ts` 会读取群组详情参与聊天上下文和 agent 配置解析。

## 常见误区

不要把 `groups` 和 `groupMap` 理解成重复数据的简单缓存。`groups` 更像列表数据，`groupMap` 承载按 ID 访问和详情合并；群组详情中的 `agents`、`config` 可能只在详情加载后才完整。

不要只看 `src/store/agentGroup/slices/member.ts` 就以为成员变更会立即手动拼接本地成员数组。当前模式是先通过 `chatGroupService` 持久化，再 `refreshGroupDetail` 拉取完整详情同步，避免本地成员结构与服务端关系表不一致。

不要忽略 supervisor agent 同步。群组详情加载后会把 `supervisorAgentId` 同步到 `agentStore` 和 `chatStore`，这关系到 sendMessage 时模型、工具和配置的解析。群组聊天并不是完全独立于普通 agent 聊天链路运行。

不要误以为 `switchTopic` 只改 agentGroup store。它实际会操作 `chatStore` 的 topic，并通过注入的 `router` 更新群组路由 query。

不要被 `isGroupsInit` 的命名误导。根据当前片段推断，它的返回逻辑是“当前 active group 是否还没有出现在 `groupMap` 中”，更接近当前群组加载态判断；而 `isGroupsInitialized` 才直接对应 `groupsInit` 初始化标记。依据是 `selectors/current.ts` 中 `isGroupsInit = !s.activeGroupId || !s.groupMap[s.activeGroupId]`，`isGroupsInitialized = s.groupsInit`。
