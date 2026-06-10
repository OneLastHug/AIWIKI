# 文件：ui-tui/packages/hermes-ink/index.d.ts

## 一句话定位

`ui-tui/packages/hermes-ink/index.d.ts` 是本地包 `@hermes/ink` 的对外 TypeScript 类型入口，负责把 forked Ink 渲染器的组件、hooks、渲染 API、终端事件类型和文本工具统一暴露给 TUI 上层代码。

## 它暴露/定义了什么

这个文件本身不实现逻辑，而是一个声明层的 barrel export。它先引入 `./ambient.d.ts`，再集中导出 `@hermes/ink` 的公共表面：基础组件 `Box`、`Text`、`Link`、`ScrollBox`、`AlternateScreen`、`RawAnsi`、`Ansi`、`NoSelect`；输入输出 hooks `useInput`、`useStdin`、`useStdout`、`useStderr`；终端相关 hooks `useTerminalTitle`、`useTerminalFocus`、`useTerminalViewport`、`useSelection`、`useTabStatus`；渲染入口 `render`、`renderSync`、`createRoot`、`forceRedraw`；以及 `stringWidth`、`wrapAnsi`、`measureElement`、`evictInkCaches` 等工具函数。

它还转发若干类型，例如 `ScrollBoxHandle`、`ScrollBoxProps`、`RenderOptions`、`Instance`、`Root`、`Key`、`MouseTrackingMode`、`EvictLevel`、`InkCacheSizes`，并把外部依赖 `ink-text-input` 的 `TextInput`、`UncontrolledTextInput` 和 `TextInputProps` 纳入同一个入口。

## 谁调用它

直接消费方是 `ui-tui/src` 下的 React/Ink TUI。典型调用包括：`ui-tui/src/entry.tsx` 动态导入 `@hermes/ink` 并调用 `ink.render(<App ... />)`；`ui-tui/src/components/appLayout.tsx` 使用 `AlternateScreen`、`ScrollBox`、`Box`、`Text` 组织主布局；`ui-tui/src/components/textInput.tsx` 依赖 `Key`、输入事件和 Ink 命名空间；`ui-tui/src/app/useInputHandlers.ts` 使用 `useInput`、`forceRedraw` 做按键路由；`ui-tui/src/app/useMainApp.ts` 使用 `useApp`、`useSelection`、`useStdout`、`useTerminalTitle` 管理应用级状态。

需要注意：`ui-tui/tsconfig.build.json` 把 `@hermes/ink` 类型映射到 `ui-tui/src/types/hermes-ink.d.ts`。因此在当前 TUI 构建中，很多类型实际由这个 shim 补齐；本文件更像 `packages/hermes-ink` 作为独立本地包时的 `types` 入口。

## 它调用谁

作为 `.d.ts` 声明文件，它没有运行时调用。它的“依赖关系”是类型级和导出级：向内指向 `ui-tui/packages/hermes-ink/src/hooks/*`、`src/ink/components/*`、`src/ink/hooks/*`、`src/ink/root.ts`、`src/ink/stringWidth.ts`、`src/ink/wrapAnsi.ts` 等实现模块；向外转发 `ink-text-input`。运行时对应入口是 `ui-tui/packages/hermes-ink/src/entry-exports.ts`，由包构建脚本用 esbuild 打包到 `dist` 或对应 `index.js`。

## 核心流程

整体流程可以理解为三层。第一层是 `packages/hermes-ink` 内部 forked Ink：`root.ts` 创建或复用 `Ink` 实例，挂载 React tree，把组件树渲染为终端输出，并处理输入、鼠标、焦点、选择、滚动和帧统计。第二层是 `index.d.ts` 将这些能力整理成稳定的包边界，让上层只从 `@hermes/ink` 导入，而不关心内部路径。第三层是 `ui-tui/src/entry.tsx` 启动 TTY、清理终端状态、启动 Python gateway，再导入 `@hermes/ink` 渲染 `<App />`，后续组件通过本入口暴露的组件和 hooks 构建完整 TUI。

## 关键函数的高层作用

`render` 是默认异步挂载入口，包装 `renderSync` 并保留一个 microtask 边界，避免首次渲染过早影响启动期输出顺序。`renderSync` 负责合并 `stdin`、`stdout`、`stderr`、`exitOnCtrlC`、`patchConsole` 等选项，创建或复用 `Ink` 实例并渲染 React 节点。`createRoot` 提供类似 `react-dom` 的 root API，适合需要先创建根、再多次 `render` 的场景。`forceRedraw` 根据 `stdout` 找到已注册实例并强制重绘，用于终端尺寸、外部编辑器返回或输入状态变化后的画面刷新。`ScrollBox` 和 `ScrollBoxHandle` 是 transcript、overlay、agent 列表等可滚动区域的核心接口。`useInput` 是按键分发入口，`useSelection` 管理终端选择复制，`evictInkCaches` 则用于长会话内存压力下清理渲染缓存。

辅助工具如 `stringWidth`、`wrapAnsi`、`measureElement` 主要服务于宽字符、ANSI 文本换行和布局测量。

## 修改风险

最大风险是声明与运行时导出不同步。当前 `src/entry-exports.ts` 已导出 `withInkSuspended`、`useExternalProcess`、`RunExternalProcess`、`scrollFastPathStats`、`isXtermJs` 等能力，但目标 `index.d.ts` 片段没有全部覆盖；而 `ui-tui/src/types/hermes-ink.d.ts` 又补了部分应用侧需要的声明。修改时如果只改实现、不改这里，独立消费 `@hermes/ink` 的类型会失真；如果只改这里、不改 `entry-exports.ts`，会出现类型允许但运行时报错。

第二类风险是公共 API 收缩。`Box`、`Text`、`useInput`、`ScrollBoxHandle`、`render` 等被大量组件依赖，改名或改变类型会造成 TUI 大面积编译失败。第三类风险是事件语义变化，特别是 `Key.meta`、`alt`、鼠标滚轮、选择和焦点事件；`ui-tui/src/lib/platform.ts` 和相关测试对这些细节有明确假设。第四类风险是包边界混乱：这里导出的路径使用 `.ts`、`.tsx` 源文件声明，而运行时入口使用 `.js` 构建产物，新增导出时要同时检查 `package.json` 的 `types`、`exports`、`src/entry-exports.ts` 和应用侧 shim，避免类型系统、打包器和 Node ESM 解析看到三个不同的公共面。
