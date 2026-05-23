# 目录：packages/model-runtime/src/core/streams

## 它负责什么

`packages/model-runtime/src/core/streams` 是 `packages/model-runtime` 里负责“模型流式响应标准化”的核心目录。它面对的是不同模型供应商返回的异构 streaming chunk，例如 OpenAI Chat Completions、OpenAI Responses API、Anthropic message stream、Google GenAI、Bedrock、Ollama、Qwen、Spark 等；它输出的是项目内部统一的 `StreamProtocolChunk` 事件，再进一步转换成 SSE 文本流，并在流经过时触发回调、统计 token 速度、转换 usage、处理首包错误和供应商业务错误。

这个目录可以理解为 model runtime 的“流协议适配层”：上游是 provider SDK 或 HTTP stream，下游是 LobeHub 自己消费的事件协议。统一事件类型定义在 `packages/model-runtime/src/core/streams/protocol.ts`，包括 `text`、`reasoning`、`tool_calls`、`grounding`、`usage`、`speed`、`stop`、`error`、`base64_image`、`content_part`、`reasoning_part` 等。各 provider 文件的主要职责不是发请求，而是把供应商原始 chunk 转成这些内部事件。

## 直接子目录地图

`packages/model-runtime/src/core/streams/openai` 承载 OpenAI 体系的复杂流解析。这里既有 `openai.ts` 处理 Chat Completions 风格流，也有 `responsesStream.ts` 处理 Responses API 事件流。由于 OpenAI-compatible provider 很多，`openai.ts` 还兼容了不少供应商扩展字段，例如 reasoning 内容、工具调用、搜索引用、base64 image、MiniMax 错误格式等。

`packages/model-runtime/src/core/streams/google` 承载 Google GenAI / Gemini 相关流解析。入口是 `google/index.ts`，旁边的 `const.ts` 放置 Google block reason 的提示映射。这个目录重点处理 Gemini 的 `GenerateContentResponse`、`functionCall`、`thought`、`thoughtSignature`、inline image、grounding、usage 和安全拦截错误。

`packages/model-runtime/src/core/streams/bedrock` 承载 AWS Bedrock 相关适配。`bedrock/index.ts` 只做再导出，具体实现分在 `claude.ts`、`llama.ts`、`common.ts`。根据当前片段推断，这里是为了复用 Bedrock 公共 chunk 包装逻辑，同时分别适配 Bedrock 上 Claude 和 Llama 的响应结构，依据是该子目录按模型族拆分并有对应测试 `llama.test.ts`。

`packages/model-runtime/src/core/streams/__snapshots__` 和 `packages/model-runtime/src/core/streams/openai/__snapshots__` 是 Vitest snapshot 输出，服务于流协议转换测试，不属于运行时代码入口。

## 关键入口

目录级导出入口是 `packages/model-runtime/src/core/streams/index.ts`。它统一导出 `anthropic`、`bedrock`、`google`、`model`、`ollama`、`openai`、`protocol`、`qwen`、`spark`。调用方通常不需要直接进入每个实现文件，而是从这个入口拿到具体 provider 的 stream 包装函数和协议工具。

最重要的协议入口是 `packages/model-runtime/src/core/streams/protocol.ts`。它定义了 `StreamContext`、`StreamProtocolChunk`、`StreamToolCallChunkData` 等核心类型，也提供流处理管线中的通用 transformer：`convertIterableToStream`、`readableFromAsyncIterable`、`createFirstErrorHandleTransformer`、`createTokenSpeedCalculator`、`createSSEProtocolTransformer`、`createCallbacksTransformer`、`createSSEDataExtractor`。如果只读一个文件理解全局设计，应该先读这个文件。

模型拉取进度流入口是 `packages/model-runtime/src/core/streams/model.ts`。它的 `createModelPullStream` 面向“下载 / 拉取模型”这类进度型 AsyncIterable，不走聊天 chunk 协议，而是把 `status`、`completed`、`total`、`digest`、`model` 等进度信息编码为 JSON line 风格的 `ReadableStream`。

Provider 入口主要是 `packages/model-runtime/src/core/streams/openai/openai.ts`、`packages/model-runtime/src/core/streams/openai/responsesStream.ts`、`packages/model-runtime/src/core/streams/anthropic.ts`、`packages/model-runtime/src/core/streams/google/index.ts`，以及 Bedrock、Ollama、Qwen、Spark 对应文件。它们通常都包含一个 provider-specific transform 函数，再暴露一个 `XxxStream` 包装函数，把原始 stream 接入统一管线。

## 主流程位置

