# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt

## 它负责什么

`KomgaUserLifecycle` 是 Komga 用户领域里的“生命周期服务”，负责把用户相关的核心变更串起来：创建用户、更新用户资料、修改密码、删除用户、失效会话、创建 API key。

它不是一个 HTTP Controller，也不是数据库 DAO。它位于 `org.gotson.komga.domain.service` 包下，标注了 Spring 的 `@Service`，说明它是领域服务层组件：上层接口把请求转成领域对象后调用它，它再协调 repository、安全组件、事务、事件发布和会话管理。

这个文件的核心职责可以概括为：

- 用户写入：通过 `KomgaUserRepository` 新增、更新、删除 `KomgaUser`。
- 密码安全：用 `PasswordEncoder` 对明文密码做编码后再保存。
- API key 安全：用 `ApiKeyGenerator` 生成明文 key，用 `TokenEncoder` 编码后存储。
- 会话失效：在权限、共享范围、限制条件或密码变化后，通过 `SessionRegistry` 让已有 session 过期。
- 清理关联数据：删除用户时清理客户端设置、阅读进度、认证活动、同步点等用户相关数据。
- 发布领域事件：通过 `ApplicationEventPublisher` 发布 `DomainEvent.UserUpdated`，让 SSE 等订阅方知道会话需要失效。

需要注意：虽然 `DomainEvent.kt` 里存在 `UserDeleted` 事件，但当前文件删除用户后发布的是 `DomainEvent.UserUpdated(user, true)`，不是 `UserDeleted`。从现有代码看，这样做的目的仍然是通知前端/客户端当前用户 session 失效；是否应该使用 `UserDeleted` 不能仅凭当前片段断定。

## 关键组成

这个类的构造函数注入了很多依赖，基本可以按职责分组理解。

`userRepository: KomgaUserRepository`

这是用户和 API key 的主要持久化入口。目标文件里用到的方法包括：

- `count()`：统计用户数。
- `findByIdOrNull()`：更新前确认用户存在，创建后重新读取用户。
- `existsByEmailIgnoreCase()`：创建用户前检查邮箱是否重复。
- `existsApiKeyByCommentAndUserId()`：创建 API key 前检查同一用户下 comment 是否重复。
- `insert(user)`、`insert(apiKey)`、`update(user)`、`delete(userId)`：执行实际写入。

`readProgressRepository`、`authenticationActivityRepository`、`syncPointRepository`、`clientSettingsDtoDao`

这些用于删除用户时清理关联数据：

- `ReadProgressRepository`：删除该用户阅读进度。
- `AuthenticationActivityRepository`：删除该用户登录/认证活动记录。
- `SyncPointRepository`：删除同步点。
- `ClientSettingsDtoDao`：删除用户客户端设置。

删除操作包在 `TransactionTemplate.executeWithoutResult` 中，意味着这些数据库清理和用户删除被当作一个事务片段处理。根据当前片段推断，如果其中一个清理步骤失败，事务会回滚，避免出现“用户删了但部分关联数据还在”或“关联数据删了但用户还在”的不一致状态。

`passwordEncoder: PasswordEncoder`

用于 `createUser` 和 `updatePassword`。代码不会直接保存传入的明文密码，而是调用：

```kotlin
passwordEncoder.encode(newPassword)
```

或：

```kotlin
passwordEncoder.encode(komgaUser.password)
```

`tokenEncoder: TokenEncoder` 和 `apiKeyGenerator: ApiKeyGenerator`

用于 API key 创建流程：

- `ApiKeyGenerator.generate()` 生成明文 API key。
- `TokenEncoder.encode()` 对 key 编码后存库。
- 返回给调用方的是包含明文 key 的 `ApiKey` 对象。

也就是说，数据库保存的是编码后的 key，调用方拿到的是创建时仅此一次可展示的明文 key。这个模式和很多系统里的 token/API key 设计一致。

`sessionRegistry: SessionRegistry`

用于查找并过期用户的 Spring Security session。`expireSessions(user)` 会构造 `KomgaPrincipal(user)`，然后调用：

```kotlin
sessionRegistry.getAllSessions(KomgaPrincipal(user), false)
```

对每个 session 执行 `expireNow()`。

