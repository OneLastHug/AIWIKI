# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/EpubTocEntry.kt

## 它负责什么

`EpubTocEntry.kt` 定义了 Komga 领域层里表示 EPUB 导航条目的最小数据结构：`EpubTocEntry`。

它主要用来承载 EPUB 中三类结构化导航信息：

- `toc`：目录，也就是书籍章节导航。
- `landmarks`：地标，例如封面、正文开始、目录页等关键位置。
- `pageList`：页码列表，例如 EPUB 内部声明的逻辑页码。

这个文件本身不解析 EPUB、不访问数据库、不生成 API 响应；它只是一个领域模型。真正的解析逻辑在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/Nav.kt`、`Ncx.kt`、`Opf.kt`、`EpubExtractor.kt` 中完成，API 转换逻辑在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/WebPubGenerator.kt` 中完成。

## 关键组成

文件内容很短：

```kotlin
package org.gotson.komga.domain.model

data class EpubTocEntry(
  val title: String,
  val href: String?,
  val children: List<EpubTocEntry> = emptyList(),
)
```

### `package org.gotson.komga.domain.model`

它位于 `domain.model` 包下，说明这是领域模型层的一部分。Komga 把媒体、书籍、系列、阅读进度等核心概念都放在这个包附近，例如 `Media.kt`、`MediaExtension.kt`、`Book.kt` 等。

### `data class EpubTocEntry`

`EpubTocEntry` 是 Kotlin `data class`，适合表达不可变数据。Kotlin 会自动生成 `equals`、`hashCode`、`toString`、`copy`、解构等方法。

这对测试和持久化很有用。仓库里的测试会直接构造 `EpubTocEntry(...)` 并比较预期结果，例如 `NavTest.kt`、`NcxTest.kt`、`OpfTest.kt`、`MediaDaoTest.kt` 都有相关使用。

### `title: String`

`title` 是导航条目的显示标题，不能为空。

例如 EPUB 目录中可能出现：

- `Cover`
- `Title Page`
- `Chapter 1`
- `Acknowledgments`
- `iii`
- `107`

在解析 `nav.xhtml` 或 `toc.ncx` 时，代码会从 XML/HTML 元素里取出文本作为 `title`。如果没有标题，解析函数会返回 `null`，该条目不会进入最终列表。

### `href: String?`

`href` 是导航条目指向的 EPUB 内部资源路径，可以为空。

它是可空字段，原因是 EPUB 导航里可能存在“只有标题、不直接链接”的分组节点。例如测试中出现过类似 `EpubTocEntry("An unlinked heading", null)` 的情况。这类节点通常用于目录分组，本身不跳转，但它可以包含 `children`。

解析时，`href` 会经过路径标准化：

- `Nav.kt` 从 EPUB 3 的 `nav` 文档里读取 `<a href="...">`。
- `Ncx.kt` 从 EPUB 2 的 NCX 文档里读取 `<content src="...">`。
- 两者都会用 `URLDecoder.decode(..., Charsets.UTF_8)` 解码 URL。
- 然后通过 `normalizeHref(...)` 把相对路径规范化到 EPUB 包内资源路径。

因此这里的 `href` 不是外部 URL，而是 EPUB 内部资源路径，可能带 fragment，例如 `xhtml/chapter1.xhtml#pg_1`。

### `children: List<EpubTocEntry> = emptyList()`

`children` 表示子目录项，是递归结构。也就是说一个 `EpubTocEntry` 可以包含多个子 `EpubTocEntry`，形成树形目录。

默认值是 `emptyList()`，所以叶子节点可以只写：

```kotlin
EpubTocEntry("Cover", "cover.xhtml")
```

有子节点时可以写：

```kotlin
EpubTocEntry(
  "Part 1",
  "part1.xhtml",
  listOf(
    EpubTocEntry("Chapter 1", "chapter1.xhtml"),
    EpubTocEntry("Chapter 2", "chapter2.xhtml"),
  ),
)
```

这种设计同时适配 EPUB 目录、页码列表和 landmarks。虽然 `pageList` 通常比较扁平，但模型没有限制它必须是一层；如果源 EPUB 提供嵌套结构，也可以表达。

## 上下游关系

### 上游：EPUB 解析模块生成它

