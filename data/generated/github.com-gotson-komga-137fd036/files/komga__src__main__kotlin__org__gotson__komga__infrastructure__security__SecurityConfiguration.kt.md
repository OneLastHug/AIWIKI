# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/security/SecurityConfiguration.kt

## 它负责什么

`SecurityConfiguration.kt` 是 Komga 服务端的核心 Spring Security 配置文件，负责把不同访问入口的认证方式、权限规则、会话策略和安全过滤器串起来。

它主要管四类入口：

1. 普通 REST / OPDS / SSE / OAuth2 / Actuator 入口  
   覆盖 `/api/**`、`/opds/**`、`/sse/**`、`/oauth2/authorization/**`、`/login/oauth2/code/**` 以及 Actuator endpoints。

2. Kobo 同步入口  
   覆盖 `/kobo/**`，使用 URL 中的 token 做 API key 认证，并要求用户具备 `KOBO_SYNC` 角色。

3. KOReader 同步入口  
   覆盖 `/koreader/**`，使用请求头 `X-Auth-User` 做 API key 认证，并要求用户具备 `KOREADER_SYNC` 角色。

4. 普通 API key 入口  
   对主 REST/OPDS/SSE 链路添加 `X-API-Key` 认证过滤器，让调用方可以不走 session/basic/OAuth2，而是通过 API key 访问接口。

这个文件不直接实现“查用户”“校验 token”“生成 session”等底层细节，而是把已有组件装配进 Spring Security 的 `SecurityFilterChain`。真正查用户的是 `KomgaUserDetailsService.kt` 和 `ApiKeyAuthenticationProvider.kt`，真正把 header/URI token 转成认证对象的是 `HeaderApiKeyAuthenticationConverter.kt`、`UriRegexApiKeyAuthenticationConverter.kt`。

## 关键组成

### 类注解

`SecurityConfiguration` 上有三个关键注解：

- `@Configuration`：声明这是 Spring 配置类。
- `@EnableWebSecurity`：启用 Web 安全配置。
- `@EnableMethodSecurity(prePostEnabled = true)`：启用方法级权限注解，例如 Controller 里的 `@PreAuthorize("hasRole('ADMIN')")`。

这意味着权限控制分两层：

- URL 层：在 `SecurityConfiguration.kt` 里配置哪些路径需要认证、哪些路径允许匿名。
- 方法层：在 Controller 或 Service 方法上用 `@PreAuthorize` 做更细粒度限制。

例如 `CommonBookController.kt`、`BookController.kt`、`UserController.kt`、`KoboController.kt`、`OpdsController.kt` 等文件里都有 `@PreAuthorize`，这些注解能生效就是因为这里启用了 `@EnableMethodSecurity`。

### 构造参数

`SecurityConfiguration` 通过构造函数注入了大量安全相关组件：

- `KomgaSettingsProvider`：提供 remember-me 的 key 和有效期。
- `UserDetailsService`：这里实际注入的是 `KomgaUserDetailsService`，按 email 加载用户。
- `ApiKeyAuthenticationProvider`：根据 API key 查找用户。
- `OAuth2UserService<OAuth2UserRequest, OAuth2User>`：处理普通 OAuth2 登录用户。
- `OAuth2UserService<OidcUserRequest, OidcUser>`：处理 OIDC 登录用户。
- `sessionCookieName`：来自 `SessionConfiguration.kt`，值是 `KOMGA-SESSION`。
- `WebAuthenticationDetailsSource`：构建认证 details，项目里是 `UserAgentWebAuthenticationDetailsSource`。
- `SessionRegistry`：来自 Spring Session，用于 session 并发管理。
- `OpdsAuthenticationEntryPoint`：给 OPDS v2 返回特定的 401 响应和认证文档链接。
- `AuthenticationEventPublisher`：发布认证成功/失败事件。
- `TokenEncoder`、`Hasher`：处理 API key 的编码和用于认证对象 name 的 hash。
- `InMemoryClientRegistrationRepository?`：如果存在，说明 OAuth2 client registration 已配置，`oauth2Enabled` 为 `true`。

这里的 `clientRegistrationRepository` 是可空的，配置类用它判断是否启用 OAuth2 登录：

```kotlin
private val oauth2Enabled = clientRegistrationRepository != null
```

所以 OAuth2 不是无条件开启，而是取决于应用是否配置了 OAuth2 client。

### `filterChain`

`filterChain(http: HttpSecurity)` 是主安全链，标了 `@Order(1)`，优先匹配主业务入口。

