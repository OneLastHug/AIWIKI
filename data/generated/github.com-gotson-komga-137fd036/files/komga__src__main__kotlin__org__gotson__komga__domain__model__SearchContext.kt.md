# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/SearchContext.kt

## 它负责什么

`SearchContext.kt` 定义了领域层的 `SearchContext` 类，用来把“当前搜索是谁发起的、能看哪些库、有哪些内容限制”打包成一个统一上下文，传给后续的搜索、分页、统计和查询构造逻辑。

它本身不执行搜索，也不直接访问数据库；它更像一个轻量的权限/过滤条件载体。实际的 SQL 条件生成发生在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt`、`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/ContentRestrictionsSearchHelper.kt` 中。

这个类聚合了三类信息：

- `userId`：当前用户 ID，主要用于读进度、阅读状态等“用户相关”查询。
- `restrictions`：当前用户的内容限制，来自 `ContentRestrictions`，包括年龄限制、允许标签、排除标签。
- `libraryIds`：当前用户被授权访问的库 ID 集合；`null` 表示不需要按库过滤，空集合表示没有任何可访问库。

## 关键组成

`SearchContext` 的定义很短：

```kotlin
class SearchContext private constructor(
  val userId: String?,
  val restrictions: ContentRestrictions,
  val libraryIds: Collection<String>?,
)
```

这里的主构造函数是 `private constructor`，说明外部不能随意传三个字段来构造上下文。外部主要通过公开构造函数或 companion object 工厂方法创建，避免调用方绕过 `KomgaUser` 的授权规则。

公开构造函数是：

```kotlin
constructor(user: KomgaUser?) : this(
  user?.id,
  user?.restrictions ?: ContentRestrictions(),
  user?.getAuthorizedLibraryIds(null)
)
```

它接收一个可空的 `KomgaUser`：

- 如果 `user != null`：
  - `userId` 使用 `user.id`。
  - `restrictions` 使用 `user.restrictions`。
  - `libraryIds` 使用 `user.getAuthorizedLibraryIds(null)` 计算当前用户有权访问的库。
- 如果 `user == null`：
  - `userId` 为 `null`。
  - `restrictions` 使用默认的 `ContentRestrictions()`，也就是没有内容限制。
  - `libraryIds` 为 `null`，表示不按库过滤。

`companion object` 提供两个工厂方法：

```kotlin
fun empty() = SearchContext(null)
```

`empty()` 创建一个没有用户、没有内容限制、没有库过滤的上下文。它常用于后台任务、生命周期服务或系统级操作，例如扫描、删除、维护等不应受某个登录用户权限影响的查询。

```kotlin
fun ofAnonymousUser() = SearchContext("UNUSED", ContentRestrictions(), null)
```

`ofAnonymousUser()` 创建一个“匿名用户式”的上下文。它和 `empty()` 的重要区别是：`userId` 不是 `null`，而是固定字符串 `"UNUSED"`。根据当前片段推断，这个值用于满足某些查询路径“需要有 userId 才能构造读进度相关 join”的要求，但又不代表真实用户。依据是 `BookSearchHelper` 和 `SeriesSearchHelper` 在处理 `SearchCondition.ReadStatus` 时，如果 `context.userId == null` 会记录 warning 并返回 `falseCondition()`；而非空 `userId` 会用于 `RequiredJoin.ReadProgress(context.userId)`。

`SearchContext.kt` 自身没有显式 `import`，因为它依赖的 `KomgaUser`、`ContentRestrictions` 都在同一个包 `org.gotson.komga.domain.model` 下。

## 上下游关系

上游主要是用户模型 `KomgaUser` 和内容限制模型 `ContentRestrictions`。

`KomgaUser` 位于 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt`。它包含：

- `id`
- `roles`
- `sharedLibrariesIds`
- `sharedAllLibraries`
- `restrictions`
- `getAuthorizedLibraryIds(libraryIds: Collection<String>?)`

`SearchContext(user)` 最关键的动作就是调用：

```kotlin
user?.getAuthorizedLibraryIds(null)
```

`KomgaUser.getAuthorizedLibraryIds` 的语义是：

- 如果用户不能访问所有库，且传入了库 ID，则取传入库 ID 与用户授权库 ID 的交集。
- 如果用户不能访问所有库，且没有传入库 ID，则返回用户授权库 ID。
- 如果用户可以访问所有库，且传入了库 ID，则保留传入库 ID。
- 如果用户可以访问所有库，且没有传入库 ID，则返回 `null`，表示无需库过滤。

