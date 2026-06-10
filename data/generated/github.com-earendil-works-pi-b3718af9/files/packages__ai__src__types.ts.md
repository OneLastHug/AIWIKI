# 文件：packages/ai/src/types.ts
## 一句话定位
这是 `packages/ai` 的公共类型中枢，定义了模型、消息、流式事件、图片生成、兼容参数和 provider 配置的统一契约；`src/index.ts` 直接对外重导出它，仓库里大量 provider、registry、utils、tests 都依赖它作为编译期边界。

## 它暴露/定义了什么
这个文件主要暴露几类核心类型：`Api`、`Provider`、`ImagesApi`、`ImagesProvider` 这类标识符联合类型，`ThinkingLevel`、`StopReason`、`ImagesStopReason` 这类枚举式字符串集合，`StreamOptions`、`ImagesOptions`、`SimpleStreamOptions` 这类调用参数，`UserMessage`、`AssistantMessage`、`ToolResultMessage`、`Message`、`AssistantImages` 这类传输对象，以及 `AssistantMessageEvent` 这种流式协议事件。  
另外还定义了很多 provider 兼容配置，例如 `OpenAICompletionsCompat`、`OpenAIResponsesCompat`、`AnthropicMessagesCompat`、`OpenRouterRouting`。文件顶部还从 `./utils/diagnostics.ts` 和 `./utils/event-stream.ts` 只读引入并重导出诊断和事件流类型。

## 谁调用它
根据当前片段推断，它是 `packages/ai` 的底座类型，被这些地方广泛引用：`src/models.ts`、`src/stream.ts`、`src/images.ts`、`src/api-registry.ts`、`src/images-api-registry.ts`、`src/providers/*`、`src/utils/*`、`scripts/generate-models.ts`，以及大量测试文件。`packages/coding-agent` 的文档也引用了这里定义的消息结构。简单说，只要代码要描述一次 LLM 请求、响应、工具调用或图片生成，通常都会碰到这里的类型。

## 它调用谁
这个文件几乎不做运行时调用，属于纯类型层。它唯一明确依赖的是 `AssistantMessageDiagnostic`、`AssistantMessageEventStream` 和 `TSchema`。其余“调用关系”更多是语义上的：`StreamFunction` 约束实现者必须返回 `AssistantMessageEventStream`，`ImagesFunction` 约束实现者必须返回 `Promise<AssistantImages>`，`Context` 把 `Message[]` 和 `Tool[]` 组合成 provider 的输入。

## 核心流程
核心流程是把一次模型交互拆成三层：  
先由 `Context` 携带 `systemPrompt`、`messages`、`tools` 进入 provider；  
再由 provider 按 `StreamOptions` 或 `ImagesOptions` 生成流式输出，文本侧走 `AssistantMessageEventStream`，图片侧走 `AssistantImages`；  
最后由 `AssistantMessage`、`ToolResultMessage`、`AssistantImages` 这些统一结构承载结果、错误状态、token usage、provider 标识和时间戳。  
`AssistantMessageEvent` 是文本流的协议骨架，规定了 `start`、各类 delta、`done`、`error` 的终止语义。`OpenAI*Compat`、`AnthropicMessagesCompat`、`OpenRouterRouting` 则负责把统一语义翻译成不同厂商 API 的细节。

## 关键函数的高层作用
这个文件没有真正的业务函数，关键的是几个“可调用契约”：  
`StreamFunction` 规定文本流 provider 的输入输出形状；  
`ImagesFunction` 规定图片生成 provider 的输入输出形状；  
`AssistantMessageEvent` 规定流式中间态到终态的演化方式；  
`SimpleStreamOptions` 则把 `reasoning` 和 `thinkingBudgets` 叠加到基础流式参数里，供上层像 `streamSimple()`、`completeSimple()` 这类封装使用。  
如果要理解整个包的执行方式，先看这些类型，就能知道 provider 层、registry 层和消费方之间允许交换什么数据。

## 修改风险
这里是高风险共享文件，改动会向整个 `ai` 包和下游 `coding-agent` 扩散。最常见风险有三类：  
第一，收窄或改名联合类型，会让一批 provider、生成脚本和测试同时失配。  
第二，调整消息结构或 `AssistantMessageEvent`，会破坏流式协议、错误终止语义和序列化格式。  
第三，兼容配置的默认值或字段名变化，会直接影响不同厂商的请求映射、缓存行为和工具调用格式。  
另外，文件里已有少量 `any` 逃逸点，例如 `ToolResultMessage<TDetails = any>` 和 `Tool.arguments: Record<string, any>`；如果要收紧类型，往往会牵出一整条 provider 适配链，不能只改这里。
