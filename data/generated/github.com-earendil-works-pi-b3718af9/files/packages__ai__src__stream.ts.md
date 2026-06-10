# 文件：packages/ai/src/stream.ts

## 一句话定位

`packages/ai/src/stream.ts` 是 `@earendil-works/pi-ai` 文本生成能力的统一入口层：调用方只需要传入 `Model`、`Context` 和选项，它负责找到对应 API provider、补齐环境变量中的 API key，并返回统一的 `AssistantMessageEventStream` 或完整的 `AssistantMessage`。

## 它暴露/定义了什么

这个文件导出 5 个公开能力：

`getEnvApiKey`：从 `packages/ai/src/env-api-keys.ts` 重新导出，方便调用方从同一个入口读取 provider 对应的环境 API key。

`stream(model, context, options?)`：标准流式接口，返回 `AssistantMessageEventStream`。

`complete(model, context, options?)`：标准非流式便捷接口，本质上调用 `stream()` 后等待 `s.result()`。

`streamSimple(model, context, options?)`：简化流式接口，使用 `SimpleStreamOptions`，面向跨 provider 的通用推理配置，例如 `reasoning`、`thinkingBudgets`。

`completeSimple(model, context, options?)`：简化非流式便捷接口，本质上调用 `streamSimple()` 后等待最终结果。

文件内部还定义了三个辅助函数：`hasExplicitApiKey()` 判断调用方是否显式传入有效 key；`withEnvApiKey()` 在未显式传 key 时从环境变量补 key；`resolveApiProvider()` 从注册表取 provider，取不到就抛错。

## 谁调用它

直接调用者包括 `packages/ai/test/*` 中大量 provider、缓存、token、abort、上下文溢出相关测试，它们直接从 `../src/stream.ts` 导入 `stream`、`complete`、`streamSimple`、`completeSimple`。

包外调用主要通过 `packages/ai/src/index.ts` 的 `export * from "./stream.ts"` 暴露给 `@earendil-works/pi-ai` 使用。根据当前片段推断，`packages/agent` 和 `packages/coding-agent` 是核心上游：例如 `packages/agent/src/harness/agent-harness.ts` 使用 `streamSimple` 驱动 agent harness；`packages/agent/src/harness/compaction/*`、`packages/coding-agent/src/core/compaction/*` 使用 `completeSimple` 做上下文压缩或分支总结；`packages/coding-agent/examples/extensions/qna.ts` 使用 `complete` 发起扩展内问答请求。

## 它调用谁

它首先通过副作用导入 `packages/ai/src/providers/register-builtins.ts`，触发内置 provider 注册。该文件会把 `"anthropic-messages"`、`"openai-responses"`、`"openai-completions"`、`"openai-codex-responses"`、`"azure-openai-responses"`、`"google-generative-ai"`、`"google-vertex"`、`"mistral-conversations"`、`"bedrock-converse-stream"` 等 API 注册到 `api-registry`。

运行时，`stream.ts` 调用 `getApiProvider(model.api)` 查找 provider；调用 `getEnvApiKey(model.provider)` 按 provider 取环境变量 key；最终调用 provider 的 `stream()` 或 `streamSimple()`。这些 provider 函数再由各自实现连接 OpenAI、Anthropic、Google、Bedrock、Mistral 等后端，并统一产出 `AssistantMessageEventStream`。

## 核心流程

调用 `stream()` 时，流程是：根据 `model.api` 查 `api-registry`；如果没有注册 provider，直接抛出 `No API provider registered for api: ...`；如果有 provider，则用 `withEnvApiKey()` 处理选项；最后调用 `provider.stream(model, context, options)` 并把返回的 `AssistantMessageEventStream` 交给上层消费。

`complete()` 只是同步语义包装：先拿到 `stream()` 返回的流，再等待 `result()`。因此它不改变 provider 行为，只改变消费方式。

`streamSimple()` 与 `stream()` 的差异在于它走 `provider.streamSimple()`，选项类型是 `SimpleStreamOptions`。这让上层可以用较稳定的跨模型抽象表达推理等级，而不是直接理解每个 provider 的私有参数。

`completeSimple()` 同理，是 `streamSimple()` 的结果等待包装。

API key 处理是中间的关键细节：如果 `options.apiKey` 是非空字符串，文件尊重调用方传入值；否则按 `model.provider` 从环境变量读取。如果没有环境 key，则保持原 options 不变，让 provider 层自行报错或处理无 key 场景。

## 关键函数的高层作用

`stream()` 是最重要的边界函数。它把上层的模型请求路由到具体 provider，并保持标准事件流协议不变。调用方不需要知道某个模型使用 OpenAI Responses、Anthropic Messages 还是 Bedrock Converse Stream，只依赖 `Model.api`。

`complete()` 面向不关心增量事件的调用方，例如测试断言、上下文压缩、一次性扩展问答。它仍复用流式通道，因此完整响应和流式响应共享同一 provider 实现。

`streamSimple()` 是跨 provider 简化入口，适合 agent 主循环、harness、压缩任务这类希望以统一参数描述请求的场景。具体 provider 如何把 `reasoning`、`thinkingBudgets` 映射成真实 API 参数，不在本文件处理。

`completeSimple()` 是最高层的简化同步入口，经常用于“给定上下文，拿一个最终 assistant message”的内部任务。

`withEnvApiKey()` 是配置兜底点，风险虽小但影响面大：它决定显式 key 和环境 key 的优先级。`resolveApiProvider()` 是注册表防线，避免未注册 API 静默失败。

## 修改风险

最大风险是破坏统一入口契约。`types.ts` 中 `StreamFunction` 约定 provider 调用后，请求、模型、运行时失败应编码进返回的流，而不是随意抛出；`stream.ts` 的 `resolveApiProvider()` 只处理“没有 provider 注册”这种入口级错误。如果在这里吞掉 provider 错误或改变异常策略，会影响 agent 重试、abort、错误展示和测试预期。

第二个风险是 API key 优先级。当前逻辑是显式 `options.apiKey` 优先，环境变量只补缺。如果改成环境变量覆盖显式 key，会破坏扩展、测试、临时凭据、OAuth 或多账号场景。

第三个风险是 `model.api` 与 `model.provider` 的职责混淆。provider 查找使用 `model.api`，环境 key 查找使用 `model.provider`。这允许多个 provider 共用 API 协议，也允许同一 API 有不同 provider 身份。把两者合并会影响模型注册和跨 provider 路由。

第四个风险是 `ProviderStreamOptions` 到 `StreamOptions` 的类型收窄。`stream()` 接受 provider 私有扩展选项，但传给注册表内部时被视为通用 `StreamOptions`。实际 provider 注册和包装层依赖 TypeScript 泛型约束维持正确性；随意改签名可能让 provider 私有选项丢失类型表达。

第五个风险是副作用导入 `./providers/register-builtins.ts`。它保证导入 `stream.ts` 时内置 provider 已注册。删除或延后这个导入，会导致普通调用方在没有手动注册 provider 时直接失败。
