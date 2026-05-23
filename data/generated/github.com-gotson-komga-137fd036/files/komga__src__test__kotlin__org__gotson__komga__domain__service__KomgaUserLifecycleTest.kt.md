# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycleTest.kt

## 它负责什么

`KomgaUserLifecycleTest.kt` 是 `KomgaUserLifecycle` 的集成测试文件，专门验证“用户 API key 生命周期”里两个容易出错的规则：

1. 当 `ApiKeyGenerator` 连续生成重复 key，导致无法得到唯一 API key 时，`KomgaUserLifecycle.createApiKey()` 最终应返回 `null`。
2. 同一个用户不能创建 comment 相同的 API key，而且 comment 的比较要忽略大小写，并且忽略前后空格。

它不是单纯的 mock 单元测试，而是使用 `@SpringBootTest` 启动 Spring 测试上下文，真实注入 `KomgaUserRepository` 和 `KomgaUserLifecycle`。也就是说，这个测试会经过 service、repository、DAO、数据库约束/查询逻辑等较完整链路，只把 `ApiKeyGenerator` 替换成 spy，用来稳定制造“重复 key”的场景。

## 关键组成

文件包名是：

`org.gotson.komga.domain.service`

这说明它测试的是领域服务层，目标实现位于：

`komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt`

主要 import 可以分成几类：

`com.ninjasquad.springmockk.SpykBean`  
用于在 Spring 容器中把真实 Bean 包成 spy。这里 spy 的对象是 `ApiKeyGenerator`，测试可以覆盖它的 `generate()` 返回值，同时保留 Spring 上下文里的依赖关系。

`io.mockk.every`  
MockK 的桩定义语法。测试中通过：

`every { apiKeyGenerator.generate() } returns uuid`

让所有 key 生成结果都固定为同一个字符串。

`org.assertj.core.api.Assertions.assertThat`、`catchThrowable`  
AssertJ 断言工具。`catchThrowable` 用于捕获异常后再判断异常类型。

`DuplicateNameException`、`KomgaUser`  
领域模型和领域异常。`DuplicateNameException` 表示同一命名空间内出现重复名称，这里对应“同一用户下 API key comment 重复”。

`KomgaUserRepository`  
领域仓储接口，测试用它直接插入用户、清理 API key、删除测试数据。

`ApiKeyGenerator`  
API key 生成器，真实实现位于：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/security/apikey/ApiKeyGenerator.kt`

其 `generate()` 使用 UUID v4，并去掉横线，生成类似 32 位字符串的随机 key。

测试类结构如下：

`@SpringBootTest`  
启动完整 Spring Boot 测试上下文。

`class KomgaUserLifecycleTest(...)`  
构造器注入两个依赖：

`userRepository: KomgaUserRepository`  
用于准备和清理测试数据。

`userLifecycle: KomgaUserLifecycle`  
被测试对象，核心方法是 `createApiKey(user, comment)`。

`@SpykBean private lateinit var apiKeyGenerator: ApiKeyGenerator`  
替换 Spring 容器中的 `ApiKeyGenerator` Bean，使 service 中注入的生成器也受测试控制。

`private val user1 = KomgaUser("user1@example.org", "")`  
`private val user2 = KomgaUser("user2@example.org", "")`

测试准备了两个用户。这里密码为空，因为本文件只关注 API key，不测试登录或密码编码。

生命周期方法：

`@BeforeAll fun setup()`  
向仓库插入 `user1` 和 `user2`。

`@AfterEach fun cleanup()`  
每个测试后删除两个用户的 API key，避免 API key 数据影响下一个测试。

`@AfterAll fun teardown()`  
所有测试结束后 `userRepository.deleteAll()` 清空用户相关数据。

需要注意，这个文件里的 `@BeforeAll`、`@AfterAll` 是实例方法形式。根据当前片段推断，项目测试配置可能启用了 JUnit 5 的 per-class 测试实例生命周期，或者有配套测试配置支持这种写法；不要脱离项目配置后直接假设所有 JUnit 项目都能这样写。

## 上下游关系

上游调用关系主要来自 REST API：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt`

