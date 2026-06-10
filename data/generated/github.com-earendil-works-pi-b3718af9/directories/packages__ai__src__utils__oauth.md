# 目录：packages/ai/src/utils/oauth

## 它负责什么

这个目录是 `packages/ai` 里专门处理 OAuth 凭据生命周期的实现层，职责很集中：把不同 AI 提供方的登录、刷新、凭据存储前置逻辑、以及最终换成可用 API key 的过程统一起来。它不是单一协议实现，而是一个 provider 级的 OAuth 子系统，覆盖 Anthropic、GitHub Copilot、OpenAI Codex 三条主线。

从当前片段看，它还承担了两类横向能力：一类是共享工具，比如 PKCE 生成、device code 轮询、OAuth 回调页；另一类是 provider 注册表，让上层可以按 `id` 找到具体 provider，再调用统一接口。目录外还有一个薄封装 `packages/ai/src/oauth.ts`，只是把这里的 `index.ts` 直接转出，方便更高层引用。

## 直接子目录地图

根据当前片段推断，这里没有更深层的子目录，只有一组平级文件。直接子项可以按角色理解：

- `index.ts`：总入口和注册表。
- `types.ts`：OAuth 相关类型与 provider 接口契约。
- `pkce.ts`：PKCE verifier / challenge 生成。
- `device-code.ts`：RFC 8628 风格的 device code 轮询通用实现。
- `oauth-page.ts`：本地回调服务器返回的成功/失败 HTML 页面。
- `anthropic.ts`：Anthropic 登录、回调、刷新、API key 转换。
- `github-copilot.ts`：GitHub Copilot 登录、刷新、域名归一化、baseUrl 推导。
- `openai-codex.ts`：OpenAI Codex / ChatGPT OAuth 登录与刷新。

如果把它看成一张地图，`index.ts` 在中心，`types.ts` 定规则，`pkce.ts`、`device-code.ts`、`oauth-page.ts` 提供共享零件，三个 provider 文件各自接一条业务流。

## 关键入口

最关键的入口是 `index.ts`。这里先导出各 provider 的公开 API，再建立 `BUILT_IN_OAUTH_PROVIDERS` 和 `oauthProviderRegistry`，然后提供统一操作：

- `getOAuthProvider(id)`：按 provider id 取实现。
- `registerOAuthProvider(provider)` / `unregisterOAuthProvider(id)` / `resetOAuthProviders()`：管理注册表。
- `getOAuthProviders()`、`getOAuthProviderInfoList()`：枚举 provider。
- `refreshOAuthToken(providerId, credentials)`：旧式统一刷新入口。
- `getOAuthApiKey(providerId, credentials)`：更高层的统一入口，必要时先刷新，再把凭据转换成 API key。

上层入口 `packages/ai/src/oauth.ts` 只是 `export * from "./utils/oauth/index.ts";`，所以真正的对外 API 还是这里。

## 主流程位置

主流程可以按“定义契约 -> provider 实现 -> 注册表分发 -> 上层取 key”来读。

1. `types.ts` 定义统一契约：`OAuthCredentials`、`OAuthLoginCallbacks`、`OAuthProviderInterface`。这决定所有 provider 都要提供 `login`、`refreshToken`、`getApiKey`，可选 `modifyModels`。
2. 各 provider 文件实现具体流程：
   - `anthropic.ts` 走本地 callback server + PKCE，配合 `oauth-page.ts` 显示成功/失败页。
   - `github-copilot.ts` 走 device code flow，复用 `device-code.ts` 的轮询器，并根据 token 或企业域名推导 baseUrl。
   - `openai-codex.ts` 同时支持 browser login 和 device code login，也依赖 `pkce.ts`、`oauth-page.ts`、`device-code.ts`。
3. `index.ts` 把这三个 provider 挂进注册表，并提供 `getOAuthApiKey()` 这种面向调用者的收口函数。
4. `packages/ai/src/oauth.ts` 负责把这套能力抛给包外使用者。

如果只看“运行时主线”，最核心的地方其实就两层：`index.ts` 的分发层，以及三个 provider 文件里的 `login` / `refreshToken` / `getApiKey` 实现。

## 推荐阅读顺序

建议按这条顺序读，理解最快：

1. `types.ts`：先确认数据结构和接口约束。
2. `index.ts`：看注册表、统一入口、凭据自动刷新逻辑。
3. `device-code.ts`、`pkce.ts`、`oauth-page.ts`：理解三块共享能力。
4. `anthropic.ts`、`github-copilot.ts`、`openai-codex.ts`：再看各 provider 的具体差异。
5. `packages/ai/src/oauth.ts`：最后看它如何对外暴露。

## 常见误区

- 误以为这里是“一个 OAuth 实现”。实际上它是多个 provider 的统一适配层，核心是抽象和分发，不是单协议实现。
- 误以为 `device-code.ts` 属于某一个 provider。它是共享轮询器，GitHub Copilot 和 OpenAI Codex 都会复用它。
- 误以为 `oauth-page.ts` 负责认证本身。它只负责本地回调页的视觉反馈，真正的交换和刷新在 provider 文件里。
- 误以为 `packages/ai/src/oauth.ts` 是独立逻辑入口。它只是外层 re-export，真正代码都在 `packages/ai/src/utils/oauth`。
- 误以为所有 provider 的登录方式一致。实际上 Anthropic 偏 callback server + PKCE，GitHub Copilot 偏 device code，OpenAI Codex 同时提供 browser 和 device code 两条路。
