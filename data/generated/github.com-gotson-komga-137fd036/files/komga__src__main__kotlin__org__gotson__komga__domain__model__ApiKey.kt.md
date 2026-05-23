# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/ApiKey.kt

## 它负责什么

`ApiKey.kt` 定义了 Komga 领域层里的 API Key 实体模型：`org.gotson.komga.domain.model.ApiKey`。

它本身不负责生成密钥、不负责鉴权、不负责数据库读写，也不负责 HTTP 接口返回格式；它只表达“一条 API Key 记录在领域模型中应该包含哪些字段”。后续的服务层、持久化层、安全认证层都会围绕这个模型工作。

文件内容很短：

```kotlin
data class ApiKey(
  val id: String = TsidCreator.getTsid256().toString(),
  val userId: String,
  val key: String,
  val comment: String,
  override val createdDate: LocalDateTime = LocalDateTime.now(),
  override val lastModifiedDate: LocalDateTime = createdDate,
) : Auditable
```

可以把它理解为“用户 API Key 的领域对象”。它表示某个用户拥有的一把 API Key，并带有显示备注和审计时间。

## 关键组成

`ApiKey.kt` 位于领域模型包：

`org.gotson.komga.domain.model`

它导入了两个外部类型：

`com.github.f4b6a3.tsid.TsidCreator`：用于默认生成 `id`。这里使用 `TsidCreator.getTsid256().toString()`，说明 `ApiKey.id` 默认是一个 TSID 字符串，而不是数据库自增 ID。

`java.time.LocalDateTime`：用于 `createdDate` 和 `lastModifiedDate` 两个审计字段。

核心类是 `data class ApiKey`。因为它是 Kotlin `data class`，编译器会自动生成 `equals`、`hashCode`、`toString`、`copy`、`componentN` 等方法。这个特性在领域对象传递、DTO 转换、测试断言里都很常见。

字段含义如下：

`id`：API Key 记录自身的唯一标识。默认值由 `TsidCreator.getTsid256().toString()` 生成。它不是用户真正拿去请求接口的密钥，而是这条 API Key 记录的 ID，删除 API Key 时使用的就是类似 `keyId` 这样的标识。

`userId`：拥有这把 API Key 的用户 ID。它把 `ApiKey` 和 `KomgaUser` 关联起来。

`key`：真正参与认证匹配的 API Key 值。从调用链看，这个字段在不同阶段可能代表不同形态：创建后返回给前端时可能是明文 key；持久化和认证查询时则更可能是编码后的 key。根据当前片段推断，依据是 `KomgaUserLifecycle.createApiKey` 会使用 `ApiKeyGenerator` 创建 key，而安全层的 `HeaderApiKeyAuthenticationConverter`、`UriRegexApiKeyAuthenticationConverter` 会先对请求中的 key 做 `tokenEncoder.encode(it)`，再交给 `ApiKeyAuthenticationProvider` 查询仓库。

`comment`：用户给 API Key 写的备注。它不是安全凭据，而是帮助用户区分不同 key 的人类可读说明。创建时服务层会检查同一用户下备注是否重复。

`createdDate`：创建时间，默认是 `LocalDateTime.now()`。

`lastModifiedDate`：最后修改时间，默认等于 `createdDate`。因为这个模型目前没有看到更新 API Key 的业务入口，所以创建后通常不会发生修改。

`ApiKey : Auditable`：表示它实现了同目录下的 `Auditable` 接口。`Auditable` 只要求两个属性：

```kotlin
interface Auditable {
  val createdDate: LocalDateTime
  val lastModifiedDate: LocalDateTime
}
```

所以 `ApiKey` 需要用 `override val createdDate` 和 `override val lastModifiedDate` 实现审计字段。

## 上下游关系

上游主要是创建 API Key 的业务流程。

`komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt` 中的 `createApiKey` 会负责创建并持久化 API Key。它接收 `KomgaUser` 和用户输入的 `comment`，先对备注做 `trim`，再通过 `KomgaUserRepository.existsApiKeyByCommentAndUserId` 检查同一用户下备注是否重复。如果重复，会抛出 `DuplicateNameException`。随后它会尝试生成唯一 API Key，并创建 `ApiKey` 对象，再通过仓库保存。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/security/apikey/ApiKeyGenerator.kt` 是密钥生成来源。`ApiKey.kt` 不直接调用它，因为领域模型只保存字段，不负责生成业务密钥。

中游是持久化仓库。

`komga/src/main/kotlin/org/gotson/komga/domain/persistence/KomgaUserRepository.kt` 定义了 API Key 相关操作，包括：

`findByApiKeyOrNull(apiKey: String): Pair<KomgaUser, ApiKey>?`

`findApiKeyByUserId(userId: String): Collection<ApiKey>`

`existsApiKeyByIdAndUserId(apiKeyId: String, userId: String): Boolean`

`existsApiKeyByCommentAndUserId(comment: String, userId: String): Boolean`

`insert(apiKey: ApiKey)`

`deleteApiKeyByIdAndUserId(apiKeyId: String, userId: String)`

`deleteApiKeyByUserId(userId: String)`

这些方法说明 `ApiKey` 是挂在用户仓库能力下管理的，不是单独的 `ApiKeyRepository`。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt` 是仓库的 JOOQ 实现。它会把 `ApiKey` 映射到数据库里的 `USER_API_KEY` 相关记录。可以看到它有 `findApiKeyByUserId`、`insert(apiKey: ApiKey)`、`deleteApiKeyByIdAndUserId`、`existsApiKeyByCommentAndUserId`、`findByApiKeyOrNull` 等实现。`UserApiKeyRecord.toDomain()` 会把数据库记录转换回 `ApiKey`。

