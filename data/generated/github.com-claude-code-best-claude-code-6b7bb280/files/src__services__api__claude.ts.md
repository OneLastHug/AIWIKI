# 文件：src/services/api/claude.ts
## 一句话定位
这是 Claude Code 的核心 API 编排层，负责把内部消息、工具、系统提示、缓存策略、beta 头、思维参数和流式/非流式请求组装成一次完整的模型调用，并把返回结果再还原成上层可消费的消息流。

## 它暴露/定义了什么
这个文件对外主要暴露一组“请求构造 + 流式执行 + 结果统计”的基础能力：`queryModelWithStreaming`、`queryModelWithoutStreaming`、`queryHaiku`、`queryWithModel`、`buildSystemPromptBlocks`、`addCacheBreakpoints`、`adjustParamsForNonStreaming`、`getMaxOutputTokensForModel`、`updateUsage`、`accumulateUsage`、`cleanupStream`，以及若干消息转换和 API 元数据函数，如 `userMessageToMessageParam`、`assistantMessageToMessageParam`、`verifyApiKey`、`configureTaskBudgetParams`、`getExtraBodyParams`。根据当前片段推断，这个文件既是“请求构造器”，也是“流事件归一化器”。

## 谁调用它
它通常不被终端用户直接调用，而是被上层查询管线间接使用。可从仓库搜索结果看，`src/query.ts`、`src/QueryEngine.ts`、`src/screens/REPL.tsx` 是最主要的入口；另外 `packages/builtin-tools/src/tools/AgentTool/runAgent.ts`、`src/utils/hooks/execAgentHook.ts`、`src/tasks/LocalMainSessionTask.ts` 也会通过 `query()` 进入这条链路。换句话说，上层只关心“发起一次模型交互”，具体的 Anthropic 请求细节基本都落在这里。

## 它调用谁
它依赖面很广，但可以分三类看。第一类是基础运行时和状态层：`src/bootstrap/state.ts`、`src/utils/config.ts`、`src/utils/model/*`、`src/utils/context.ts`、`src/utils/messages.ts`、`src/utils/betas.ts`。第二类是观测与会话管理：`src/utils/log.ts`、`src/utils/queryProfiler.ts`、`src/utils/telemetry/sessionTracing.ts`、`src/services/analytics/*`、`src/services/langfuse/*`。第三类是 provider 和协议适配：`./client.ts`、`./openai/index.ts`、`./gemini/index.ts`、`./grok/index.ts`，以及 Anthropic SDK 本身。它还会按 feature flag 动态引入 `autoModeState.js`、`cachedMicrocompact.js` 等模块。

## 核心流程
核心流程可以概括为“预处理 -> 组装 -> 发送 -> 解析 -> 结算”。先根据模型、querySource、工具集合和 feature flag 决定 betas、advisor、fast mode、prompt caching、cached microcompact、SearchExtraTools 等能力；再对消息做标准化、工具结果配对修复、advisor block 清理、媒体数量裁剪；随后构建 system prompt、工具 schema、max_tokens、thinking、output_config、metadata 和额外 body 参数。真正发请求时，它通过 `getAnthropicClient()` 走流式接口，配合 `withRetry()` 管理重试，必要时切换到非流式 fallback。流返回后会逐个处理 `message_start`、`content_block_start`、`text_delta`、`tool_use` 等事件，持续累积 usage、cost、stop reason、request id，并把内部状态转换成上层消息。结束时还会做 prompt cache 记录、Langfuse/telemetry 采样、stream 资源释放和 API 成功/失败日志落盘。

## 关键函数的高层作用
`queryModel` 是总控入口，负责整条请求生命周期。`queryModelWithStreaming` 和 `queryModelWithoutStreaming` 则分别提供流式与非流式的外层能力。`queryHaiku`、`queryWithModel` 是两条更窄的便捷路径，前者偏轻量模型探测，后者用于“走完整 Claude Code 基础设施但指定模型”的场景。`addCacheBreakpoints` 和 `buildSystemPromptBlocks` 负责把缓存控制精确嵌到 message/system prompt 结构里。`updateUsage`、`accumulateUsage` 处理 Anthropic 流式 usage 的累积语义。`cleanupStream` 是资源回收的防泄漏出口。`adjustParamsForNonStreaming` 和 `getMaxOutputTokensForModel` 则把长请求、thinking budget 和环境变量上限约束住。

## 修改风险
这里是高风险文件，改动很容易牵一发动全身。第一类风险是缓存和 beta 头：`cache_control`、`cache_reference`、`ADVISOR_BETA_HEADER`、`PROMPT_CACHING_SCOPE_BETA_HEADER`、`FAST_MODE_BETA_HEADER` 这些字段一旦拼错或顺序变了，轻则缓存失效，重则 400。第二类风险是 provider 分支：OpenAI、Gemini、Grok、Anthropic 的消息格式并不完全一致，任何消息归一化的改动都可能只在某个 provider 上炸。第三类风险是流式状态机和 usage 统计，尤其是 `message_delta` 的累计语义、tool result 配对、stream watchdog、资源释放，改坏后会出现卡死、漏算成本或内存泄漏。第四类风险是 feature flag 与会话状态的组合，很多逻辑依赖 `bootstrap/state.ts` 的 latch 行为，改动前最好同时回看 `src/query.ts` 和相关测试。
