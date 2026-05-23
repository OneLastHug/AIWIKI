# 目录：src/services/session

## 它负责什么

`src/services/session` 是客户端侧的旧版会话服务目录，位于 LobeHub 的 Client Services 层。它的职责不是直接操作数据库，也不是承载 UI 状态，而是把前端 Store、页面组件里对“会话 / 助手会话 / 会话分组”的操作，统一转发到 TRPC lambda 客户端：`lambdaClient.session` 与 `lambdaClient.sessionGroup`。

这个目录当前只有一个实际入口：`src/services/session/index.ts`。其中定义了 `SessionService` 类，并导出单例 `sessionService`。代码注释明确标记：`Session service is legacy. Use agentService for agent CRUD operations.` 也就是说，它主要承担历史兼容职责。新的 Agent CRUD 逻辑应优先看 `agentService`，但移动端和部分旧的 session 入口仍在使用这里。

从功能面看，它覆盖两组能力：

第一组是 session 本体操作，包括创建、复制、查询、统计、搜索、更新、删除会话，例如 `createSession`、`cloneSession`、`getGroupedSessions`、`countSessions`、`rankSessions`、`updateSession`、`searchSessions`、`removeSession`、`removeAllSessions`。

第二组是 session group 操作，包括创建、删除、重命名、排序会话分组，例如 `createSessionGroup`、`removeSessionGroup`、`removeSessionGroups`、`updateSessionGroup`、`updateSessionGroupOrder`。

它更像一个“前端服务适配器”：把前端使用的 `LobeAgentSession`、`UpdateSessionParams`、`SessionGroupItem` 等类型，转换成后端 TRPC router 接受的输入格式。

## 直接子目录地图

`src/services/session` 当前没有直接子目录。目录结构非常扁平：

`src/services/session/index.ts` 是核心服务入口，包含 `SessionService` 类和 `sessionService` 单例。

`src/services/session/index.test.ts` 是对应测试文件，用于验证服务层调用或数据转换行为。

因此，这不是一个大目录，也没有按能力拆分为 `crud`、`group`、`query` 等子模块。读这个目录时，不需要从树结构入手，而应该把它放进整体链路中理解：UI / Store 调用 `sessionService`，`sessionService` 调用 `lambdaClient`，后端 lambda router 再调用数据库 model。

## 关键入口

最关键的入口是 `src/services/session/index.ts` 里的 `sessionService`：

`export const sessionService = new SessionService();`

外部调用通常不会直接实例化 `SessionService`，而是导入这个单例。主要调用方集中在以下几类路径：

`src/store/session/slices/session/action.ts` 使用它处理会话列表拉取、创建、复制、删除、搜索、更新、刷新等主流程。

`src/store/session/slices/sessionGroup/action.ts` 使用它处理会话分组的创建、删除、重命名和排序。

`src/store/home/slices/sidebarUI/action.ts` 也会调用分组相关方法，说明旧的首页侧边栏 UI 仍与 session group 服务有耦合。

`src/routes/(main)/settings/stats/features/overview/TotalAssistants.tsx`、`src/routes/(main)/settings/stats/features/rankings/AssistantsRank.tsx`、`src/features/User/DataStatistics.tsx` 使用 `countSessions`、`rankSessions` 等统计查询能力。

从后端入口看，`SessionService` 调用的是 `lambdaClient.session.*` 与 `lambdaClient.sessionGroup.*`。对应服务端 router 主要在 `src/server/routers/lambda/session.ts` 和 `src/server/routers/lambda/sessionGroup.ts`。这些 router 再通过 `SessionModel`、`SessionGroupModel`、部分场景的 `ChatGroupModel` 访问数据库层。根据当前片段推断，最终数据库模型位于 `packages/database/src/models/session.ts` 和相关 session group model 中，依据是 lambda router 中导入并实例化了 `SessionModel`、`SessionGroupModel`。

## 主流程位置

会话列表拉取主流程大致是：

前端 Store 在 `src/store/session/slices/session/action.ts` 中通过 `useFetchSessions` 发起 SWR 请求，调用 `sessionService.getGroupedSessions()`。服务层转发到 `lambdaClient.session.getGroupedSessions.query()`。服务端 `src/server/routers/lambda/session.ts` 中的 `getGroupedSessions` 会读取普通 sessions 和 chat groups，并合并排序，返回 `{ sessionGroups, sessions }`。Store 收到数据后调用 `internal_processSessions`，拆分出 `customSessionGroups`、`defaultSessions`、`pinnedSessions` 等前端展示结构。

创建会话主流程大致是：