`eventPublisher: ApplicationEventPublisher`

用于发布 `DomainEvent.UserUpdated`。这个事件携带两个字段：

- `user: KomgaUser`
- `expireSession: Boolean`

在 `interfaces/sse/SseController.kt` 中，`DomainEvent.UserUpdated` 会在 `expireSession == true` 时向该用户推送 `SessionExpired` SSE 事件。也就是说，`KomgaUserLifecycle` 不直接管 SSE，只发布领域事件；SSE 层根据事件决定是否通知客户端。

`transactionTemplate: TransactionTemplate`

只在 `deleteUser` 中使用。它让删除用户和清理用户关联数据处于事务控制中。

`logger`

文件顶部定义：

```kotlin
private val logger = KotlinLogging.logger {}
```

用于记录用户更新、删除、session 失效、API key 重试等操作日志。

## 上下游关系

上游调用方主要是接口层、启动任务和认证集成代码。

从调用关系看，`KomgaUserLifecycle` 被这些位置使用：

- `interfaces/api/rest/UserController.kt`
- `interfaces/api/rest/ClaimController.kt`
- `interfaces/apprunner/PasswordResetRunner.kt`
- `interfaces/scheduler/InitialUserController.kt`
- `infrastructure/security/oauth2/KomgaOAuth2UserServiceConfiguration.kt`

其中 `UserController.kt` 是最主要的 HTTP API 调用方。例如：

- 用户修改自己的密码时调用 `updatePassword(user, newPassword, false)`。
- 管理员修改其他用户密码时调用 `updatePassword(user, newPassword, user.id != principal.user.id)`。
- 删除用户时调用 `deleteUser(it)`。
- 更新用户资料/权限时调用 `updateUser(updatedUser)`。
- 创建 API key 时调用 `createApiKey(principal.user, apiKeyRequest.comment)`。

`PasswordResetRunner.kt` 会在应用运行器场景中重置密码，并传入 `expireSessions = true`，说明命令式重置密码后需要让旧 session 失效。

下游依赖主要包括：

- `domain.persistence.KomgaUserRepository`：用户和 API key 的核心持久化。
- `domain.persistence.ReadProgressRepository`：删除阅读进度。
- `domain.persistence.AuthenticationActivityRepository`：删除认证活动。
- `domain.persistence.SyncPointRepository`：删除同步点。
- `infrastructure.jooq.main.ClientSettingsDtoDao`：删除客户端设置。
- `infrastructure.security.TokenEncoder`：编码 API key。
- `infrastructure.security.apikey.ApiKeyGenerator`：生成 API key。
- `infrastructure.security.KomgaPrincipal`：用于匹配 Spring Security session。
- Spring Security 的 `SessionRegistry`、`PasswordEncoder`。
- Spring 的 `ApplicationEventPublisher` 和 `TransactionTemplate`。

事件下游中，`interfaces/sse/SseController.kt` 监听 `DomainEvent.UserUpdated`。当 `expireSession` 为 `true` 时，它会发送 `SessionExpired` 事件给对应用户。客户端收到后通常应重新认证或退出当前会话，具体客户端行为需看前端/移动端实现。

领域模型方面，`KomgaUser` 定义在 `domain/model/KomgaUser.kt`。它包含：

- `email`
- `password`
- `roles`
- `sharedLibrariesIds`
- `sharedAllLibraries`
- `restrictions`
- `id`
- 审计字段 `createdDate`、`lastModifiedDate`

`KomgaUser` 还有 `isAdmin`、`canAccessAllLibraries()`、`canAccessLibrary()`、`isContentAllowed()` 等权限/可见性相关逻辑。因此 `KomgaUserLifecycle.updateUser()` 特别关注角色、限制和共享库字段是否变化，一旦变化就会过期 session。

## 运行/调用流程

创建用户流程：

1. 上层构造一个 `KomgaUser`，其中密码仍可能是明文。
2. 调用 `createUser(komgaUser)`。
3. `createUser` 先通过 `existsByEmailIgnoreCase(komgaUser.email)` 检查邮箱是否已经存在。
4. 如果存在，抛出 `UserEmailAlreadyExistsException`。
5. 如果不存在，用 `passwordEncoder.encode(komgaUser.password)` 编码密码。
6. 调用 `userRepository.insert(...)` 插入用户。
7. 再用 `findByIdOrNull(komgaUser.id)!!` 读取刚创建的用户。
8. 记录日志并返回创建后的 `KomgaUser`。

