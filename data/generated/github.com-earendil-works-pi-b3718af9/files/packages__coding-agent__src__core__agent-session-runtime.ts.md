# 文件：packages/coding-agent/src/core/agent-session-runtime.ts

## 一句话定位

`agent-session-runtime.ts` 是 `coding-agent` 会话运行时的生命周期协调层：它把当前 `AgentSession`、绑定到当前 `cwd` 的 `AgentSessionServices`、`SessionManager` 和扩展事件串起来，负责 `/new`、`/resume`、`/fork`、`/import`、退出等会话切换流程。

## 它暴露/定义了什么

这个文件主要定义并导出：

- `CreateAgentSessionRuntimeResult`：创建运行时后的结果，继承 `CreateAgentSessionResult`，额外带上 `services` 和 `diagnostics`。
- `CreateAgentSessionRuntimeFactory`：运行时工厂类型。调用方传入 `cwd`、`agentDir`、`SessionManager`、可选 `sessionStartEvent` 和 `projectTrustContext`，返回完整会话运行时组件。
- `SessionImportFileNotFoundError`：`/import` 指向不存在 JSONL 文件时抛出的专用错误。
- `AgentSessionRuntime`：核心类，持有当前 `AgentSession`、当前 `AgentSessionServices`、诊断信息、模型 fallback 信息，并提供会话替换方法。
- `createAgentSessionRuntime`：初始运行时创建入口。
- 末尾从 `agent-session-services.ts` 再导出若干服务创建相关类型和函数，方便上层统一从 runtime 模块取用。

## 谁调用它

直接调用者主要在 `packages/coding-agent/src/main.ts`：这里构造 `CreateAgentSessionRuntimeFactory`，然后调用 `createAgentSessionRuntime` 建立初始 runtime。之后 runtime 被交给不同模式使用。

运行模式侧包括 `packages/coding-agent/src/modes/interactive/interactive-mode.ts`、`packages/coding-agent/src/modes/print-mode.ts`、`packages/coding-agent/src/modes/rpc/rpc-mode.ts`。其中交互模式最依赖它，因为 `/new`、`/resume`、`/fork`、`/import` 这类命令需要替换当前会话。测试侧大量覆盖在 `packages/coding-agent/test/suite/agent-session-runtime.test.ts`、`agent-session-runtime-events.test.ts`、`agent-session-branching.test.ts` 以及若干 regressions 中。

## 它调用谁

它调用 `SessionManager` 创建、打开、分支和读取会话；调用 `assertSessionCwdExists` 校验恢复或导入的会话目录是否可用；调用 `emitSessionShutdownEvent` 和 `session.extensionRunner.emit` 触发生命周期扩展事件；调用 `AgentSession.dispose()` 释放旧会话；调用传入的 `createRuntime` 工厂重新创建 `AgentSession` 与 `AgentSessionServices`。文件系统层面，它用 `existsSync`、`mkdirSync`、`copyFileSync` 处理 JSONL 导入，用 `resolvePath`、`resolve`、`join`、`basename` 规范路径。

## 核心流程

初始创建时，`createAgentSessionRuntime` 先用 `assertSessionCwdExists` 校验 `SessionManager` 的 cwd，再调用外部传入的 `createRuntime`。这个工厂负责真正构造 agent、服务、扩展、诊断等对象。函数最后把结果包进 `AgentSessionRuntime`，并保存同一个工厂供后续会话切换复用。

会话切换的共性流程是：先发 `session_before_switch` 或 `session_before_fork`，扩展可以返回 cancel；没有取消则确定目标 `SessionManager` 和目标 session file；随后对旧会话发 `session_shutdown`，运行同步的 `beforeSessionInvalidate`，再 `dispose` 旧 `AgentSession`；然后用 `createRuntime` 按新 cwd 和新 `SessionManager` 创建新运行时；最后 `apply` 替换内部引用，并通过 `rebindSession`、`withSession` 让宿主 UI 或调用方拿到新的 `ReplacedSessionContext`。

## 关键函数的高层作用

`switchSession` 处理恢复已有会话。它用 `SessionManager.open` 打开指定 JSONL，可接受 `cwdOverride`，并支持通过 `projectTrustContextFactory` 为新 cwd 生成信任上下文。它的风险点在于恢复前必须通过 cwd 校验，否则可能在错误项目目录中继续执行。

`newSession` 创建新会话。如果当前会话是持久化的，它沿用当前 session dir；否则创建内存会话。可选 `parentSession` 会记录父会话关系。`setup` 钩子会在新 session 创建后修改 `SessionManager`，并重新把 `buildSessionContext().messages` 写回 agent 状态。

`fork` 负责从历史条目分叉。`position: "at"` 以选中 entry 为叶子；默认 `"before"` 要求选中的是用户消息，并把分叉点设为其父节点，同时提取用户文本作为 `selectedText` 返回。持久化会话会打开当前文件并创建 branched session；内存会话则直接在当前 `SessionManager` 上分叉。

`importFromJsonl` 处理 JSONL 导入。它先解析输入路径并检查存在性，必要时创建 session dir，把外部文件复制到会话目录，再按恢复流程打开新 session。不存在文件会抛 `SessionImportFileNotFoundError`，而 cwd 缺失由 `assertSessionCwdExists` 相关错误处理。

`dispose` 是最终退出路径，只发送 `session_shutdown`，执行 UI 失效前钩子，然后释放当前 session，不再创建新 runtime。

`emitBeforeSwitch`、`emitBeforeFork`、`teardownCurrent`、`apply`、`finishSessionReplacement` 是生命周期辅助函数：分别负责扩展取消点、旧会话关闭、内部引用替换、以及替换后的宿主重绑定。

## 修改风险

最大风险是生命周期事件顺序。`session_shutdown`、`beforeSessionInvalidate`、`dispose`、`createRuntime`、`rebindSession`、`withSession` 的顺序影响扩展上下文、TUI 组件、RPC 持有的 session 引用；改错会导致旧扩展仍被使用、UI 绑定到废弃 session，或替换后上下文丢失。

第二类风险是 cwd 与 session file 的一致性。`switchSession`、`importFromJsonl`、`fork` 都可能切到不同 `cwd` 或不同 JSONL 文件，绕过 `assertSessionCwdExists`、错误使用 `this.cwd` / `sessionManager.getCwd()`，会让 agent 在错误目录执行命令。

第三类风险是持久化与内存会话分支逻辑不同。`fork` 对根节点、用户消息、`position`、`parentSession`、`createBranchedSession` 的处理比较敏感，轻微调整可能破坏历史树或回归分支测试。

第四类风险是取消语义。`session_before_switch` 和 `session_before_fork` 返回 cancel 时必须保证旧 session 未被销毁、文件未被复制或分支未被创建到不可恢复状态。`importFromJsonl` 当前在复制前触发取消点，这是有意保护。
