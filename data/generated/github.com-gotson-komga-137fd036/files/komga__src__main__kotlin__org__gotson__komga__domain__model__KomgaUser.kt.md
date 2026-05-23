# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt

## 它负责什么

`KomgaUser.kt` 定义 Komga 系统中的用户领域模型 `KomgaUser`。它不是一个单纯的数据容器，而是把“用户身份信息”和“用户访问权限规则”放在同一个领域对象里。

这个文件主要负责四类事情：

1. 表示用户基础数据：邮箱、密码、角色、用户 id、创建时间、修改时间。
2. 表示用户可访问的图书库范围：是否能访问全部 library，或者只能访问 `sharedLibrariesIds` 指定的 library。
3. 表示用户的内容限制规则：年龄分级限制、分享标签 allow/exclude 限制。
4. 提供权限判断方法：例如 `canAccessLibrary`、`getAuthorizedLibraryIds`、`isContentAllowed`，供 API 层、查询层、内容检查器复用。

它位于 `org.gotson.komga.domain.model` 包下，属于领域模型层。调用方不需要知道数据库里用户权限如何存储，只需要拿到 `KomgaUser` 后调用这些方法即可。

## 关键组成

### `KomgaUser` 数据类

核心定义是：

```kotlin
data class KomgaUser(...)
```

主要字段如下：

- `email: String`

  用户邮箱。字段上有：

  ```kotlin
  @Email(regexp = ".+@.+\\..+")
  @NotBlank
  ```

  表示邮箱不能为空，并且需要满足一个简单的邮箱格式校验。

- `password: String`

  用户密码，同样要求 `@NotBlank`。从模型本身看，它只是保存密码字符串；根据当前片段不能确定这里一定是明文还是已加密值，但在持久化层 `KomgaUserDao` 中会直接把 `user.password` 写入 `USER.PASSWORD` 字段，因此实际值如何处理应继续看 `userLifecycle.createUser` 等上游服务。

- `roles: Set<UserRoles>`

  用户角色集合，默认值是：

  ```kotlin
  setOf(UserRoles.FILE_DOWNLOAD, UserRoles.PAGE_STREAMING)
  ```

  也就是说普通新用户默认具备文件下载和页面流式读取能力，但默认不是管理员。

  `UserRoles.kt` 中定义的角色包括：

  - `ADMIN`
  - `FILE_DOWNLOAD`
  - `PAGE_STREAMING`
  - `KOBO_SYNC`
  - `KOREADER_SYNC`

- `sharedLibrariesIds: Set<String>`

  用户被授权访问的 library id 集合。它只在用户不是“访问全部 library”时真正起过滤作用。

- `sharedAllLibraries: Boolean`

  是否共享全部 library。默认是 `true`。这意味着如果没有额外配置，用户默认可访问所有 library。

- `restrictions: ContentRestrictions`

  内容限制规则，默认是空限制：

  ```kotlin
  ContentRestrictions()
  ```

  `ContentRestrictions` 内部包含：

  - `ageRestriction: AgeRestriction?`
  - `labelsAllow: Set<String>`
  - `labelsExclude: Set<String>`

- `id: String`

  用户 id，默认使用：

  ```kotlin
  TsidCreator.getTsid256().toString()
  ```

  这说明用户 id 不是数据库自增整数，而是由 TSID 生成器产生的字符串。TSID 通常用于生成带时间特征、可排序的唯一 id。

- `createdDate`、`lastModifiedDate`

  这两个字段来自 `Auditable` 接口：

  ```kotlin
  interface Auditable {
    val createdDate: LocalDateTime
    val lastModifiedDate: LocalDateTime
  }
  ```

  `KomgaUser` 默认创建时间是 `LocalDateTime.now()`，默认修改时间等于创建时间。

### `isAdmin`

```kotlin
@delegate:Transient
val isAdmin: Boolean by lazy {
  roles.contains(UserRoles.ADMIN)
}
```

`isAdmin` 是一个惰性计算属性，用来判断当前用户是否包含 `UserRoles.ADMIN`。

