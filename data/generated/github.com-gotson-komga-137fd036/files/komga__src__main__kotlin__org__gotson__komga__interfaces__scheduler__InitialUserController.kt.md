# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/InitialUserController.kt

## 它负责什么

`InitialUserController.kt` 负责在应用启动完成后，按条件自动创建“初始用户”。

它的作用不是普通的用户注册接口，也不是后台定时任务，而是一个 Spring 启动阶段的初始化控制器：当应用处于 `noclaim` profile，且数据库里还没有任何用户时，它会把预先定义好的 `initialUsers` 写入数据库。

这个文件解决的是 Komga 首次启动时的账号引导问题：

- 在开发环境 `dev` 下，创建固定的两个用户：
  - `admin@example.org / admin`，拥有全部 `UserRoles`
  - `user@example.org / user`，使用 `KomgaUser` 默认角色
- 在非开发环境 `!dev` 下，创建一个管理员用户：
  - `admin@example.org`
  - 随机生成 12 位字母数字密码
  - 拥有全部 `UserRoles`
- 创建完成后，会把登录邮箱和明文初始密码写入日志，方便部署者首次登录。

它只在 `@Profile("!test & noclaim")` 条件下启用，也就是说：

- `test` profile 下不启用；
- 必须显式启用 `noclaim` profile 才会启用；
- 如果已有用户，则不会重复创建。

## 关键组成

这个文件里有三个主要类。

`InitialUserController` 是核心启动控制器：

```kotlin
@Profile("!test & noclaim")
@Component
class InitialUserController(
  private val userLifecycle: KomgaUserLifecycle,
  private val initialUsers: List<KomgaUser>,
)
```

它通过构造函数注入两个依赖：

- `KomgaUserLifecycle`：领域服务，负责真正创建用户、统计用户数量、编码密码等。
- `List<KomgaUser>`：由下面两个配置类根据 profile 提供的初始用户列表。

核心方法是：

```kotlin
@EventListener(ApplicationReadyEvent::class)
fun createInitialUserOnStartupIfNoneExist()
```

`ApplicationReadyEvent` 表示 Spring Boot 应用已经启动完成。监听这个事件的好处是：数据库、Repository、服务 Bean 等基础设施通常已经准备好，此时再执行初始化用户逻辑更稳妥。

方法内部逻辑很简单：

```kotlin
if (userLifecycle.countUsers() == 0L) {
  initialUsers.forEach {
    userLifecycle.createUser(it)
    logger.info { "Initial user created. Login: ${it.email}, Password: ${it.password}" }
  }
}
```

它先调用 `countUsers()` 判断数据库中是否没有用户。只有数量为 `0` 时才遍历 `initialUsers` 并调用 `createUser()`。

`InitialUsersDevConfiguration` 是开发环境配置：

```kotlin
@Configuration
@Profile("dev")
class InitialUsersDevConfiguration {
  @Bean
  fun initialUsers(): List<KomgaUser> =
    listOf(
      KomgaUser("admin@example.org", "admin", roles = UserRoles.entries.toSet()),
      KomgaUser("user@example.org", "user"),
    )
}
```

这里提供一个名为 `initialUsers` 的 Bean，类型是 `List<KomgaUser>`。开发环境使用固定密码，方便本地调试。

第一个用户显式传入：

```kotlin
roles = UserRoles.entries.toSet()
```

表示拥有 `UserRoles` 枚举中的全部角色，包括 `ADMIN`、`FILE_DOWNLOAD`、`PAGE_STREAMING`、`KOBO_SYNC`、`KOREADER_SYNC`。

