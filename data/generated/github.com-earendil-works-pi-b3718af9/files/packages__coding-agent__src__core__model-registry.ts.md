# 文件：packages/coding-agent/src/core/model-registry.ts

## 一句话定位

`model-registry.ts` 是 coding-agent 的模型与 provider 注册中心：它把 `@earendil-works/pi-ai` 内置模型、用户 `models.json` 自定义模型、扩展动态注册 provider、认证存储和请求级 header/API key 解析统一成一个运行时可查询的 `ModelRegistry`。

## 它暴露/定义了什么

文件主要暴露 `ModelRegistry`、`ProviderConfigInput`、`ResolvedRequestAuth` 和测试用的 `clearApiKeyCache`。内部定义了多组 `typebox` schema，用来校验 `models.json` 中的 provider、model、compat、routing、thinking level、model override 等结构。核心状态包括 `models`、`providerRequestConfigs`、`modelRequestHeaders`、`registeredProviders`、`loadError`、`authStorage`、`modelsJsonPath`。

从外部看，`ModelRegistry` 提供三类能力：模型清单查询，如 `getAll()`、`getAvailable()`、`find()`；认证与展示信息查询，如 `getApiKeyAndHeaders()`、`getProviderAuthStatus()`、`getProviderDisplayName()`、`getApiKeyForProvider()`、`isUsingOAuth()`；动态 provider 生命周期，如 `registerProvider()`、`unregisterProvider()`、`refresh()`。

## 谁调用它

创建入口主要在 `packages/coding-agent/src/core/sdk.ts`、`packages/coding-agent/src/core/agent-session-services.ts` 和 `packages/coding-agent/src/main.ts`，它们用 `ModelRegistry.create(authStorage, modelsPath)` 装配会话或 SDK 运行环境。测试和 harness 也会用 `ModelRegistry.inMemory(authStorage)` 避免读取磁盘配置。

运行期调用者更广：`model-resolver.ts` 用它做模型范围、默认模型和恢复模型解析；`agent-session.ts` 在发请求、压缩、重试、扩展 provider 注册时读取模型和认证；`interactive-mode.ts`、`model-selector.ts` 用它刷新模型列表、显示 provider 名称、检查登录状态；`cli/list-models.ts` 和 `rpc-mode.ts` 用它列出或选择可用模型；扩展系统的 `extensions/runner.ts`、`extensions/loader.ts` 间接触发动态 provider 注册。

## 它调用谁

模型来源依赖 `@earendil-works/pi-ai`：`getProviders()`、`getModels()` 提供内置 provider/model，`registerApiProvider()`、`resetApiProviders()` 管理动态 API stream 实现；OAuth 侧调用 `registerOAuthProvider()`、`resetOAuthProviders()`。认证依赖 `AuthStorage`，包括 `getApiKey()`、`hasAuth()`、`getAuthStatus()`、`getOAuthProviders()`、`get()`。配置值解析依赖 `resolve-config-value.ts`，负责环境变量、命令型配置、header 解析和缓存。文件读取使用 `fs.existsSync/readFileSync`，JSON 注释清理由 `stripJsonComments()` 完成，路径规范化由 `normalizePath()` 完成。

## 核心流程

初始化时，构造函数保存 `AuthStorage` 和可选 `modelsJsonPath`，然后调用 `loadModels()`。`loadModels()` 先读取 `models.json`，得到自定义模型、provider 级覆盖、model 级覆盖和加载错误；即使自定义配置失败，也保留内置模型。之后 `loadBuiltInModels()` 遍历 `pi-ai` 内置 provider/model，套用 provider 的 `baseUrl/compat` 覆盖，再套用单模型 override。接着 `mergeCustomModels()` 合并自定义模型，同 provider+id 冲突时自定义模型胜出。最后，如果当前 auth storage 中存在 OAuth 凭据且 OAuth provider 提供 `modifyModels`，会让 OAuth provider 调整模型，例如更新 `baseUrl`。

