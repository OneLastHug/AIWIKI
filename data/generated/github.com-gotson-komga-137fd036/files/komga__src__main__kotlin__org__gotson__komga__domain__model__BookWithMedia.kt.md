# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/BookWithMedia.kt

## 它负责什么

`BookWithMedia` 是一个非常轻量的组合类型，把 `Book` 和 `Media` 绑在一起，方便后续流程一次性传递“书本元数据 + 媒体解析结果”这两个上下文。

根据当前片段推断，它本身不承载业务逻辑，不负责持久化，也不负责计算；它只是一个数据载体。这个文件在 `org.gotson.komga.domain.model` 包下，内容只有一个 `data class`：

```kotlin
data class BookWithMedia(
  val book: Book,
  val media: Media,
)
```

## 关键组成

这个文件没有额外的 import，也没有方法、常量、伴生对象或扩展逻辑，核心只有两部分字段：

`book: Book`  
代表图书本体，来自 `Book.kt`。它包含书名、文件 URL、文件修改时间、文件哈希、编号、`id`、`seriesId`、`libraryId` 等信息。很多下游逻辑会用它来定位实际文件路径，也会用它的 `id` 进行关联。

`media: Media`  
代表该书对应的媒体分析结果，来自 `Media.kt`。它包含 `status`、`mediaType`、`pages`、`files`、`pageCount`、`epubDivinaCompatible` 等字段。很多下游逻辑会用它判断当前书是否可读、分页是否齐全、应该用哪种提取器。

补充一点，`TransientBook.kt` 里有一个扩展函数 `fun TransientBook.toBookWithMedia() = BookWithMedia(book, media)`，说明这个类型经常作为从临时书对象过渡到标准处理对象的中间载体。

## 上下游关系

上游主要有两类来源。

第一类是控制器和生命周期服务直接从仓库或服务层拿到 `Book` 与 `Media` 后手工组装，例如 `CommonBookController.kt`、`KoboController.kt`、`BookLifecycle.kt`、`BookMetadataLifecycle.kt`、`SeriesMetadataLifecycle.kt` 里都能看到 `BookWithMedia(book, media)` 这种写法。

第二类是 `TransientBook`。`TransientBook.kt` 提供了 `toBookWithMedia()`，把临时书对象转成这里使用的标准组合对象。

下游非常广，说明它是项目里一个常见的上下文封装。

在 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt` 里，`BookWithMedia` 被用于生成缩略图、提取封面、读取页内容、读取文件内容、计算页哈希。这里的逻辑会同时依赖 `book.book.path` 和 `book.media` 的状态、页信息、媒体类型。

在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/comicrack/ComicInfoProvider.kt`、`.../epub/EpubMetadataProvider.kt`、`.../barcode/IsbnBarcodeProvider.kt`、`SeriesMetadataFromBookProvider.kt` 中，它作为元数据提取输入，供不同 provider 根据书文件和媒体分析结果生成 `BookMetadataPatch` 或系列元数据。

在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KepubConverter.kt` 和 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookConverter.kt`、`BookPageEditor.kt` 里，它用于文件级处理，比如转换、重新封装、读取 ZIP/EPUB 内部资源。

在控制器层，`CommonBookController.kt` 和 `KoboController.kt` 通过它把请求参数对应到可处理的书对象，再交给分析器或转换器。

## 运行/调用流程

根据当前片段推断，一个典型流程是这样的。

先由控制器或服务拿到 `Book` 和 `Media`。`Book` 通常来自书库记录或目录扫描结果，`Media` 通常来自分析器或媒体仓库。

然后把两者包装成 `BookWithMedia(book, media)`。如果来源是 `TransientBook`，则直接调用 `toBookWithMedia()`。

接着，处理逻辑会根据不同任务读取这个对象里的两个关键维度：

1. `book` 提供文件路径与业务标识。
2. `media` 提供媒体状态、页数、文件列表和媒体格式信息。

在 `BookAnalyzer` 中，这个对象会先被做状态校验，比如 `media.status` 是否为 `READY`。如果未就绪，就会抛 `MediaNotReadyException`。如果页码越界，也会抛 `IndexOutOfBoundsException`。之后再根据 `media.profile` 分派到 PDF、EPUB 或 DIVINA 对应的提取逻辑。

在 metadata provider 里，流程更像“读取文件上下文并生成补丁”：provider 接收 `BookWithMedia`，检查书和媒体信息，再决定是否能从封面、条目、ISBN 或 ComicInfo 中抽取元数据。

所以这个类型本身不做事，但它是很多“读书文件、读媒体分析、生成结果”流程的统一入口。

## 小白阅读顺序

如果第一次读这块代码，建议按这个顺序看。

先看 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookWithMedia.kt`，只需要确认它就是一个两字段组合体。

再看 `komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt` 和 `komga/src/main/kotlin/org/gotson/komga/domain/model/Media.kt`，理解这两个字段各自代表什么。

然后看 `komga/src/main/kotlin/org/gotson/komga/domain/model/TransientBook.kt`，理解 `toBookWithMedia()` 为什么存在。

接着看 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt` 中 `generateThumbnail`、`getPoster`、`getPageContent`、`getFileContent`、`hashPages` 这些方法，能最直观理解它在运行时怎么被消费。

最后再回头看 `CommonBookController.kt`、`BookLifecycle.kt`、`BookMetadataLifecycle.kt`、`KepubConverter.kt` 这类调用方，就能把“控制器/服务层如何组装它”与“分析器/提供器如何使用它”串起来。

## 常见误区

很多人会把 `BookWithMedia` 误认为一个独立业务实体，但它其实不是。它没有自己的持久化表，没有行为方法，也没有状态机。

第二个误区是把它当成 `Book` 的子类或 `Media` 的派生模型。实际上它只是把两个平级对象打包，方便参数传递。`Book` 仍然负责书的基础身份，`Media` 仍然负责分析结果。

第三个误区是以为它一定包含最新、完整的媒体信息。实际上它只是不加限制地承载这两个对象，数据是否完整、是否可用，要看下游逻辑怎么校验，例如 `BookAnalyzer` 会检查 `media.status == READY`。

第四个误区是忽略它在跨层调用中的作用。它虽然代码极短，但在 controller、service、metadata provider、converter 之间被频繁传递，是这条处理链的统一上下文。