因为 `SearchContext` 构造时传的是 `null`，所以它表达的是“以当前用户自己的最大授权范围作为默认搜索范围”。

`ContentRestrictions` 位于 `komga/src/main/kotlin/org/gotson/komga/domain/model/ContentRestrictions.kt`。它负责保存：

- `ageRestriction`
- `labelsAllow`
- `labelsExclude`

其中 `labelsAllow` 和 `labelsExclude` 会经过 `lowerNotBlank()` 规范化为小写并去掉空白值；而且 `labelsAllow` 会减去 `labelsExclude`，避免同一个标签既被允许又被排除。

下游主要分三类。

第一类是接口层控制器。REST 和 OPDS 控制器会在处理当前登录用户请求时创建 `SearchContext(principal.user)`，然后传给 repository。例如：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v2/Opds2Controller.kt`

第二类是 repository 接口。它们把 `SearchContext` 作为查询参数的一部分：

- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/BookRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SeriesRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/persistence/BookDtoRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/persistence/SeriesDtoRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SyncPointRepository.kt`

第三类是 jOOQ 查询实现和查询辅助类。真正消费 `SearchContext` 的地方包括：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/ContentRestrictionsSearchHelper.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDao.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesDao.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDtoDao.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesDtoDao.kt`

这些下游代码会把 `SearchContext` 转换成数据库查询条件，例如库过滤、内容限制过滤、阅读状态 join 等。

## 运行/调用流程

一个典型的用户发起查询流程如下：

1. 用户请求 REST 或 OPDS 接口。
2. 控制器从 `principal.user` 取得当前 `KomgaUser`。
3. 控制器创建 `SearchContext(principal.user)`。
4. 控制器把业务搜索条件，例如 `BookSearch` 或 `SeriesSearch`，连同 `SearchContext`、分页参数传给 repository。
5. repository 的 jOOQ 实现创建 `BookSearchHelper(context)` 或 `SeriesSearchHelper(context)`。
6. 查询 Helper 先生成基础上下文条件，再叠加用户显式搜索条件。
7. DAO 使用生成的 jOOQ `Condition` 和 `RequiredJoin` 组装 SQL。
8. 数据库返回已经被权限和内容限制过滤后的结果。

在 `BookSearchHelper` 中，基础条件生成逻辑是：

```kotlin
fun toCondition(): Pair<Condition, Set<RequiredJoin>> {
  val restrictions = toConditionInternal(context.restrictions)
  val authorizedLibraries = toConditionInternal(context.libraryIds)
  return restrictions.first.and(authorizedLibraries.first) to (restrictions.second + authorizedLibraries.second)
}
```

这表示每次图书搜索都会自动叠加两类基础过滤：

- `context.restrictions`：内容限制。
- `context.libraryIds`：授权库限制。

`SeriesSearchHelper` 中也有几乎相同的基础逻辑。因此 `SearchContext` 是图书查询和系列查询的通用上下文。

库权限过滤的语义在 `BookSearchHelper` 和 `SeriesSearchHelper` 中都类似：

```kotlin
if (libraryIds == null) return DSL.noCondition() to emptySet()
if (libraryIds.isEmpty()) return DSL.falseCondition() to emptySet()
```

这段逻辑非常关键：

- `libraryIds == null`：不加库过滤，通常表示用户可访问所有库，或者是系统级查询。
- `libraryIds.isEmpty()`：直接返回 false 条件，表示没有任何可见结果。
- `libraryIds` 有值：转换成多个 `LibraryId == xxx` 条件的 OR 查询。

内容限制过滤由 `ContentRestrictionsSearchHelper` 负责。它会根据 `ContentRestrictions` 生成以下类型的条件：

- `ALLOW_ONLY` 年龄限制：要求 `SERIES_METADATA.AGE_RATING` 不为空且小于等于限制年龄。
- `EXCLUDE` 年龄限制：允许年龄为空，或年龄小于排除阈值。
- `labelsAllow`：要求系列出现在指定 sharing label 的集合中。
- `labelsExclude`：要求系列不出现在指定 sharing label 的集合中。

阅读状态查询还会依赖 `userId`。在 `BookSearchHelper` 中，如果查询 `SearchCondition.ReadStatus` 但 `context.userId == null`，代码会记录 warning 并返回 `DSL.falseCondition()`。如果 `userId` 非空，则会加入 `RequiredJoin.ReadProgress(context.userId)`，用当前用户的阅读进度表判断 `UNREAD`、`READ` 或 `IN_PROGRESS`。

`SeriesSearchHelper` 对系列阅读状态也是同样思路，只是判断依据变成 `READ_PROGRESS_SERIES.READ_COUNT` 和 `SERIES.BOOK_COUNT` 的关系。

系统级调用则常使用 `SearchContext.empty()`。例如生命周期服务、任务发射器、库控制器中的某些内部查询会创建空上下文，避免把某个用户的权限限制带入后台维护任务。

另一个特殊调用是 `SearchContext.ofAnonymousUser()`。`BookDtoDao.findAll(pageable)` 和 `SeriesDtoDao.findAll(pageable)` 使用它作为默认上下文。根据当前片段推断，这类默认查询需要一个非空 `userId` 来避免读状态条件路径直接失败，但该 ID 不对应真实用户，因此取名 `"UNUSED"`。

## 小白阅读顺序

建议按下面顺序阅读，比较容易理解这个文件为什么存在。

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchContext.kt`  
   先掌握三个字段：`userId`、`restrictions`、`libraryIds`。这个文件只有十几行，重点不是代码量，而是它承载的查询上下文语义。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt`  
   重点看 `getAuthorizedLibraryIds`、`canAccessAllLibraries`、`restrictions`。这些决定 `SearchContext(user)` 怎么从用户身上提取权限范围。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/ContentRestrictions.kt`  
   重点看 `labelsAllow`、`labelsExclude` 的标准化，以及 `isRestricted` 的含义。这样能理解为什么 `SearchContext` 只保存一个 `ContentRestrictions` 对象，而不自己处理标签或年龄逻辑。

