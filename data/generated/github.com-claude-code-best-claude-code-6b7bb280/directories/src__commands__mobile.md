# 目录：src/commands/mobile

## 它负责什么

`src/commands/mobile` 负责实现 Claude Code REPL 内的 `/mobile` 斜杠命令。它的功能很集中：在终端界面中显示一个二维码面板，用户可以用手机扫描二维码下载 Claude 移动端应用。这个目录不参与 Claude API 请求、会话管理、权限判断、MCP、模型选择或工具执行，它只是一个本地 UI 命令。

从命令声明看，`/mobile` 是 `local-jsx` 类型命令。也就是说，它不是普通的文本命令，也不是会把输入交给模型处理的 prompt，而是在当前 CLI 进程里动态加载一个 React/Ink 组件，然后把组件挂到 REPL 的本地 JSX 命令渲染槽中。它的别名包括 `/ios` 和 `/android`，但这两个别名不会直接决定初始平台；实现里默认先展示 `ios`，用户可以在面板内切换到 `android`。

这个目录的职责边界很窄：命令注册在 `index.ts`，真正的终端 UI 和二维码生成逻辑在 `mobile.tsx`。二维码内容来自内置的平台下载地址，文档中不展开真实地址；源码里分别指向 iOS App Store 和 Android Google Play 的 Claude 应用页面。

## 直接子目录地图

`src/commands/mobile` 当前没有直接子目录，只有两个文件：

`src/commands/mobile/index.ts`：命令元信息入口，声明命令类型、名称、别名、描述，以及懒加载实现模块。

`src/commands/mobile/mobile.tsx`：命令的实际 UI 实现，生成二维码、维护当前平台状态、处理键盘交互，并导出 `call()` 供 REPL 命令系统调用。

因此这里不是一个复杂功能域目录，也没有拆分 services、components、utils 或 tests。阅读时应把它当作一个小型本地斜杠命令样例来看。

## 关键入口

第一层入口是 `src/commands/mobile/index.ts`。它导出默认对象 `mobile`，并通过 `satisfies Command` 约束为通用命令类型。关键字段包括：

`type: 'local-jsx'`：表示这个命令运行后会返回 React 节点，由 REPL 本地渲染。

`name: 'mobile'`：主命令名，对应用户输入 `/mobile`。

`aliases: ['ios', 'android']`：别名命令，对应 `/ios` 和 `/android`。

`description: 'Show QR code to download the Claude mobile app'`：用于命令列表、提示或帮助信息展示。

`load: () => import('./mobile.js')`：懒加载真正实现。注意源码是 TypeScript/TSX，但运行时导入路径写成 `.js`，这是本仓库 ESM + TS 编译约定下常见写法。

第二层入口是 `src/commands/mobile/mobile.tsx` 导出的 `call(onDone)`。REPL 匹配到 `/mobile` 后会执行 `matchingCommand.load()`，再调用模块里的 `call()`。这里的 `call()` 返回 `<MobileQRCode onDone={onDone} />`，也就是把命令生命周期交给 `MobileQRCode` 组件控制。

## 主流程位置

主流程可以按“注册、匹配、加载、渲染、退出”理解。

注册阶段发生在 `src/commands.ts`。该文件集中导入大量内置斜杠命令，其中包含 `import mobile from './commands/mobile/index.js'`。根据当前片段推断，`mobile` 会被放入全局 commands 列表，供 REPL 的 slash command 匹配逻辑使用；依据是 `src/commands.ts` 是命令聚合文件，且 `src/screens/REPL.tsx` 中使用 `commands.find(...)` 查询命令。

匹配与加载阶段在 `src/screens/REPL.tsx`。当用户提交以 `/` 开头的输入时，REPL 会找到 `matchingCommand`。如果命令类型是 `local-jsx`，REPL 会构造 `onDone` 回调和工具上下文，然后执行 `const mod = await matchingCommand.load()`，再执行 `const jsx = await mod.call(onDone, context, commandArgs)`。虽然 `/mobile` 的 `call()` 只使用 `onDone`，但统一接口仍允许命令接收上下文和参数。

