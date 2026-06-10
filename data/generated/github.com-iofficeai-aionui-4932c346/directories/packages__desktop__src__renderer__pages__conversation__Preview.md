# 目录：packages/desktop/src/renderer/pages/conversation/Preview

## 它负责什么

`packages/desktop/src/renderer/pages/conversation/Preview` 是会话页里的“预览面板”模块，负责把聊天、文件、Diff、Office 文档、URL、图片、Markdown、HTML、代码等内容以侧边或嵌入式面板的形式打开、切换、查看和编辑。它不是底层文件读取服务，也不是 Office 转换服务；它更像 renderer 层的预览工作台：接收外部传入的内容与元数据，维护预览 tab 状态，然后选择合适的 viewer、editor、toolbar、历史记录与主题配置来展示。

从邻近引用看，预览入口主要被 `usePreviewLauncher`、`useAutoPreviewOfficeFiles`、Markdown Mermaid 预览、Diff 预览按钮、导航拦截器、聊天输入区、侧边栏关闭逻辑等调用。根据当前片段推断，这个目录承担“预览状态中心 + 预览 UI 容器 + 类型化渲染组件”的角色，真正的文件内容读取、Office 预览、历史快照保存等能力通过 `common/adapter/ipcBridge.ts` 里的 preview 相关 API 或外部 hook 接入。

## 直接子目录地图

`components` 是 UI 组件总入口，下面按职责继续分层。`components/PreviewPanel` 放面板框架相关组件，包括 `PreviewPanel.tsx`、`PreviewToolbar.tsx`、`PreviewTabs.tsx`、`PreviewHistoryDropdown.tsx`、`PreviewContextMenu.tsx`、`PreviewConfirmModals.tsx` 和 `previewToolbarUtils.ts`。这里是面板外壳、tab 切换、工具栏按钮、右键菜单、确认弹窗和历史下拉的集中位置。

`components/editors` 放可编辑内容的编辑器封装，包括 `CodeEditor.tsx`、`MarkdownEditor.tsx`、`HTMLEditor.tsx`。当预览内容处于 editable 模式，或需要对文本类内容进行编辑时，应优先从这里理解编辑交互。

`components/renderers` 更偏底层渲染能力，目前有 `HTMLRenderer.tsx`、`SelectionToolbar.tsx`、`htmlInspectScript.ts`。从命名看，它处理 HTML 渲染、选区工具条以及注入到 HTML 预览环境中的检查脚本。

`components/viewers` 是按内容类型拆分的查看器集合，包括 `MarkdownViewer.tsx`、`HTMLViewer.tsx`、`ImageViewer.tsx`、`PDFViewer.tsx`、`DiffViewer.tsx`、`URLViewer.tsx`、`ExcelViewer.tsx`、`PptViewer.tsx`、`OfficeDocViewer.tsx`、`OfficeWatchViewer.tsx`。阅读时不要把它们看成独立页面，它们是由 `PreviewPanel` 或上层选择逻辑按 `PreviewContentType` 分发出来的具体渲染实现。

`context` 放预览状态上下文。`PreviewContext.tsx` 应是最核心的状态与动作提供者，外部大量代码通过 `usePreviewContext` 调用 `openPreview`、`closePreview`、`findPreviewTab` 等能力。`PreviewToolbarExtrasContext.tsx` 看起来用于让具体 viewer 或 editor 向面板工具栏追加额外操作。

`hooks` 放预览面板内部行为 hook。`usePreviewHistory.ts` 负责历史快照相关流程；`usePreviewKeyboardShortcuts.ts` 处理快捷键；`useScrollSync.ts` 和 `useScrollSyncHelpers.ts` 处理预览与编辑、或不同视图之间的滚动同步；`useTabOverflow.ts` 处理 tab 宽度溢出；`useThemeDetection.ts` 处理主题感知。

`theme` 放编辑器和 Markdown 渲染主题配置，包括 `codeEditorConfig.ts`、`codeEditorTheme.ts`、`languageLoader.ts`、`markdownHighlightStyle.ts`、`markdownTheme.ts`。它不只是视觉样式目录，也包含代码语言加载与高亮策略。

## 关键入口

目录自身的聚合入口是 `packages/desktop/src/renderer/pages/conversation/Preview/index.ts`，外部通常从这里导入 preview context 或组件能力。真正的状态入口在 `packages/desktop/src/renderer/pages/conversation/Preview/context/PreviewContext.tsx`，因为邻近模块直接引用 `usePreviewContext` 来打开或关闭预览。

UI 主入口是 `packages/desktop/src/renderer/pages/conversation/Preview/components/PreviewPanel/PreviewPanel.tsx`。如果要理解“预览面板长什么样、tab 如何组织、toolbar 和 viewer 如何装配”，应该从它开始，而不是从某个具体 viewer 开始。

