# 子系统：src/services/api

## 解决什么问题

`src/services/api` 是 CLI 与模型服务、账号服务、配额服务之间的 API 访问层。它把上层的对话消息、系统提示词、工具定义、thinking 配置、模型选项等，转换为实际可发送的请求，并把不同后端返回的流式事件统一还原成内部使用的 `StreamEvent`、`AssistantMessage`、`SystemAPIErrorMessage`。

这个目录的核心职责不是“业务编排”，而是“网络边界适配”：上层只需要调用 `queryModelWithStreaming` 或 `queryModelWithoutStreaming`，不直接关心 Anthropic SDK、Bedrock、Vertex、Foundry、OpenAI、Gemini、Grok 的差异。目录内还承担认证头拼装、重试、限流处理、非流式 fallback、API 日志、token usage、成本统计、bootstrap 缓存、文件下载、会话 ingress、组织级开关等横切能力。

## 相关目录和文件

最核心的文件是 `src/services/api/claude.ts`、`src/services/api/client.ts`、`src/services/api/withRetry.ts`。

`src/services/api/claude.ts` 是主请求管线，负责消息规范化、工具 schema 生成、beta header、stream 事件消费、fallback、usage 与 cost 统计。`src/services/api/client.ts` 负责创建 Anthropic SDK client，并按环境变量切换 first-party、Bedrock、Foundry、Vertex 等后端。`src/services/api/withRetry.ts` 封装 API 错误重试、429/529 处理、OAuth 刷新、云厂商认证错误恢复、fast mode cooldown、persistent retry 等策略。

兼容层在 `src/services/api/openai`、`src/services/api/gemini`、`src/services/api/grok`。这些目录把内部 Anthropic 风格的消息、工具和流事件转换到第三方 API，再适配回内部事件模型。`src/services/api/bootstrap.ts` 处理启动时从服务端获取 client data 和额外模型选项，并写入全局配置缓存。`src/services/api/filesApi.ts` 处理 Files API 下载与本地路径构造。`src/services/api/sessionIngress.ts` 处理远程会话日志追加、读取和 teleport events。`logging.ts`、`errors.ts`、`errorUtils.ts`、`promptCacheBreakDetection.ts` 则提供观测、错误呈现和 prompt cache 检测支持。

## 核心对象

`getAnthropicClient` 是底层 client 工厂。它统一添加 `x-app`、`User-Agent`、`X-Claude-Code-Session-Id`、远程容器/session header、自定义 header、认证 header，并根据 `CLAUDE_CODE_USE_BEDROCK`、`CLAUDE_CODE_USE_FOUNDRY`、`CLAUDE_CODE_USE_VERTEX` 等环境变量创建不同 SDK client。对 first-party 请求，它还会通过 `CLIENT_REQUEST_ID_HEADER` 注入客户端请求 ID，方便超时场景排查。

`queryModelWithStreaming` 和 `queryModelWithoutStreaming` 是上层主要入口。二者最终都会进入 `queryModel`，区别是前者把模型流事件持续 yield 给调用方，后者消费完整个 generator 后返回最终 assistant message。

`withRetry` 是 API 层的重试状态机。它接收 `getClient`、`operation` 和 `RetryOptions`，在失败时决定是否重新获取 client、是否刷新 OAuth、是否处理云厂商凭证、是否等待 `retry-after`、是否触发 model fallback 或 fast mode fallback。它本身是 async generator，因此能在重试等待期间向上层 yield `system/api_retry` 类消息。

`executeNonStreamingRequest` 是流式失败后的非流式 fallback helper。根据当前 retry context 重新构造 `BetaMessageStreamParams`，调用 `anthropic.beta.messages.create` 的非 stream 模式，并复用 `withRetry` 的错误处理。

`queryModelOpenAI`、`queryModelGemini`、`queryModelGrok` 是第三方 provider 入口。它们的共同目标是把第三方请求和响应伪装成 Anthropic 内部语义，使上游对话循环不需要分叉。

## 运行流程

典型流式请求从上层 `src/query.ts` 或 `QueryEngine` 进入 `queryModelWithStreaming`。API 层先通过 `withStreamingVCR` 包一层录制/回放能力，然后进入 `queryModel`。

`queryModel` 会先对消息做 `normalizeMessagesForAPI`，修复 tool result 配对、去除不适合发送的块、限制媒体数量。随后根据 `getAPIProvider()` 判断 provider：如果是 `openai`、`gemini`、`grok`，会动态 import 对应适配器并提前返回；否则继续走 Anthropic 兼容管线。

