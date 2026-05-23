# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/MarkSelectedPreference.kt

## 它负责什么

`MarkSelectedPreference.kt` 定义了一个领域枚举 `MarkSelectedPreference`，用于表达“新增缩略图后，是否应该把它标记为当前选中的封面/海报”。

源码非常短：

```kotlin
package org.gotson.komga.domain.model

enum class MarkSelectedPreference {
  NO,
  YES,
  IF_NONE_OR_GENERATED,
}
```

它位于 `org.gotson.komga.domain.model` 包下，属于领域模型层。它本身不保存图片、不处理文件、不访问数据库，只提供一个语义明确的策略值，交给服务层执行具体逻辑。

在 Komga 中，书籍和系列都可以拥有多个 thumbnail/poster。新增一个缩略图时，系统需要决定：

- 新图是否立即成为 selected thumbnail；
- 如果已有 selected thumbnail，新图是否可以替换它；
- 自动生成图、本地 artwork、用户上传图之间如何保持优先级。

`MarkSelectedPreference` 就是为这个决策提供统一的枚举参数。

## 关键组成

这个文件没有 import，只有一个 `enum class`。三个枚举值分别对应三种选择策略。

`NO`

表示新增缩略图后不要将其标记为 selected。

在 `BookLifecycle.addThumbnailForBook` 和 `SeriesLifecycle.addThumbnailForSeries` 中，`MarkSelectedPreference.NO` 都会被转换为：

```kotlin
false
```

也就是说，缩略图仍然会被插入仓库，但不会成为当前选中的封面。

常见来源包括：

- REST 上传接口中 `selected=false`；
- 本地 artwork 导入时，该 artwork 自身没有被标记为 selected；
- 测试中显式添加非选中缩略图。

`YES`

表示新增缩略图后强制将其设为 selected。

在服务层中，`MarkSelectedPreference.YES` 会被转换为：

```kotlin
true
```

随后调用 repository 的 `markSelected(...)` 方法，把当前新增的 thumbnail 标记为选中项。

主要用于用户主动上传封面并要求选中它，例如：

- `BookController` 上传 book poster 时，如果请求参数 `selected=true`，调用 `MarkSelectedPreference.YES`；
- `SeriesController` 上传 series poster 时，如果请求参数 `selected=true`，调用 `MarkSelectedPreference.YES`。

这表示用户意图优先级最高，服务层不再判断当前是否已有封面。

`IF_NONE_OR_GENERATED`

表示“有条件地设为 selected”。

这是最值得注意的枚举值，因为它不是简单的是/否，而是表达自动流程中的保守替换策略。

在 `BookLifecycle.addThumbnailForBook` 中逻辑是：

```kotlin
val selectedThumbnail = thumbnailBookRepository.findSelectedByBookIdOrNull(thumbnail.bookId)
selectedThumbnail == null || selectedThumbnail.type == ThumbnailBook.Type.GENERATED
```

也就是说，对书籍缩略图来说：

- 如果当前没有 selected thumbnail，则新增图可以成为 selected；
- 如果当前 selected thumbnail 是 `GENERATED` 自动生成图，则新增图也可以替换它；
- 如果当前 selected thumbnail 是用户上传图或其他更明确的封面，则不会替换。

在 `SeriesLifecycle.addThumbnailForSeries` 中逻辑更简单：

```kotlin
thumbnailsSeriesRepository.findSelectedBySeriesIdOrNull(thumbnail.seriesId) == null
```

也就是说，对系列缩略图来说：

- 只有当前没有 selected thumbnail 时，新增图才会成为 selected；
- 如果已经有 selected thumbnail，不会替换。

根据当前片段推断，书籍和系列这里存在差异，是因为 book thumbnail 有明确的 `GENERATED` 类型替换场景，而 series thumbnail 的条件逻辑只关心是否已有 selected 项。

## 上下游关系

上游调用方主要有三类。

第一类是 REST API controller。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt` 中，上传 book poster 时接收请求参数：

```kotlin
@RequestParam("selected") selected: Boolean = true
```

然后将布尔值转换成枚举：

```kotlin
if (selected) MarkSelectedPreference.YES else MarkSelectedPreference.NO
```

也就是说，外部 API 暴露的是简单的 `selected=true/false`，内部领域服务接收的是更有语义的 `MarkSelectedPreference`。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt` 也采用相同模式。上传 series poster 时，如果 `selected=true`，传入 `YES`；否则传入 `NO`。

第二类是自动缩略图生成流程。

`komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt` 中的 `generateThumbnailAndPersist(book: Book)` 会调用：

```kotlin
addThumbnailForBook(..., MarkSelectedPreference.IF_NONE_OR_GENERATED)
```

这说明自动生成 book thumbnail 时，不会无条件覆盖用户选择。它只会在没有封面，或当前封面也是自动生成图时，才把新生成的图设为 selected。

第三类是本地 artwork 导入流程。

`komga/src/main/kotlin/org/gotson/komga/domain/service/LocalArtworkLifecycle.kt` 中，刷新本地 artwork 时会读取 `localArtworkProvider` 返回的 thumbnails：

```kotlin
bookLifecycle.addThumbnailForBook(
  it,
  if (it.selected) MarkSelectedPreference.IF_NONE_OR_GENERATED else MarkSelectedPreference.NO
)
```

series 也类似：

```kotlin
seriesLifecycle.addThumbnailForSeries(
  it,
  if (it.selected) MarkSelectedPreference.IF_NONE_OR_GENERATED else MarkSelectedPreference.NO
)
```

这里的含义是：本地 artwork 文件如果被 provider 识别为 selected 候选，也只是“有条件地选中”，而不是强制覆盖现有用户选择。

下游执行者主要是两个生命周期服务。

`komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`

负责 book thumbnail 的插入、去重、选中、清理和事件发布。它会根据 `MarkSelectedPreference` 计算 `selected` 布尔值，然后：

- 如果 `selected=true`，调用 `thumbnailBookRepository.markSelected(thumbnail)`；
- 如果 `selected=false`，调用 `thumbnailsHouseKeeping(thumbnail.bookId)`；
- 最后发布 `DomainEvent.ThumbnailBookAdded(newThumbnail)`。

`komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`

负责 series thumbnail 的插入、选中和事件发布。它同样根据 `MarkSelectedPreference` 计算 `selected`，如果为 true，则调用：

```kotlin
thumbnailsSeriesRepository.markSelected(thumbnail)
```

然后发布：

```kotlin
DomainEvent.ThumbnailSeriesAdded(newThumbnail)
```

## 运行/调用流程

以用户上传 book poster 为例，流程大致如下。

1. 客户端调用 `BookController` 的上传 poster 接口，并传入图片文件和 `selected` 参数。
2. `BookController` 查找 book，检测上传文件 media type，确认它是图片。
3. controller 构造 `ThumbnailBook`，类型为 `ThumbnailBook.Type.USER_UPLOADED`。
4. controller 根据请求参数转换策略：
   - `selected=true` -> `MarkSelectedPreference.YES`
   - `selected=false` -> `MarkSelectedPreference.NO`
5. `BookLifecycle.addThumbnailForBook` 先插入 thumbnail，但插入时会把 `selected` 临时设为 false。
6. 服务层根据 `MarkSelectedPreference` 决定最终是否选中。
7. 如果应该选中，调用 repository 的 `markSelected(...)`。
8. 构造带有最终 `selected` 状态的 `newThumbnail`。
9. 发布 `DomainEvent.ThumbnailBookAdded(newThumbnail)`。
10. controller 将结果转换为 DTO 返回。

以自动生成 book thumbnail 为例，流程稍有不同。

1. `BookLifecycle.generateThumbnailAndPersist(book)` 调用 `bookAnalyzer.generateThumbnail(...)` 生成 thumbnail。
2. 它调用 `addThumbnailForBook(..., MarkSelectedPreference.IF_NONE_OR_GENERATED)`。
3. `addThumbnailForBook` 插入新的 `GENERATED` thumbnail 前，会先删除同一本书已有的 generated thumbnail，因为注释说明 only one generated thumbnail is allowed。
4. 插入后检查当前 selected thumbnail。
5. 如果当前没有 selected thumbnail，或当前 selected thumbnail 也是 `GENERATED`，新图成为 selected。
6. 如果当前 selected thumbnail 是用户上传图等更明确的选择，新图不会覆盖它。
7. 最后发布 thumbnail added 事件。

以本地 artwork 导入为例：

1. `LocalArtworkLifecycle.refreshLocalArtwork(book)` 读取 library 配置。
2. 如果 `library.importLocalArtwork` 为 true，就从 `LocalArtworkProvider` 获取 book thumbnails。
3. 对每个 thumbnail，如果 provider 标记它 `selected=true`，传入 `IF_NONE_OR_GENERATED`。
4. 如果 provider 标记它 `selected=false`，传入 `NO`。
5. 最终是否选中仍由 `BookLifecycle` 或 `SeriesLifecycle` 判断。

