# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/ContentRestrictions.kt

## 它负责什么

`ContentRestrictions.kt` 定义了领域模型 `ContentRestrictions`，用于描述一个用户在访问内容时受到的限制条件。它不是直接执行数据库查询或权限判断的服务，而是一个承载规则配置的值对象，主要包含三类信息：

1. 年龄限制：`ageRestriction`
2. 允许访问的共享标签集合：`labelsAllow`
3. 排除访问的共享标签集合：`labelsExclude`

这个类的核心职责是把外部传入的限制配置规范化成稳定、可比较、可复用的领域对象。后续用户模型、搜索上下文、jOOQ 查询辅助代码会基于它生成具体判断逻辑或 SQL 条件。

从命名和调用方看，它用于 Komga 的内容共享与访问控制场景：用户可以被配置为只能看某些年龄评级范围内的内容，或者只能看带有某些 sharing labels 的内容，也可以被禁止查看带有某些 sharing labels 的内容。

## 关键组成

目标文件内容很短，结构如下：

```kotlin
class ContentRestrictions(
  val ageRestriction: AgeRestriction? = null,
  labelsAllow: Set<String> = emptySet(),
  labelsExclude: Set<String> = emptySet(),
)
```

### `ageRestriction`

`ageRestriction` 类型来自同目录的 `AgeRestriction.kt`：

```kotlin
data class AgeRestriction(
  val age: Int,
  val restriction: AllowExclude,
)

enum class AllowExclude {
  ALLOW_ONLY,
  EXCLUDE,
}
```

它由两个字段组成：

- `age`：年龄阈值，例如 `10`、`16`
- `restriction`：限制模式，可能是 `ALLOW_ONLY` 或 `EXCLUDE`

根据后续调用方可以看出，两种模式语义不同：

- `ALLOW_ONLY`：只允许访问年龄评级不高于指定值的内容，并且内容必须有年龄评级
- `EXCLUDE`：排除年龄评级大于等于指定值的内容，年龄评级为空的内容仍然可以通过年龄条件

例如在 `KomgaUser.isContentAllowed()` 中：

```kotlin
ageRating != null && ageRating <= restrictions.ageRestriction.age
```

用于 `ALLOW_ONLY`；

```kotlin
ageRating != null && ageRating >= restrictions.ageRestriction.age
```

用于 `EXCLUDE`。

数据库条件里也对应同样逻辑，位于 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/Utils.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/ContentRestrictionsSearchHelper.kt`。

### `labelsAllow`

构造参数中的 `labelsAllow` 不是直接保存，而是经过规范化：

```kotlin
val labelsAllow =
  labelsAllow
    .lowerNotBlank()
    .toSet()
    .minus(labelsExclude.lowerNotBlank().toSet())
```

这里做了几件事：

1. 调用 `lowerNotBlank()`
2. 转成 `Set`
3. 从允许集合里移除排除集合中的标签

`lowerNotBlank()` 定义在 `komga/src/main/kotlin/org/gotson/komga/language/LanguageUtils.kt`：

```kotlin
fun Iterable<String>.lowerNotBlank() = this.map { it.lowercase().trim() }.filter { it.isNotBlank() }
```

因此标签会被统一处理为：

- 小写
- 去掉首尾空白
- 过滤空字符串
- 去重，因为最终转为 `Set`

最关键的一点是：`labelsAllow` 会减去 `labelsExclude`。也就是说，如果同一个标签同时出现在允许列表和排除列表中，最终以排除为准。

例如传入：

```kotlin
labelsAllow = setOf("Action", "Adult")
labelsExclude = setOf("adult")
```

最终结果会接近：

```kotlin
labelsAllow = setOf("action")
labelsExclude = setOf("adult")
```

这里 `Adult` 和 `adult` 会在小写化后被视为同一个标签，排除规则胜出。

### `labelsExclude`

`labelsExclude` 的处理更直接：

```kotlin
val labelsExclude = labelsExclude.lowerNotBlank().toSet()
```

它同样会小写、去空白、过滤空字符串、去重，但不会再被其他集合修正。

这说明 `labelsExclude` 在这个模型中优先级更高。允许列表要避开排除列表，而排除列表保留完整的排除意图。

### `isRestricted`

```kotlin
@delegate:Transient
val isRestricted: Boolean by lazy {
  ageRestriction != null || labelsAllow.isNotEmpty() || labelsExclude.isNotEmpty()
}
```

`isRestricted` 是一个派生属性，用于快速判断当前对象是否真的包含限制条件。

当以下任一条件成立时，它为 `true`：

- 有年龄限制
- `labelsAllow` 非空
- `labelsExclude` 非空

否则它为 `false`。

这里有两个细节：

1. `by lazy` 表示首次访问时才计算，之后缓存结果。
2. `@delegate:Transient` 表示 lazy 委托字段不参与序列化。

注意，`isRestricted` 本身不是构造参数，而是由其他字段推导出来的状态。它不参与 `equals()` 和 `hashCode()` 的显式比较逻辑。

### `toString()`

```kotlin
override fun toString(): String =
  "ContentRestrictions(ageRestriction=$ageRestriction, labelsAllow=$labelsAllow, labelsExclude=$labelsExclude)"
