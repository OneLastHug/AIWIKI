# 目录：src/commands/session

## 它负责什么

`src/commands/session` 负责实现交互式 REPL 里的 `/session` 斜杠命令，用来在 Remote Mode 下展示当前远程会话的访问入口：终端里渲染一个远程会话面板，包含二维码和可在浏览器打开的会话 URL。它不是“会话管理”目录，也不负责创建、恢复、持久化或同步 Claude Code 会话；它只是一个很薄的展示型命令。

从实现形态看，它属于 `local-jsx` 命令：命令被触发后不会生成 prompt 内容交给模型，而是在本地 Ink UI 中渲染 React 组件。它依赖全局 AppState 中的 `remoteSessionUrl`，再通过 `qrcode` 包把 URL 转成 UTF-8 文本二维码。二维码生成失败时只记录 debug 日志，仍然展示 URL，因此二维码是增强体验，不是核心依赖。

这个命令只在 Remote Mode 下启用和显示。`index.ts` 通过 `getIsRemoteMode()` 控制 `isEnabled` 与 `isHidden`，所以普通本地模式下用户通常不会在命令列表里看到它。命令名是 `session`，别名是 `remote`，描述是 `Show remote session URL and QR code`。

## 直接子目录地图

这个目录没有直接子目录，只有两个文件：

`src/commands/session/index.ts`：命令注册入口。定义命令元数据，包括 `type: 'local-jsx'`、`name: 'session'`、`aliases: ['remote']`、启用条件、隐藏条件，以及懒加载实现模块 `./session.js`。

`src/commands/session/session.tsx`：命令 UI 实现。导出 `call`，内部渲染 `SessionInfo` 组件；组件读取 `remoteSessionUrl`，生成二维码，处理 ESC 关闭，并显示 Remote session 面板。

因此，这里不是一个复杂功能域，而是一个单命令目录。阅读时重点不在“目录分层”，而在它如何接入通用命令系统和 Remote Mode 状态。

## 关键入口

第一入口是 `src/commands/session/index.ts`。它把 `/session` 声明成一个可被命令系统识别的 `Command`：

`type: 'local-jsx'` 表示命令结果是本地 JSX UI。

`name: 'session'` 是用户输入 `/session` 时匹配的主命令名。

`aliases: ['remote']` 允许用户用 `/remote` 触发同一逻辑。

`isEnabled: () => getIsRemoteMode()` 表示只有 Remote Mode 当前为真时命令才可用。

`isHidden` getter 返回 `!getIsRemoteMode()`，让它在非 Remote Mode 下从帮助、补全或命令展示中隐藏。

`load: () => import('./session.js')` 使用懒加载，只有用户真正调用命令时才加载 React UI 与二维码依赖。

第二入口是 `src/commands/session/session.tsx` 里的 `call`：

`call(onDone)` 返回 `<SessionInfo onDone={onDone} />`，符合 `LocalJSXCommandCall` 类型约定。`SessionInfo` 使用 `useAppState(s => s.remoteSessionUrl)` 读取当前远程会话 URL。若没有 URL，它会显示“Not in remote mode”提示；若有 URL，则异步调用 `qrToString(url, { type: 'utf8', errorCorrectionLevel: 'L' })` 生成终端可显示的二维码文本。

关闭入口是 `useKeybinding('confirm:no', onDone, { context: 'Confirmation' })`。根据命名和使用方式，这里的 `confirm:no` 对应 ESC 或取消类按键；按下后调用命令系统传入的 `onDone`，让上层清理本地 JSX 面板。

## 主流程位置

命令注册主流程在 `src/commands.ts`。该文件导入 `session`，并把它放进 `COMMANDS()` 返回的内置命令数组中。随后 `getCommands(cwd)` 会汇总内置命令、skills、plugins、workflows 等来源，并通过 `meetsAvailabilityRequirement` 与 `isCommandEnabled` 做过滤。由于 `/session` 的 `isEnabled` 依赖 `getIsRemoteMode()`，所以它是否出现在最终命令集合中取决于当前是否处于 Remote Mode。