它的 `securityMatchers` 只让这条链作用于：

- `/api/**`
- `/opds/**`
- `/sse/**`
- `/oauth2/authorization/**`
- `/login/oauth2/code/**`
- Actuator endpoints

主链的核心规则是：

- Actuator health endpoint 允许匿名访问。
- 其他 Actuator endpoint 只允许 `ADMIN`。
- 一些特殊接口允许匿名访问，例如：
  - `/api/v1/claim`
  - `/api/v1/oauth2/providers`
  - `/api/v1/client-settings/global/list`
  - `/api/v1/books/{bookId}/resource/**`
  - `/api/v1/fonts/resource/**`
  - `/opds/v2/auth`
  - `/koreader/users/create`
- `/api/**`、`/opds/**`、`/sse/**` 的其他请求都要求已认证。

主链还配置了：

- `cors {}`：启用 CORS 配置。
- `csrf { disable() }`：关闭 CSRF。
- `headers.cacheControl.disable()`：缓存头交给 `WebMvcConfiguration` 处理。
- `headers.frameOptions.sameOrigin()`：允许同源 iframe，注释说明是为了 epub reader iframe。
- `httpBasic`：启用 HTTP Basic，并绑定 `userAgentWebAuthenticationDetailsSource`。
- `logout`：登出地址是 `/api/logout`，删除 `KOMGA-SESSION` cookie，并让 HTTP session 失效。
- `sessionManagement`：session 按需创建，允许无限 session 数量，使用注入的 `SessionRegistry`。
- `exceptionHandling`：对 `/opds/v2/**` 使用 `OpdsAuthenticationEntryPoint`。
- `rememberMe`：使用 `TokenBasedRememberMeServices`，cookie 名为 `komga-remember-me`。
- `addFilterAfter(restAuthenticationFilter(), BasicAuthenticationFilter::class.java)`：在 Basic 认证过滤器之后添加 REST API key 过滤器。

### OAuth2 登录配置

当 `oauth2Enabled == true` 时，主链会额外启用 `oauth2Login`。

它配置了：

- 普通 OAuth2 user service：`oauth2UserService`
- OIDC user service：`oidcUserService`
- 登录页：`/login`
- 登录成功跳转：`/?server_redirect=Y`
- 登录失败跳转：`/login?server_redirect=Y&error=...`

`KomgaOAuth2UserServiceConfiguration.kt` 里可以看到 OAuth2/OIDC 登录后的用户处理逻辑：

- OAuth2 登录需要拿到 email，否则抛 `ERR_1024`。
- OIDC 登录需要 email；如果开启 email verification，还会检查 `emailVerified`。
- 如果用户已存在，就包装成 `KomgaPrincipal`。
- 如果用户不存在且允许 OAuth2 自动建号，就创建用户。
- 否则抛 OAuth2 错误。

所以 `SecurityConfiguration.kt` 只负责接入 OAuth2 流程，用户映射和自动创建逻辑不在这里。

### `koboFilterChain`

`koboFilterChain(http: HttpSecurity)` 是 `/kobo/**` 专用安全链。

它关闭了：

- CSRF
- form login
- HTTP Basic
- logout

然后设置：

```kotlin
securityMatcher("/kobo/**")
authorize(anyRequest, hasRole(UserRoles.KOBO_SYNC.name))
addFilterBefore<AnonymousAuthenticationFilter>(koboAuthenticationFilter())
```

这表示 Kobo 请求不会走 Basic 登录，也不是普通 Web session 登录，而是通过 `koboAuthenticationFilter()` 尝试认证。认证成功后，还必须有 `KOBO_SYNC` 角色。

`koboAuthenticationFilter()` 使用：

```kotlin
UriRegexApiKeyAuthenticationConverter(Regex("""/kobo/([\w-]+)"""), ...)
```

也就是说它从 URL 中抽取 `/kobo/{token}` 里的 `{token}`。`KoboController.kt` 的注释也说明了 Kobo API key 在 URL 中，例如 `/kobo/<api_key>/v1/library/sync`。

这个链里 session 管理代码被注释掉了，注释说明 Kobo 在收到 session ID cookie header 时，某些请求会出现 JSON 问题，尤其是 `/v1/user/profile`。因此 Kobo 链路刻意避免正常 session cookie 逻辑干扰设备端行为。

### `kosyncFilterChain`

`kosyncFilterChain(http: HttpSecurity)` 是 `/koreader/**` 专用安全链。

