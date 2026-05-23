# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/AuthenticationActivityCleanupController.kt

## 它负责什么

`AuthenticationActivityCleanupController.kt` 是 Komga 中负责“定期清理登录/认证活动记录”的 Spring 组件。

它的职责很单一：每天运行一次，把数据库中早于当前 UTC 时间一个月的 `authentication_activity` 记录删除掉。这里的认证活动包括用户登录成功、登录失败、API Key 登录、OAuth2 登录、RememberMe 登录等记录，这些记录由安全层的 `LoginListener` 写入，之后可以通过用户相关 REST API 查询。

从分层看，这个文件位于：

`komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/AuthenticationActivityCleanupController.kt`

它属于 `interfaces.scheduler` 包。这个包里的类通常不是业务实体本身，而是“接口层的调度入口”：通过 Spring 的 `@Scheduled`、`@EventListener` 等机制，在合适时机触发应用任务或维护任务。例如同目录下的 `PeriodicScannerController.kt` 会在应用启动时安排资料库扫描，`MetricsPublisherController.kt` 会发布指标，而本文件专门处理认证活动历史记录的生命周期。

## 关键组成

这个文件的完整结构很短，核心元素如下：

```kotlin
package org.gotson.komga.interfaces.scheduler
```

包名说明它是一个调度控制器，不是领域服务，也不是底层 DAO。这里的 `Controller` 不是传统 REST Controller，而是“调度入口控制器”。

```kotlin
import io.github.oshai.kotlinlogging.KotlinLogging
import org.gotson.komga.domain.persistence.AuthenticationActivityRepository
import org.springframework.context.annotation.Profile
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Component
import java.time.LocalDateTime
import java.time.ZoneId
```

这些 import 分别承担不同职责：

`KotlinLogging` 用来创建日志对象。

`AuthenticationActivityRepository` 是领域层定义的认证活动仓储接口，提供查询、插入、删除认证活动的方法。

`@Profile` 用来控制 Spring Bean 只在特定 profile 下启用。

`@Scheduled` 用来声明定时任务。

`@Component` 让 Spring 能扫描并注册这个类。

`LocalDateTime` 和 `ZoneId` 用来计算“一个月前的 UTC 时间”。

```kotlin
private val logger = KotlinLogging.logger {}
```

这是文件级 logger。`private` 表示只在当前 Kotlin 文件内可见。该组件运行清理任务前会打一条 info 日志，方便运维或调试时知道清理阈值。

```kotlin
@Profile("!test")
@Component
class AuthenticationActivityCleanupController(
  private val authenticationActivityRepository: AuthenticationActivityRepository,
)
```

这里有两个关键注解：

`@Component`：把 `AuthenticationActivityCleanupController` 注册为 Spring Bean。只有成为 Bean，Spring 才会处理它里面的 `@Scheduled` 方法。

`@Profile("!test")`：表示在非 `test` profile 下启用。也就是说测试环境不会注册这个定时清理组件。这样做可以避免自动定时任务影响测试结果，比如测试刚插入的认证活动被后台清理掉，或者测试运行过程中出现不可控的时间触发行为。

构造函数注入了：

`authenticationActivityRepository: AuthenticationActivityRepository`

这个 repository 是接口，具体实现位于：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/AuthenticationActivityDao.kt`

也就是说，本文件不直接写 SQL，也不关心数据库访问细节。它只负责决定“什么时候清理”和“清理到哪个时间点”。

```kotlin
@Scheduled(fixedRate = 86_400_000)
fun cleanup() {
  val olderThan = LocalDateTime.now(ZoneId.of("Z")).minusMonths(1)
  logger.info { "Remove authentication activity older than $olderThan (UTC)" }
  authenticationActivityRepository.deleteOlderThan(olderThan)
}
```

这是核心逻辑。

`@Scheduled(fixedRate = 86_400_000)` 表示固定频率执行，单位是毫秒。`86_400_000` 毫秒等于 24 小时，所以注释 `// Run every day` 是准确的。

`fixedRate` 的含义是“以上一次任务开始时间为基准，固定间隔再次触发”。这和 `fixedDelay` 不同，`fixedDelay` 是以上一次任务结束时间为基准。对于这个清理任务来说，删除旧记录通常很快，使用 `fixedRate` 足够。

`LocalDateTime.now(ZoneId.of("Z")).minusMonths(1)` 会取当前 UTC 时间，然后减去一个月。`ZoneId.of("Z")` 表示 UTC，也就是零时区。

变量名 `olderThan` 的语义是“早于这个时间点的记录”。随后调用：