这里重新读取一次用户，可能是为了拿到数据库层补全或规范化后的字段。根据当前片段看，`KomgaUser` 本身已经有默认 `id` 和时间字段，但 repository 实现可能还会处理其他细节。

修改密码流程：

1. 调用 `updatePassword(user, newPassword, expireSessions)`。
2. 用 `passwordEncoder.encode(newPassword)` 生成新密码哈希/编码值。
3. 通过 `user.copy(password = encoded)` 得到更新后的用户对象。
4. 调用 `userRepository.update(updatedUser)`。
5. 如果 `expireSessions == true`，调用 `expireSessions(updatedUser)`。
6. 发布 `DomainEvent.UserUpdated(updatedUser, expireSessions)`。

这里的 `expireSessions` 参数由上游决定。比如用户自己改密码时可能不踢掉当前 session，而管理员改其他人的密码或命令行重置密码时会让已有 session 失效。

更新用户资料流程：

1. 调用 `updateUser(user)`。
2. 先通过 `findByIdOrNull(user.id)` 查找已有用户。
3. 如果用户不存在，`requireNotNull(existing)` 会抛错，提示不能更新不存在的用户。
4. 生成 `toUpdate = user.copy(password = existing.password)`。
5. 调用 `userRepository.update(toUpdate)`。
6. 比较以下字段是否变化：
   - `roles`
   - `restrictions`
   - `sharedAllLibraries`
   - `sharedLibrariesIds`
7. 如果这些权限/访问范围相关字段发生变化，则 `expireSessions = true`。
8. 需要时调用 `expireSessions(toUpdate)`。
9. 发布 `DomainEvent.UserUpdated(toUpdate, expireSessions)`。

这里有一个很重要的设计：`updateUser` 会强制保留原密码，不接受传入对象里的 `password`。这说明普通用户资料更新和密码更新被刻意拆开，避免“更新用户资料时顺手改密码”造成安全风险或误覆盖。

删除用户流程：

1. 调用 `deleteUser(user)`。
2. 记录删除日志。
3. 进入 `transactionTemplate.executeWithoutResult`。
4. 依次删除：
   - 客户端设置：`clientSettingsDtoDao.deleteByUserId(user.id)`
   - 阅读进度：`readProgressRepository.deleteByUserId(user.id)`
   - 认证活动：`authenticationActivityRepository.deleteByUser(user)`
   - 同步点：`syncPointRepository.deleteByUserId(user.id)`
   - 用户本身：`userRepository.delete(user.id)`
5. 事务结束后调用 `expireSessions(user)`。
6. 发布 `DomainEvent.UserUpdated(user, true)`。

删除用户时，session 失效发生在事务外。根据当前片段推断，这是因为 session registry 不属于数据库事务，只有数据库删除成功后才需要处理登录态。

失效 session 流程：

1. 调用 `expireSessions(user)`。
2. 构造 `KomgaPrincipal(user)`。
3. 通过 `sessionRegistry.getAllSessions(..., false)` 查找该用户所有未过期 session。
4. 遍历每个 session，记录 session id。
5. 调用 `expireNow()` 标记 session 过期。

这里的关键是 `KomgaPrincipal(user)` 的相等性/匹配逻辑必须能和登录时注册到 `SessionRegistry` 的 principal 对上。否则 `getAllSessions` 可能找不到该用户的 session。具体匹配规则需要继续查看 `infrastructure/security/KomgaPrincipal` 才能完全确认。

创建 API key 流程：

1. 调用 `createApiKey(user, comment)`。
2. 先对 `comment` 执行 `trim()`。
3. 检查同一用户下是否已有相同 comment 的 API key。
4. 如果有，抛出 `DuplicateNameException("api key comment already exists for this user", "ERR_1034")`。
5. 最多尝试 10 次生成唯一 API key。
6. 每次尝试中：
   - 创建明文 `ApiKey(userId = user.id, key = apiKeyGenerator.generate(), comment = commentTrimmed)`。
   - 存库时使用 `plainTextKey.copy(key = tokenEncoder.encode(plainTextKey.key))`。
   - 成功后返回明文 `plainTextKey`。
