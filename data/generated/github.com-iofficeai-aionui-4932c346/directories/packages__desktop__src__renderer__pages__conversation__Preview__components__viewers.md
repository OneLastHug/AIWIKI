# 目录：packages/desktop/src/renderer/pages/conversation/Preview/components/viewers

## 它负责什么

`viewers` 是会话 `Preview` 面板里的“具体内容查看器”集合。它不负责决定预览面板何时打开、当前选中了哪个文件、工具栏整体如何布局；它更像是一组按内容类型分流后的终端渲染组件：上层把 `file_path`、`content`、`workspace`、文件名或预览模式传进来，这里根据文件类型完成实际显示。

从当前片段看，这个目录覆盖的预览类型比较完整：图片、Markdown、HTML、PDF、Office 文档、PPT、Excel、Diff、普通 URL/web 页面等。它们共同服务于 `packages/desktop/src/renderer/pages/conversation/Preview` 这一块会话侧边预览能力，尤其是对本地文件、生成内容、办公文档和网页嵌入的展示。

这里的组件普遍属于 renderer 进程 UI 层。涉及本地文件读取、系统打开文件、图片转 base64、Office 预览服务启动等能力时，不直接使用 Node.js API，而是通过 `ipcBridge` 或已有平台工具间接访问主进程能力。比如 `ImageViewer.tsx` 通过 `ipcBridge.fs.getImageBase64.invoke` 读取图片数据，`PDFViewer.tsx` 通过 `ipcBridge.shell.openFile.invoke` 调系统应用打开文件。

## 直接子目录地图

这个目录当前没有直接子目录，全部内容以 viewer 组件文件平铺在 `viewers` 下：

`DiffViewer.tsx`、`ExcelViewer.tsx`、`HTMLViewer.tsx`、`ImageViewer.tsx`、`MarkdownViewer.tsx`、`OfficeDocViewer.tsx`、`OfficeWatchViewer.tsx`、`PDFViewer.tsx`、`PptViewer.tsx`、`URLViewer.tsx`、`index.ts`。

按职责可以把它们理解成三类：

第一类是静态内容查看器：`ImageViewer.tsx`、`MarkdownViewer.tsx`、`HTMLViewer.tsx`、`PDFViewer.tsx`、`DiffViewer.tsx`。它们主要把已有的 `content` 或 `file_path` 转成可视化 UI。

第二类是 Office 相关查看器：`OfficeDocViewer.tsx`、`OfficeWatchViewer.tsx`、`PptViewer.tsx`、`ExcelViewer.tsx`。其中 `OfficeWatchViewer.tsx` 更像公共底座，抽象了 `ppt`、`word`、`excel` 这类文档的预览代理、启动状态、错误码和 iframe/webview 承载逻辑；`PptViewer.tsx`、`ExcelViewer.tsx`、`OfficeDocViewer.tsx` 根据当前片段推断是面向不同文档类型的薄封装或类型入口。

第三类是外部页面承载：`URLViewer.tsx` 使用 `WebviewHost` 在应用内预览网页类内容，适合会话预览面板中的 URL 资源。

## 关键入口

目录级入口是 `index.ts`。上层代码通常不应该直接理解每个 viewer 的内部实现，而是通过这里导出的组件建立依赖。学习时先看 `index.ts` 可以知道对外暴露了哪些 viewer，以及命名是否和文件名一一对应。

实际运行入口不在这个目录里，而在 `Preview` 面板更上层的类型分发组件中。根据当前片段推断，`packages/desktop/src/renderer/pages/conversation/Preview` 下面会有一个负责接收预览对象、判断 mime/type/extension、再选择 `MarkdownViewer`、`ImageViewer`、`PDFViewer` 等组件的主组件。依据是 `viewers` 文件自身只定义具体渲染器，没有看到统一的类型判断中心；同时 `PDFViewer.tsx` 引用了同级上层的 `../../previewUrls`，`MarkdownViewer.tsx` 引用了兄弟目录 `../renderers/SelectionToolbar`，说明它们被嵌在更大的 `Preview` 体系里使用。

几个值得优先识别的单组件入口：

`MarkdownViewer.tsx` 的默认导出是 `MarkdownPreview`。它支持 `source` 和 `preview` 视图模式，使用 `Streamdown` 渲染 Markdown，并处理 LaTeX 分隔符、选中文本工具栏、相对图片路径解析和本地图片 base64 加载。

`ImageViewer.tsx` 的默认导出是 `ImagePreview`。它的核心流程是优先使用传入的 `content`，否则根据 `file_path` 调 IPC 加载图片数据，并维护 loading/error 状态。

`PDFViewer.tsx` 的默认导出是 `PDFPreview`。它通过 `buildPdfSrc` 构造 PDF 资源地址，用 Electron `webview` 承载本地或内容型 PDF，并通过 `PreviewToolbarExtrasContext` 在需要时把“系统应用打开”等按钮挂到上层工具栏区域。

`OfficeWatchViewer.tsx` 是 Office 类预览的关键底座。它定义了 `DocType`、错误码、代理路径、iframe 标题、i18n key、安装提示和 Office 预览启动相关状态。阅读 Office/PPT/Excel 预览时应把它当作核心实现看。

