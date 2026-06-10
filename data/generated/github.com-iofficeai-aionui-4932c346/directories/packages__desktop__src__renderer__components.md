# 子系统：packages/desktop/src/renderer/components

## 解决什么问题

`packages/desktop/src/renderer/components` 是桌面端 renderer 进程的共享 UI 组件层，负责把页面级业务、全局状态、Electron/Web 运行时差异和基础设计系统连接起来。它不是单纯的组件清单，而是多个页面复用的“交互基础设施”：应用外框、路由容器、侧栏、标题栏、聊天输入框、Markdown 渲染、文件预览、设置弹窗、Agent 选择器、工作区选择器等都在这里沉淀。

从职责上看，这个目录位于 `pages` 和 `hooks/services/utils` 之间。`pages` 负责具体页面编排，例如会话页、引导页、设置页、定时任务页；`components` 提供跨页面复用的可视化和交互单元；更底层的数据读取、IPC、文件处理、主题、认证、上传状态等则主要来自 `hooks`、`services`、`utils` 和 `common`。因此，修改这里通常会影响多个入口页面，而不是单一功能点。

## 相关目录和文件

`components/layout` 是应用壳层。`Layout.tsx` 负责侧栏展开收起、移动端判断、托盘事件、快捷键、深链、通知点击、目录选择弹窗挂载等全局交互；`Router.tsx` 使用 `HashRouter`、`Routes` 和懒加载页面定义主要路由；`Sider`、`Titlebar`、`WindowControls` 则承接导航和桌面窗口控制；`InstallationIntegrityDialog.tsx` 处理运行时组件缺失或校验失败的提示。

`components/chat` 是聊天输入和输入辅助组件区域。核心是 `SendBox`，它整合文本输入、发送/停止、文件拖拽和粘贴、语音输入、斜杠菜单、`@file` 文件提及、移动端 action sheet、`/btw` 覆盖层等能力。`SlashCommandMenu`、`AtFileMenu`、`BtwOverlay`、`MobileActionSheet`、`ThoughtDisplay`、`CommandQueuePanel` 是它周边的输入增强或状态展示组件。

`components/Markdown` 负责消息和说明文本的 Markdown 渲染。`index.tsx` 基于 `react-markdown`，接入 `remark-gfm`、`remark-math`、`remark-breaks`、`rehype-katex`，并用 `CodeBlock`、`ShadowView`、`LocalImageView` 替换默认代码块、容器和本地图片展示。

`components/base` 是项目风格化的基础组件封装，如 `AionModal`、`AionSelect`、`AionScrollArea`、`AionSteps`、`FileChangesPanel`。它们通常包裹 `@arco-design/web-react`，补齐主题、尺寸、字体缩放和统一样式。

`components/media` 处理文件和媒体相关 UI，包括 `FileAttachButton`、`FilePreview`、`HorizontalFileList`、`UploadProgressBar`、`LocalImageView`、`Diff2Html`、`WebviewHost`。它连接上传状态、文件类型识别、diff 预览和内嵌 webview 展示。

`components/settings` 和其下的 `SettingsModal` 是设置相关的弹窗化入口，同时部分内容也被 `pages/settings` 复用。`DirectorySelectionModal`、`LanguageSwitcher`、`ScaleControl`、`FontSizeStepper`、`UpdateModal` 等承担具体设置项或系统操作。`components/agent` 和 `components/workspace` 则分别提供 Agent 状态/模式/模型选择与工作区选择、最近工作区维护。

## 核心对象

`Layout` 是 renderer 主界面的外层容器。它通过 `LayoutContext` 向子组件传递布局状态，内部处理桌面和移动端差异，并挂载 `Outlet` 给路由页面渲染。它还调用 `useDeepLink`、`useNotificationClick`、`useDirectorySelection`、`useConversationShortcuts` 等 hook，把系统级事件转成 UI 行为。

`PanelRoute`/`Router` 是路由核心对象。它根据认证状态决定是否进入 `login`，认证后加载 `guid`、`conversation/:id`、`settings/*`、`cron`、`team/:id` 等页面。页面组件多数使用 `React.lazy` 和 `Suspense`，加载时回退到 `AppLoader`。

`SendBox` 是聊天输入核心。它的 props 覆盖受控输入、发送回调、停止回调、加载态、工具区、附件回调、斜杠菜单、工作区文件选择、移动端加号菜单等。组件内部依赖输入组合事件、上传状态、拖拽上传、粘贴服务、会话上下文和团队权限，属于高耦合的交互枢纽。

`MarkdownView` 是文本渲染核心。它会规范化 LaTeX 分隔符，拦截链接点击并通过平台工具打开外部链接；本地图片路径交给 `LocalImageView`；代码块交给 `CodeBlock`；可选开启 `allowHtml`，但注释明确提示只应用于可信内容。

`AionModal` 是基础弹窗封装。它在 Arco `Modal` 之上提供预设尺寸、header/footer 配置、内容区域样式、字体缩放适配，并保留旧 `title`、`showCustomClose` API 的兼容能力。

