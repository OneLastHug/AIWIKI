# 文件：packages/coding-agent/examples/extensions/custom-provider-gitlab-duo/index.ts

## 一句话定位

这个文件是一个 `pi-coding-agent` 扩展示例，用来把 GitLab Duo 作为自定义模型 provider 注册进 `pi`，并通过 GitLab AI Gateway 转发到 Anthropic 与 OpenAI 后端流式实现。

## 它暴露/定义了什么

文件主要定义并导出 `MODELS`，这是 GitLab Duo 可用模型清单，包含模型 `id`、展示名、后端类型、代理入口、是否支持 reasoning、输入模态、价格、上下文窗口和最大输出 token 等元数据。它还定义了 `GitLabModel`、`Backend`、`DirectAccessToken` 等本地类型，用于把 GitLab Duo 的模型描述映射到 `pi-ai` 的模型注册格式。

根据当前片段推断，文件底部还会默认导出一个扩展入口函数，接收 `ExtensionAPI`，并调用 `pi.registerProvider("gitlab-duo", ...)`。依据是目标文件注释中的使用方式、`rg` 结果中该文件第 378 行出现 `pi.registerProvider("gitlab-duo", {`，以及 `packages/coding-agent/src/core/extensions/types.ts` 中扩展 API 暴露了 `registerProvider`。

## 谁调用它

它不是业务运行时主动 import 的核心模块，而是由扩展加载器在用户通过 `pi -e ./packages/coding-agent/examples/extensions/custom-provider-gitlab-duo` 启动时加载。调用链大致是：CLI 读取扩展路径，`packages/coding-agent/src/core/extensions/loader.ts` 构造扩展上下文，`packages/coding-agent/src/core/extensions/runner.ts` 执行扩展代码，扩展代码再通过传入的 `ExtensionAPI` 注册 provider。

认证入口由用户交互触发：注释说明用户可以执行 `/login gitlab-duo`，或者设置 `GITLAB_TOKEN`。因此 provider 的实际调用方是模型注册表、会话运行时和交互模式中的模型选择/请求流程，而不是普通应用代码直接调用这里的函数。

## 它调用谁

它调用 `@earendil-works/pi-ai` 提供的模型与流式基础设施，包括 `createAssistantMessageEventStream`、`streamSimpleAnthropic`、`streamSimpleOpenAIResponses` 以及相关类型 `Model`、`Context`、`SimpleStreamOptions`、`OAuthCredentials`、`OAuthLoginCallbacks` 等。

对外部服务，它通过 `fetch` 调用 GitLab OAuth token 接口、GitLab direct access 接口，以及 GitLab AI Gateway 的 Anthropic/OpenAI 代理入口。文档中不展开真实地址，源码中的这些地址可概括为 GitLab 主站、GitLab cloud AI Gateway、Anthropic proxy 和 OpenAI proxy，均属于外部网络依赖。

## 核心流程

第一步是模型注册。扩展加载后，文件把 `MODELS` 转换成 provider 配置，注册名为 `gitlab-duo` 的 provider，并声明一个自定义 API 名称，`rg` 结果显示为 `"gitlab-duo-api"`。这样 `pi` 的模型注册表就能发现这些 GitLab Duo 模型，并把后续请求路由到此 provider 的自定义 stream 逻辑。

第二步是认证。用户可以通过 `/login gitlab-duo` 走 OAuth PKCE：`generatePKCE` 生成 verifier/challenge，`loginGitLab` 让 UI 打开授权地址并提示用户粘贴 callback URL，然后用授权码换取 GitLab access token。也可以通过环境变量或配置传入 token。

第三步是换取 direct access token。真正请求模型前，`getDirectAccessToken` 使用 GitLab access token 调用 direct access 接口，拿到短期 token 和附加 headers，并在内存中缓存约 25 分钟，减少每次模型调用前的认证开销。403 会被翻译成更明确的 GitLab Duo 权限错误。

第四步是流式转发。根据模型的 `backend` 字段选择 Anthropic 或 OpenAI Responses 的 `pi-ai` 内置 simple stream 实现。这里的关键设计是：该扩展不重新实现 Anthropic/OpenAI 协议解析，而是只负责 GitLab Duo 的认证、headers、baseUrl 和模型清单适配，然后委托给成熟的内置流处理器。

## 关键函数的高层作用

`getDirectAccessToken` 是认证桥接函数：把用户的 GitLab access token 转成 GitLab AI Gateway 可用的 direct access token，并维护进程内缓存。它是模型请求前最关键的准备步骤，失败会直接阻断推理请求。

`invalidateDirectAccessToken` 只是清空缓存，通常用于认证失败、token 过期或需要强制刷新时，属于辅助函数。

`generatePKCE` 是 OAuth 安全辅助函数，生成 PKCE verifier 和 challenge，避免在 OAuth 授权码流程中使用客户端密钥。

`loginGitLab` 是登录流程的核心函数：通过 `OAuthLoginCallbacks` 把授权 URL 交给 UI，再从用户粘贴的 callback URL 提取 `code`，最后换取 `OAuthCredentials`。

根据当前片段推断，文件后半段还有一个自定义 stream 函数：它读取 `options.apiKey` 作为 GitLab token，查找 `MODEL_MAP` 中的模型配置，调用 `getDirectAccessToken`，合并 direct access headers，然后按 `backend` 分派到 `streamSimpleAnthropic` 或 `streamSimpleOpenAIResponses`。依据是 `rg` 结果显示第 315 行读取 `options?.apiKey`，第 321 行调用 `getDirectAccessToken`，第 324 行构造 `streamOptions`，且文件开头导入了两个 simple stream 实现。

## 修改风险

最高风险是认证与 header 组装。GitLab direct access 返回的 token 和 headers 需要原样传入 AI Gateway；如果错误覆盖 `Authorization`、遗漏 GitLab 返回的附加 header，或者把用户 GitLab token 当作下游模型 API key 发送，都会导致请求失败或凭据暴露风险。

第二类风险是模型元数据漂移。`MODELS` 中的模型 id、上下文窗口、maxTokens、reasoning、价格和后端类型必须与 GitLab Duo 当前支持能力匹配。错误的 `backend` 会把请求送到错误协议实现；错误的 token 限制会造成运行时截断、服务端拒绝或成本展示不准。

第三类风险是缓存策略。`DIRECT_ACCESS_TTL` 目前是本地固定 25 分钟，如果 GitLab 实际 token 生命周期变化，可能出现过期 token 被复用，或过度频繁刷新。修改缓存时要考虑并发请求共享 `cachedDirectAccess` 的行为。

第四类风险是扩展注册契约。`pi.registerProvider("gitlab-duo", ...)` 的 provider 名、API 名、OAuth 配置和模型列表会被模型注册表、`/login`、模型选择和会话运行时共同依赖。改名会影响用户配置和已保存凭据；改 stream 签名或返回事件流格式会影响 `createAssistantMessageEventStream` 及上层会话消费逻辑。
