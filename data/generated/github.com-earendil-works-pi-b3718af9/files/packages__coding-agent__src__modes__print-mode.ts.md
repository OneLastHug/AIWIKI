# 文件：packages/coding-agent/src/modes/print-mode.ts
## 一句话定位
这个文件定义了 coding-agent 的“单次打印”模式入口：接收一组 prompt，把它们发给当前会话，按 `text` 或 `json` 两种格式把结果输出到标准输出，然后退出。根据当前片段推断，它是 CLI 里非交互式模式的核心执行器。

## 它暴露/定义了什么
它主要暴露两个东西：`PrintModeOptions` 和 `runPrintMode()`。  
`PrintModeOptions` 只描述这一路径需要的输入：输出模式、附加消息、初始消息和初始图片。  
`runPrintMode(runtimeHost, options)` 是真正的执行函数，返回 `Promise<number>`，以退出码表达成功或失败。

## 谁调用它
从 `packages/coding-agent/src/main.ts` 可以直接看到，CLI 根据 `appMode` 分支时会调用 `runPrintMode()`，也就是 `pi -p`、`pi --mode json` 这类单次输出入口。  
它还被 `packages/coding-agent/src/modes/index.ts` 重新导出，说明这是模式层公共 API 的一部分。根据当前片段推断，外部通常不会直接依赖它的内部细节，而是通过主入口走到这里。

## 它调用谁
它的下游依赖比较集中，主要有这些：
- `AgentSessionRuntime`：取出 `session`，注册重绑定逻辑，创建/切换/分叉会话。
- `session.bindExtensions()`：把运行模式、命令上下文动作和错误回调注入扩展系统。
- `session.subscribe()`：在 `json` 模式下把事件流原样写到 stdout。
- `session.prompt()`：发送初始消息和后续消息。
- `writeRawStdout()`、`flushRawStdout()`：绕过常规输出缓冲，保证结构化输出不被污染。
- `killTrackedDetachedChildren()`：收到退出信号时清理子进程。
- `runtimeHost.dispose()`：结束时释放运行时资源。

## 核心流程
整体流程是“准备运行时 -> 绑定扩展 -> 发送 prompt -> 输出结果 -> 清理资源”。

先初始化状态，注册 `SIGTERM`，在非 Windows 再加 `SIGHUP`。信号触发时会先杀掉跟踪的 detached 子进程，再异步释放运行时并退出。随后调用 `runtimeHost.setRebindSession()`，把会话重绑逻辑挂进去，这一步很关键，因为后续 reload、switch session、fork 等动作都要靠它保持上下文一致。

接着进入 `rebindSession()`：拿到当前 `session`，调用 `bindExtensions()`，把 `mode`、`waitForIdle`、`newSession`、`fork`、`navigateTree`、`switchSession`、`reload` 这些命令上下文动作注册进去。之后订阅会话事件；如果是 `json` 模式，每个事件都会以一行 JSON 直接写到 stdout。

正式执行时，`json` 模式会先输出 header（如果存在），然后发送 `initialMessage` 和 `messages`。`text` 模式则在所有 prompt 完成后读取最后一条 assistant message：如果 stop reason 是 `error` 或 `aborted`，打印错误并返回非零退出码；否则只把其中的文本内容写到 stdout。最后无论成功失败，都要注销信号监听、释放 runtime、刷新 stdout。

## 关键函数的高层作用
`runPrintMode()` 是唯一核心函数，职责很完整：协调会话生命周期、绑定扩展接口、处理输入消息、选择输出格式、收尾清理。  
`disposeRuntime()` 负责幂等释放，避免重复清理。  
`registerSignalHandlers()` 负责把命令行进程的退出语义和运行时清理绑定起来。  
`rebindSession()` 则是这个文件最重要的桥接层，它把 `runtimeHost` 和 `session` 的能力转换成扩展系统可以消费的上下文动作。

## 修改风险
这个文件的修改风险偏高，因为它处在 CLI 输出链路的末端，任何变动都可能直接影响用户看到的文本、JSON 事件流和退出码。  
第一类风险是输出格式破坏：`json` 模式里多打一行日志、少 flush 一次、header 结构变化，都会让下游解析失败。  
第二类风险是会话生命周期问题：`subscribe()`、信号监听、`dispose()` 的清理顺序如果不稳，容易留下重复订阅、资源泄漏或进程无法退出。  
第三类风险是行为假设过强：当前 `text` 模式默认只看最后一条 assistant message，意味着如果最终输出结构变化，或者最后一条不是 assistant，就可能静默丢结果。  
第四类风险来自扩展绑定契约：`bindExtensions()` 里传入的 `mode`、`commandContextActions` 是和 `packages/coding-agent/src/core/agent-session.ts`、扩展运行器联动的，改接口要同步检查上游和下游。