```

它输出三个核心字段，方便日志、调试或测试断言。

### `equals()` 和 `hashCode()`

虽然这个类看起来很像 Kotlin `data class`，但它是普通 `class`，并手写了 `equals()` 和 `hashCode()`：

```kotlin
override fun equals(other: Any?): Boolean {
  if (this === other) return true
  if (other !is ContentRestrictions) return false

  if (ageRestriction != other.ageRestriction) return false
  if (labelsAllow != other.labelsAllow) return false
  if (labelsExclude != other.labelsExclude) return false

  return true
}
```

比较维度只有三个：

- `ageRestriction`
- `labelsAllow`
- `labelsExclude`

这符合它作为值对象的用途：只要三项限制内容相同，就认为两个 `ContentRestrictions` 相等。

它没有把 `isRestricted` 纳入比较，因为 `isRestricted` 是从这三个字段推导出的结果，不需要重复作为身份依据。

为什么这里没有使用 `data class`？根据当前片段推断，原因可能和构造参数规范化有关：构造参数 `labelsAllow`、`labelsExclude` 与实际属性同名但处理逻辑不同，尤其 `labelsAllow` 需要减去规范化后的 `labelsExclude`。手写普通类可以更明确地控制最终属性、`equals()`、`hashCode()` 和 `toString()`。依据是该类没有 `data class`，但显式实现了 data class 通常自动生成的几个方法。

## 上下游关系

### 上游：用户配置与用户模型

`ContentRestrictions` 被 `KomgaUser` 持有：

```kotlin
val restrictions: ContentRestrictions = ContentRestrictions()
```

路径为 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt`。

这说明内容限制是用户维度的配置。每个用户可以有一套自己的访问限制。如果没有指定，默认是：

```kotlin
ContentRestrictions()
```

即：

- 无年龄限制
- 无允许标签限制
- 无排除标签限制

REST 用户接口也会构造它。调用位置在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt`，根据 `rg` 结果可见它在创建或更新用户时会被使用。也就是说，外部 API 请求中的限制字段最终会落到这个领域模型上。

持久化层 `KomgaUserDao` 也会读写它，路径为 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt`。根据当前片段推断，用户限制配置会保存在数据库里，并在读取用户时还原成 `ContentRestrictions`。

### 下游：内存判断

`KomgaUser.isContentAllowed()` 会直接使用 `ContentRestrictions` 判断某个内容是否允许访问：

```kotlin
fun isContentAllowed(
  ageRating: Int? = null,
  sharingLabels: Set<String> = emptySet(),
): Boolean
```

它先把传入的 `sharingLabels` 也做 `lowerNotBlank()` 处理，这和 `ContentRestrictions` 内部的标签规范化保持一致。

判断过程分为两段：

1. 先看是否满足“允许条件”
2. 再看是否命中“排除条件”

允许条件包括：

- 年龄 `ALLOW_ONLY`
- 标签 `labelsAllow`

排除条件包括：

- 年龄 `EXCLUDE`
- 标签 `labelsExclude`

最终返回：

```kotlin
return !ageDenied && !labelDenied
```

也就是说，即使通过了允许条件，只要命中排除条件，仍会被拒绝。

### 下游：搜索上下文

`SearchContext` 持有 `restrictions`：

```kotlin
class SearchContext private constructor(
  val userId: String?,
  val restrictions: ContentRestrictions,
  val libraryIds: Collection<String>?,
)
```

路径为 `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchContext.kt`。

它从 `KomgaUser` 中取出限制：

