# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/security/KomgaUserDetailsService.kt

## 它负责什么

`KomgaUserDetailsService.kt` 是 Komga 对 Spring Security `UserDetailsService` 接口的实现。它的职责非常集中：当 Spring Security 需要根据登录名加载用户时，它把传入的 `username` 当作用户 email，到 Komga 自己的用户仓储 `KomgaUserRepository` 中查找用户；找到后包装成 `KomgaPrincipal`；找不到则抛出 `UsernameNotFoundException`。

从安全链路角度看，它是“Spring Security 标准认证机制”和“Komga 自己的用户模型”之间的适配层。Spring Security 不直接认识 Komga 的 `KomgaUser`，而是通过 `UserDetails` 抽象工作；这个文件负责把 `KomgaUser` 转成符合 `UserDetails` 的 `KomgaPrincipal`。

代码主体只有一个类：

```kotlin
@Component
class KomgaUserDetailsService(
  private val userRepository: KomgaUserRepository,
) : UserDetailsService {
  override fun loadUserByUsername(username: String): UserDetails =
    userRepository.findByEmailIgnoreCaseOrNull(username)?.let {
      KomgaPrincipal(it)
    } ?: throw UsernameNotFoundException(username)
}
```

## 关键组成

第一组 import 是 Komga 自己的领域接口：

```kotlin
import org.gotson.komga.domain.persistence.KomgaUserRepository
```

`KomgaUserRepository` 位于 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/KomgaUserRepository.kt`，定义了用户持久化查询能力。这里用到的是：

```kotlin
fun findByEmailIgnoreCaseOrNull(email: String): KomgaUser?
```

这个方法按 email 查询用户，并且忽略大小写。它的 JOOQ 实现在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt` 中，核心条件是：

```kotlin
.where(u.EMAIL.equalIgnoreCase(email))
```

所以这里的 `username` 实际上不是传统意义上的独立用户名，而是用户 email。

第二组 import 是 Spring Security 接口和异常：

```kotlin
import org.springframework.security.core.userdetails.UserDetails
import org.springframework.security.core.userdetails.UserDetailsService
import org.springframework.security.core.userdetails.UsernameNotFoundException
```

`UserDetailsService` 是 Spring Security 的用户加载接口。认证流程中，框架会调用：

```kotlin
loadUserByUsername(username: String): UserDetails
```

返回的 `UserDetails` 会提供密码、角色、账号状态等信息。Komga 返回的是 `KomgaPrincipal`，它在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/KomgaPrincipal.kt` 中定义。

第三个关键注解是：

```kotlin
@Component
```

这表示 `KomgaUserDetailsService` 会被 Spring 扫描为 Bean，之后可以通过依赖注入交给安全配置使用。它不是手动 new 出来的服务，而是 Spring 容器管理的安全组件。

`KomgaPrincipal` 是理解这个文件的关键邻近类。它持有：

```kotlin
val user: KomgaUser
```

并实现了 `UserDetails`、`OAuth2User`、`OidcUser`。其中与本文件最直接相关的是 `UserDetails` 部分：

```kotlin
override fun getAuthorities(): MutableCollection<out GrantedAuthority> =
  user.roles
    .map { SimpleGrantedAuthority("ROLE_$it") }
    .toMutableSet()

override fun getUsername() = name
override fun getPassword() = user.password
```

也就是说，`KomgaUserDetailsService` 只负责“查出用户并包装”；真正向 Spring Security 暴露 password、roles、username、账号状态的是 `KomgaPrincipal`。

## 上下游关系

上游是 Spring Security 的认证流程和 Komga 的安全配置。

在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/SecurityConfiguration.kt` 中，构造函数注入的是接口类型：

```kotlin
private val komgaUserDetailsService: UserDetailsService
```

由于 `KomgaUserDetailsService` 标记了 `@Component` 并实现了 `UserDetailsService`，Spring 会把它作为可注入实现。安全配置中有两处直接使用它。

第一处是主安全过滤链：

```kotlin
.userDetailsService(komgaUserDetailsService)
```

这表示 `/api/**`、`/opds/**`、`/sse/**` 等受保护入口在进行基于用户详情的认证时，会使用这个 service 加载用户。

第二处是 remember-me：

```kotlin
TokenBasedRememberMeServices(komgaSettingsProvider.rememberMeKey, komgaUserDetailsService)
```

remember-me token 被校验后，也需要重新加载用户详情，因此同样依赖这个文件。换句话说，普通登录和记住登录状态恢复都会经过同一套“email 查用户 -> 包装 principal”的逻辑。

下游是 `KomgaUserRepository` 和 `KomgaPrincipal`。

`KomgaUserRepository` 是数据访问抽象，下游实现之一是 `KomgaUserDao`。本文件不关心数据库细节，只调用仓储接口：

```kotlin
userRepository.findByEmailIgnoreCaseOrNull(username)
```

查到的领域对象会被包装为：

```kotlin
KomgaPrincipal(it)
```

之后控制器、服务和安全表达式拿到的认证主体通常就是 `KomgaPrincipal`。仓库中大量接口层代码通过 `@AuthenticationPrincipal principal: KomgaPrincipal` 使用当前用户，例如 REST API、OPDS、SSE、Kobo、KOReader 同步等模块。

相关路径包括：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v2/Opds2Controller.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt`。

需要注意，`KomgaPrincipal` 不只服务于本文件。API key 认证、OAuth2/OIDC 认证也会构造 `KomgaPrincipal`。例如 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/apikey/ApiKeyAuthenticationProvider.kt` 会在 API key 认证成功后创建：

```kotlin
KomgaPrincipal(user, apiKey = apiKey, name = authentication.name)
```

