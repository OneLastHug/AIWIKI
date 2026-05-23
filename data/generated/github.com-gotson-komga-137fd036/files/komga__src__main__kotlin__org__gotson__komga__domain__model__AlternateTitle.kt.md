# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/AlternateTitle.kt

## 它负责什么

`AlternateTitle.kt` 定义了 Komga 领域模型中的一个小型值对象：`AlternateTitle`。它用来表示“系列的备用标题 / 别名标题 / 其他语言标题”。

源码非常短：

```kotlin
package org.gotson.komga.domain.model

data class AlternateTitle(
  val label: String,
  val title: String,
)
```

它位于 `org.gotson.komga.domain.model` 包下，属于 domain 层模型，不直接负责数据库访问、HTTP 接口、校验或业务流程调度。它只表达一条备用标题记录的核心数据：

- `label`：标题标签，通常用于说明这个备用标题的来源、语言或分类，例如 `fr`、`en`、`original` 等。
- `title`：实际备用标题文本，例如某个系列的法语名、别名、原文名等。

从仓库上下文看，`AlternateTitle` 当前主要挂在 `SeriesMetadata` 上，用来补充 series 级别的元数据，而不是 book 级别的元数据。

## 关键组成

这个文件只有一个 Kotlin `data class`，没有 import、继承、接口实现和自定义方法。

`data class AlternateTitle`

这是 Kotlin 的数据类。使用 `data class` 后，编译器会自动生成一些常用能力：

- `equals()`：按字段值比较两个备用标题是否相等。
- `hashCode()`：按字段生成哈希值。
- `toString()`：输出类似 `AlternateTitle(label=..., title=...)` 的调试字符串。
- `copy()`：复制对象并替换部分字段。
- `component1()`、`component2()`：支持解构声明。

这说明它被设计成“轻量数据载体”，而不是复杂业务对象。

`val label: String`

`label` 是不可变字段。对象创建后不能修改。

需要注意的是，`AlternateTitle` 自身没有做 `trim()`、大小写归一化、BCP47 语言标签校验或非空校验。也就是说，如果直接构造：

```kotlin
AlternateTitle(" fr ", " La Series ")
```

对象内部会保留原始字符串。是否清洗、校验，依赖上游调用者或 API DTO 校验。

`val title: String`

`title` 也是不可变字段，用来保存备用标题正文。

同样，它本身不做空白过滤。REST 更新入口使用的 `AlternateTitleUpdateDto` 对 `label` 和 `title` 加了 `@NotBlank`，但领域对象本身没有硬性限制。

## 上下游关系

`AlternateTitle` 的上游主要有三类：API 更新请求、数据库读取、业务构造。

REST 更新入口中，`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/AlternateTitleUpdateDto.kt` 定义了外部请求使用的更新 DTO：

```kotlin
class AlternateTitleUpdateDto {
  @get:NotBlank
  val label: String? = null

  @get:NotBlank
  val title: String? = null
}
```

这说明客户端提交备用标题时，`label` 和 `title` 都不能为空白。随后在 `SeriesController` 中，会把更新 DTO 转成领域对象：

```kotlin
AlternateTitle(it.label!!, it.title!!)
```

这里使用了 `!!`，说明控制器依赖 Bean Validation 先保证字段存在且非空白。

数据库读取入口在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesMetadataDao.kt`。其中 `findAlternateTitles(seriesId)` 会查询 `SERIES_METADATA_ALTERNATE_TITLE` 表，然后映射为领域对象：

```kotlin
.map { AlternateTitle(it.label, it.title) }
```

也就是说，数据库中的 `LABEL` 和 `TITLE` 字段会直接进入 `AlternateTitle.label`、`AlternateTitle.title`。

`AlternateTitle` 的直接下游主要是 `SeriesMetadata`、DAO 保存逻辑、REST 输出 DTO 和 Web UI 类型。

在 `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesMetadata.kt` 中，它作为系列元数据的一部分存在：

```kotlin
val alternateTitles: List<AlternateTitle> = emptyList()
```

同时 `SeriesMetadata` 还有对应的锁字段：

```kotlin
val alternateTitlesLock: Boolean = false
```

这表示备用标题不仅是元数据字段，也参与 Komga 的元数据锁定机制。根据当前片段推断，锁定字段通常用于防止扫描、刷新或外部元数据覆盖用户手工维护的值，依据是 `SeriesMetadata` 中每个可编辑元数据字段几乎都有对应的 `xxxLock`。

持久化保存时，`SeriesMetadataDao.insertAlternateTitles(metadata)` 会把每个 `AlternateTitle` 写入 `SERIES_METADATA_ALTERNATE_TITLE` 表：

```kotlin
step.bind(metadata.seriesId, it.label, it.title)
```

更新系列元数据时，DAO 会先删除该 series 原有的备用标题记录，再重新批量插入当前 `metadata.alternateTitles`。所以它的更新语义更接近“整体替换列表”，不是单条增删改。

REST 输出时，`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/AlternateTitleDto.kt` 提供了 API DTO：

```kotlin
data class AlternateTitleDto(
  val label: String,
  val title: String,
)