在 Anthropic 管线中，代码会生成工具 schema、处理 deferred tools、拼装 system prompt、thinking config、max tokens、temperature、metadata、beta headers、prompt cache 相关配置。之后通过 `withRetry` 创建 client，并调用 `anthropic.beta.messages.create({ stream: true }).withResponse()` 获取原始流。

流式事件到达后，`claude.ts` 维护 `contentBlocks`、`textDeltas`、`partialMessage`、`usage`、`stopReason` 等状态，把 `message_start`、`content_block_start`、`content_block_delta`、`content_block_stop`、`message_delta`、`message_stop` 组装为内部 assistant message 和增量事件。请求结束后记录 usage、cost、TTFT、API 日志、Langfuse observation、provider usage bucket 等。

如果流式链路发生可恢复错误，`withRetry` 先处理重试。某些情况下还会进入非流式 fallback，用 `executeNonStreamingRequest` 重新请求并转换为 assistant message。

## 上下游依赖

上游主要是 `src/query.ts`、`src/QueryEngine.ts`、REPL 和 headless 模式。它们依赖 API 层提供统一的消息流，而不是直接接触具体 provider SDK。

下游依赖包括 `@anthropic-ai/sdk`、`@anthropic-ai/bedrock-sdk`、`@anthropic-ai/vertex-sdk`、`@anthropic-ai/foundry-sdk`、`openai` SDK、`@ant/model-provider`、`axios`、`google-auth-library` 等。认证信息来自 `src/utils/auth.js`，模型与 provider 决策来自 `src/utils/model/providers.js`、`src/utils/model/model.js`，全局状态来自 `src/bootstrap/state.js`，系统提示词和工具 schema 来自 `src/utils/api.js`、`src/Tool.js`、`@claude-code-best/builtin-tools`。

观测链路依赖 `src/services/analytics`、`src/services/langfuse`、`src/services/providerUsage`、`src/utils/log.js`、`src/utils/queryProfiler.js`。配置缓存依赖 `src/utils/config.js`，OAuth endpoint 和 beta header 来自 `src/constants/oauth.js`、`src/constants/betas.js`。

## 修改时最容易踩的坑

第一，`feature('FLAG')` 的用法受 Bun 编译器限制，只能直接放在 `if` 或三元条件里。不要把结果赋值给变量，也不要放进复杂表达式。

第二，`claude.ts` 是多 provider 共享入口。第三方 provider 分支发生在部分预处理之后、Anthropic 专属逻辑之前。修改消息规范化、工具过滤、媒体裁剪时，要确认 OpenAI/Gemini/Grok 是否也需要同样行为。

第三，重试不是简单 `catch + retry`。`withRetry` 会影响 OAuth 刷新、client 重建、fast mode 状态、529 fallback、persistent retry 的用户可见系统消息。新增错误处理时要避免吞掉 `APIUserAbortError`，也不要让后台 query 在 529 时放大请求量。

第四，usage 字段不能随便覆盖。OpenAI 兼容层的 `updateOpenAIUsage` 特意保留 cache 字段，`claude.ts` 也有类似累计逻辑；如果适配器某次 delta 缺字段，不应把已有 cache token 清零。

第五，client header 有 provider 边界。`CLIENT_REQUEST_ID_HEADER` 只应发给 first-party Anthropic base URL，其他 provider 或严格代理可能拒绝未知 header。

第六，API 层很多函数会写全局配置缓存或更新全局状态，例如 bootstrap、prompt cache、quota、provider usage。修改时要注意非交互模式、隐私级别、essential traffic only 以及测试 mock。

## 推荐阅读顺序

1. 先读 `src/services/api/client.ts`，理解 provider client 如何创建、认证和注入 header。
2. 再读 `src/services/api/withRetry.ts`，掌握错误恢复和重试语义。
3. 阅读 `src/services/api/claude.ts` 中 `queryModelWithStreaming`、`queryModelWithoutStreaming`、`executeNonStreamingRequest`、provider 分支和主 stream 循环。
4. 按需阅读 `src/services/api/openai/index.ts`、`src/services/api/gemini/index.ts`、`src/services/api/grok/index.ts`，理解第三方兼容层如何转换消息、工具和流事件。
5. 最后补充看 `src/services/api/bootstrap.ts`、`src/services/api/filesApi.ts`、`src/services/api/sessionIngress.ts`、`src/services/api/logging.ts`，这些是围绕主模型请求的辅助 API 能力。
