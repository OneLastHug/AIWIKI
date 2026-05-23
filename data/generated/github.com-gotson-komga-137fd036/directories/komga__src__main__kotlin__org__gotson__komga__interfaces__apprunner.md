# 目录：komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner` 是 Komga 启动期命令行辅助功能的入口目录。它不处理 HTTP 请求，也不是后台定时任务，而是通过 Spring Boot 的 `ApplicationRunner` 在应用启动后读取命令行参数，执行一次性管理动作。

当前目录只有两个文件：

`komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner/ListUsersRunner.kt`  
`komga/src/main/kotlin/org/gotson/komga/interfaces/apprunner/PasswordResetRunner.kt`

它们面向的典型场景是：管理员无法通过 Web UI 登录，或者需要在容器/命令行环境中快速检查已有用户、重置用户密码。也就是说，这个目录提供的是“随应用启动触发的运维入口”。

两个 runner 都标了：

```kotlin
@Profile("!test")
@Component
```

含义是：在非 `test` profile 下注册为 Spring Bean；测试环境中不会启用，避免测试启动时因为命令行参数或真实数据访问产生副作用。

## 关键组成

`ListUsersRunner` 的职责很窄：如果启动参数里存在 `--list-users`，就从用户仓储读取所有用户，提取 email，并写入日志。

核心逻辑在 `ListUsersRunner.run(args: ApplicationArguments)`：

```kotlin
if (args.getOptionValues("list-users") != null) {
  val emails = userRepository.findAll().map { it.email }
  if (emails.isNotEmpty())
    logger.info { "Here is a list of all users: $emails" }
  else
    logger.info { "No users exist yet" }
}
```

这里依赖 `KomgaUserRepository.findAll()`。接口定义在 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/KomgaUserRepository.kt`，JOOQ 实现在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt`。`KomgaUserDao.findAll()` 使用只读 DSL 上下文 `dslRO` 查询用户表及用户共享库信息，然后映射成领域对象 `KomgaUser`。

`PasswordResetRunner` 的职责是根据命令行参数重置一个或多个用户的密码。它识别两个参数名：

```kotlin
private val resetFor = "reset"
private val resetTo = "newpassword"
```

也就是启动时传入：

```text
--reset=user@domain.com --newpassword=YourNewPassword
```

如果只传了其中一个参数，会记录 warning：

```kotlin
"You need to specify both '--reset=user@domain.com' and '--newpassword=YourNewPassword'"
```

如果新密码为空白字符串，也会拒绝执行：

```kotlin
"The new password must not be blank"
```

真正执行重置时，它先通过 `KomgaUserRepository.findByEmailIgnoreCaseOrNull(arg)` 按 email 忽略大小写查用户；查到后调用：

```kotlin
userLifecycle.updatePassword(user, newPassword, true)
```

这里没有在 runner 内部直接写数据库密码字段，而是委托给 `KomgaUserLifecycle`。这是一个重要设计点：密码更新属于用户生命周期行为，应该经过统一的领域服务。

`KomgaUserLifecycle.updatePassword()` 位于 `komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt`，关键动作包括：

1. 使用 `PasswordEncoder.encode(newPassword)` 对明文密码编码。
2. 调用 `userRepository.update(updatedUser)` 持久化。
3. 如果 `expireSessions` 为 `true`，调用 `expireSessions(updatedUser)` 让该用户现有会话失效。
4. 发布 `DomainEvent.UserUpdated(updatedUser, expireSessions)`。

因此，`PasswordResetRunner` 虽然是命令行入口，但不会绕过安全与领域事件机制。

## 上下游关系

上游是 Spring Boot 应用启动流程。应用启动后，Spring 会发现 `@Component` 标注的 `ApplicationRunner` Bean，并把启动参数封装为 `ApplicationArguments` 传给 `run()` 方法。

本目录的直接上游可以理解为：

`Spring Boot startup` -> `ApplicationArguments` -> `ListUsersRunner.run()` / `PasswordResetRunner.run()`

