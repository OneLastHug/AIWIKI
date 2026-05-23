# 文件：packages/model-runtime/src/index.ts
## 一句话定位
这是 `@lobechat/model-runtime` 的总入口和公共导出面。它本身几乎不承载业务逻辑，主要职责是把底层运行时、各家 provider、工具函数和类型统一汇总出来，让上层通过一个包入口就能拿到完整的模型能力。

## 它暴露/定义了什么
这个文件是一个典型的 barrel file，向外暴露三类东西：一类是核心运行时与工厂，比如 `ModelRuntime`、`createOpenAICompatibleRuntime`、`createRouterRuntime`；一类是 provider 实现，比如 `LobeOpenAI`、`LobeAnthropicAI`、`LobeGoogleAI` 等大量具体厂商封装；另一类是通用工具和类型，比如 `consumeStreamUntilDone`、`AgentRuntimeError`、`getModelPricing`、`parseDataUri`、`ModelRuntimeHooks`。  
另外，`package.json` 里把 `.` 指向 `./src/index.ts`，所以它就是这个包的主入口；同一个包还额外暴露了 `./vertexai` 子路径。

## 谁调用它
根据当前片段推断，调用方是整个仓库里所有需要模型能力的上层模块，主要包括服务端路由、运行时包装层和其他业务包。能直接看到的使用方有 `src/server/modules/ModelRuntime/index.ts`、`src/services/chat/mecha/clientModelRuntime.ts`、`src/server/services/memory/userMemory/extract.ts`、`packages/fetch-sse/src/fetchSSE.ts`、`src/app/(backend)/webapi/chat/[provider]/route.ts` 等。它的定位不是“被某一个地方专用调用”，而是仓库级共享基础设施。

## 它调用谁
这个文件本身不做计算，只把外部导入的模块重新导出，所以“调用谁”更准确地说是“它把谁挂到公共 API 上”。真正的执行链发生在被导出的模块里：`ModelRuntime` 会在 `chat()` 里校验能力、执行 hooks，再把请求转给具体 provider runtime；`core/openaiCompatibleFactory` 负责把统一的 payload 转成 OpenAI 兼容请求，并处理流、错误和多模态差异；`runtimeMap.ts` 负责把 provider key 映射到具体实现类，比如 `openai` 对应 `LobeOpenAI`。

## 核心流程
从使用者视角看，流程通常是：先通过这个入口拿到 `ModelRuntime` 或某个 provider 类，再构造 runtime 实例，最后发起 `chat`、`embeddings`、`generateObject`、`createImage`、`createVideo` 之类请求。  
在 `ModelRuntime` 内部，核心路径是“hooks 预处理 -> 交给具体 provider -> 统一错误/回调处理”。如果走 OpenAI 兼容路径，则会先经过 `createOpenAICompatibleRuntime`，再进入消息转换、参数修正、流式响应转换和错误归一化。这一层的价值是把不同厂商差异收敛到同一套上层接口。

## 关键函数的高层作用
`ModelRuntime` 是编排层，负责生命周期钩子、异常回传和统一调用入口。  
`createOpenAICompatibleRuntime` 是适配层工厂，把不同 provider 的差异塞进统一的 OpenAI 风格接口。  
`createRouterRuntime` 是路由层选择器，按模型或 provider 分发到合适 runtime。  
`consumeStreamUntilDone` 用于把流消费到结束，常见于需要等待完整结果的后台任务。  
`pruneReasoningPayload`、`getModelPropertyWithFallback`、`getModelPricing`、`parseDataUri` 这些则属于支撑函数，分别处理推理字段裁剪、模型属性回退、价格读取和 data URI 解析。

## 修改风险
这是高风险入口文件。任何导出增删、重命名或路径变动，都会直接影响大量 `@lobechat/model-runtime` 的调用方，轻则类型报错，重则运行时找不到符号。  
第二个风险是循环依赖和包体积：这里汇总了很多 provider，改动导出顺序或新增依赖时，可能放大初始化副作用。  
第三个风险是公共契约漂移：`ModelRuntime`、`runtimeMap` 和各 provider 的能力声明必须一致，否则会出现“入口能导入，但运行时不支持”的问题。  
最后，`package.json` 的主入口和子路径导出是对外契约，改这里要同步检查下游测试，尤其是 `src/server/modules/ModelRuntime/index.test.ts` 这类覆盖主路径的用例。
