# 目录：src/services/api/openai

## 它负责什么

`src/services/api/openai` 是 Claude Code API 层里的 OpenAI 兼容适配目录。它的职责不是把整个应用改成 OpenAI 协议，而是在主查询链路内部提供一个“协议桥”：上游仍然使用项目内部的 Anthropic/Claude 风格消息、工具、流事件和 `AssistantMessage` 类型；当运行环境切到 OpenAI 兼容模式时，这一层负责把请求转换成 OpenAI Chat Completions 或 ChatGPT Responses 可接受的格式，再把返回的流式结果转回 Anthropic 风格事件，交给原有 `query` 管线继续消费。

这个目录覆盖的典型场景包括：使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 接入 OpenAI 兼容端点；接入 Ollama、DeepSeek、vLLM 等实现了 OpenAI Chat Completions 协议的服务；对 DeepSeek、MiMo 等模型自动或显式启用 thinking 参数；在 ChatGPT 订阅认证可用时走 Responses 后端。它也兼顾工具调用、工具选择、流式 usage 统计、max tokens 处理、Langfuse 观测数据转换，以及 provider usage 的 rate-limit header 采集。

需要注意，这里是“OpenAI 兼容请求路径”，不是 provider 选择总入口。provider 决策主要在 `src/utils/model/providers.ts` 以及更上层的 API 调用逻辑中完成；本目录只处理进入 OpenAI 路径后的请求构造、客户端创建、流适配和结果组装。

## 直接子目录地图

这个目录下只有一个直接子目录：

`src/services/api/openai/__tests__`：放置 OpenAI 兼容层的单元测试和隔离测试。测试重点包括 `queryModelOpenAI` 的流式输出组装、usage 累加、`max_tokens` 透传、deferred MCP tools 可见性、Responses 适配器行为，以及 thinking 参数构造。它是理解本目录边界条件的辅助材料，但 overview 阅读时不需要从测试开始。

其余都是目录根部的 TypeScript 模块。按角色可分为四组：入口编排模块 `index.ts`；客户端与认证模块 `client.ts`、`chatgptAuth.ts`；请求体和共享工具模块 `requestBody.ts`、`openaiShared.ts`；Responses 专用适配模块 `responsesAdapter.ts`。

## 关键入口

最重要的入口是 `src/services/api/openai/index.ts` 中的 `queryModelOpenAI`。它是一个 async generator，输入为项目内部的 `Message[]`、`SystemPrompt`、`Tools`、`AbortSignal` 和 `Options`，输出为 `StreamEvent`、`AssistantMessage` 或 `SystemAPIErrorMessage`。从注释和调用关系看，它承担完整的 OpenAI 兼容查询流程：解析模型名、规范化消息、处理 search extra tools / deferred tools、转换消息和工具 schema、构造请求、调用 OpenAI 客户端或 Responses 流、把流事件重新整理成内部消息。

上游关键入口在 `src/services/api/claude.ts`。该文件仍是核心 API 层的大入口，但当检测到 OpenAI 兼容 provider 时，会动态导入 `./openai/index.js` 并 `yield* queryModelOpenAI(...)`。这说明 OpenAI 路径是主 Claude API 管线的一个分支，而不是独立的 CLI 流程。

