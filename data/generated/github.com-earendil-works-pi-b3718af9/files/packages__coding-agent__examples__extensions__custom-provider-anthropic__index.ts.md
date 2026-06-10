# 文件：packages/coding-agent/examples/extensions/custom-provider-anthropic/index.ts
## 一句话定位
这是一个“自定义 Anthropic 提供方”的示例入口，目标不是业务功能本身，而是演示如何把 OAuth、API key、消息转换、工具调用和流式输出接到 `pi` 的扩展体系里，形成一个可被选择的模型提供方。

## 它暴露/定义了什么
文件里主要定义了两类东西：一类是认证相关函数 `loginAnthropic`、`refreshAnthropicToken`；另一类是流式请求与协议适配层 `streamCustomAnthropic`，外加若干转换辅助函数，比如消息块转换、工具名映射、停止原因映射、敏感字符清理。根据当前片段推断，文件尾部还会把这些能力封装成一个可注册的扩展/provider 对象，交给 `ExtensionAPI` 或示例加载器使用。

## 谁调用它
从注释里的用法看，这个文件主要被 `pi -e ...` 这种扩展加载流程调用，也就是 `coding-agent` 的扩展运行时来拉起。更细一点说，运行时会读取这个示例目录，拿到 provider 定义后，再在用户选择 `/model` 时把它接入实际对话。OAuth 场景下，`/login custom-anthropic` 也会触发这里的登录逻辑。

## 它调用谁
它直接调用 `@anthropic-ai/sdk` 的 `Anthropic` 客户端和 `messages.stream`，并依赖 `@earendil-works/pi-ai` 提供的类型、`createAssistantMessageEventStream`、`calculateCost` 等基础设施。认证部分还用到 `fetch`、`crypto.subtle`、`URLSearchParams`、`atob`/`btoa`。扩展层面则依赖 `@earendil-works/pi-coding-agent` 的 `ExtensionAPI` 类型。

## 核心流程
主流程可以理解成“认证判别 -> 参数拼装 -> 流式转发 -> 事件回写”。先通过 `isOAuthToken` 判断当前 `apiKey` 是 OAuth 令牌还是普通 key；再据此配置 Anthropic 客户端头部、beta 能力和 system prompt。随后 `convertMessages` 把 `pi-ai` 的消息结构翻译成 Anthropic messages 格式，`convertTools` 把工具定义翻译成 `input_schema`。发起 `client.messages.stream(...)` 后，代码逐个消费 Anthropic 事件，把文本、thinking、tool_use 等块重新组装成 `AssistantMessageEventStream`，同时更新 token usage 和 cost。若是 OAuth 模式，还会注入“Claude Code”身份相关头部和工具名映射，尽量贴近官方 CLI 行为。

## 关键函数的高层作用
`loginAnthropic` 负责 OAuth PKCE 登录和授权码换 token；`refreshAnthropicToken` 负责刷新过期凭证。`convertMessages` 是最关键的协议桥，负责把用户、助手、工具结果三种消息统一成 Anthropic 可接受的请求体，并处理图像、thinking、连续 tool result 合并。`streamCustomAnthropic` 是总调度器，封装客户端创建、请求参数、流事件解析和输出流写回。其余如 `sanitizeSurrogates`、`mapStopReason`、`toClaudeCodeName` 都属于局部适配，用来避免协议细节把主流程弄脏。

## 修改风险
这类文件的风险主要在协议兼容，不在算法复杂度。改消息转换很容易破坏 tool call 顺序、图像内容格式或 cache_control，导致模型请求异常。改 OAuth 流程会直接影响 `/login`、token 刷新和浏览器直连头部，风险最高。改工具名映射会让“stealth mode”下的 Claude Code 工具行为失配。改 thinking budget 或 stop reason 映射，会影响上层对模型状态的判断。由于它是示例入口，任何字段名、header、beta feature、message 结构变化，都可能把一个“能跑的示例”变成“看起来还在，实际不可用”的状态。