这里有两个细节：

1. 它不是构造参数，而是根据 `roles` 派生出来的属性。
2. `@delegate:Transient` 表示 lazy 委托字段不参与某些序列化/持久化处理，避免把 lazy 的内部状态当成业务字段。

管理员身份会影响 library 权限判断。即使 `sharedAllLibraries` 是 `false`，只要 `isAdmin` 为 `true`，`canAccessAllLibraries()` 仍然返回 `true`。

### `getAuthorizedLibraryIds`

```kotlin
fun getAuthorizedLibraryIds(libraryIds: Collection<String>?): Collection<String>?
```

这个方法把“调用方希望查询的 library 范围”和“当前用户实际有权限的 library 范围”合并成最终可用的过滤条件。

它的返回值设计很重要：

- 返回 `null`：表示不需要按 library 过滤，也就是用户可以看全部 library。
- 返回一个集合：表示只能看集合内的 library。
- 返回空集合：表示经过交集后没有可访问 library。

逻辑分四种情况：

1. 用户不能访问全部 library，且调用方传入了 `libraryIds`

   ```kotlin
   libraryIds.intersect(sharedLibrariesIds)
   ```

   返回请求范围和用户授权范围的交集。

2. 用户不能访问全部 library，且调用方没有传入 `libraryIds`

   ```kotlin
   sharedLibrariesIds
   ```

   返回用户被授权的全部 library。

3. 用户可以访问全部 library，且调用方传入了 `libraryIds`

   ```kotlin
   libraryIds
   ```

   用户权限不再缩小范围，但保留调用方主动指定的查询范围。

4. 用户可以访问全部 library，且调用方没有传入 `libraryIds`

   ```kotlin
   null
   ```

   表示查询层不需要增加 library 限制。

这个方法在很多 Controller 和 Repository 调用中出现，例如 `ReferentialController`、`BookController`、`ReadListController`、`SeriesCollectionController`、OPDS 控制器等。它是“把用户权限转成查询条件”的主要入口。

### `canAccessAllLibraries`

```kotlin
fun canAccessAllLibraries(): Boolean = sharedAllLibraries || isAdmin
```

判断用户是否能访问所有 library。

注意这里是“或”关系：

- `sharedAllLibraries == true`，可以访问全部 library。
- 或者用户是 `ADMIN`，也可以访问全部 library。

因此管理员权限会覆盖 `sharedLibrariesIds` 的限制。

### `canAccessLibrary`

文件里有两个重载：

```kotlin
fun canAccessLibrary(libraryId: String): Boolean =
  canAccessAllLibraries() || sharedLibrariesIds.any { it == libraryId }

fun canAccessLibrary(library: Library): Boolean =
  canAccessAllLibraries() || sharedLibrariesIds.any { it == library.id }
```

一个接收 `libraryId: String`，一个接收 `Library` 对象。

它们的逻辑一致：

1. 如果用户能访问所有 library，直接返回 `true`。
2. 否则检查目标 library id 是否存在于 `sharedLibrariesIds` 中。

这类方法常用于访问单个资源前的即时权限判断。例如 `ContentRestrictionChecker` 中，访问 book 或 series 前会先判断用户是否能访问对应 `libraryId`，不允许则抛出 `403 FORBIDDEN`。

### `isContentAllowed`

```kotlin
fun isContentAllowed(
  ageRating: Int? = null,
  sharingLabels: Set<String> = emptySet(),
): Boolean
```

这个方法判断某个内容是否通过当前用户的内容限制规则。输入是内容自身的元数据：

- `ageRating`：内容年龄分级，可为空。
- `sharingLabels`：内容的分享标签集合。

方法内部会先处理标签：

```kotlin
val labels = sharingLabels.lowerNotBlank().toSet()
```

这说明标签会被转成小写，并过滤空白值。`ContentRestrictions` 构造时也会对 allow/exclude 标签做类似归一化，所以匹配时大小写不敏感，空白标签不会参与判断。