`EpubTocEntry` 的主要上游在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub` 目录。

相关文件包括：

- `Nav.kt`
- `Ncx.kt`
- `Opf.kt`
- `EpubExtractor.kt`

#### EPUB 3：`Nav.kt`

`Nav.kt` 处理 EPUB 3 的 `nav` 文档。核心流程是：

1. `EpubPackage.getNavResource()` 从 manifest 中找到带 `nav` property 的资源。
2. 读取该资源内容。
3. `processNav(document, navElement)` 用 Jsoup 解析 XML。
4. 找到对应类型的 `<nav>`，例如 `toc`、`landmarks`、`page-list`。
5. 遍历 `ol > li`。
6. 对每个 `li` 调用 `navLiElementToTocEntry(...)`。
7. 递归生成 `EpubTocEntry` 树。

其中 `navLiElementToTocEntry(...)` 会读取：

- `:root > a, span` 的文本作为 `title`
- `:root > a` 的 `href` 作为链接
- `:root > ol > li` 作为子节点

如果标题存在，就构造：

```kotlin
EpubTocEntry(title, href?.let { normalizeHref(navDir, it) }, children)
```

如果标题不存在，就返回 `null`，上层通过 `mapNotNull` 忽略该节点。

#### EPUB 2：`Ncx.kt`

`Ncx.kt` 处理 EPUB 2 的 NCX 文件。核心流程类似：

1. `EpubPackage.getNcxResource()` 找到 `application/x-dtbncx+xml` 资源，或者 id 是 `toc`、`ncx`、`ncxtoc` 的资源。
2. `processNcx(document, navType)` 用 Jsoup 解析 XML。
3. 根据 `Epub2Nav` 中定义的层级选择器找到导航节点。
4. 递归调用 `ncxElementToTocEntry(...)`。
5. 生成 `EpubTocEntry` 树。

`ncxElementToTocEntry(...)` 读取：

- `navLabel > text` 作为 `title`
- `content` 的 `src` 属性作为 `href`
- 子级 `navPoint` 或对应节点作为 `children`

然后构造同一个领域模型 `EpubTocEntry`。

这说明 `EpubTocEntry` 是 EPUB 2 和 EPUB 3 导航结构之间的统一抽象。上游解析格式不同，但下游拿到的是同一种树形数据。

#### OPF guide：`Opf.kt`

`Opf.kt` 也会生成 `EpubTocEntry`，主要用于 EPUB landmarks 的回退来源。根据当前片段推断，当 EPUB 3 `nav` 中没有有效 landmarks 时，`EpubExtractor.getLandmarks(...)` 会回退到 OPF guide。

依据是 `EpubExtractor.kt` 中：

```kotlin
fun getLandmarks(epub: EpubPackage): List<EpubTocEntry> {
  // Epub 3
  epub.getNavResource()?.let { processNav(it, Epub3Nav.LANDMARKS) }?.let { if (it.isNotEmpty()) return it }

  // Epub 2
  return processOpfGuide(epub.opfDoc, epub.opfDir)
}
```

也就是说，landmarks 既可能来自 EPUB 3 `nav`，也可能来自 EPUB 2/OPF 的 guide。

### 中游：`MediaExtensionEpub` 保存它

`EpubTocEntry` 不直接挂在 `Media` 主体字段上，而是放在 EPUB 专属扩展对象中：

`komga/src/main/kotlin/org/gotson/komga/domain/model/MediaExtension.kt`

其中：

```kotlin
data class MediaExtensionEpub(
  val toc: List<EpubTocEntry> = emptyList(),
  val landmarks: List<EpubTocEntry> = emptyList(),
  val pageList: List<EpubTocEntry> = emptyList(),
  val isFixedLayout: Boolean = false,
  val positions: List<R2Locator> = emptyList(),
) : MediaExtension
```

这说明 Komga 的 `Media` 是通用媒体模型，而 EPUB 特有信息通过 `MediaExtensionEpub` 扩展。`toc`、`landmarks`、`pageList` 都统一使用 `List<EpubTocEntry>`，避免为三种导航信息分别建三套类似模型。

`BookAnalyzer.kt` 中分析 EPUB 时会调用：

- `epubExtractor.getToc(epub)`
- `epubExtractor.getLandmarks(epub)`
- `epubExtractor.getPageList(epub)`

然后把结果放入：

```kotlin
MediaExtensionEpub(
  toc = toc,
  landmarks = landmarks,
  pageList = pageList,
  isFixedLayout = isFixedLayout,
  positions = positions,
)
```

### 下游：WebPub API 转成 `WPLinkDto`

最终对外接口不直接暴露 `EpubTocEntry`，而是在 `WebPubGenerator.kt` 中转换成 Web Publication 格式使用的 `WPLinkDto`。

相关 DTO 位于：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/dto/WepPub.kt`