下游主要分两类：REST 管理接口和安全认证流程。

REST 管理接口在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt`：

`GET me/api-keys`：读取当前用户的 API Keys，调用 `userRepository.findApiKeyByUserId(principal.user.id)`，再转换成 DTO，并通过 `redacted()` 隐藏真实 key。

`POST me/api-keys`：创建当前用户的 API Key，调用 `userLifecycle.createApiKey(principal.user, apiKeyRequest.comment)`。成功时返回 `ApiKeyDto`，这通常是用户唯一能看到完整 API Key 的时机。

`DELETE me/api-keys/{keyId}`：删除当前用户指定 ID 的 API Key。它先用 `existsApiKeyByIdAndUserId` 确认这条 key 属于当前用户，再调用 `deleteApiKeyByIdAndUserId` 删除。

DTO 转换在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/ApiKeyDto.kt`。`ApiKey.toDto()` 会把领域对象转换为接口返回对象；`ApiKeyDto.redacted()` 会把 `key` 替换成 6 个星号，避免列表接口泄露真实 API Key。

安全认证流程在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/apikey` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/SecurityConfiguration.kt`：

`HeaderApiKeyAuthenticationConverter` 从请求头读取 API Key，例如 `X-API-Key` 或 `X-Auth-User`。

`UriRegexApiKeyAuthenticationConverter` 从 URI 中提取 API Key，例如 `/kobo/([\w-]+)`。

这些 converter 会把请求里的 key 编码后放进 `ApiKeyAuthenticationToken.credentials`。

`ApiKeyAuthenticationProvider` 再调用 `userRepository.findByApiKeyOrNull(authentication.credentials.toString())` 查询用户和 `ApiKey`。查到后构造 `KomgaPrincipal(user, apiKey = apiKey, name = authentication.name)`，把当前认证用户和使用的 API Key 一起放入 Spring Security 的 principal。

`SecurityConfiguration.kt` 配置了不同入口使用 API Key 认证：

`/kobo/**` 使用 URI 中的 key。

KoSync 相关入口使用 `X-Auth-User`。

REST API 使用 `X-API-Key`。

## 运行/调用流程

创建流程大致如下：

1. 用户通过 REST 接口请求创建 API Key，请求进入 `UserController.createApiKeyForCurrentUser`。
2. Controller 从 `KomgaPrincipal` 中拿到当前用户 `principal.user`，从请求体 `ApiKeyRequestDto` 中拿到 `comment`。
3. Controller 调用 `KomgaUserLifecycle.createApiKey(principal.user, apiKeyRequest.comment)`。
4. `KomgaUserLifecycle` 对备注做清理和唯一性检查，同一用户下已有相同备注时抛出 `DuplicateNameException`。
5. 服务层生成实际 API Key，构造 `ApiKey` 领域对象。
6. `ApiKey` 构造时，如果没有显式传入 `id`，会自动生成 TSID；如果没有传入时间，会自动设置 `createdDate = now`，`lastModifiedDate = createdDate`。
7. 服务层通过 `KomgaUserRepository.insert(apiKey)` 保存。
8. JOOQ 实现 `KomgaUserDao.insert(apiKey)` 把字段写入用户 API Key 表。
9. Controller 把 `ApiKey` 转成 `ApiKeyDto` 返回给调用方。

查询列表流程如下：

1. 用户请求 `GET me/api-keys`。
2. `UserController.getApiKeysForCurrentUser` 调用 `userRepository.findApiKeyByUserId(principal.user.id)`。
3. `KomgaUserDao.findApiKeyByUserId` 查询当前用户的所有 API Key 记录。
4. 每条数据库记录通过 `UserApiKeyRecord.toDomain()` 转成 `ApiKey`。
5. Controller 调用 `toDto().redacted()`，把真实 key 替换成 `******` 后返回。

认证流程如下：

