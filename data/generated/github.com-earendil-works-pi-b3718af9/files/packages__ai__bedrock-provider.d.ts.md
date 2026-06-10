# 文件：packages/ai/bedrock-provider.d.ts

## 一句话定位

`packages/ai/bedrock-provider.d.ts` 是 `@earendil-works/pi-ai/bedrock-provider` 子路径导出的类型入口，用一行 `export * from "./dist/bedrock-provider.js";` 把已构建产物中的 Bedrock Provider 类型声明重新暴露出来；它本身不是业务实现，而是发布包根部的类型转发层。

## 它暴露/定义了什么

该文件直接暴露 `./dist/bedrock-provider.js` 对应声明中的全部导出。根据源码 `packages/ai/src/bedrock-provider.ts`，核心导出是 `bedrockProviderModule`，其结构包含两个函数引用：

- `streamBedrock`：Amazon Bedrock Converse Stream 的完整流式调用入口。
- `streamSimpleBedrock`：简化流式调用入口，用于适配通用 simple stream 形态。

类型层面上，它让外部消费者可以通过包子路径 `@earendil-works/pi-ai/bedrock-provider` 获取 Bedrock 专用模块，而不是从主入口直接静态加载 Bedrock 实现。这个设计与 `packages/ai/package.json` 中的 `exports["./bedrock-provider"]` 对应，发布时类型指向 `./dist/bedrock-provider.d.ts`，运行时代码指向 `./dist/bedrock-provider.js`。

## 谁调用它

最明确的调用方是 `packages/coding-agent/src/bun/register-bedrock.ts`。该文件从主包导入 `setBedrockProviderModule`，再从 `@earendil-works/pi-ai/bedrock-provider` 导入 `bedrockProviderModule`，最后调用 `setBedrockProviderModule(bedrockProviderModule)`。这说明 Bedrock provider 在某些运行环境，尤其是 Bun 相关启动路径中，会被显式注册进 `pi-ai` 的 provider registry。

另一个间接调用路径在 `packages/ai/src/providers/register-builtins.ts`。默认注册内置 provider 时，`bedrock-converse-stream` 会被注册为懒加载 provider：如果没有外部注入的 `bedrockProviderModuleOverride`，运行时会通过 `importNodeOnlyProvider("./amazon-bedrock.ts")` 动态加载真实实现。根据当前片段推断，`bedrock-provider.d.ts` 主要服务于“显式注入 Bedrock 模块”的发布包 API，而默认路径则通过懒加载绕开主入口的 Node-only 依赖。

## 它调用谁

目标文件自身不调用任何代码，只做类型再导出。其背后的源码入口 `packages/ai/src/bedrock-provider.ts` 调用关系很薄：它从 `packages/ai/src/providers/amazon-bedrock.ts` 导入 `streamBedrock` 和 `streamSimpleBedrock`，再把它们包装成 `bedrockProviderModule` 对象。

真正的下游调用集中在 `amazon-bedrock.ts`：它依赖 `@aws-sdk/client-bedrock-runtime` 的 `BedrockRuntimeClient`、`ConverseStreamCommand` 等 AWS SDK 类型和客户端，也调用仓库内的 `AssistantMessageEventStream`、`calculateCost`、`parseStreamingJson`、`createHttpProxyAgentsForTarget`、`sanitizeSurrogates`、`buildBaseOptions`、`adjustMaxTokensForThinking`、`clampReasoning`、`transformMessages` 等工具。

## 核心流程

整体流程可以分成三层。

第一层是发布入口：`packages/ai/bedrock-provider.d.ts` 把 Bedrock 子路径的类型导向 dist 产物，使外部 TypeScript 用户能够识别 `@earendil-works/pi-ai/bedrock-provider` 的导出。

第二层是模块包装：`packages/ai/src/bedrock-provider.ts` 只创建 `bedrockProviderModule`，把 `streamBedrock` 和 `streamSimpleBedrock` 成组暴露。这个对象符合 `register-builtins.ts` 中 `BedrockProviderModule` 的形状。

第三层是注册和执行：`setBedrockProviderModule` 会把外部传入模块转换成 registry 内部使用的 `{ stream, streamSimple }` 形态，并覆盖默认懒加载模块。之后当模型 API 为 `bedrock-converse-stream` 时，统一 provider registry 会调用对应的 stream 函数。`streamBedrock` 创建 `AssistantMessageEventStream`，解析 region/profile/endpoint/bearer token/proxy 等配置，构造 `BedrockRuntimeClient` 和 `ConverseStreamCommand`，把上下文消息、system prompt、tool config、thinking 参数、metadata 转换成 Bedrock Converse Stream 请求，随后消费 AWS 返回的 streaming events，并转成项目统一的 assistant message event。

## 关键函数的高层作用

`bedrockProviderModule` 是当前入口的关键导出。它不是类，也不做初始化，只是把 Bedrock 的两个 stream 函数组装成可注入模块。它的价值在于解耦：主包可以保持通用 provider registry，Bedrock 的 Node/AWS SDK 相关实现则通过子路径或懒加载进入。

`setBedrockProviderModule` 位于 `packages/ai/src/providers/register-builtins.ts`，是这个模块的主要接收方。它接收 `BedrockProviderModule`，设置 `bedrockProviderModuleOverride`，让后续 `loadBedrockProviderModule` 优先使用显式注入版本。

`loadBedrockProviderModule` 是默认兜底加载器：如果已有 override，就直接返回；否则动态导入 `./amazon-bedrock.ts`，再抽取 `streamBedrock` 和 `streamSimpleBedrock`。这也是避免主入口静态牵引 Bedrock Node-only 依赖的关键点。

`streamBedrock` 是真实业务核心：负责凭据与 region 解析、请求构造、消息和工具转换、thinking/caching 配置、AWS streaming event 到内部事件的映射、usage/cost 统计和错误格式化。辅助函数如 `convertMessages`、`buildSystemPrompt`、`convertToolConfig`、`handleContentBlockDelta`、`handleMetadata` 只是分别承担格式转换和流事件处理，不是当前 `.d.ts` 文件本身的职责。

## 修改风险

这个文件看似只有一行，但属于发布 API 的边界文件，风险主要在兼容性和打包路径。若改动 `export * from "./dist/bedrock-provider.js";` 的目标路径，可能导致 TypeScript 无法解析 `@earendil-works/pi-ai/bedrock-provider`，即使运行时代码仍存在也会破坏下游类型检查。

如果删除该子路径声明，`packages/coding-agent/src/bun/register-bedrock.ts` 这类显式导入方会失去类型支持，并可能暴露出包 `exports`、构建产物、源码入口之间的不一致。若改变 `bedrockProviderModule` 的形状，还必须同步 `BedrockProviderModule`、`setBedrockProviderModule`、懒加载注册逻辑和测试，否则 Bedrock provider 可能无法注册，或者 `streamSimpleBedrock` 不再被端到端转发。

更深层的风险在于 Bedrock 实现带有环境敏感行为：AWS profile、region、ARN region、custom endpoint、bearer token、proxy、HTTP/1 强制、prompt caching、thinking、tool call、usage 统计都交织在 `streamBedrock` 中。修改类型入口时不要顺手改实现；修改实现时需要覆盖 `bedrock-custom-headers.test.ts`、`bedrock-endpoint-resolution.test.ts`、`bedrock-thinking-payload.test.ts`、`bedrock-convert-messages.test.ts` 这类针对回归点的测试。
