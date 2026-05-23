# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/R2Locator.kt

## 它负责什么

`R2Locator.kt` 定义了 Komga 领域层里的 `R2Locator` 数据模型，用来表达“出版物中的一个精确位置”。这里的 R2 指向 Readium/Web Publication 生态里常见的 Locator 概念：一个 locator 至少要能说明它指向哪一个资源文件，也可以补充资源内位置、整本书进度、上下文文本等信息。

在 Komga 中，它主要承担三个角色：

1. 阅读进度的结构化坐标  
   例如 EPUB 中的某个 XHTML 文件、文件内百分比、整本书百分比，或者 PDF/漫画里的页码。

2. 外部阅读器同步协议的中间表示  
   Kobo、KOReader 等接口会把各自的进度格式转换成 `R2Locator`，再交给领域服务保存。

3. EPUB 分析阶段生成“可匹配位置表”  
   `EpubExtractor` 会为 EPUB 生成一组 `R2Locator` positions，之后保存阅读进度时用用户上报的位置去匹配这些标准位置。

这个文件本身没有业务算法，重点是领域模型的字段设计和序列化行为。

## 关键组成

文件包名是：

```kotlin
package org.gotson.komga.domain.model
```

它只引入了一个外部注解：

```kotlin
import com.fasterxml.jackson.annotation.JsonInclude
```

`R2Locator` 和内部嵌套类都标注了：

```kotlin
@JsonInclude(JsonInclude.Include.NON_EMPTY)
```

这表示 Jackson 序列化成 JSON 时，会省略空值或空集合。比如 `title = null`、`text = null`、`fragments = emptyList()` 通常不会出现在输出 JSON 中。这个行为很重要，因为 locator 会被用于 API 响应、同步数据、数据库中的 JSON 存储，省略空字段可以让数据更贴近协议定义，也减少冗余。

`R2Locator` 是一个 Kotlin `data class`：

```kotlin
data class R2Locator(
  val href: String,
  val type: String,
  val title: String? = null,
  val locations: Location? = null,
  val text: Text? = null,
  val koboSpan: String? = null,
)
```

各字段含义如下：

`href`：定位到的资源 URI。对 EPUB 来说通常是某个内容文件，例如 XHTML 文件名。源码注释强调 `href` 不应该指向资源片段，也就是说不要把 `#fragment` 当作标准定位主体。实际保存进度时，`BookLifecycle` 里也会把 `href` 中的 fragment 去掉再匹配 EPUB 文件。

`type`：资源的媒体类型，例如 `application/xhtml+xml`。对 EPUB 保存进度时，外部上报的 `type` 不一定可信，`BookLifecycle` 会用已经分析出的匹配位置中的真实 `type` 覆盖它。

`title`：这个 locator 所在章节或小节的标题。当前读取到的调用片段里没有看到它作为核心逻辑参与计算，更像是展示或上下文增强字段。

`locations`：资源内或出版物内的位置表达，类型是内部类 `R2Locator.Location`。这是阅读进度逻辑最常用的字段。

`text`：文本上下文，类型是内部类 `R2Locator.Text`。适合高亮、批注、搜索结果等场景，但当前片段里主要看到阅读进度同步，对 `text` 没有明显使用。

`koboSpan`：Komga 自定义字段，用于把 `R2Locator` 和 Kobo/KEPUB 里的 `koboSpan` 对应起来。它不是标准 Locator 的核心字段，而是为了 Kobo 同步和 KEPUB 位置匹配扩展出来的。

内部类 `Location`：

```kotlin
data class Location(
  val fragments: List<String> = emptyList(),
  val progression: Float? = null,
  val position: Int? = null,
  val totalProgression: Float? = null,
)
```

`fragments`：资源内的一个或多个 fragment。它和 `href` 的边界要分清：`href` 指资源本身，fragment 放在 `locations.fragments` 里。

`progression`：资源内部进度，范围按注释是 `0` 到 `1`。例如 EPUB 某个 XHTML 文件内读到 35%，就是 `0.35F`。Kobo 接口里的 `contentSourceProgressPercent / 100` 会转成这个字段。

`position`：出版物中的位置索引。对于 PDF、DIVINA 漫画等页式媒体，保存进度时会直接把它当页码使用；对于 EPUB positions，它是 Komga 生成的位置序号。

`totalProgression`：整本出版物的总进度，范围也是 `0` 到 `1`。Kobo 响应会把它乘以 100 输出为百分比，KOReader 同步也优先使用它表示整体进度。

内部类 `Text`：

```kotlin
data class Text(
  val after: String? = null,
  val before: String? = null,
  val highlight: String? = null,
)
```

