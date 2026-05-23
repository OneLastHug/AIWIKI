# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/security/oauth2/KomgaOAuth2UserServiceConfiguration.kt

## 它负责什么

`KomgaOAuth2UserServiceConfiguration.kt` 是 Komga 的 OAuth2/OIDC 登录用户适配配置。它不负责发起 OAuth2 授权跳转，也不负责注册 OAuth2 client；它的职责发生在外部身份提供商已经认证完成、Spring Security 准备加载用户信息时。

这个文件主要做三件事：

1. 定义普通 OAuth2 登录使用的 `OAuth2UserService<OAuth2UserRequest, OAuth2User>` Bean。
2. 定义 OIDC 登录使用的 `OAuth2UserService<OidcUserRequest, OidcUser>` Bean。
3. 把外部登录返回的用户身份转换成 Komga 内部可识别的 `KomgaPrincipal`，并绑定到本地 `KomgaUser`。

换句话说，它是“外部账号”和“Komga 本地账号”之间的桥接层。外部服务只提供 OAuth2/OIDC 用户信息；Komga 后续权限判断、角色读取、会话身份都需要基于自己的 `KomgaUser` 模型，因此这里必须根据 email 找到或创建本地用户。

## 关键组成

### `KomgaOAuth2UserServiceConfiguration`

这是一个 Spring `@Configuration` 类，构造函数注入了三个依赖：

- `KomgaUserRepository`：用于按 email 查找本地用户。
- `KomgaUserLifecycle`：用于创建本地用户，并触发用户生命周期逻辑，例如密码编码、事件发布等。
- `KomgaProperties`：读取 Komga 配置项，决定是否允许 OAuth2 自动创建账号、是否要求 OIDC email 已验证。

它暴露两个 `@Bean`：

```kotlin
@Bean
fun oauth2UserService(): OAuth2UserService<OAuth2UserRequest, OAuth2User>
```

```kotlin
@Bean
fun oidcUserService(): OAuth2UserService<OidcUserRequest, OidcUser>
```

这两个 Bean 会被 `SecurityConfiguration` 注入，并挂到 `http.oauth2Login { userInfoEndpoint { ... } }` 上。

### `oauth2UserService()`

这个方法处理普通 OAuth2 provider，例如 GitHub 这类不一定严格走 OIDC 的登录源。

内部先准备两个 delegate：

- `DefaultOAuth2UserService`
- `GithubOAuth2UserService`

选择逻辑是：

```kotlin
when (userRequest.clientRegistration.registrationId.lowercase()) {
  "github" -> githubDelegate
  else -> defaultDelegate
}
```

也就是说，只有 `registrationId` 等于 `github` 时才使用 GitHub 专用逻辑，其余 provider 走 Spring Security 默认的 `DefaultOAuth2UserService`。

加载外部用户后，它会读取：

```kotlin
oAuth2User.getAttribute<String>("email")
```

如果没有 email，直接抛出：

```kotlin
OAuth2AuthenticationException("ERR_1024")
```

拿到 email 后，再调用：

```kotlin
userRepository.findByEmailIgnoreCaseOrNull(email)
```

如果找到了本地用户，就把该用户和外部 `OAuth2User` 包装成：

```kotlin
KomgaPrincipal(existingUser, oAuth2User = oAuth2User)
```

如果没找到，则进入 `tryCreateNewUser(email)`。

### `oidcUserService()`

这个方法处理 OIDC provider。OIDC 用户信息由 Spring Security 的 `OidcUserService` 加载：

```kotlin
val oidcUser = delegate.loadUser(userRequest)
```

然后它做三层校验：

1. `oidcUser.email == null` 时抛 `ERR_1028`。
2. 如果配置 `komga.oidc-email-verification=true`，但 `emailVerified == null`，抛 `ERR_1027`。
3. 如果配置 `komga.oidc-email-verification=true`，但 `emailVerified == false`，抛 `ERR_1026`。

默认配置来自 `KomgaProperties`：

```kotlin
var oauth2AccountCreation: Boolean = false
var oidcEmailVerification: Boolean = true
```

所以默认情况下：

- OAuth2/OIDC 登录不会自动创建 Komga 用户。
- OIDC 登录要求 provider 明确声明 email 已验证。

