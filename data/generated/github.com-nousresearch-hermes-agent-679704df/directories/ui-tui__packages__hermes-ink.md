# 目录：ui-tui/packages/hermes-ink

## 它负责什么

`ui-tui/packages/hermes-ink` 是 `ui-tui` 内部维护的一套终端 React 渲染运行时，包名是 `@hermes/ink`。它的定位类似定制版 Ink：把 React 组件树渲染到终端 stdout，同时处理 stdin 输入、TTY 尺寸变化、备用屏幕、鼠标事件、文本选择、链接悬停、ANSI 解析、宽字符测量、布局计算和增量刷屏。

从 `ui-tui/package.json` 看，顶层 TUI 通过本地依赖 `"@hermes/ink": "file:./packages/hermes-ink"` 使用它；开发命令也会先 `npm run build --prefix packages/hermes-ink`，再启动 `src/entry.tsx`。因此它不是 Hermes 业务聊天逻辑本身，而是 `ui-tui/src` 里组件、输入处理、滚动历史、主题渲染、性能面板等功能的底层 UI 引擎。根据当前片段推断，`ui-tui/src` 负责 Hermes TUI 的应用语义，`hermes-ink` 负责“React 树如何变成终端帧”。

## 直接子目录地图

`src/bootstrap` 很小，目前核心是 `state.ts`，用于保存或刷新启动/交互相关状态。它被 `src/ink/ink.tsx` 引用，用来在渲染过程中记录交互时间一类的运行态信息。

`src/hooks` 是包顶层导出的 stream hook 区，包含 `use-stdout.ts`、`use-stderr.ts`。这些 hook 给业务组件访问当前 stdout/stderr，而不用直接碰 Node 全局对象。

`src/ink` 是主目录，绝大多数能力都在这里。它包含渲染器、React reconciler、DOM 抽象、终端输出、ANSI/OSC/CSI/DEC 控制序列、事件系统、布局、文本测量、缓存、选择、高亮、滚动和核心组件。阅读这个包基本就是阅读 `src/ink`。

`src/ink/components` 是公开组件层，包含 `Box`、`Text`、`ScrollBox`、`AlternateScreen`、`Link`、`RawAnsi`、`Ansi` 相关组件、上下文组件等。`ui-tui/src/components` 大量从 `@hermes/ink` 导入这些组件来搭建界面。

`src/ink/events` 是输入事件抽象层，包含 click、focus、keyboard、mouse、paste、resize、terminal focus 等事件对象，以及 dispatcher、emitter、event-handlers。这里把终端原始输入转换为 React/Ink 内部可派发的事件。

`src/ink/hooks` 是 Ink 内部导出的交互 hook，包含 `use-input`、`use-app`、`use-selection`、`use-terminal-title`、`use-terminal-focus`、`use-terminal-viewport`、`use-external-process` 等。业务层的快捷键、外部进程暂停恢复、终端标题、选择状态都通过这些 hook 接入。

`src/ink/layout` 是布局层，包含 `engine.ts`、`geometry.ts`、`node.ts`、`yoga.ts`。它把组件样式和节点树转成终端上的矩形布局，并桥接到本地 TypeScript 版 Yoga 实现。

`src/ink/termio` 是终端控制序列和解析层，包含 `ansi.ts`、`csi.ts`、`dec.ts`、`osc.ts`、`parser.ts`、`sgr.ts`、`tokenize.ts`、`types.ts`。备用屏幕、鼠标追踪、剪贴板、超链接、tab 状态、颜色样式等底层协议都在这里附近。

`src/native-ts/yoga-layout` 是 Yoga 布局的本地 TypeScript 实现或适配，提供 `index.ts`、`enums.ts`。`src/ink/ink.tsx` 会读取 Yoga 计数器，用于布局性能统计。

`src/utils` 是通用工具层，包含 debug、日志、环境判断、外部命令执行、全屏判断、ANSI 切片、semver、早期输入处理等。它服务于渲染运行时，不承载具体 Hermes 聊天业务。

## 关键入口

包级入口是 `index.js`，内容很薄，只是 `export * from './dist/entry-exports.js'`。源码入口对应 `src/entry-exports.ts`，这里集中导出公开 API：`Box`、`Text`、`ScrollBox`、`AlternateScreen`、`Link`、`Ansi`、`RawAnsi`、`render`、`renderSync`、`createRoot`、`forceRedraw`、`useInput`、`useApp`、`useStdout`、`useStdin`、`useSelection`、`useTerminalTitle`、`useExternalProcess`、`stringWidth`、`wrapAnsi` 等。

`package.json` 的 `build` 脚本使用 esbuild 将 `src/entry-exports.ts` 打包到 `dist`，运行时再由 `index.js` 暴露出去。`exports` 还额外暴露 `./text-input`，实际由 `text-input.js`、`text-input.d.ts` 包装，底层导出 `ink-text-input` 的文本输入组件。

