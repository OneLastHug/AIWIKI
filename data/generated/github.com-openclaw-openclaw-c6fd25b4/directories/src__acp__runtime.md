# 子系统：src/acp/runtime

## 解决什么问题

`src/acp/runtime` 是 ACP 后端运行时的“契约层”和“轻量注册层”。它不直接实现 ACP 协议服务器，也不负责把消息投递到网关；它负责定义 core 与具体 ACP backend 之间怎样创建会话、发送 turn、流式返回事件、查询能力、设置运行时选项、取消和关闭。

从代码关系看，ACP 的上层控制逻辑在 `src/acp/control-plane`，协议接入与 SDK 翻译在 `src/acp/translator.ts`、`src/acp/server.ts` 等文件；而 `src/acp/runtime` 提供的是这些模块可以依赖的稳定接口。具体 backend 通过 `registerAcpRuntimeBackend` 注册为 `AcpRuntimeBackend`，上层通过 `requireAcpRuntimeBackend` 取出可用实现，再调用 `AcpRuntime` 接口。

因此，这个目录解决的核心问题是：让 OpenClaw core 不直接绑定某个 ACP backend 实现，同时仍能统一处理会话身份、错误码、能力探测、可用性判断和持久化元数据读写。

## 相关目录和文件

`src/acp/runtime/types.ts` 是中心文件，定义 `AcpRuntime`、`AcpRuntimeHandle`、`AcpRuntimeEvent`、`AcpRuntimeTurn`、`AcpRuntimeCapabilities` 等契约。

`src/acp/runtime/registry.ts` 管理 backend 注册表，提供 `registerAcpRuntimeBackend`、`getAcpRuntimeBackend`、`requireAcpRuntimeBackend`。它用 process/global singleton 保存注册状态，注释说明这是为了让 bundled plugin、core、Vitest、Jiti 等不同上下文共享同一份 backend map。

`src/acp/runtime/session-identity.ts` 负责把 runtime handle、runtime status、session meta 中的各种 id 合并为统一的 `SessionAcpIdentity`，并判断 pending/resolved 状态。`src/acp/runtime/session-identifiers.ts` 则把这些 id 渲染成状态行或 thread 详情行。

`src/acp/runtime/session-meta.ts` 是运行时与 session store 的连接点，读取、列举和更新 session entry 中的 `acp` 元数据。它依赖 `src/config/sessions/*` 和 `src/routing/session-key.ts`。

`src/acp/runtime/errors.ts` 与 `src/acp/runtime/error-text.ts` 定义统一错误码、错误归一化、cause chain 渲染和面向用户的 next step 文案。`src/acp/runtime/availability.ts` 用策略配置、sandbox 状态和 backend health 判断 ACP spawn 是否可用。`src/acp/runtime/adapter-contract.testkit.ts` 是 adapter 实现的契约测试工具。

## 核心对象

`AcpRuntime` 是最关键的接口。它要求 backend 至少实现 `ensureSession`、`runTurn`、`cancel`、`close`，可选实现 `startTurn`、`getCapabilities`、`getStatus`、`setMode`、`setConfigOption`、`doctor`、`prepareFreshSession`。其中 `startTurn` 是较新的 turn API，允许事件流和最终结果分离；`runTurn` 是兼容性的 async iterable 事件流接口。

`AcpRuntimeHandle` 是上层后续调用 runtime 的句柄，包含 `sessionKey`、`backend`、`runtimeSessionName`，并可携带 `cwd`、`acpxRecordId`、`backendSessionId`、`agentSessionId`。这些字段会被 `session-identity.ts` 提取并写回 session meta。

`AcpRuntimeEvent` 是 runtime 向上层输出的事件联合类型，包含 `text_delta`、`status`、`tool_call`、`done`、`error` 等。控制平面会把它们交给 `src/acp/control-plane/manager.turn-stream.ts` 消费，再继续传给调用方或协议层。

`AcpRuntimeError` 是本目录的统一错误对象，错误码目前包括 `ACP_BACKEND_MISSING`、`ACP_BACKEND_UNAVAILABLE`、`ACP_BACKEND_UNSUPPORTED_CONTROL`、`ACP_DISPATCH_DISABLED`、`ACP_INVALID_RUNTIME_OPTION`、`ACP_SESSION_INIT_FAILED`、`ACP_TURN_FAILED`。

## 运行流程

典型 ACP 会话初始化从 `src/acp/control-plane/manager.core.ts` 的 `AcpSessionManager.initializeSession` 开始：先根据配置和 session key 解析目标 backend，然后通过 `requireRuntimeBackend` 取得注册的 `AcpRuntimeBackend`，再调用 `runtime.ensureSession` 创建或恢复后端会话。返回的 `AcpRuntimeHandle` 会被转换为 identity，并与 backend、agent、mode、cwd、runtimeOptions 一起写入 session store 的 `acp` 元数据。

