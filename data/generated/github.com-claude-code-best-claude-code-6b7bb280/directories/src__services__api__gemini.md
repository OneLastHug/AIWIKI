# 目录：src/services/api/gemini
## 它负责什么
这个目录是 Gemini 兼容层的核心适配目录，职责很明确：把仓库内部统一使用的 Anthropic 风格消息、工具和流事件，转换成 Gemini API 能接受的请求格式，再把 Gemini 的 SSE 流响应转回上层能继续处理的 Anthropic 风格事件。根据当前片段推断，这里不承担页面、命令行或认证交互本身，而是专注于“模型调用桥接”。

它的定位和 `src/services/api/openai`、`src/services/api/grok` 类似，都是 `src/services/api/claude.ts` 里的 provider 分流目标之一。也就是说，Gemini 只是多供应商体系中的一个后端适配分支。

## 直接子目录地图
这个目录下面没有更深的子目录，只有两个直接文件：

- `index.ts`：主适配入口，负责组织请求、工具转换、流适配和结果回传。
- `client.ts`：Gemini 的底层流式请求客户端，负责拼 URL、发起 fetch、解析 SSE 流。

从结构上看，`index.ts` 是“业务编排层”，`client.ts` 是“传输层”。这是这个目录最重要的分层。

## 关键入口
真正被外部调用的入口是 `src/services/api/gemini/index.ts` 里的 `queryModelGemini(...)`。上层在 `src/services/api/claude.ts` 中通过 `getAPIProvider() === 'gemini'` 这一分支动态导入它：

- `src/services/api/claude.ts`：选择 Gemini provider 并 `yield* queryModelGemini(...)`
- `src/services/api/gemini/index.ts`：处理消息、工具、模型、流和观测
- `src/services/api/gemini/client.ts`：执行 `streamGeminiGenerateContent(...)`

如果只看目录内部，`queryModelGemini` 就是对外门面；如果看整个 API 层，`src/services/api/claude.ts` 才是总分发入口。

## 主流程位置
主流程基本都集中在 `src/services/api/gemini/index.ts` 中，可以按下面的顺序理解：

1. 解析模型：通过 `resolveGeminiModel(options.model)` 选出最终 Gemini 模型。
2. 规范化输入：调用 `normalizeMessagesForAPI(messages, tools)` 预处理消息。
3. 处理工具：用 `toolToAPISchema(...)` 把内部工具转成 API schema，再过滤掉不适合直接送进 Gemini 的特殊工具类型。
4. 转换上下文：用 `anthropicMessagesToGemini(...)` 把消息和 system prompt 变成 Gemini 的 `contents` / `systemInstruction`。
5. 组装请求：用 `anthropicToolsToGemini(...)`、`anthropicToolChoiceToGemini(...)` 生成 Gemini 侧的工具配置和 toolConfig。
6. 发起流式请求：调用 `streamGeminiGenerateContent(...)`，这一步实际落到 `client.ts`。
7. 适配流事件：用 `adaptGeminiStreamToAnthropic(...)` 把 Gemini 流转成仓库内统一的流事件。
8. 重建输出块：在 `content_block_start`、`content_block_delta`、`content_block_stop` 这些事件里逐步拼回 `AssistantMessage`。
9. 记录观测：最后调用 `recordLLMObservation(...)`，把输入、输出、工具和 thinking 信息送进 Langfuse 跟踪。

`client.ts` 的主流程更底层，核心就是三件事：确定 base URL、POST 请求、解析 SSE 帧。它会读取 `GEMINI_BASE_URL`，默认回退到 Google 的 `v1beta` 地址，并把 `GEMINI_API_KEY` 放进 `x-goog-api-key` 头里。响应回来后，它不会依赖 SDK，而是自己读取 `response.body`，用 `parseSSEFrames(...)` 拆帧，再 `JSON.parse` 成 `GeminiStreamChunk`。

## 推荐阅读顺序
如果你是第一次看这块，建议按这个顺序：

1. `src/services/api/claude.ts`：先看 provider 分发，知道 Gemini 是在哪一层被选中的。
2. `src/services/api/gemini/index.ts`：再看高层编排，理解消息、工具、流事件怎么串起来。
3. `src/services/api/gemini/client.ts`：最后看底层 SSE 传输，确认网络请求是怎么发和怎么收的。
4. `@ant/model-provider` 中与 Gemini 相关的适配函数：如 `anthropicMessagesToGemini`、`adaptGeminiStreamToAnthropic`、`resolveGeminiModel`，这些逻辑大多不在本目录里，但决定了格式转换的边界。

## 常见误区
最容易误判的一点，是把这个目录当成“Gemini SDK 封装层”。实际上它更像是一个协议适配器，重点不是封装官方 SDK，而是把仓库内部统一的消息协议接到 Gemini 的 HTTP SSE 接口上。

第二个误区，是以为 `client.ts` 里会做复杂业务逻辑。其实它主要是传输和解析，核心策略都在 `index.ts` 和 `@ant/model-provider` 里。

第三个误区，是忽略上层分发位置。Gemini 目录本身不决定 provider 选择，真正的入口是在 `src/services/api/claude.ts`，那里根据当前 provider 决定是否动态导入 `./gemini/index.js`。

第四个误区，是把工具转换理解成 Gemini 独有逻辑。根据当前片段推断，真正的工具格式转换主要依赖共享能力：内部工具先经过 `toolToAPISchema(...)`，再交给 `anthropicToolsToGemini(...)` 做协议映射。这个目录更多是在“串流程”，不是“重新发明一套工具系统”。
