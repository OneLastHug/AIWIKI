# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/MediaExtension.kt

## 它负责什么

`MediaExtension.kt` 定义了 `Media` 模型的“媒体扩展信息”机制。它本身不描述一本书的通用媒体状态、页数、文件列表等基础信息，而是给不同媒体格式挂载额外结构化数据。

在当前代码片段中，扩展机制主要服务于 EPUB：

- `MediaExtension` 是所有媒体扩展的标记接口。
- `MediaExtensionEpub` 保存 EPUB 专属数据，例如目录、landmarks、page list、固定版式标记、阅读位置索引。
- `ProxyExtension` 是一个轻量代理，只保存扩展类型的类名，用来表示“这个 `Media` 有某种扩展数据，但当前没有把完整扩展内容加载出来”。

它和 `Media.kt` 的关系很直接：`Media` 中有字段 `extension: MediaExtension? = null`，表示一本书的媒体信息可以额外挂载一个扩展对象。

## 关键组成

### `interface MediaExtension`

`MediaExtension` 是一个空接口：

```kotlin
interface MediaExtension
```

它的作用不是提供行为，而是做类型边界。只有实现了这个接口的类，才被认为是合法的媒体扩展。

这类接口常见于领域模型中，用来统一约束“某类可扩展数据”。后续如果支持新的媒体格式，比如某种特殊图片集合、音频书、PDF 专属结构，也可以新增类似 `MediaExtensionXxx : MediaExtension` 的数据类。

### `ProxyExtension`

`ProxyExtension` 实现了 `MediaExtension`，但它不保存真实扩展内容，只保存：

```kotlin
val extensionClassName: String
```

也就是扩展类的完整类名，例如根据当前上下文推断，EPUB 扩展对应的类名会类似：

```text
org.gotson.komga.domain.model.MediaExtensionEpub
```

它的构造函数是 `private constructor`，外部不能直接创建，只能通过伴生对象的 `of` 方法创建：

```kotlin
class ProxyExtension private constructor(
  val extensionClassName: String,
) : MediaExtension
```

这样可以保证创建代理时会做合法性校验。

### `ProxyExtension.of(extensionClass: String?)`

这是 `ProxyExtension` 的工厂方法：

```kotlin
fun of(extensionClass: String?): ProxyExtension? =
  extensionClass?.let {
    val kClass = Class.forName(extensionClass).kotlin
    if (kClass.qualifiedName != MediaExtension::class.qualifiedName && kClass.isSubclassOf(MediaExtension::class))
      ProxyExtension(extensionClass)
    else
      null
  }
```

它做了几件事：

1. 如果传入的 `extensionClass` 是 `null`，直接返回 `null`。
2. 使用 `Class.forName(extensionClass).kotlin` 根据类名反射出 Kotlin `KClass`。
3. 判断这个类不是 `MediaExtension` 接口本身。
4. 判断这个类是否是 `MediaExtension` 的子类。
5. 只有合法时才创建 `ProxyExtension`。

这里导入了两个 Kotlin 反射相关能力：

```kotlin
import kotlin.reflect.KClass
import kotlin.reflect.full.isSubclassOf
```

`isSubclassOf` 是关键，它避免数据库或外部数据里记录了一个不相关的类名后，被错误包装为媒体扩展。

需要注意：`Class.forName(extensionClass)` 如果类名不存在，理论上会抛出异常。目标文件没有捕获异常，说明调用方应当保证传入的是系统已知、可加载的扩展类名。根据 `MediaDao` 的调用片段，类名主要来自媒体表中的 `EXTENSION_CLASS` 字段。

### `proxyForType<T>()`

`ProxyExtension` 提供了一个内联泛型方法：

```kotlin
inline fun <reified T> proxyForType(): Boolean = T::class.qualifiedName == extensionClassName
```

它用于判断当前代理是否代表某个扩展类型，例如 `WebPubGenerator.kt` 中出现了类似逻辑：

```kotlin
media.extension.proxyForType<MediaExtensionEpub>()
```

因为使用了 `reified T`，调用时不需要额外传入 `KClass`，函数内部可以直接拿到 `T::class.qualifiedName`。

### `proxyForType(clazz: KClass<out Any>)`

另一个重载方法接收显式的 `KClass`：

```kotlin
fun proxyForType(clazz: KClass<out Any>): Boolean = clazz.qualifiedName == extensionClassName
```

这个版本适合在运行时已经拿到某个 `KClass` 对象，但无法或不方便使用泛型时调用。

两个 `proxyForType` 本质都是比较类名字符串，而不是比较实例类型。原因是 `ProxyExtension` 本来就不持有真实扩展对象，只知道“真实扩展应该是什么类”。

### `data class MediaExtensionEpub`

`MediaExtensionEpub` 是当前文件中唯一具体的扩展数据类：

```kotlin
data class MediaExtensionEpub(
  val toc: List<EpubTocEntry> = emptyList(),
  val landmarks: List<EpubTocEntry> = emptyList(),
  val pageList: List<EpubTocEntry> = emptyList(),
  val isFixedLayout: Boolean = false,
  val positions: List<R2Locator> = emptyList(),
) : MediaExtension
```