`before`、`highlight`、`after` 分别表示定位点前、定位点处、定位点后的文本。根据文件注释，它适合用于 highlight、annotation、search result 这类需要文本上下文的场景。根据当前片段推断，Komga 的阅读进度同步路径并不依赖它，依据是调用方主要读取 `locations`、`href`、`type`、`koboSpan`。

## 上下游关系

上游来源主要有四类。

第一类是外部同步 API。`komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt` 会把 Kobo 上报的 bookmark 转成 `R2Locator`：`href` 来自 Kobo 的 location source，`progression` 来自内容资源内百分比，`totalProgression` 来自整本书百分比，`koboSpan` 来自 Kobo 的 `kobospan` 类型 location value。

第二类是 KOReader 同步接口。`komga/src/main/kotlin/org/gotson/komga/interfaces/api/kosync/KoreaderSyncController.kt` 会根据媒体类型构造 locator：PDF/DIVINA 使用 `locations.position` 表示页码；EPUB 使用 `href` 和 `locations.totalProgression`，并给出默认 `type = "application/xhtml+xml"`，后续由领域服务校正。

第三类是 EPUB 分析器。`komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/EpubExtractor.kt` 会生成 `List<R2Locator>` 作为 EPUB positions。固定布局 EPUB 每页生成一个位置；普通 EPUB 按 Readium 风格大致每 1024 字节生成一个位置，并尝试匹配最近的 `koboSpan`。生成完后还会为每个 locator 计算 `totalProgression`。

第四类是已有阅读进度。`komga/src/main/kotlin/org/gotson/komga/domain/model/ReadProgress.kt` 中 `locator: R2Locator?` 是阅读进度记录的一部分。`komga/src/main/kotlin/org/gotson/komga/domain/model/R2Progression.kt` 又把 `ReadProgress` 转成包含 `modified`、`device`、`locator` 的 `R2Progression`，供同步协议使用。

下游消费主要有这些位置。

`komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt` 是保存阅读进度时的核心消费者。它根据媒体类型解释 `R2Locator`：页式媒体看 `locations.position`；EPUB 看 `href` 和 `locations.progression`，再匹配已分析出的 `extension.positions`。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadProgressDao.kt` 会把 locator 作为 JSON/GZip 形式反序列化回 `R2Locator`，说明这个模型会落库保存。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/dto/ReadingStateDto.kt` 会把保存的 locator 转回 Kobo 需要的 reading state：`totalProgression * 100` 作为整本书百分比，`progression * 100` 作为资源内百分比，`href` 和 `koboSpan` 组成 Kobo location。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/R2Positions.kt` 暴露 `positions: List<R2Locator>`，说明客户端也可以拿到 EPUB 的 R2 positions 列表。

## 运行/调用流程

一个典型的 EPUB 阅读进度保存流程如下。

1. EPUB 被分析时，`EpubExtractor` 为每个可定位位置生成 `R2Locator`。每个 locator 包含 `href`、`type`、`locations.progression`、`locations.position`，如果能识别 KEPUB span，还会包含 `koboSpan`。最后补上 `locations.totalProgression`。

2. 这些 positions 被保存到 EPUB 的媒体扩展信息中，字段形态类似 `MediaExtensionEpub.positions: List<R2Locator>`。后续同步或进度保存都以这批 positions 为标准坐标系。

3. 外部阅读器上报进度。Kobo 通过 `KoboController` 转成 `R2Locator`，KOReader 通过 `KoreaderSyncController` 转成 `R2Locator`。这里的 locator 是“客户端上报坐标”，可能不完整，也可能有不可信字段。

4. `BookLifecycle` 接收 `R2Progression`。其中 `R2Progression.locator` 就是本文件定义的模型。

5. 如果媒体是 `DIVINA` 或 `PDF`，`BookLifecycle` 要求 `newProgression.locator.locations?.position` 必须在 `1..media.pageCount` 范围内，然后直接用它作为 `ReadProgress.page`。是否已读完由 `position == media.pageCount` 判断。

6. 如果媒体是 `EPUB`，`BookLifecycle` 先清理并解码 `href`，检查它必须存在于媒体文件列表中。然后要求 `locations.progression` 必须存在，因为 EPUB 需要资源内进度来匹配 positions。

7. `BookLifecycle` 从 `extension.positions` 里筛选同一个 `href` 的位置。如果固定布局且只有一个位置，就直接匹配；否则优先找 `locations.progression` 完全相等的位置。找不到精确匹配时，会找上一个小于当前 progression 的 position 和下一个大于当前 progression 的 position，并选择前者作为匹配位置。如果无法形成有效前后关系，就认为 progression 非法。

8. 匹配成功后，服务使用匹配位置中的 `totalProgression` 计算普通 `ReadProgress.page`：`media.pageCount * totalProgression` 四舍五入。是否读完则看 `totalProgression >= 0.99F`。

9. 保存 locator 时，`BookLifecycle` 会修正几个字段：`type` 使用匹配位置的 `type`；如果客户端没有传 `koboSpan`，就用匹配位置的 `koboSpan`；`locations.totalProgression` 不信任客户端传入值，而是用匹配位置计算出的标准值覆盖。

10. 对外同步时，Kobo/KOReader 再从保存的 `ReadProgress.locator` 读取 `totalProgression`、`progression`、`href`、`koboSpan`，转成各自协议格式返回。

这个流程说明：`R2Locator` 自身只是数据容器，真正的校验、匹配、修正逻辑在 `BookLifecycle`、`EpubExtractor` 和各接口 Controller 中。

## 小白阅读顺序

建议先读 `R2Locator.kt` 本身，只需要抓住三层结构：`R2Locator` 指向资源，`Location` 表示位置数字，`Text` 表示文本上下文。

第二步读 `komga/src/main/kotlin/org/gotson/komga/domain/model/R2Progression.kt`。它展示 `R2Locator` 如何被包进同步进度对象里，并且能看到 `ReadProgress.toR2Progression()` 在没有 locator 时会回退为 `R2Locator("", "")`。

第三步读 `komga/src/main/kotlin/org/gotson/komga/domain/model/ReadProgress.kt`。这里能理解 Komga 内部最终保存的是普通页码、完成状态、设备信息、时间以及可选的 `locator`。

第四步读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/EpubExtractor.kt` 中生成 positions 的逻辑。重点看 `R2Locator(...)` 是如何被创建的：固定布局 EPUB 一页一个位置，普通 EPUB 按文件大小切分位置，并计算 `progression`、`position`、`totalProgression`、`koboSpan`。