核心类入口是 `src/ink/ink.tsx` 中的 `Ink` class。它持有 stdout/stdin/stderr、React Fiber root、DOM root、renderer、focus manager、screen buffer、selection state、terminal size、alt screen 状态、鼠标悬停状态、缓存池和渲染调度器。这个类是“运行中的一个终端 UI 实例”。

更上层的创建入口在 `src/ink/root.ts`：`renderSync` 会创建或复用 `Ink` 实例并立即渲染；默认导出的异步 `render` 保留一个 microtask 边界后调用 `renderSync`；`createRoot` 提供类似 `react-dom` 的 root API，可先创建 root，再多次 `root.render(node)`。

## 主流程位置

主流程可以按“应用调用、React 提交、布局、帧生成、终端写入”理解。

第一步，`ui-tui/src` 里的业务入口根据当前片段推断会动态导入 `@hermes/ink`，并使用 `render` 或 `createRoot` 挂载根组件。这个判断依据是 `ui-tui/src/entry.tsx` 中出现对 `@hermes/ink` 的导入，且大量组件从该包导入 `Box`、`Text`、`ScrollBox`、`useInput`。

第二步，`src/ink/root.ts` 创建 `Ink` 实例。实例内部在 `src/ink/ink.tsx` 构造函数里创建 `dom.createNode('ink-root')`，创建 `FocusManager`，调用 `createRenderer`，设置 `rootNode.onRender`、`rootNode.onImmediateRender`，再通过 `reconciler.createContainer(...)` 建立 React Fiber 容器。

第三步，React commit 后触发布局与渲染。`rootNode.onComputeLayout` 会设置 Yoga 宽度并调用 `calculateLayout(this.terminalColumns)`，说明布局宽度直接跟当前终端列数绑定。随后 `scheduleRender` 将 `onRender` 放到 microtask，并用 `FRAME_INTERVAL_MS` 节流，避免每次状态变化都立即刷屏。

第四步，渲染帧由 `render-node-to-output.ts`、`render-to-screen.ts`、`screen.ts`、`output.ts`、`renderer.ts`、`terminal.ts` 等共同完成。根据文件名和 `ink.tsx` 的导入关系可见，流程包括节点转输出、生成/维护 screen buffer、处理选择和搜索高亮、应用链接 hover 高亮、计算 diff，再通过 `writeDiffToTerminal` 写入终端。

第五步，输入和终端事件反向进入组件树。`parse-keypress.ts`、`events/*`、`hit-test.ts`、`selection.ts`、`focus.ts` 和 `components/App.tsx` 共同支撑键盘、鼠标、点击、悬停、选择、粘贴、resize、terminal focus。`useInput` 等 hook 是业务组件接入这些事件的主要表面。

## 推荐阅读顺序

1. 先读 `ui-tui/packages/hermes-ink/package.json` 和 `src/entry-exports.ts`，确认这个包暴露给 `ui-tui/src` 的 API 边界。
2. 再读 `src/ink/root.ts`，理解 `render`、`renderSync`、`createRoot` 如何创建和管理 `Ink` 实例。
3. 接着读 `src/ink/ink.tsx` 的构造函数和 resize、alt screen、render 调度相关方法，建立运行时主干认识。
4. 然后看 `src/ink/components/Box.tsx`、`src/ink/components/Text.tsx`、`src/ink/components/ScrollBox.tsx`、`src/ink/components/AlternateScreen.tsx`，理解业务层实际使用的组件模型。
5. 再进入 `src/ink/reconciler.ts`、`src/ink/dom.ts`、`src/ink/renderer.ts`、`src/ink/render-node-to-output.ts`、`src/ink/terminal.ts`，串起 React 节点到终端 diff 输出的链路。
6. 最后按需求查 `src/ink/events`、`src/ink/termio`、`src/ink/selection.ts`、`src/ink/wrapAnsi.ts`、`src/ink/stringWidth.ts`，这些是输入协议、终端协议和文本细节。

## 常见误区

不要把 `hermes-ink` 当作普通 React 前端组件库。它运行在 Node/TTY 环境，输出目标是终端，不是浏览器 DOM；`Box`、`Text` 的布局和样式最终都会被转换成字符单元、ANSI 样式和终端控制序列。

不要把这里和 Python 的 `tui_gateway` 混在一起。`tui_gateway` 负责后端 JSON-RPC、会话、模型和工具调用；`hermes-ink` 负责 TypeScript/React 侧的终端渲染和交互基础设施。

不要在阅读时逐个叶子文件展开。这个目录文件很多，overview 阶段应抓住 `entry-exports.ts`、`root.ts`、`ink.tsx`、`components`、`events`、`termio`、`layout` 这几条主线。

不要以为 `index.js` 就是源码主逻辑。它只是发布入口，真正导出清单在 `src/entry-exports.ts`，真正运行时在 `src/ink/root.ts` 和 `src/ink/ink.tsx`。

不要忽略终端状态。备用屏幕、鼠标追踪、resize、SIGCONT、stdout drain、selection overlay、OSC 8 hyperlink 等都是这个包的核心复杂度来源。很多看似 UI 组件的问题，实际根因可能在 `termio`、`terminal.ts` 或 screen diff 层。