`src/services/api/openai/client.ts` 的 `getOpenAIClient` 是网络客户端入口。它读取 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_ORG_ID`、`OPENAI_PROJECT_ID`、`API_TIMEOUT_MS` 等环境变量，创建 `openai` SDK client，并包装 `fetch` 来采集 OpenAI 兼容服务返回的 rate-limit headers。该 client 默认会缓存，因此运行时切换环境变量后需要注意缓存影响，文件内也提供了 `clearOpenAIClientCache`。

`src/services/api/openai/requestBody.ts` 是请求体构造入口，主要导出 `isOpenAIThinkingEnabled`、`resolveOpenAIMaxTokens`、`buildOpenAIRequestBody`。它是纯函数模块，专门从 `index.ts` 中抽离出来，便于测试且避免导入 OpenAI SDK client 等重副作用模块。

`src/services/api/openai/responsesAdapter.ts` 是 ChatGPT Responses 路径入口，核心函数包括 `buildResponsesRequest`、`createChatGPTResponsesStream`、`adaptResponsesStreamToAnthropic`。根据当前片段推断，只有在 `chatgptAuth.ts` 判定 ChatGPT auth 可用时，`index.ts` 才会走 Responses 适配；否则默认使用 Chat Completions 兼容路径。

## 主流程位置

主流程集中在 `queryModelOpenAI`。第一段是模型与消息准备：通过 `resolveOpenAIModel(options.model)` 得到 OpenAI 侧模型名，再用 `normalizeMessagesForAPI(messages, tools)` 做共享预处理。随后它会检查 `isSearchExtraToolsEnabled`，识别 deferred tools，并过滤真实传给 API 的工具列表。因为 OpenAI 兼容端点不能直接理解 Anthropic 的 `defer_loading` 或 `tool_reference` beta payload，所以这里会在必要时通过文本形式把可延迟加载工具列表塞进消息上下文，并保留 `SearchExtraToolsTool` 作为工具发现入口。

第二段是格式转换：`index.ts` 从 `@ant/model-provider` 引入 `anthropicMessagesToOpenAI`、`anthropicToolsToOpenAI`、`anthropicToolChoiceToOpenAI`、`adaptOpenAIStreamToAnthropic` 等函数，把内部 Anthropic 风格消息、工具定义和 tool choice 转成 OpenAI 风格。这里体现了项目的适配层策略：转换尽量集中在 provider adapter，主查询管线继续消费统一的 Anthropic 风格流事件。

第三段是请求参数构造。`requestBody.ts` 决定是否启用 thinking：`OPENAI_ENABLE_THINKING` 显式假值会禁用，显式真值会启用，否则根据模型名中是否包含 `deepseek` 或 `mimo` 自动判断。`resolveOpenAIMaxTokens` 的优先级是程序传入 override、`OPENAI_MAX_TOKENS`、`CLAUDE_CODE_MAX_OUTPUT_TOKENS`、模型上限默认值。`buildOpenAIRequestBody` 负责输出 `chat.completions.create()` 的 streaming 请求体，并在 thinking 开启时同时发送多种兼容字段，如 `thinking`、`enable_thinking`、`chat_template_kwargs`。

第四段是流式调用和回填。普通 OpenAI 兼容路径会通过 `getOpenAIClient(...).chat.completions.create(...)` 发起请求，然后用 `adaptOpenAIStreamToAnthropic` 转成 Anthropic raw stream event。ChatGPT auth 路径则通过 `buildResponsesRequest`、`createChatGPTResponsesStream` 和 `adaptResponsesStreamToAnthropic` 走 Responses API。之后 `index.ts` 会累计 content blocks、usage、stop reason，并在完成时组装 `AssistantMessage`；如果 stop reason 是 `max_tokens`，还会额外产生一个 `SystemAPIErrorMessage`，提示通过 `OPENAI_MAX_TOKENS` 或 `CLAUDE_CODE_MAX_OUTPUT_TOKENS` 调整上限。

## 推荐阅读顺序

1. 先读 `src/services/api/claude.ts` 中委托到 `queryModelOpenAI` 的位置，确认 OpenAI 兼容层如何接入主 API 管线。
2. 再读 `src/services/api/openai/index.ts` 的 `queryModelOpenAI`，只抓主流程分段：消息准备、工具过滤、格式转换、请求发起、流式回填。
3. 接着读 `src/services/api/openai/requestBody.ts`，理解 max tokens 和 thinking 参数如何由环境变量与模型名共同决定。
4. 然后读 `src/services/api/openai/client.ts`，关注环境变量、client 缓存、proxy fetch options、rate-limit header 采集。
5. 如果需要理解 ChatGPT 订阅认证路径，再读 `src/services/api/openai/chatgptAuth.ts` 和 `src/services/api/openai/responsesAdapter.ts`。
6. 最后参考 `src/services/api/openai/__tests__`，用测试用例验证边界行为，例如 usage 累加、stop reason、Responses stream 映射和 deferred tools。

## 常见误区

第一个误区是把本目录当成“OpenAI provider 注册中心”。实际上它是请求适配层。provider 选择、环境变量切换和模型 provider 优先级还要看 `src/utils/model/providers.ts`、`src/services/providerRegistry` 以及 `src/services/api/claude.ts` 的上游逻辑。

第二个误区是认为 OpenAI 兼容路径只支持官方 OpenAI。代码中的 `OPENAI_BASE_URL`、thinking 兼容字段、DeepSeek/MiMo 自动识别、注释中的本地模型场景，都说明它面向更广义的 OpenAI-compatible endpoint。也正因为如此，请求体会发送一些官方 OpenAI 不一定使用、但第三方服务可能识别的字段。

第三个误区是以为流式返回会直接变成 OpenAI 消息给 UI 使用。项目内部仍以 Anthropic 风格事件和消息结构为主，OpenAI 结果会先经 `adaptOpenAIStreamToAnthropic` 或 `adaptResponsesStreamToAnthropic` 转回统一格式，再进入原有消息组装和 UI 展示链路。

第四个误区是忽略工具系统差异。Anthropic 的 deferred tools、tool reference、SearchExtraToolsTool 不能原样传给 OpenAI 兼容端点，因此 `index.ts` 有专门的过滤和提示注入逻辑。阅读工具调用问题时，不能只看 `anthropicToolsToOpenAI`，还要看 `queryModelOpenAI` 之前如何筛选工具集合。

第五个误区是运行中改了 `OPENAI_BASE_URL` 或 `OPENAI_API_KEY` 就期待立即生效。`getOpenAIClient` 默认缓存 client，除非使用 fetch override 或显式 `clearOpenAIClientCache`，否则已创建的 client 可能继续沿用旧配置。
