# 文件：packages/agent/src/harness/agent-harness.ts

## 一句话定位

`packages/agent/src/harness/agent-harness.ts` 定义 `AgentHarness`，它是 `packages/agent` 中位于低层 `runAgentLoop()` 之上的编排层，负责把一次用户输入、模型流式调用、工具、会话持久化、资源、压缩、分支摘要、事件 hook 统一成可被上层应用调用的稳定 API。

## 它暴露/定义了什么

这个文件主要暴露 `AgentHarness<TSkill, TPromptTemplate, TTool>` 泛型类。泛型允许宿主应用自定义 `Skill`、`PromptTemplate` 和 `AgentTool` 的具体形状，同时仍复用 harness 的生命周期管理。

它还定义了一批内部辅助逻辑：`createUserMessage()` 构造用户消息，`createFailureMessage()` 构造失败 assistant 消息，`cloneStreamOptions()`、`mergeHeaders()`、`applyStreamOptionsPatch()` 处理流式调用配置，`normalizeHarnessError()`、`normalizeHookError()` 把 session、compaction、branch summary、hook 等子系统错误规整为 `AgentHarnessError`。这些函数不是业务入口，但对外部错误语义和 provider 请求配置有直接影响。

类内部维护的核心状态包括：`session`、`phase`、`runAbortController`、`runPromise`、`pendingSessionWrites`、`model`、`thinkingLevel`、`systemPrompt`、`streamOptions`、`resources`、`tools`、`activeToolNames`，以及 steering、follow-up、next-turn 队列和事件 handler 表。

## 谁调用它

源码中 `packages/agent/src/index.ts` 重新导出该文件，因此它是 `@earendil-works/pi-agent` 对外 API 的一部分。根据当前片段和搜索结果，直接调用者包括测试与示例：`packages/agent/test/harness/agent-harness.test.ts`、`packages/agent/test/harness/agent-harness-stream.test.ts`、`packages/agent/test/scratch/simple.ts`。文档 `packages/agent/docs/agent-harness.md`、`packages/agent/docs/observability.md`、`packages/agent/docs/hooks.md` 也围绕它描述生命周期、可观测性和 hook 设计。

从 API 形态推断，真实宿主通常会创建 `new AgentHarness({ env, session, model, tools, resources, streamOptions, ... })`，然后调用 `prompt()`、`skill()`、`promptFromTemplate()`、`compact()`、`navigateTree()`、`steer()`、`followUp()` 等方法驱动一次或多次 agent 运行。

## 它调用谁

最关键的下游是 `../agent-loop.ts` 的 `runAgentLoop()`，它承担真正的 agent 循环执行。harness 负责准备上下文、模型、工具、消息和 stream 函数，再交给 agent loop。

模型请求侧，它引入 `@earendil-works/pi-ai` 的 `streamSimple()`、`Model`、`UserMessage`、`AssistantMessage` 等类型和函数。会话与消息转换侧，它调用 `./messages.ts` 的 `convertToLlm()`。上下文压缩侧，它调用 `./compaction/compaction.ts` 的 `prepareCompaction()`、`compact()` 和 `DEFAULT_COMPACTION_SETTINGS`。分支摘要侧，它调用 `./compaction/branch-summarization.ts` 的 `collectEntriesForBranchSummary()`、`generateBranchSummary()`。资源调用侧，它使用 `formatSkillInvocation()` 和 `formatPromptTemplateInvocation()` 把 skill/template 变成用户消息文本。

## 核心流程

一次普通 `prompt()` 的高层流程是：先检查 `phase` 必须是 `idle`，否则抛出 `AgentHarnessError("busy")`；再把文本和图片包装成 `UserMessage`，创建本轮 `turnState` 快照，包括 session 消息、资源、stream options、系统提示词、模型、thinking level、工具和 active tools；然后进入 `turn` phase，调用 `runAgentLoop()`。

