# 目录：packages/tui/src

## 它负责什么

`packages/tui/src` 是 `@earendil-works/pi-tui` 包的源码目录，定位是一个终端 UI 基础库。它不直接承载业务里的“对话代理”逻辑，而是提供在终端里构建交互界面的底层能力：组件渲染、键盘输入解析、焦点管理、覆盖层、文本编辑器、列表选择、Markdown 展示、终端图片协议、ANSI 宽度计算和差量刷新。

从 `packages/tui/package.json` 看，这个包的描述是“Terminal User Interface library with differential rendering for efficient text-based applications”，入口产物是 `dist/index.js`，类型入口是 `dist/index.d.ts`。源码层面的公共 API 汇总在 `packages/tui/src/index.ts`，它把核心类、组件、键盘工具、终端抽象、图片渲染工具和文本工具统一导出，供上层包调用。

这个目录可以理解为仓库里的“终端界面运行时”。上层应用只需要组合 `TUI`、`Container`、`Editor`、`SelectList`、`Markdown`、`Loader` 等对象，就能得到可交互的命令行界面；底层终端状态、输入事件、光标、刷新和宽度处理由这里托底。

## 直接子目录地图

`packages/tui/src` 下面只有一个直接子目录：`packages/tui/src/components`。它收纳可复用 UI 组件，包含文本、盒子、输入框、编辑器、列表、加载状态、Markdown、图片和间隔组件等。这里的组件共同遵循 `Component` 接口：核心方法是 `render(width: number): string[]`，可选方法是 `handleInput(data: string): void`，并且需要支持 `invalidate()` 来清理渲染缓存或触发重新计算。

根目录下的文件则更偏底层和横向能力：`tui.ts` 是 TUI 容器与渲染主控；`terminal.ts` 抽象真实终端并处理 raw mode、resize、Kitty 键盘协议、bracketed paste 等；`keys.ts`、`keybindings.ts` 处理按键解析和快捷键配置；`stdin-buffer.ts` 负责把批量 stdin 输入拆成独立序列；`utils.ts` 放 ANSI、宽度、换行、截断等公共文本工具；`terminal-image.ts` 处理 Kitty、iTerm2 等终端图片能力；`autocomplete.ts`、`fuzzy.ts` 支撑补全和模糊匹配；`kill-ring.ts`、`undo-stack.ts`、`word-navigation.ts` 服务编辑器行为。

## 关键入口

最外部的学习入口是 `packages/tui/src/index.ts`。它不是运行主程序，而是公共导出清单。读它可以快速知道这个包对外暴露了哪些能力：`TUI`、`Container`、`Component`、`Focusable`、`ProcessTerminal`、`Editor`、`Input`、`Markdown`、`SelectList`、`SettingsList`、`Image`、`Loader`、`CancellableLoader`、`KeybindingsManager`、`parseKey`、`matchesKey`、`renderImage`、`visibleWidth`、`wrapTextWithAnsi` 等。

运行时核心入口是 `packages/tui/src/tui.ts`。其中 `Component` 定义组件契约，`Container` 提供纵向组合子组件的基础容器，`TUI` 继承 `Container` 并负责启动终端、接收输入、管理焦点、显示 overlay、请求重绘和做差量渲染。`CURSOR_MARKER` 是一个重要细节：可聚焦组件在渲染输出中标记光标位置，`TUI` 再把硬件光标移动到对应位置，用于 IME 候选窗等真实终端体验。

终端适配入口是 `packages/tui/src/terminal.ts`。`Terminal` 是接口，`ProcessTerminal` 是使用 `process.stdin/stdout` 的真实实现。它处理 raw mode、bracketed paste、窗口 resize、Windows VT 输入、Kitty 键盘协议协商、输入拆包、进度指示和退出时恢复终端状态。

组件入口集中在 `packages/tui/src/components`。其中 `editor.ts` 是最复杂的交互组件，负责多行编辑、光标移动、自动补全、粘贴标记、撤销、kill ring、按键处理和软换行；`input.ts` 更像单输入框；`select-list.ts` 和 `settings-list.ts` 是菜单与设置项选择；`markdown.ts` 是文本渲染；`image.ts` 使用终端图片能力；`loader.ts` 与 `cancellable-loader.ts` 提供加载反馈。