它保存 EPUB 相关的增强信息：

- `toc`：目录结构，类型是 `List<EpubTocEntry>`。
- `landmarks`：EPUB landmarks，通常用于标记封面、目录、正文起点等重要位置。
- `pageList`：EPUB 的页面列表。
- `isFixedLayout`：是否为 fixed layout EPUB。固定版式 EPUB 常见于漫画、绘本、杂志等内容。
- `positions`：阅读位置列表，类型是 `List<R2Locator>`，用于精确定位出版物中的位置。

`EpubTocEntry.kt` 定义了目录节点：

```kotlin
data class EpubTocEntry(
  val title: String,
  val href: String?,
  val children: List<EpubTocEntry> = emptyList(),
)
```

它是递归结构，`children` 可以继续嵌套子目录。

`R2Locator.kt` 定义了定位信息，包含 `href`、`type`、`title`、`locations`、`text`、`koboSpan` 等字段。注释说明它用于保存和共享出版物中的精确位置，可用于阅读进度、书签、高亮、搜索结果、跳转位置等场景。

## 上下游关系

### 上游：扩展数据从哪里来

根据调用点，`MediaExtensionEpub` 的主要生产者是：

```text
komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt
```

`BookAnalyzer.kt` 中导入并构造了 `MediaExtensionEpub`。根据当前片段推断，书籍分析流程在识别和解析 EPUB 文件时，会提取 EPUB 的目录、landmarks、page list、固定版式信息、positions，然后组装成 `MediaExtensionEpub`，最终放进 `Media.extension`。

`Media.kt` 是承载者：

```kotlin
data class Media(
  ...
  val extension: MediaExtension? = null,
  ...
)
```

所以完整关系是：

```text
EPUB 文件分析结果
→ MediaExtensionEpub
→ Media.extension
→ 持久化到数据库
```

### 中游：持久化和懒加载

`MediaDao.kt` 和 `Utils.kt` 是这个文件的重要基础设施调用方。

`Utils.kt` 中有：

```text
deserializeMediaExtension(...)
```

根据 `rg` 结果，它会使用 `ObjectMapper` 和 `Class.forName(extensionClass)` 把存储的扩展数据反序列化成 `MediaExtension`。代码片段显示它读取的是压缩 JSON 数据，返回类型是 `MediaExtension?`。

`MediaDao.kt` 中有几个关键行为：

- `findExtensionByIdOrNull(bookId: String): MediaExtension?` 会按书籍 ID 查出完整扩展对象。
- 插入或更新 `Media` 时，如果发现 `extension` 是 `ProxyExtension`，会记录错误，因为代理不应该被当作真实扩展写回数据库。
- 常规查询 `Media` 时，会通过 `ProxyExtension.of(extensionClass)` 构造代理放进 `Media.extension`。
- 完整扩展内容需要通过 `mediaRepository.findExtensionByIdOrNull(bookId)` 再查。

这说明设计上把扩展数据当作可能较重的数据处理：普通媒体查询只带一个轻量代理，真正需要 EPUB 扩展内容时再单独加载。

### 下游：谁消费 EPUB 扩展

调用点包括：

```text
komga/src/main/kotlin/org/gotson/komga/interfaces/api/WebPubGenerator.kt
komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt
komga/src/main/kotlin/org/gotson/komga/interfaces/api/kosync/KoreaderSyncController.kt
komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt
komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt
komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/KoboDtoDao.kt
```

其中 `WebPubGenerator.kt` 的逻辑很能说明 `ProxyExtension` 的用途：

```kotlin
when (media.extension) {
  is ProxyExtension if media.extension.proxyForType<MediaExtensionEpub>() ->
    mediaRepository.findExtensionByIdOrNull(media.bookId) as? MediaExtensionEpub
  is MediaExtensionEpub ->
    media.extension
}
```

也就是说，下游拿到 `Media` 后会先看 `extension`：

- 如果已经是 `MediaExtensionEpub`，直接使用。
- 如果只是 `ProxyExtension`，但代理类型指向 `MediaExtensionEpub`，就通过仓储按 `bookId` 加载完整扩展。
- 如果不是 EPUB 扩展，就不按 EPUB 扩展处理。

`KoboController.kt`、`KoreaderSyncController.kt`、`BookController.kt` 等 API 层也会通过：

```kotlin
mediaRepository.findExtensionByIdOrNull(book.id) as? MediaExtensionEpub
```

读取 EPUB 扩展。这说明这些接口需要 EPUB 的结构化阅读信息，可能用于目录、阅读位置、Kobo/KOReader 同步、WebPub 输出等功能。

## 运行/调用流程

一个典型流程可以按下面理解：

