# 目录：docs/prds/teams

## 它负责什么

`docs/prds/teams` 是团队协作（Teams / Agent Team）功能的 PRD 文档入口目录，用来承载“团队”这一产品域的需求索引、功能拆分和实现对照说明。根据当前片段观察，这个目录本身不是业务实现目录，也不是测试目录，而是放在 `docs/prds` 下的产品需求文档区；它对应的实现主要分散在桌面端 renderer 页面、主进程/公共类型、IPC 业务服务、会话消息链路以及 E2E 用例中。

当前目录下只有 `README.md`，且读取到的片段没有可见正文内容。因此这个目录更像是一个预留的 PRD 索引位：它的路径命名已经把主题限定为 `teams`，但功能细节需要结合实现侧代码和测试用例来理解。根据当前片段推断，Teams 功能面向“多个 Agent 组成一个团队”的协作场景，包含创建团队、选择 leader、添加/删除成员、团队页多 tab 会话、成员消息转发、权限模式传播、侧边栏展示、置顶/重命名/删除、工作区联动、全屏/模型选择等流程。

它和 `docs/prds/conversations`、`docs/prds/remote`、`docs/prds/workspaces` 等目录的关系也要分清：Teams 不是一个独立的聊天后端，而是在普通 conversation 能力、ACP/remote agent 能力、workspace 展示能力之上组织出“团队会话”的产品层。实现上也能看到 team-owned conversations 会被普通历史列表过滤，只通过 Teams 面板进入。

## 直接子目录地图

`docs/prds/teams` 当前没有直接子目录。

直接文件只有：

- `docs/prds/teams/README.md`：Teams PRD 的索引入口。当前片段未读到正文内容，因此还不能从文档本身确认它的完整需求清单。学习时应把它当作目录级入口，而不是功能细节来源。

邻近 PRD 目录中可辅助理解 Teams 的位置：

- `docs/prds/conversations`：描述单聊、ACP、remote agent 等会话能力，Teams 的成员会话和消息展示依赖这些基础能力。
- `docs/prds/workspaces`：与工作区、文件、预览相关；Teams 页面中的工作区折叠、成员会话工作区迁移可从这里建立背景。
- `docs/prds/remote`：远程连接和 Channels 能力；remote agent 文档里出现 `teamEventBus` 和团队协作的事件衔接线索。
- `docs/prds/settings`：设置页和 agent 管理相关能力，Teams 创建时的 agent 选择、模型选择与这里的 agent 配置背景有关。

## 关键入口

文档入口是 `docs/prds/teams/README.md`。由于当前文件没有可见正文，真正读代码时需要从实现入口反推 PRD 范围。

前端页面入口集中在 `packages/desktop/src/renderer/pages/team`。其中 `TeamPage.tsx` 是团队详情页的核心容器，`index.tsx` 是页面模块导出入口。组件层面，`components/TeamCreateModal.tsx` 对应创建团队弹窗，`components/TeamTabs.tsx` 对应 leader / member 的 tab 切换，`components/TeamChatView.tsx` 对应团队成员聊天视图，`components/TeamChatEmptyState.tsx` 处理空态，`components/TeamAgentIdentity.tsx` 和 `components/AgentStatusBadge.tsx` 处理成员身份与状态展示。`components/agentSelectUtils.tsx` 与 `components/teamCreateModelResolver.ts` 是创建团队时 agent 与模型选择的辅助逻辑。

状态和副作用入口集中在 `packages/desktop/src/renderer/pages/team/hooks`。`useTeamList.ts` 负责团队列表数据，`useTeamSession.ts` 负责团队页会话生命周期，`useTeamPendingPermissions.ts` 和 `TeamPermissionContext.tsx` 负责权限审批、模式传播和 warmup 相关上下文，`TeamTabsContext.tsx` 负责团队 tab 状态，`useSiderTeamBadges.ts` 和 `useTeamCreatedRedirect.ts` 分别服务侧边栏徽标与创建后跳转。

类型入口在 `packages/desktop/src/common/types/team/database.ts`、`packages/desktop/src/common/types/team/teamTypes.ts`。这些文件定义 Teams 业务的持久化结构和运行时类型，是理解 team、slot、member、conversation 关系的基础。`packages/desktop/src/common/adapter/teamMapper.ts` 则体现了团队数据和通用 adapter 数据之间的转换边界。

验证入口在 `tests/e2e/cases/teams`，覆盖创建、删除、重命名、置顶、成员操作、成员消息、tab 上下文、会话模式、工作区迁移、过期 URL、UI 细节、白名单等端到端场景。

## 主流程位置

创建团队主流程大致从侧边栏或团队入口打开 `TeamCreateModal.tsx`，选择团队名称、leader agent、模型等配置，再通过 bridge / IPC 调用底层 team 服务创建记录。创建成功后，`useTeamCreatedRedirect.ts` 负责跳转到 `#/team/:id` 一类的团队页面。根据当前片段推断，创建逻辑会结合 `agentSelectUtils.tsx` 过滤 `team_capable` 的 agent，并用 `teamCreateModelResolver.ts` 决定默认模型或可用模型。

