# 文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/BookPage.kt`

## 它负责什么

这个文件定义了“书页”这一层最基础的领域模型：`BookPage`。它描述一本书中的单页文件信息，包括文件名、媒体类型、尺寸、文件哈希和文件大小。根据当前片段推断，它是整个书页分析、存储、转换、校验链路里的通用载体，很多服务都直接围绕它传递页面元数据。

这里还有一个针对集合的扩展函数 `restoreHashFrom`，作用是：当页面在转换、编辑后重新生成时，把旧页面里已经存在且非空的 `fileHash` 回填到新页面上，避免因为文件重建而丢失可复用的哈希信息。

## 关键组成

- `open class BookPage`
  - `fileName: String`：页面文件名。
  - `mediaType: String`：页面媒体类型，例如图片格式。
  - `dimension: Dimension?`：页面尺寸，可能为空。
  - `fileHash: String`：页面哈希，默认空字符串。
  - `fileSize: Long?`：页面大小，可能为空。
- `override fun toString()`
  - 自定义字符串输出，方便日志和调试。
- `fun copy(...)`
  - 手写的复制方法，语义上类似 `data class` 的 `copy`，但这里是普通类。
- `fun Collection<BookPage>.restoreHashFrom(restoreFrom: Collection<BookPage>)`
  - 逐页匹配旧页面并回填哈希。
  - 匹配条件是：
    - `fileSize` 相同
    - `mediaType` 相同
    - `fileName` 相同
    - 旧页 `fileHash` 非空
  - 找到后返回 `newPage.copy(fileHash = it.fileHash)`。

补充关系：
- `BookPageNumbered` 继承自 `BookPage`，额外增加 `pageNumber`，说明 `BookPage` 是更通用的基类。
- `Media.pages` 使用的是 `List<BookPage>`，说明它是媒体页面集合的标准元素。

## 上下游关系

上游主要有三类：

- 分析层：`BookAnalyzer`、`EpubExtractor`
  - 它们从压缩包、EPUB、PDF 等来源解析页面，构造 `BookPage`。
- 持久化层：`MediaDao`
  - `MediaPageRecord.toDomain()` 会把数据库记录还原成 `BookPage`。
- 转换/编辑层：`BookConverter`、`BookPageEditor`
  - 这些流程会生成新的页面集合，并调用 `restoreHashFrom` 把旧哈希带过去。

下游主要有：

- `Media` 聚合对象
  - `pages: List<BookPage>` 是媒体的核心组成之一。
- 页面获取和展示链路
  - `BookLifecycle.getBookPage(...)`、`TransientBookLifecycle.getBookPage(...)`、`WebPubGenerator`、`BookController` 等都会间接依赖页面元数据。
- 哈希相关流程
  - 转换或删页后，后续逻辑还会利用 `fileHash` 做重复页识别、页面历史维护等。

## 运行/调用流程

1. 扫描或解析书籍文件时，`BookAnalyzer`、`EpubExtractor` 等组件创建 `BookPage` 列表。
2. 这些页面被封装进 `Media`，作为一本书的页面元信息。
3. 数据落库时，`MediaDao` 把数据库记录反向映射成 `BookPage`。
4. 发生转换或页面编辑时，新的 `Media.pages` 会重新生成。
5. `restoreHashFrom` 根据文件名、类型、大小，把旧页面中可复用的 `fileHash` 回填到新页面里。
6. 更新后的 `Media` 再写回数据库，后续页面获取、缩略图生成、重复页处理继续使用这些信息。

## 小白阅读顺序

1. 先看 `BookPage.kt`，理解字段含义和 `restoreHashFrom` 的匹配策略。
2. 再看 `BookPageNumbered.kt`，确认它如何在基础页模型上增加页码。
3. 接着看 `Media.kt`，理解 `pages` 在媒体聚合里的位置。
4. 然后看 `MediaDao.kt` 的 `toDomain()`，理解数据库如何还原为 `BookPage`。
5. 最后看 `BookConverter.kt` 和 `BookPageEditor.kt` 中的 `restoreHashFrom` 调用，理解这个类型在转换/编辑流程中的实际作用。

## 常见误区

- 把 `BookPage` 当成 `data class`
  - 它不是 `data class`，而是普通 `open class`，所以这里手写了 `copy` 和 `toString`。
- 只看 `fileName` 就认为能唯一识别页面
  - 实际上 `restoreHashFrom` 还会结合 `fileSize` 和 `mediaType`，说明单靠文件名不够稳妥。
- 以为 `fileHash` 总是现成可用
  - 新生成页面时哈希可能缺失，所以才需要从旧页面集合回填。
- 忽略 `BookPageNumbered`
  - 它说明书页有两种常见层次：基础元信息页和带页码的页。
- 把 `dimension` 和 `fileSize` 视为必填
  - 这两个字段都允许为空，说明解析源不同、信息不完整时也要能正常建模。
