# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/AgeRestriction.kt

## 它负责什么

`AgeRestriction.kt` 定义了 Komga 领域层里的“年龄限制”模型，用来描述某个用户在访问内容时，应该按内容的 `ageRating` 做怎样的过滤。

这个文件本身不执行过滤逻辑，只提供两个领域概念：

- `AgeRestriction`：年龄限制值对象，包含限制年龄值和限制模式。
- `AllowExclude`：限制模式枚举，说明这个年龄值应该被当作“只允许不超过该年龄”还是“排除达到该年龄及以上”。

它位于 `org.gotson.komga.domain.model` 包下，属于核心领域模型。它会被 `ContentRestrictions` 聚合到用户的内容限制配置中，再由 `KomgaUser.isContentAllowed()`、数据库查询辅助逻辑、REST DTO、DAO 持久化层共同使用。

源码很短：

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

可以把它理解成一个二元组：

```text
age + restriction
```

例如：

```text
AgeRestriction(10, ALLOW_ONLY)
```

表示只允许访问年龄分级小于等于 10 的内容。

```text
AgeRestriction(16, EXCLUDE)
```

表示排除年龄分级大于等于 16 的内容。

## 关键组成

### `AgeRestriction`

`AgeRestriction` 是 Kotlin `data class`，有两个字段：

```kotlin
val age: Int
val restriction: AllowExclude
```

`age` 表示年龄阈值。它不是“用户年龄”，而是用于和内容元数据里的年龄分级比较的阈值。

`restriction` 表示限制方式，类型是同文件中的 `AllowExclude` 枚举。

因为它是 `data class`，Kotlin 自动生成：

- `equals()`
- `hashCode()`
- `toString()`
- `copy()`
- 解构函数 `component1()`、`component2()`

这对领域模型很有用：比如 `ContentRestrictions.equals()` 会直接比较 `ageRestriction`，而 `data class` 的值相等语义正好符合这里的需求。

### `AllowExclude`

`AllowExclude` 有两个值：

```kotlin
ALLOW_ONLY
EXCLUDE
```

它不是一个通用的“开关枚举”，而是一个过滤策略枚举。

`ALLOW_ONLY` 的语义是：

```text
只允许 ageRating <= age 的内容
```

在 `KomgaUser.isContentAllowed()` 中，对应逻辑是：

```kotlin
ageRating != null && ageRating <= restrictions.ageRestriction.age
```

也就是说，当用户配置了 `ALLOW_ONLY` 时，没有 `ageRating` 的内容也不会因为年龄规则而自动通过。它必须有年龄分级，并且年龄分级小于等于阈值。

`EXCLUDE` 的语义是：

```text
排除 ageRating >= age 的内容
```

在 `KomgaUser.isContentAllowed()` 中，对应逻辑是：

```kotlin
ageRating != null && ageRating >= restrictions.ageRestriction.age
```

也就是说，达到或超过阈值的内容会被拒绝。

## 上下游关系

### 上游：用户限制配置

`AgeRestriction` 通常不会单独使用，而是作为 `ContentRestrictions` 的一部分出现。

相关文件：

`komga/src/main/kotlin/org/gotson/komga/domain/model/ContentRestrictions.kt`

其中字段是：

```kotlin
val ageRestriction: AgeRestriction? = null
```

这说明年龄限制是可选的。没有配置年龄限制时，`ageRestriction` 为 `null`，用户只可能受标签限制影响，或者完全不受内容限制影响。

`ContentRestrictions` 还包含：

```kotlin
labelsAllow
labelsExclude
```

所以 Komga 的内容限制并不只有年龄维度，还包括共享标签维度。`AgeRestriction` 是其中的年龄过滤部分。

### 中游：用户内容可见性判断

最关键的调用方是：

`komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt`

其中 `KomgaUser.isContentAllowed()` 会读取：

```kotlin
restrictions.ageRestriction
```

并根据 `AllowExclude` 决定内容是否可见。

它接收两个输入：

```kotlin
ageRating: Int? = null
sharingLabels: Set<String> = emptySet()
```

其中 `ageRating` 通常来自 series/book 的元数据年龄分级，`sharingLabels` 来自共享标签。

年龄限制在这里参与两阶段判断：

