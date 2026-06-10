# 文件：ui-tui/src/entry.tsx

## 一句话定位

`ui-tui/src/entry.tsx` 是 Hermes TUI 的 Node/Ink 进程入口：它不负责具体聊天 UI 或业务状态，而是负责启动终端运行环境、拉起/连接 Python `tui_gateway`、安装退出与内存保护机制，最后把 `App` 挂到 `@hermes/ink` 渲染器上。

## 它暴露/定义了什么

这个文件没有导出公共函数、组件或类型，主要通过顶层代码执行副作用完成启动。它定义了一个局部辅助函数 `dumpNotice`，用于把内存快照和 heap dump 结果格式化为 stderr 提示。除此之外，核心“定义”是启动顺序本身：TTY 检查、终端尺寸修正、终端模式重置、网关客户端创建与启动、生命周期钩子注册、内存监控启动、动态导入 Ink 与 React App、调用 `ink.render()`。

文件开头的 shebang 指定使用 Node，并打开较大的 V8 heap 与 `--expose-gc`，说明该入口预期直接作为可执行脚本运行，也要配合内存诊断能力使用。

## 谁调用它

从 `ui-tui/package.json` 看，`npm start` 执行 `tsx src/entry.tsx`，`npm run dev` 也会 watch 这个入口。根据仓库说明，用户运行 `hermes --tui` 时会启动这个 TUI；仪表盘 `/chat` 也会嵌入真实的 `hermes --tui`，因此间接依赖同一个入口。根据当前片段推断，生产构建脚本会把该入口打包或作为 bundle 入口使用，依据是 `package.json` 中存在 `build` 脚本和 `src/entry.tsx` 的 start/dev 入口配置。

## 它调用谁

它直接依赖 `GatewayClient` 管理前端 Node 进程和 Python 网关之间的通信。`GatewayClient.start()` 会根据环境决定连接已有 WebSocket 网关，或 spawn `python -m tui_gateway.entry`，并处理 stdout/stderr 上的 JSON-RPC 事件。

它还调用多个启动期工具：`clampStdoutDimensions()` 修正异常终端尺寸；`resetTerminalModes()` 清理鼠标、焦点、粘贴等终端模式；`setupGracefulExit()` 注册信号和异常清理；`startMemoryMonitor()` 定期检查 Node 内存并在高水位生成 heap dump；`performHeapDump()` 支持启动时手动 dump；`recordParentLifecycle()` 写父进程生命周期日志；`openExternalUrl()` 处理 Ink 链接点击。

UI 层通过动态导入 `@hermes/ink`、`./app.js`、`./lib/perfPane.js`、`./lib/fpsStore.js` 完成。`App` 继续调用 `useMainApp(gw)`，再把状态传给 `AppLayout`，这说明 `entry.tsx` 只传入网关对象，不直接管理 transcript、composer、slash command 或会话状态。

## 核心流程

第一步是环境防御：如果 `stdin` 不是 TTY，输出 `hermes-tui: no TTY` 后正常退出，避免在非交互环境中启动全屏 TUI。随后修正 stdout 的列/行数，防止 WSL 等环境报告离谱尺寸影响 Ink 布局。接着重置终端模式，并根据 `TERMUX_TUI_MODE` 决定只换行还是清屏；这体现了 Termux 用户需要保留历史输出，桌面终端则需要干净的 AlternateScreen 启动体验。

第二步创建 `GatewayClient` 并立即 `gw.start()`。这个顺序很关键：文件后面才动态导入 Ink 和 App，意图是让 Python 网关尽早启动，减少冷启动等待。`memoryMonitor.ts` 的注释也印证了启动路径在刻意避免过早加载完整 Ink bundle。

第三步安装退出清理。收到 `SIGINT`、`SIGTERM`、`SIGHUP` 时，入口会记录父进程生命周期、重置终端模式，并通过 `gw.kill('graceful-exit-cleanup')` 结束网关。未捕获异常和未处理 Promise rejection 只记录错误，不在这里展开业务恢复。

第四步启动内存监控。高内存时写 heap dump 提示；critical 时记录日志、重置终端模式、输出诊断信息并 `process.exit(137)`，用明确退出码表达 OOM 保护。`beforeExit` 中停止监控定时器，避免进程收尾阶段继续持有资源。

最后动态导入 Ink、App、性能帧日志和 FPS 追踪模块。若性能日志或 FPS 追踪启用，就构造 `onFrame` 回调；否则保持 `undefined`，让默认渲染路径不承担额外计时成本。最终 `ink.render(<App gw={gw} />)`，设置 `exitOnCtrlC: false`，把 Ctrl-C 生命周期交给前面的 graceful exit 机制，并把超链接点击交给 `openExternalUrl()`。

## 关键函数的高层作用

`dumpNotice` 是很薄的格式化函数，把 `MemorySnapshot` 和 `HeapDumpResult` 转成统一的 stderr 文本，辅助内存高水位和 critical 分支复用。

`setupGracefulExit(...)` 在这里承担进程收口职责：保证信号退出时先恢复终端，再关闭网关，避免留下异常终端模式或孤儿 Python 子进程。

`startMemoryMonitor(...)` 是运行期保护网。它不参与 UI 状态，但在 Ink/React 长会话内存上涨时触发缓存清理、heap dump 和必要的 137 退出，优先保留可诊断信息。

`ink.render(...)` 是 UI 交接点。它把已经启动的 `GatewayClient` 注入 `App`，并配置帧事件与链接点击。之后主要控制权转移到 `useMainApp`、`GatewayProvider`、`AppLayout` 等组件和 hook。

## 修改风险

最大风险是启动顺序。`gw.start()` 早于 Ink/App 动态导入不是随意安排；如果把大量 React/Ink 模块提前静态导入，可能增加冷启动时间，也可能延迟 Python 网关的 `gateway.ready`。同理，`forceTruecolor.js` 注释要求必须第一 import，移动它可能导致 chalk/supports-color 初始化时机错误。

终端清理也很敏感。删除或延后 `resetTerminalModes()`，会让崩溃后的鼠标追踪、焦点事件或 bracketed paste 状态污染用户终端。修改清屏逻辑要注意 `TERMUX_TUI_MODE` 的特殊保留历史行为。

退出处理和 Ctrl-C 配置必须配套。`ink.render` 使用 `exitOnCtrlC: false`，依赖 `setupGracefulExit` 接管信号；若只改其中一边，可能出现 Ctrl-C 不退出、重复退出、网关未关闭，或终端未恢复。

内存监控分支涉及诊断和退出码。`process.exit(137)`、heap dump、`recordParentLifecycle()` 的组合用于区分 Node OOM、信号退出和网关 EOF。随意改 stderr 文案问题不大，但改变退出码或移除生命周期记录，会降低线上 crash 分析能力。

最后，`onHyperlinkClick` 看似 UI 细节，实际补偿了鼠标追踪模式下终端原生 URL 点击失效的问题。修改鼠标/链接相关行为时，需要同时验证普通桌面终端、Termux、dashboard PTY 嵌入场景。