`SessionActionImpl.createSession` 先合并 `DEFAULT_AGENT_LOBE_SESSION` 和用户默认设置，形成 `LobeAgentSession`。随后调用 `sessionService.createSession(LobeSessionType.Agent, newSession)`。服务层会把前端的 `group` 映射为后端 session 的 `groupId`，并把 `config` 与 `meta` 合并后传给 `lambdaClient.session.createSession.mutate()`。后端 `sessionRouter.createSession` 再调用 `ctx.sessionModel.create(input)`。但这里要特别注意：该入口已标记 deprecated，新 Agent 创建应迁移到 `agentService.createAgent` 或对应 agent router。

更新会话主流程大致是：

Store 中的 `internal_updateSession` 会先用 reducer 乐观更新本地列表，再调用 `sessionService.updateSession(id, data)`，最后 `refreshSessions()` 触发 SWR 刷新。服务层会把 `group: 'default'` 转成 `groupId: null`，并把 `meta` 拆开合并到后端更新对象中，调用 `lambdaClient.session.updateSession.mutate()`。

分组排序主流程大致是：

`SessionGroupActionImpl.updateSessionGroupSort` 接收分组数组，生成 `{ id, sort }[]`，先通过 `internal_dispatchSessionGroups` 更新本地顺序，再调用 `sessionService.updateSessionGroupOrder(sortMap)`。服务层转发到 `lambdaClient.sessionGroup.updateSessionGroupOrder.mutate()`，后端由 `sessionGroupRouter.updateSessionGroupOrder` 调用 `SessionGroupModel.updateOrder`。

## 推荐阅读顺序

1. 先读 `src/services/session/index.ts`，把 `SessionService` 的方法按 session 操作和 session group 操作分成两块理解。重点看每个方法转发到哪个 `lambdaClient` router，以及前端字段如何转换成后端字段，例如 `group` 到 `groupId`、`meta` 到 config/update value。

2. 再读 `src/store/session/slices/session/action.ts`，理解服务在前端状态流中的位置。重点看 `useFetchSessions`、`createSession`、`duplicateSession`、`removeSession`、`internal_updateSession`、`internal_processSessions`。

3. 接着读 `src/store/session/slices/sessionGroup/action.ts`，理解分组增删改和排序如何通过 `sessionService` 进入后端。

4. 然后读 `src/server/routers/lambda/session.ts` 和 `src/server/routers/lambda/sessionGroup.ts`，确认每个客户端方法对应的后端 procedure。这里可以看到鉴权、数据库上下文注入、Zod input schema 和 model 调用。

5. 最后根据需要下钻到数据库模型，例如 `packages/database/src/models/session.ts`。overview 阶段不建议一开始就深入 DB model，否则容易把服务层职责和持久化细节混在一起。

## 常见误区

第一个误区是把 `src/services/session` 当成当前推荐的 Agent CRUD 入口。代码注释已经明确说明这是 legacy service，`createSession`、后端的 `sessionRouter.createSession` 等也带有 deprecated 标记。理解旧逻辑时可以读它，新开发 Agent 创建能力时应优先寻找 `agentService` 及 agent router。

第二个误区是以为这里负责维护前端会话状态。实际上状态维护在 `src/store/session`，特别是 `internal_processSessions`、`internal_dispatchSessions` 和 SWR 刷新逻辑。`sessionService` 只负责请求转发和轻量参数转换。

第三个误区是忽略 `group` 与 `groupId` 的字段差异。前端 session 类型里常见的是 `group`，后端 session schema 使用的是 `groupId`。`updateSession` 中还会把 `group === 'default'` 转成 `null`。读分组相关问题时，这个映射很关键。

第四个误区是把普通 agent session 和 chat group session 混为一谈。`getGroupedSessions` 的后端实现会把普通 sessions 和 chat groups 合并成统一列表，chat group 会被映射成 `type: 'group'` 的 session-like 结构。Store 里 `updateSessionGroupId` 也会区分 `session.type === 'group'`，group session 走 `chatGroupService.updateGroup`，普通 agent session 才走 `sessionService.updateSession`。

第五个误区是认为 `hasSessions` 返回“是否存在 session”。当前实现是调用 `countSessions()` 后返回 `result === 0`，语义更接近“是否没有 session”。根据当前片段推断，这个命名可能有历史遗留或语义不一致风险，依据是函数名与返回条件相反。

第六个误区是只看 `src/services/session` 本目录就试图理解全部流程。这个目录本身很薄，真正的主流程分散在 `src/store/session/slices/session/action.ts`、`src/store/session/slices/sessionGroup/action.ts`、`src/server/routers/lambda/session.ts`、`src/server/routers/lambda/sessionGroup.ts`。读它时应把它当作链路中的适配层，而不是业务闭环。