`WPLinkDto` 包含：

```kotlin
data class WPLinkDto(
  val title: String? = null,
  val rel: String? = null,
  val href: String? = null,
  val type: String? = null,
  ...
  val children: List<WPLinkDto> = emptyList(),
  ...
)
```

`WebPubGenerator.kt` 中会把 EPUB 扩展里的三个列表分别转换：

```kotlin
toc = extension?.toc?.map { it.toWPLinkDto(...) } ?: emptyList()
landmarks = extension?.landmarks?.map { it.toWPLinkDto(...) } ?: emptyList()
pageList = extension?.pageList?.map { it.toWPLinkDto(...) } ?: emptyList()
```

转换函数是递归的：

```kotlin
private fun EpubTocEntry.toWPLinkDto(uriBuilder: UriComponentsBuilder): WPLinkDto =
  WPLinkDto(
    title = title,
    href = href?.let { ... },
    children = children.map { it.toWPLinkDto(uriBuilder) },
  )
```

这里有一个重要细节：`EpubTocEntry.href` 是 EPUB 内部路径，而 `WPLinkDto.href` 是面向 API 客户端的资源 URL。转换时会把路径拼到 `books/{bookId}/resource/` 之下，并保留 fragment。

例如内部路径：

```text
xhtml/chapter1.xhtml#pg_1
```

会被拆成：

- 资源路径：`xhtml/chapter1.xhtml`
- fragment：`pg_1`

再组装成 API 可访问的资源地址，并把 `#pg_1` 拼回末尾。

## 运行/调用流程

完整流程可以按“扫描分析 EPUB -> 存入媒体扩展 -> 生成 WebPub 响应”理解。

1. 书籍被分析时，`BookAnalyzer.analyzeEpub(...)` 打开 EPUB 包。

2. `BookAnalyzer` 调用 `epubExtractor.getToc(epub)` 获取目录。

3. `EpubExtractor.getToc(...)` 优先尝试 EPUB 3：

   ```kotlin
   epub.getNavResource()?.let { processNav(it, Epub3Nav.TOC) }
   ```

   如果结果非空，就直接返回。

4. 如果 EPUB 3 `nav` 没有可用目录，则回退到 EPUB 2 NCX：

   ```kotlin
   epub.getNcxResource()?.let { return processNcx(it, Epub2Nav.TOC) }
   ```

5. 对 `landmarks`，流程类似，但 EPUB 2 回退来源是 OPF guide。

6. 对 `pageList`，流程也是先 EPUB 3 `nav`，再 EPUB 2 NCX。

7. `Nav.kt`、`Ncx.kt` 或 `Opf.kt` 解析源 XML/HTML，把每个导航节点转换为 `EpubTocEntry`。如果节点有子级，会递归放入 `children`。

8. `BookAnalyzer` 把结果写入 `MediaExtensionEpub`：

   ```kotlin
   extension = MediaExtensionEpub(
     toc = toc,
     landmarks = landmarks,
     pageList = pageList,
     ...
   )
   ```

9. 后续生成 WebPub API 响应时，`WebPubGenerator` 读取 `MediaExtensionEpub`。

10. `WebPubGenerator` 把每个 `EpubTocEntry` 递归转换成 `WPLinkDto`，并把 EPUB 内部 `href` 转成客户端可访问的资源 URL。

11. 最终客户端在 WebPub 响应中看到的是 `toc`、`landmarks`、`pageList` 字段，每个字段都是 `WPLinkDto` 树，而不是原始的 `EpubTocEntry`。

## 小白阅读顺序

建议按下面顺序读，不要一开始就钻进 EPUB 规范细节。

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/EpubTocEntry.kt`

   只需要理解三个字段：`title`、`href`、`children`。重点是 `children` 让它变成树形结构。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/MediaExtension.kt`

   看 `MediaExtensionEpub` 如何把 `toc`、`landmarks`、`pageList` 放在同一个 EPUB 扩展模型里。这样能明白 `EpubTocEntry` 不是孤立存在的，而是 EPUB 媒体分析结果的一部分。