1. 先判断“允许条件”。
2. 再判断“拒绝条件”。

`ALLOW_ONLY` 属于允许条件：

```text
如果配置为 ALLOW_ONLY，则内容必须满足 ageRating <= age。
```

`EXCLUDE` 属于拒绝条件：

```text
如果配置为 EXCLUDE，则内容只要满足 ageRating >= age，就会被拒绝。
```

### 下游：REST API DTO

REST 层会把领域模型转换成接口返回值。

相关文件：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/UserDto.kt`

其中定义了：

```kotlin
data class AgeRestrictionDto(
  val age: Int,
  val restriction: AllowExclude,
)
```

以及转换函数：

```kotlin
fun AgeRestriction.toDto() = AgeRestrictionDto(age, restriction)
```

用户 DTO 中有：

```kotlin
val ageRestriction: AgeRestrictionDto?
```

这说明 API 返回用户信息时，会把年龄限制作为用户限制配置的一部分返回。

### 下游：REST API 更新输入

相关文件：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/UserUpdateDto.kt`

其中定义了：

```kotlin
data class AgeRestrictionUpdateDto(
  @get:PositiveOrZero
  val age: Int,
  val restriction: AllowExcludeDto,
)
```

这里有一个容易混淆的地方：接口层使用的是 `AllowExcludeDto`，它比领域枚举多一个值：

```kotlin
enum class AllowExcludeDto {
  ALLOW_ONLY,
  EXCLUDE,
  NONE,
}
```

`NONE` 只存在于 DTO 层，用于表达“清空年龄限制”这类 API 更新语义。领域层的 `AllowExclude` 没有 `NONE`，因为真正的领域模型里“不限制”是通过 `ageRestriction = null` 表达的，而不是通过枚举值表达。

`AllowExcludeDto.toDomain()` 只允许：

```kotlin
ALLOW_ONLY -> AllowExclude.ALLOW_ONLY
EXCLUDE -> AllowExclude.EXCLUDE
```

如果是 `NONE`，会抛出 `IllegalArgumentException()`。根据当前片段推断，`UserController` 在调用 `toDomain()` 前会先处理 `NONE`，将其转成 `ageRestriction = null`。

### 下游：数据库持久化

相关文件：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt`

从调用片段可以看到，DAO 会把数据库字段转换回领域对象：

```kotlin
AgeRestriction(
  userRecord.ageRestriction,
  if (userRecord.ageRestrictionAllowOnly) AllowExclude.ALLOW_ONLY else AllowExclude.EXCLUDE
)
```

也会在保存用户时写入：

```kotlin
user.restrictions.ageRestriction?.age
```

以及根据枚举写入布尔字段：

```kotlin
AllowExclude.ALLOW_ONLY
AllowExclude.EXCLUDE
```

根据当前片段推断，数据库里并不是直接存 `ALLOW_ONLY` / `EXCLUDE` 字符串，而是至少拆成两个字段：

- 一个字段保存年龄阈值，例如 `AGE_RESTRICTION`
- 一个字段保存是否为 allow-only，例如 `AGE_RESTRICTION_ALLOW_ONLY`

这样持久化层把数据库结构翻译成领域层更清晰的 `AgeRestriction(age, restriction)`。

### 下游：查询过滤

相关文件：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/ContentRestrictionsSearchHelper.kt`

搜索结果显示它会根据 `AgeRestriction` 生成 SQL 条件。

当限制是 `ALLOW_ONLY` 时，会使用类似条件：

```kotlin
SERIES_METADATA.AGE_RATING.lessOrEqual(restrictions.ageRestriction.age)
```

当限制是 `EXCLUDE` 时，会使用类似条件：

```kotlin
SERIES_METADATA.AGE_RATING.lessThan(restrictions.ageRestriction.age)
```

两者和 `KomgaUser.isContentAllowed()` 的内存判断语义相互对应：

- `ALLOW_ONLY age=10`：允许 `ageRating <= 10`
- `EXCLUDE age=16`：允许 `ageRating < 16`，也就是排除 `ageRating >= 16`

根据当前片段推断，这些查询条件用于在列表接口、搜索接口或集合查询中提前过滤不可见内容，避免先查出全部内容再在内存中过滤。