第二个用户没有传 `roles`，因此使用 `KomgaUser` 默认值。根据 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt`，默认角色是：

```kotlin
setOf(UserRoles.FILE_DOWNLOAD, UserRoles.PAGE_STREAMING)
```

所以 `user@example.org` 不是管理员，只是普通用户。

`InitialUsersProdConfiguration` 是非开发环境配置：

```kotlin
@Configuration
@Profile("!dev")
class InitialUsersProdConfiguration {
  @Bean
  fun initialUsers(): List<KomgaUser> =
    listOf(
      KomgaUser("admin@example.org", RandomStringUtils.secure().nextAlphanumeric(12), roles = UserRoles.entries.toSet()),
    )
}
```

它同样提供 `initialUsers` Bean，但只创建一个管理员用户。密码由：

```kotlin
RandomStringUtils.secure().nextAlphanumeric(12)
```

生成，长度为 12，内容为字母数字。这里使用的是 Apache Commons Lang 的 `RandomStringUtils.secure()`，语义上是安全随机生成器，不是硬编码默认密码。

需要注意，`InitialUsersDevConfiguration` 和 `InitialUsersProdConfiguration` 都没有 `noclaim` 条件，它们只按 `dev` 或 `!dev` 创建候选用户 Bean。真正决定是否自动写入数据库的是 `InitialUserController` 上的 `@Profile("!test & noclaim")`。

## 上下游关系

上游主要是 Spring Boot 的启动生命周期和 profile 配置。

`InitialUserController` 依赖 Spring 容器完成以下事情：

- 根据 profile 决定是否注册 `InitialUserController` Bean；
- 根据 `dev` 或 `!dev` 决定注册哪个 `initialUsers` Bean；
- 在 `ApplicationReadyEvent` 事件发布时调用 `createInitialUserOnStartupIfNoneExist()`。

从 profile 角度看，它的生效条件可以拆成两层：

- 控制器层：`!test & noclaim`
- 初始用户列表层：`dev` 或 `!dev`

组合后大致得到：

| profile 状态 | 控制器是否创建 | 初始用户来源 | 效果 |
| --- | --- | --- | --- |
| `test` | 否 | 不重要 | 不自动创建初始用户 |
| 没有 `noclaim` | 否 | 可能存在 | 不自动创建初始用户 |
| `noclaim + dev` | 是 | `InitialUsersDevConfiguration` | 首次启动创建 admin 和 user |
| `noclaim + !dev` | 是 | `InitialUsersProdConfiguration` | 首次启动创建随机密码 admin |

下游主要是 `KomgaUserLifecycle`。

`InitialUserController` 不直接访问数据库，而是调用：

```kotlin
userLifecycle.countUsers()
userLifecycle.createUser(it)
```

根据 `komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt`，`countUsers()` 实际委托给用户仓库：

```kotlin
fun countUsers() = userRepository.count()
```

`createUser()` 则负责：

1. 检查邮箱是否已存在：

```kotlin
if (userRepository.existsByEmailIgnoreCase(komgaUser.email)) throw UserEmailAlreadyExistsException(...)
```

2. 使用 `PasswordEncoder` 对明文密码编码：

```kotlin
userRepository.insert(komgaUser.copy(password = passwordEncoder.encode(komgaUser.password)))
```

3. 从仓库重新读取创建后的用户：

```kotlin
val createdUser = userRepository.findByIdOrNull(komgaUser.id)!!
```

所以，`InitialUserController` 里日志打印的是初始明文密码，但真正落库的密码会在 `KomgaUserLifecycle.createUser()` 中被编码。

模型层是 `KomgaUser` 和 `UserRoles`：

- `KomgaUser` 定义用户邮箱、密码、角色、共享库权限、内容限制、用户 ID、创建时间等字段。
- `UserRoles` 定义可授予用户的角色集合。
- `UserRoles.entries.toSet()` 是“授予所有当前枚举角色”的写法。

同目录中，例如 `AuthenticationActivityCleanupController.kt` 也位于 `interfaces/scheduler`，并且同样是 Spring 管理的后台控制器。它用 `@Scheduled` 做周期清理，而 `InitialUserController` 用 `@EventListener(ApplicationReadyEvent::class)` 做启动后一次性初始化。两者都体现了这个包的定位：放置由框架事件或调度机制驱动的接口层控制器。

## 运行/调用流程

一次典型的启动流程如下。

1. Spring Boot 启动，读取 active profiles。

如果当前 profile 包含 `noclaim`，且不包含 `test`，Spring 会注册：

```kotlin
InitialUserController
```

否则这个控制器不会进入容器，后续逻辑完全不会执行。

2. Spring 根据 `dev` profile 决定初始用户列表。

如果启用了 `dev`：

```kotlin
InitialUsersDevConfiguration.initialUsers()
```

会提供两个用户：

```kotlin
admin@example.org / admin
user@example.org / user
```

如果没有启用 `dev`：

```kotlin
InitialUsersProdConfiguration.initialUsers()
```

会提供一个管理员用户，密码是随机生成的 12 位字符串。

3. 应用启动完成后，Spring 发布 `ApplicationReadyEvent`。

`InitialUserController.createInitialUserOnStartupIfNoneExist()` 被触发。

4. 控制器检查用户总数。

```kotlin
userLifecycle.countUsers() == 0L
```

如果数据库中已有至少一个用户，方法直接结束，不创建任何用户。

这里的判断是“有没有任何用户”，不是“有没有 admin@example.org”。因此，只要系统里存在任意用户，初始用户逻辑就不会再运行。

5. 如果没有用户，则逐个创建初始用户。

控制器对 `initialUsers` 执行：

```kotlin
userLifecycle.createUser(it)
```

真正创建时，`KomgaUserLifecycle.createUser()` 会检查邮箱重复、编码密码、插入数据库，并重新读取用户。

6. 控制器记录日志。

每创建一个用户后，它会记录：

```kotlin
Initial user created. Login: ${it.email}, Password: ${it.password}
```

这里的 `it.password` 是创建前 `KomgaUser` 对象中的明文密码。对于生产配置，这正是随机生成的初始密码；对于开发配置，则是固定的 `admin` 或 `user`。

根据当前片段推断，这个日志是部署者获取首次登录密码的重要通道，尤其是在 `!dev` 环境下，因为随机密码没有其他返回路径出现在这个文件中。依据是生产配置只生成随机密码并放进 `KomgaUser`，随后控制器唯一显式输出该明文密码的位置就是日志。

## 小白阅读顺序

建议按下面顺序读，不要一上来纠结 Spring profile 表达式。

第一步，先看 `InitialUserController` 的构造函数：

```kotlin
private val userLifecycle: KomgaUserLifecycle,
private val initialUsers: List<KomgaUser>,
```

先理解它只做两件事：查用户数量、创建用户。它本身不负责密码加密、不负责 SQL、不负责权限判断。

第二步，看 `createInitialUserOnStartupIfNoneExist()`：

```kotlin
@EventListener(ApplicationReadyEvent::class)
fun createInitialUserOnStartupIfNoneExist()
```

重点理解这个方法不是被 HTTP 请求调用的，而是应用启动完成后由 Spring 事件系统自动调用的。

第三步，看这个判断：

```kotlin
if (userLifecycle.countUsers() == 0L)
```

这是防止重复创建初始用户的关键。它的含义是“系统完全没有用户时才初始化”，不是“缺少默认管理员时补一个”。

第四步，看两个配置类：

```kotlin
InitialUsersDevConfiguration
InitialUsersProdConfiguration
```

这里能看出开发环境和非开发环境的初始账号策略完全不同。开发环境为了方便，用固定密码；非开发环境为了安全，用随机密码。

第五步，跳到 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt` 看默认角色。