3. 接着读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookAnalyzer.kt` 的 `analyzeEpub(...)`

   重点看它如何调用 `epubExtractor.getToc(...)`、`getLandmarks(...)`、`getPageList(...)`，以及异常时如何记录错误并回退为空列表。这样能理解导航数据是在书籍分析阶段产生的。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/EpubExtractor.kt`

   重点看 `getToc`、`getPageList`、`getLandmarks` 三个方法。这里能看出 EPUB 3 和 EPUB 2 的优先级：优先 `nav`，再回退到 `ncx` 或 `opf guide`。

5. 然后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/Nav.kt`

   这是 EPUB 3 导航解析。重点看 `processNav(...)` 和 `navLiElementToTocEntry(...)` 怎么递归构造 `EpubTocEntry`。

6. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/Ncx.kt`

   这是 EPUB 2 NCX 解析。对照 `Nav.kt` 看，会发现虽然源格式不同，但最后都归一成 `EpubTocEntry`。

7. 最后读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/WebPubGenerator.kt`

   重点看 `EpubTocEntry.toWPLinkDto(...)`。这里能看到领域模型如何被转换为 API DTO，以及 `href` 如何从 EPUB 内部路径变成可访问 URL。

## 常见误区

### 误区一：以为 `EpubTocEntry` 只表示目录

它的名字里有 `Toc`，但实际用途不只 `toc`。`MediaExtensionEpub` 里 `toc`、`landmarks`、`pageList` 三个字段都使用 `List<EpubTocEntry>`。

更准确地说，它表示“EPUB 导航条目”，目录只是其中一种用途。

### 误区二：以为 `href` 一定不为空

`href` 是 `String?`，明确允许为空。原因是 EPUB 导航里可能有分组标题或无链接标题，它们本身不跳转，但可以有子节点。

所以消费方处理 `EpubTocEntry` 时，不能直接假设 `href!!`。`WebPubGenerator` 中也是用 `href?.let { ... }` 安全处理。

### 误区三：以为 `children` 只是普通列表，不影响整体结构

`children: List<EpubTocEntry>` 是这个模型最关键的设计点。它让目录支持多级嵌套，例如“附录”下面还有多层子项。

解析代码 `Nav.kt` 和 `Ncx.kt` 都是递归构造它，API 转换 `toWPLinkDto(...)` 也是递归转换它。如果修改这个字段，会影响 EPUB 目录树从解析到接口输出的完整链路。

### 误区四：以为它负责解析 EPUB

`EpubTocEntry.kt` 没有任何解析逻辑，也没有 import。它只是数据结构。

解析职责在 infrastructure 层：

- `Nav.kt` 负责 EPUB 3 `nav`。
- `Ncx.kt` 负责 EPUB 2 NCX。
- `Opf.kt` 负责 OPF guide 相关回退。
- `EpubExtractor.kt` 负责选择解析来源和组织回退策略。

这符合分层设计：领域模型表达数据形状，基础设施层处理具体文件格式。

### 误区五：以为 `href` 是最终 API URL

`EpubTocEntry.href` 是 EPUB 包内部资源路径，不是客户端最终访问 URL。

最终 API URL 在 `WebPubGenerator.kt` 里生成。转换时会把内部路径拼到类似 `books/{bookId}/resource/` 的资源接口下面，并保留 fragment。

因此不要在上游解析阶段把 `href` 变成 HTTP URL，否则会污染领域模型，也会破坏 API 层统一构建链接的逻辑。

### 误区六：以为 EPUB 2 和 EPUB 3 会产生不同模型

EPUB 2 的 NCX 和 EPUB 3 的 nav 源格式不同，但 Komga 会把它们统一转换为 `EpubTocEntry`。

这种统一模型让后续 `BookAnalyzer`、`MediaExtensionEpub`、`WebPubGenerator` 不需要关心导航来源，只要处理同一种树形结构即可。

### 误区七：忽略测试里的结构样例

如果想快速理解边界情况，测试比生产解析代码更直观。相关测试包括：

- `komga/src/test/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/NavTest.kt`
- `komga/src/test/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/NcxTest.kt`
- `komga/src/test/kotlin/org/gotson/komga/infrastructure/mediacontainer/epub/OpfTest.kt`
- `komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main/MediaDaoTest.kt`

这些测试展示了常见情况：空 `href`、多级 `children`、带 fragment 的路径、带空格或特殊字符的路径，以及 `toc`、`landmarks`、`pageList` 的持久化场景。
