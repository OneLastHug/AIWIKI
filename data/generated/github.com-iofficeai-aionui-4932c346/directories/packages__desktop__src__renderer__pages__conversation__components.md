# 子系统：packages/desktop/src/renderer/pages/conversation/components
## 解决什么问题
这个目录承载的是“会话页的可复用界面层”，它把会话详情页里最常见、最容易变动的几块 UI 拆出来：主聊天区、历史区、标题编辑、工作区开关、滑动分栏、技能提示，以及移动端/桌面端不同布局下的壳层组织。它不是单纯的组件杂物间，而是会话页面的布局骨架和交互拼装层。根据当前片段推断，它主要服务于 `packages/desktop/src/renderer/pages/conversation/index.tsx` 所代表的会话主页面，并被 `pages/team/TeamPage.tsx` 等邻近页面复用。

## 相关目录和文件
核心文件集中在 `packages/desktop/src/renderer/pages/conversation/components/` 下：
`ChatLayout/index.tsx` 负责总体布局；`ChatConversation.tsx`、`ChatHistory.tsx` 分别对应主聊天内容和历史侧栏；`ChatSlider.tsx` 处理左右区域的拖拽/分隔；`ChatTitleEditor.tsx` 管理会话标题编辑；`WorkspaceCollapse.tsx` 管理工作区折叠态；`ConversationSkillsIndicator.tsx`、`SkillRuleGenerator.tsx` 服务于技能与规则展示；`ConversationTitleMinimap/` 目录则是标题预览与定位小地图，包含 `index.tsx`、`minimapTypes.ts`、`minimapUtils.ts`、`useMinimapPanel.ts` 和样式文件；`ChatLayout/` 子目录里还有 `MobileWorkspaceOverlay.tsx`、`WorkspaceOpenButton.tsx`、`WorkspacePanelHeader.tsx` 与 `chat-layout.css`，说明布局同时兼顾移动端覆盖层和桌面端面板头部。

## 核心对象
这里的核心对象不是单个数据模型，而是一组围绕会话视图状态的 UI 构件：
`ChatLayout` 是总容器，决定主区、侧栏和工作区如何排布；`ChatSlider` 是布局尺寸变化的控制器；`ChatHistory` 负责历史浏览；`ChatTitleEditor` 负责可编辑标题；`ConversationTitleMinimap` 负责压缩态的标题导航与可视提示；`WorkspaceCollapse` 和 `WorkspaceOpenButton` 处理工作区开合；`ConversationSkillsIndicator` 与 `SkillRuleGenerator` 则把会话能力、规则生成结果挂到页面上。目录内还配套了 `minimapTypes.ts`、`layout.css` 这类类型和样式文件，说明这些组件有比较强的布局契约。

## 运行流程
会话页进入后，外层页面先准备会话上下文、宽度约束和运行时状态，再把这些状态传给这里的布局组件。`ChatLayout` 作为入口决定当前是桌面双栏、单栏，还是移动端覆盖层模式；`ChatSlider` 在允许拖动时更新分栏比例；`WorkspaceCollapse` 和 `MobileWorkspaceOverlay` 控制工作区是否展开；`ChatConversation` 渲染当前会话主体，`ChatHistory` 提供历史导航；标题编辑与 minimap 组件在会话标题区域工作，补足重命名和快速定位能力。根据当前片段推断，这些组件还会借助上层 hooks 和 runtime 状态，在会话切换、窗口缩放、工作区开关变化时重新计算布局。

## 上下游依赖
上游主要来自 `packages/desktop/src/renderer/pages/conversation/hooks/`、`runtime/` 和 `utils/`，例如 `useLayoutConstraints.ts`、`useWorkspaceCollapse.ts`、`useTitleRename.ts`、`conversationRuntime.ts`、`layoutCalc.ts`、`conversationCache.ts` 等，它们提供尺寸、标题、会话缓存和运行时状态。下游则是实际消费这些组件的页面：`packages/desktop/src/renderer/pages/conversation/index.tsx` 是主入口，`packages/desktop/src/renderer/pages/team/TeamPage.tsx` 也直接使用 `ChatLayout` 和 `ChatSlider`，说明这里不是仅供单页使用的私有实现。再往下会连到 `Messages/`、`Workspace/`、`Preview/` 等同级目录，它们分别提供消息流、工作区内容和文件预览。

## 修改时最容易踩的坑
第一，`ChatLayout`、`ChatSlider`、`useLayoutConstraints` 和 `layoutCalc.ts` 是耦合关系，改一处很容易把分栏宽度算坏。第二，这些组件同时服务桌面和移动端，尤其 `MobileWorkspaceOverlay` 与 `WorkspaceOpenButton` 的交互不能只看桌面效果。第三，这个目录被 `TeamPage` 复用，改布局时要检查团队页是否被连带影响。第四，项目约束里前端文本应走 i18n，组件新增文案不能硬编码。第五，AionUi 的 renderer 侧要求用 Arco 组件和既有样式体系，别把交互控件退回到原生 HTML 或临时拼装样式。第六，`ConversationTitleMinimap` 有独立的 types、utils 和 hook，改标题导航逻辑时要保持这几者的契约一致。

## 推荐阅读顺序
先看 `packages/desktop/src/renderer/pages/conversation/index.tsx`，再看 `hooks/useLayoutConstraints.ts`、`useWorkspaceCollapse.ts`、`useTitleRename.ts`，把页面状态来源搞清楚；接着读 `components/ChatLayout/index.tsx` 和 `ChatSlider.tsx`，理解整体布局；然后看 `ChatConversation.tsx`、`ChatHistory.tsx`、`ChatTitleEditor.tsx`；最后补 `ConversationTitleMinimap/index.tsx`、`minimapUtils.ts`、`useMinimapPanel.ts`，再回头看 `pages/team/TeamPage.tsx` 验证复用场景。