它同样关闭：

- CSRF
- form login
- HTTP Basic
- logout

然后设置：

```kotlin
securityMatcher("/koreader/**")
authorize(anyRequest, hasRole(UserRoles.KOREADER_SYNC.name))
addFilterBefore<AnonymousAuthenticationFilter>(kosyncAuthenticationFilter())
```

认证方式来自 `kosyncAuthenticationFilter()`，它使用：

```kotlin
HeaderApiKeyAuthenticationConverter("X-Auth-User", ...)
```

也就是说 KOReader 同步 API 从请求头 `X-Auth-User` 读取 token，并要求认证后的用户有 `KOREADER_SYNC` 角色。

与 Kobo 不同，KOReader 链启用了 session management：

- `SessionCreationPolicy.IF_REQUIRED`
- 使用 `theSessionRegistry`
- `maximumSessions = -1`

### API key 过滤器工厂方法

文件末尾有三个过滤器构造方法：

- `koboAuthenticationFilter()`
- `kosyncAuthenticationFilter()`
- `restAuthenticationFilter()`

三者都创建 `ApiKeyAuthenticationFilter`，区别在于 token 来源不同：

| 方法 | 适用入口 | token 来源 | Converter |
| --- | --- | --- | --- |
| `koboAuthenticationFilter()` | `/kobo/**` | URL `/kobo/{token}` | `UriRegexApiKeyAuthenticationConverter` |
| `kosyncAuthenticationFilter()` | `/koreader/**` | Header `X-Auth-User` | `HeaderApiKeyAuthenticationConverter` |
| `restAuthenticationFilter()` | `/api/**`、`/opds/**`、`/sse/**` 主链 | Header `X-API-Key` | `HeaderApiKeyAuthenticationConverter` |

这些过滤器共用同一个认证管理器：

```kotlin
fun apiKeyAuthenticationProvider(): AuthenticationManager =
  ProviderManager(apiKeyAuthenticationProvider).apply {
    setAuthenticationEventPublisher(authenticationEventPublisher)
  }
```

这里方法名容易误导：`apiKeyAuthenticationProvider()` 返回的是 `AuthenticationManager`，内部包了一层 `ProviderManager`，而真正的 provider 是构造函数注入的 `ApiKeyAuthenticationProvider`。

## 上下游关系

### 上游：Spring Boot / Spring Security 自动装配

`SecurityConfiguration.kt` 被 Spring Boot 启动时扫描为配置类。Spring 会注入它需要的 bean，并调用其中的 `@Bean` 方法生成多个 `SecurityFilterChain`。

它依赖的关键上游配置包括：

- `SessionConfiguration.kt`：提供 `sessionCookieName`、`SessionRegistry`、session cookie serializer、session header resolver。
- `KomgaOAuth2UserServiceConfiguration.kt`：提供 OAuth2/OIDC user service。
- `PasswordEncoderConfiguration.kt`：根据项目结构推断，它通常会为 password/basic 登录提供 password encoder。
- `CorsConfiguration.kt`：为这里的 `cors {}` 提供 CORS 具体规则。
- Spring Boot Actuator：这里通过 `EndpointRequest` 管理 Actuator endpoint 权限。

### 上游：用户与 API key 查询

普通用户名密码或 HTTP Basic 登录最终会用 `KomgaUserDetailsService.kt`：

```kotlin
userRepository.findByEmailIgnoreCaseOrNull(username)
```

查到后包装为 `KomgaPrincipal`。

API key 登录最终会用 `ApiKeyAuthenticationProvider.kt`：

```kotlin
userRepository.findByApiKeyOrNull(authentication.credentials.toString())
```

查到后同样包装为 `KomgaPrincipal`，并把匹配到的 `ApiKey` 放进 principal。

`KomgaPrincipal.kt` 会把用户角色转换成 Spring Security 权限：

```kotlin
SimpleGrantedAuthority("ROLE_$it")
```

因此 `UserRoles.ADMIN` 会变成 `ROLE_ADMIN`，`hasRole('ADMIN')` 才能匹配。

### 下游：Controller 和接口权限

`SecurityConfiguration.kt` 负责先把请求变成“已认证用户”或“匿名/未认证请求”。随后 Controller 方法上的 `@PreAuthorize` 会继续做细粒度判断。

典型下游包括：

