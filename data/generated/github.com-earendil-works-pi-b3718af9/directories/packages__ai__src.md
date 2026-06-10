# 目录：packages/ai/src

## 它负责什么

`packages/ai/src` 是仓库中 AI 能力的底层适配包源码目录，角色更像“统一 AI SDK 内核”，而不是某个具体产品界面。它把不同模型供应商、模型元数据、流式输出、工具调用校验、OAuth 登录、图片生成、代理/诊断等能力封装成统一接口，供上层 CLI、TUI、coding-agent 等包调用。

从 `index.ts` 的导出可以看出，这个目录对外暴露的核心面包括：模型注册与查询、API provider 注册、文本/对话流处理、图片生成、会话资源清理、TypeBox schema 辅助、工具参数校验、OAuth 类型，以及各 provider 的配置类型。也就是说，上层通常不直接依赖 `providers/openai-responses.ts` 之类的具体实现，而是通过 `models.ts`、`api-registry.ts`、`stream.ts`、`types.ts` 这些统一层进入。

这个目录的边界也比较清晰：它负责“如何和 AI provider 打交道”，不负责终端 UI、不负责项目工作流编排，也不负责 coding-agent 的业务策略。模型清单文件如 `models.generated.ts`、`image-models.generated.ts` 是数据来源，具体 provider 文件负责协议转换和请求实现，公共类型和注册表负责把这些实现组织起来。

## 直接子目录地图

`packages/ai/src/providers` 是最重要的子目录，承载各家模型 API 的实现和注册逻辑。这里有 `anthropic.ts`、`google.ts`、`google-vertex.ts`、`mistral.ts`、`amazon-bedrock.ts`、`azure-openai-responses.ts`、`openai-responses.ts`、`openai-completions.ts`、`openai-codex-responses.ts`、`cloudflare.ts`、`faux.ts` 等文件。`register-builtins.ts` 负责把内置文本 provider 注册进统一注册表；`transform-messages.ts`、`simple-options.ts`、`openai-responses-shared.ts`、`openai-prompt-cache.ts`、`github-copilot-headers.ts` 这类文件是 provider 实现之间复用的转换和辅助层。`faux.ts` 是测试/假 provider 入口，常用于不访问真实外部模型的测试。

`packages/ai/src/providers/images` 是图片 provider 的注册区域。顶层的 `images.ts` 会导入 `./providers/images/register-builtins.ts`，再通过 `images-api-registry.ts` 找到对应图片 API provider，最后调用 `provider.generateImages(...)`。

`packages/ai/src/utils` 是跨 provider 的工具层。这里包括流式事件处理 `event-stream.ts`、JSON 修复和流式解析 `json-parse.ts`、工具参数校验 `validation.ts`、上下文溢出识别 `overflow.ts`、诊断信息 `diagnostics.ts`、HTTP proxy 解析 `node-http-proxy.ts`、abort signal 合并 `abort-signals.ts`、Unicode 清理 `sanitize-unicode.ts`、TypeBox 辅助 `typebox-helpers.ts` 等。它不是业务入口，但很多主流程会依赖这些基础能力。

`packages/ai/src/utils/oauth` 是 OAuth 支持目录。从 `index.ts` 的导出看，对外主要暴露 `OAuthCredentials`、`OAuthProviderInterface`、`OAuthPrompt`、`OAuthSelectPrompt` 等类型；`cli.ts` 则通过 `getOAuthProvider`、`getOAuthProviders` 做登录交互。

## 关键入口

`packages/ai/src/index.ts` 是包级公共入口。它集中 re-export 了模型、注册表、流、类型、图片、校验、诊断、OAuth 类型和内置 provider 注册逻辑。学习这个目录时，先看 `index.ts` 可以快速判断哪些能力是公开 API，哪些只是内部实现细节。

`packages/ai/src/types.ts` 是类型中心。虽然当前读取没有逐段展开该文件，但根据 `images.ts`、`utils/oauth/types.ts`、`utils/validation.ts` 的导入关系可以确认，`Model`、`Api`、`AssistantImages`、`ImagesApi`、`ImagesModel`、`Tool`、`ToolCall` 等跨模块类型都汇聚在这里或由这里参与组织。理解它有助于看懂 provider 函数签名。

`packages/ai/src/models.ts` 和 `packages/ai/src/models.generated.ts` 是文本模型元数据入口。`models.generated.ts` 是生成文件，保存已知 provider/model 的静态数据；`models.ts` 通常承担注册、查询、筛选这些数据的运行时接口。注意仓库规则里明确不应直接改 `models.generated.ts`，而应改生成脚本后再生成。

`packages/ai/src/api-registry.ts` 是文本 provider 注册表入口。provider 实现会注册到这里，上层根据模型的 `api` 或 provider 标识解析到具体实现。与之对应，图片能力使用 `images-api-registry.ts`、`image-models.ts`、`image-models.generated.ts`、`images.ts`。