这里可以看到，`MarkSelectedPreference` 的核心价值是把“调用者的意图”传给服务层，而不是让调用者直接操纵数据库里的 selected 状态。

## 小白阅读顺序

建议按下面顺序理解这个文件。

1. 先看 `MarkSelectedPreference.kt`

先确认它只是一个 enum，没有隐藏逻辑。重点记住三个值：

- `NO`：不要选中；
- `YES`：强制选中；
- `IF_NONE_OR_GENERATED`：条件选中。

2. 再看 `BookLifecycle.addThumbnailForBook`

路径是 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`。

这里是理解该枚举最关键的地方。重点看这几段：

- 不同 `ThumbnailBook.Type` 插入前的处理；
- `when (markSelected)` 如何转换成 `selected`；
- `IF_NONE_OR_GENERATED` 对已有 selected thumbnail 的判断；
- `markSelected(...)` 和 `thumbnailsHouseKeeping(...)` 的分支。

读完这里可以明白：枚举值本身只是策略，真正执行策略的是生命周期服务。

3. 再看 `SeriesLifecycle.addThumbnailForSeries`

路径是 `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`。

对比 book 逻辑看，会发现 series 的 `IF_NONE_OR_GENERATED` 只判断“是否已有 selected”，没有检查 `GENERATED` 类型。这个差异能帮助理解：同一个枚举值在不同聚合服务中可以有相近但不完全相同的业务解释。

4. 再看 `BookController` 和 `SeriesController`

路径分别是 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`。

重点看上传 thumbnail/poster 的接口。controller 接收外部布尔参数 `selected`，但不会自己决定数据库如何改，而是转换为 `MarkSelectedPreference.YES` 或 `MarkSelectedPreference.NO` 交给 domain service。

5. 最后看 `LocalArtworkLifecycle`

路径是 `komga/src/main/kotlin/org/gotson/komga/domain/service/LocalArtworkLifecycle.kt`。

这里能理解 `IF_NONE_OR_GENERATED` 的业务场景：自动导入的本地 artwork 可以成为封面候选，但不应该随便覆盖用户已经明确选中的封面。

## 常见误区

误区一：以为 `MarkSelectedPreference` 是 thumbnail 的 selected 字段。

它不是字段值，而是“如何处理 selected 字段”的策略。真正的 selected 状态存在于 `ThumbnailBook`、`ThumbnailSeries` 等模型里，并由 repository 持久化。

误区二：以为 `YES`、`NO`、`IF_NONE_OR_GENERATED` 只是三态布尔。

它们不是普通三态布尔。`IF_NONE_OR_GENERATED` 带有业务判断，需要查询当前已有 selected thumbnail 后才能得出 true 或 false。尤其在 book 场景中，它还会检查当前 selected thumbnail 的类型是否为 `ThumbnailBook.Type.GENERATED`。

误区三：以为 `IF_NONE_OR_GENERATED` 在 book 和 series 中行为完全一样。

不完全一样。

在 book 中：

```kotlin
selectedThumbnail == null || selectedThumbnail.type == ThumbnailBook.Type.GENERATED
```

在 series 中：

```kotlin
findSelectedBySeriesIdOrNull(...) == null
```

也就是说，book 允许新的候选图替换已有 generated 图；series 只在没有 selected 图时选中新增图。

误区四：以为 controller 传入的 `ThumbnailBook(selected = selected)` 会直接决定最终 selected。

在 `BookLifecycle.addThumbnailForBook` 中，插入时会执行：

```kotlin
thumbnail.copy(selected = false)
```

series 也是类似处理。最终是否 selected 由 `MarkSelectedPreference` 经过服务层判断后决定。controller 构造对象时的 selected 值不是最终持久化依据。

误区五：以为自动生成缩略图会覆盖用户上传的封面。

根据 `BookLifecycle.generateThumbnailAndPersist` 的调用方式，自动生成图使用的是 `MarkSelectedPreference.IF_NONE_OR_GENERATED`。这意味着它只会在没有封面或当前封面也是 generated 时选中，不会覆盖用户上传且已选中的封面。

误区六：以为这个 enum 只服务 REST API。

它也服务内部自动流程。调用方包括 REST controller、自动 thumbnail 生成、local artwork 导入以及测试代码。它是领域层对“选中策略”的统一表达，而不只是接口参数转换工具。