校验通过后，同样按 email 查找本地用户；找不到则尝试创建；最终返回：

```kotlin
KomgaPrincipal(existingUser, oidcUser)
```

注意这里第二个参数位置是 `oidcUser`，因为 `KomgaPrincipal` 的构造函数是：

```kotlin
KomgaPrincipal(
  val user: KomgaUser,
  val oAuth2User: OAuth2User? = null,
  val oidcUser: OidcUser? = null,
  ...
)
```

在 Kotlin 中调用 `KomgaPrincipal(existingUser, oidcUser)` 会把 `oidcUser` 传给第二个参数 `oAuth2User`，但由于 `OidcUser` 同时也是 `OAuth2User`，这是类型上成立的。这里没有使用命名参数 `oidcUser = oidcUser`，因此 `KomgaPrincipal` 的 `claims`、`idToken`、`userInfo` 是否可用要看后续是否依赖 `oidcUser` 字段。根据当前片段推断，Komga 主要依赖内部 `KomgaUser` 的角色和身份，OIDC claims 不是这个登录链路的主要数据源。

### `tryCreateNewUser(email: String)`

这是一个私有辅助方法：

```kotlin
private fun tryCreateNewUser(email: String) =
  if (komgaProperties.oauth2AccountCreation) {
    logger.info { "Creating new user from OAuth2 login: $email" }
    userLifecycle.createUser(KomgaUser(email, RandomStringUtils.secure().nextAlphanumeric(12)))
  } else {
    throw OAuth2AuthenticationException("ERR_1025")
  }
```

它受 `komga.oauth2-account-creation` 控制。

如果开启自动创建：

- 用 email 构造 `KomgaUser`。
- 随机生成 12 位字母数字密码。
- 调用 `KomgaUserLifecycle.createUser()` 创建本地用户。

这里的随机密码不是给用户直接使用的 OAuth2 登录密码，而是为了满足本地用户模型的 password 字段。`KomgaUserLifecycle.createUser()` 会在保存前编码密码：

```kotlin
userRepository.insert(komgaUser.copy(password = passwordEncoder.encode(komgaUser.password)))
```

如果未开启自动创建，则抛出 `ERR_1025`，登录失败。

### `GithubOAuth2UserService`

同目录的 `GithubOAuth2UserService.kt` 是这个配置文件的重要邻近上下文。

GitHub 的用户信息接口在某些 scope 下可能不会直接返回 `email`。因此这个类继承 `DefaultOAuth2UserService`，在默认加载用户后，如果满足：

- client scopes 包含 `user:email` 或 `user`
- 当前 `OAuth2User` 没有 `email`

就额外请求 GitHub 的 `/emails` 接口，取出：

- `verified == true`
- `primary == true`

的 email，然后放回 `OAuth2User` attributes 中。

这解释了为什么主配置里对 `github` 单独分支：普通 provider 直接拿 user info 就够，GitHub 需要补 email。

## 上下游关系

### 上游：Spring Security OAuth2 登录流程

`SecurityConfiguration.kt` 中注入了这两个 Bean：

```kotlin
private val oauth2UserService: OAuth2UserService<OAuth2UserRequest, OAuth2User>
private val oidcUserService: OAuth2UserService<OidcUserRequest, OidcUser>
```

当检测到 OAuth2 client registration 存在时，会启用：

```kotlin
http.oauth2Login { oauth2 ->
  oauth2.userInfoEndpoint {
    it.userService(oauth2UserService)
    it.oidcUserService(oidcUserService)
  }
}
```

因此调用入口不是业务 Controller，而是 Spring Security 的 OAuth2 登录过滤器链。用户从 `/oauth2/authorization/**` 发起登录，provider 回调 `/login/oauth2/code/**` 后，Spring Security 会调用这里定义的 user service 获取用户信息。

### 中游：外部用户到本地用户的绑定

本文件拿到外部身份后，统一用 email 作为绑定键：

```kotlin
userRepository.findByEmailIgnoreCaseOrNull(email)
```

这意味着 Komga 的 OAuth2/OIDC 账号映射策略是“外部 email 匹配本地 email”，而不是使用 provider user id、subject、issuer 等字段。

普通 OAuth2 分支读取 attributes 中的 `"email"`。