类型和常量入口是 `packages/desktop/src/renderer/pages/conversation/Preview/types.ts`、`packages/desktop/src/renderer/pages/conversation/Preview/constants.ts`。内容类型本身还会关联 `packages/desktop/src/common/types/office/preview.ts` 中的 `PreviewContentType`、`PreviewHistoryTarget`、`PreviewSnapshotInfo`。

外部启动入口主要在 `packages/desktop/src/renderer/hooks/file/usePreviewLauncher.ts`。它负责把文件路径、文件名、fallback 内容、workspace、contentType 等整理成 `openPreview` 需要的输入，并处理大文本截断、二进制类型、Diff 内容、错误分类等逻辑。自动打开 Office 文件的入口在 `packages/desktop/src/renderer/hooks/file/useAutoPreviewOfficeFiles.ts`。

## 主流程位置

典型手动预览流程是：外部组件触发预览，例如 Diff 组件、Markdown Mermaid 块或文件相关 UI 调用 `usePreviewLauncher`；`usePreviewLauncher` 根据 `PreviewContentType` 读取或准备内容，必要时调用后端/桥接能力；准备完成后调用 `usePreviewContext().openPreview(...)`；`PreviewContext` 把内容加入或定位到已有 tab；`PreviewPanel` 渲染 tab、toolbar、历史菜单、上下文菜单；最后按类型分发到 `components/viewers` 或 `components/editors` 中的具体实现。

自动 Office 预览流程不同：`useAutoPreviewOfficeFiles` 监听当前 workspace 里的文件新增事件，结合 `useAutoPreviewOfficeFilesEnabled` 的设置开关，过滤 Word、Excel、PowerPoint 等文件，然后通过 `findPreviewTab` 避免重复打开，再调用 `openPreview` 创建对应 Office 类型的预览 tab。具体 Office 文件内容或转换能力不在本目录内完成，邻近证据显示桥接层在 `packages/desktop/src/common/adapter/ipcBridge.ts` 中有 `pptPreview`、`wordPreview`、`excelPreview` 以及 preview panel/history 相关接口。

历史流程集中在 `hooks/usePreviewHistory.ts`、`components/PreviewPanel/PreviewHistoryDropdown.tsx` 和 `PreviewContext` 的交互中。根据当前片段推断，历史快照的服务端或主进程桥接调用由 `ipcBridge.ts` 的 `/api/preview-history/*` 路由承担，本目录负责展示历史、选择快照、保存或恢复内容。

## 推荐阅读顺序

第一步先看 `README.cn.md` 或 `README.en.md`，建立模块意图和术语。第二步看 `types.ts`、`constants.ts` 和 `common/types/office/preview.ts`，先弄清楚支持哪些 `PreviewContentType`、tab 元数据和历史目标。第三步看 `context/PreviewContext.tsx`，重点找 `openPreview`、`closePreview`、`findPreviewTab` 这类动作，因为它们连接外部调用和内部面板状态。

第四步读 `components/PreviewPanel/PreviewPanel.tsx`，再顺着它看 `PreviewToolbar.tsx`、`PreviewTabs.tsx`、`PreviewHistoryDropdown.tsx`。第五步按需要读具体 viewer：想理解 Markdown/HTML/代码就看 `MarkdownViewer.tsx`、`HTMLViewer.tsx`、`HTMLRenderer.tsx` 和 `editors`；想理解文件预览就看 `PDFViewer.tsx`、`ImageViewer.tsx`、`DiffViewer.tsx` 和 Office 相关 viewer。最后再看 `hooks` 与 `theme`，它们解释快捷键、滚动同步、tab 溢出、主题和高亮这些横切行为。

## 常见误区

不要把 `Preview` 目录理解成“文件预览后端”。它位于 `renderer/pages/conversation`，职责是会话页 UI 和状态编排；文件读取、Office 转换、preview history API 等能力来自外部 hook、adapter 或后端路由。

不要从某个 `viewer` 反推全部流程。`viewers` 只是最终渲染层，预览是否打开、是否复用 tab、标题如何来、是否 editable、历史如何保存，核心仍在 `PreviewContext`、`PreviewPanel` 和外部启动 hook。

不要忽略 `PreviewToolbarExtrasContext.tsx`。工具栏按钮不一定全部写死在 `PreviewToolbar.tsx`，具体 viewer/editor 可能通过 extras context 注入与当前内容类型相关的操作。

不要把 `renderers` 和 `viewers` 混为一谈。`viewers` 是面向内容类型的完整查看组件；`renderers` 更像某类内容内部复用的渲染基础设施，例如 HTML 渲染、选区工具条和检查脚本。

不要硬编码用户可见文字或颜色。该项目约定用户文本走 i18n，样式优先使用 UnoCSS 语义 token 或 CSS 变量；预览模块相关文案能在 `renderer/services/i18n/locales/*/preview.json` 找到对应上下文。