- `interfaces/api/rest/UserController.kt`：很多用户管理接口要求 `ADMIN`。
- `interfaces/api/rest/BookController.kt`：部分书籍操作要求 `ADMIN` 或 `PAGE_STREAMING`。
- `interfaces/api/rest/CommonBookController.kt`：下载、页面流等接口要求 `FILE_DOWNLOAD` 或 `PAGE_STREAMING`。
- `interfaces/api/opds/v1/OpdsController.kt`、`interfaces/api/opds/v2/Opds2Controller.kt`：OPDS 部分资源要求 `PAGE_STREAMING`。
- `interfaces/api/kobo/KoboController.kt`：Kobo 入口本身由 `/kobo/**` 链要求 `KOBO_SYNC`，内部部分下载接口还会要求 `FILE_DOWNLOAD`。
- `interfaces/api/kosync/KoreaderSyncController.kt`：KOReader 入口由 `/koreader/**` 链要求 `KOREADER_SYNC`。

也就是说，URL 安全链只解决“能不能进入某类入口”，业务接口能不能执行，还可能由方法级注解决定。

## 运行/调用流程

### 普通 REST 请求：`/api/**`

1. 请求进入 Spring Security。
2. `@Order(1)` 的主 `filterChain` 匹配 `/api/**`。
3. 如果路径在 permit list 中，例如 `/api/v1/claim`，允许匿名继续。
4. 否则要求 authenticated。
5. Spring Security 可能通过 session、HTTP Basic、remember-me 或 API key 完成认证。
6. API key 情况下，请求头 `X-API-Key` 被 `restAuthenticationFilter()` 读取。
7. `HeaderApiKeyAuthenticationConverter` 把 header token 转成 `ApiKeyAuthenticationToken`：
   - `Hasher` 计算 masked token，作为认证对象的 name。
   - `TokenEncoder` 编码 token，作为 credentials。
   - `UserAgentWebAuthenticationDetailsSource` 填充 details。
8. `ApiKeyAuthenticationProvider` 用 credentials 去用户仓库查 API key。
9. 查到后创建 authenticated `ApiKeyAuthenticationToken`，principal 是 `KomgaPrincipal`。
10. 请求继续进入 Controller。
11. 如果 Controller 方法有 `@PreAuthorize`，再按用户角色判断是否允许执行。

### OPDS v2 请求：`/opds/v2/**`

1. 请求进入主 `filterChain`。
2. `/opds/**` 默认要求 authenticated，除 `/opds/v2/auth` 外。
3. 如果未认证，且路径匹配 `/opds/v2/**`，使用 `OpdsAuthenticationEntryPoint`。
4. 返回 401，同时设置：
   - `WWW-Authenticate: Basic realm="Realm"`
   - `Link` header 指向 OPDS auth document
   - body 是 OPDS authentication document JSON

这和普通 REST 401 不完全一样，是为了符合 OPDS 客户端的认证发现流程。

### OAuth2 登录

1. 用户访问 OAuth2 authorization 入口。
2. 主 `filterChain` 匹配 `/oauth2/authorization/**` 或 `/login/oauth2/code/**`。
3. 如果配置了 OAuth2 client registration，则启用 `oauth2Login`。
4. 登录成功后，OAuth2/OIDC user service 根据 email 找到或创建 Komga 用户。
5. 包装成 `KomgaPrincipal`。
6. 成功跳转到 `/?server_redirect=Y`。
7. 失败跳转到 `/login?server_redirect=Y&error=...`。

如果没有 `InMemoryClientRegistrationRepository`，`oauth2Enabled` 为 `false`，这段 OAuth2 登录配置不会启用。

### Kobo 请求：`/kobo/{api_key}/...`

1. 请求进入 `koboFilterChain`。
2. 关闭 Basic、form login、logout、CSRF。
3. `koboAuthenticationFilter()` 在 `AnonymousAuthenticationFilter` 前执行。
4. `UriRegexApiKeyAuthenticationConverter` 从 URI 中匹配 `/kobo/([\w-]+)`，取出 API key。
5. 通过 `ApiKeyAuthenticationProvider` 查用户和 API key。
6. 认证成功后，Spring Security 检查用户是否有 `KOBO_SYNC` 角色。
7. 通过后进入 `KoboController.kt`。

### KOReader 请求：`/koreader/**`

1. 请求进入 `kosyncFilterChain`。
2. 关闭 Basic、form login、logout、CSRF。
3. `kosyncAuthenticationFilter()` 在 `AnonymousAuthenticationFilter` 前执行。
4. `HeaderApiKeyAuthenticationConverter` 从 `X-Auth-User` header 读取 token。
5. 通过 `ApiKeyAuthenticationProvider` 查用户和 API key。
6. 认证成功后，检查用户是否有 `KOREADER_SYNC` 角色。
7. 通过后进入 `KoreaderSyncController.kt`。