## 主流程位置

主流程大致从上层创建 `ProcessTerminal` 和 `TUI` 开始。`TUI.start()` 调用 `terminal.start(onInput, onResize)`，终端进入 raw mode，启用 bracketed paste，注册 resize，并尝试协商 Kitty 键盘协议。随后 stdin 进入 `StdinBuffer`，被拆分为更小的按键、转义序列或 paste 事件，再交给 `TUI` 的输入处理。

输入分发由焦点决定。`TUI.setFocus()` 维护当前焦点组件；如果 overlay 捕获焦点，则输入优先进入 overlay；否则进入普通 focused component。组件收到 `handleInput()` 后更新自身状态，例如 `Editor` 修改文本、游标或补全列表，`SelectList` 修改当前选中项。组件一般会通过外部调用或状态变化触发 `TUI.requestRender()`。

渲染主线在 `packages/tui/src/tui.ts`。`Container.render(width)` 顺序收集子组件行；`TUI` 在此基础上叠加 overlay、处理光标标记、裁剪终端高度，并与上一帧做差量比较，只写出需要变化的行。这里还会处理终端图片行中的 Kitty image id，避免旧图片残留。根据当前片段推断，差量渲染是这个包性能设计的核心，依据是文件头注释“Minimal TUI implementation with differential rendering”以及 `TUI` 对 previous frame、cursor、terminal clear/write 的集中管理。

编辑器主流程在 `packages/tui/src/components/editor.ts`：文本状态由多行数组和光标坐标维护；`wordWrapLine()` 负责根据终端宽度做软换行；`handleInput()` 解析按键并调用移动、删除、插入、补全、撤销等内部逻辑；渲染时再输出带边框、补全列表或光标标记的行。

## 推荐阅读顺序

建议先读 `packages/tui/src/index.ts`，建立公共 API 地图，确认哪些能力是给外部使用的。第二步读 `packages/tui/src/tui.ts`，重点看 `Component`、`Container`、`TUI`、`setFocus()`、`showOverlay()`、`start()`、`stop()`、`requestRender()`，理解整个终端 UI 的生命周期。

第三步读 `packages/tui/src/terminal.ts`，把真实终端输入输出、raw mode、paste、resize、Kitty 协议和 `StdinBuffer` 串起来。第四步读 `packages/tui/src/components/editor.ts`、`packages/tui/src/components/input.ts`、`packages/tui/src/components/select-list.ts`，它们代表主要交互组件。最后补读 `keys.ts`、`keybindings.ts`、`utils.ts`、`terminal-image.ts`，这些是理解跨平台按键、宽字符、ANSI 文本和图片渲染问题的支撑层。

如果只想做地图式了解，可以按 `index.ts`、`tui.ts`、`terminal.ts`、`components/editor.ts` 的顺序阅读；如果要调 UI 行为，再进入具体组件和工具文件。

## 常见误区

不要把 `packages/tui/src` 当成 CLI 业务入口。它是终端 UI 库，真正的产品命令、模型调用或 agent 流程在其他包中，当前目录只负责“如何在终端里显示和交互”。

不要认为组件直接写 stdout。正常路径是组件返回字符串行，由 `TUI` 统一合成、裁剪、定位光标并差量写入终端；直接绕过 `TUI` 写终端会破坏帧状态。

不要只看 `components` 而忽略 `terminal.ts` 和 `keys.ts`。很多看似组件的问题，实际来自输入序列拆包、Kitty 协议、Apple Terminal 的 Shift+Enter 兼容、Windows VT 输入或 bracketed paste。

不要把 `visibleWidth` 等同于 `string.length`。终端 UI 中 ANSI escape、宽字符、emoji、CJK 字符都会影响列宽，相关逻辑集中在 `utils.ts`，编辑器换行和文本截断都依赖这些工具。

不要把 overlay 理解成普通子组件。`showOverlay()` 有独立的栈、焦点恢复、隐藏和捕获策略；调试弹窗、补全或选择器时，应同时检查 overlay 选项和当前 focused component。