第五步读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt` 中保存 progression 的分支。这里是理解 `position`、`progression`、`totalProgression` 差异的关键。

第六步再看接口适配层：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/kosync/KoreaderSyncController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/dto/ReadingStateDto.kt`。这一步能理解为什么同一个 `R2Locator` 要同时服务 Kobo、KOReader 和 Komga 自己的进度模型。

## 常见误区

误区一：把 `href` 当成完整 URL 或带 fragment 的定位点。  
文件注释明确说 `href` 必须引用 publication 中的资源，不应该指向资源片段。资源内 fragment 应该放到 `locations.fragments`。`BookLifecycle` 保存 EPUB 进度时也会把 `href` 的 `#...` 部分去掉再做文件匹配。

误区二：混淆 `progression` 和 `totalProgression`。  
`progression` 是当前资源内部进度，比如当前 XHTML 文件内读到 40%。`totalProgression` 是整本书进度，比如整本 EPUB 读到 62%。Kobo DTO 中也能看到二者分别映射到 `contentSourceProgressPercent` 和 `progressPercent`。

误区三：认为 `position` 总是页码。  
对 PDF 和 DIVINA 来说，`locations.position` 会被当成页码，且要求在 `1..pageCount`。但对 EPUB positions 来说，`position` 是分析阶段生成的位置序号，不等同于真实纸质页码，也不一定和显示页码一致。

误区四：认为客户端传来的 `type`、`totalProgression` 一定可信。  
`BookLifecycle` 对 EPUB 保存时会用匹配 position 的 `type` 覆盖客户端传入值，也会用服务端计算出的 `totalProgression` 覆盖客户端传入值。源码注释甚至明确提到 Kobo 的 total progression 可能是错的。

误区五：忽略 `koboSpan` 是 Komga 扩展字段。  
`koboSpan` 不是通用 locator 必备字段，而是为了 Kobo/KEPUB 位置映射加入的 Komga specific 字段。没有 `koboSpan` 时，保存 EPUB 进度会尝试从匹配到的标准 position 补上。

误区六：看到 `@JsonInclude(NON_EMPTY)` 后以为字段不存在就是错误。  
很多字段本来就是可选的，例如 `title`、`locations`、`text`、`koboSpan`。序列化时空字段会被省略，这是设计的一部分。真正的必填要求取决于使用场景：保存 PDF/DIVINA 进度需要 `locations.position`，保存 EPUB 进度需要有效 `href` 和 `locations.progression`。

误区七：把 `R2Locator` 当成负责计算进度的类。  
它只是不可变数据结构。进度位置生成在 `EpubExtractor`，保存校验和匹配在 `BookLifecycle`，协议转换在 Kobo/KOReader Controller 和 DTO 中。理解这个文件时，应重点看字段语义和它如何被上下游解释，而不是寻找算法入口。