`authenticationActivityRepository.deleteOlderThan(olderThan)`

把这个阈值交给仓储层删除。

## 上下游关系

上游主要是认证事件记录写入方。

认证活动记录由 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/LoginListener.kt` 创建。这个类监听 Spring Security 的认证事件：

`AuthenticationSuccessEvent`

`AbstractAuthenticationFailureEvent`

当用户认证成功时，`LoginListener.onSuccess` 会构造 `AuthenticationActivity`，记录用户 ID、邮箱、API Key 信息、IP、User-Agent、是否成功、来源等信息，然后调用：

`authenticationActivityRepository.insert(activity)`

当用户认证失败时，`LoginListener.onFailure` 也会构造 `AuthenticationActivity`，记录失败的 principal、IP、User-Agent、错误信息、来源等，再插入仓储。

所以，本文件清理的不是普通用户资料，也不是阅读历史，而是由安全登录流程不断写入的认证审计记录。

中游是领域仓储接口：

`komga/src/main/kotlin/org/gotson/komga/domain/persistence/AuthenticationActivityRepository.kt`

它定义了这些方法：

```kotlin
fun findAll(pageable: Pageable): Page<AuthenticationActivity>
fun findAllByUser(user: KomgaUser, pageable: Pageable): Page<AuthenticationActivity>
fun findMostRecentByUser(user: KomgaUser, apiKeyId: String?): AuthenticationActivity?
fun insert(activity: AuthenticationActivity)
fun deleteByUser(user: KomgaUser)
fun deleteOlderThan(dateTime: LocalDateTime)
```

本文件只使用其中的 `deleteOlderThan(dateTime: LocalDateTime)`。

下游实际执行删除的是：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/AuthenticationActivityDao.kt`

其中实现为：

```kotlin
override fun deleteOlderThan(dateTime: LocalDateTime) {
  dslRW
    .deleteFrom(aa)
    .where(aa.DATE_TIME.lt(dateTime))
    .execute()
}
```

这里的 `aa` 是 `Tables.AUTHENTICATION_ACTIVITY`，所以最终删除条件是：

`AUTHENTICATION_ACTIVITY.DATE_TIME < olderThan`

也就是说，只删除数据库字段 `DATE_TIME` 早于阈值的认证活动记录。