OIDC 分支读取 `oidcUser.email`，并根据配置检查 `emailVerified`。

### 下游：`KomgaPrincipal`

本文件最终返回的不是原始 `OAuth2User` 或 `OidcUser`，而是 `KomgaPrincipal`。

`KomgaPrincipal` 同时实现：

- `UserDetails`
- `OAuth2User`
- `OidcUser`

它的权限来自内部用户：

```kotlin
user.roles.map { SimpleGrantedAuthority("ROLE_$it") }
```

所以外部 provider 返回的权限不会直接成为 Komga 权限。Komga 的授权仍然以本地 `KomgaUser.roles` 为准。

这也是该文件的核心安全边界：OAuth2/OIDC 只证明“这个人是谁”，真正能访问什么由 Komga 内部用户和角色决定。

### 下游：登录失败处理

如果本文件抛出 `OAuth2AuthenticationException`，`SecurityConfiguration` 的 failure handler 会取出错误码：

```kotlin
when (exception) {
  is OAuth2AuthenticationException -> exception.error.errorCode
  else -> exception.message
}
```

然后重定向到：

```text
/login?server_redirect=Y&error=<errorMessage>
```

因此这里的 `ERR_1024`、`ERR_1025`、`ERR_1026`、`ERR_1027`、`ERR_1028` 不是随意字符串，而是会传给前端登录页展示或解析的错误码。

## 运行/调用流程

### 普通 OAuth2 登录流程

1. 用户点击某个 OAuth2 provider 登录。
2. Spring Security 跳转到外部 provider。
3. 外部 provider 认证成功后回调 Komga 的 `/login/oauth2/code/**`。
4. Spring Security 根据 client registration 判断这是普通 OAuth2 登录。
5. 调用 `oauth2UserService()` 返回的 `OAuth2UserService`。
6. 如果 provider registrationId 是 `github`，使用 `GithubOAuth2UserService`；否则使用 `DefaultOAuth2UserService`。
7. delegate 调用 provider 的 user info endpoint，返回 `OAuth2User`。
8. 从 `OAuth2User` attributes 中读取 `"email"`。
9. 如果没有 email，抛 `ERR_1024`，登录失败。
10. 如果有 email，按 email 忽略大小写查询本地用户。
11. 如果本地用户存在，返回 `KomgaPrincipal(existingUser, oAuth2User = oAuth2User)`。
12. 如果本地用户不存在，调用 `tryCreateNewUser(email)`。
13. 如果 `komga.oauth2-account-creation=false`，抛 `ERR_1025`。
14. 如果允许自动创建，创建本地用户，再返回 `KomgaPrincipal`。
15. Spring Security 把 `KomgaPrincipal` 放入认证上下文，后续请求按 Komga 内部角色授权。

### OIDC 登录流程

1. 用户通过 OIDC provider 登录。
2. Spring Security 完成授权码交换和 token 处理。
3. 调用 `oidcUserService()` 返回的 `OAuth2UserService`。
4. `OidcUserService` 加载 `OidcUser`。
5. 检查 `email` 是否存在；不存在抛 `ERR_1028`。
6. 如果 `komga.oidc-email-verification=true`，检查 `emailVerified`。
7. `emailVerified == null` 时抛 `ERR_1027`。
8. `emailVerified == false` 时抛 `ERR_1026`。
9. 通过 email 查找本地用户。
10. 找不到时根据 `komga.oauth2-account-creation` 决定是否创建。
11. 返回 `KomgaPrincipal`，进入 Spring Security 认证上下文。

### 自动创建用户流程

`tryCreateNewUser()` 的行为可以单独理解：

1. 检查 `komgaProperties.oauth2AccountCreation`。
2. 如果关闭，抛 `OAuth2AuthenticationException("ERR_1025")`。
3. 如果开启，记录日志。
4. 创建 `KomgaUser(email, randomPassword)`。
5. 调用 `KomgaUserLifecycle.createUser()`。
6. `KomgaUserLifecycle` 检查 email 是否已存在。
7. 保存前对密码进行编码。
8. 插入用户并重新查询返回创建后的 `KomgaUser`。

这里通过 `KomgaUserLifecycle` 而不是直接调用 repository，是为了复用领域层用户创建规则。

