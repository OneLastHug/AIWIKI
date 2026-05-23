# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/ReadProgress.kt

## 它负责什么

`ReadProgress.kt` 定义的是 Komga 领域层里的“单本书阅读进度”模型：`ReadProgress`。它不是控制器、不是数据库 DAO，也不负责计算进度，而是用一个 Kotlin `data class` 承载“某个用户读到某本书的哪个位置”这件事。

从字段看，它表达的是一个以 `bookId + userId` 为核心身份的阅读状态：

- 哪本书：`bookId`
- 哪个用户：`userId`
- 当前页码：`page`
- 是否读完：`completed`
- 阅读发生时间：`readDate`
- 来自哪个设备：`deviceId`、`deviceName`
- 更精确的 EPUB/Kobo/R2 定位信息：`locator`
- 审计时间：`createdDate`、`lastModifiedDate`

这个文件位于 `org.gotson.komga.domain.model` 包下，说明它属于领域模型层。它的职责是“描述状态”，而不是“执行行为”。真正的业务校验、生成 `ReadProgress`、保存和发送事件，主要在 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`、`SeriesLifecycle.kt` 等服务中完成。

## 关键组成

目标文件内容很短：

```kotlin
data class ReadProgress(
  val bookId: String,
  val userId: String,
  val page: Int,
  val completed: Boolean,
  val readDate: LocalDateTime = LocalDateTime.now(),
  val deviceId: String = "",
  val deviceName: String = "",
  val locator: R2Locator? = null,
  override val createdDate: LocalDateTime = LocalDateTime.now(),
  override val lastModifiedDate: LocalDateTime = createdDate,
) : Auditable
```

### `ReadProgress`

`ReadProgress` 是 Kotlin `data class`，因此天然具备：

- 基于主构造参数的 `equals`
- `hashCode`
- `toString`
- `copy`
- componentN 解构函数

这类模型很适合在领域层、持久化层、事件层之间传递。

### `bookId`

`bookId: String` 表示这条阅读进度属于哪一本书。它不是 `Book` 对象，而是书籍 ID，说明模型尽量保持轻量，避免直接持有完整聚合对象。

在调用方中，`BookLifecycle.markReadProgress` 会用 `book.id` 创建它：

```kotlin
ReadProgress(book.id, user.id, page, page == media.pageCount, locator = locator)
```

### `userId`

`userId: String` 表示进度归属用户。阅读进度通常是用户维度的数据：同一本书，不同用户可以有不同进度。

仓库搜索结果中可以看到多个查询维度都围绕 `bookId` 和 `userId`：

- `ReadProgressRepository.findByBookIdAndUserIdOrNull`
- `findAllByUserId`
- `findAllByBookId`

这说明 `bookId + userId` 基本构成一条阅读进度记录的自然定位方式。

### `page`

`page: Int` 表示当前页码。页码在业务服务里会被校验。

例如 `BookLifecycle.markReadProgress` 中：

```kotlin
require(page in 1..media.pageCount) {
  "Page argument ($page) must be within 1 and book page count (${media.pageCount})"
}
```

所以 `ReadProgress` 本身不阻止非法页码；它假设调用方已经完成校验。这是典型的“领域数据对象 + 服务层校验”风格。

### `completed`

`completed: Boolean` 表示这本书是否读完。

普通标记进度时，`completed` 由当前页是否等于总页数决定：

```kotlin
page == media.pageCount
```

直接标记完成时，则创建：

```kotlin
ReadProgress(bookId, user.id, media.pageCount, true)
```

所以 `completed` 不是从 `page` 动态计算出来的属性，而是持久化到模型里的明确状态。调用方需要保证它和 `page` 的关系合理。

### `readDate`

`readDate: LocalDateTime = LocalDateTime.now()` 表示这次阅读进度更新发生的时间。

它和审计字段不完全一样：

- `readDate`：用户阅读行为的时间
- `createdDate`：记录创建时间
- `lastModifiedDate`：记录最后修改时间

在普通 `markReadProgress` 场景中，如果没有显式传入，`readDate` 默认就是当前时间。  
在同步场景中，例如 `BookLifecycle.markProgression`，会使用外部同步对象的修改时间：

```kotlin
newProgression.modified
  .withZoneSameInstant(ZoneId.systemDefault())
  .toLocalDateTime()