运行期间，harness 提供自定义 `StreamFn`。该函数会合并当前 `streamOptions`、认证 header、hook 修改结果，再调用 `streamSimple()` 发起模型流式请求。工具调用、agent 事件、模型输出等由 agent loop 产生，harness 负责把它们转成外部可订阅事件并维护会话写入顺序。若运行成功，最后一个 assistant 消息必须存在；若失败或中止，则通过 `createFailureMessage()` 落一条失败 assistant 消息，避免 session 缺失本轮结果。

`skill()` 和 `promptFromTemplate()` 根据当前片段推断是 `prompt()` 的语义包装：先从 `resources.skills` 或 `resources.promptTemplates` 中查找名称，再格式化 invocation 文本，最后走同一套 turn 流程。依据是文件导入了对应 formatter，且搜索结果显示未知 skill/template 会抛 `invalid_argument`。

`compact()` 是结构性操作，要求 harness 空闲；它准备可压缩 transcript，拿到 auth 后调用压缩实现，期间发出 compaction 相关 hook，完成后更新 session。`navigateTree()` 也是空闲期结构操作，用于切换 session 树节点，并可按需生成 branch summary。

## 关键函数的高层作用

`constructor()` 建立 harness 初始运行环境，注册工具，校验工具名和 active tool 名不能重复且必须存在，设置模型、thinking level、队列模式、资源和 stream options。

`emitOwn()`、`emitAny()`、`emitHook()` 是事件系统核心。`emitAny()` 面向通配订阅者，`emitHook()` 面向可返回结果的 hook，并采用“最后一个非 undefined 结果生效”的语义。hook 抛错会被包装成 `AgentHarnessError("hook")`。

`createTurnState()` 根据当前 harness 状态生成本轮不可随意漂移的快照，降低运行中配置变化影响已启动 turn 的风险。

`createStreamFn()` 是 provider 请求出口，负责把模型请求参数、stream options、认证信息、hook patch 合并后交给 `streamSimple()`。

`prompt()`、`skill()`、`promptFromTemplate()` 是主要用户入口，分别处理直接提示词、skill 调用和模板调用。

`steer()`、`followUp()` 根据当前片段推断用于运行中追加用户消息；它们要求 harness 非 idle，并按 `QueueMode` 控制排队行为。依据是类中存在 `steerQueue`、`followUpQueue`、对应 queue mode，以及搜索结果显示 idle 时会抛 `invalid_state`。

`compact()`、`navigateTree()` 是 session 结构维护入口，风险高于普通 turn，因为它们会重写或移动 transcript 上下文。

## 修改风险

最高风险在生命周期和持久化顺序。`phase`、`runPromise`、`pendingSessionWrites`、abort controller、next-turn 队列共同保证运行中不会出现并发结构操作、乱序写 session、重复落 assistant 消息。随意改变这些状态的更新时机，容易引入隐性竞态。

第二类风险是 hook 语义。外部扩展可能依赖事件顺序、hook 可修改 stream options、hook 错误归类为 `"hook"`、以及提交后 hook 失败不回滚的行为。修改 `emitHook()`、`applyStreamOptionsPatch()` 或事件发射点，需要同步检查相关测试和文档。

第三类风险是模型请求配置。`headers`、`metadata`、auth、provider hook patch 的合并规则会影响鉴权、缓存、重试和观测数据。尤其是 `undefined` 在 patch 中表示删除字段，这类语义不能简单替换成浅合并。

第四类风险是资源与工具快照。运行中修改 `resources`、`tools`、`activeToolNames` 如果影响已启动 turn，可能导致模型看到的工具列表与实际可执行工具不一致。这里应保持“启动 turn 时冻结快照”的思路。

最后，`compact()` 和 `navigateTree()` 会改变 session 历史结构，且依赖 branch summary 与 compaction 子系统。修改时应重点验证空闲态限制、错误归类、目标 entry 查找、摘要失败处理，以及与普通 prompt 并发时的 busy 行为。
