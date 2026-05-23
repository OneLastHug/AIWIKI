# 目录：src/routes/(main)/home/features

## 它负责什么

`src/routes/(main)/home/features` 是桌面端主首页的功能组件集合，服务于 `src/routes/(main)/home` 这个 SPA 路由。它不是全局 `src/features` 那种跨页面业务域，而是贴近首页路由的局部 feature：负责首页中间区域的欢迎文案、Agent 选择、输入框、启动入口，以及首页侧边栏可复用的最近访问区块等。

从当前入口看，主页页面文件 `src/routes/(main)/home/index.tsx` 只做外层组合：挂载 `HomePageTracker`、`NavHeader`、`WideScreenContainer`，然后渲染 `./features` 导出的 `HomeContent`。真正的首页主内容入口在 `src/routes/(main)/home/features/index.tsx`，它组合 `AgentSelect`、`WelcomeText`、`InputArea`，登录用户额外展示 `DailyBrief`。因此这个目录可以理解为“首页主体验的局部组件层”，其中最核心的是用户进入首页后选择会话 Agent、看到动态欢迎语、在输入框发起一次聊天/写作/研究/群组模式请求的链路。

需要注意，目录里也包含一些侧边栏或预留模块，例如 `Recents`、`FeaturedPlugins`、`SuggestQuestions`。它们不一定都由 `features/index.tsx` 直接挂载，而是可能被 `src/routes/(main)/home/_layout` 或创建弹窗等邻近逻辑引用。

## 直接子目录地图

`AgentSelect` 负责首页输入框上方的 Agent 选择器。它会加载 Agent 列表，展示当前选中的 Agent 元信息，并把选择结果写入 `systemStatus.homeSelectedAgentId`。它还包含 `useResolvedHomeAgentId`，用于把首页当前有效 Agent 解析出来；如果本地保存的 Agent 不可用，则回退到 inbox agent。

`InputArea` 是首页主输入区。它承接 `ChatInputProvider`、`DesktopChatInput`、拖拽上传、文件上下文、Banner 展示、快捷启动列表和发送逻辑。这里是首页从“输入内容”进入“聊天会话”的关键位置。

`WelcomeText` 负责首页欢迎语和每日 brief 文案的动态展示。它使用 `useHomeDailyBrief`，并支持把文案中的内部路径或外部引用渲染成可点击链接。根据当前片段推断，它与 `InputArea` 共享同一组 daily brief 数据：欢迎语显示一句，输入框 placeholder 对应同一组 hint。

`Recents` 是最近访问/最近会话区块，主要用于首页布局的侧边栏区域，而不是首页中间主内容。它读取 `useHomeStore` 里的 recents 数据，结合 `useInitRecents` 初始化，并提供显示数量、上移下移、隐藏区块、自定义侧边栏等菜单能力。

`FeaturedPlugins` 是推荐插件区块，内部用 `GroupBlock` 包装标题、更多菜单和插件网格列表。根据当前片段推断，它是首页或发现页风格的推荐模块，但在当前 `features/index.tsx` 中没有直接挂载；是否实际显示取决于其他入口是否引用它。

`SuggestQuestions` 当前只看到 `useRandomQuestions` hook，并被邻近的 `_layout/hooks/useCreateModal.tsx` 引用，用于创建 Agent 或引导问题时生成随机建议问题。

`components` 放共享小组件，例如 `GroupBlock`、`GroupSkeleton`、`ScrollShadowWithButton`、`Time`。这些不是业务入口，而是供 `FeaturedPlugins`、`Recents` 等局部区块复用的展示积木。

## 关键入口

最重要的入口是 `src/routes/(main)/home/features/index.tsx`。它定义首页主体内容的结构：外层 `Flexbox`，上半部分是 `AgentSelect` + `WelcomeText` + `InputArea`，登录后再显示 `DailyBrief`。如果只是理解“首页中间区域显示什么”，从这里读即可。

第二个入口是 `src/routes/(main)/home/features/InputArea/index.tsx`。它决定输入框怎么初始化、哪些按钮出现、Banner 如何随机展示、文件上传如何接入、placeholder 如何来自 daily brief、以及发送按钮如何绑定 `useSend`。这里连接了 `useAgentStore`、`useChatStore`、`useGlobalStore`、`useServerConfigStore`、`useFileStore` 等多个 store，是首页交互密度最高的位置。

第三个入口是 `src/routes/(main)/home/features/InputArea/useSend.ts`。它是“按下发送后发生什么”的主逻辑：读取编辑器内容和缓存输入，处理空输入时的 daily hint fallback，读取上传文件和上下文，按 `useHomeStore` 中的 `inputActiveMode` 分派到 `sendAsAgent`、`sendAsGroup`、`sendAsWrite`、`sendAsResearch`，默认模式则确保 Agent 配置已加载，然后调用 `useChatStore.sendMessage` 并跳转到会话地址。

