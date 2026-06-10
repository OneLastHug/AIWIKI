# 文件：src/services/api/client.ts

## 一句话定位

这是 Claude Code 的统一 API 客户端工厂层，负责把环境变量、登录态、代理、调试日志和多云 provider 选择，收敛成一个可直接发请求的 Anthropic 风格 client。根据当前片段推断，它是上层所有“向模型发起请求”逻辑的公共入口，而不是单一业务模块的私有工具。

## 它暴露/定义了什么

这个文件最核心的导出是 `getAnthropicClient()`，它按调用方给的 `model`、`maxRetries`、`apiKey`、`fetchOverride`、`source` 生成一个客户端实例。除此之外，它还导出常量 `CLIENT_REQUEST_ID_HEADER`，用于给请求打上可追踪的客户端请求 ID。

文件内还定义了几个辅助函数：`createStderrLogger()`、`configureApiKeyHeaders()`、`getCustomHeaders()`、`buildFetch()`。它们不直接对外作为主要 API，但共同组成了客户端创建流程。

## 谁调用它

从当前仓库片段能直接看到它被这些模块调用：`src/services/tokenEstimation.ts`、`src/services/claudeAiLimits.ts`、`src/utils/sideQuery.ts`、`src/utils/model/modelCapabilities.ts`。这些调用点覆盖了 token 统计、配额探测、侧边查询、模型能力刷新等场景，说明它不是“聊天主循环”的单点依赖，而是整个 API 层的基础设施。

根据当前片段推断，更多面向模型请求的模块也可能依赖它，只是片段里没有显式列出。

## 它调用谁

它直接依赖了大量横向基础模块：`src/utils/auth.js` 负责 OAuth、API key、AWS/GCP 认证刷新；`src/utils/model/providers.js` 决定当前 provider；`src/utils/proxy.js` 提供代理 `fetch` 选项；`src/bootstrap/state.js` 提供 session ID 和是否非交互状态；`src/utils/debug.js` 负责调试日志；`src/constants/oauth.js` 提供 OAuth 配置；`src/utils/http.js` 提供 User-Agent；`src/utils/envUtils.js` 处理 region 和布尔环境变量。它还会动态导入 `./bedrockClient.js`、`@anthropic-ai/foundry-sdk`、`@anthropic-ai/vertex-sdk`、`google-auth-library`，以及直接使用 `@anthropic-ai/sdk`。

## 核心流程

1. 先组装默认请求头：`x-app`、`User-Agent`、`X-Claude-Code-Session-Id`、自定义头、容器/远程会话标识、`x-client-app`、`x-auth-nonce` 等。
2. 如果开启了额外保护开关，就补上 `x-anthropic-additional-protection`。
3. 先检查并刷新 OAuth token，再决定是否补 `Authorization` 头。Claude 订阅用户和普通 API key 用户在这里分流。
4. 构造 `fetch` 包装器：仅在 first-party Anthropic 场景注入 `x-client-request-id`，并写入调试日志，方便把超时或失败请求和服务端日志对齐。
5. 按环境变量选择 provider：
   - `CLAUDE_CODE_USE_BEDROCK`：走 Bedrock，处理 AWS region、临时凭证、Bearer token、跳过认证等逻辑。
   - `CLAUDE_CODE_USE_FOUNDRY`：走 Azure Foundry，处理 API key 或 Azure AD token provider。
   - `CLAUDE_CODE_USE_VERTEX`：走 Vertex，处理 GCP 凭证、项目 ID 兜底和 region 选择。
   - 否则回退到第一方 Anthropic client，必要时使用 staging OAuth base URL。
6. 返回最终 client。部分 provider 返回的并不是真正同构的 Anthropic SDK 类型，所以这里用了类型断言来统一上层接口。

## 关键函数的高层作用

`getAnthropicClient()` 是核心：它不是简单 new 一个 SDK，而是在“创建 client”这一刻完成认证、路由、日志、代理和请求归因的统一编排。

`configureApiKeyHeaders()` 负责把 API key/辅助工具产生的 token 写进 `Authorization`，并兼容非交互会话。

`getCustomHeaders()` 把 `ANTHROPIC_CUSTOM_HEADERS` 按行解析成头部字典，支持 curl 风格的 `Name: Value` 写法。它是一个很薄的解析器，但对调试和企业代理场景很关键。

`buildFetch()` 是请求侧的拦截层。它在不改变上层调用方式的情况下，补充请求 ID 和调试日志，并尽量避免把额外头部送到不接受它们的 provider。

## 修改风险

这个文件属于高风险基础件，改动会影响整个模型访问链路。最容易出问题的地方有三个：

第一，认证优先级。`apiKey`、OAuth token、Claude 订阅态、Bedrock/Vertex/Foundry 的凭证顺序如果改错，会直接导致登录失败、鉴权回退错误，或者在非交互模式下卡住。

第二，请求头和 `fetch` 包装。这里的头部既用于内部追踪，也会经过代理和第三方网关。新增或改名很容易触发严格代理拒绝，或者让服务端日志关联失效。

第三，多 provider 兼容分支。Bedrock、Foundry、Vertex 返回值都被强行统一成 `Anthropic`，这意味着类型上看似一致，运行时却可能有细微差异。任何 region 选择、默认 projectId、token 刷新、跳过认证的逻辑调整，都可能带来跨云可用性问题，甚至出现账单或审计归属偏差。根据当前片段推断，这也是作者在 Vertex 分支里专门注明 `projectId` 风险的原因。
