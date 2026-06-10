# 目录：packages/@ant/ink

## 它负责什么
`packages/@ant/ink` 是一个内部 fork 的终端 React 渲染框架，职责不是做业务 UI，而是把 React 组件稳定地渲染到终端里。它提供了一整套从渲染根、布局、事件、输入、焦点、快捷键，到主题和设计系统的能力，供上层 CLI 直接复用。

从当前目录结构看，它明显分成三层：`core/` 负责渲染引擎和终端 I/O，`components/` 负责基础 UI 原语和运行时上下文，`theme/` 负责主题与更高层的设计系统组件。`docs/` 里也按这三层展开了完整文档，说明这个包本身就是一个可独立理解的框架层，而不是零散工具集。

## 直接子目录地图
- `src/core/`：最核心的实现区，包含 reconciler、布局、屏幕缓冲、终端协议、事件分发、渲染输出等。这里是“React 怎么变成终端字符”的主战场。
- `src/components/`：基础组件和上下文提供者，像 `Box`、`Text`、`ScrollBox`、`Button`、`App`、`TerminalSizeContext` 这类都在这里。它更接近 React 组件层。
- `src/theme/`：主题系统和设计系统组件，包含 `ThemeProvider`、`ThemedBox`、`ThemedText`，以及 `Dialog`、`Tabs`、`ProgressBar`、`FuzzyPicker` 等更高层组件。
- `src/hooks/`：面向终端交互的 hooks 层，处理输入、选区、焦点、终端尺寸、标题、通知、动画计时等。
- `src/keybindings/`：按键绑定相关逻辑，包括解析、匹配、解析器、上下文和注册机制。
- `src/types/`：类型声明文件，补足 Ink 元素和 JSX 类型。
- `src/utils/`：体量较小的辅助工具。根据当前片段推断，这里偏向与终端主题或运行时辅助相关的独立小模块，现有可见文件是 `systemThemeWatcher.ts`。
- `docs/`：面向使用者和维护者的分章节文档，从入门到终端集成一应俱全。

## 关键入口
最直接的对外入口是 `src/index.ts`，它负责把这个包的能力统一导出。`package.json` 里的 `main`、`types` 和 `exports` 都指向它，说明外部依赖方实际拿到的就是这一个聚合入口。

真正的运行起点在 `src/core/root.ts`。这里提供 `renderSync()`、默认导出的 `wrappedRender`，以及 `createRoot()`，负责创建或复用 Ink 实例、挂载输出流、返回 `rerender` 和 `unmount` 等控制接口。它是“应用如何启动”的第一层入口。

再往下是 `src/core/ink.tsx`。它定义了 `Ink` 类，是渲染器实例本体，持有终端、屏幕、布局、输入、选择、hover、alt screen、重绘调度等状态。可以把它理解为整个包的引擎核心。

组件层的关键入口是 `src/components/App.tsx`。它不是普通业务组件，而是所有 Ink 应用共享的根组件，负责 stdin/stdout context、错误边界、终端输入解析、点击/悬停派发、Ctrl+C 处理等。

主题层的关键入口是 `src/theme/ThemeProvider.tsx`。它维护当前主题设置、预览主题、自动主题解析，以及和 `useStdin()` 相关的终端主题监听逻辑，是高层样式系统的控制中心。

## 主流程位置
主流程可以按“入口 -> 引擎 -> 组件树 -> 输出终端”来理解。

1. 外部调用 `src/index.ts` 暴露的 `renderSync()` 或 `createRoot()`。
2. 进入 `src/core/root.ts`，创建或复用 `Ink` 实例。
3. `src/core/ink.tsx` 负责建立 React reconciler、布局引擎、screen buffer、终端写出器，并把 React 树交给渲染流程。
4. 渲染树的根部由 `src/components/App.tsx` 承接，它把 stdin、stdout、焦点、终端尺寸、选择状态等上下文分发给子组件。
5. 主题相关逻辑由 `src/theme/ThemeProvider.tsx` 注入，决定最终如何着色、如何切换 `auto`、如何与系统主题同步。
6. 细粒度的输入、按键绑定、滚动、选区、终端标题和通知等行为，由 `src/hooks/`、`src/keybindings/` 和 `src/core/events/` 一起完成。
7. 最终输出通过 `src/core/render-to-screen.ts`、`src/core/render-node-to-output.ts`、`src/core/output.ts`、`src/core/terminal.ts` 等模块写回终端。

如果只看路径角色，这个包的主干非常清晰：`root.ts` 负责装配，`ink.tsx` 负责运行，`App.tsx` 负责承接交互，`ThemeProvider.tsx` 负责视觉体系，`core/` 里的其余模块负责把一切落到终端字符流上。

## 推荐阅读顺序
1. `src/index.ts`：先看导出面，建立这个包到底提供什么能力的全局认识。
2. `src/core/root.ts`：理解最外层 API，知道实例如何创建和复用。
3. `src/core/ink.tsx`：看引擎本体，理解渲染、输入、屏幕、焦点、选择是怎么串起来的。
4. `src/components/App.tsx`：看根组件如何把终端事件接入 React 树。
5. `src/theme/ThemeProvider.tsx`：理解主题系统如何接入终端环境。
6. `docs/11-core-architecture.md`、`docs/04-theme-system.md`、`docs/08-keybindings.md`：按主线补文档视角。
7. 再按需回到 `src/hooks/`、`src/keybindings/`、`src/core/events/` 做局部深入。

## 常见误区
- 把它当成普通 UI 组件库。实际上它是“终端渲染框架”，核心价值在渲染管线和输入系统，不只是 Box/Text 这些原语。
- 只看 `src/components/` 就以为掌握了全貌。真正的行为逻辑大多在 `src/core/`，尤其是 `ink.tsx`、`reconciler.ts`、`render-to-screen.ts`、`terminal.ts` 一线。
- 以为 `ThemeProvider` 只是样式上下文。它还负责 `auto` 主题、系统主题监听和预览状态，是交互逻辑的一部分。
- 把 `src/index.ts` 当成业务入口。它其实是聚合导出层，真正的初始化与运行控制在 `src/core/root.ts` 和 `src/core/ink.tsx`。
- 忽略 `docs/`。这个目录不是附属材料，而是把整个三层架构拆成了可读的学习路径，适合用来反向确认代码结构。
