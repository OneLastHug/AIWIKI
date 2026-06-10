# 子系统：src/agents/pi-hooks

## 解决什么问题

`src/agents/pi-hooks` 是 OpenClaw 在 Pi agent 运行时周围加的一组“上下文管理钩子”。它不负责模型调用本身，也不直接定义 agent 主循环，而是在 Pi 的 extension/context/compaction 流程里插入 OpenClaw 需要的策略：上下文裁剪、压缩摘要保护、压缩指令解析、会话级运行时状态传递。

这个目录主要解决两个风险：第一，长会话里工具结果、图片、thinking block 等内容会让上下文膨胀，影响 token 预算和缓存命中；第二，自动 compaction 如果摘要结构不稳定、遗漏用户待办、丢失路径/URL/ID 等精确标识，会破坏后续回合连续性。这里的代码把这些策略做成 Pi hooks，而不是散落在主运行时里。

根据当前片段推断，这一层属于 OpenClaw 对上游 Pi SDK 的适配层：它依赖 `@earendil-works/pi-agent-core`、`@earendil-works/pi-ai`、`@earendil-works/pi-coding-agent` 的消息和 extension 类型，同时把 OpenClaw 自己的配置、插件摘要 provider、CJK token 估算、tool-call 修复、post-compaction context 等能力接进来。

## 相关目录和文件

核心入口有两个。`src/agents/pi-hooks/context-pruning.ts` 是 context pruning 的公开入口，默认导出 `context-pruning/extension.ts`，并重新导出 `pruneContextMessages`、`computeEffectiveSettings`、`DEFAULT_CONTEXT_PRUNING_SETTINGS`。`src/agents/pi-hooks/compaction-safeguard.ts` 是 compaction safeguard 的主体，负责组织摘要生成、质量保护、fallback、provider 接入和取消原因处理。

`src/agents/pi-hooks/context-pruning/` 是上下文裁剪子模块：`extension.ts` 注册 Pi 的 `context` 事件；`runtime.ts` 保存每个 `SessionManager` 对应的运行时参数；`pruner.ts` 具体改写消息数组；`settings.ts` 解析用户/运行时配置；`tools.ts` 根据 allow/deny glob 判断某个 tool 是否可裁剪。

`src/agents/pi-hooks/compaction-instructions.ts` 处理 compaction 指令优先级和默认指令；`src/agents/pi-hooks/compaction-safeguard-quality.ts` 负责结构化摘要模板、必需 section、精确标识提取、质量检查相关逻辑；`src/agents/pi-hooks/compaction-safeguard-runtime.ts` 保存 compaction 所需的 session 级上下文；`src/agents/pi-hooks/session-manager-runtime-registry.ts` 是两类 runtime registry 共用的 WeakMap 工具。

测试集中在同级文件：`compaction-instructions.test.ts`、`compaction-safeguard.test.ts`、`context-pruning.test.ts`、`context-pruning/pruner.test.ts`。它们说明这个目录的行为边界比文件结构更重要：重点不是“有哪些文件”，而是消息裁剪和摘要连续性是否满足 contract。

## 核心对象

`ContextPruningRuntimeValue` 是 context pruning 的运行时状态，包含 `settings`、`contextWindowTokens`、`isToolPrunable`、`dropThinkingBlocks`、`lastCacheTouchAt`。它通过 `setContextPruningRuntime` 和 `getContextPruningRuntime` 绑定到 `ctx.sessionManager`。这里的关键假设写在注释里：Pi 传给 `ExtensionContext` 的 `sessionManager` 必须和设置 runtime 时是同一个对象实例。

`EffectiveContextPruningSettings` 是裁剪策略的归一化结果。默认策略是 `cache-ttl`，TTL 为 5 分钟，保留最近 3 个 assistant 回合，超过一定比例后对可裁剪工具结果做 soft trim 或 hard clear。`ContextPruningToolMatch` 用 allow/deny glob 控制哪些工具名可裁剪，避免误删关键工具结果。

`CompactionSafeguardRuntimeValue` 是 compaction safeguard 的会话级参数集合，包含 `maxHistoryShare`、`contextWindowTokens`、`identifierPolicy`、`customInstructions`、`model`、`workspaceDir`、`postCompactionSections`、`qualityGuardEnabled`、`provider`、`cancelReason` 等。它承担一个上游适配职责：注释说明 `compact.ts` workflow 中 `ctx.model` 可能为 `undefined`，所以 model 需要通过 runtime 传入。

`DEFAULT_COMPACTION_INSTRUCTIONS` 是默认摘要指令，强调保留会话主要语言、保持结构标题、不要翻译或改写 code/path/identifier/error message。`buildCompactionStructureInstructions` 固定要求摘要包含 `## Decisions`、`## Open TODOs`、`## Constraints/Rules`、`## Pending user asks`、`## Exact identifiers`，这是后续质量检查和上下文恢复的核心 contract。

## 运行流程

