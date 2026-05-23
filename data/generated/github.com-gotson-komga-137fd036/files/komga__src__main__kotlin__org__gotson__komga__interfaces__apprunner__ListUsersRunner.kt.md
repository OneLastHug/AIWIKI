# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner/ListUsersRunner.kt

## 它负责什么

`ListUsersRunner.kt` 定义了一个 Spring Boot 启动阶段运行器：`ListUsersRunner`。

它的职责非常单一：当应用启动参数中包含 `--list-users` 时，读取系统中所有 Komga 用户，并把这些用户的 `email` 列表输出到日志中。

它不是一个 REST API，也不是后台定时任务，而是一个“应用启动时的一次性辅助命令”。典型用途是管理员在服务启动时想确认当前数据库里有哪些用户，例如排查登录问题、忘记已有账号邮箱、迁移后检查用户数据是否存在等。

核心行为可以概括为：

1. Spring Boot 启动应用。
2. Spring 容器发现 `ListUsersRunner` 这个 `@Component`。
3. 如果当前 profile 不是 `test`，该 runner 会被注册。
4. Spring Boot 在启动流程中调用它的 `run(args)`。
5. 它检查启动参数里是否存在 `list-users`。
6. 如果存在，就从 `KomgaUserRepository` 查询全部用户。
7. 只提取每个用户的 `email`。
8. 如果有用户，日志输出邮箱列表；如果没有用户，日志输出 `No users exist yet`。

## 关键组成

这个文件的包名是：

```kotlin
package org.gotson.komga.interfaces.apprunner
```

从包名可以看出它属于 `interfaces` 层下的 `apprunner` 模块。这里的 `interfaces` 不一定只代表 HTTP 接口，也包括应用与外部运行环境交互的入口，例如命令行启动参数。

主要 import 有几类：

```kotlin
import io.github.oshai.kotlinlogging.KotlinLogging
```

用于创建 Kotlin 风格的 logger。文件顶部定义：

```kotlin
private val logger = KotlinLogging.logger {}
```

这是文件级私有日志对象，只能在当前 Kotlin 文件中访问。

```kotlin
import org.gotson.komga.domain.persistence.KomgaUserRepository
```

这是领域层的用户仓库接口。`ListUsersRunner` 不直接访问数据库表，也不依赖 JOOQ 实现，而是依赖抽象接口 `KomgaUserRepository`。这符合分层设计：接口层只知道“我要查询用户”，不关心数据具体怎么查。

```kotlin
import org.springframework.boot.ApplicationArguments
import org.springframework.boot.ApplicationRunner
```

这两个来自 Spring Boot。`ApplicationRunner` 是 Spring Boot 提供的启动回调接口，实现它的 Bean 会在应用启动完成后被调用。`ApplicationArguments` 是启动参数的包装对象，用来读取 `--xxx` 形式的参数。

```kotlin
import org.springframework.context.annotation.Profile
import org.springframework.stereotype.Component
```

`@Component` 让 Spring 自动扫描并注册这个类。`@Profile("!test")` 表示该 Bean 在 `test` profile 下不启用。

类定义如下：

```kotlin
@Profile("!test")
@Component
class ListUsersRunner(
  private val userRepository: KomgaUserRepository,
) : ApplicationRunner
```

这里有几个重点：

- `ListUsersRunner` 是 Spring Bean。
- 它通过构造函数注入 `KomgaUserRepository`。
- 它实现了 `ApplicationRunner`，所以启动后会被 Spring Boot 自动调用。
- `@Profile("!test")` 避免测试环境启动时执行该逻辑，减少测试干扰。

核心方法是：

```kotlin
override fun run(args: ApplicationArguments) {
  if (args.getOptionValues("list-users") != null) {
    val emails = userRepository.findAll().map { it.email }
    if (emails.isNotEmpty())
      logger.info { "Here is a list of all users: $emails" }
    else
      logger.info { "No users exist yet" }
  }
}
```

这里使用 `args.getOptionValues("list-users") != null` 判断参数是否出现。注意它不关心参数值，只关心是否有这个 option。也就是说，启动参数写成类似下面形式时就会触发：

```bash
--list-users
```

如果没有传 `--list-users`，整个 `run` 方法除了参数判断外不会做任何实际工作。

## 上下游关系

上游入口是 Spring Boot 应用启动流程。

仓库入口文件中可以看到 `komga/src/main/kotlin/org/gotson/komga/Application.kt` 使用了 `@SpringBootApplication` 和 `runApplication<Application>(*args)`。根据 Spring Boot 机制，应用启动时会扫描组件，并在合适阶段调用所有 `ApplicationRunner` Bean。因此 `ListUsersRunner` 没有普通意义上的“业务代码调用方”，它的调用者是 Spring Boot 框架。

它的直接上游数据来源是：

```kotlin
ApplicationArguments
```

也就是应用启动参数。`ListUsersRunner` 从中读取 `list-users` 这个 option。

它的直接下游依赖是：

```kotlin
KomgaUserRepository
```

该接口位于 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/KomgaUserRepository.kt`，其中定义了：

```kotlin
fun findAll(): Collection<KomgaUser>
```

实际实现根据当前片段可确认是：

```kotlin
komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt
```

`KomgaUserDao` 标注了 `@Component`，实现了 `KomgaUserRepository`，并通过 JOOQ 查询数据库。它的 `findAll()` 大致流程是：

```kotlin
override fun findAll(): Collection<KomgaUser> =
  dslRO
    .selectBase()
    .fetchAndMap(dslRO)