1. 扫描或分析一本书时，`BookAnalyzer.kt` 解析媒体文件。
2. 如果文件是 EPUB，分析器提取 EPUB 专属信息。
3. 分析器创建 `MediaExtensionEpub`，其中包含 `toc`、`landmarks`、`pageList`、`isFixedLayout`、`positions`。
4. `MediaExtensionEpub` 被放入 `Media.extension`。
5. `MediaDao.kt` 保存 `Media` 时，把扩展类名和扩展内容分别写入数据库字段。根据当前片段推断，扩展内容会通过 `ObjectMapper` 序列化为 JSON 并 gzip 压缩保存。
6. 后续普通查询 `Media` 时，DAO 不一定加载完整扩展内容，而是根据数据库里的扩展类名创建 `ProxyExtension`。
7. API 或服务层如果需要 EPUB 扩展详情，会判断 `Media.extension`：
   - 如果是 `MediaExtensionEpub`，直接用。
   - 如果是 `ProxyExtension` 且 `proxyForType<MediaExtensionEpub>()` 为 `true`，调用 `mediaRepository.findExtensionByIdOrNull(media.bookId)` 加载完整扩展。
8. 完整扩展被用于 WebPub 生成、Kobo 接口、KOReader 同步、REST 接口响应或生命周期处理。

这个设计的重点是：`Media.extension` 既可能是真实数据，也可能是代理。调用方不能只靠 `as? MediaExtensionEpub` 处理所有情况，如果拿到的是 `ProxyExtension`，需要再走仓储加载。

## 小白阅读顺序

建议按这个顺序读：

1. 先读 `MediaExtension.kt`
   
   目标是搞清楚三个概念：`MediaExtension`、`ProxyExtension`、`MediaExtensionEpub`。这个文件很短，是入口。

2. 再读 `Media.kt`
   
   看 `Media` 如何通过 `extension: MediaExtension?` 挂载扩展数据。注意 `Media` 自身仍然是媒体通用信息模型，扩展字段只是补充。

3. 再读 `EpubTocEntry.kt`
   
   理解 `toc`、`landmarks`、`pageList` 中每个节点是什么结构。重点看 `children`，它说明 EPUB 目录可以嵌套。

4. 再读 `R2Locator.kt`
   
   理解 `positions` 是怎么描述阅读位置的。这里的注释比较完整，适合了解 locator 的用途。

5. 接着读 `BookAnalyzer.kt`
   
   找 `MediaExtensionEpub(` 的构造位置，看 EPUB 文件分析时哪些数据被填进去。

6. 再读 `MediaDao.kt` 和 `Utils.kt`
   
   重点看扩展数据如何保存、如何反序列化、什么时候只返回 `ProxyExtension`。

7. 最后读下游调用方
   
   可以看 `WebPubGenerator.kt`，因为它同时处理了真实 `MediaExtensionEpub` 和 `ProxyExtension` 两种情况。再根据兴趣看 `KoboController.kt`、`KoreaderSyncController.kt`、`BookController.kt`。

## 常见误区

### 误区一：以为 `MediaExtension` 有业务方法

`MediaExtension` 是空接口，不提供行为。它主要用于类型归类和持久化反序列化边界。真正的数据字段在具体实现类里，比如 `MediaExtensionEpub`。

### 误区二：以为 `ProxyExtension` 是真实扩展数据

`ProxyExtension` 不是 EPUB 扩展详情，它只是一个“类型占位符”。它只有 `extensionClassName`，没有 `toc`、`positions` 等内容。

如果代码需要 EPUB 的目录或阅读位置，不能从 `ProxyExtension` 里取，而应该调用：

```kotlin
mediaRepository.findExtensionByIdOrNull(bookId) as? MediaExtensionEpub
```

### 误区三：以为 `Media.extension as? MediaExtensionEpub` 总是够用

不一定。普通查询返回的 `Media.extension` 可能是 `ProxyExtension`。如果只写：

```kotlin
media.extension as? MediaExtensionEpub
```

在代理场景下会得到 `null`，即使数据库里实际存在 EPUB 扩展内容。

更稳妥的模式是参考 `WebPubGenerator.kt`：

```kotlin
when (media.extension) {
  is ProxyExtension -> 判断代理类型后再加载完整扩展
  is MediaExtensionEpub -> 直接使用
}
```

### 误区四：以为 `ProxyExtension.of` 只是简单包装字符串

它不是无条件包装。它会反射加载类，并验证这个类是 `MediaExtension` 的子类，同时排除 `MediaExtension` 接口本身。这个校验保证代理只代表合法扩展类型。

### 误区五：忽略 `Class.forName` 的风险

`ProxyExtension.of` 使用 `Class.forName(extensionClass)`。如果数据库里的类名错误、类被重命名、包名变化，可能导致类加载失败。目标文件没有捕获异常，说明这里依赖持久化数据和代码版本保持一致。

### 误区六：把 `toc`、`landmarks`、`pageList` 当成同一种东西

它们都用 `EpubTocEntry` 表示，但语义不同：

- `toc` 是目录。
- `landmarks` 是关键结构位置。
- `pageList` 是页面列表。

相同的数据结构不代表相同业务含义。下游 API 或阅读器集成可能会分别使用它们。

### 误区七：认为 `positions` 只是页码

`positions` 的类型是 `R2Locator`，它比普通页码丰富得多。它可以包含资源 `href`、资源类型、章节标题、片段、局部进度、全书进度、文本上下文，以及 Komga 专用的 `koboSpan`。因此它更接近“可共享、可跳转的阅读定位对象”，不是简单整数页码。