```

这说明 `readDate` 可以代表“客户端实际记录的阅读时间”，不一定总是服务器当前时间。

### `deviceId` 和 `deviceName`

这两个字段默认是空字符串：

```kotlin
val deviceId: String = "",
val deviceName: String = "",
```

在普通 Web/API 标记页码时，它们通常不重要。  
在 Kobo、KOReader 或 R2 progression 同步场景中，它们用于记录进度来自哪个设备。

`BookLifecycle.markProgression` 中会传入：

```kotlin
newProgression.device.id
newProgression.device.name
```

所以这两个字段主要服务跨设备阅读同步。

### `locator`

`locator: R2Locator? = null` 是更精确的阅读位置描述，类型来自同包下的 `R2Locator.kt`。

`R2Locator` 用于表达 publication 中的具体资源和位置，例如：

- `href`：资源 URI
- `type`：资源媒体类型
- `title`：章节或小节标题
- `locations`：位置、progression、totalProgression 等
- `text`：上下文文本
- `koboSpan`：Komga 为 Kobo 映射保留的字段

对于普通图片漫画或 PDF，页码通常足够；对于 EPUB，尤其是 Divina/Kobo/R2 同步，单纯页码可能不够精确，所以需要 `locator` 保存更细的位置。

在 `BookLifecycle.markReadProgress` 中，如果媒体类型是 `MediaProfile.EPUB`，会根据 EPUB extension 的 `positions[page - 1]` 生成 locator；其他类型则是 `null`。

### `createdDate` 和 `lastModifiedDate`

`ReadProgress` 实现了 `Auditable`：

```kotlin
interface Auditable {
  val createdDate: LocalDateTime
  val lastModifiedDate: LocalDateTime
}
```

因此它必须提供：

```kotlin
override val createdDate: LocalDateTime = LocalDateTime.now()
override val lastModifiedDate: LocalDateTime = createdDate
```

默认情况下，创建时间是当前时间，最后修改时间等于创建时间。

根据搜索结果，`ReadProgressDao` 中有 `ReadProgressRecord.toDomain()` 和 `ReadProgress.toQuery(...)`，可以推断数据库读写时会把这些审计字段映射到表字段。这里没有展开 DAO 文件全文，因此关于具体字段名属于“根据当前片段推断”，依据是 `ReadProgressDao.kt` 的类名、导入、`toDomain`、`toQuery`、`save` 等搜索命中。

## 上下游关系

### 上游：谁创建或修改 `ReadProgress`

主要上游是领域服务和接口层。

REST API 入口中可以看到相关控制器：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kosync/KoreaderSyncController.kt`

这些控制器通常不会直接承载完整业务，而是调用领域服务或 repository。

直接创建 `ReadProgress` 的关键服务包括：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`

`BookLifecycle` 中的典型创建路径有三类。

第一类，用户标记读到某页：

```kotlin
ReadProgress(book.id, user.id, page, page == media.pageCount, locator = locator)
```

第二类，用户把一本书标记为已读：

```kotlin
ReadProgress(bookId, user.id, media.pageCount, true)
```

第三类，外部设备同步 R2/Kobo progression：

```kotlin
ReadProgress(
  book.id,
  user.id,
  newProgression.locator.locations!!.position!!,
  newProgression.locator.locations.position == media.pageCount,
  newProgression.modified.withZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime(),
  newProgression.device.id,
  newProgression.device.name,
  newProgression.locator,
)
```

以及 EPUB 分支会经过更复杂的 locator 匹配后创建 `ReadProgress`。

### 下游：谁消费 `ReadProgress`

`ReadProgress` 的下游主要有四类。

第一类是持久化层：

- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/ReadProgressRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadProgressDao.kt`