## 运行流程

应用启动时，`renderer/main.tsx` 初始化运行时补丁、浏览器适配、配置服务、i18n、主题、认证和多个全局 provider，然后引入 `Layout`、`Router`、`Sider` 组成主 UI。`Router` 先检查认证状态，未认证时进入登录页，认证后进入受保护布局。受保护布局中，`Layout` 渲染标题栏、侧栏、主内容区域，并由 `Outlet` 承载当前页面。

进入会话页后，页面通常组合 `components/chat`、`components/media`、`components/Markdown`。用户在 `SendBox` 输入文本、选择文件、触发斜杠菜单或语音输入，组件将内容通过页面传入的 `onSend` 交回会话平台实现；消息展示侧再用 `MarkdownView` 渲染模型输出、代码块、表格、本地图片和数学公式。

进入设置页或设置弹窗时，页面会复用 `SettingsModal/contents` 和 `base` 组件。语言、字体缩放、模型、Agent、能力、系统项等设置内容在页面和弹窗之间共享一部分实现，从而避免两套设置 UI 分叉。

## 上下游依赖

上游调用者主要是 `packages/desktop/src/renderer/main.tsx`、`packages/desktop/src/renderer/pages/*`、`packages/desktop/src/renderer/hooks/*`。例如 `main.tsx` 直接装配 `Layout`、`Router`、`Sider`；`pages/conversation` 使用 `SendBox`、`ThoughtDisplay`、`FilePreview`、`MarkdownView`；`pages/settings` 复用 `SettingsModal/contents` 和 `AionModal`；`pages/guid` 使用 `AgentModeSelector`、`FilePreview`、`UploadProgressBar`、工作区工具。

下游依赖包括 `@arco-design/web-react`、`@icon-park/react`、`react-router-dom`、`react-i18next`、`react-markdown`、`remark-*`、`rehype-*`、`katex`、`diff2html` 相关样式，以及项目内部的 `@/common`、`@renderer/hooks`、`@renderer/services`、`@renderer/utils`、`@renderer/pages/conversation` 等。涉及 Electron 能力时，组件不直接访问 Node.js，而是通过 `ipcBridge` 或 renderer 平台工具间接调用，这符合 renderer 进程边界。

## 修改时最容易踩的坑

第一，用户可见文本必须走 i18n。这个目录包含大量按钮、弹窗、提示和错误信息，新增文案时不能直接写中文或英文字符串，应同步维护 locale key，并在必要时运行 i18n 校验。

第二，交互组件应优先使用 Arco 和项目封装组件，避免直接写原生 `<button>`、`<input>`、`<select>` 等交互元素。已有代码中 `AionModal`、`AionSelect`、`AionScrollArea` 等承担了统一主题和字体缩放逻辑，绕开它们容易造成视觉和可访问性不一致。

第三，`SendBox` 的状态来源很多，涉及受控输入、上传、移动端、组合输入法、历史输入、文件提及、斜杠菜单和加载态。修改发送条件、键盘事件或附件同步时，要同时考虑中文输入法 composing、移动端聚焦、防重复发送、`allowSendWhileLoading` 和 pending attachments。

第四，`MarkdownView` 的 `allowHtml` 有安全边界。默认只启用 KaTeX，不启用 raw HTML；如果为了展示效果打开 HTML，必须确认内容来源可信，否则会扩大渲染风险。

第五，renderer 目录不能混入 Node.js API。文件选择、外部链接、运行时状态、窗口控制等能力应沿用 `ipcBridge`、preload 暴露接口或 `utils/platform`，不要在组件里直接调用主进程能力。

第六，布局组件影响全局。`Layout` 同时处理移动端判断、侧栏、托盘事件、深链、通知、快捷键和更新弹窗，任何样式或 effect 改动都可能影响所有页面，需要特别关注路由切换后的清理逻辑和移动端表现。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/renderer/main.tsx`，理解 provider、全局样式、配置服务和 `Layout`/`Router` 的挂载关系。
2. 再读 `packages/desktop/src/renderer/components/layout/Router.tsx` 和 `packages/desktop/src/renderer/components/layout/Layout.tsx`，掌握页面如何进入组件体系。
3. 读 `packages/desktop/src/renderer/components/base/AionModal.tsx`、`AionSelect.tsx`、`AionScrollArea.tsx`，了解共享基础组件的设计约束。
4. 读 `packages/desktop/src/renderer/components/chat/SendBox/index.tsx`，再按需看 `SlashCommandMenu`、`AtFileMenu`、`BtwOverlay`、`MobileActionSheet`。
5. 读 `packages/desktop/src/renderer/components/Markdown/index.tsx`、`CodeBlock.tsx`、`components/media/LocalImageView.tsx`，理解消息内容渲染链路。
6. 最后结合具体业务页阅读调用方，例如 `packages/desktop/src/renderer/pages/conversation`、`packages/desktop/src/renderer/pages/settings`、`packages/desktop/src/renderer/pages/guid`，把共享组件和页面编排对应起来。