#### 第一阶段：allow 规则

先计算两个“允许条件”：

```kotlin
val ageAllowed =
  if (restrictions.ageRestriction?.restriction == AllowExclude.ALLOW_ONLY)
    ageRating != null && ageRating <= restrictions.ageRestriction.age
  else
    null
```

当年龄限制模式是 `ALLOW_ONLY` 时，只有内容的 `ageRating` 不为空，且小于等于用户允许年龄，才算年龄允许。

如果不是 `ALLOW_ONLY`，`ageAllowed` 是 `null`，表示年龄 allow 规则没有启用。

标签 allow 规则：

```kotlin
val labelAllowed =
  if (restrictions.labelsAllow.isNotEmpty())
    restrictions.labelsAllow.intersect(labels).isNotEmpty()
  else
    null
```

如果配置了 `labelsAllow`，内容标签必须和 allow 集合有交集，才算标签允许。如果没有配置 allow 标签，则 `labelAllowed` 为 `null`，表示标签 allow 规则没有启用。

随后组合 `ageAllowed` 和 `labelAllowed`：

```kotlin
val allowed =
  when {
    ageAllowed == null -> labelAllowed != false
    labelAllowed == null -> ageAllowed != false
    else -> ageAllowed != false || labelAllowed != false
  }
if (!allowed) return false
```

可以这样理解：

- 如果只启用了标签 allow，那么标签 allow 不能是 `false`。
- 如果只启用了年龄 allow，那么年龄 allow 不能是 `false`。
- 如果年龄 allow 和标签 allow 都启用了，只要其中一个不是 `false` 就可以通过 allow 阶段。

第三种情况尤其容易误读：当 `ALLOW_ONLY` 年龄限制和 `labelsAllow` 同时存在时，它不是要求“两者都满足”，而是“年龄满足或标签满足即可进入下一阶段”。

#### 第二阶段：exclude 规则

通过 allow 阶段后，再计算 deny 条件。

年龄 exclude：

```kotlin
val ageDenied =
  if (restrictions.ageRestriction?.restriction == AllowExclude.EXCLUDE)
    ageRating != null && ageRating >= restrictions.ageRestriction.age
  else
    false
```

当年龄限制模式是 `EXCLUDE` 时，如果内容年龄分级不为空且大于等于限制年龄，则拒绝。

标签 exclude：

```kotlin
val labelDenied =
  if (restrictions.labelsExclude.isNotEmpty())
    restrictions.labelsExclude.intersect(labels).isNotEmpty()
  else
    false
```

只要内容标签和 exclude 集合有交集，就拒绝。

最终返回：

```kotlin
return !ageDenied && !labelDenied
```

也就是说 exclude 规则是硬拒绝：年龄拒绝或标签拒绝任意一个命中，内容都不可访问。

### `toString`

`KomgaUser` 覆盖了 `toString()`：

```kotlin
override fun toString(): String =
  "KomgaUser(createdDate=$createdDate, email='$email', roles=$roles, sharedLibrariesIds=$sharedLibrariesIds, sharedAllLibraries=$sharedAllLibraries, restrictions=$restrictions, id='$id', lastModifiedDate=$lastModifiedDate)"
```

注意它没有输出 `password`。这是一个有意的安全处理，避免日志或调试输出中泄露密码字段。

## 上下游关系

### 上游：创建和更新用户

`KomgaUser` 会被 API 层和初始化逻辑创建。