`ReadProgressRepository` 是领域层接口，`ReadProgressDao` 是 jOOQ 实现。`BookLifecycle` 保存进度时调用：

```kotlin
readProgressRepository.save(progress)
```

第二类是事件系统：

- `komga/src/main/kotlin/org/gotson/komga/domain/model/DomainEvent.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt`

保存或删除进度后会发布事件：

```kotlin
DomainEvent.ReadProgressChanged(progress)
DomainEvent.ReadProgressDeleted(progress)
```

`SseController` 接收到这些事件后，会向对应用户发送 SSE 通知，例如 `ReadProgressChanged`、`ReadProgressDeleted`。

第三类是 API DTO 转换：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/dto/ReadingStateDto.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/BookDto.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/TachiyomiReadProgressDto.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/TachiyomiReadProgressV2Dto.kt`

例如 Kobo 接口中有 `ReadProgress.toDto()`，用于把领域模型转成 Kobo 需要的阅读状态响应。

第四类是搜索、列表和聚合查询：

- `BookDao.kt`
- `BookDtoDao.kt`
- `SeriesDao.kt`
- `SeriesDtoDao.kt`
- `ReadProgressDtoDao.kt`
- `BookSearchHelper.kt`
- `SeriesSearchHelper.kt`

这些地方通过 `RequiredJoin.ReadProgress(userId)` 把当前用户的阅读进度 join 到书籍或系列查询中，让 API 返回书籍列表时可以带上阅读状态，或按阅读状态过滤。

## 运行/调用流程

以“用户在 REST API 中标记一本书读到某页”为例，整体流程可以理解为：

1. 用户调用接口，例如 `BookController.markBookReadProgress`
2. 控制器接收 `ReadProgressUpdateDto`
3. 控制器根据请求内容调用 `BookLifecycle.markReadProgress(...)` 或 `markReadProgressCompleted(...)`
4. `BookLifecycle` 查询媒体信息，拿到 `media.pageCount`、`media.profile` 等
5. 如果是普通页码进度，校验 `page in 1..media.pageCount`
6. 如果是 EPUB，并且需要 locator，则从 EPUB extension 的 `positions` 中取对应位置
7. 创建 `ReadProgress`
8. 调用 `readProgressRepository.save(progress)` 持久化
9. 发布 `DomainEvent.ReadProgressChanged(progress)`
10. SSE 层把变化通知给相关用户
11. 后续 API 查询书籍、系列或 Kobo 状态时，再从 repository/DAO 读出这条进度并转成 DTO

以“外部阅读设备同步进度”为例，流程稍复杂：

1. Kobo/KOReader/R2 相关接口收到客户端同步数据
2. 领域服务调用 `BookLifecycle.markProgression(...)`
3. 如果本地已有进度，会比较 `newProgression.modified` 和已有 `savedProgress.readDate`
4. 如果新进度比已有进度旧，则拒绝，避免旧设备覆盖新进度
5. 根据媒体类型分支处理：
   - `DIVINA`、`PDF`：使用 locator 中的 `position` 作为页码
   - `EPUB`：根据 `href`、`progression`、EPUB positions 匹配真实位置
6. 生成包含 `deviceId`、`deviceName`、`locator`、`readDate` 的 `ReadProgress`
7. 保存并发布 `ReadProgressChanged`

这个流程说明 `ReadProgress` 不是孤立模型，它是阅读同步、页面进度、完成状态、实时通知之间的连接点。

## 小白阅读顺序

建议按下面顺序读，不要一开始就钻进 DAO 或同步细节。

第一步，先读目标文件：

- `komga/src/main/kotlin/org/gotson/komga/domain/model/ReadProgress.kt`

重点理解每个字段代表什么。尤其注意 `page`、`completed`、`readDate`、`locator` 的区别。

第二步，读审计接口：

- `komga/src/main/kotlin/org/gotson/komga/domain/model/Auditable.kt`

这里只定义了 `createdDate` 和 `lastModifiedDate`，帮助理解为什么 `ReadProgress` 末尾要 `: Auditable`。

第三步，读位置模型：

- `komga/src/main/kotlin/org/gotson/komga/domain/model/R2Locator.kt`

如果你只关心漫画图片页码，可以先略读；如果你关心 EPUB、Kobo、跨设备同步，就要认真看 `href`、`type`、`locations.progression`、`locations.totalProgression`、`koboSpan`。

第四步，读创建逻辑：

- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`