下游主要是用户领域与持久化层：

`ListUsersRunner` 下游：

`ListUsersRunner` -> `KomgaUserRepository.findAll()` -> `KomgaUserDao.findAll()` -> 数据库用户表及相关用户共享表 -> 日志输出

`PasswordResetRunner` 下游：

`PasswordResetRunner` -> `KomgaUserRepository.findByEmailIgnoreCaseOrNull()` -> `KomgaUserLifecycle.updatePassword()` -> `PasswordEncoder` -> `KomgaUserRepository.update()` -> `SessionRegistry.expireNow()` -> `ApplicationEventPublisher.publishEvent()`

从分层角度看，`interfaces/apprunner` 属于接口层。它把“外部输入”从命令行参数转换成领域操作。它不负责密码加密细节、不负责 SQL、不负责会话机制，也不直接发布事件；这些都交给 domain service、security、persistence 等下游组件。

它和 `interfaces/api/rest/UserController.kt` 有相似业务下游：REST API 里也有用户密码更新入口，例如 `updatePasswordForCurrentUser`、`updatePasswordByUserId`。区别是 REST Controller 面向已登录用户或管理员请求，而 `PasswordResetRunner` 面向启动时的命令行运维场景。

## 运行/调用流程

应用以普通方式启动时，如果没有传入相关参数，这两个 runner 基本不会产生业务动作。

`ListUsersRunner` 流程：

1. Spring 创建 `ListUsersRunner`，注入 `KomgaUserRepository`。
2. 应用启动完成后调用 `run(args)`。
3. 检查 `args.getOptionValues("list-users")` 是否不为 `null`。
4. 如果没有 `--list-users`，直接结束。
5. 如果有 `--list-users`，调用 `userRepository.findAll()`。
6. 将返回的 `KomgaUser` 集合映射为 email 列表。
7. 如果列表不为空，日志输出所有用户 email；否则日志输出还没有用户。

这里判断的是参数是否存在，而不是参数值是否有内容。也就是说，根据 Spring Boot `ApplicationArguments` 的常见行为，`--list-users` 这种无值 option 也能触发；代码只关心 `getOptionValues(...) != null`。

`PasswordResetRunner` 流程：

1. Spring 创建 `PasswordResetRunner`，注入 `KomgaUserRepository` 和 `KomgaUserLifecycle`。
2. 应用启动后调用 `run(args)`。
3. 从 `--newpassword` 读取第一个值：

   ```kotlin
   val newPassword = args.getOptionValues(resetTo)?.firstOrNull()
   ```

4. 从 `--reset` 读取目标用户 email 集合：

   ```kotlin
   val resetFor = args.getOptionValues(resetFor)?.toSet() ?: emptySet()
   ```

   这里局部变量名和类属性名同为 `resetFor`。根据当前片段推断，右侧 `args.getOptionValues(resetFor)` 解析到的是类属性 `"reset"`，因为局部变量尚未完成初始化；但这种写法可读性一般，阅读时容易误会。

5. 如果 `--reset` 和 `--newpassword` 只提供了一个，记录 warning 并返回。

   条件使用了 `xor`：

   ```kotlin
   if (resetFor.isEmpty() xor (newPassword == null))
   ```

   意思是“两个条件恰好一个为真”时才报缺参。

6. 如果二者都没提供，直接返回，表示不执行密码重置。

7. 如果新密码是空白字符串，记录 warning 并返回。

8. 对每个 `--reset` 指定的 email：
   先调用 `findByEmailIgnoreCaseOrNull(arg)` 查用户。
   如果用户存在，日志记录 `Reset password for user: ...`，然后调用 `userLifecycle.updatePassword(user, newPassword, true)`。
   如果用户不存在，日志记录 `User does not exist: ...`。

根据当前代码，`--reset` 可以出现多次或带多个值，最终会转成 `Set`，所以可以一次启动重置多个用户，重复 email 会被去重。具体命令行格式取决于 Spring Boot 对参数的解析方式，但代码层面支持 `getOptionValues("reset")` 返回多个值。