7. 如果插入过程中抛异常，会记录 debug 日志并重试。
8. 10 次都失败则返回 `null`。

这里捕获的是通用 `Exception`，注释说明目的是处理“无法生成唯一 API key”的情况。根据当前片段推断，唯一性冲突可能来自数据库约束或 repository 插入逻辑；代码没有显式判断具体异常类型。

## 小白阅读顺序

1. 先读 `domain/model/KomgaUser.kt`，理解用户对象有哪些字段，尤其是 `roles`、`sharedLibrariesIds`、`sharedAllLibraries`、`restrictions`、`password`。
2. 再读 `domain/persistence/KomgaUserRepository.kt`，看用户服务能对数据库做哪些动作。这个接口能帮助你理解 `KomgaUserLifecycle` 为什么只调用 repository，而不是自己写 SQL。
3. 然后读本文件 `domain/service/KomgaUserLifecycle.kt`，按函数顺序看：
   - `createUser`
   - `updatePassword`
   - `updateUser`
   - `deleteUser`
   - `expireSessions`
   - `createApiKey`
4. 接着看 `interfaces/api/rest/UserController.kt`，理解 HTTP 请求如何调用这些生命周期方法。
5. 再看 `domain/model/DomainEvent.kt` 中的 `UserUpdated`，明白事件携带了什么。
6. 最后看 `interfaces/sse/SseController.kt` 对 `DomainEvent.UserUpdated` 的处理，理解为什么服务层发布事件后，客户端会收到 `SessionExpired`。

如果只想快速理解这个文件，可以先抓住一条主线：用户数据变化后，不只是写数据库，还可能要让旧 session 失效，并通知客户端。

## 常见误区

误区一：以为 `updateUser` 会更新密码。

实际上不会。`updateUser` 明确执行：

```kotlin
val toUpdate = user.copy(password = existing.password)
```

这会保留数据库里原来的密码。修改密码必须走 `updatePassword`。

误区二：以为所有用户更新都会踢 session。

不是。`updateUser` 只在这些字段变化时才让 session 失效：

- `roles`
- `restrictions`
- `sharedAllLibraries`
- `sharedLibrariesIds`

这些字段会影响用户权限、内容可见性或访问范围，所以旧 session 不能继续沿用旧权限状态。其他字段变化不一定需要踢 session。

误区三：以为 `DomainEvent.UserUpdated` 只表示普通资料更新。

在这个文件中，删除用户后也发布了 `DomainEvent.UserUpdated(user, true)`。它在这里更像是“用户相关状态发生变化，并且客户端 session 需要失效”的信号，而不只是狭义的资料更新事件。

误区四：以为 API key 明文会存进数据库。

不会。`createApiKey` 返回的是明文 key，但插入 repository 的是：

```kotlin
plainTextKey.copy(key = tokenEncoder.encode(plainTextKey.key))
```

也就是编码后的 key。调用方必须在创建时展示或保存明文，因为之后通常无法从数据库还原明文。

误区五：以为 `createApiKey` 一定成功。

不一定。它最多尝试 10 次。如果一直因为异常失败，最终返回 `null`。上游调用方需要处理空值。`UserController.kt` 中创建 API key 时使用了安全调用 `?.toDto()`，说明它确实考虑了失败返回 `null` 的情况。

误区六：以为删除用户只删 `user` 表。

不是。`deleteUser` 会清理多个用户关联数据，包括客户端设置、阅读进度、认证活动、同步点，最后才删除用户本身。这体现了领域服务层的价值：它知道“删除一个用户”在业务上意味着哪些关联资源也要处理。

误区七：以为 session 失效和 SSE 通知是一回事。

不是。`expireSessions(user)` 是服务端 Spring Security session 层面的失效；`eventPublisher.publishEvent(DomainEvent.UserUpdated(...))` 触发的是事件机制，下游 `SseController` 可能给客户端推送 `SessionExpired`。前者影响服务端认证状态，后者影响客户端感知和交互。两者常常一起发生，但不是同一个动作。
