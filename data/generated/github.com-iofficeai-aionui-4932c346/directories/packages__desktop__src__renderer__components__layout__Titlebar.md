# 目录：packages/desktop/src/renderer/components/layout/Titlebar

## 它负责什么

`packages/desktop/src/renderer/components/layout/Titlebar` 是桌面端 renderer 布局层里的标题栏组件目录，负责在应用窗口顶部组织“窗口级导航”和“运行环境相关控制”。它不是普通页面头部，而是 `Layout` 的一部分：既要处理 Electron 桌面窗口的拖拽区域、Windows/Linux 自定义窗口按钮，也要兼容 macOS、WebUI 和移动窄屏下的不同交互。

这个目录的核心职责可以概括为四类：

第一，渲染应用顶栏骨架。`Titlebar` 会根据当前运行环境、是否移动端、是否 macOS、是否存在 workspace 等条件，决定标题栏高度、按钮组合、居中标题和右侧工具区。

第二，承接全局布局开关。它通过 `useLayoutContext` 读取和修改主侧栏折叠状态，通过 `dispatchWorkspaceToggleEvent` 触发 workspace 面板展开/收起，并监听 `WORKSPACE_STATE_EVENT` 来同步 workspace 折叠状态。也就是说，侧栏和 workspace 的入口都被集中到了标题栏。

第三，处理路由级导航。它使用 `useLocation`、`useNavigate` 和 `useNavigationHistory` 判断当前路由，桌面端显示后退/前进按钮；移动端进入设置页时显示“返回聊天”的入口，并用 `sessionStorage` 记住最近一个非 settings 路径。

第四，给移动端对话页提供紧凑品牌区。移动端标题栏空间有限，目录里的 `MobileConversationBrand` 会根据 conversation 信息显示会话名称和 agent logo；团队模式下则根据 `/team/:id` 路由显示 team 名称。根据当前片段推断，这里承担的是“移动端会话上下文识别”的视觉入口，依据是 `Titlebar/index.tsx` 中对 `/conversation/:id`、`/team/:id` 的路径解析，以及 `MobileConversationBrand.tsx` 中对 `ipcBridge.conversation.get` 和 `AgentLogoIcon` 的使用。

## 直接子目录地图

这个目标目录当前没有直接子目录，只有三个直接文件：

`packages/desktop/src/renderer/components/layout/Titlebar/index.tsx` 是主入口，定义并导出 `Titlebar` 组件，集中处理环境判断、按钮显示、路由状态、workspace 状态和移动端标题。

`packages/desktop/src/renderer/components/layout/Titlebar/MobileConversationBrand.tsx` 是移动端会话品牌子组件，负责读取 conversation，推导 backend 类型，结合 preset assistant 信息渲染 agent logo 和会话标题。

`packages/desktop/src/renderer/components/layout/Titlebar/titlebar.css` 是标题栏样式文件，覆盖桌面、macOS、移动端、按钮、品牌区、右侧工具区以及窗口控制按钮相关样式。虽然 `WindowControls` 文件在相邻目录 `packages/desktop/src/renderer/components/layout/WindowControls.tsx`，但它的 `.app-window-controls` 样式也放在这个 CSS 里，因此阅读 Titlebar 时需要把这个相邻组件一起纳入视野。

## 关键入口

最关键入口是 `packages/desktop/src/renderer/components/layout/Titlebar/index.tsx`。它暴露的组件签名是 `Titlebar: React.FC<TitlebarProps>`，目前 `TitlebarProps` 只有一个字段：`workspaceAvailable`。这个字段由上层布局传入，用来决定标题栏是否需要显示 workspace 切换按钮，以及移动端标题是否按对话/工作区场景居中偏移。

上层入口在 `packages/desktop/src/renderer/components/layout/Layout.tsx`。该文件导入 `Titlebar`，并在主布局结构中渲染 `<Titlebar workspaceAvailable={workspaceAvailable} />`。因此，学习时不要把 Titlebar 当作页面组件看，它更接近 layout chrome，也就是包裹页面路由内容的外框组件。

跨目录入口还包括 `packages/desktop/src/renderer/components/layout/WindowControls.tsx`。`Titlebar/index.tsx` 在 Electron 非 macOS 环境下渲染 `WindowControls`，后者通过 `ipcBridge.windowControls` 调用 minimize、maximize、unmaximize、close，并订阅 `maximizedChanged` 来切换最大化/还原图标。窗口控制逻辑不在 Titlebar 目录内，但它是 Titlebar 右侧工具区的重要组成部分。

移动端工具区的入口是 DOM slot：`app-titlebar-actions-slot`。`Titlebar/index.tsx` 在移动端右侧 toolbar 中渲染这个空容器，`packages/desktop/src/renderer/pages/conversation/components/ChatLayout/index.tsx` 会查找这个元素，把模型选择器、定时任务等聊天页动作挂到标题栏上。这个设计说明 Titlebar 不直接知道所有页面动作，而是提供一个移动端动作插槽。

## 主流程位置

主流程从 `Layout.tsx` 开始。`Layout` 负责判断移动端、侧栏宽度、workspace 可用性，并通过 `LayoutContext` 把 `siderCollapsed`、`setSiderCollapsed`、`isMobile` 等状态提供给下游。随后 `Layout` 渲染 `Titlebar`，标题栏开始根据上下文和运行环境组装 UI。

