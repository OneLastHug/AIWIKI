# 目录：komga/src/main/kotlin/org/gotson/komga/infrastructure/security

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/infrastructure/security` 是 Komga 服务端的安全基础设施目录，主要负责把 Spring Security、Spring Session、OAuth2/OIDC、API Key、CORS、登录审计等机制串起来。它不直接实现业务权限判断本身，而是负责“请求进来以后，如何识别用户、如何建立 `SecurityContext`、如何限制入口、如何记录认证活动”。

这个目录的核心职责可以分成几类：

1. HTTP 安全链配置：`SecurityConfiguration.kt` 定义不同 URL 空间的 `SecurityFilterChain`，包括普通 API/OPDS/SSE/Actuator、`/kobo/**`、`/koreader/**`。
2. 用户身份模型：`KomgaPrincipal.kt` 把领域用户 `KomgaUser` 包装成 Spring Security 需要的 `UserDetails`、`OAuth2User`、`OidcUser`。
3. 登录方式适配：支持 Basic Auth、Remember Me、OAuth2/OIDC、Header API Key、URI API Key。
4. 会话处理：`session` 子目录用 Spring Session + Caffeine 管理会话，并支持 Cookie 或 Header 两种 session id 传递方式。
5. 安全辅助配置：CORS、密码编码、Token 编码、OPDS 认证入口、User-Agent 记录等。
6. 登录审计：`LoginListener.kt` 监听 Spring Security 认证成功/失败事件，写入 `AuthenticationActivityRepository`。

## 关键组成

`SecurityConfiguration.kt` 是总入口。它使用 `@EnableWebSecurity` 和 `@EnableMethodSecurity(prePostEnabled = true)` 开启 Web 安全与方法级权限控制。这里定义了三条安全链：

普通链 `filterChain` 使用 `@Order(1)`，匹配 `/api/**`、`/opds/**`、`/sse/**`、OAuth2 登录回调路径以及 Actuator endpoint。它允许匿名访问少数入口，例如 `/api/v1/claim`、`/api/v1/oauth2/providers`、`/opds/v2/auth`、部分资源路径和 KOReader 用户创建接口；其他 `/api/**`、`/opds/**`、`/sse/**` 要求认证。Actuator 的 `HealthEndpoint` 允许匿名，其余 Actuator 只允许 `ADMIN` 角色。

`koboFilterChain` 专门匹配 `/kobo/**`，关闭表单登录、Basic Auth 和 logout，只允许 `KOBO_SYNC` 角色访问，并在 `AnonymousAuthenticationFilter` 前插入 API Key 认证过滤器。它从 URI 中用正则 `/kobo/([\w-]+)` 提取 token。

`kosyncFilterChain` 专门匹配 `/koreader/**`，要求 `KOREADER_SYNC` 角色，从请求头 `X-Auth-User` 取 API Key。普通 REST API 的 API Key 则从 `X-API-Key` 请求头读取。

`apikey` 子目录是自定义 API Key 认证机制。`ApiKeyAuthenticationFilter.kt` 是 `OncePerRequestFilter`，每个请求最多处理一次。它通过 `AuthenticationConverter` 从请求中提取 token，生成未认证的 `ApiKeyAuthenticationToken`，再交给 `AuthenticationManager`。认证成功后，它创建新的 `SecurityContext` 并保存到 `RequestAttributeSecurityContextRepository`。认证失败时返回 `401 Unauthorized`。

`ApiKeyAuthenticationProvider.kt` 是真正查库的地方。它从 token credentials 中拿到已经编码过的 API Key，调用 `KomgaUserRepository.findByApiKeyOrNull` 查找用户和 API Key，成功后返回带 `KomgaPrincipal` 的已认证 `ApiKeyAuthenticationToken`。这里的 `principal.name` 不是明文 token，而是 converter 里用 `Hasher.computeHash` 得到的 masked token，用于日志或显示时避免暴露原始 API Key。

`HeaderApiKeyAuthenticationConverter.kt` 和 `UriRegexApiKeyAuthenticationConverter.kt` 分别负责从 Header 和 URI 中取 token。它们都会做两件事：用 `Hasher` 生成 masked token 作为 principal name，用 `TokenEncoder` 生成可查库的 token hash 作为 credentials。`ApiKeyGenerator.kt` 用 UUID v4 去掉短横线生成 API Key 原文。

`KomgaUserDetailsService.kt` 是传统用户名密码登录的用户加载器。它按 email 忽略大小写查询 `KomgaUserRepository`，找到后包装为 `KomgaPrincipal`，找不到则抛出 `UsernameNotFoundException`。

`KomgaPrincipal.kt` 是本目录最重要的数据承载类之一。它同时实现 `UserDetails`、`OAuth2User`、`OidcUser`，因此同一个 principal 可以被 Basic Auth、OAuth2、OIDC、API Key 多种认证方式复用。它把 `user.roles` 转成 `ROLE_xxx` 格式的 `SimpleGrantedAuthority`，这是 `hasRole(UserRoles.ADMIN.name)` 等规则能工作的基础。

`oauth2` 子目录处理第三方登录映射。`KomgaOAuth2UserServiceConfiguration.kt` 定义 `oauth2UserService` 和 `oidcUserService`。OAuth2 登录时先从 provider 拿用户信息，再要求存在 email；如果本地用户不存在，则根据 `komgaProperties.oauth2AccountCreation` 决定是否自动创建用户。OIDC 登录还会根据 `komgaProperties.oidcEmailVerification` 校验 `emailVerified`。`GithubOAuth2UserService.kt` 是 GitHub 特例：当默认 user info 中没有 email，但 scope 包含 `user:email` 或 `user` 时，会额外请求 GitHub emails endpoint，挑选 primary 且 verified 的 email。

`session` 子目录处理 session。`SessionConfiguration.kt` 开启 `@EnableCaffeineHttpSession`，定义 session cookie 名 `KOMGA-SESSION`、session header 名 `X-Auth-Token`，并用 `SmartHttpSessionIdResolver` 同时支持 Cookie 和 Header。`SmartHttpSessionIdResolver.kt` 的策略很直接：如果请求里有 `X-Auth-Token`，就使用 Header resolver；否则使用 Cookie resolver。`SessionListener.kt` 只做 session 事件 debug 日志。

`CorsConfiguration.kt` 只有在配置项 `komga.cors.allowed-origins` 非空时才注册 CORS 配置。它允许配置中的 origin、所有 HTTP method、credentials，并暴露 `Content-Disposition` 和 session header。这个条件化注册由内部类 `CorsAllowedOriginsPresent` 实现。

`PasswordEncoderConfiguration.kt` 提供两个 bean：密码使用 `BCryptPasswordEncoder`，token 使用 `TokenEncoder`，内部是 SHA-512 hex。注释里明确说明 token 编码必须是确定性的，因为查找 API Key 时只有 token，没有 username，不能像 BCrypt 那样每次盐值不同。

`OpdsAuthenticationEntryPoint.kt` 是 OPDS v2 的专用未认证响应。普通未认证响应通常只是 401，但 OPDS v2 这里会返回认证文档 JSON，设置 `WWW-Authenticate`，并通过 `Link` header 指向 `/opds/v2/auth`。

`UserAgentWebAuthenticationDetails.kt` 和 `UserAgentWebAuthenticationDetailsSource.kt` 扩展 Spring 的 `WebAuthenticationDetails`，把 `User-Agent` 一起放入 authentication details。`LoginListener.kt` 后续会读取这个 details，记录认证活动来源、IP、User-Agent、成功失败和错误信息。

## 上下游关系

上游输入主要来自 HTTP 请求和 Spring Security 事件。

HTTP 请求进入 Spring Security filter chain 后，`SecurityConfiguration.kt` 根据路径选择不同安全链。普通 `/api/**`、`/opds/**`、`/sse/**` 走主链；`/kobo/**` 和 `/koreader/**` 走专门链。路径和 Header 中的 API Key 会被 converter 转成 `ApiKeyAuthenticationToken`。用户名密码登录通过 `KomgaUserDetailsService` 查用户。OAuth2/OIDC 登录通过 `KomgaOAuth2UserServiceConfiguration` 查或创建本地用户。

下游主要是领域层和持久层：

`KomgaUserRepository` 被 `KomgaUserDetailsService`、`ApiKeyAuthenticationProvider`、`LoginListener`、OAuth2 服务使用，用于按 email 或 API Key 查找用户。`KomgaUserLifecycle` 被 OAuth2 自动创建用户流程使用。`AuthenticationActivityRepository` 被 `LoginListener` 使用，用于写入登录审计。`OpdsGenerator` 被 `OpdsAuthenticationEntryPoint` 使用，用于生成 OPDS 认证文档。

和配置系统的关系也很紧密：`KomgaSettingsProvider` 提供 remember-me key 和有效期；`KomgaProperties` 提供 CORS、OAuth2 自动建号、OIDC email 校验等开关；`ServerProperties` 提供 servlet session timeout。

角色权限来自领域模型 `UserRoles`。安全配置里直接使用 `UserRoles.ADMIN`、`UserRoles.KOBO_SYNC`、`UserRoles.KOREADER_SYNC`。具体业务接口中如果还有 `@PreAuthorize` 之类方法级权限，则依赖本目录启用的 `@EnableMethodSecurity` 和 `KomgaPrincipal.authorities`。

## 运行/调用流程

普通 API 请求的大致流程如下：

1. 请求命中 `SecurityConfiguration.filterChain`，例如 `/api/v1/...`。
2. Spring Security 先应用 CORS、禁用 CSRF、配置 headers、session、logout、Basic Auth、Remember Me 等。
3. 如果请求带 `X-API-Key`，`restAuthenticationFilter()` 创建的 `ApiKeyAuthenticationFilter` 会在 `BasicAuthenticationFilter` 后运行。
4. `HeaderApiKeyAuthenticationConverter` 读取 `X-API-Key`，把原始 token 转为 masked principal 和 SHA-512 credentials。
5. `ApiKeyAuthenticationProvider` 用 credentials 查 `KomgaUserRepository.findByApiKeyOrNull`。
6. 查到后生成 `KomgaPrincipal`，其 authorities 来自用户角色。
7. `ApiKeyAuthenticationFilter` 把认证结果写入 `SecurityContext`。
8. 后续授权规则或 controller 方法级权限基于 `SecurityContext.authentication` 判断是否允许访问。
9. 认证成功或失败事件被 `LoginListener` 捕获，并写入认证活动表。

用户名密码或 Basic Auth 的流程类似，但用户加载发生在 `KomgaUserDetailsService.loadUserByUsername`，密码校验使用 `BCryptPasswordEncoder`。成功后 principal 仍然是 `KomgaPrincipal`。

OAuth2 登录流程如下：

1. 如果存在 `InMemoryClientRegistrationRepository`，`SecurityConfiguration` 判断 `oauth2Enabled = true`，启用 `oauth2Login`。
2. 用户从 `/oauth2/authorization/**` 开始授权，provider 回调 `/login/oauth2/code/**`。
3. `oauth2UserService` 或 `oidcUserService` 从 provider 加载用户信息。
4. 服务要求拿到 email。GitHub 场景可能额外调用 emails endpoint 补齐 email。
5. 本地按 email 查用户；不存在则根据配置决定自动创建或抛出 OAuth2 错误。
6. 成功后返回 `KomgaPrincipal`，登录成功跳转到 `/?server_redirect=Y`；失败跳转到 `/login?server_redirect=Y&error=...`。

Kobo 请求流程与普通 API Key 类似，但 token 来源是 URI。`/kobo/{token}/...` 被 `UriRegexApiKeyAuthenticationConverter` 提取 token，认证成功后必须拥有 `KOBO_SYNC` 角色。KOReader 请求则从 `X-Auth-User` 头取 token，认证成功后必须拥有 `KOREADER_SYNC` 角色。

Session 的传递逻辑在 `SmartHttpSessionIdResolver`：请求里有 `X-Auth-Token` 时按 Header 读写 session id；没有时按 `KOMGA-SESSION` Cookie 读写。这个设计让 Web UI 可以走 Cookie，而某些客户端或跨域场景可以走 Header。根据当前片段推断，这也是 CORS 配置暴露 session header 的原因，因为 `CorsConfiguration.kt` 会 `addExposedHeader(sessionHeaderName)`。

## 小白阅读顺序

建议先读 `SecurityConfiguration.kt`。这能建立全局地图：哪些路径受保护、哪些路径匿名、有哪些登录方式、不同 filter chain 分别服务什么客户端。

第二步读 `KomgaPrincipal.kt` 和 `KomgaUserDetailsService.kt`。先理解“认证成功后系统眼里的用户长什么样”。尤其要注意 `KomgaPrincipal` 同时实现了 `UserDetails`、`OAuth2User`、`OidcUser`，这是多认证方式能统一进入 Spring Security 上下文的关键。

第三步读 `apikey/ApiKeyAuthenticationFilter.kt`、`apikey/HeaderApiKeyAuthenticationConverter.kt`、`apikey/UriRegexApiKeyAuthenticationConverter.kt`、`apikey/ApiKeyAuthenticationProvider.kt`。这组文件解释了 Komga 自定义 API Key 的完整闭环：提取 token、编码 token、查库、生成认证结果、写入 `SecurityContext`。

第四步读 `session/SessionConfiguration.kt` 和 `session/SmartHttpSessionIdResolver.kt`。理解 Cookie session 与 Header session 如何共存，尤其是 `KOMGA-SESSION` 和 `X-Auth-Token` 的区别。

第五步读 `oauth2/KomgaOAuth2UserServiceConfiguration.kt` 和 `oauth2/GithubOAuth2UserService.kt`。这里关注外部账号如何映射到本地用户，以及自动创建账号和 email 校验的配置影响。

第六步读辅助类：`CorsConfiguration.kt`、`PasswordEncoderConfiguration.kt`、`TokenEncoder.kt`、`OpdsAuthenticationEntryPoint.kt`、`LoginListener.kt`。这些文件不是主流程入口，但对实际部署、安全响应和审计非常重要。

## 常见误区

误区一：以为所有接口都走同一条认证链。实际上这里至少有三条 `SecurityFilterChain`。普通 API、Kobo、KOReader 的认证入口和角色要求不同。调试认证问题时要先确认请求路径命中了哪条链。

误区二：把 `X-Auth-Token` 和 `X-API-Key` 混为一谈。`X-API-Key` 是普通 REST API 的 API Key 认证头；`X-Auth-Token` 是 session id header，由 `SmartHttpSessionIdResolver` 处理；`X-Auth-User` 则用于 KOReader API Key 认证。

误区三：以为 API Key 会以明文参与查库或日志。converter 会把原始 token 用 `TokenEncoder` 转成 SHA-512 credentials 供查库，同时用 `Hasher.computeHash` 生成 masked token 作为 principal name。根据当前片段推断，明文 token 只在请求解析瞬间出现，不应被持久化或记录。

误区四：以为 OAuth2 登录一定会自动创建用户。是否自动创建取决于 `komgaProperties.oauth2AccountCreation`。如果关闭，外部账号 email 在本地不存在时会抛出 `ERR_1025`。

误区五：忽略 GitHub email 的特殊处理。GitHub user info 中 email 可能为空，所以 `GithubOAuth2UserService` 会在有合适 scope 时额外请求 `/emails`，挑选 primary 且 verified 的 email。

误区六：把 OPDS 未认证响应当成普通 401。`OpdsAuthenticationEntryPoint` 对 `/opds/v2/**` 返回的是 OPDS 认证文档 JSON，并设置 `WWW-Authenticate` 和 `Link` header，这是为了适配 OPDS 客户端协议。

误区七：认为 `CorsConfiguration.kt` 总是生效。它只有在 `komga.cors.allowed-origins` 非空时才注册 `corsConfigurationSource`。如果没有配置 allowed origins，就不会按这里的 bean 暴露 CORS 行为。

误区八：把 `TokenEncoder` 当成密码编码器。密码用 `BCryptPasswordEncoder`，token 用确定性的 SHA-512。两者设计目标不同：密码校验可以依赖盐和非确定性格式，API Key 查找必须能从请求 token 稳定算出同一个存储值。
