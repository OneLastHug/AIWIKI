# 文件：packages/ai/src/utils/oauth/index.ts
## 一句话定位
这是 `@earendil-works/pi-ai/oauth` 的总入口，负责把各家 OAuth 能力统一成一个可注册、可查询、可刷新、可取 API key 的公共层，同时把 Anthropic、GitHub Copilot、OpenAI Codex 这些具体实现重新导出给上层使用。

## 它暴露/定义了什么
这个文件本质上是“聚合 + 注册中心 + 高层门面”。它先导出 `anthropic.ts`、`github-copilot.ts`、`openai-codex.ts`、`device-code.ts`、`types.ts` 中的能力，再在本文件内维护一个内存里的 `oauthProviderRegistry`。对外可直接使用的核心 API 包括 `getOAuthProvider`、`registerOAuthProvider`、`unregisterOAuthProvider`、`resetOAuthProviders`、`getOAuthProviders`、`getOAuthProviderInfoList`、`refreshOAuthToken`、`getOAuthApiKey`。`packages/ai/src/oauth.ts` 只是简单转发，`packages/ai/package.json` 的 `./oauth` 入口也会把它发布为包级 API。

## 谁调用它
根据当前片段推断，调用方主要是三类：
1. `packages/ai/src/cli.ts`，用于 CLI 层查询可用 OAuth provider。
2. `packages/coding-agent/src/core/auth-storage.ts`、`packages/coding-agent/src/core/model-registry.ts`、`packages/coding-agent/src/core/extensions/loader.ts`，用于账号存储、模型/扩展加载和 provider 注入。
3. 测试与交互 UI，如 `packages/ai/test/oauth.ts`、`packages/coding-agent/test/auth-storage.test.ts`、`packages/coding-agent/src/modes/interactive/components/login-dialog.ts`，用于验证登录、刷新和选择 provider 的流程。

## 它调用谁
它直接依赖 `./anthropic.ts`、`./github-copilot.ts`、`./openai-codex.ts`、`./types.ts`。其中 registry 里的 provider 对象必须实现 `OAuthProviderInterface`，因此 `getApiKey()` 和 `refreshToken()` 这类真正的业务动作都下放给具体 provider。`getOAuthApiKey()` 还会用 `Date.now()` 判断过期时间，并在需要时调用 provider 的 `refreshToken()`。

## 核心流程
这份文件的主线很清楚：先把内置 provider 组装进 `BUILT_IN_OAUTH_PROVIDERS`，再建立 `oauthProviderRegistry`。外部读场景走 `getOAuthProvider(s)`；写场景走 `registerOAuthProvider`、`unregisterOAuthProvider`、`resetOAuthProviders`。当上层需要取服务端 API key 时，`getOAuthApiKey()` 先按 `providerId` 找到账户凭据，发现过期就自动刷新，最后调用 provider 的 `getApiKey()` 产出最终可用的 key，并把刷新后的凭据一并返回。`refreshOAuthToken()` 则是对单个 provider 刷新的薄封装，且已标记为 deprecated。

## 关键函数的高层作用
`getOAuthProvider` 是单点查找入口。`registerOAuthProvider` 和 `unregisterOAuthProvider` 允许扩展或临时替换 provider，其中内置 provider 被注销后会恢复默认实现，这一点避免了测试或插件把核心能力彻底删掉。`resetOAuthProviders` 用于把注册表重置到干净的内置状态。`getOAuthProviderInfoList` 只是兼容旧接口的简化视图，信息量比 `getOAuthProviders()` 少。`getOAuthApiKey` 是最关键的业务门面，承担“检查是否过期、自动刷新、返回可用 key”的完整链路。

## 修改风险
这类文件的风险主要在“全局注册表”而不是单个函数。改动 provider ID、注册顺序或默认内置列表，会同时影响 CLI、编码代理、测试和包外消费者。`unregisterOAuthProvider` 的回退逻辑如果改坏，内置 provider 可能被永久移除，导致后续登录/刷新失效。`getOAuthApiKey()` 里对过期时间和刷新异常的处理也很敏感，异常信息、返回结构或刷新策略变化，都会向上游传播成认证失败或行为不一致。由于它是包级入口，任何破坏性改动都会扩大到 `@earendil-works/pi-ai/oauth` 的所有调用方。