进入 `Titlebar/index.tsx` 后，第一层是运行环境分支：`isElectronDesktop()` 判断是否 Electron，`isMacOS()` 判断是否 macOS。非 macOS 的 Electron 桌面显示 `WindowControls`；macOS 和 WebUI 更偏向在标题栏上保留 workspace 开关；桌面端启用 `-webkit-app-region: drag`，按钮区域再通过 `no-drag` 排除拖拽。

第二层是导航和布局按钮分支。左侧 `menu` 区可能包含主侧栏 toggle、移动端 settings 返回按钮、桌面端 history back/forward。主侧栏按钮调用 `layout.setSiderCollapsed`；workspace 按钮调用 `dispatchWorkspaceToggleEvent`；前进后退走 `NavigationHistoryContext`；移动端设置页返回则优先回到 `sessionStorage` 中保存的最近非 settings 路径。

第三层是标题内容分支。默认标题是 `AionUi`。移动端会根据当前路径决定是否显示 team 名称、conversation 名称，或者用 `MobileConversationBrand` 显示带 logo 的会话品牌。为了保证标题视觉居中，组件会用 `ResizeObserver` 测量左侧 menu 和右侧 toolbar 的宽度差，并写入 CSS 变量 `--app-titlebar-mobile-center-offset`。

第四层是样式落点。`titlebar.css` 用 `app-titlebar--desktop`、`app-titlebar--mac`、`app-titlebar--mobile`、`app-titlebar--mobile-conversation` 等 class 区分布局；按钮使用 `app-titlebar__button`、`app-titlebar__button--mobile`；标题区使用 `app-titlebar__brand`、`app-titlebar__brand-mobile`、`app-titlebar__brand-text`。主题预设目录里也有对 `.app-titlebar` 的覆盖，因此改样式时要注意可能受到外部主题 CSS 影响。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/renderer/components/layout/Layout.tsx` 中渲染 `Titlebar` 的位置，理解它在整体布局里位于 `Sider`、workspace、`Outlet` 之前还是之间，以及 `LayoutContext` 提供了哪些状态。

2. 再读 `packages/desktop/src/renderer/components/layout/Titlebar/index.tsx` 的顶部状态和派生变量，重点看 `showWindowControls`、`showWorkspaceButton`、`showSiderToggle`、`showBackToChatButton`、`showHistoryNav` 这些布尔值。它们基本决定了标题栏在不同平台和路由下的外观。

3. 接着读 `Titlebar/index.tsx` 的几个 handler 和 effect：`handleSiderToggle`、`handleWorkspaceToggle`、`handleBackToChat`，以及同步 workspace、保存最近非 settings 路径、加载移动端标题、计算居中偏移的 `useEffect`。这些是行为主线。

4. 然后读 `packages/desktop/src/renderer/components/layout/Titlebar/MobileConversationBrand.tsx`，理解移动端会话标题如何从 conversation 推导 backend，并如何交给 `AgentLogoIcon` 渲染。

5. 最后读 `packages/desktop/src/renderer/components/layout/Titlebar/titlebar.css` 和相邻的 `packages/desktop/src/renderer/components/layout/WindowControls.tsx`。前者解释布局和视觉细节，后者解释 Windows/Linux 自定义窗口按钮如何通过 IPC 接入主进程。

## 常见误区

不要把 `Titlebar` 理解成某个页面自己的 header。它属于 layout chrome，跨 conversation、team、settings、guid 等路由复用。页面级动作如果要出现在移动端标题栏，通常应通过 `app-titlebar-actions-slot` 这类插槽接入，而不是把页面逻辑硬塞进 `Titlebar`。

不要忽略 Electron 平台差异。Windows/Linux 下标题栏需要自定义 `WindowControls`；macOS 需要给系统 traffic light 预留空间；WebUI 没有原生窗口控制，但仍可能需要 workspace 开关。`isElectronDesktop()` 和 `isMacOS()` 是理解显示分支的关键。

不要只看 `Titlebar` 目录内的文件就下结论。workspace 开关依赖 `@renderer/utils/workspace/workspaceEvents`，侧栏状态来自 `LayoutContext`，历史导航来自 `NavigationHistoryContext`，窗口按钮 IPC 在 `WindowControls.tsx` 和主进程 bridge 中完成，移动端聊天动作插槽由 conversation 页面使用。

不要随意改 `titlebar.css` 中的 `-webkit-app-region`。标题栏作为可拖拽区域时，按钮、菜单、窗口控制区必须显式设置 `no-drag`，否则点击事件可能被窗口拖拽吞掉。

不要把移动端标题居中看成纯 CSS 问题。当前实现会动态测量左右区域宽度，并通过 CSS 变量修正中心点。如果新增左侧或右侧按钮，必须考虑 `ResizeObserver` 计算是否仍然成立，以及 `max-width: calc(100% - 180px)` 是否足够容纳新内容。

不要忽略 i18n。标题栏按钮 tooltip 使用 `useTranslation` 读取 `common.expandMore`、`common.collapse`、`common.back`、`common.historyBack`、`common.forward` 等键。新增用户可见文案时应继续使用 i18n key，而不是直接写死字符串。