## 小白阅读顺序

1. 先看 `KomgaOAuth2UserServiceConfiguration.kt` 的构造函数，理解它依赖 `KomgaUserRepository`、`KomgaUserLifecycle`、`KomgaProperties`。
2. 再看 `oauth2UserService()`，重点关注普通 OAuth2 登录如何从 attributes 里拿 `"email"`。
3. 接着看 `oidcUserService()`，对比 OIDC 多了哪些 email 校验。
4. 然后看 `tryCreateNewUser()`，理解为什么未开启 `oauth2AccountCreation` 时新用户不能登录。
5. 再读 `GithubOAuth2UserService.kt`，理解 GitHub 为什么要额外请求 `/emails`。
6. 然后看 `SecurityConfiguration.kt` 中 `http.oauth2Login` 的 `userInfoEndpoint` 配置，确认这两个 Bean 的调用入口。
7. 最后看 `KomgaPrincipal.kt`，理解登录成功后 Komga 真正放进认证上下文的对象是什么。

建议带着一个问题读：外部 provider 认证成功后，Komga 凭什么知道这是哪个本地用户？答案就是：这个文件用 email 做映射，并把本地 `KomgaUser` 包装进 `KomgaPrincipal`。

## 常见误区

### 误区一：以为 OAuth2 登录成功就一定能进入 Komga

不是。外部 provider 登录成功只代表 provider 认证通过。Komga 还要求能拿到 email，并且本地存在对应用户，或者配置允许自动创建账号。

可能失败的情况包括：

- 普通 OAuth2 user info 没有 `email`，触发 `ERR_1024`。
- 本地没有对应 email，且 `komga.oauth2-account-creation=false`，触发 `ERR_1025`。
- OIDC 没有 email，触发 `ERR_1028`。
- OIDC 要求验证 email，但 provider 没有返回 `email_verified`，触发 `ERR_1027`。
- OIDC 返回 `email_verified=false`，触发 `ERR_1026`。

### 误区二：以为 provider 的角色或权限会直接进入 Komga

不会。`KomgaPrincipal.getAuthorities()` 使用的是内部 `KomgaUser.roles`。外部 OAuth2/OIDC 的 scopes、claims、groups 在当前文件中没有被映射成 Komga 角色。

根据当前片段推断，Komga 的 OAuth2/OIDC 登录只负责身份认证，不负责自动授权或角色同步。依据是 `KomgaPrincipal` 的 authorities 来自 `user.roles`，而本文件创建用户时只传入 email 和随机密码，没有处理外部角色字段。

### 误区三：以为 GitHub 一定会返回 email

GitHub 的 user info 不一定直接返回 email。`GithubOAuth2UserService` 只有在 scopes 包含 `user:email` 或 `user` 且当前用户属性缺少 email 时，才会额外请求 `/emails`，并选择 primary 且 verified 的 email。

如果 GitHub client 没有合适 scope，或者 `/emails` 请求失败，最终仍可能没有 email，然后主流程会抛 `ERR_1024`。

### 误区四：以为 `oauth2AccountCreation` 默认开启

默认是关闭的：

```kotlin
var oauth2AccountCreation: Boolean = false
```

所以默认行为更保守：管理员需要先在 Komga 中创建对应 email 的用户，外部登录才能映射成功。只有显式开启后，首次 OAuth2/OIDC 登录才会自动创建 Komga 用户。

### 误区五：以为 OIDC email 验证只看 email 是否存在

默认还要求 `emailVerified` 为 `true`：

```kotlin
var oidcEmailVerification: Boolean = true
```

因此 OIDC provider 必须返回可信的 email verification 信息。若 provider 不返回 `email_verified`，默认也会失败。这是一个安全取舍：防止未验证邮箱被用来绑定已有 Komga 账号。

### 误区六：以为这里处理 OAuth2 client 注册配置

这个文件不配置 client id、client secret、authorization uri、token uri 等 OAuth2 client registration。它只处理 user info 加载后的用户映射。OAuth2 是否启用由 `SecurityConfiguration` 中的 `InMemoryClientRegistrationRepository?` 是否存在决定；真正的 client registration 配置在其他 Spring Boot OAuth2 client 配置体系中完成。