进入团队页后，`TeamPage.tsx` 拉取 team 数据并组织页面布局。`TeamTabs.tsx` 展示 leader 和成员 slot，`TeamChatView.tsx` 把当前 slot 的 conversation 接入既有聊天组件。这里不是重新实现一套聊天系统，而是复用 `pages/conversation` 下的 ACP / Aionrs / remote 会话发送框、消息流和展示组件。普通会话列表中有过滤 team-owned conversations 的逻辑，例如 `pages/conversation/GroupedHistory/utils/groupingHelpers.ts`，这说明团队内部的成员会话不应直接混入普通聊天历史，而是由 Teams 页面统一呈现。

成员通信主流程涉及会话消息事件。`pages/conversation/platforms/acp/useAcpMessage.ts` 中出现 `teammate_message` 处理，`pages/conversation/Messages/components/MessageText.tsx` 和 `TeammateMessageAvatar.tsx` 负责把队友消息渲染成带发送者身份的消息气泡。远程 agent 文档与实现片段中还出现 `teamEventBus`，说明 remote agent 流式响应完成或错误时会向团队协作层发事件。根据当前片段推断，Teams 的“协作”不是简单地把多个聊天框并排显示，而是通过事件总线、conversation extra、teammate message 标记把成员间消息组织起来。

权限与模式主流程在 `TeamPermissionContext.tsx`、`useTeamPendingPermissions.ts` 以及 conversation 发送框中串联。`AcpSendBox.tsx`、`AionrsSendBox.tsx` 会读取 `useTeamPermission()`，在团队模式下先 warmup session，并让 leader 的模式变更传播给成员。团队模式因此会影响发送框行为、权限审批状态、slash command 拉取和会话初始化时机。

侧边栏和列表主流程由 `useTeamList.ts`、`useSiderTeamBadges.ts` 以及 conversation 侧边栏扩展位承接。E2E 用例 `team-rename-pin.e2e.ts`、`team-delete.e2e.ts` 表明团队条目支持上下文菜单、重命名、置顶/取消置顶、删除后跳转离开团队页等行为。

## 推荐阅读顺序

1. 先看 `docs/prds/teams/README.md`，确认目录是否后来补充了 PRD 索引。当前片段中它没有可见正文，所以不要停在这里。
2. 再看 `packages/desktop/src/common/types/team/database.ts` 和 `packages/desktop/src/common/types/team/teamTypes.ts`，先建立 team、slot、agent、conversation 的数据模型。
3. 接着看 `packages/desktop/src/renderer/pages/team/TeamPage.tsx`、`components/TeamCreateModal.tsx`、`components/TeamTabs.tsx`、`components/TeamChatView.tsx`，理解页面从创建到进入团队详情的结构。
4. 然后看 `hooks/useTeamSession.ts`、`hooks/TeamPermissionContext.tsx`、`hooks/useTeamPendingPermissions.ts`，理解会话生命周期、权限审批和 leader 模式传播。
5. 再横向看 `packages/desktop/src/renderer/pages/conversation/platforms/acp/useAcpMessage.ts`、`AcpSendBox.tsx`、`AionrsSendBox.tsx`、`Messages/components/MessageText.tsx`，理解 Teams 如何复用普通会话能力并注入团队语义。
6. 最后用 `tests/e2e/cases/teams` 校准真实用户流程，优先读 `team-create.e2e.ts`、`team-agent-lifecycle.e2e.ts`、`team-communication.e2e.ts`、`team-member-messaging.e2e.ts`、`team-rename-pin.e2e.ts`、`team-delete.e2e.ts`。

## 常见误区

不要把 `docs/prds/teams` 当成实现目录。它只是 PRD 文档入口，真实实现不在 `docs` 下，而是在 `packages/desktop/src/renderer/pages/team`、`packages/desktop/src/common/types/team`、conversation 平台代码和相关 IPC 服务中。

不要把 Teams 理解成一个全新的聊天平台。根据当前片段推断，它更像是建立在现有 conversation、ACP、Aionrs、remote agent 能力上的组织层，通过 team id、slot、conversation extra、`teammate_message`、`teamEventBus` 等机制把多个 agent 会话编排成协作界面。

不要只看 `TeamPage.tsx` 就判断功能完整性。创建、跳转、权限、消息、侧边栏、工作区折叠、成员头像和模型选择都分散在 hooks、components、conversation 子模块和 E2E 中。

不要忽略普通会话列表的过滤逻辑。team-owned conversations 会被隐藏在普通历史列表之外，这会影响调试时“为什么数据库里有 conversation 但侧边栏不显示”的判断。

不要把成员 tab 等同于独立路由。团队页内部通过 `TeamTabs` 和上下文切换当前成员会话，URL 主要定位 team，具体 tab 状态更多由页面状态和上下文管理。

不要把 leader 权限模式当作每个成员完全独立配置。发送框中读取 `TeamPermissionContext`，leader 的模式变化可能传播给成员；调试权限审批和 YOLO / confirmed 模式时要从团队上下文而不是单个发送框局部状态入手。

不要忽视 E2E。`tests/e2e/cases/teams` 覆盖了很多 PRD 文档当前未展开的行为，是当前片段下最直接的产品流程证据。