命令执行主流程在 `src/utils/processUserInput/processSlashCommand.tsx` 的 `local-jsx` 分支。用户输入 `/session` 后，通用斜杠命令处理器匹配到命令对象，调用 `command.load()` 懒加载 `src/commands/session/session.tsx`，再调用模块导出的 `call(onDone, context, args)`。如果返回 JSX，处理器会通过 `setToolJSX` 把它挂到 REPL 的本地命令 UI 槽位里，并隐藏输入框。

还有一个相邻流程在 `src/utils/handlePromptSubmit.ts`，用于处理 `immediate` 类型的 `local-jsx` 命令，即模型运行中也能立即弹出的命令。`/session` 当前没有声明 `immediate: true`，所以它主要走普通斜杠命令流程；这里可作为理解 `local-jsx` 命令整体机制的参考，而不是 `/session` 的主要路径。

Remote Mode 状态来源分布在相邻模块。`src/bootstrap/state.ts` 提供 `getIsRemoteMode()`；`src/state/AppStateStore.ts` 定义 `remoteSessionUrl` 的默认状态；`src/main.tsx` 中包含 Remote Mode 初始化逻辑，会创建或取得远程会话，并把 `remoteSessionUrl` 注入初始 AppState。根据当前片段推断，`src/commands/session` 不直接创建 URL，而是消费这些上游状态，依据是它只读取 `useAppState(s => s.remoteSessionUrl)`，没有网络请求或会话创建代码。

## 推荐阅读顺序

1. 先读 `src/commands/session/index.ts`，确认这是一个受 Remote Mode 控制的 `local-jsx` 命令，并记住命令名 `/session` 与别名 `/remote`。

2. 再读 `src/commands/session/session.tsx`，关注 `SessionInfo` 的三个核心动作：读取 `remoteSessionUrl`、生成二维码、通过 `onDone` 关闭界面。

3. 接着看 `src/commands.ts` 中 `session` 的导入和 `COMMANDS()` 数组位置，理解它如何进入全局命令集合，以及为什么 `isEnabled` 会影响最终可见性。

4. 然后看 `src/utils/processUserInput/processSlashCommand.tsx` 的 `local-jsx` 分支，理解命令被用户输入触发后，如何从 `load()` 到 `call()`，再到 `setToolJSX` 渲染在 REPL 中。

5. 最后按需查看 Remote Mode 上游：`src/bootstrap/state.ts` 的 `getIsRemoteMode()`、`src/state/AppStateStore.ts` 的 `remoteSessionUrl` 字段、`src/main.tsx` 中 Remote Mode 初始化片段。这里能帮助回答“URL 从哪里来”，但不是理解 `/session` UI 的必读起点。

## 常见误区

`src/commands/session` 不是会话恢复功能。历史会话恢复、选择旧会话、按 session id resume 等逻辑不在这里，相关功能应去看 `src/commands/resume`、主 REPL 状态和消息历史模块。

`/session` 也不是 Remote Control Server 的主入口。它只展示当前 Remote Mode 会话入口；Remote Control、Bridge、CCR、WebSocket 或服务端会话创建逻辑位于 `src/bridge`、`src/hooks/useRemoteSession.ts`、`src/services/api/sessionIngress.ts`、`src/main.tsx` 等相邻区域。

不要把 `aliases: ['remote']` 理解成顶层 CLI 的 `remote`、`remote-control` 或 `bridge` 子命令。这里的 `/remote` 是 REPL 内的斜杠命令别名，只在命令系统中指向 `/session`。

不要期望二维码生成失败会导致命令失败。`session.tsx` 明确把二维码视为非关键能力：失败只写 `logForDebugging`，URL 仍然展示。

不要在非 Remote Mode 下调试它的可见性问题。`index.ts` 同时用 `isEnabled` 和 `isHidden` 依赖 `getIsRemoteMode()`，所以普通模式下它被隐藏是设计行为。若强行触发到 UI 实现层，`SessionInfo` 也会因为缺少 `remoteSessionUrl` 显示“Not in remote mode”的提示。
