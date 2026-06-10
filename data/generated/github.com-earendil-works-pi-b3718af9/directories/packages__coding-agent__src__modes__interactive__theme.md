# 子系统：packages/coding-agent/src/modes/interactive/theme

## 解决什么问题

这个目录负责把“主题”从静态配色数据变成 interactive 模式可直接消费的渲染能力。它解决两类问题：一是让 TUI 的颜色、边框、Markdown、diff、语法高亮等视觉元素统一由同一套主题定义驱动；二是让主题既能内置提供 `dark.json`、`light.json`，又能支持用户自定义主题文件，并在运行时校验、加载、切换。

根据当前片段推断，这里不仅是配色表，还承担“主题注册与解析层”的职责，即把 JSON 主题映射成 `@earendil-works/pi-tui` 需要的 `EditorTheme`、`MarkdownTheme`、`SelectListTheme`、`SettingsListTheme` 等运行期对象。

## 相关目录和文件

核心文件只有四个：`theme.ts`、`theme-schema.json`、`dark.json`、`light.json`。其中 `theme-schema.json` 定义主题文件结构，`dark.json`、`light.json` 是内置主题样例，`theme.ts` 是加载、校验、解析、转换和对外导出的主入口。

上层接入点主要在 `packages/coding-agent/src/modes/interactive/interactive-mode.ts`，它会从资源加载器注册主题。下游使用方分布在 `packages/coding-agent/src/modes/interactive/components/`，例如 `assistant-message.ts`、`login-dialog.ts`、`session-selector.ts`、`oauth-selector.ts`、`trust-selector.ts` 等都直接引用 `theme.ts` 导出的 `theme`。`custom-editor.ts` 还会接收 `EditorTheme`，说明主题层也负责编辑器配色的桥接。

## 核心对象

`theme.ts` 里最重要的是三组对象：`ThemeJsonSchema`、`ThemeColor` / `ThemeBg` 类型，以及实际的主题运行时对象。`ThemeJsonSchema` 用 TypeBox 定义 JSON 结构，覆盖 `colors` 中几乎所有界面语义色，例如 `accent`、`borderAccent`、`toolSuccessBg`、`syntaxKeyword`、`thinkingHigh`、`bashMode` 等。

`light.json` 和 `dark.json` 用 `vars` 做颜色别名复用，再由 `colors` 把语义色映射成具体值。这个设计能减少重复，也让“语义名”稳定、具体色值可替换。`theme.ts` 里还引入了 `highlight`、`supportsLanguage`、`watchWithErrorHandler`、`closeWatcher`，说明它同时承担语法高亮和文件监听。`getCapabilities` 来自 `@earendil-works/pi-tui`，表明主题转换会根据终端能力在 truecolor 和 256-color 之间降级。

## 运行流程

启动 interactive 模式后，`interactive-mode.ts` 会从资源加载器注册主题，随后各组件通过 `theme.fg(...)`、`theme.bg(...)`、`theme.bold(...)`、`theme.italic(...)` 之类的接口输出样式化文本。`theme.ts` 先读取内置主题目录和自定义主题目录，再用 `Compile(ThemeJsonSchema)` 校验 JSON，保证字段完整且颜色值合法。

随后它会解析 `vars`，把字符串变量名、十六进制颜色和 0-255 的 256 色索引统一归一化；在终端只支持 256 色时，还会把 truecolor 近似映射到最接近的色块。根据当前片段推断，文件还会把主题数据转换成多个细分主题对象，例如 Markdown 主题和编辑器主题，并把它们分发给对话消息、列表选择器、登录面板、差异展示和代码块高亮等控件。

## 上下游依赖

上游依赖主要有三类。第一类是配置与资源路径：`getThemesDir`、`getCustomThemesDir` 决定内置主题和用户主题的位置。第二类是终端 UI 库：`@earendil-works/pi-tui` 提供主题能力接口和各类主题类型。第三类是辅助能力：`fs-watch` 负责监听主题文件变化，`syntax-highlight.ts` 负责代码高亮支持判断与着色。

下游则是 interactive 模式的所有视觉组件。它们不直接操作 JSON，而是依赖 `theme.ts` 暴露的统一样式 API，因此这个目录实际上是整个交互界面的视觉枢纽。

## 修改时最容易踩的坑

第一，`ThemeJsonSchema`、`theme-schema.json`、`ThemeColor` 三者必须同步。新增或删除颜色键时，只改一处会造成校验通过不了或类型不一致。第二，`vars` 既支持变量名也支持直接值，改解析逻辑时要保留别名递归和默认值语义。第三，终端能力降级不能破坏语义色，尤其是高亮、错误、选中态和 diff 颜色，否则交互界面会失去层次。

第四，`interactive-mode.ts` 和各组件都在直接引用 `theme.ts`，因此改导出名或接口会有较大连锁影响。第五，watcher 生命周期要和面板生命周期一致，避免热更新后留下悬挂监听。第六，Markdown 和代码高亮色不是纯装饰，它们承载可读性，修改时要特别检查深色、浅色两套主题的对比度。

## 推荐阅读顺序

先看 `theme-schema.json`，理解完整字段集合；再看 `dark.json`、`light.json`，建立语义色到实际色值的直觉；然后读 `theme.ts`，重点关注 schema 校验、颜色解析、终端降级和导出对象；最后回到 `interactive-mode.ts` 和 `components/` 下几个直接使用 `theme` 的文件，理解这个子系统如何影响实际界面。
