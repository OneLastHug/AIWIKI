# 目录：komga/src/main/kotlin/org/gotson/komga/infrastructure/security/oauth2

## 它负责什么

这个目录专门处理 Komga 的 OAuth2 / OIDC 登录接入，核心职责不是“做认证协议本身”，而是把外部身份提供方返回的用户信息，转换成 Komga 内部可用的 `KomgaPrincipal` 和本地用户记录。

从当前代码看，它主要解决两类问题：

1. GitHub OAuth2 只返回基础用户信息时，补齐邮箱。
2. 把 OAuth2 / OIDC 登录结果映射到本地用户表，必要时自动创建账户，并交给 Spring Security 后续流程使用。

也就是说，这个目录位于“外部登录系统”和“Komga 本地账号体系”之间，是一层适配器。

## 关键组成

目录里只有两个文件：

- `GithubOAuth2UserService.kt`
- `KomgaOAuth2UserServiceConfiguration.kt`

`GithubOAuth2UserService` 继承自 Spring Security 的 `DefaultOAuth2UserService`。它在 `loadUser()` 里先走标准 OAuth2 用户加载流程，然后在满足条件时额外请求 GitHub 的 `/emails` 接口，尝试把 `email` 填回用户属性里。它只在 `user:email` 或 `user` scope 出现、且当前用户属性里没有 `email` 时才做这一步。若请求失败，会记一条 warn 日志，但不会直接中断登录。

`KomgaOAuth2UserServiceConfiguration` 是 Spring `@Configuration`。它提供两个 Bean：

- `oauth2UserService()`：处理普通 OAuth2 登录，按 `registrationId` 选择 `GithubOAuth2UserService` 或默认 `DefaultOAuth2UserService`
- `oidcUserService()`：处理 OIDC 登录，使用 `OidcUserService` 再做 Komga 自己的校验

这两个 Bean 最终都会把外部用户转换为 `KomgaPrincipal`。如果邮箱找不到本地用户，就会通过 `KomgaUserLifecycle.createUser()` 创建新账号，前提是配置允许。

## 上下游关系

上游是 Spring Security 的 OAuth2/OIDC 登录流程。`SecurityConfiguration` 里把这里提供的 Bean 挂到：

- `oauth2.userInfoEndpoint.userService(oauth2UserService)`
- `oauth2.userInfoEndpoint.oidcUserService(oidcUserService)`

因此真正触发逻辑的入口不是这个目录本身，而是安全链路里的登录请求。

中游依赖包括：

- `KomgaUserRepository`：按邮箱查本地用户
- `KomgaUserLifecycle`：创建新用户
- `KomgaProperties`：控制是否允许 OAuth2 自动建号、是否要求 OIDC 邮箱已验证
- `KomgaPrincipal`：把本地用户和外部身份信息封装成 Spring Security 可用的主体

下游则是整个登录后的授权与会话体系。`KomgaPrincipal` 同时实现 `UserDetails`、`OAuth2User`、`OidcUser`，所以后续的权限判断、会话维持、页面登录态展示都能继续使用它。

根据当前片段推断，这里是 Komga “外部登录统一落地到本地用户”的关键桥梁，而不是单纯的第三方账号登录封装。

## 运行/调用流程

### OAuth2 登录流程

1. 用户通过 OAuth2 发起登录。
2. `SecurityConfiguration` 把请求交给 `oauth2UserService()`。
3. 代码按 `registrationId` 判断：
   - `github` 走 `GithubOAuth2UserService`
   - 其他 provider 走 `DefaultOAuth2UserService`
4. 如果返回的用户里没有 `email`，但 scope 符合 GitHub 邮箱读取条件，则额外请求 GitHub `/emails`。
5. 拿到邮箱后，去 `KomgaUserRepository.findByEmailIgnoreCaseOrNull()` 查本地用户。
6. 找不到则调用 `tryCreateNewUser(email)`：
   - `komgaProperties.oauth2AccountCreation = true` 时创建
   - 否则抛 `OAuth2AuthenticationException("ERR_1025")`
7. 最终返回 `KomgaPrincipal(existingUser, oAuth2User = oAuth2User)`。

### OIDC 登录流程

1. 用户通过 OIDC 登录。
2. `oidcUserService()` 调用 `OidcUserService.loadUser()`。
3. 校验邮箱：
   - `email == null` 抛 `ERR_1028`
   - 如果开启 `oidcEmailVerification`，且 `emailVerified == null` 抛 `ERR_1027`
   - 如果开启 `oidcEmailVerification`，且 `emailVerified == false` 抛 `ERR_1026`
4. 按邮箱查本地用户，查不到则尝试创建。
5. 返回 `KomgaPrincipal(existingUser, oidcUser)`。

### GitHub 邮箱补全流程

1. `GithubOAuth2UserService.loadUser()` 先调用父类拿基础用户信息。
2. 只有在 scope 包含 `user:email` 或 `user`，且当前属性缺少 `email` 时，才会发起额外请求。
3. 用访问令牌调用 `${userInfoEndpoint.uri}/emails`。
4. 在返回列表中筛选 `verified == true` 且 `primary == true` 的邮箱。
5. 失败时只记日志，不阻断登录。

## 小白阅读顺序

1. 先看 `KomgaOAuth2UserServiceConfiguration.kt`，因为它定义了真正被 Spring 注入和调用的 Bean。
2. 再看 `GithubOAuth2UserService.kt`，理解 GitHub 为什么需要额外补邮箱。
3. 接着看 `SecurityConfiguration.kt` 中 `oauth2Login { userService(...); oidcUserService(...) }` 的挂接位置，确认入口。
4. 再看 `KomgaPrincipal.kt`，理解外部身份如何包装成系统内部主体。
5. 最后看 `KomgaProperties.kt` 里的 `oauth2AccountCreation` 和 `oidcEmailVerification`，理解配置开关对流程的影响。

## 常见误区

1. 以为这个目录负责“完整 OAuth2 实现”。实际上它只负责用户信息转换和校验，协议交互仍由 Spring Security 和 provider 完成。

2. 以为 GitHub 登录一定能直接拿到邮箱。实际上这里专门补了一步 `/emails` 请求，说明基础 userInfo 可能不够。

3. 以为只要外部登录成功就一定能进系统。不是，`email` 是这里的关键绑定键，没有邮箱会直接失败，OIDC 还可能因为邮箱验证状态失败。

4. 以为自动建号默认开启。根据当前代码，`oauth2AccountCreation` 默认是 `false`，所以没有显式配置时，找不到本地用户会报错而不是创建账号。

5. 以为 provider 返回什么就直接原样使用。实际上这里会把外部身份统一收敛成 `KomgaPrincipal`，后续系统只认这个内部主体。