侧边栏相关入口是 `src/routes/(main)/home/features/Recents/index.tsx`，它不是首页正文入口，但被 `src/routes/(main)/home/_layout/Body/index.tsx` 引用，属于同一 home 路由下的重要功能块。

## 主流程位置

首页渲染主流程从 `src/routes/(main)/home/index.tsx` 进入。页面先渲染追踪和导航，再在宽屏容器里渲染 `HomeContent`，也就是 `src/routes/(main)/home/features/index.tsx`。

用户看到的主流程是：`AgentSelect` 解析并展示当前 Agent，`WelcomeText` 展示动态欢迎语，`InputArea` 提供可输入、可上传、可切换模式的聊天输入框。输入区内部通过 `ChatInputProvider` 接入通用聊天输入组件，并把编辑器实例写到 `useChatStore.mainInputEditor`，让后续发送逻辑能读取和清空编辑器内容。

发送主流程集中在 `InputArea/useSend.ts`。默认发送会使用 `useResolvedHomeAgentId` 得到 active agent；如果是首次从首页选择某个 Agent，会先通过 `agentService.getAgentConfigById` 拉取配置并写入 `agentMap`，避免 `sendMessage` 读取不到模型和 provider。随后调用 `sendMessage` 创建隔离 topic，并通过 `router.push` / `router.replace` 进入对应聊天页面。其他模式则交给 home store 的 `sendAsAgent`、`sendAsGroup`、`sendAsWrite`、`sendAsResearch`。

侧边栏主流程在 `src/routes/(main)/home/_layout/index.tsx` 和 `_layout/Body/index.tsx`。`_layout` 保持 Home layout 活跃，挂载 `Sidebar`、`HomeAgentIdSync`、`RecentHydration`；`Body` 再把 `Recents` 作为一个可排序、可隐藏的 accordion 区块接入。

## 推荐阅读顺序

1. 先读 `src/routes/(main)/home/index.tsx`，确认 home 页面外壳如何挂载 `features`。
2. 再读 `src/routes/(main)/home/features/index.tsx`，建立首页主体的组件地图。
3. 读 `src/routes/(main)/home/features/AgentSelect/index.tsx` 和 `src/routes/(main)/home/features/AgentSelect/useResolvedHomeAgentId.ts`，理解首页当前 Agent 如何选择、持久化和回退。
4. 读 `src/routes/(main)/home/features/InputArea/index.tsx`，看输入框、Banner、上传、placeholder 和 `ChatInputProvider` 的组合方式。
5. 读 `src/routes/(main)/home/features/InputArea/useSend.ts`，理解真正发送消息、创建 topic、跳转会话的主链路。
6. 如果关注侧边栏，再读 `src/routes/(main)/home/_layout/Body/index.tsx` 和 `src/routes/(main)/home/features/Recents/index.tsx`。
7. 最后再看 `WelcomeText`、`FeaturedPlugins`、`components` 这些展示型或辅助型模块。

## 常见误区

第一个误区是把这个目录当成全局业务 feature。它位于 `src/routes/(main)/home/features`，更接近路由私有组件层；跨路由通用能力通常在 `src/features`、`src/hooks`、`src/store`、`src/services` 中。

第二个误区是以为 `features/index.tsx` 会挂载目录下所有子模块。当前片段显示，首页正文只直接挂载 `AgentSelect`、`WelcomeText`、`InputArea` 和登录后的 `DailyBrief`；`Recents` 是侧边栏使用，`SuggestQuestions` 被创建弹窗 hook 使用，`FeaturedPlugins` 在当前 home 入口片段中未见直接引用。

第三个误区是忽略 `AgentSelect` 和 `InputArea/useSend` 的配合。首页选择 Agent 不只是 UI 状态，它会影响 `sendMessage` 的 `agentId`，并且需要确保 Agent 配置已进入 `agentMap`。否则发送时可能已跳转到聊天页，但运行时拿不到模型配置。

第四个误区是把空输入发送当成无效操作。这里如果用户直接按 Enter，`useSend` 会尝试使用当前 daily brief 的 hint 作为消息，并推进 brief 轮换；这是首页智能提示体验的一部分。

第五个误区是只看 `InputArea/index.tsx` 而不看 store。`InputArea` 本身大量依赖 `useHomeStore`、`useChatStore`、`useFileStore`、`useAgentStore` 和 `useGlobalStore`。要理解模式切换、上传文件、上下文选择、loading 和侧边栏偏好，需要顺着这些 store 继续读。