在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt` 中，管理员创建用户时会根据请求 DTO 构造 `KomgaUser`：

```kotlin
KomgaUser(
  email,
  password,
  roles = UserRoles.Companion.valuesOf(roles),
  sharedAllLibraries = sharedLibraries == null || sharedLibraries.all,
  sharedLibrariesIds = ...,
  restrictions = ContentRestrictions(...)
)
```

这里能看到几个业务默认值：

- 如果请求没有设置 `sharedLibraries`，默认用户可访问全部 library。
- 如果请求没有设置限制，默认没有内容限制。
- 请求中的角色字符串通过 `UserRoles.valuesOf` 转换成领域枚举集合。
- 请求中的年龄限制和标签限制被转换成 `ContentRestrictions`。

更新用户时，`UserController` 使用 Kotlin data class 的 `copy`：

```kotlin
existing.copy(...)
```

只替换请求中实际设置的字段，未设置的字段沿用旧值。

初始化逻辑中也会创建用户，例如 `InitialUserController` 会创建默认管理员或测试用户：

```kotlin
KomgaUser("admin@example.org", "admin", roles = UserRoles.entries.toSet())
KomgaUser("user@example.org", "user")
```

根据当前片段推断，`roles = UserRoles.entries.toSet()` 表示管理员测试用户拥有所有角色。

### 下游：数据库持久化

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt` 负责把数据库记录映射成 `KomgaUser`，以及把 `KomgaUser` 写回数据库。

读取时，DAO 会：

- 从 `USER` 表读取基础用户字段。
- 从 `USER_ROLE` 表读取角色。
- 从 `USER_LIBRARY_SHARING` 表读取可访问 library。
- 从 `USER_SHARING` 表读取标签 allow/exclude。
- 根据 `AGE_RESTRICTION` 和 `AGE_RESTRICTION_ALLOW_ONLY` 还原 `AgeRestriction`。
- 最终构造 `KomgaUser`。

例如：

```kotlin
KomgaUser(
  email = userRecord.email,
  password = userRecord.password,
  roles = UserRoles.valuesOf(roles),
  sharedLibrariesIds = ulr.mapNotNull { it.libraryId }.toSet(),
  sharedAllLibraries = userRecord.sharedAllLibraries,
  restrictions = ContentRestrictions(...),
  id = userRecord.id,
  createdDate = userRecord.createdDate.toCurrentTimeZone(),
  lastModifiedDate = userRecord.lastModifiedDate.toCurrentTimeZone(),
)
```

写入时，DAO 会把 `KomgaUser` 拆开写到多张表：

- `USER`：基础字段、密码、是否共享所有 library、年龄限制。
- `USER_ROLE`：角色集合。
- `USER_LIBRARY_SHARING`：指定共享 library。
- `USER_SHARING`：标签 allow/exclude 限制。

所以 `KomgaUser` 是领域层聚合后的用户视图，数据库层则是拆表存储。

### 下游：API 权限检查

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/ContentRestrictionChecker.kt` 是一个典型调用方。

访问 book 时，它会先检查 library 权限：

```kotlin
if (!komgaUser.canAccessLibrary(book.libraryId)) {
  throw ResponseStatusException(HttpStatus.FORBIDDEN)
}
```

如果用户有内容限制，再读取 series metadata，检查年龄分级和分享标签：

```kotlin
if (komgaUser.restrictions.isRestricted)
  seriesMetadataRepository.findById(book.seriesId).let {
    if (!komgaUser.isContentAllowed(it.ageRating, it.sharingLabels)) {
      throw ResponseStatusException(HttpStatus.FORBIDDEN)
    }
  }