```

其中 `dslRO` 是只读数据库上下文，说明列出用户这个操作走的是读路径，不会修改数据。

`KomgaUser` 模型位于：

```kotlin
komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt
```

其中 `email` 是构造参数之一，并带有校验注解：

```kotlin
@Email(regexp = ".+@.+\\..+")
@NotBlank
val email: String
```

所以 `ListUsersRunner` 输出的邮箱来自领域模型 `KomgaUser.email`，而不是直接从数据库 record 或 DTO 中取值。

同目录下还有一个相邻文件：

```kotlin
komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner/PasswordResetRunner.kt
```

它也是 `@Profile("!test")`、`@Component`、`ApplicationRunner`。它通过启动参数 `--reset` 和 `--newpassword` 重置用户密码。两者可以放在一起理解：`interfaces.apprunner` 目录存放的是“通过启动参数触发的一次性维护功能”。

## 运行/调用流程

完整流程可以按下面理解：

1. 管理员启动 Komga，并传入命令行参数 `--list-users`。
2. `Application.kt` 中的 `runApplication<Application>(*args)` 启动 Spring Boot。
3. Spring 扫描到 `ListUsersRunner`。
4. 因为类上有 `@Profile("!test")`，只要当前不是 `test` profile，这个 Bean 就会生效。
5. Spring 使用构造函数注入 `KomgaUserRepository`。
6. 应用启动后，Spring Boot 调用 `ListUsersRunner.run(args)`。
7. `run` 方法调用：

```kotlin
args.getOptionValues("list-users")
```

8. 如果结果不是 `null`，说明启动参数里出现了 `--list-users`。
9. runner 调用：

```kotlin
userRepository.findAll()
```

10. 实际上进入 `KomgaUserDao.findAll()`，通过 JOOQ 从数据库读取用户数据，并映射成 `KomgaUser` 集合。
11. runner 执行：

```kotlin
.map { it.email }
```

只保留邮箱字段。
12. 如果邮箱列表不为空，日志输出：

```text
Here is a list of all users: [...]
```

13. 如果没有任何用户，日志输出：

```text
No users exist yet
```

这里要注意：`ListUsersRunner` 只是输出日志，不会把结果返回给命令行标准输出，也不会停止应用。根据当前片段推断，它更像一个启动时的辅助观察功能，而不是独立 CLI 子命令；依据是它实现的是 Spring Boot `ApplicationRunner`，并且没有调用退出流程或返回状态码的逻辑。

## 小白阅读顺序

建议按这个顺序读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner/ListUsersRunner.kt`

   重点看三个点：`@Component`、`ApplicationRunner`、`run(args)`。理解它为什么会在启动时自动执行。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner/PasswordResetRunner.kt`

   它和 `ListUsersRunner` 是同一种模式：启动参数触发维护动作。对比后会更容易理解 `interfaces.apprunner` 目录的定位。

3. 然后读 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/KomgaUserRepository.kt`

   看 `ListUsersRunner` 依赖的抽象接口。特别关注 `findAll()`，这是本文件唯一真正调用的业务依赖。

4. 接着读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt`

   这里能看到 `findAll()` 的实际数据库实现。它通过 `dslRO.selectBase().fetchAndMap(dslRO)` 查询用户，并把数据库 record 转成 `KomgaUser`。

5. 最后读 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt`

   这里能确认 `email` 字段属于领域模型，并且用户对象还包含密码、角色、共享库权限、内容限制、创建时间、更新时间等信息。`ListUsersRunner` 只取其中的 `email`，没有输出其他敏感字段。

如果只是想快速理解本文件，读完第 1、3、4 步就够了。如果想理解它在 Komga 架构里的位置，再补第 2、5 步。

## 常见误区

误区一：以为 `ListUsersRunner` 是一个 API 接口。

它不是 Controller，没有 HTTP 路由，也不会响应前端请求。它是 Spring Boot 启动阶段的 `ApplicationRunner`，只能通过应用启动参数触发。

误区二：以为它每次启动都会列出用户。

不会。虽然 `run(args)` 每次启动都会被 Spring Boot 调用，但真正查询用户之前有判断：

```kotlin
if (args.getOptionValues("list-users") != null)
```

只有传了 `--list-users` 才会查询并输出日志。

误区三：以为 `--list-users=false` 不会触发。

从代码看，它只判断 `getOptionValues("list-users") != null`，并不解析布尔值。因此只要 option 存在，就会触发。根据 Spring Boot 参数解析规则，类似 `--list-users=false` 这种形式通常也会让 `list-users` option 存在，所以仍可能触发。这里的判断语义是“参数是否出现”，不是“参数值是否为 true”。

误区四：以为它会输出完整用户信息。

不会。它执行的是：

```kotlin
userRepository.findAll().map { it.email }
```

虽然 `KomgaUserRepository.findAll()` 返回完整 `KomgaUser`，但本文件只取 `email`。密码、角色、权限、内容限制等不会在这里被输出。

误区五：以为它会修改数据库。

不会。它只调用 `findAll()` 并写日志。实际实现 `KomgaUserDao.findAll()` 使用只读 `dslRO` 查询路径，没有插入、更新、删除逻辑。

误区六：忽略 `@Profile("!test")`。

这个注解表示测试 profile 下不会启用该 runner。也就是说，在 `test` profile 里，即使存在对应启动参数，这个 Bean 也不会按正常应用 profile 那样注册执行。这样可以避免测试环境被启动参数类维护逻辑干扰。

误区七：以为日志输出等同于命令行返回结果。

代码使用的是：

```kotlin
logger.info { ... }
```

结果进入应用日志系统，而不是显式 `println`。在不同部署方式下，用户可能需要去控制台日志、容器日志或配置的日志文件中查看输出。