### 测试覆盖

调用搜索中可以看到多处测试直接使用 `AgeRestriction`：

`komga/src/test/kotlin/org/gotson/komga/domain/model/KomgaUserTest.kt`

`komga/src/test/kotlin/org/gotson/komga/domain/model/ContentRestrictionsTest.kt`

`komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDaoTest.kt`

这些测试覆盖了：

- `ALLOW_ONLY` 的用户内容访问判断
- `EXCLUDE` 的用户内容访问判断
- `ContentRestrictions` 中年龄限制是否被保存
- DAO 持久化和读取后是否还原为正确的 `AgeRestriction`
- REST 接口创建、更新用户限制时的行为

## 运行/调用流程

一个典型流程可以这样理解：

1. 管理员通过 REST API 创建或更新用户限制。

   输入中可能包含：

   ```json
   {
     "ageRestriction": {
       "age": 12,
       "restriction": "ALLOW_ONLY"
     }
   }
   ```

2. REST DTO 接收该输入。

   对应类型是：

   ```kotlin
   AgeRestrictionUpdateDto
   ```

   其中 `age` 要满足 `@PositiveOrZero`，即不能是负数。

3. Controller 将 DTO 转成领域对象。

   根据当前片段和调用搜索结果，类似逻辑是：

   ```kotlin
   AgeRestriction(it.age, it.restriction.toDomain())
   ```

4. 领域对象被放入用户限制配置。

   也就是：

   ```kotlin
   ContentRestrictions(ageRestriction = AgeRestriction(...))
   ```

5. 用户对象持有该限制。

   在 `KomgaUser` 中：

   ```kotlin
   val restrictions: ContentRestrictions
   ```

6. DAO 保存到数据库。

   `KomgaUserDao` 会把 `AgeRestriction.age` 和 `AllowExclude` 分别写入用户相关表字段。

7. 用户访问内容列表或详情时，系统会判断是否允许访问。

   如果走内存判断，核心入口是：

   ```kotlin
   KomgaUser.isContentAllowed(ageRating, sharingLabels)
   ```

   如果走数据库查询过滤，则由 jOOQ 查询辅助逻辑把年龄限制转成 SQL 条件。

8. 判断结果决定内容是否出现在响应中，或者是否允许用户访问。

举例：

```kotlin
AgeRestriction(10, AllowExclude.ALLOW_ONLY)
```

内容 `ageRating = 8`：

```text
8 <= 10，允许
```

内容 `ageRating = 12`：

```text
12 <= 10 不成立，不允许
```

内容 `ageRating = null`：

```text
ALLOW_ONLY 要求 ageRating != null，因此不允许
```

再看：

```kotlin
AgeRestriction(16, AllowExclude.EXCLUDE)
```

内容 `ageRating = 15`：

```text
15 >= 16 不成立，不会被年龄规则拒绝
```

内容 `ageRating = 16`：

```text
16 >= 16 成立，被拒绝
```

内容 `ageRating = 18`：

```text
18 >= 16 成立，被拒绝
```

内容 `ageRating = null`：

```text
ageRating != null 不成立，不会被 EXCLUDE 年龄规则拒绝
```

这里能看出一个重要差异：

- `ALLOW_ONLY` 对没有年龄分级的内容更严格。
- `EXCLUDE` 对没有年龄分级的内容不会按年龄规则拒绝。

## 小白阅读顺序

建议按下面顺序阅读，而不是只看 `AgeRestriction.kt`：

1. 先看 `komga/src/main/kotlin/org/gotson/komga/domain/model/AgeRestriction.kt`

   先记住两个概念：

   ```text
   AgeRestriction = age + restriction
   AllowExclude = ALLOW_ONLY / EXCLUDE
   ```

2. 再看 `komga/src/main/kotlin/org/gotson/komga/domain/model/ContentRestrictions.kt`

   理解年龄限制只是用户内容限制的一部分，和 `labelsAllow`、`labelsExclude` 并列。

3. 再看 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaUser.kt`

   重点看 `isContentAllowed()`。这是理解 `ALLOW_ONLY` 和 `EXCLUDE` 真实语义的关键位置。

4. 然后看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/UserDto.kt`

   理解领域对象如何返回给前端或 API 调用方。