重点看这些方法：

- `markReadProgress`
- `markReadProgressCompleted`
- `deleteReadProgress`
- `markProgression`

这里能看到字段是怎么被填充的，也能看到哪些校验不在 `ReadProgress` 里，而是在服务层里。

第五步，读 repository 和 DAO：

- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/ReadProgressRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ReadProgressDao.kt`

目标是理解 `ReadProgress` 怎么保存、怎么按 `bookId` 和 `userId` 查询、怎么从数据库 record 转回领域对象。

第六步，再读接口 DTO：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/dto/ReadingStateDto.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/BookDto.kt`

这一步看的是“领域模型如何暴露给客户端”。同一个 `ReadProgress`，在不同 API 中可能会被转成不同格式。

## 常见误区

### 误区一：以为 `ReadProgress` 会自己校验页码

不会。`ReadProgress` 只是数据类，构造函数没有 `require` 校验。页码范围校验发生在 `BookLifecycle.markReadProgress`、`markProgression` 等服务方法里。

所以不要只看 `ReadProgress(page: Int)` 就以为任何整数都合法。合法性来自调用链上游的业务逻辑。

### 误区二：以为 `completed` 一定可以由 `page == 总页数` 自动推出

在普通页码阅读场景中，确实经常用 `page == media.pageCount` 设置 `completed`。但 `ReadProgress` 里没有 `media.pageCount`，所以它不能自己计算。

另外 EPUB 同步场景中，完成状态可能来自 `totalProgression >= 0.99F` 这类逻辑，而不只是简单页码比较。也就是说，`completed` 是被业务服务计算后写入的结果。

### 误区三：混淆 `readDate`、`createdDate` 和 `lastModifiedDate`

这三个字段语义不同：

- `readDate`：阅读行为或客户端进度的时间
- `createdDate`：记录创建时间
- `lastModifiedDate`：记录最后修改时间

同步场景里尤其要注意：`readDate` 可能来自设备上报的 `modified` 时间，而不是服务器保存时间。

### 误区四：以为 `locator` 总是存在

`locator` 是可空字段：

```kotlin
val locator: R2Locator? = null
```

普通图片漫画或某些页码式阅读进度可能只有 `page`，没有 `locator`。EPUB、Kobo、R2 progression 这类场景才更依赖 locator。

因此使用 `ReadProgress.locator` 时要处理 `null`，不能默认它一定存在。

### 误区五：把 `deviceId` 和 `deviceName` 当成必填设备信息

它们默认是空字符串，不是 nullable：

```kotlin
val deviceId: String = ""
val deviceName: String = ""
```

这表示很多阅读进度并不关心设备来源。只有同步设备进度时，才会填入真实设备信息。

### 误区六：以为这个模型只服务 REST API

不是。搜索结果显示它同时出现在 REST、Kobo、KOReader、SSE、jOOQ DAO、搜索 join、DTO 转换、同步点生命周期等多个位置。

更准确地说，`ReadProgress` 是 Komga 内部统一的阅读进度领域模型。不同接口协议只是把它转换成各自需要的 DTO。

### 误区七：以为删除进度只是数据库删除

在 `BookLifecycle.deleteReadProgress` 中，删除前会先查出已有 `ReadProgress`，删除后发布：

```kotlin
DomainEvent.ReadProgressDeleted(progress)
```

这说明删除阅读进度不只是持久化动作，还会触发事件，让 SSE 或同步机制知道状态发生了变化。