```

这说明 `KomgaUser` 的权限判断方法直接决定 API 是否返回 `403 FORBIDDEN`。

### 下游：查询过滤

很多 Controller 会把 `principal.user.getAuthorizedLibraryIds(...)` 传给 repository。

例如 `ReferentialController`、`ReadListController`、`SeriesCollectionController`、`BookController`、`OpdsController`、`Opds2Controller` 等都会调用：

```kotlin
principal.user.getAuthorizedLibraryIds(null)
```

或者：

```kotlin
principal.user.getAuthorizedLibraryIds(libraryIds)
```

这些 repository 再根据返回值决定 SQL 查询是否加 library 过滤条件。

这是一种常见分层方式：

- `KomgaUser` 负责算出“当前用户最终允许查询哪些 library”。
- Repository/DAO 负责把这个结果转成数据库查询条件。

### 相关领域模型

`KomgaUser.kt` 依赖同目录下几个模型：

- `UserRoles.kt`

  定义角色枚举，并提供 `valuesOf(roles: Iterable<String>)`，用于把字符串集合转换成 `Set<UserRoles>`。无效字符串会被忽略。

- `ContentRestrictions.kt`

  定义内容限制集合。构造时会把标签统一转小写、过滤空白，并且会从 `labelsAllow` 中移除同时出现在 `labelsExclude` 的标签。也就是说 exclude 优先级更高。

- `AgeRestriction.kt`

  定义年龄限制：

  ```kotlin
  data class AgeRestriction(
    val age: Int,
    val restriction: AllowExclude,
  )
  ```

  `AllowExclude` 有两个值：

  - `ALLOW_ONLY`
  - `EXCLUDE`

- `Auditable.kt`

  定义审计字段接口，要求模型提供 `createdDate` 和 `lastModifiedDate`。

## 运行/调用流程

### 创建用户流程

典型流程如下：

1. 管理员通过用户 API 提交创建请求。
2. `UserController` 接收 `UserCreationDto`。
3. Controller 将 DTO 转换为 `KomgaUser`：
   - 角色字符串转成 `UserRoles`。
   - library sharing 配置转成 `sharedAllLibraries` 和 `sharedLibrariesIds`。
   - 年龄和标签限制转成 `ContentRestrictions`。
4. `userLifecycle.createUser(...)` 接收 `KomgaUser`。
5. 持久化层 `KomgaUserDao` 将 `KomgaUser` 拆成多张表记录保存。
6. 之后认证或查询用户时，DAO 再把多表记录还原成 `KomgaUser`。

### 查询列表流程

以查询图书、系列、标签、作者等资源为例：

1. 请求进入 Controller。
2. Spring Security 提供当前登录主体，里面有 `principal.user: KomgaUser`。
3. Controller 调用：

   ```kotlin
   principal.user.getAuthorizedLibraryIds(requestedLibraryIds)
   ```

4. `KomgaUser` 根据用户是否有全库权限、是否是管理员、请求是否指定 library，返回最终 library 过滤集合。
5. Repository/DAO 根据这个结果查询数据库。
6. 如果返回值是 `null`，通常表示不需要 library 过滤；如果是集合，则只查集合内的 library。

### 访问单个内容流程

以访问某本书为例：

1. API 拿到当前用户 `KomgaUser` 和目标 book。
2. 先调用：

   ```kotlin
   canAccessLibrary(book.libraryId)
   ```

   如果不允许，直接返回 `403 FORBIDDEN`。

3. 如果用户配置了内容限制：

   ```kotlin
   komgaUser.restrictions.isRestricted
   ```

   则读取对应 series 的 metadata。

4. 调用：

   ```kotlin
   isContentAllowed(ageRating, sharingLabels)
   ```

5. 如果返回 `false`，返回 `403 FORBIDDEN`。
6. 如果通过，继续正常返回内容。

### 内容限制判断流程

`isContentAllowed` 可以按两个阶段理解：

1. allow 阶段

   如果配置了 `ALLOW_ONLY` 年龄限制，内容年龄必须在允许范围内；如果配置了 `labelsAllow`，内容标签需要命中 allow 标签。两者都配置时，命中任意一类 allow 条件即可进入下一阶段。

2. exclude 阶段

   如果配置了 `EXCLUDE` 年龄限制，达到或超过限制年龄的内容会被拒绝；如果内容标签命中 `labelsExclude`，也会被拒绝。

最终必须同时满足：

- 没有被 allow 阶段挡掉。
- 没有命中任何 exclude 规则。

## 小白阅读顺序

1. 先看 `KomgaUser` 构造参数

   从 `email`、`password`、`roles`、`sharedLibrariesIds`、`sharedAllLibraries`、`restrictions` 这些字段开始，先理解一个用户对象里保存了哪些信息。

2. 再看 `UserRoles.kt`

   理解系统里有哪些角色，尤其是 `ADMIN`、`FILE_DOWNLOAD`、`PAGE_STREAMING`。然后回到 `KomgaUser` 看 `isAdmin`。

3. 阅读 library 权限方法

   按顺序看：

   - `canAccessAllLibraries`
   - `canAccessLibrary(libraryId: String)`
   - `canAccessLibrary(library: Library)`
   - `getAuthorizedLibraryIds`

   这部分比内容限制更简单，是理解用户权限的第一层。

4. 阅读 `ContentRestrictions.kt` 和 `AgeRestriction.kt`

   先弄清楚：

   - `ALLOW_ONLY` 是只允许某些内容。
   - `EXCLUDE` 是排除某些内容。
   - `labelsAllow` 和 `labelsExclude` 都会被统一成小写。
   - 同时出现在 allow 和 exclude 的标签会从 allow 中移除。

5. 最后看 `isContentAllowed`

   这个方法逻辑最绕，建议分成“allow 阶段”和“exclude 阶段”阅读。不要一开始就试图一次性读懂整个 `when` 表达式。

6. 对照调用方

   看 `ContentRestrictionChecker.kt`，理解 `canAccessLibrary` 和 `isContentAllowed` 如何变成 API 的 `403 FORBIDDEN`。

   再看 `KomgaUserDao.kt`，理解数据库记录如何还原成这个领域对象。

## 常见误区

1. 误以为 `sharedLibrariesIds` 总是生效

   实际上，如果 `sharedAllLibraries == true` 或用户是 `ADMIN`，`sharedLibrariesIds` 不会限制用户访问范围。此时 `canAccessAllLibraries()` 返回 `true`。

2. 误以为 `getAuthorizedLibraryIds(null)` 返回空集合代表全量访问

   不是。这里的 `null` 有特殊语义：表示“不需要按 library 过滤”。如果返回空集合，反而表示没有可访问的 library。

3. 误以为管理员只靠 `sharedAllLibraries` 获得全库权限

   管理员通过 `isAdmin` 获得全库访问能力。`canAccessAllLibraries()` 是：

   ```kotlin
   sharedAllLibraries || isAdmin
   ```

   所以管理员即使 `sharedAllLibraries` 为 `false`，仍然能访问全部 library。

4. 误以为 `isContentAllowed` 中 allow 规则都必须满足

   当年龄 `ALLOW_ONLY` 和 `labelsAllow` 同时存在时，代码使用的是“或”逻辑。也就是说，年龄允许或标签允许任一满足，就能通过 allow 阶段。之后仍然会继续检查 exclude 规则。

5. 误以为 exclude 只是降低优先级

   exclude 是硬拒绝。只要年龄 exclude 命中，或者标签 exclude 命中，最终都会返回 `false`。

6. 误以为没有 `ageRating` 会自动通过所有年龄规则

   不完全是。对于 `ALLOW_ONLY`，代码要求：

   ```kotlin
   ageRating != null && ageRating <= restrictions.ageRestriction.age
   ```

   所以内容没有 `ageRating` 时，无法通过年龄 allow 条件。

   但对于 `EXCLUDE`，代码要求：

   ```kotlin
   ageRating != null && ageRating >= restrictions.ageRestriction.age
   ```

   所以内容没有 `ageRating` 时，不会命中年龄 exclude。

7. 误以为标签大小写会影响匹配

   不会。`sharingLabels` 和 `ContentRestrictions` 内部标签都会经过 `lowerNotBlank()` 处理。根据当前片段推断，这个工具函数会转小写并过滤空白字符串，依据是它的命名以及在 `ContentRestrictions` 和 `KomgaUser.isContentAllowed` 中的使用方式。

8. 误以为 `toString()` 会打印所有字段

   `KomgaUser` 自定义了 `toString()`，没有包含 `password`。这避免了日志中泄露密码信息。

9. 误以为 `KomgaUser` 只被 REST API 使用

   不是。它还被 OPDS 控制器、查询上下文 `SearchContext`、JOOQ DAO、OAuth2 用户创建逻辑、初始化用户逻辑等使用。它是跨接口层、持久化层和领域层的核心用户模型。
