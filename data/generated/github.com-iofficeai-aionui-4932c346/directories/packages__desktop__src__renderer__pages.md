# 子系统：packages/desktop/src/renderer/pages

## 解决什么问题

`packages/desktop/src/renderer/pages` 是桌面端 Renderer 进程的页面层，负责承载应用的主要业务界面：入口引导、登录、会话、团队协作、定时任务、设置页以及组件展示页。它位于 React UI 的“路由页面”位置，向上被 `packages/desktop/src/renderer/components/layout/Router.tsx` 挂载到 `HashRouter`，向下组合 `components`、`hooks`、`utils`、IPC bridge、全局上下文和 Arco Design 组件，形成可交互的业务页面。

这个目录不是纯展示层。尤其是 `conversation`、`guid`、`team`、`cron`、`settings` 都包含页面私有 hook、状态适配、业务工具函数和局部组件。因此阅读时应把它理解为“各业务页面的前端编排层”：它负责把路由参数、用户输入、会话状态、模型/助手配置、文件预览、任务状态等上下文组织成完整 UI 流程，但不应直接混入主进程能力；跨进程能力应经由 preload 暴露的桥接 API 或 `@/common` 适配层完成。

## 相关目录和文件

`packages/desktop/src/renderer/components/layout/Router.tsx` 是页面目录最重要的入口。根据当前片段推断，它使用 `HashRouter`、`Routes`、`Route`、`Navigate` 将页面映射到 `/guid`、`/login`、`/chat` 或会话相关路由、`/team/:teamId`、`/settings/...`、`/scheduled`、`/scheduled/:job_id`、`/test/components` 等路径。

`packages/desktop/src/renderer/main.tsx` 是更上层的装配点，会引入 `Router`，同时包裹如 `PreviewProvider` 这类页面级上下文，并触发 `repairAllCronJobTimeZonesOnce` 等启动期修复逻辑。

`packages/desktop/src/renderer/pages/conversation` 是会话主页面子系统，包含 `GroupedHistory`、`Messages`、`Preview`、`Workspace`、`components`、`hooks`、`runtime`、`platforms`、`utils` 等分层。它连接聊天消息流、历史会话、工作区文件、预览面板和运行时视图状态。

`packages/desktop/src/renderer/pages/guid` 是应用引导/新建会话入口，包含模型选择、助手选择、快捷动作、提及下拉、输入框状态和发送逻辑。它与 `conversation` 的创建参数、错误处理、预热逻辑存在直接关系。

`packages/desktop/src/renderer/pages/settings` 聚合模型、助手、Agent、外观、能力、MCP 工具、WebUI、系统、扩展等设置页。其 `components/SettingsSider.tsx` 与路由路径需要保持一致。

`packages/desktop/src/renderer/pages/cron` 负责定时任务列表、详情、创建弹窗、状态标签、侧边栏提示和时区修复。`packages/desktop/src/renderer/pages/team` 负责团队会话、团队列表、创建弹窗、权限请求和团队标签页状态。

## 核心对象

核心页面组件包括 `GuidPage`、`LoginPage`、`ChatConversation` 或 `conversation/index.tsx` 导出的会话页、`TeamPage`、`ScheduledTasksPage`、`TaskDetailPage`，以及设置页下的 `AgentSettings`、`AssistantSettings`、`AppearanceSettings`、`SystemSettings`、`ToolsSettings/McpManagement` 等。

核心 hook 分布在各页面内部，例如 `useGuidSend` 负责从引导页发起会话创建和导航，`useGuidAgentSelection` 维护助手选择，`useConversationAgents`、`useWorkspaceCollapse`、`useTitleRename` 维护会话页交互，`useCronJobs` 聚合定时任务数据，`useTeamSession`、`useTeamList`、`useTeamPendingPermissions` 支撑团队页状态。

核心上下文和运行时对象包括 `PreviewProvider`、`usePreviewContext`、`TeamPermissionContext`、`TeamTabsContext`、`conversationRuntimeViewStore`、`useConversationRuntimeView`。这些对象让跨组件状态不必层层透传，但也意味着修改页面时要先确认状态来源和更新路径。