`packages/ai/src/stream.ts` 是对话/文本生成的关键流程入口之一。根据目录命名和 `index.ts` 导出，它承担统一流式响应抽象，provider 返回的增量事件最终会被整理成上层可消费的 assistant message、tool call、usage、stop reason 等结构。具体细节需继续阅读该文件确认。

`packages/ai/src/cli.ts` 是这个包自带的轻量命令行入口，主要面向 OAuth 登录和 provider 列表，不是模型对话主入口。它读取/写入 `auth.json`，支持 `login [provider]` 和 `list`。

## 主流程位置

文本模型调用的主流程可以按“模型元数据 -> provider 注册 -> 请求转换 -> 流式归一化”来理解。模型列表来自 `models.generated.ts`，运行时查询在 `models.ts`；API provider 由 `providers/register-builtins.ts` 注册到 `api-registry.ts`；具体请求实现位于 `providers/*.ts`，例如 OpenAI Responses、Anthropic、Google、Mistral、Bedrock 等；跨 provider 的消息转换通常经过 `providers/transform-messages.ts` 或 provider 内部转换；最终流式事件和 assistant message 处理集中在 `stream.ts` 及 `utils/event-stream.ts` 一带。

工具调用相关流程主要落在 `types.ts` 和 `utils/validation.ts`。`validation.ts` 使用 TypeBox 编译 schema，对 `ToolCall.arguments` 做结构校验和部分类型 coercion，并生成可读错误。上层 agent 在执行工具前应通过这里保证参数符合声明。

图片生成的主流程更短：`image-models.generated.ts` 提供图片模型数据，`image-models.ts` 提供 `getImageModel`、`getImageProviders`、`getImageModels` 等查询函数，`providers/images/register-builtins.ts` 注册图片 provider，`images.ts` 的 `generateImages(...)` 根据 `model.api` 从 `images-api-registry.ts` 取 provider，然后调用 `provider.generateImages(model, context, options)`。

OAuth 主流程在 `cli.ts` 与 `utils/oauth`。`cli.ts` 根据用户选择调用对应 provider 的 `login(...)`，provider 通过 prompt/callback 完成设备码、选择项或授权信息采集，最后把 credentials 写入本地 `auth.json`。根据当前片段推断，真正的 OAuth provider 适配实现集中在 `utils/oauth/index.ts` 及其邻近文件，依据是 `cli.ts` 从该路径导入 `getOAuthProvider`、`getOAuthProviders`。

## 推荐阅读顺序

1. 先读 `packages/ai/src/index.ts`，建立公开 API 边界，区分哪些文件是包外使用者真正会碰到的入口。
2. 再读 `packages/ai/src/types.ts`，把 `Model`、`Api`、message、tool、usage、image 相关类型串起来。
3. 接着读 `packages/ai/src/models.ts`、`packages/ai/src/api-registry.ts`、`packages/ai/src/providers/register-builtins.ts`，理解“模型如何映射到 provider”。
4. 选择一个 provider 深入，例如 `packages/ai/src/providers/openai-responses.ts` 或 `packages/ai/src/providers/anthropic.ts`，对照 `providers/transform-messages.ts` 看消息格式如何被翻译。
5. 读 `packages/ai/src/stream.ts` 和 `packages/ai/src/utils/event-stream.ts`，理解流式事件如何被抽象成统一输出。
6. 最后按需求补读专题：工具校验看 `utils/validation.ts`，上下文溢出看 `utils/overflow.ts`，图片生成看 `images.ts`、`image-models.ts`、`images-api-registry.ts`，OAuth 看 `cli.ts`、`utils/oauth`。

## 常见误区

不要把 `providers` 下的某个具体文件当成全局入口。它们是适配层，实现各自 API 协议；真正的公共入口是 `index.ts`，运行时分发靠 `api-registry.ts` 和内置注册逻辑。

不要直接修改 `models.generated.ts` 或 `image-models.generated.ts` 来增删模型。它们是生成结果，正确路径应从生成脚本或模型数据来源入手，否则后续生成会覆盖手工修改。

不要把 `cli.ts` 理解为这个包的完整聊天 CLI。它主要处理 OAuth 登录/列出 provider，不代表上层 `pi` 命令的交互主流程。

不要假设所有 provider 返回同一种原生事件格式。这个目录存在 `stream.ts`、`event-stream.ts`、`transform-messages.ts` 和多个 shared helper，正是为了把差异收敛到统一类型。

不要跳过 `utils/validation.ts`。工具调用参数不是简单透传，目录中有明确的 TypeBox 校验、coercion 和错误格式化逻辑；理解 agent 工具执行问题时，这里通常是关键路径之一。