## 小白阅读顺序

1. 先看 `SecurityConfiguration.kt` 顶部的构造函数  
   重点理解它没有自己查数据库，而是注入了 `UserDetailsService`、`ApiKeyAuthenticationProvider`、OAuth2 services、session registry 等外部组件。

2. 再看 `filterChain()`  
   这是主入口。先读 `securityMatchers`，搞清楚这条链只管哪些 URL；再读 `authorizeHttpRequests`，区分 permitAll、authenticated、hasRole。

3. 接着看 `koboFilterChain()` 和 `kosyncFilterChain()`  
   这两个是专用链，比主链更容易理解：一个匹配 `/kobo/**`，一个匹配 `/koreader/**`，都靠 API key 认证并要求特定角色。

4. 然后看三个 filter factory  
   也就是 `koboAuthenticationFilter()`、`kosyncAuthenticationFilter()`、`restAuthenticationFilter()`。重点看 token 从哪里来：
   - Kobo：URI
   - KOReader：`X-Auth-User`
   - REST：`X-API-Key`

5. 再跳到 `ApiKeyAuthenticationFilter.kt`  
   看它如何从 converter 拿到 `Authentication`，再交给 `AuthenticationManager` 认证，认证成功后写入 `SecurityContext`。

6. 再跳到 `ApiKeyAuthenticationProvider.kt`  
   看它如何通过 `KomgaUserRepository.findByApiKeyOrNull()` 查 API key，并创建 authenticated token。

7. 最后看 `KomgaPrincipal.kt` 和 `UserRoles.kt`  
   理解为什么 `UserRoles.ADMIN` 会被转换成 `ROLE_ADMIN`，以及 `hasRole('ADMIN')` 是如何匹配上的。

## 常见误区

1. 不要以为这个文件只配置登录页  
   它实际是整个后端认证入口的总装配点，REST、OPDS、SSE、Kobo、KOReader、OAuth2、Actuator 都在这里被分流。

2. 不要把 `hasRole(UserRoles.ADMIN.name)` 理解成直接比较字符串 `ADMIN`  
   Spring Security 的 `hasRole('ADMIN')` 实际匹配的是 authority `ROLE_ADMIN`。项目里的 `KomgaPrincipal` 会把用户角色转换成 `ROLE_$it`，所以两边才能对上。

3. 不要以为所有路径都走同一条安全链  
   主链只匹配 `/api/**`、`/opds/**`、`/sse/**`、OAuth2 和 Actuator。`/kobo/**`、`/koreader/**` 有自己的 `SecurityFilterChain`。

4. 不要以为 API key 只有一种传法  
   这里有三种：
   - REST/OPDS/SSE 主链：`X-API-Key`
   - KOReader：`X-Auth-User`
   - Kobo：URL 中的 `/kobo/{api_key}`

5. 不要以为 `permitAll` 一定覆盖所有链  
   `filterChain()` 的 `authorizeHttpRequests` 里写了 `/koreader/users/create` 的 `permitAll`，但这条主链的 `securityMatchers` 并不包含 `/koreader/**`。根据当前片段推断，这条规则不会作用到 `kosyncFilterChain()`；真正处理 `/koreader/**` 的是后面的 KOReader 专用链，并且它对 `anyRequest` 要求 `KOREADER_SYNC`。如果要确认实际运行行为，需要结合 Spring Security 多链排序和相关测试继续验证。

6. 不要把 `apiKeyAuthenticationProvider()` 当成 provider 本身  
   这个方法名虽然叫 `apiKeyAuthenticationProvider`，但返回类型是 `AuthenticationManager`。它内部用 `ProviderManager` 包装了构造函数注入的 `ApiKeyAuthenticationProvider`。

7. 不要以为 OAuth2 一定启用  
   OAuth2 是否启用取决于 `InMemoryClientRegistrationRepository` 是否存在。没有配置 OAuth2 client registration 时，`oauth2Login` 这段不会生效。

8. 不要忽略 OPDS 的特殊 401 响应  
   `/opds/v2/**` 未认证时使用 `OpdsAuthenticationEntryPoint`，它不仅返回 401，还返回 OPDS authentication document 和 `Link` header。这是给 OPDS 客户端发现认证方式用的，不是普通 REST 错误格式。