`HTMLViewer.tsx` 是交互较重的查看器。它不仅渲染 HTML，还包含编辑切换、元素检查、复制、下载等操作逻辑，因此它既是 viewer，也是一个小型 HTML 预览工作台。

## 主流程位置

主流程可以按“上层分发 -> viewer 渲染 -> 必要时跨进程取资源 -> 状态反馈/工具栏扩展”理解。

第一步，上层 `Preview` 区域拿到预览目标。目标可能来自会话中的附件、生成文件、链接或工作区文件。上层根据文件类型选择 viewer。这个分发点不在 `viewers` 目录内；本目录只承接已经选定类型后的渲染工作。

第二步，viewer 组件读取统一形态的输入。常见入参包括 `file_path`、`content`、`file_name`、`workspace`、`hideToolbar`、`viewMode`、`containerRef` 等。不是每个 viewer 都需要全部字段：Markdown 更依赖 `content` 和 `file_path` 的目录信息，图片和 PDF 更依赖 `file_path`，URL viewer 则主要依赖 `url`。

第三步，组件内部选择渲染策略。纯文本或 Markdown 走 React 渲染；HTML 可能构造 iframe 或沙箱预览区域；PDF 使用 Electron webview；URL 和部分 Office 预览使用 `WebviewHost` 或 iframe；本地图片通过 IPC 转成可显示的数据地址。

第四步，处理预览状态。这里的 viewer 普遍有 loading、error、empty/path missing 等状态。错误文案使用 i18n key，例如 `preview.loading`、`preview.pdf.loadFailed`、`preview.openInSystemFailed` 等，而不是硬编码展示文本。学习这块时要注意：这些组件是用户可见界面，新增文案需要同步 i18n。

第五步，可选地向上层工具栏注册扩展操作。`PDFViewer.tsx` 使用 `PreviewToolbarExtrasContext`，说明部分 viewer 可以把自身操作按钮挂到预览面板公共工具栏，而不是只在自身内容区内渲染按钮。这个模式适合“打开系统应用”“下载”“切换模式”等和当前预览对象相关的操作。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/renderer/pages/conversation/Preview/components/viewers/index.ts`，确认目录对外暴露的组件边界。

2. 再回到 `packages/desktop/src/renderer/pages/conversation/Preview` 的上层组件，寻找导入 `viewers` 的地方，理解文件类型如何被分发到具体 viewer。这个分发点是理解主流程的关键，不在当前目录内部。

3. 阅读 `MarkdownViewer.tsx`。它覆盖了内容渲染、主题、选区工具栏、相对资源解析、IPC 图片加载等多种典型模式，是这个目录里最能体现 renderer 侧预览复杂度的文件之一。

4. 阅读 `ImageViewer.tsx` 和 `PDFViewer.tsx`。这两个文件能帮助理解本地文件预览如何处理 `file_path`、loading/error、IPC 以及 Electron `webview`。

5. 阅读 `OfficeWatchViewer.tsx`，再看 `OfficeDocViewer.tsx`、`PptViewer.tsx`、`ExcelViewer.tsx`。Office 预览有自己的代理、安装、错误码和文档类型映射，应该先掌握公共底座，再看具体类型封装。

6. 最后看 `HTMLViewer.tsx`、`DiffViewer.tsx`、`URLViewer.tsx`。它们分别代表交互式 HTML 预览、差异内容展示和网页承载，可作为特定能力补充阅读。

## 常见误区

不要把 `viewers` 当成预览系统的总入口。这里是“被选中的具体渲染器集合”，真正决定使用哪个 viewer 的逻辑应在 `Preview` 上层查找。

不要在 viewer 内直接访问 Node.js 文件系统。当前项目区分 renderer 和 main 进程，本目录位于 renderer 侧，读取本地文件、打开系统应用、启动 Office 相关服务等能力应通过 `ipcBridge`、`WebviewHost` 或平台工具完成。

不要忽略 `workspace`。图片和 Markdown 内部图片解析都可能依赖当前工作区上下文；只传 `file_path` 而不传 `workspace`，在沙箱、远程工作区或多工作区场景下可能出现路径解析错误。

不要把 `content` 和 `file_path` 视为完全等价。某些 viewer 支持直接渲染 `content`，某些 viewer 更依赖磁盘路径；PDF、图片、Office 文档这类二进制或容器格式通常需要更谨慎地处理资源来源。

不要在新增用户可见文字时硬编码中文或英文。这里已有大量 `t('preview...')` 形式的 i18n 使用，新增错误提示、按钮标题、状态文案都应沿用 i18n。

不要把 Office 相关 viewer 逐个孤立理解。`OfficeWatchViewer.tsx` 承担了跨 `word`、`ppt`、`excel` 的公共预览流程，具体 viewer 很可能只是类型化入口；排查 Office 预览问题时优先看公共底座。

不要在文档中输出真实外部服务地址。代码里可能存在安装页、代理地址或网页地址常量，学习文档只需说明其角色即可，避免展开真实网址。