聊天流主流程集中在 `protocol.ts` 和各 provider 文件的尾部管线。典型路径是：provider SDK 返回 `AsyncIterable` 或 `ReadableStream`；如果是 `AsyncIterable`，先通过 `convertIterableToStream` 转为 Web `ReadableStream`；然后经过 `createFirstErrorHandleTransformer` 处理首包抛错或供应商错误；再通过 provider-specific transformer 把原始 chunk 转为 `StreamProtocolChunk`；随后 `createTokenSpeedCalculator` 在 `usage` 到达时补充 `speed`；再由 `createSSEProtocolTransformer` 编码成 `id/event/data` 形式的 SSE；最后 `createCallbacksTransformer` 一边透传字节流，一边聚合文本、reasoning、usage、grounding、tool calls、error，并触发 `ChatStreamCallbacks`。

OpenAI Chat Completions 的主流程在 `packages/model-runtime/src/core/streams/openai/openai.ts`。核心转换函数会处理 `choices[0].delta.content`、`delta.tool_calls`、`finish_reason`、`usage`、`citations`、`annotations`、reasoning 字段和图片字段。OpenAI Responses API 的主流程在 `packages/model-runtime/src/core/streams/openai/responsesStream.ts`，核心分支按 `response.created`、`response.output_item.added`、`response.function_call_arguments.delta`、`response.output_text.delta`、`response.reasoning_summary_text.delta`、`response.completed` 等事件类型转换。

Anthropic 的主流程在 `packages/model-runtime/src/core/streams/anthropic.ts`，按 `message_start`、`content_block_start`、`content_block_delta`、`message_delta`、`message_stop` 分段处理，重点是 `thinking`、`signature_delta`、`tool_use`、`input_json_delta`、citations 和 usage 聚合。Google 的主流程在 `packages/model-runtime/src/core/streams/google/index.ts`，核心是从 `GenerateContentResponse.candidates[0].content.parts` 中提取 text、thought、inlineData、functionCall、grounding 和 usage。

## 推荐阅读顺序

1. 先读 `packages/model-runtime/src/core/streams/index.ts`，建立“这个目录对外暴露什么”的第一印象。
2. 再读 `packages/model-runtime/src/core/streams/protocol.ts`，重点看 `StreamProtocolChunk`、`StreamContext` 和几个 `create*Transformer`，这是理解所有 provider 的共同语言。
3. 然后读 `packages/model-runtime/src/core/streams/openai/openai.ts`，因为它覆盖的兼容场景最多，能快速看到项目如何处理 text、reasoning、tool calls、grounding、usage 和 error。
4. 接着读 `packages/model-runtime/src/core/streams/openai/responsesStream.ts`，对比 Chat Completions 与 Responses API 两套事件模型的差异。
5. 再读 `packages/model-runtime/src/core/streams/anthropic.ts` 和 `packages/model-runtime/src/core/streams/google/index.ts`，理解非 OpenAI 协议如何映射到同一套内部事件。
6. 最后按需要阅读 `bedrock`、`ollama.ts`、`qwen.ts`、`spark.ts`、`cloudflare.ts`、`utils.ts` 和测试文件。overview 阶段不建议逐个叶子文件展开。

## 常见误区

不要把这个目录理解成“模型请求发起层”。它主要处理 stream shape 的转换、错误规整、SSE 编码和 callback 聚合；真正的 provider 请求构造通常在 `packages/model-runtime/src/providers` 或更上层 runtime 中完成。

不要认为所有 provider 都输出 OpenAI 格式。虽然 `openai/openai.ts` 兼容了大量 OpenAI-compatible 供应商，但 Anthropic、Google、Bedrock 等都有自己的事件结构，所以目录里存在多套 transform 函数，最终只是在 `StreamProtocolChunk` 层统一。

不要把 `usage`、`stop`、`speed` 的顺序当成天然来自供应商。`speed` 是 `createTokenSpeedCalculator` 根据首个输出 chunk、`inputStartAt` 和 `usage` 计算后追加的内部事件；`usage` 也常经过 `usageConverters` 归一化。

不要忽略 `StreamContext`。很多解析看似是无状态 chunk 映射，实际依赖 `context.id`、`toolIndex`、`tool`、`tools`、`returnedCitation`、`returnedCitationArray`、`thinkingInContent`、`usage` 等跨 chunk 状态。工具调用参数、citation 聚合、Anthropic usage 累加、Gemini thought signature 都可能依赖这些状态。

不要把测试 snapshot 当作实现入口。`__snapshots__` 只用于固定预期输出；理解主流程应从 `protocol.ts` 和 provider 入口开始。