```kotlin
constructor(user: KomgaUser?) :
  this(user?.id, user?.restrictions ?: ContentRestrictions(), user?.getAuthorizedLibraryIds(null))
```

这说明查询或搜索相关逻辑不会直接依赖完整的 `KomgaUser`，而是通过 `SearchContext` 携带用户 ID、内容限制和可访问 library 范围。

### 下游：数据库查询条件

`ContentRestrictions` 会被转换为 jOOQ `Condition`。

一个转换函数在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/Utils.kt`：

```kotlin
fun ContentRestrictions.toCondition(): Condition
```

另一个类似逻辑在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/ContentRestrictionsSearchHelper.kt`：

```kotlin
protected fun toConditionInternal(restrictions: ContentRestrictions): Pair<Condition, Set<RequiredJoin>>
```

二者核心条件一致：

- `ALLOW_ONLY` 年龄限制会生成 `AGE_RATING is not null and AGE_RATING <= age`
- `EXCLUDE` 年龄限制会生成 `AGE_RATING is null or AGE_RATING < age`
- `labelsAllow` 会要求 series 出现在 `SERIES_METADATA_SHARING` 中并带有允许标签
- `labelsExclude` 会要求 series 不出现在带有排除标签的集合中

查询条件最终结构是：

```kotlin
ageAllowed
  .or(labelAllowed)
  .and(ageDenied.and(labelDenied))
```

可理解为：

1. 先满足允许侧条件：年龄允许或标签允许
2. 再同时满足排除侧条件：年龄未被排除且标签未被排除

当没有某类限制时，对应条件使用 `DSL.noCondition()`，不会实际收窄查询。

`ContentRestrictionsSearchHelper` 还会返回 `RequiredJoin` 集合，告诉调用方是否需要 join `SeriesMetadata` 等表。这说明它服务于更复杂的搜索构造器，比如 `BookSearchHelper`、`SeriesSearchHelper`。

### 下游：仓储接口

多个 repository/DAO 方法接收 `ContentRestrictions` 参数，例如：

- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/ReadListRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SeriesCollectionRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/persistence/BookDtoRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDtoDao.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadListDao.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesCollectionDao.kt`

这表明 `ContentRestrictions` 不只是用户对象上的静态配置，也会在读取书籍、系列、阅读列表、合集等内容时参与过滤。

## 运行/调用流程

一个典型流程可以这样理解：

1. 用户创建或更新时，API 层接收限制配置。
2. `UserController` 将请求数据构造成 `ContentRestrictions`。
3. 构造过程中：
   - `labelsAllow` 被小写、trim、过滤空值、去重
   - `labelsExclude` 被小写、trim、过滤空值、去重
   - `labelsAllow` 中与 `labelsExclude` 冲突的标签被移除
4. `ContentRestrictions` 被保存到 `KomgaUser.restrictions`。
5. 当用户访问内容或发起搜索时，系统从 `KomgaUser` 创建 `SearchContext`。
6. 查询层读取 `SearchContext.restrictions`。
7. jOOQ 辅助函数把限制对象转换成 SQL `Condition`。
8. 数据库查询只返回用户可见的内容。
9. 在某些不走数据库查询的场景中，`KomgaUser.isContentAllowed()` 可以在内存中对单个内容做同等语义的判断。

以标签为例：

```kotlin
ContentRestrictions(
  labelsAllow = setOf("Kids", "Family"),
  labelsExclude = setOf("adult")
)
```

会使用户倾向于只能看到带有 `kids` 或 `family` 共享标签的内容，同时排除带有 `adult` 的内容。

如果传入：

```kotlin
ContentRestrictions(
  labelsAllow = setOf("Adult", "Family"),
  labelsExclude = setOf("adult")
)
```

最终 `labelsAllow` 中的 `adult` 会被移除。这样避免同一个标签既表示允许又表示排除，降低后续查询和判断的歧义。

以年龄为例：

```kotlin
ContentRestrictions(
  ageRestriction = AgeRestriction(12, AllowExclude.ALLOW_ONLY)
)
```

表示只允许年龄评级存在且小于等于 `12` 的内容。

而：

```kotlin
ContentRestrictions(
  ageRestriction = AgeRestriction(16, AllowExclude.EXCLUDE)
)
```

表示排除年龄评级大于等于 `16` 的内容；年龄评级为空的内容不会因为年龄条件被排除。

如果同时存在年龄允许和标签允许，`KomgaUser.isContentAllowed()` 的逻辑是二者满足其一即可通过允许阶段；但排除条件仍然最终生效。数据库条件也体现为 `ageAllowed.or(labelAllowed).and(...)`。

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/ContentRestrictions.kt`

   重点看构造函数和三个属性：`ageRestriction`、`labelsAllow`、`labelsExclude`。这个文件本身不长，先搞清楚“限制对象里有什么”。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/AgeRestriction.kt`

   理解 `AgeRestriction` 和 `AllowExclude`。尤其要区分 `ALLOW_ONLY` 与 `EXCLUDE`，这是后面所有判断的基础。

3. 再看 `komga/src/main/kotlin/org/gotson/komga/language/LanguageUtils.kt`

   找到 `lowerNotBlank()`，理解标签为什么会大小写不敏感、为什么空白字符串会被忽略。

4. 接着读 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt`

   重点看两个地方：

   - `val restrictions: ContentRestrictions = ContentRestrictions()`
   - `fun isContentAllowed(...)`

   这里能看到限制对象如何真正参与用户访问判断。