`KomgaUser` 默认 roles 是：

```kotlin
FILE_DOWNLOAD
PAGE_STREAMING
```

所以没有显式传 `roles = UserRoles.entries.toSet()` 的用户不是管理员。

第六步，跳到 `komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt` 看 `createUser()`。

这里能确认两个关键事实：

- 创建用户前会检查邮箱是否重复；
- 明文密码会通过 `PasswordEncoder` 编码后再保存。

第七步，再回头理解 `@Profile`：

```kotlin
@Profile("!test & noclaim")
@Profile("dev")
@Profile("!dev")
```

此时再看 profile，比较容易理解：一个决定控制器是否运行，另外两个决定初始用户列表长什么样。

## 常见误区

误区一：以为这个文件总会创建默认管理员。

不会。`InitialUserController` 只有在 `!test & noclaim` profile 条件满足时才存在。如果没有启用 `noclaim`，即使 `initialUsers` Bean 被配置出来，也不会被这个控制器使用。

误区二：以为每次启动都会重置管理员密码。

不会。核心判断是：

```kotlin
userLifecycle.countUsers() == 0L
```

只要数据库里已有任何用户，它就不会创建初始用户，也不会修改已有用户密码。

误区三：以为生产环境默认密码是固定的 `admin`。

不是。固定的 `admin@example.org / admin` 只在 `dev` profile 下出现。非 `dev` 环境中，密码来自：

```kotlin
RandomStringUtils.secure().nextAlphanumeric(12)
```

并且会通过日志输出。

误区四：以为日志里的密码就是数据库里保存的密码。

日志里打印的是创建时的明文初始密码，数据库中保存的是 `KomgaUserLifecycle.createUser()` 里经过 `PasswordEncoder` 编码后的密码。两者不是同一个字符串。

误区五：以为 `initialUsers` 是外部配置文件读取的。

从当前文件看，`initialUsers` 是 Spring `@Bean` 方法直接构造出来的 `List<KomgaUser>`，不是从 YAML、properties 或数据库读取。是否还有其他 profile 或测试替换 Bean，需要看更大范围配置；根据当前片段，主要来源就是本文件中的两个配置类。

误区六：以为 `UserRoles.entries.toSet()` 只表示管理员。

它表示授予 `UserRoles` 枚举中的所有角色。当前 `UserRoles` 包含：

```kotlin
ADMIN
FILE_DOWNLOAD
PAGE_STREAMING
KOBO_SYNC
KOREADER_SYNC
```

其中 `ADMIN` 只是其中之一。因为 `KomgaUser.isAdmin` 判断的是角色集合是否包含 `UserRoles.ADMIN`，所以拥有全部角色的用户自然也是管理员。

误区七：以为 `InitialUserController` 是 REST Controller。

它没有 `@RestController`、没有路由注解、没有请求映射。它是 `@Component`，通过 `@EventListener(ApplicationReadyEvent::class)` 被启动事件调用。包名里虽然有 `interfaces`，但这里的接口不是 HTTP API，而是应用与 Spring 调度/事件机制之间的适配层。
