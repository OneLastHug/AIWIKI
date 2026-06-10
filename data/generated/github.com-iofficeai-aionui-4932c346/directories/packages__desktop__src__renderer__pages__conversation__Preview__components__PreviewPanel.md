# 目录：packages/desktop/src/renderer/pages/conversation/Preview/components/PreviewPanel
## 它负责什么
这个目录是 `Preview` 模块里“预览面板”这一层的组件集合，核心职责是把预览页的顶栏、标签页、右键菜单、关闭确认、历史下拉等交互拼成一个完整面板。根据当前片段推断，它不是渲染具体内容的底层实现，而是负责“怎么组织预览、怎么切换、怎么保存、怎么关闭”的外壳层；真正的内容渲染器分布在同级的 `viewers`、`editors`、`renderers` 目录里。

从结构上看，这个目录更像一个聚合入口：`PreviewPanel.tsx` 负责主流程，`index.ts` 负责对外导出，其他文件则是面板内部的功能拆分。它服务的对象是整个 conversation 页面的文档预览场景，支持 Markdown、HTML、code、diff、PDF、图片、Office 文档、URL 等多种预览类型，但这里本身不关心每种格式的细节，只关心面板级交互。

## 直接子目录地图
这个目录下面没有子目录，一级内容全部是文件。可按职责看成三类：

1. 面板主骨架：`PreviewPanel.tsx`
2. 面板辅助交互：`PreviewTabs.tsx`、`PreviewToolbar.tsx`、`PreviewContextMenu.tsx`、`PreviewConfirmModals.tsx`、`PreviewHistoryDropdown.tsx`
3. 样式与工具：`preview.css`、`previewToolbarUtils.ts`
4. 对外聚合：`index.ts`

换句话说，这里是“一个面板目录”，不是“一个模块树”。它的深层子系统并不在这个目录里，而在同级的 `context`、`hooks`、`viewers`、`editors`、`renderers` 中。

## 关键入口
最重要的入口是 `PreviewPanel.tsx`。它是面板的主组件，直接从 `usePreviewContext()` 读取当前打开状态、tabs、activeTab、关闭/切换/保存等动作，再结合 `useLayoutContext()`、`useResizableSplit()`、`usePreviewHistory()`、`useScrollSync()`、`useTabOverflow()`、`useThemeDetection()` 等 hooks 组装整套交互。

`index.ts` 是该目录的统一出口，只做 re-export，不承载业务逻辑。`PreviewToolbar.tsx` 是顶部操作区入口，负责 source/preview 切换、分屏、下载、关闭、历史入口等按钮。`PreviewTabs.tsx` 则是 tab 栏入口，和 active tab 切换、关闭、右键菜单联动最紧密。

如果只想快速理解这个目录，优先看 `PreviewPanel.tsx`，然后看 `index.ts`、`PreviewToolbar.tsx`、`PreviewTabs.tsx`。

## 主流程位置
主流程几乎都收敛在 `PreviewPanel.tsx` 里：

1. 初始化阶段：从 `usePreviewContext()` 拿到当前预览状态，从 `useLayoutContext()` 拿到布局环境。
2. 视图状态管理：本地维护 `viewMode`、`isSplitScreenEnabled`、`inspectMode`、`toolbarExtras`、关闭确认态、右键菜单态。
3. 文件切换回退：当 `activeTabId` 或当前文件标识变化时，把 `viewMode` 重置为 `preview`，避免上一个文件的 source 状态串到下一个文件。
4. 分屏与滚动同步：通过 `useResizableSplit()` 管理编辑区和预览区比例，通过 `useScrollSync()` 在双栏模式下同步滚动。
5. 历史与快照：`usePreviewHistory()` 提供历史版本、保存快照、刷新历史、错误提示等能力。
6. 关闭与批量关闭：对单个 tab 提供未保存确认；对左侧、右侧、其他 tabs 提供批量关闭。
7. HTML 审核联动：选中元素后通过 `addDomSnippet()` 把 DOM 片段送回上下文。
8. 最终渲染：把 `PreviewTabs`、`PreviewToolbar`、`PreviewContextMenu`、`PreviewConfirmModals`、`PreviewHistoryDropdown` 和具体 viewer/editor 组合成完整 UI。

从依赖关系看，这里是“编排层”，不是“算法层”。真正规则判断分散在 `previewToolbarUtils.ts` 和各个 hook 中，UI 组合与状态流转才是这个目录的重点。

## 推荐阅读顺序
1. 先看 `index.ts`，确认这个目录对外暴露了什么。
2. 再看 `PreviewPanel.tsx`，把主流程和状态流先串起来。
3. 接着看 `PreviewToolbar.tsx`、`PreviewTabs.tsx`、`PreviewContextMenu.tsx`、`PreviewConfirmModals.tsx`，理解面板交互拆分。
4. 然后看 `previewToolbarUtils.ts`，补齐工具栏按钮显示规则。
5. 最后再回到父级 `context/PreviewContext.tsx` 和 `hooks/index.ts`，把数据来源与行为来源补全。

## 常见误区
1. 把这个目录当成整个预览系统。实际上它只是面板层，真正的内容渲染在同级 `viewers`、`editors`、`renderers`。
2. 以为 `index.ts` 有业务逻辑。它只是导出入口，方便上层统一引用。
3. 把历史快照功能当成已完整开放的 UI。根据当前片段推断，底层历史逻辑存在，但 `PreviewToolbar.tsx` 里 `SHOW_SNAPSHOT_HISTORY = false`，说明入口暂时被隐藏。
4. 忽略“文件切换会重置视图模式”这个细节。这里不是简单保存 UI 状态，而是按当前文件身份防止 source/preview 状态串档。
5. 只看 toolbar 不看 context。这个目录的大部分行为都依赖 `usePreviewContext()` 提供的 tab、保存、关闭、DOM 片段等能力，离开上下文很难理解完整流程。