fun AlternateTitle.toDto() = AlternateTitleDto(label, title)
```

这说明 domain 对象不会直接暴露给 API 响应，而是通过 `toDto()` 转成接口层 DTO。

前端侧也有对应类型，例如 `komga-webui/src/types/komga-series.ts` 中存在 `AlternateTitleDto`，说明这个字段会出现在系列相关页面或编辑表单的数据结构里。

## 运行/调用流程

一个典型的读取流程如下：

1. 客户端请求某个 series 的详情或元数据。
2. 后端进入 series 查询相关逻辑。
3. `SeriesMetadataDao.findById(seriesId)` 查询主表 `SERIES_METADATA`。
4. DAO 额外调用 `findAlternateTitles(seriesId)` 查询 `SERIES_METADATA_ALTERNATE_TITLE`。
5. 每条数据库记录被映射成 `AlternateTitle(label, title)`。
6. DAO 调用 `SeriesMetadata(..., alternateTitles = alternateTitles, ...)` 组装完整领域对象。
7. 接口层把 `AlternateTitle` 转成 `AlternateTitleDto`。
8. API 响应返回给前端，前端以 `alternateTitles: AlternateTitleDto[]` 使用。

一个典型的更新流程如下：

1. 客户端提交 series metadata 更新请求，其中可能包含 `alternateTitles`。
2. 请求体中的备用标题先进入 `SeriesMetadataUpdateDto.alternateTitles`。
3. 每个元素使用 `AlternateTitleUpdateDto` 表示，并通过 `@NotBlank` 校验 `label` 和 `title`。
4. `SeriesController` 把 DTO 转成领域对象 `AlternateTitle(it.label!!, it.title!!)`。
5. 控制器或服务层把新的 `alternateTitles` 放进 `SeriesMetadata.copy(...)` 或新建的 `SeriesMetadata`。
6. `SeriesMetadataDao.update(metadata)` 更新主表字段，并删除原有 `SERIES_METADATA_ALTERNATE_TITLE` 记录。
7. `insertAlternateTitles(metadata)` 将当前列表按 `batchSize` 分块批量插入。
8. 后续读取时看到的就是更新后的完整备用标题列表。

需要特别注意：`AlternateTitle` 本身不是流程控制点。它没有方法调用 DAO，也不感知 API。它只是贯穿这些流程的数据结构。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/AlternateTitle.kt`

   先确认它只是一个 `data class`，字段只有 `label` 和 `title`。不要一开始就把它想复杂。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesMetadata.kt`

   重点找：

   ```kotlin
   val alternateTitles: List<AlternateTitle> = emptyList()
   val alternateTitlesLock: Boolean = false
   ```

   这里能看出 `AlternateTitle` 是 series metadata 的组成部分，并且有对应锁字段。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/AlternateTitleDto.kt`

   这里能看到 domain model 到 REST 输出 DTO 的转换：

   ```kotlin
   fun AlternateTitle.toDto() = AlternateTitleDto(label, title)
   ```

4. 再读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/AlternateTitleUpdateDto.kt`

   这里能看到更新请求对 `label`、`title` 的校验要求是 `@NotBlank`。

5. 最后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesMetadataDao.kt`

   重点看三个地方：

   - `findAlternateTitles(seriesId)`：数据库记录如何变成 `AlternateTitle`。
   - `insertAlternateTitles(metadata)`：`AlternateTitle` 如何写回数据库。
   - `update(metadata)`：更新时为什么会先删除旧记录再插入新列表。

读完这几处后，就能理解这个文件虽然小，但它连接了 domain、API、数据库和前端类型。

## 常见误区

误区一：以为 `AlternateTitle` 是“主标题”。

不是。主标题在 `SeriesMetadata.title`，排序标题在 `SeriesMetadata.titleSort`。`AlternateTitle` 表示补充性的备用标题列表，例如别名、翻译名、原文名等。

误区二：以为 `label` 一定是合法语言代码。

从当前代码看，`AlternateTitle.label` 没有经过 `BCP47TagValidator.normalize()`，也没有类似 `SeriesMetadata.language` 的语言标签规范化逻辑。API 只要求它 `@NotBlank`。所以它可以是语言代码，也可以是其他标签。具体语义更多取决于上游 UI 或调用者约定。

误区三：以为 `AlternateTitle` 会自动清理空格。

不会。`SeriesMetadata` 对 `title`、`summary`、`publisher`、`language` 等字段做了 `trim()` 或规范化，但 `AlternateTitle` 是独立 `data class`，没有清洗逻辑。根据当前片段，REST 更新层只保证非空白，不保证存入领域对象前一定去掉前后空格。

误区四：以为它属于 `BookMetadata`。

不是。`BookMetadata.kt` 中没有 `alternateTitles` 字段。当前引用显示它挂在 `SeriesMetadata` 上，表示系列级备用标题。

误区五：以为更新备用标题是逐条 patch。

从 `SeriesMetadataDao.update(metadata)` 看，更新时会删除该 series 的所有旧 `SERIES_METADATA_ALTERNATE_TITLE` 记录，然后把当前列表重新插入。因此它的持久化行为是列表整体替换，而不是按单条记录做增量更新。

误区六：以为 domain model 和 REST DTO 是同一个东西。

不是。`AlternateTitle` 位于 `domain.model`，是领域层对象；`AlternateTitleDto` 和 `AlternateTitleUpdateDto` 位于 `interfaces.api.rest.dto`，是接口层对象。两者字段形状相似，但职责不同：domain model 表示业务概念，DTO 表示 API 输入输出格式。
