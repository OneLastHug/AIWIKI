# 文件：packages/ai/README.md

## 一句话定位
这是 `@earendil-works/pi-ai` 的对外说明书，用来告诉使用者如何通过一个统一接口接入多家 LLM provider、管理模型与上下文、处理 tool calling、以及在不同 provider 之间切换会话。

## 它暴露/定义了什么
根据当前片段推断，它不暴露运行时代码，而是定义了这个包的能力边界和使用方式。README 重点说明了：统一的 `getModel`、`stream`、`complete`、`Context`、`Tool` 等核心概念，TypeBox 类型导出 `Type`、`Static`、`TSchema`，以及支持的 provider 清单、安装方式、快速开始示例和各类高级能力。它还把图像输入、图像生成、thinking/reasoning、停止原因、错误处理、模型与 provider 查询、跨 provider handoff、上下文序列化、浏览器使用、OAuth 登录这些主题串成一条完整使用路径。

## 谁调用它
严格说 README 本身不被程序“调用”，而是被以下对象阅读和依赖：
1. 直接安装 `@earendil-works/pi-ai` 的应用开发者。
2. 在别的包里集成 LLM 能力的工程师，尤其是需要 tool calling、流式输出和上下文持久化的人。
3. 维护上层 agent / CLI / 应用层代码的开发者，他们会先看这份文档确认该包能提供哪些抽象。

## 它调用谁
README 也不“调用”代码，但它显式引用了包内对外 API 和外部能力入口。可理解为它指向：
1. 本包导出的 API：`getModel`、`stream`、`complete`、`Context`、`Tool`、`StringEnum`。
2. TypeBox 生态：用于 schema 定义、校验和类型推导。
3. 各个 provider 的后端接入层：OpenAI、Anthropic、Google、Azure OpenAI、OpenRouter、Bedrock 等。
4. OAuth 与环境变量相关机制：用于 Vertex AI、GitHub Copilot、OpenAI Codex 等登录和鉴权。

## 核心流程
这份 README 的主线很清晰：先说明包的定位，再列 provider，接着给出安装方式和最小可运行示例，然后逐步展开高级能力。使用者通常会按这个顺序理解：先用 `getModel` 选 provider 和模型，再构造 `Context`，把 `Tool` 和消息塞进去；如果需要实时输出就走 `stream`，如果只要一次性结果就走 `complete`。拿到返回值后，可以把消息继续追加回 `context.messages`，再触发 tool execution 或继续对话。README 还把跨 provider handoff、token/cost tracking、context serialization 这些能力放在同一条链路里，说明这个包的目标不是单次请求，而是支持可持续的 agent 会话管理。

## 关键函数的高层作用
`getModel` 用来从 provider 与模型名生成统一的模型句柄，是整个调用链的起点。`stream` 负责流式输出，把文本、thinking、toolcall、done、error 等事件拆开给上层处理，适合交互式场景。`complete` 负责一次性拿完整响应，适合批处理或不需要逐 token 展示的场景。`Context` 是会话载体，承载 system prompt、messages、tools，并可序列化后在模型之间传递。`Tool` 和 `StringEnum` 则是工具定义层，保证参数 schema 可验证、可转换、可跨系统传输。

## 修改风险
这里的风险主要是文档与实际 API 漂移。一旦 README 中的函数名、事件类型、provider 支持列表、OAuth 说明或 TypeBox 用法和源码不一致，就会直接误导下游接入者。另一个风险是示例代码过于完整，任何一个字段名、事件分支或上下文结构变更，都会影响读者对真实协议的理解。由于它覆盖面很广，修改时要特别注意同步更新示例、事件枚举、provider 限制和兼容性说明，否则容易让用户在接入阶段踩坑。
