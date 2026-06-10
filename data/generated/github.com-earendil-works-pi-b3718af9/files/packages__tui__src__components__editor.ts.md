# 文件：`packages/tui/src/components/editor.ts`

## 一句话定位
这是 TUI 里一个带状态的多行文本编辑器组件，负责接收键盘输入、维护光标和文本状态、做换行布局与渲染，并把提交、修改、自动补全和历史导航这些交互串起来。

## 它暴露/定义了什么
这个文件主要定义了 `Editor` 类，以及少量支撑编辑器行为的工具函数和类型。对外最重要的是 `Editor` 本身：它实现了 `Component` 和 `Focusable`，可以被 TUI 容器直接渲染和聚焦。它还暴露了编辑器的配置面，如 `EditorTheme`、`EditorOptions`，以及 `wordWrapLine()` 这种用于布局的辅助函数。内部还定义了粘贴标记识别、分词包装、自动补全触发规则、历史栈、kill ring、undo 栈等编辑器子系统。

## 谁调用它
根据当前片段推断，它不是独立工具，而是被 `packages/tui/src/tui.ts` 这类界面编排层持有并调用：TUI 会反复调用它的 `render(width)` 来绘制内容，也会把按键事件转发给它的输入处理逻辑。文件里的 `render()`、`handleInput()`、`getText()`、`setText()` 这些方法都说明它是“输入区组件”而不是纯数据结构。另一个直接依赖是 `SelectList`，编辑器在自动补全激活时会把候选项列表嵌进自己的渲染结果里。

## 它调用谁
它调用的外部模块比较集中：`getKeybindings()` 负责把原始按键数据映射成语义动作；`decodePrintableKey()`、`matchesKey()` 负责识别可打印字符和特殊组合键；`KillRing`、`UndoStack` 负责剪切/粘贴式编辑和撤销；`getGraphemeSegmenter()`、`getWordSegmenter()`、`visibleWidth()`、`truncateToWidth()` 负责按终端宽度做可见布局；`findWordBackward()`、`findWordForward()` 负责单词级移动；`SelectList` 负责自动补全候选菜单。它还通过 `TUI.requestRender()` 触发重绘，通过 `onChange`、`onSubmit` 回调把结果交回上层。

## 核心流程
核心路径可以概括成“输入 - 变更 - 布局 - 渲染 - 回调”。`handleInput()` 先按键绑定分发：撤销、删除、移动、换行、提交、历史上下切换、跳字符、Tab 补全等都在这里进入不同分支。编辑动作会修改 `state.lines`、`cursorLine`、`cursorCol`，同时维护 `history`、`undoStack`、`killRing`、`pasteBuffer` 等辅助状态。`render()` 再基于当前终端宽度把逻辑行拆成视觉行：先做内容宽度和滚动计算，再调用 `layoutText()` 与 `wordWrapLine()`，最后插入边框、滚动提示、光标高亮和自动补全列表。提交时则把文本交给 `onSubmit`，并在成功后把内容写入历史栈。

## 关键函数的高层作用
`wordWrapLine()` 负责按词优先、按字素回退地拆分一行文本，避免终端宽度不足时把可读性弄坏。`segmentWithMarkers()` 和 `isPasteMarker()` 是一个比较特殊的设计点：它把粘贴标记当成原子段，保证光标移动和删除不会把“逻辑粘贴块”拆碎。`layoutText()` 把逻辑行映射成屏幕行，并精确决定光标落在哪个折行片段里。`navigateHistory()` 处理上下箭头进入历史浏览、退出历史浏览时恢复草稿。`setTextInternal()` 是一个内部写入口，用来在不扰乱历史状态的前提下替换文本。`setAutocompleteProvider()`、`handleTabCompletion()`、`cancelAutocomplete()` 则是补全生命周期的控制面。

## 修改风险
这个文件的风险很集中，改动时最容易破坏的是“光标位置、换行、提交语义”三件事。任何涉及 `segmentWithMarkers()`、`wordWrapLine()` 或 `layoutText()` 的改动，都可能让粘贴标记被拆开、宽字符宽度算错、折行后光标漂移。`handleInput()` 的分支很多，新增或调整快捷键时容易和已有键位冲突，尤其是 Enter、Tab、Shift+Enter、撤销、补全确认这些高频动作。历史浏览、undo、autocomplete 三套状态彼此耦合，改一处可能影响退出历史时是否恢复草稿、补全确认后是否继续提交、撤销是否回到正确文本。最后，`render()` 还承担硬件光标标记和滚动提示，改动它会直接影响 IME 候选窗定位和长文本可读性。
