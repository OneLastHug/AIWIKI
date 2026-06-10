# 目录：packages/desktop/src/renderer/components/layout/Sider

## 它负责什么

`packages/desktop/src/renderer/components/layout/Sider` 是桌面端 renderer 侧的主侧边栏实现目录，负责把“会话入口、搜索、定时任务、团队、历史会话、设置入口、主题切换、退出登录”等导航能力组织成一个统一的左侧栏。它不是单纯的展示组件，而是侧边栏的交互中枢：会读取当前路由、移动端布局状态、登录状态、主题状态、定时任务列表，并在用户点击不同入口时完成路由跳转、关闭预览、清理 tooltip、退出批量模式等 UI 状态收束。

从结构上看，这个目录承担的是 layout 层的 Sider 编排职责。具体业务数据主要来自外部模块，例如会话历史来自 `@renderer/pages/conversation/GroupedHistory`，设置侧栏来自 `@renderer/pages/settings/components/SettingsSider`，定时任务来自 `@renderer/pages/cron/useCronJobs`，团队数据来自 `@renderer/pages/team/hooks/useTeamList`。因此这里更像“侧边栏外壳 + 局部导航组件 + 若干排序/持久化辅助”，而不是所有业务列表的完整实现地。

## 直接子目录地图

`CronJobSiderSection`：定时任务在侧边栏中的分组展示。它包含定时任务分区组件和单个任务项组件。分区负责展开/折叠、预取既有会话、监听会话刷新；任务项负责进入任务详情、展开子会话、按 workspace 分组显示子会话，并支持子会话重命名、删除、置顶和拖拽排序。

`SiderNav`：侧边栏顶部固定导航区。它把“新建会话”“批量管理”“搜索会话”“定时任务入口”等稳定入口拆成小组件，并通过 `index.ts` 统一导出。这个目录的组件更偏导航按钮，不直接处理深层业务列表。

根目录下的文件则是侧边栏主体和通用工具：`index.tsx` 是主入口，`SiderFooter.tsx` 是底部设置/返回/主题/退出区域，`TeamSiderSection.tsx` 是团队分区，`SiderItem.tsx` 是可复用的侧栏行，`SortableSiderEntry.tsx` 是拖拽包装，`siderOrder.ts` 与 `useStoredSiderOrder.ts` 处理本地排序持久化，`Sider.module.css` 保存少量无法用 utility class 清晰表达的样式。

## 关键入口

最重要的入口是 `packages/desktop/src/renderer/components/layout/Sider/index.tsx`，默认导出 `Sider` 组件。外部 layout 使用这个组件时，主要通过 `collapsed` 控制收起态，通过 `onSessionClick` 在移动端或抽屉场景下通知父级关闭侧栏。

`Sider` 内部会根据 `pathname.startsWith('/settings')` 切换两套主体内容：在设置路由下懒加载 `SettingsSider`；在非设置路由下展示顶部导航、团队/定时任务插槽和会话历史。会话历史本体由懒加载的 `WorkspaceGroupedHistory` 负责，`Sider` 通过 `afterPinnedContent` 把 `TeamSiderSection` 和 `CronJobSiderSection` 插入到“置顶内容之后、项目和普通会话之前”的位置。

另一个入口是 `packages/desktop/src/renderer/components/layout/Sider/SiderNav/index.ts`，它对外导出 `SiderToolbar`、`SiderSearchEntry`、`SiderScheduledEntry`。如果只改顶部固定导航，通常从这里顺藤摸瓜即可。

## 主流程位置

侧边栏主渲染流程集中在 `index.tsx`：先读取 layout、route、auth、theme、cron jobs 等上下文；再定义若干点击处理函数；最后按“主体区域 + footer”布局渲染。

非设置页的主流程是：`SiderToolbar` 提供新建会话和批量管理；`SiderSearchEntry` 调用 `ConversationSearchPopover` 进入会话搜索；`SiderScheduledEntry` 固定展示定时任务总入口；分割线之后进入可滚动区；`WorkspaceGroupedHistory` 渲染会话历史，并通过 `afterPinnedContent` 插入团队分区和定时任务分区；底部始终渲染 `SiderFooter`。

设置页的主流程更简单：主体区域切换为 `SettingsSider`，底部 `SiderFooter` 的设置按钮变成返回按钮，并在非收起状态下显示主题切换。`index.tsx` 还维护 `lastNonSettingsPathRef`，用于从设置页返回用户进入设置前的页面。

团队流程集中在 `TeamSiderSection.tsx`。它从团队 hooks 读取团队列表和徽标数量，用 `localStorage` 保存团队分区展开状态和置顶团队 id。展开态下每个团队通过 `SiderItem` 渲染，并提供置顶、重命名、删除菜单；收起态下只显示团队图标和角标。

定时任务流程集中在 `CronJobSiderSection/CronJobSiderSection.tsx` 和 `CronJobSiderSection/CronJobSiderItem.tsx`。分区组件负责拿到 jobs 后渲染任务列表；单个任务项会读取任务关联会话，按 workspace 拆组，并使用 `useStoredSiderOrder`、`SortableSiderEntry`、`@dnd-kit` 支持同组内拖拽排序。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/renderer/components/layout/Sider/index.tsx`，建立整体布局和路由切换模型，尤其关注 `isSettings`、`collapsed`、`afterPinnedContent`、`SiderFooter` 的组合关系。
2. 再读 `packages/desktop/src/renderer/components/layout/Sider/SiderNav`，理解顶部固定入口如何拆分，以及收起态和展开态的差异。
3. 接着读 `packages/desktop/src/renderer/components/layout/Sider/SiderFooter.tsx`，看设置页返回、主题切换、退出登录这些底部动作如何与主入口配合。
4. 然后读 `packages/desktop/src/renderer/components/layout/Sider/TeamSiderSection.tsx`，理解团队分区、置顶、重命名、删除和角标逻辑。
5. 最后读 `packages/desktop/src/renderer/components/layout/Sider/CronJobSiderSection`、`siderOrder.ts`、`useStoredSiderOrder.ts`，因为这里涉及定时任务子会话、workspace 分组、拖拽排序和本地持久化，复杂度最高。

## 常见误区

不要把这个目录理解成“会话历史列表”的完整实现。普通会话历史主要在 `@renderer/pages/conversation/GroupedHistory`，这里只是把它懒加载进侧边栏，并提供插槽和必要的状态参数。

不要在这里直接绕过路由或上下文做全局状态修改。当前实现中，进入新会话、搜索选择、定时任务跳转、团队跳转都会先调用 `cleanupSiderTooltips`、`blurActiveElement`，部分流程还会 `closePreview`、退出批量模式；这些步骤是侧栏交互一致性的一部分。

不要忽略 `collapsed`。很多组件都有收起态专门分支：顶部入口会从文字按钮变成图标按钮，团队分区变成图标列表，定时任务分区在主入口中收起时不展示任务列表，tooltip 也只在收起且非移动端时启用。

不要把 `localStorage` key 当成纯样式状态。`team-section-expanded`、`team-pinned-ids`、`cron-section-expanded`、`cron-job-conversation-order-*` 会影响用户长期看到的顺序和展开状态，修改时要考虑兼容已有数据。

不要在跨分组拖拽排序上做错误假设。`useStoredSiderOrder` 在传入 `getGroupKey` 时会阻止跨组移动；`CronJobSiderItem` 中子会话按 workspace 分组后，排序只在同一组内生效。根据当前片段推断，这是为了避免拖拽同时改变 workspace 归属，因为排序 hook 只持久化 id 顺序，不负责修改会话的 workspace 元数据。