执行一次 turn 时，`AcpSessionManager.runTurn` 会先解析 session meta，确保或复用 runtime handle，然后调用 `applyRuntimeControls` 把 mode、model、thinking、timeout 等运行时选项同步到 backend。随后 `consumeAcpTurnStream` 根据 backend 是否提供 `startTurn` 选择新旧事件消费路径：新路径等待 `turn.events` 与 `turn.result`，旧路径直接消费 `runTurn`。事件中的输出会更新任务进度，`done` 或失败结果会决定 turn 是否完成。

turn 结束后，manager 会通过 `reconcileRuntimeSessionIdentifiers` 尝试从 handle 和 `getStatus` 返回值中刷新 `agentSessionId`、`backendSessionId`、`acpxRecordId`，并写回 session meta。`oneshot` 会话完成后会关闭 runtime 并清缓存；`persistent` 会话则可在后续 turn 复用。

## 上下游依赖

上游主要是具体 ACP backend 或 bundled plugin，它们实现 `AcpRuntime` 并注册到 `registry.ts`。根据当前片段推断，默认提示中提到的 acpx runtime plugin 是一个主要 backend，因为错误文案提示安装和启用 acpx runtime plugin，且 handle/status 字段中多次出现 `acpxRecordId`。

下游主要是 `src/acp/control-plane/manager.core.ts`、`src/acp/control-plane/manager.runtime-controls.ts`、`src/acp/control-plane/manager.turn-stream.ts`、`src/acp/control-plane/manager.identity-reconcile.ts`。此外，agent 工具和能力展示也会读取 runtime 可用性，例如 `src/agents/tools/sessions-spawn-tool.ts`、`src/agents/subagent-spawn.ts`、`src/agents/cli-runner/helpers.ts` 会通过 `isAcpRuntimeSpawnAvailable` 判断是否展示或启用 ACP spawn 能力。

配置和持久化依赖集中在 `src/config/sessions/*`、`src/config/types.openclaw.ts`、`src/config/config.ts`。错误与日志依赖 `src/infra/errors.ts`、`src/logging/redact.ts`，用于保留可诊断信息同时避免泄露敏感内容。

## 修改时最容易踩的坑

第一，不能把具体 backend 策略写进 core runtime 契约。`types.ts` 应保持通用，backend 特有字段只能作为可选标识或 `details` 里的扩展信息，否则会破坏插件边界。

第二，session identity 的状态机很敏感。`ensureSession` 早期可能只有 record id，真正的 `agentSessionId` 要等首个回复或 status 才出现，所以 `pending` 和 `resolved` 合并逻辑不能随意简化。否则会影响 resume、状态展示和 thread 详情。

第三，`startTurn` 与 `runTurn` 两条路径都要保持可用。新增事件或终止语义时，需要同时考虑 `AcpRuntimeTurn.result`、事件流里的 `done/error`，以及 `consumeAcpTurnStream` 对 terminal event 的判断。

第四，错误必须走 `AcpRuntimeError` 归一化。直接抛普通 Error 会丢失错误码，影响 failover、用户提示、状态记录和测试断言。包含外部请求细节时也要通过现有 redaction 路径处理。

第五，注册表是进程级共享状态。测试中需要使用 `testing.resetAcpRuntimeBackendsForTests()` 清理，否则不同测试上下文会互相污染。

第六，能力探测不是纯声明。`manager.runtime-controls.ts` 会把 `getCapabilities`、方法存在性、必要时 `getStatus` 中的 config option keys 合并起来判断支持情况。改动 `configOptionKeys` 或控制名时，容易让 `/acp set`、turn 前控制同步和状态展示出现不一致。

## 推荐阅读顺序

1. 先读 `src/acp/runtime/types.ts`，建立 `AcpRuntime`、handle、event、turn result 的整体模型。
2. 再读 `src/acp/runtime/registry.ts` 和 `src/acp/runtime/availability.ts`，理解 backend 如何注册、选择和判断可用。
3. 然后读 `src/acp/runtime/session-identity.ts`、`src/acp/runtime/session-identifiers.ts`、`src/acp/runtime/session-meta.ts`，理解 session id 怎样从 runtime 流向持久化状态和用户展示。
4. 接着读 `src/acp/runtime/errors.ts`、`src/acp/runtime/error-text.ts`，掌握错误码和错误渲染契约。
5. 最后跳到 `src/acp/control-plane/manager.core.ts`、`src/acp/control-plane/manager.turn-stream.ts`、`src/acp/control-plane/manager.runtime-controls.ts`，观察 runtime 契约在初始化、执行 turn、应用控制和关闭会话中的真实调用方式。
6. 如果要实现新 backend，再读 `src/acp/runtime/adapter-contract.testkit.ts` 和同目录测试文件，用测试契约反推 adapter 必须满足的行为。