4. 然后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/ContentRestrictionsSearchHelper.kt`  
   这里能看到内容限制如何从领域模型变成 SQL 条件，尤其是年龄限制和 sharing label 的实际数据库过滤方式。

5. 接着读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/SeriesSearchHelper.kt`  
   重点看 `toCondition()`，它们会把 `SearchContext` 的基础条件和用户搜索条件合并。

6. 最后回到控制器和 repository  
   例如 `BookController`、`SeriesController`、`OpdsController`、`BookRepository`、`SeriesRepository`。从这些调用方可以看到 `SearchContext(principal.user)` 是如何从 API 请求一路传到数据库查询层的。

## 常见误区

第一个误区：以为 `SearchContext.empty()` 表示匿名用户。  
实际上 `empty()` 是 `SearchContext(null)`，表示没有用户 ID、没有内容限制、没有库过滤。它更像系统级空上下文，而不是普通匿名访问上下文。匿名式上下文有单独的 `ofAnonymousUser()`。

第二个误区：以为 `libraryIds == null` 表示没有可访问库。  
在当前查询 Helper 中，`libraryIds == null` 会变成 `DSL.noCondition()`，也就是不加库过滤；真正的“没有任何可访问库”是空集合，会变成 `DSL.falseCondition()`。

第三个误区：以为 `userId` 只用于权限判断。  
库权限主要由 `libraryIds` 表达，内容限制由 `restrictions` 表达。`userId` 的重要用途是阅读进度、阅读状态这类“跟某个用户有关”的查询，例如 `SearchCondition.ReadStatus`。

第四个误区：以为 `SearchContext` 会自己判断内容是否允许。  
`SearchContext` 只是保存 `ContentRestrictions`。单个对象层面的判断在 `KomgaUser.isContentAllowed`；数据库查询层面的过滤在 `ContentRestrictionsSearchHelper`。

第五个误区：以为 `ContentRestrictions()` 一定代表“用户有权限看所有内容”。  
它只代表没有年龄和标签限制；是否能看所有库还要看 `libraryIds`。一个用户可以没有内容限制，但只能访问部分 library。

第六个误区：忽略 `private constructor` 的意图。  
`SearchContext` 不鼓励外部随便拼字段，而是希望通过 `SearchContext(user)`、`empty()`、`ofAnonymousUser()` 这些受控入口创建。这样可以统一复用 `KomgaUser.getAuthorizedLibraryIds(null)` 的授权逻辑，减少调用方各自实现权限过滤时出现偏差。

第七个误区：把 `"UNUSED"` 当成真实用户 ID。  
`ofAnonymousUser()` 中的 `"UNUSED"` 从命名和使用场景看是占位值，不是数据库中的真实用户。根据当前片段推断，它的作用是让需要非空 `userId` 的查询路径能够构造，而不是表达真实身份。
