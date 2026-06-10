# 文件：packages/tui/src/tui.ts

## 一句话定位

`packages/tui/src/tui.ts` 是 `@earendil-works/pi-tui` 的核心调度层：它定义终端 UI 的组件协议，并由 `TUI` 类统一管理组件树渲染、差分刷新、输入分发、焦点、硬件光标、图片资源和浮层 overlay。

## 它暴露/定义了什么

该文件主要暴露三类内容。

第一类是组件契约：`Component` 要求组件实现 `render(width)` 和 `invalidate()`，可选实现 `handleInput(data)`，并可声明 `wantsKeyRelease`。`Focusable` 表示组件可以获得焦点并配合硬件光标定位；`isFocusable()` 是对应类型守卫；`CURSOR_MARKER` 是组件在渲染文本里标记真实输入光标位置的零宽控制序列。

第二类是容器和主控制器：`Container` 是简单的组件组合容器，按顺序渲染子组件；`TUI extends Container` 是真正的终端 UI 管理器，持有 `Terminal`，维护上次渲染结果、焦点组件、输入监听器、overlay 栈、光标状态、窗口尺寸、Kitty 图片 ID 等状态。

第三类是 overlay 相关类型：`OverlayOptions`、`OverlayHandle`、`OverlayAnchor`、`OverlayMargin`、`OverlayUnfocusOptions`、`SizeValue` 等，用于描述浮层的尺寸、锚点、偏移、边距、可见性和焦点行为。文件也重新导出 `visibleWidth`，供上层组件计算终端列宽。

## 谁调用它

`packages/tui/src/index.ts` 会重新导出这里的核心类型和类，使它成为 TUI 包的公共入口之一。包内组件如 `components/editor.ts`、`components/input.ts`、`components/select-list.ts`、`components/markdown.ts`、`components/image.ts`、`components/loader.ts` 等都依赖 `Component`、`Focusable`、`CURSOR_MARKER` 或 `TUI`。

包外调用主要来自 `packages/coding-agent`。例如 `packages/coding-agent/src/cli/startup-ui.ts` 根据当前片段可见会创建启动界面的 `TUI`；扩展加载逻辑也把 `@earendil-works/pi-tui` 暴露给插件；若干 coding-agent 测试用 fake `TUI` 或真实 `TUI` 验证交互模式状态。

## 它调用谁

`TUI` 直接依赖 `./terminal.ts` 中的 `Terminal` 抽象，具体写屏、移动光标、隐藏/显示光标、读取终端尺寸等都通过该抽象完成。键盘处理依赖 `./keys.ts` 的 `matchesKey()`、`isKeyRelease()`，用于识别调试快捷键和 Kitty 键盘释放事件。

渲染文本处理依赖 `./utils.ts` 的 `extractSegments()`、`normalizeTerminalOutput()`、`sliceByColumn()`、`sliceWithWidth()`、`visibleWidth()`，这些函数承担 ANSI 片段拆分、宽度计算、按列裁剪和输出标准化。图片能力依赖 `./terminal-image.ts` 的 `getCapabilities()`、`setCellDimensions()`、`isImageLine()`、`deleteKittyImage()`，用于终端图片协议和 Kitty 图片资源清理。`fs`、`os`、`path` 根据当前片段推断主要服务于终端图片或临时文件处理，依据是文件中存在 Kitty 图片序列解析和图片删除逻辑。

## 核心流程

渲染流程以 `requestRender()` 为入口。调用方不直接频繁写终端，而是请求一次刷新；`TUI` 用最小渲染间隔合并请求，避免输入或流式输出时过度刷屏。真正渲染时，它读取终端宽高，先渲染基础 `Container` 子组件，再按 overlay 栈叠加可见浮层。渲染结果会被标准化、按终端宽度裁剪，并和 `previousLines` 做差分，只更新变化行；当窗口变小或内容缩短时，还要处理残留行清理。

