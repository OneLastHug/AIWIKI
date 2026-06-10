# 文件：packages/ai/src/env-api-keys.ts

## 一句话定位

`packages/ai/src/env-api-keys.ts` 是 `packages/ai` 中负责把进程环境变量里的模型供应商 API Key 规范化为内部配置结构的入口文件。根据当前片段推断，它的定位不是发起请求，也不是选择模型，而是在运行时启动或创建 provider 前，把 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GEMINI_API_KEY` 等环境变量转换成代码可消费的 API key 映射。

## 它暴露/定义了什么

由于当前可读取证据只确认了文件存在，未能取得源码正文，以下为根据文件名、仓库包名和常见调用方式的高层推断。

该文件大概率暴露一个或多个读取环境变量的函数，例如 `loadEnvApiKeys`、`apiKeysFromEnv` 或类似命名，用于返回“供应商标识 -> API key / base URL / auth 配置”的结构。它也可能定义环境变量名到 provider 名称的映射表，例如 OpenAI、Anthropic、Google/Gemini、Groq、xAI、OpenRouter、Mistral、DeepSeek、Cerebras、本地 OpenAI-compatible 服务等。

它通常不会定义模型列表、provider 客户端或请求协议细节；这些属于 `packages/ai` 中模型注册、provider factory 或 client 层的职责。

## 谁调用它

根据当前片段推断，调用方应位于 `packages/ai` 的 provider 初始化路径，或上层 `packages/coding-agent` 在构造 AI 客户端时调用它。典型调用场景包括：

运行 CLI 或 agent 时，从 `process.env` 自动发现可用 provider；在没有显式配置 key 的情况下补齐认证信息；展示可用模型或 provider 时判断哪些服务具备凭据；测试中临时注入环境变量，验证配置解析结果。

如果仓库有统一的 AI 配置入口，调用链大概率是：CLI / coding-agent 配置层 -> `packages/ai` 配置加载层 -> `env-api-keys.ts` -> provider 创建逻辑。

## 它调用谁

这个文件的下游依赖通常很轻。根据当前片段推断，它主要读取 `process.env` 或接收一个环境对象参数，再调用本包内的 provider 类型、常量或配置结构。它不应直接调用外部模型 API，也不应创建网络客户端。

如果实现较规范，核心函数会接受类似 `NodeJS.ProcessEnv` 的对象，而不是在所有逻辑里直接散落读取 `process.env`，这样便于测试。它可能还会调用字符串清理逻辑，例如过滤空字符串、去除无效值、合并别名环境变量。

## 核心流程

核心流程可以理解为四步。

第一步，收集候选环境变量。文件维护一组“供应商 -> 环境变量名”的映射，例如 OpenAI 使用 `OPENAI_API_KEY`，Anthropic 使用 `ANTHROPIC_API_KEY`，Google/Gemini 可能接受 `GOOGLE_GENERATIVE_AI_API_KEY` 或 `GEMINI_API_KEY` 这类别名。

第二步，读取并过滤。函数从传入的环境对象或 `process.env` 中取值，忽略 `undefined`、空字符串或只包含空白的值，避免把无效 key 写入配置。

第三步，归一化为内部结构。外部环境变量名是面向用户的，内部通常需要 provider id、API key 字段、base URL 字段或 auth 对象。这个文件的核心价值就在于把不稳定、分散的环境变量输入变成稳定的内部数据形状。

第四步，把结果交给上层配置合并。环境变量通常只是配置来源之一，可能会和配置文件、命令行参数、默认 provider 设置合并。优先级应由上层决定，本文件更适合保持“只解析环境，不做全局策略”的边界。

## 关键函数的高层作用

核心函数的职责应是“从环境变量加载 API keys”。它的输入可能是可选的环境对象，输出是 provider key 映射或配置片段。理解它时不要把重点放在每个变量名，而要看它如何保证输出结构稳定、如何处理缺失值，以及是否支持 provider 别名。

映射表类常量的作用是集中维护环境变量约定。新增 provider 时，最小改动通常是在这里增加 provider id 和对应变量名，再确保 provider 初始化层认识这个 id。

辅助函数如果存在，一般只负责判断字符串是否有效、从多个别名中选择第一个可用值、或构造单个 provider 的配置项。这些函数的风险较低，但会影响所有通过环境变量配置 key 的用户。

## 修改风险

最高风险是破坏环境变量兼容性。环境变量名属于用户入口，一旦重命名、删除或改变优先级，现有 CLI、CI、本地 shell 配置都会失效。除非明确做 breaking change，否则应避免无迁移提示地改动。

第二类风险是 provider id 不一致。如果这里输出的 key 和模型注册、provider factory、配置文件 schema 使用的 provider 名称不同，会导致“环境变量存在但系统认为没有配置”的问题。这类错误通常不会在编译期暴露，更多表现为运行时找不到可用 provider。

第三类风险是空值处理。把空字符串当作有效 key 传下去，会把问题延后到远端 API 请求阶段，错误信息更难定位。相反，过度过滤也可能误删用户刻意设置的值。修改时应明确空白、别名和优先级规则。

第四类风险是泄露敏感信息。这个文件不应打印 API key，不应把 key 拼进错误消息，也不应在调试输出里暴露完整值。若需要诊断，只能显示 provider 是否配置或 key 的安全摘要。

新增 provider 时，除了改 `env-api-keys.ts`，还需要同步检查 provider 创建逻辑、模型列表、配置 schema、文档和测试。根据当前片段推断，这个文件处在认证配置入口，改动面看似很小，但会影响所有依赖环境变量启动的 AI 功能。
