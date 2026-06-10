# 文件：ui-tui/packages/hermes-ink/index.js

## 一句话定位

`ui-tui/packages/hermes-ink/index.js` 是本地包 `@hermes/ink` 的运行时入口文件，本身不承载渲染逻辑，只把包的公开 API 从构建产物 `./dist/entry-exports.js` 统一转出，作为 Hermes TUI 使用 forked Ink renderer 的稳定导入门面。

## 它暴露/定义了什么

这个文件只包含一行：

```js
export * from './dist/entry-exports.js'
```

因此它实际暴露的内容由 `ui-tui/packages/hermes-ink/src/entry-exports.ts` 决定，再经 `package.json` 的 `build` 脚本打包到 `dist/entry-exports.js`。公开 API 主要包括几类：

- 渲染入口：`render`、`renderSync`、`createRoot`、`forceRedraw`
- 基础组件：`Box`、`Text`、`Newline`、`Spacer`、`Link`、`ScrollBox`
- 终端能力组件：`AlternateScreen`、`RawAnsi`、`Ansi`、`NoSelect`
- Hooks：`useInput`、`useStdin`、`useStdout`、`useStderr`、`useApp`、`useSelection`、`useTerminalViewport`、`useTerminalFocus`、`useTerminalTitle`、`useTabStatus`
- 工具函数：`measureElement`、`stringWidth`、`wrapAnsi`、`isXtermJs`、`evictInkCaches`
- 输入组件转发：`TextInput`、`UncontrolledTextInput` 来自 `ink-text-input`

类型侧由 `ui-tui/packages/hermes-ink/index.d.ts` 对应声明，源码侧由 `src/entry-exports.ts` 维护真实导出列表。

## 谁调用它

主要调用者是整个 `ui-tui` 应用中对 `@hermes/ink` 的导入。最核心的运行时调用出现在 `ui-tui/src/entry.tsx`：它动态 `import('@hermes/ink')`，再调用 `ink.render(<App gw={gw} />, options)` 挂载 TUI。

`ui-tui/package.json` 将 `@hermes/ink` 声明为 `file:./packages/hermes-ink` 本地依赖，因此普通开发运行时会按 Node package exports 解析到这个 `index.js`。不过生产构建脚本 `ui-tui/scripts/build.mjs` 有一个重要例外：它通过 esbuild alias 把 `@hermes/ink` 指向 `packages/hermes-ink/src/entry-exports.ts`，绕过预构建 bundle。注释说明这是为了避免 esbuild 的 helper 破坏某些懒初始化导出，尤其是 `render` 这类导出。

## 它调用谁

`index.js` 直接调用关系极少，只依赖并转出 `./dist/entry-exports.js`。根据当前片段推断，这个 `dist` 文件由 `package.json` 中的脚本生成：

```json
"build": "esbuild src/entry-exports.ts --bundle --platform=node --format=esm --packages=external --outdir=dist"
```

真实调用链在被转出的模块中展开：`entry-exports.ts` 汇总 `src/ink/root.ts`、组件、hooks、终端工具、文本测量与包装工具，并转发 `ink-text-input`。其中渲染入口进一步调用 `src/ink/ink.tsx`、`src/ink/instances.ts`、React reconciler 及终端输出相关模块。

## 核心流程

运行时流程可以理解为四层：

1. 外部代码写 `import('@hermes/ink')` 或静态导入 `@hermes/ink`。
2. Node 根据 `ui-tui/packages/hermes-ink/package.json` 的 `exports["."]` 解析到 `index.js`。
3. `index.js` 将请求转发到 `dist/entry-exports.js`。
4. `dist/entry-exports.js` 提供 `render`、组件、hooks 和工具函数，供 `ui-tui/src/entry.tsx` 与各组件使用。

在开发/生产 bundle 构建时，流程略有不同：`ui-tui/scripts/build.mjs` 把 `@hermes/ink` alias 到源码 `src/entry-exports.ts`，因此最终 `dist/entry.js` 中会直接包含 hermes-ink 源码入口，而不是通过这个 `index.js` 再加载预构建产物。也就是说，`index.js` 更像包消费边界；bundle 构建为了稳定性主动绕过它。

## 关键函数的高层作用

`index.js` 没有定义函数。关键 API 来自它转出的 `src/entry-exports.ts`，其中最重要的是 `src/ink/root.ts` 的渲染函数：

`render` 是默认异步挂载入口。它保留一个 microtask 边界后调用 `renderSync`，再返回包含 `rerender`、`unmount`、`waitUntilExit`、`cleanup` 的实例对象。这个 microtask 边界从注释看是为了保持旧版异步初始化行为，避免首帧渲染过早影响 scrollback。

`renderSync` 创建或复用某个 stdout 对应的 `Ink` 实例，调用 `instance.render(node)` 完成 React 树挂载，并把生命周期方法包装成对外实例。

`createRoot` 类似 `react-dom` 的 `createRoot`，先创建根实例但不立即渲染，适合复用同一个 root 渲染多个 sequential screens。

`forceRedraw` 根据 stdout 从 `instances` 表中取现有 `Ink` 实例并触发重绘，用于外部暂停/恢复或终端状态变化后的补救刷新。

其他组件和 hooks 是 TUI 上层 UI 的基础设施：`Box`、`Text` 负责布局与文本渲染，`useInput` 负责键盘事件，`ScrollBox` 支持滚动视图，`Link` 和 `onHyperlinkClick` 配合处理终端中可点击链接。

## 修改风险

这个文件虽小，但风险集中在“包入口稳定性”。如果把 `export * from './dist/entry-exports.js'` 改错，所有通过 `@hermes/ink` 运行时导入的代码都会失效，包括 `ui-tui/src/entry.tsx` 的动态导入。路径、扩展名、ESM 语义都不能随意改。

另一个风险是源码导出列表与构建产物不同步。`index.js` 指向 `dist/entry-exports.js`，但真实维护点是 `src/entry-exports.ts`。新增或删除 API 时，如果没有运行 `npm run build --prefix packages/hermes-ink` 生成 `dist`，运行时包入口可能暴露旧接口，而 TypeScript 或 bundle alias 路径看到的却是新接口，造成开发环境与实际包消费行为不一致。

还要注意 `package.json` 的 `exports`、`main`、`types` 三者必须保持一致：运行时入口是 `index.js`，类型入口是 `index.d.ts`。若只改 JS 不改声明，使用方会出现类型通过但运行失败，或运行可用但类型不可见的问题。

最后，`ui-tui/scripts/build.mjs` 明确绕过预构建 `@hermes/ink` bundle，说明这里曾经存在构建器与懒初始化导出的兼容问题。因此不要轻易把生产构建改回直接消费 `index.js` 或 `dist/entry-exports.js`；如果必须调整，需要重点验证 `render`、`createRoot`、首帧渲染、输入 raw mode、超链接点击、窗口 resize 和 `TextInput` 光标行为。
