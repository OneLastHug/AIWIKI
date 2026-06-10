# 目录：packages/desktop/src/renderer/pages/team

## 它负责什么

`packages/desktop/src/renderer/pages/team` 是桌面端 renderer 里的“团队会话”页面模块，负责把一个 `TTeam` 展示成多 Agent 协作的聊天工作台。它不直接实现团队数据的持久化，也不直接访问主进程或文件系统，而是通过 `ipcBridge.team.*`、`ipcBridge.conversation.*` 等 IPC 能力读取和更新团队、会话、模型等信息。

从当前片段看，这个目录覆盖三类职责：第一是团队页面入口，按路由参数加载 team 并渲染页面；第二是团队内多 Agent 的聊天布局，包括 leader、成员卡片、横向滚动、全屏某个成员、移除成员、重命名团队等交互；第三是创建团队相关的弹窗与 Agent 选择逻辑，负责选择团队 leader、解析默认模型、选择 workspace，然后调用团队创建 IPC。

需要注意的是，这里不是通用 conversation 页面本身。团队页面会复用 `packages/desktop/src/renderer/pages/conversation/platforms/*` 下的聊天实现，例如 `AcpChat`、`AionrsChat`、`LegacyReadOnlyConversation`，本目录主要做“团队编排层”和页面外壳。

## 直接子目录地图

`components` 存放团队页面的局部 UI 与工具组件。主要包括团队聊天视图、创建弹窗、Agent 身份展示、状态徽标、标签页、空状态，以及创建团队时的 Agent 选项转换和默认模型解析工具。它承担页面可视层的大部分工作，但其中也有少量与创建流程相关的纯逻辑函数，例如 `agentSelectUtils.tsx`、`teamCreateModelResolver.ts`。

`hooks` 存放团队页面专用状态与上下文。这里有标签页上下文、权限上下文、团队列表、团队会话、创建后跳转、侧边栏徽标、待处理权限计数等逻辑。根据当前片段推断，这些 hook 负责把页面状态、SWR 数据、IPC 更新和局部缓存组合起来，避免 `TeamPage.tsx` 完全承担所有状态管理。

根目录下的文件数量很少，核心是 `index.tsx` 和 `TeamPage.tsx`。前者是路由入口，后者是页面主体。

## 关键入口

`packages/desktop/src/renderer/pages/team/index.tsx` 是进入团队详情页的最外层入口。它通过 `useParams<{ id: string }>()` 读取路由里的 `id`，再用 `useSWR` 以 `team/${id}` 为 key 调用 `ipcBridge.team.get.invoke({ id })` 获取团队数据。加载中或没有数据时返回 `null`，拿到团队后渲染 `<TeamPage key={team.id} team={team} />`。这里的 `key={team.id}` 很关键：它让切换团队时重新挂载页面内部状态，避免上一个团队的标签页、滚动位置或局部状态残留。

`packages/desktop/src/renderer/pages/team/TeamPage.tsx` 是主页面入口。它接收 `team: TTeam`，调用 `useTeamSession(team)` 获取团队成员状态、重命名或移除 Agent 的操作、刷新 team 的能力；同时读取登录用户，用于刷新用户对应的团队列表缓存。它外层挂载 `TeamTabsProvider`，内部由 `TeamPageContent` 负责渲染具体布局。

`packages/desktop/src/renderer/pages/team/components/TeamCreateModal.tsx` 是创建团队入口组件。它负责选择 team leader、填写 team name、选择项目目录 workspace，并在提交时构造 `TeamAgent[]`，解析 conversation type 和默认 model，最后调用 `ipcBridge.team.create.invoke(...)`。创建成功后通过 `onCreated(team)` 把结果交回调用方。创建后的导航逻辑很可能在 `hooks/useTeamCreatedRedirect.ts` 中完成；这是根据文件名和目录职责推断。

## 主流程位置

团队详情加载流程在 `index.tsx`。路由参数 `id` 决定 SWR key，IPC 返回的 team 数据进入 `TeamPage`。如果调试“为什么团队页空白”，优先看这里的 `id` 是否存在、`ipcBridge.team.get` 是否返回数据，以及 SWR key 是否被正确触发。

团队页面状态主流程在 `TeamPage.tsx` 和 `hooks/useTeamSession.ts`。`TeamPage` 负责把 `team.agents` 交给 `TeamTabsProvider`，同时提供 `renameAgent`、`removeAgent`、`mutateTeam` 等操作。页面中重命名团队会调用 `ipcBridge.team.renameTeam.invoke`，成功后刷新当前 team 和团队列表缓存。移除 Agent 时会根据该 slot 当前状态决定是否弹确认框，然后调用移除逻辑。

