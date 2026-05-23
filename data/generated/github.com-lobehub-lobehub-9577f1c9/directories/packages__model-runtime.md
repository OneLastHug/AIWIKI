# 目录：packages/model-runtime

## 它负责什么

`packages/model-runtime` 是这套仓库里“模型运行时”的核心包，负责把上层业务输入的 `ChatStreamPayload`、`EmbeddingsPayload`、`GenerateObjectPayload`、图片/视频/语音等请求，转换成不同模型供应商能接受的调用格式，再把流式返回、usage、错误和计费信息统一回来。根据当前片段推断，它本质上是一个“模型适配层 + 运行时编排层”：上层只面对统一接口，底层则按 provider、模型族、API 形态做分流。

它同时承担三类工作：一是统一入口和导出面，二是 provider 适配器的封装，三是通用的协议、流处理、错误处理、成本计算等基础能力。目录里测试文件很多，说明这里是高频变更、强约束的底层包。

## 直接子目录地图

- `src/const`：模型相关常量与能力判定，例如哪些模型走 Responses API、哪些模型禁止流式、哪些 Claude 模型有上下文缓存或采样参数冲突。
- `src/core`：运行时骨架，是最关键的一层。里面又分成 `RouterRuntime`、`anthropicCompatibleFactory`、`openaiCompatibleFactory`、`contextBuilders`、`streams`、`usageConverters` 等子域。
- `src/helpers`：偏轻量的辅助函数，主要处理 chat 方法参数合并、tool calls 解析这类胶水逻辑。
- `src/providers`：最大的一块，几乎按供应商一目录一适配器组织。这里包含 `openai`、`anthropic`、`google`、`bedrock`、`deepseek`、`qwen`、`volcengine`、`ollama` 等大量 provider，也包含少数带专项能力的子目录，如图片、视频、 coding plan 之类的变体。
- `src/types`：统一的请求/响应/错误/模型/工具/多模态类型定义。
- `src/utils`：错误归一化、JSON 安全解析、流消费、URL 脱敏、模型参数回退、价格计算等通用工具。
- `docs`：包内文档，当前可见的是测试覆盖说明，偏维护用途。

## 关键入口

- `packages/model-runtime/package.json`：这个包的出口定义很清楚，`"."` 指向 `src/index.ts`，另外还单独导出了 `./vertexai`。这意味着对外主入口是 barrel file，而不是直接依赖某个 provider 内部文件。
- `packages/model-runtime/src/index.ts`：顶层聚合出口，集中导出 `ModelRuntime`、`createOpenAICompatibleRuntime`、`createOpenAICompatibleRuntime`、`consumeStreamUntilDone`、`getModelPricing`、`parseDataUri` 以及大量 provider runtime。
- `packages/model-runtime/src/runtimeMap.ts`：provider 名称到 runtime 实现的映射中心，像 `openai`、`anthropic`、`google`、`ollama`、`volcengine` 等都在这里统一注册。
- `packages/model-runtime/src/core/ModelRuntime.ts`：运行时外壳，负责生命周期 hooks、timing、错误回调，以及把真实 provider runtime 包一层。
- `packages/model-runtime/src/core/RouterRuntime/index.ts`：路由型 runtime 的入口。根据命名和导出结构判断，它负责在多个 runtime 之间做选择或尝试。
- `packages/model-runtime/src/providers/openai/index.ts`、`packages/model-runtime/src/providers/anthropic/index.ts`：代表性 provider 入口，展示了“参数构建 + factory 生成 runtime”的标准模式。

## 主流程位置

主流程大致是：

1. 上层从包根入口 `src/index.ts` 或具体 provider 入口拿到 runtime。
2. `ModelRuntime` 先接住请求，执行 `beforeChat`、`onChatFinal`、`onChatError` 这类 hook，再把请求交给具体 provider runtime。
3. provider runtime 一般不是手写完整实现，而是通过 `openaiCompatibleFactory`、`anthropicCompatibleFactory` 这类工厂创建，先在 `handlePayload` 里改写参数，再交给底层 SDK 或 HTTP 调用。
4. 流式返回由 `src/core/streams` 统一解析，不同厂商协议在这里做适配和归一。
5. usage、cost、模型能力判断则分别落在 `src/core/usageConverters`、`src/const/models.ts` 和 `src/utils` 中。

从文件结构看，真正的“分发中枢”主要有三个：`runtimeMap.ts` 负责 provider 选择，`ModelRuntime.ts` 负责生命周期编排，`core/*Factory` 负责把某个厂商协议变成统一 runtime。

## 推荐阅读顺序

1. 先看 `packages/model-runtime/package.json` 和 `src/index.ts`，弄清楚对外暴露了什么。
2. 再看 `src/runtimeMap.ts`，理解 provider 如何注册到统一映射里。
3. 接着看 `src/core/ModelRuntime.ts`，把请求生命周期和 hook 机制串起来。
4. 然后看 `src/providers/openai/index.ts`、`src/providers/anthropic/index.ts` 这种典型适配器，建立“factory + handlePayload”的模式感。
5. 最后补 `src/core/streams`、`src/core/usageConverters`、`src/utils`、`src/types`，把协议、计费和错误归一的边角补齐。

## 常见误区

- 容易把 `src/index.ts` 当成业务实现，但它实际上只是总出口，核心逻辑分散在 `core`、`providers`、`utils` 里。
- 容易只看某一个 provider 文件，忽略 `runtimeMap.ts` 和 `ModelRuntime.ts`。真正的统一行为通常在这两层。
- 容易把 `src/providers` 误解成“同质化实现集合”，其实里面很多目录都带有厂商私有协议差异，比如图片、视频、 coding plan、特殊流格式。
- 容易忽略 `src/const/models.ts`，但这里决定了不少模型级分支，比如 Responses API、流式限制、Claude 参数冲突等。
- 容易只看主路径不看测试。这个目录里测试和快照很多，说明它的协议边界比较脆，改动时最好顺手检查相邻测试文件。