输入流程从终端字节进入 `TUI`。全局 input listener 先有机会改写或消费输入；随后识别调试快捷键；如果是 Kitty key release，默认过滤，除非当前焦点组件声明 `wantsKeyRelease`。最终输入转交给当前 `focusedComponent.handleInput()`。这使编辑器、输入框、选择列表等组件只关心自己的交互逻辑，而不需要知道底层终端协议。

焦点流程围绕普通组件和 overlay 组件展开。普通组件可通过 `focus()` 一类方法成为当前焦点；overlay 显示时，如果不是 `nonCapturing`，会捕获焦点并记录之前焦点。overlay 隐藏、临时隐藏或取消焦点时，`TUI` 根据栈顶可见捕获层、之前焦点、显式 target 等恢复焦点。根据当前片段推断，文件里有专门的 blocked/eligible restore 状态，是为了处理“某个 overlay 想恢复焦点但被更上层 overlay 阻挡”的场景。

硬件光标流程依赖 `CURSOR_MARKER`。可聚焦组件在渲染文本中插入该 marker，`TUI` 扫描并移除 marker，同时计算其所在行列，最后移动终端硬件光标。这样 IME 候选窗能出现在真实输入位置，而不是总在逻辑内容末尾。

## 关键函数的高层作用

`Container.addChild()`、`removeChild()`、`clear()`、`render()` 提供最基础的纵向组件组合能力。它没有布局系统，只是把每个子组件渲染出的行顺序拼接。

`TUI.requestRender()` 是外部最常用的刷新入口，负责节流和异步调度。组件状态变化后通常调用它，而不是直接调用底层渲染。

`TUI.render()` 或内部同名刷新方法是核心执行点：收集组件输出、处理 overlay、处理 ANSI 宽度、定位光标、执行差分写屏、维护 previous 状态，并清理不再出现的 Kitty 图片。

`showOverlay()` 返回 `OverlayHandle`，是浮层生命周期入口。调用者通过 handle 控制 `hide()`、`setHidden()`、`focus()`、`unfocus()`，而不是直接操作 `overlayStack`。

`focus()`、overlay focus restore 相关方法负责维持唯一焦点，并同步 `Focusable.focused` 标记。它们的正确性直接影响输入框、编辑器和弹窗之间的键盘归属。

`extractKittyImageIds()` 是辅助函数，只从 Kitty graphics escape sequence 中提取图片 ID，用于后续资源回收；`parseSizeValue()` 将数字或百分比尺寸转换为绝对列/行；`isTermuxSession()` 是终端环境特例判断。

## 修改风险

最大风险是终端渲染副作用。这里不是普通字符串拼接，任何对 `visibleWidth`、列裁剪、ANSI 标准化、差分刷新或清屏逻辑的改动，都可能导致宽字符、颜色样式、窗口 resize、内容缩短后残影、滚动区域覆盖等问题。

第二个风险是焦点和 overlay 栈。`nonCapturing`、隐藏浮层、嵌套浮层、手动 `unfocus()`、恢复旧焦点这些场景交叉很多，轻微改动可能让输入落到错误组件，或者让弹窗关闭后编辑器不再接收输入。

第三个风险是硬件光标和 IME。`CURSOR_MARKER` 必须保持零宽且在输出前被剥离；行列计算必须和最终写入终端的文本一致，否则中文输入法候选窗会错位，或者终端显示出异常控制字符。

第四个风险是 Kitty 图片资源。图片行识别、ID 提取和 `deleteKittyImage()` 清理如果失衡，可能造成图片残留、闪烁或误删仍在显示的图片。涉及 `terminal-image.ts` 时应同时检查图片组件和相关测试。

修改该文件后，重点应跑 TUI 渲染、overlay、shrink、cell size、markdown/editor 相关测试，并按仓库规则执行 `npm run check`；如果改到交互行为，还需要用虚拟终端或 tmux 手动验证真实终端表现。
