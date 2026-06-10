# 文件：packages/ai/src/providers/register-builtins.ts
## 一句话定位
这是 `packages/ai` 里“内建 API provider 注册器”的入口文件，负责把各个模型厂商的 stream 实现懒加载地挂到全局 `api-registry` 上，并在导入时自动完成默认注册。

## 它暴露/定义了什么
它对外主要暴露三类东西：一是注册控制函数 `registerBuiltInApiProviders()`、`resetApiProviders()`、`setBedrockProviderModule()`；二是一组已经包装好的 `streamXXX` / `streamSimpleXXX` 适配器；三是模块初始化副作用，文件末尾直接调用 `registerBuiltInApiProviders()`，所以只要 `src/stream.ts` 或 `src/index.ts` 触发导入，内建 provider 就会自动进入 registry。

文件内部还定义了不少辅助层：`createLazyStream()`、`createLazySimpleStream()`、`forwardStream()`、`createLazyLoadErrorMessage()`，以及一组 `loadXXXProviderModule()`，分别对应 Anthropic、OpenAI、Google、Mistral、Azure OpenAI、Bedrock 等 provider。

## 谁调用它
根据当前片段推断，直接调用方主要有两类。第一类是包内入口：`packages/ai/src/stream.ts` 和 `packages/ai/src/index.ts` 都通过 `import "./providers/register-builtins.ts"` 或 `export * from "./providers/register-builtins.ts"` 触发它的副作用。第二类是运行时重建逻辑：`packages/coding-agent/src/core/model-registry.ts` 和 `packages/coding-agent/src/core/agent-session.ts` 会调用 `resetApiProviders()`，把 provider registry 清空后重新装回默认实现。Bedrock 还有一个专门入口 `packages/coding-agent/src/bun/register-bedrock.ts`，通过 `setBedrockProviderModule()` 注入 Bun 侧的实现。

## 它调用谁
它直接依赖 `../api-registry.ts` 的 `registerApiProvider()`、`clearApiProviders()`，以及 `../utils/event-stream.ts` 的 `AssistantMessageEventStream`。真正执行各 provider 逻辑时，它再去加载 `./anthropic.ts`、`./openai-completions.ts`、`./google.ts` 等模块，并把这些模块里的具体 stream 函数转换成统一形状后注册进去。Bedrock 是特殊分支：通过 `importNodeOnlyProvider()` 动态导入 `./amazon-bedrock.ts`，避免在非 Node 环境误触发。

## 核心流程
核心流程是“先注册壳子，再按需加载实现”。注册时并不把 provider 代码一次性拉进来，而是先用 `createLazyStream()` / `createLazySimpleStream()` 包一层：当上层真正调用某个模型流式接口时，包装器才异步 `import()` 对应 provider 模块，取出具体 stream 函数，再把子流通过 `forwardStream()` 转发到外层 `AssistantMessageEventStream`。

如果模块加载失败，`createLazyLoadErrorMessage()` 会构造一个带 `stopReason: "error"` 的 `AssistantMessage`，然后把错误事件推回调用方，保证失败路径也符合上层协议。`registerBuiltInApiProviders()` 则负责把这些包装后的函数按 `api` 名称逐个注册进全局 registry。`resetApiProviders()` 的语义很简单：先清空，再重装默认内建 provider。

## 关键函数的高层作用
`registerBuiltInApiProviders()` 是主入口，决定有哪些 API 名称被视为“内建能力”。`createLazyStream()` 和 `createLazySimpleStream()` 是最重要的抽象，它们把“加载模块”和“提供流”解耦，避免启动时强依赖所有 provider。`loadBedrockProviderModule()` 是最容易出分支问题的地方，因为它允许外部通过 `setBedrockProviderModule()` 覆盖实现。其余 `loadXXXProviderModule()` 基本都是同一种模式：缓存 Promise、动态导入、映射成统一接口。

## 修改风险
这里的修改风险偏高，主要集中在三点。第一，`api` 字符串是 registry 的主键，改名会直接影响 `stream.ts` 的解析和下游模型配置。第二，懒加载和错误转发是协议的一部分，任何改动都可能让调用方拿不到正确的 `AssistantMessageEventStream` 结束信号。第三，`resetApiProviders()` 会影响整个进程的 provider 状态，和 `coding-agent` 的 refresh/reload 逻辑强绑定，改动注册顺序或覆盖逻辑容易引入“某些 provider 丢失、Bedrock 覆盖失效、重复注册后状态不一致”等问题。