认证活动的读取方主要在：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt`

相关 REST 接口包括：

`GET me/authentication-activity`：当前用户查看自己的认证活动。

`GET authentication-activity`：管理员查看全部认证活动。

`GET {id}/authentication-activity/latest`：查看某个用户最近一次认证活动，可按 `apikey_id` 过滤。

因此，本清理任务会影响这些接口能查到的历史范围。一个月以前的认证活动会被删除，之后前端或 API 就查不到这些旧记录了。

根据当前片段推断，认证活动的保留周期是固定写死在代码里的一个月，没有看到从配置文件读取保留周期的逻辑。依据是 `cleanup()` 中直接调用 `minusMonths(1)`，且目标文件没有注入配置属性。

## 运行/调用流程

完整流程可以按时间线理解：

1. 应用启动时，Spring 扫描 `@Component`

如果当前 profile 不是 `test`，Spring 会创建 `AuthenticationActivityCleanupController` Bean。

如果当前 profile 是 `test`，由于 `@Profile("!test")`，这个 Bean 不会注册，定时清理也不会运行。

2. Spring Scheduling 识别 `@Scheduled`

`cleanup()` 方法上有：

```kotlin
@Scheduled(fixedRate = 86_400_000)
```

Spring 的定时任务机制会把它注册为一个周期任务。前提是项目中已经启用了 Spring Scheduling，通常通过 `@EnableScheduling` 或 Spring Boot 配置完成。目标文件本身不负责启用 scheduling，只声明任务。

3. 到达触发时间后执行 `cleanup()`

每次执行时，代码先计算 UTC 时间：

```kotlin
val olderThan = LocalDateTime.now(ZoneId.of("Z")).minusMonths(1)
```

如果当前 UTC 时间是 2026-05-22 10:00，那么 `olderThan` 大致就是 2026-04-22 10:00。早于这个时间的认证活动会被视为过期。

4. 写入日志

```kotlin
logger.info { "Remove authentication activity older than $olderThan (UTC)" }
```

日志中明确标注 `(UTC)`，这是因为 `olderThan` 使用 UTC 计算。这样可以减少排查时区问题的困惑。

5. 调用 repository 删除

```kotlin
authenticationActivityRepository.deleteOlderThan(olderThan)
```

控制器不自己处理 SQL，而是交给领域仓储接口。

6. jOOQ DAO 执行数据库删除

`AuthenticationActivityDao.deleteOlderThan` 使用写库 DSLContext `dslRW` 执行：

```kotlin
deleteFrom(authentication_activity)
where(date_time < olderThan)
execute()
```

删除完成后，旧认证活动从数据库中消失。之后 `UserController` 的认证活动查询接口只能查到未被清理的数据。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就陷入 Spring 注解细节：

1. 先看目标文件的 `cleanup()`

重点理解三件事：

`@Scheduled(fixedRate = 86_400_000)` 表示每天执行。

`olderThan = now(UTC).minusMonths(1)` 表示保留最近一个月。

`deleteOlderThan(olderThan)` 表示把删除动作交给仓储。

2. 再看 `AuthenticationActivityRepository.kt`

这个接口能帮助你理解认证活动数据有哪些操作能力。目标文件只依赖接口，不依赖具体数据库实现，这是典型的分层设计：调度层只调用抽象，不直接碰 SQL。

3. 再看 `AuthenticationActivityDao.kt`

重点看 `deleteOlderThan` 的实现。它会告诉你“olderThan”到底怎样作用到数据库上：通过 `DATE_TIME.lt(dateTime)` 删除更早的数据。

顺便可以看 `insert` 方法，理解这些记录和数据库表字段的关系，比如 `USER_ID`、`EMAIL`、`API_KEY_ID`、`IP`、`USER_AGENT`、`SUCCESS`、`ERROR`、`SOURCE`。

4. 再看 `LoginListener.kt`

这个文件解释认证活动从哪里来。登录成功和失败事件都会被监听，然后插入 `AuthenticationActivity`。理解它之后，你会知道清理任务不是孤立存在的，它是在给不断增长的认证审计记录做定期瘦身。

5. 最后看 `UserController.kt` 的认证活动接口

重点看：

`getAuthenticationActivityForCurrentUser`

`getAuthenticationActivity`

`getLatestAuthenticationActivityByUserId`

这几个接口说明认证活动记录会被用户或管理员查询。清理任务会直接影响这些接口返回的历史数据范围。

## 常见误区

误区一：以为 `AuthenticationActivityCleanupController` 是 REST Controller。

虽然类名里有 `Controller`，但它没有 `@RestController`，也没有 `@GetMapping`、`@PostMapping`。它是一个 Spring `@Component`，靠 `@Scheduled` 被后台定时调用，不对外提供 HTTP 接口。

误区二：以为它清理的是用户账号或登录状态。

它只清理认证活动记录，也就是审计/历史日志类数据。它不会删除 `KomgaUser`，不会删除 API Key，也不会强制用户下线。真正删除的是 `AUTHENTICATION_ACTIVITY` 表中较旧的记录。

误区三：忽略 `@Profile("!test")`。

测试环境下这个 Bean 不会启用。如果你在测试中发现 `cleanup()` 没有自动执行，这是符合代码设计的。要测试清理逻辑，应直接测试 repository/DAO，或者在非 `test` profile 下验证调度行为。

误区四：把 `fixedRate = 86_400_000` 理解成“每天凌晨执行”。

`fixedRate` 只表示每隔 24 小时执行一次，不代表固定在每天 00:00。首次执行时间和 Spring 定时任务注册后的调度行为有关。代码没有配置 cron 表达式，所以不能假设它在某个具体时钟时间运行。

误区五：忽略 UTC。

代码使用：

```kotlin
LocalDateTime.now(ZoneId.of("Z"))
```

并且日志写了 `(UTC)`。这说明清理阈值按 UTC 计算。认证活动 DAO 在读取时会调用 `toCurrentTimeZone()` 转换展示时区，但删除条件直接和数据库中的 `DATE_TIME` 比较。阅读这段逻辑时，要区分“存储/删除比较的时间”和“展示给用户的时间”。

误区六：以为保留周期可配置。

根据当前片段推断，保留周期固定为一个月。目标文件没有读取配置属性，也没有注入类似 `KomgaProperties` 的配置对象，而是直接写死：

```kotlin
.minusMonths(1)
```

如果未来要改成可配置，需要新增配置项并注入到这个组件，而不是只改数据库层。

误区七：以为删除会按用户分组。

`cleanup()` 调用的是 `deleteOlderThan(olderThan)`，没有传入用户 ID。DAO 的删除条件也只有 `DATE_TIME < dateTime`。所以它是全局清理：所有用户、所有来源、成功和失败记录，只要早于阈值都会被删除。