## 小白阅读顺序

建议先读 `ListUsersRunner.kt`，因为它只有一个参数、一个仓储调用、一个日志输出。读完它可以理解本目录的基本模式：实现 `ApplicationRunner`，在 `run()` 中检查 `ApplicationArguments`，有匹配参数才执行动作。

第二步读 `PasswordResetRunner.kt`。重点看三个判断：

```kotlin
if (resetFor.isEmpty() xor (newPassword == null))
```

```kotlin
if (resetFor.isEmpty()) return
```

```kotlin
if (newPassword.isNullOrBlank())
```

这三段分别处理：只传一半参数、完全没传参数、新密码为空白。

第三步读 `KomgaUserRepository.kt`。这能帮助你知道 runner 依赖的是领域仓储接口，而不是具体数据库实现。接口中和本目录最相关的方法是：

```kotlin
fun findAll(): Collection<KomgaUser>
fun findByEmailIgnoreCaseOrNull(email: String): KomgaUser?
fun update(user: KomgaUser)
```

第四步读 `KomgaUserDao.kt` 中的 `findAll()`、`findByEmailIgnoreCaseOrNull()` 和 `update()`。这一步主要是确认仓储接口最终如何落到数据库。`findAll()` 会读取用户基础字段、角色、共享库和内容限制等信息；runner 只用 email，但查询返回的是完整 `KomgaUser` 领域对象。

第五步读 `KomgaUserLifecycle.kt` 的 `updatePassword()` 和 `expireSessions()`。这是理解密码重置副作用的关键：密码不是简单替换字符串，而是经过编码、持久化、会话失效和领域事件发布。

如果继续扩展阅读，可以再看 `interfaces/api/rest/UserController.kt` 中和密码更新相关的接口。它能帮助你对比“HTTP 管理入口”和“启动参数管理入口”的差异。

## 常见误区

第一个误区：以为 `apprunner` 是普通业务服务。实际上它是接口层的启动期入口，生命周期由 Spring Boot 控制。它不会被 Controller 调用，也不会在用户点击页面按钮时运行；只有应用启动时才会执行 `run()`。

第二个误区：以为 `--reset` 是重置开关，`--newpassword` 是可选项。代码要求二者必须同时存在。只传 `--reset=user@domain.com` 不会重置密码，只会输出 warning；只传 `--newpassword=xxx` 也一样。

第三个误区：以为密码会被 runner 直接写入数据库。实际调用链是 `PasswordResetRunner` -> `KomgaUserLifecycle.updatePassword()` -> `PasswordEncoder.encode()` -> `KomgaUserRepository.update()`。这保证了密码会被编码，并且会触发会话失效和用户更新事件。

第四个误区：忽略 `expireSessions = true`。命令行重置密码后，该用户已有 session 会被 `SessionRegistry` 标记失效。这是安全行为，意味着用户需要用新密码重新登录。

第五个误区：以为 `ListUsersRunner` 会把用户返回到控制台标准输出。它使用的是 `KotlinLogging`，输出位置取决于应用日志配置。在容器环境中通常能从容器日志看到；在本地运行时则看 Spring Boot 日志输出。

第六个误区：把该目录当作测试工具。两个类都有 `@Profile("!test")`，测试 profile 下不会注册。若测试中需要类似能力，通常应该直接调用仓储或服务，而不是依赖这些 runner。

第七个误区：忽略参数名的精确写法。列用户参数是 `--list-users`，重置密码参数是 `--reset` 和 `--newpassword`。代码没有识别 `--reset-password`、`--email`、`--password` 之类别名。

第八个误区：误读 `PasswordResetRunner` 里的 `resetFor`。类里有属性 `private val resetFor = "reset"`，`run()` 里又有局部变量 `val resetFor = ...`。局部变量初始化右侧使用的是参数名 `"reset"`，初始化完成后局部变量表示待重置用户集合。阅读时要区分“参数名 reset”和“解析出来的用户集合”。