5. 再看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/UserUpdateDto.kt`

   特别注意 `AllowExcludeDto.NONE`。它是 API 更新语义，不是领域模型语义。

6. 最后看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KomgaUserDao.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/ContentRestrictionsSearchHelper.kt`

   理解这个领域模型如何落库，以及如何被转换成数据库查询条件。

如果只是想快速掌握业务含义，优先读：

```text
AgeRestriction.kt -> ContentRestrictions.kt -> KomgaUser.isContentAllowed()
```

这三处足够建立主线。

## 常见误区

### 误区一：把 `age` 理解成用户年龄

`AgeRestriction.age` 更准确地说是“内容年龄分级阈值”，不是用户的真实年龄字段。

它会和内容元数据里的 `ageRating` 比较，例如：

```text
内容 ageRating <= 限制 age
内容 ageRating >= 限制 age
```

所以它不是身份资料里的年龄，也不是生日换算出来的年龄。

### 误区二：以为 `ALLOW_ONLY` 和 `EXCLUDE` 只是反义词

它们确实方向相反，但对边界和空值的处理不完全对称。

`ALLOW_ONLY age=10`：

```text
允许 ageRating <= 10
ageRating = null 不允许
```

`EXCLUDE age=10`：

```text
拒绝 ageRating >= 10
ageRating = null 不会因为年龄规则被拒绝
```

所以不要简单理解成：

```text
ALLOW_ONLY(10) 等价于 not EXCLUDE(10)
```

它们在 `ageRating = null` 时语义不同。

### 误区三：以为领域枚举里有 `NONE`

领域层的 `AllowExclude` 只有：

```kotlin
ALLOW_ONLY
EXCLUDE
```

没有 `NONE`。

`NONE` 出现在 REST 更新 DTO 的 `AllowExcludeDto` 中，用来表达接口调用时“取消年龄限制”。进入领域模型后，这种状态会变成：

```kotlin
ageRestriction = null
```

而不是：

```kotlin
AgeRestriction(age, NONE)
```

### 误区四：以为 `AgeRestriction` 自己会判断是否允许访问

`AgeRestriction.kt` 只是数据定义，没有方法，也没有业务判断。

真正判断内容是否允许访问的是：

```kotlin
KomgaUser.isContentAllowed()
```

真正把限制转成数据库查询条件的是：

```kotlin
ContentRestrictionsSearchHelper
```

真正负责持久化的是：

```kotlin
KomgaUserDao
```

所以阅读时不要在 `AgeRestriction.kt` 里寻找过滤算法，它只是被其他模块消费的领域值对象。

### 误区五：忽略标签限制和年龄限制的组合关系

`AgeRestriction` 只是 `ContentRestrictions` 的一部分。用户是否能看到内容，还可能受到标签限制影响：

```kotlin
labelsAllow
labelsExclude
```

从 `KomgaUser.isContentAllowed()` 的结构看，系统会同时考虑年龄规则和标签规则。允许规则和拒绝规则组合后，才得到最终结果。

因此排查“为什么某个内容不可见”时，不能只看年龄限制，还要看共享标签。

### 误区六：误解边界值

边界是包含的：

`ALLOW_ONLY age=12` 允许：

```text
ageRating <= 12
```

所以 `ageRating = 12` 是允许的。

`EXCLUDE age=16` 拒绝：

```text
ageRating >= 16
```

所以 `ageRating = 16` 是拒绝的。

这点和数据库查询条件也对应：

- `ALLOW_ONLY` 使用 `lessOrEqual`
- `EXCLUDE` 的允许侧等价于 `lessThan`

### 误区七：认为负数年龄可以进入 API

领域模型 `AgeRestriction` 本身没有在构造函数上声明校验注解，但 REST 更新 DTO 的 `AgeRestrictionUpdateDto.age` 有：

```kotlin
@PositiveOrZero
```

这说明通过 API 更新时，年龄值应为 0 或正数。

不过根据当前片段，领域模型自身没有强制校验。如果代码内部直接构造 `AgeRestriction(-1, ...)`，这个文件本身不会阻止。实际项目通常依赖 API DTO 校验、业务服务约束或测试来避免非法值进入。