OAuth2/OIDC 配置也会根据外部身份匹配本地用户，然后返回 `KomgaPrincipal`。因此本文件是“用户名/密码或 remember-me 这类 Spring Security 用户详情加载”的入口之一，而不是所有认证方式的唯一入口。

## 运行/调用流程

典型的 HTTP Basic 或需要 `UserDetailsService` 的认证流程可以按下面理解：

1. 请求进入 Komga 后端，例如访问 `/api/**`、`/opds/**` 或 `/sse/**`。
2. `SecurityConfiguration` 中的主 `SecurityFilterChain` 对这些路径启用认证规则。
3. 当认证机制需要按用户名加载用户时，Spring Security 调用 `komgaUserDetailsService.loadUserByUsername(username)`。
4. `KomgaUserDetailsService` 把 `username` 当作 email，调用 `KomgaUserRepository.findByEmailIgnoreCaseOrNull(username)`。
5. 如果数据库中存在这个 email 对应的用户，返回 `KomgaUser`。
6. 当前文件用 `KomgaPrincipal(it)` 包装该用户，并把它作为 `UserDetails` 返回给 Spring Security。
7. Spring Security 再通过 `KomgaPrincipal.getPassword()` 获取密码哈希，通过 `getAuthorities()` 获取角色权限，通过 `isEnabled()` 等方法判断账号状态。
8. 如果认证成功，后续控制器可以通过 `@AuthenticationPrincipal principal: KomgaPrincipal` 拿到当前用户。
9. 如果仓储返回 `null`，本文件抛出 `UsernameNotFoundException(username)`，认证失败。

remember-me 的流程也类似，只是入口不同：remember-me token 校验时，`TokenBasedRememberMeServices` 也会用同一个 `UserDetailsService` 根据用户名重新加载用户详情。这样可以保证用户被删除、email 变化或角色变化后，后续请求能基于最新用户数据判断。

这个文件的异常处理也值得注意：

```kotlin
?: throw UsernameNotFoundException(username)
```

这里没有返回空对象，也没有创建匿名用户。找不到用户时必须抛出 Spring Security 识别的标准异常，让认证流程进入失败分支。

## 小白阅读顺序

建议先读 `KomgaUserDetailsService.kt` 本身。这个文件很短，先确认三件事：它是 `@Component`，实现 `UserDetailsService`，唯一方法是 `loadUserByUsername`。

然后读 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/KomgaUserRepository.kt`。重点看 `findByEmailIgnoreCaseOrNull`，理解它是领域层的用户查询接口。这里可以顺便注意还有 `findByApiKeyOrNull`、`existsByEmailIgnoreCase` 等方法，说明用户仓储不仅服务普通登录，也服务 API key 和用户管理逻辑。

第三步读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt` 中的 `findByEmailIgnoreCaseOrNull` 实现。重点是 `u.EMAIL.equalIgnoreCase(email)`，这能解释为什么登录 email 大小写不敏感。

第四步读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/KomgaPrincipal.kt`。这个类回答“查出来的 `KomgaUser` 怎么变成 Spring Security 能理解的用户”。尤其要看 `getAuthorities()`、`getUsername()`、`getPassword()`。

第五步读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/SecurityConfiguration.kt`。重点搜索 `userDetailsService(komgaUserDetailsService)` 和 `TokenBasedRememberMeServices`。这能帮助你把当前文件放回完整安全链路中。

最后可以抽样读一个调用 `@AuthenticationPrincipal principal: KomgaPrincipal` 的控制器，例如 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt`。这样可以看到认证成功后的 principal 如何被业务接口使用。

## 常见误区

第一个误区是把 `username` 理解成独立用户名字段。根据当前文件和仓储实现，`loadUserByUsername(username)` 中的 `username` 实际被当作 email 使用，查询方法也是 `findByEmailIgnoreCaseOrNull`。这是 Spring Security 接口命名和 Komga 业务模型之间的差异。

第二个误区是认为这个文件会校验密码。它不校验密码，只返回包含密码信息的 `UserDetails`。密码比对由 Spring Security 的认证 provider 和 password encoder 处理。本文件只负责“按登录标识加载用户详情”。

第三个误区是认为这个文件决定用户有哪些权限。权限的生成不在这里，而在 `KomgaPrincipal.getAuthorities()` 中完成。它把 `user.roles` 映射为 Spring Security 约定的 `ROLE_xxx`：

```kotlin
SimpleGrantedAuthority("ROLE_$it")
```

所以如果要理解角色授权，应继续看 `KomgaPrincipal`、`UserRoles` 以及使用 `hasRole(...)`、方法级安全注解的地方。

第四个误区是认为找不到用户时返回 `null` 就可以。`UserDetailsService.loadUserByUsername` 的语义要求找不到用户时抛出 `UsernameNotFoundException`。当前文件正是按这个约定实现，否则 Spring Security 的认证失败流程可能无法正确识别。

第五个误区是把 `KomgaUserDetailsService` 看成所有认证方式的中心。它确实是标准用户详情加载入口，也被 remember-me 使用，但 API key、OAuth2、OIDC 等路径也可能直接创建 `KomgaPrincipal`。例如 API key provider 会通过 API key 找到用户，再构造带 `apiKey` 的 principal；OAuth2/OIDC 服务会按外部身份匹配本地用户，再构造带 OAuth/OIDC 信息的 principal。

第六个误区是忽略大小写匹配。这个文件名里没有显示大小写逻辑，但它调用的仓储方法和 DAO 实现明确使用忽略大小写的 email 查询。因此用户用不同大小写输入 email 时，根据当前片段推断，应能匹配同一个账号；依据是 `KomgaUserDao.findByEmailIgnoreCaseOrNull` 使用了 `u.EMAIL.equalIgnoreCase(email)`。