请求阶段通常先由 resolver 或 UI 选出 `Model<Api>`，再由 `getApiKeyAndHeaders()` 合并认证和 headers。它优先从 `AuthStorage` 取 provider API key，取不到再解析 `models.json` 或动态注册 provider 中的 `apiKey`；headers 由模型内置 headers、provider headers、model headers 合并，且 model headers 后覆盖 provider headers。若 provider 配置了 `authHeader`，会把 API key 写入 `Authorization: Bearer ...`。

动态扩展阶段，`registerProvider()` 会迁移旧式环境变量写法、校验配置、应用 provider 配置并保存到 `registeredProviders`。如果注册包含 `models`，会替换该 provider 的全部当前模型；如果只有 `baseUrl/headers`，则作为 override 更新已有模型。`unregisterProvider()` 删除动态注册后调用 `refresh()`，重建内置模型、磁盘模型和剩余动态 provider。

## 关键函数的高层作用

`loadCustomModels()` 是磁盘配置入口：读取、去注释、schema 校验、业务校验，并分离出自定义模型、provider override、model override、请求认证配置和 model headers。

`validateConfig()` 和 `validateProviderConfig()` 负责约束配置完整性。前者面向 `models.json`，区分内置 provider 与非内置 provider；后者面向扩展动态注册，要求自定义模型必须有 `baseUrl` 以及 `apiKey` 或 `oauth`。

`parseModels()` 把配置文件里的 model definition 转成 `pi-ai` 的 `Model<Api>`，对内置 provider 可继承默认 `api/baseUrl`，对缺省成本、上下文窗口、输出 token 等填默认值。

`applyModelOverride()` 和 `mergeCompat()` 控制覆盖语义：普通字段直接覆盖，`cost`、`thinkingLevelMap`、`compat` 做浅层或局部深合并，`openRouterRouting`、`vercelGatewayRouting` 也会单独合并，避免整个 compat 被替换。

`refresh()` 是重载入口：清理请求配置、错误、动态 API/OAuth 注册，重新加载磁盘和内置模型，再重放仍然登记的动态 provider。它是 UI 刷新模型、登录状态变化和 unregister 恢复行为的基础。

辅助函数如 `formatValidationPath()`、`storeProviderRequestConfig()`、`storeModelHeaders()`、旧配置迁移函数主要服务错误信息、缓存 key 和向后兼容警告，不是主流程决策点。

## 修改风险

最高风险是合并顺序。当前语义是内置模型先应用 provider/model override，再被自定义模型按 provider+id 覆盖，最后可能被 OAuth `modifyModels` 调整；动态注册含 `models` 时又会替换整个 provider。改变顺序会影响用户 `models.json`、扩展 provider 和 OAuth provider 的优先级。

认证风险也较高。`getApiKeyAndHeaders()` 明确优先 `AuthStorage`，然后才是配置值；`getProviderAuthStatus()` 又刻意不执行命令型配置，只报告来源。如果把 cached/uncached 解析、命令执行或 fallback 策略改错，可能造成 UI 显示已配置但请求失败，或在状态检查时执行外部命令。

schema 与类型风险集中在 `compat`。这里支持 OpenAI completions、OpenAI responses、Anthropic messages 多种兼容字段，但运行时用 union 后再通过类型断言合并。新增 compat 字段时必须同时考虑 `typebox` schema、`ProviderConfigInput`、`ModelOverrideSchema`、`mergeCompat()` 和 `pi-ai` 的真实 `Model<Api>` 类型，否则配置可能通过不了校验，或通过后不会生效。

动态 provider 风险在全局注册。`refresh()` 会调用 `resetApiProviders()`、`resetOAuthProviders()`，然后重放 `registeredProviders`。如果新增状态没有纳入重放，刷新或 unregister 后扩展能力会丢失。反过来，如果 unregister 没有正确清理 provider request config 或 model headers，也可能让已删除 provider 的认证/header 残留。

最后，错误处理策略是“配置文件坏了也保留内置模型”。修改 `loadCustomModels()` 或 `loadModels()` 时不要把 `models.json` 错误升级成整体不可用，除非明确要改变产品行为；否则 `list-models`、交互式模型选择和已有会话恢复都会受到影响。