1. 客户端请求受保护接口，并提供 API Key。REST 场景下通常在 `X-API-Key` 请求头中；KoSync 场景可能是 `X-Auth-User`；Kobo 场景可能在 `/kobo/{key}` 这样的 URI 中。
2. 对应的 `ApiKeyAuthenticationFilter` 使用 converter 提取 key。
3. converter 对原始 key 做 hash/encode 处理，创建未认证的 `ApiKeyAuthenticationToken`。
4. Spring Security 调用 `ApiKeyAuthenticationProvider.retrieveUser`。
5. Provider 使用 `KomgaUserRepository.findByApiKeyOrNull` 查询数据库。
6. 如果找到匹配记录，返回包含 `KomgaUser` 和 `ApiKey` 的 `KomgaPrincipal`。
7. 后续业务代码可以通过 `@AuthenticationPrincipal principal: KomgaPrincipal` 获取当前用户；如果需要，也可以读取 `principal.apiKey` 知道本次请求使用的是哪一把 API Key。

删除流程如下：

1. 用户请求 `DELETE me/api-keys/{keyId}`。
2. Controller 用 `existsApiKeyByIdAndUserId(keyId, principal.user.id)` 确认这条 API Key 存在且属于当前用户。
3. 如果不存在，返回 `404 NOT_FOUND`。
4. 如果存在，调用 `deleteApiKeyByIdAndUserId(keyId, principal.user.id)` 删除。
5. 根据当前片段还可以看到 `SyncPointController` 和 `SyncPointRepository.deleteByUserIdAndApiKeyIds` 会处理和 API Key 相关的同步点清理逻辑；具体触发时机需要继续查看同步相关代码才能完全确认。

## 小白阅读顺序

建议先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/ApiKey.kt`，只看字段含义。重点区分 `id` 和 `key`：`id` 是这条记录的 ID，`key` 才是认证用的密钥值。

第二步读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Auditable.kt`，理解为什么 `ApiKey` 要 `override createdDate` 和 `override lastModifiedDate`。

第三步读 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/KomgaUserRepository.kt`，看有哪些围绕 API Key 的仓库方法。这里能帮助你理解领域模型会被怎样保存、查询、删除。

第四步读 `komga/src/main/kotlin/org/gotson/komga/domain/service/KomgaUserLifecycle.kt` 的 `createApiKey`，理解 API Key 是在哪里创建的。这里比 `ApiKey.kt` 更接近业务规则，例如备注去空格、备注唯一性、生成失败重试、保存到仓库等。

第五步读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt` 中和 API Key 相关的方法，尤其是 `insert(apiKey: ApiKey)`、`findApiKeyByUserId`、`findByApiKeyOrNull`、`UserApiKeyRecord.toDomain()`。这一步能把领域对象和数据库字段对应起来。

第六步读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt` 中的 `me/api-keys` 三个接口，理解用户如何创建、查看、删除 API Key。

最后读安全认证部分：`komga/src/main/kotlin/org/gotson/komga/infrastructure/security/apikey/HeaderApiKeyAuthenticationConverter.kt`、`komga/src/main/kotlin/org/gotson/komga/infrastructure/security/apikey/UriRegexApiKeyAuthenticationConverter.kt`、`komga/src/main/kotlin/org/gotson/komga/infrastructure/security/apikey/ApiKeyAuthenticationProvider.kt`、`komga/src/main/kotlin/org/gotson/komga/infrastructure/security/SecurityConfiguration.kt`。这一步能理解 API Key 如何从 HTTP 请求变成登录态。

## 常见误区

第一个误区：把 `ApiKey.id` 当成客户端请求时使用的 API Key。实际上 `id` 是记录 ID，用于标识、删除、关联；`key` 字段才和认证凭据有关。

第二个误区：以为 `ApiKey.kt` 会生成真正的 API Key。它只会默认生成 `id`。真正的密钥生成在安全/服务相关组件中完成，例如 `ApiKeyGenerator` 和 `KomgaUserLifecycle.createApiKey`。

第三个误区：以为 `comment` 可以随便重复。服务层会检查 `existsApiKeyByCommentAndUserId`，同一用户下重复备注会被拒绝，错误会在 REST 层转成 `BAD_REQUEST`。

第四个误区：以为查询 API Key 列表会返回真实 key。`UserController.getApiKeysForCurrentUser` 会调用 `redacted()`，把 key 替换成 `******`。通常只有创建 API Key 的响应才适合展示完整 key。

第五个误区：以为 `ApiKey.key` 在所有层都一定是明文。根据当前片段推断，认证流程会对请求中的 key 做 `tokenEncoder.encode` 后查询仓库，因此数据库里保存和查询的更可能是编码后的值；而创建接口为了让用户看到新生成的 key，返回对象中的 `key` 可能是明文。阅读时要结合调用位置判断，不要只看字段名下结论。

第六个误区：看到 `lastModifiedDate` 就以为 API Key 有更新流程。当前片段里主要看到创建、查询、删除，没有看到修改 API Key 的 REST 入口。`lastModifiedDate` 更多是为了统一实现 `Auditable`，以及和其他领域模型保持一致。

第七个误区：以为 API Key 只服务普通 REST API。`SecurityConfiguration.kt` 显示它还参与 Kobo、KoSync 等入口认证：REST 使用 `X-API-Key`，KoSync 使用 `X-Auth-User`，Kobo 可以从 `/kobo/{key}` 形式的 URI 中提取 key。