context pruning 的流程从 `contextPruningExtension(api)` 开始。它注册 `api.on("context", ...)`，在每次 Pi 准备上下文时读取 `ctx.sessionManager` 上的 `ContextPruningRuntimeValue`。如果没有 runtime，直接不介入；如果启用 `cache-ttl` 且缓存触碰时间还没过期，也不介入。只有满足 TTL 过期等条件时，才调用 `pruneContextMessages` 生成新的消息数组，并在真正发生变化时返回 `{ messages: next }`。

`pruneContextMessages` 的核心策略是估算消息体积并只处理可裁剪区域。根据当前片段可见，它会区分 user、assistant、toolResult 等消息，分别估算文本、图片、thinking、toolCall arguments 的字符/token 权重；图片会按固定估值计入预算。它还会保留最近若干 assistant 回合，保护尾部上下文；对于可裁剪 tool result，会收集文本和图片占位，soft trim 时保留头尾片段，hard clear 时用 placeholder 替代旧内容。

compaction safeguard 的流程更偏“摘要质量管控”。它会从 session branch 收集 message/custom_message/branch_summary，过滤真实会话内容，必要时把 previous compaction summary 作为一个待重新蒸馏的 user message 前置。摘要生成优先尝试注册的 `CompactionProvider`；provider 返回空或普通失败时降级到内置 LLM summarization，但 abort/timeout 会继续抛出，避免吞掉取消语义。摘要完成后，质量层会检查必需 section、最新用户 ask 的关键词重叠、精确标识是否保留等；失败时可按配置重试或生成结构化 fallback。

## 上下游依赖

上游主要是 Pi SDK 的消息模型和 extension 事件：`AgentMessage`、`ExtensionAPI`、`ExtensionContext`、`ContextEvent`。这个目录不能随意改变消息 shape，因为它直接改写 Pi 即将送入模型的上下文。

OpenClaw 内部上游包括 `src/agents/compaction.ts` 的 token/window 估算和 staged summarization，`src/agents/content-blocks.ts` 的内容块处理，`src/agents/pi-embedded-runner/thinking.ts` 的 thinking block 处理，`src/plugins/compaction-provider.ts` 的插件摘要 provider，`src/cli/parse-duration.ts` 的 TTL 解析，以及 `src/utils/cjk-chars.ts` 对中日韩字符的加权估算。

下游是 agent 会话连续性、压缩后的 prompt 内容、工具调用结果配对、用户可见的 compaction 行为。`compaction-safeguard-runtime.ts` 里的 `consumeCompactionSafeguardCancelReason` 还说明 OpenClaw 会消费更具体的取消原因，用它替换上游通用的 “Compaction cancelled” 类信息。

## 修改时最容易踩的坑

最容易踩的是破坏 `SessionManager` 对象身份假设。`session-manager-runtime-registry.ts` 用 `WeakMap<object, TValue>` 存 runtime，键不是 session id 字符串，而是对象实例。如果调用链换了 wrapper、新建了 session manager，`get` 会读不到配置，hook 会静默不生效。

第二个坑是把 context pruning 当成持久化历史修改。`context-pruning.ts` 顶部说明它只影响当前请求的 in-memory context，不会重写磁盘上的 session history。修改 `pruner.ts` 时要保持这个边界，不能把裁剪结果反写到历史存储。

第三个坑是摘要结构。`compaction-safeguard-quality.ts` 对 section 标题有精确要求，改标题、翻译标题、调整顺序都会影响质量检查和后续恢复。默认指令要求“正文语言可跟随会话，但结构标题不变”，这是面向多语言会话的重要约束。

第四个坑是取消和超时语义。`tryProviderSummarize` 对 abort/timeout 是 rethrow，对普通 provider 失败才 fallback。把所有错误都吞掉会导致用户取消不及时，或者把真实超时伪装成成功降级。

第五个坑是 token/字符估算。这里同时考虑 CJK 字符、图片估值、thinking block、toolCall arguments。简单按字符串长度裁剪，容易在中文、多模态或工具密集会话里误判预算。

## 推荐阅读顺序

先读 `src/agents/pi-hooks/session-manager-runtime-registry.ts`，理解这个目录如何把运行时配置挂到 `SessionManager` 对象身份上。

再读 `src/agents/pi-hooks/context-pruning.ts` 和 `src/agents/pi-hooks/context-pruning/extension.ts`，建立 Pi extension 接入点的整体印象。

然后读 `src/agents/pi-hooks/context-pruning/settings.ts`、`src/agents/pi-hooks/context-pruning/tools.ts`、`src/agents/pi-hooks/context-pruning/pruner.ts`，按“配置归一化 -> 工具匹配 -> 消息裁剪”的顺序理解 context pruning。

接着读 `src/agents/pi-hooks/compaction-instructions.ts`、`src/agents/pi-hooks/compaction-safeguard-runtime.ts`、`src/agents/pi-hooks/compaction-safeguard-quality.ts`，掌握 compaction 的默认指令、运行时参数和质量 contract。

最后读 `src/agents/pi-hooks/compaction-safeguard.ts` 和对应测试文件，重点看它如何把 provider、内置 summarization、previous summary、质量检查和 fallback 串成完整流程。