5. 然后读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchContext.kt`

   这个文件告诉你：搜索时不是把整个用户对象到处传，而是提取出 `restrictions` 和 library 权限范围。

6. 最后读查询层：

   - `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/Utils.kt`
   - `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/ContentRestrictionsSearchHelper.kt`

   重点看 `ContentRestrictions.toCondition()` 和 `toConditionInternal()`。这一步能把领域对象和 SQL 查询过滤联系起来。

如果想看行为是否符合预期，可以再读测试：

- `komga/src/test/kotlin/org/gotson/komga/domain/model/ContentRestrictionsTest.kt`
- `komga/src/test/kotlin/org/gotson/komga/domain/model/KomgaUserTest.kt`

这些测试会比业务代码更直接地展示边界条件，例如空限制、年龄允许、年龄排除、标签允许、标签排除、允许与排除冲突等。

## 常见误区

### 误区一：以为 `labelsAllow` 和 `labelsExclude` 会原样保存

不会。两个集合都会经过 `lowerNotBlank()`，所以大小写和首尾空白不会保留。

例如 `" Action "` 会变成 `"action"`，空字符串或纯空白字符串会被过滤掉。

### 误区二：以为允许标签和排除标签优先级相同

实际不是。`labelsAllow` 会执行：

```kotlin
.minus(labelsExclude.lowerNotBlank().toSet())
```

所以同一个标签同时出现在允许和排除中时，排除优先。最终该标签只会留在 `labelsExclude`。

### 误区三：以为 `ALLOW_ONLY` 和 `EXCLUDE` 是对称的

它们不是简单取反。

`ALLOW_ONLY` 年龄限制要求 `ageRating != null`，并且 `ageRating <= age`。这意味着年龄评级为空的内容不会通过 `ALLOW_ONLY` 年龄条件。

`EXCLUDE` 年龄限制在查询层表现为：

```kotlin
AGE_RATING is null or AGE_RATING < age
```

这意味着年龄评级为空的内容不会因为 `EXCLUDE` 年龄规则被过滤掉。

### 误区四：以为 `ContentRestrictions` 自己会判断内容是否可见

`ContentRestrictions` 本身只保存和规范化限制配置。真正判断内容是否允许访问的是 `KomgaUser.isContentAllowed()`，真正转换为数据库过滤条件的是 jOOQ 辅助函数，例如 `ContentRestrictions.toCondition()` 和 `ContentRestrictionsSearchHelper.toConditionInternal()`。

### 误区五：以为 `isRestricted` 是独立字段

`isRestricted` 是派生属性，不是构造参数，也不是单独存储的业务配置。它只根据 `ageRestriction`、`labelsAllow`、`labelsExclude` 推导当前对象是否包含任何限制。

### 误区六：以为这是普通 DTO

它更像领域值对象。虽然结构简单，但它承担了重要的业务规范化职责：

- 标签大小写统一
- 空标签过滤
- 集合去重
- 允许/排除冲突处理
- 值对象相等性定义

如果把这些逻辑放在 API 层、数据库层或调用方各自处理，就容易出现不同路径下规则不一致的问题。这里集中在 `ContentRestrictions` 中处理，能保证后续内存判断和数据库查询都使用同一套干净数据。