多 Agent 展示主流程在 `TeamPageContent`。它从 `useTeamTabs()` 读取 `agents`、`activeSlotId`、`statusMap`、`switchTab`，找出当前 active agent 和 leader agent；再把每个 agent 渲染为一个聊天面板。这里还处理横向滚动箭头、激活 tab 后滚动到对应卡片、单个 Agent 全屏展示、workspace 侧边栏标题与内容、待处理权限计数等页面级行为。

单个 Agent 的聊天加载在 `TeamAgentConversation`，它根据 `agent.conversation_id` 用 SWR 获取 conversation，然后传给 `TeamChatView`。如果 conversation 是 `aionrs`，还会在 header 区域接入模型选择器；如果是 ACP 或兼容 ACP 的类型，则走相应平台聊天组件。`TeamChatView` 是平台分发层，会根据 `conversation.type` 懒加载 `AcpChat`、`AionrsChat` 或 legacy 只读会话，并把团队空状态 `TeamChatEmptyState` 作为 empty slot 传下去。

团队创建主流程在 `TeamCreateModal.tsx`、`agentSelectUtils.tsx`、`teamCreateModelResolver.ts`。`agentSelectUtils.tsx` 把 CLI agents 和 preset assistants 统一成 `TeamAgentOption`，并过滤出 `team_capable` 且未废弃的运行时 Agent；`resolveConversationType` 把 backend 映射到 `acp` 或 `aionrs`。`teamCreateModelResolver.ts` 负责为不同 conversation type 解析默认模型，避免创建出来的团队会话缺失模型配置。

权限和提示流程分散在 `hooks/TeamPermissionContext.tsx`、`hooks/useTeamPendingPermissions.ts`、`components/AgentStatusBadge.tsx`。其中 `useTeamPendingPermissions` 会用 `team_id` 和 conversation ids 管理待处理权限数量，并使用 `localStorage` 做局部缓存。根据当前片段推断，这些计数最终进入 `TeamTabs` 或 badge，用来提醒某个 Agent 会话里存在待处理授权。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/renderer/pages/team/index.tsx`，确认团队页如何从路由进入、如何通过 IPC 加载 team。
2. 再读 `packages/desktop/src/renderer/pages/team/TeamPage.tsx`，重点看 `TeamPage`、`TeamPageContent`、`TeamAgentConversation` 三层结构，理解 team、agent、conversation 如何串起来。
3. 接着读 `packages/desktop/src/renderer/pages/team/hooks/TeamTabsContext.tsx` 和 `packages/desktop/src/renderer/pages/team/hooks/useTeamSession.ts`，理解 active slot、Agent 状态、重命名、移除、刷新这些核心状态从哪里来。
4. 然后读 `packages/desktop/src/renderer/pages/team/components/TeamChatView.tsx`，明确团队页面如何复用 ACP、AionRS、Legacy conversation 组件。
5. 如果关注创建流程，再读 `packages/desktop/src/renderer/pages/team/components/TeamCreateModal.tsx`，随后补 `agentSelectUtils.tsx` 和 `teamCreateModelResolver.ts`。
6. 最后读 `TeamPermissionContext.tsx`、`useTeamPendingPermissions.ts`、`useSiderTeamBadges.ts`、`useTeamList.ts`、`useTeamCreatedRedirect.ts` 这类辅助 hook，补齐侧边栏、权限提示、创建后跳转等边缘流程。

## 常见误区

不要把 `team` 页面理解成新的聊天引擎。真正的聊天渲染仍在 `conversation/platforms` 体系里，本目录只是按团队结构组织多个 conversation，并处理团队专属的布局、状态和操作。

不要在这个目录里直接访问 Node.js API。它位于 renderer 进程，只能通过 preload 暴露的 `ipcBridge` 与主进程通信。团队创建、获取、重命名、移除成员、更新 conversation model 等都应走已有 IPC。

不要绕过 i18n 写死用户可见文本。当前文件里大量使用 `useTranslation()` 和 `t('team....')`、`t('common....')`，新增按钮、提示、空状态文案时也应沿用 i18n key。

不要只改 `TeamChatView` 就期望影响团队整体布局。`TeamChatView` 只负责把单个 conversation 分发到对应聊天组件；横向多面板、tab、全屏、workspace sider、移除成员这些行为主要在 `TeamPage.tsx` 和相关 hooks 中。

不要忽略 `key={team.id}`、SWR key、`mutateTeam`、`globalMutate` 之间的关系。团队页有多层缓存：当前 team、用户团队列表、conversation 数据、权限计数缓存。修改团队结构后，如果只更新局部状态而不刷新相关 SWR key，侧边栏或页面内容可能出现不同步。

不要把 leader 当成普通成员处理。页面里多处通过 `agent.role === 'leader'` 或 leader conversation id 判断是否显示发送框、模型选择器、空状态提示和移除逻辑。涉及删除、切换、默认 active slot 或团队派发能力时，需要优先确认 leader 相关约束。