渲染阶段同样在 `src/screens/REPL.tsx`。如果 `call()` 返回 JSX，REPL 会调用 `setToolJSX({ jsx, shouldHidePromptInput: false, isLocalJSXCommand: true })`。这会把 `/mobile` 的 UI 放进本地命令渲染区域。fullscreen 环境下，`toolJSX?.isLocalJSXCommand === true` 的命令会走居中或底部模态渲染路径；非 fullscreen 环境则保持内联渲染路径。

组件内部流程在 `src/commands/mobile/mobile.tsx` 的 `MobileQRCode`。组件初始化 `platform` 为 `ios`，初始化 `qrCodes` 为空字符串。`useEffect()` 首次挂载时并行调用 `qrToString()`，提前生成 iOS 和 Android 两份终端 UTF-8 二维码，避免切换平台时闪烁。当前展示内容由 `platform` 决定：先取 `PLATFORMS[platform].url`，再取 `qrCodes[platform]`，把二维码字符串按换行拆成多行 `<Text>` 输出。

交互阶段由 `handleKeyDown()` 和 `useKeybinding()` 处理。按 `tab`、`left`、`right` 会在 `ios` 与 `android` 之间切换；按 `q` 或 `ctrl+c` 会调用 `onDone()` 关闭面板；`useKeybinding('confirm:no', handleClose, { context: 'Confirmation' })` 让通用的取消/否定按键也能关闭该命令。界面底部会显示当前平台选择状态、切换提示和当前平台下载地址；真实地址不在本文展开。

## 推荐阅读顺序

1. 先读 `src/commands/mobile/index.ts`，确认这是一个 `local-jsx` 斜杠命令，而不是 Commander 子命令或后台任务。

2. 再读 `src/commands.ts` 中对 `mobile` 的导入位置，理解它如何进入全局命令集合。这里不需要通读整个文件，只要知道它是内置命令聚合点即可。

3. 接着读 `src/screens/REPL.tsx` 中 `matchingCommand.load()`、`mod.call(...)`、`setToolJSX(...)` 附近的逻辑，理解本地 JSX 命令如何被加载和挂载。

4. 最后读 `src/commands/mobile/mobile.tsx`，重点看 `PLATFORMS`、`MobileQRCode`、`useEffect()`、`handleKeyDown()` 和导出的 `call()`。这几个点已经覆盖该目录的主要行为。

如果只是学习如何新增一个简单本地 UI slash command，`src/commands/mobile` 是很好的最小样例：声明对象很短，UI 状态也很少，比 `/config`、`/agents` 这类复杂命令更容易建立心智模型。

## 常见误区

不要把 `/mobile` 理解成 `src/main.tsx` 里的顶层 CLI 子命令。它不是 `claude mobile` 这种 Commander 命令，而是 REPL 内用户输入 `/mobile` 后触发的 slash command。

不要以为 `/ios` 和 `/android` 会分别直接打开对应平台或设置初始平台。根据当前实现，别名只用于命令匹配，组件内部仍默认 `platform` 为 `ios`，平台切换由面板内按键完成。

不要以为二维码是在每次切换平台时重新生成。实现中 `useEffect()` 在组件挂载后一次性并行生成两份二维码，切换时只是读取已经缓存到 `qrCodes` 状态里的字符串。

不要把它归入网络请求功能。`mobile.tsx` 使用 `qrcode` 包把静态下载地址转成终端字符二维码，并没有向应用商店或外部服务发请求。二维码内容里包含外部下载地址，但生成过程本身是本地计算。

不要忽略 `onDone`。本地 JSX 命令能否正确退出，依赖组件在合适的按键事件里调用 `onDone()`。`/mobile` 中 `q`、`ctrl+c` 和通用 `confirm:no` 都会走这个关闭路径。

不要把这个目录当作移动端集成层。它不包含移动端认证、设备绑定、push、deep link 或远程控制逻辑；它只是下载入口展示面板。