其中 `POST me/api-keys` 对应方法 `createApiKeyForCurrentUser(...)`，会调用：

`userLifecycle.createApiKey(principal.user, apiKeyRequest.comment)`

如果返回 `ApiKey`，接口返回 DTO；如果抛出 `DuplicateNameException`，接口转换成 `400 BAD_REQUEST`；如果返回 `null`，接口转换成 `503 SERVICE_UNAVAILABLE`，原因是服务端无法生成唯一 API key。

被测核心实现位于：

`komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt`

`createApiKey(user, comment)` 的关键逻辑是：

1. `comment.trim()` 去掉前后空白。
2. 调用 `userRepository.existsApiKeyByCommentAndUserId(commentTrimmed, user.id)` 判断同一用户下 comment 是否重复。
3. 如果重复，抛出 `DuplicateNameException("api key comment already exists for this user", "ERR_1034")`。
4. 最多尝试 10 次生成 API key。
5. 每次创建一个 `ApiKey(userId, key, comment)`。
6. 存库前把 key 用 `tokenEncoder.encode(...)` 编码。
7. 存库成功则返回原始明文 `ApiKey`。
8. 如果插入失败或其他异常，会记录 debug 日志并进入下一次尝试。
9. 10 次都失败后返回 `null`。

仓储接口位于：

`komga/src/main/kotlin/org/gotson/komga/domain/persistence/KomgaUserRepository.kt`

和本测试直接相关的方法包括：

`insert(user: KomgaUser)`  
插入测试用户。

`insert(apiKey: ApiKey)`  
由 `KomgaUserLifecycle.createApiKey()` 调用，用于保存 API key。

`existsApiKeyByCommentAndUserId(comment, userId)`  
检查同一用户下 comment 是否重复。

`deleteApiKeyByUserId(userId)`  
测试清理 API key。

`deleteAll()`  
测试结束后清理用户数据。