## 运行流程

应用启动后，`main.tsx` 装配全局 provider 与 `Router`。`Router.tsx` 根据认证状态决定进入 `/guid` 还是 `/login`，并通过布局组件承载主页面。用户在 `guid` 中输入需求、选择模型/助手或快捷动作后，`useGuidSend` 会组织创建会话所需参数，调用会话创建相关能力，成功后通过 `react-router-dom` 导航到会话页面。

进入会话页后，页面会加载历史、消息列表、工作区和预览上下文。消息展示由 `Messages` 负责，文件和产物预览由 `Preview` 与 `Workspace` 协作，侧边栏历史由 `GroupedHistory` 提供。设置页通常从 `/settings/{tab}` 进入，由 `SettingsSider` 控制不同设置模块；定时任务页从 `/scheduled` 进入，详情页通过 `job_id` 路由参数读取任务；团队页通过 team 相关 hook 获取列表、会话和权限状态。

## 上下游依赖

上游主要是 `Router.tsx`、`Layout`、`Sider`、`Titlebar`、全局上下文和 `main.tsx`。其中 `Sider` 会直接引用 `GroupedHistory`、`SettingsSider`、`CronJobSiderSection`、`TeamSiderSection` 等页面内部模块，说明页面目录并非只被路由消费，也被布局导航复用。

下游依赖包括 `@arco-design/web-react`、`@icon-park/react`、`react-router-dom`、`@/renderer/components`、`@/renderer/hooks`、`@/renderer/utils`、`@/common` 与 IPC bridge。根据当前片段推断，页面中的业务数据最终会通过 renderer hooks、common adapter 或 preload 暴露的 API 与主进程、文件系统、模型平台、MCP、定时任务服务等能力交互。

## 修改时最容易踩的坑

第一，路由路径和设置侧边栏配置必须同步。新增 `/settings/...` 页面时，只改 `Router.tsx` 不改 `SettingsSider`，会导致页面能访问但导航不可见，或导航跳到不存在路径。

第二，Renderer 页面不能直接使用 Node.js API。项目架构明确区分 `packages/desktop/src/process` 和 `packages/desktop/src/renderer`，页面层需要通过 IPC bridge 或已有 hook 获取主进程能力。

第三，用户可见文本应走 i18n。当前片段中 `TestShowcase.tsx` 有硬编码中文，可能是展示/测试页面遗留；新增正式页面时不要照搬，应按项目 i18n 规范添加 key。

第四，会话相关状态分散在 `conversation`、全局上下文、侧边栏和预览 provider 中。修改消息、预览、工作区或历史列表时，要同时检查 `components/layout/Sider`、`hooks/context/ConversationHistoryContext.tsx`、`components/chat/SendBox` 等调用方。

第五，页面目录内有不少深层私有工具，例如 `conversation/utils/conversationCache.ts`、`cron/repairCronJobTimeZone.ts`、`guid/hooks/agentSelectionUtils.ts`。它们虽然在 `pages` 下，但已被其他 renderer 模块引用，重命名或移动会产生跨目录影响。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/renderer/main.tsx`，理解全局 provider、启动期副作用和 `Router` 的挂载方式。
2. 再读 `packages/desktop/src/renderer/components/layout/Router.tsx`，建立路由到页面模块的映射。
3. 按主链路阅读 `packages/desktop/src/renderer/pages/guid`，重点看 `GuidPage.tsx`、`hooks/useGuidSend.ts`、模型和助手选择相关 hook。
4. 继续读 `packages/desktop/src/renderer/pages/conversation/index.tsx`、`components/ChatConversation.tsx`、`Messages`、`Workspace`、`Preview`，理解聊天主流程。
5. 然后读 `packages/desktop/src/renderer/components/layout/Sider` 与 `pages/conversation/GroupedHistory`，补全导航、历史和侧边栏关系。
6. 最后按需阅读 `settings`、`cron`、`team`。这些模块相对独立，但会复用会话、助手、Agent、模型平台和权限等基础能力。