具体实现位于：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt`

从当前片段可以确认：

`existsApiKeyByCommentAndUserId` 使用 `uak.COMMENT.equalIgnoreCase(comment)`，所以 comment 查重忽略大小写。结合 service 层先 `trim()`，测试里的 `"test"`、`"TEST"`、`" test "` 都应该被视作重复。

根据当前片段推断，重复 key 的失败来自 DAO 插入 API key 时触发数据库唯一约束或等价的持久化异常；`createApiKey()` 捕获异常后重试，最终返回 `null`。依据是测试固定 `ApiKeyGenerator.generate()` 返回同一个值，第一次创建成功，后续创建同样 key 时预期为 `null`，而 service 实现只是在 `userRepository.insert(...)` 外层捕获异常。

## 运行/调用流程

第一个测试：

`given existing api key when api key cannot be uniquely generated then it returns null`

流程如下：

1. 创建一个真实 `ApiKeyGenerator()`，调用 `generate()` 得到一个 UUID 风格字符串 `uuid`。
2. 用 `every { apiKeyGenerator.generate() } returns uuid` 固定 Spring 容器中 spy 生成器的返回值。
3. 调用 `userLifecycle.createApiKey(user1, "test key")`。
4. 第一次创建时数据库里还没有这个 key，所以插入成功。
5. 再次调用 `userLifecycle.createApiKey(user1, "test key 2")`。
6. 因为生成器仍然返回同一个 `uuid`，每次尝试都会生成重复 key。
7. `createApiKey()` 最多重试 10 次，全部失败后返回 `null`。
8. 再对 `user2` 调用 `createApiKey(user2, "test key 3")`。
9. 即使换了用户，只要底层 API key 本身要求全局唯一，重复 key 仍无法插入，所以同样返回 `null`。
10. 测试断言 `apiKey` 和 `apiKey2` 都是 `null`。

这个测试验证的是“API key 字符串唯一性”不是“用户内唯一性”。如果 key 已存在，换用户也不能复用同一个 key。

第二个测试：

`given existing api key comment when api key with same comment is generated then it throws exception`

这是一个参数化测试：

`@ValueSource(strings = ["test", "TEST", " test "])`

流程如下：

1. 先为 `user1` 创建 comment 为 `"test"` 的 API key。
2. 再分别尝试用 `"test"`、`"TEST"`、`" test "` 创建新的 API key。
3. service 先对 comment 执行 `trim()`，所以 `" test "` 变成 `"test"`。
4. repository 的 comment 查询使用忽略大小写比较，所以 `"TEST"` 也等同于 `"test"`。
5. 因此三种输入都应该触发 `DuplicateNameException`。
6. 测试用 `catchThrowable` 捕获异常，再断言异常精确类型是 `DuplicateNameException`。

这里断言使用的是：

`isExactlyInstanceOf(DuplicateNameException::class.java)`

不是 `isInstanceOf`。这意味着测试要求抛出的异常必须正好是 `DuplicateNameException`，不能是它的子类。

## 小白阅读顺序

建议按下面顺序读：

1. 先读本测试文件顶部的两个字段：`user1`、`user2`。先理解测试只准备两个用户，不关心密码、权限、登录流程。
2. 再读 `setup()`、`cleanup()`、`teardown()`。确认测试数据的生命周期：测试前插用户，每个测试后删 API key，所有测试后删用户。
3. 接着读第一个测试，重点看 `@SpykBean apiKeyGenerator` 和 `every { ... } returns uuid`。这一步是在制造“永远生成同一个 key”的极端场景。
4. 然后打开 `KomgaUserLifecycle.createApiKey()`。把测试里的调用和实现里的 `for (attempt in 1..10)` 对上，就能理解为什么最后返回 `null`。
5. 再读第二个参数化测试。重点看三组输入 `"test"`、`"TEST"`、`" test "` 为什么都应该失败。
6. 最后看 `KomgaUserDao.existsApiKeyByCommentAndUserId(...)`。它使用 `equalIgnoreCase`，和 service 的 `trim()` 一起构成 comment 去重规则。
7. 如果继续追上游，再看 `UserController.createApiKeyForCurrentUser(...)`，理解 service 的返回值和异常如何变成 HTTP 响应。

## 常见误区

一个常见误区是把这个文件当成纯单元测试。它用了 `@SpringBootTest`，实际跑的是 Spring 上下文和真实 repository，只是 spy 了 `ApiKeyGenerator`。因此它覆盖的是更接近真实运行时的行为。

另一个误区是认为 API key 只需要在同一用户下唯一。第一个测试特意对 `user1` 和 `user2` 都尝试复用同一个生成结果，并断言都返回 `null`，说明 API key 字符串应当全局不可重复。根据当前片段推断，这个规则由持久化层唯一约束或插入异常体现。

还容易误解的是 comment 去重规则。`" test "` 不是一个不同 comment，因为 service 会先 `trim()`；`"TEST"` 也不是不同 comment，因为 DAO 查询使用忽略大小写比较。所以对用户而言，`test`、`TEST`、前后带空格的 `test` 都是同一个 API key comment。

不要忽略 `cleanup()`。如果每个测试后不删除 API key，第一个测试制造的重复 key 或第二个测试创建的 `"test"` comment 会污染后续测试，让测试结果依赖执行顺序。

也不要误以为 `createApiKey()` 返回的是存入数据库的同一个 key 对象。实现中存库时会保存 `plainTextKey.copy(key = tokenEncoder.encode(plainTextKey.key))`，但返回给调用方的是明文 `plainTextKey`。这符合 API key 常见设计：创建时只展示一次明文，数据库保存编码后的值。

最后，`catch (e: Exception)` 在 `createApiKey()` 中捕获范围很宽。这个测试关心的是“重复 key 导致插入失败后重试并最终返回 null”的结果，但如果未来持久化层抛出非唯一性相关异常，也可能被同一逻辑吞掉并表现为生成失败。阅读或修改这里时要意识到这是一个设计取舍。
