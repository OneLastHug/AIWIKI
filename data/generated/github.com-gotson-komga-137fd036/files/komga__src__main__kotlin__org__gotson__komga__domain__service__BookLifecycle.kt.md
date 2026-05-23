# 文件：`komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt`

## 它负责什么

`BookLifecycle` 是 Komga 里“书籍生命周期”的业务编排服务。它不是单纯读写数据库，也不是单纯处理图片，而是把一本 `Book` 从“分析、散列、生成缩略图、读取页内容、记录阅读进度、删除文件/记录”这一整套动作串起来。

根据当前片段推断，它的职责可以概括为三层：

1. **书籍内容处理**  
   调用 `BookAnalyzer` 分析书籍、取页、生成封面、计算页面 hash。
2. **书籍状态持久化**  
   通过 `BookRepository`、`MediaRepository`、`ThumbnailBookRepository`、`ReadProgressRepository` 等把分析结果、缩略图、阅读进度等保存下来。
3. **生命周期收尾动作**  
   删除书籍记录、删除磁盘文件、清理关联数据，并发布 `DomainEvent`、`HistoricalEvent` 通知系统其他部分。

它的定位很明确：**是书籍相关业务流程的中心协调器**，不是底层算法实现者。图片转换交给 `ImageConverter`，哈希交给 `Hasher` / `KoreaderHasher`，书籍结构分析交给 `BookAnalyzer`。

## 关键组成

### 1. 注入依赖

这个类依赖很多仓储和基础设施对象，说明它负责跨多个领域对象的编排：

- `BookRepository`：书籍主记录的增删改查
- `MediaRepository`：分析后的媒体信息，如页数、格式、EPUB 扩展信息
- `BookMetadataRepository`：书籍元数据
- `ReadProgressRepository`：阅读进度
- `ThumbnailBookRepository`：书籍缩略图
- `ReadListRepository`：阅读列表中的关联书籍
- `LibraryRepository`：读取库级配置，例如 `analyzeDimensions`、`hashFiles`、`hashKoreader`、`hashPages`
- `BookAnalyzer`：分析书籍、生成缩略图、取页、页 hash
- `ImageConverter`：缩放和格式转换
- `ApplicationEventPublisher`：发布领域事件
- `TransactionTemplate`：把多表更新包在事务里
- `Hasher`、`KoreaderHasher`：普通 hash 和 Koreader hash
- `HistoricalEventRepository`：记录历史事件
- `KomgaSettingsProvider`：系统设置，主要用于缩略图再生成阈值
- `@Qualifier("pdfImageType") ImageType`：PDF 页面的输出类型

### 2. 核心方法群

#### 分析与持久化
- `analyzeAndPersist(book)`  
  分析书籍，更新 `Media`，必要时调整阅读进度，并决定后续任务是否要生成缩略图或刷新元数据。

#### 哈希
- `hashAndPersist(book)`  
- `hashKoreaderAndPersist(book)`  
- `hashPagesAndPersist(book)`  

这三类方法都先检查库配置，再决定是否计算并写回。

#### 缩略图
- `generateThumbnailAndPersist(book)`  
- `addThumbnailForBook(thumbnail, markSelected)`  
- `deleteThumbnailForBook(thumbnail)`  
- `getThumbnail(bookId)`  
- `getThumbnailBytes(...)`  
- `getThumbnailBytesOriginal(bookId)`  
- `getThumbnailBytesByThumbnailId(thumbnailId)`  
- `findBookThumbnailsToRegenerate(forBiggerResultOnly)`  
- `thumbnailsHouseKeeping(bookId)`  

这部分是整个文件里最“细”的逻辑，既包含新增、选择、清理，也包含字节读取和尺寸缩放。

#### 页内容
- `getBookPage(book, number, convertTo, resizeTo)`  
  负责读出指定页，必要时转换格式或缩放。

#### 删除与软删除
- `deleteOne(book)`  
- `deleteMany(books)`  
- `softDeleteMany(books)`  
- `deleteBookFiles(book)`  

这组方法负责区分“删除数据库记录”“删除磁盘文件”“标记删除时间”。

#### 阅读进度
- `markReadProgress(book, user, page)`  
- `markReadProgressCompleted(bookId, user)`  
- `deleteReadProgress(book, user)`  
- `markProgression(book, user, newProgression)`  

这组方法把本地阅读行为和外部阅读器同步进来的进度统一成 `ReadProgress`。

## 上下游关系

### 上游调用者

从搜索结果看，`BookLifecycle` 被这些地方调用：

- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`  
  后台任务入口，负责调度分析、生成缩略图、哈希、删除文件。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/BookImporter.kt`  
  导入升级书籍时，调用 `deleteOne(bookToUpgrade)` 清理旧书。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`  
  Kobo/同步场景下调用 `markProgression(...)`。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/CommonBookController.kt`  
  也会调用 `markProgression(...)`。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kosync/KoreaderSyncController.kt`  
  KOReader 同步走 `markProgression(...)`。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt`  
  批量删库内容时会调用 `deleteOne(...)`、`softDeleteMany(...)`。
- `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt`  
  删除系列文件时会调用 `deleteBookFiles(...)`，软删系列时会间接触发 `softDeleteMany(...)`。

### 下游依赖

`BookLifecycle` 自己又往下调用这些组件：

- `BookAnalyzer`：真正解析书本结构、页内容、缩略图、页 hash
- `MediaRepository`：保存分析结果和读取页面信息
- `ReadProgressRepository`：读写阅读进度
- `ThumbnailBookRepository`：维护缩略图实体和选中状态
- `BookRepository`：书籍主表更新/删除
- `HistoricalEventRepository`：记录用户可见的历史动作
- `ApplicationEventPublisher`：向系统广播 `DomainEvent`
- `ImageConverter`：缩放/转换图片
- `Hasher` / `KoreaderHasher`：文件 hash
- `KomgaSettingsProvider`：控制缩略图再生成策略

换句话说，**上游是任务、控制器、导入和其他生命周期服务；下游是仓储、分析器、转换器和事件系统**。

## 运行/调用流程

### 1. 分析一本书
典型路径是 `TaskHandler` 触发 `Task.AnalyzeBook`，然后调用 `analyzeAndPersist(book)`。

流程是：

1. 读取库配置中的 `analyzeDimensions`
2. 调用 `bookAnalyzer.analyze(book, ...)`
3. 在事务里更新 `Media`
4. 如果旧 `Media` 是 `OUTDATED` 且页数变了，就修正阅读进度
5. 发布 `DomainEvent.BookUpdated(book)`
6. 如果新媒体状态是 `READY`，返回后续动作：
   - `BookAction.GENERATE_THUMBNAIL`
   - `BookAction.REFRESH_METADATA`

这意味着 `analyzeAndPersist` 不只是保存结果，它还会**决定后续任务链**。

### 2. 生成缩略图
`TaskHandler` 触发 `generateThumbnailAndPersist(book)` 时：

1. 调用 `bookAnalyzer.generateThumbnail(BookWithMedia(...))`
2. 把结果交给 `addThumbnailForBook(...)`
3. 在 `addThumbnailForBook` 里按类型处理：
   - `GENERATED`：只保留一个生成缩略图
   - `SIDECAR`：同 URL 的旧记录先删掉
   - `USER_UPLOADED`：直接插入
4. 决定是否设为 selected
5. 选择后发布 `DomainEvent.ThumbnailBookAdded(...)`
6. 若未选中，则补做一次 `thumbnailsHouseKeeping(...)`

这里可以看出，它把“缩略图数据一致性”也放在生命周期服务里管理了。

### 3. 读取页面内容
`getBookPage(book, number, convertTo, resizeTo)` 的逻辑是：

1. 读 `Media`
2. 调 `bookAnalyzer.getPageContent(...)`
3. 根据媒体类型决定原始 MIME：
   - PDF 用 `pdfImageType.mediaType`
   - 其他格式从 `media.pages[number - 1].mediaType` 取
4. 如果给了 `resizeTo`，先缩放成 JPEG
5. 如果给了 `convertTo`，检查读写格式支持，再转换
6. 返回 `TypedBytes`

这段方法是“按页导出”的核心接口，也带着明显的保护性检查。

### 4. 写阅读进度
`markReadProgress(...)` 和 `markProgression(...)` 是两条输入路径：

- `markReadProgress(...)`：本地按页数直接记进度
- `markProgression(...)`：外部阅读器同步进度，逻辑更复杂

特别是 `markProgression(...)`：

1. 如果已有进度，先检查新时间戳必须更新
2. 根据 `MediaProfile` 分支：
   - `DIVINA` / `PDF`：按页码直接写
   - `EPUB`：先校验 href，再找 `MediaExtensionEpub.positions`
3. EPUB 下会把外部进度映射到内部位置
4. 构造 `ReadProgress`
5. 保存并发布 `DomainEvent.ReadProgressChanged(...)`

这里的关键点是：**外部同步进度不能直接照单全收，必须映射到内部内容模型**。

### 5. 删除书籍
删除分两层：

#### `deleteOne(book)`
1. 事务里删阅读进度、读书单关联、媒体、缩略图、元数据、书籍记录
2. 发布 `DomainEvent.BookDeleted(book)`

#### `deleteBookFiles(book)`
1. 先检查路径存在且可写
2. 删除书籍文件
3. 删除 sidecar 缩略图文件
4. 如果目录空了，尝试删空目录
5. 记录 `HistoricalEvent.BookFileDeleted` / `HistoricalEvent.SeriesFolderDeleted`
6. 最后调用 `softDeleteMany(listOf(book))`

也就是说，`deleteBookFiles` 是“磁盘清理 + 软删标记”，而 `deleteOne` 是“纯数据库删除”。

## 小白阅读顺序

如果第一次看这个文件，建议按这个顺序读：

1. 先看 `analyzeAndPersist(book)`  
   它最能代表这个类的总目标：分析后保存，并决定后续动作。
2. 再看 `generateThumbnailAndPersist(book)` 和 `addThumbnailForBook(...)`  
   这能帮你理解缩略图如何落库、如何选中、如何清理。
3. 看 `getBookPage(...)`  
   了解“按页读取/转换”的请求是怎么处理的。
4. 看 `markProgression(...)`  
   这是最容易读偏的地方，尤其 EPUB 的位置映射逻辑。
5. 最后看 `deleteOne(...)`、`deleteBookFiles(...)`、`softDeleteMany(...)`  
   这部分决定了删除时到底删什么、保留什么、怎么发事件。

如果你想建立“全局视角”，再回头看调用方：

- `TaskHandler.kt`：任务驱动入口
- `BookImporter.kt`：导入升级时的旧书清理
- `KoboController.kt`、`CommonBookController.kt`、`KoreaderSyncController.kt`：进度同步入口
- `LibraryContentLifecycle.kt`、`SeriesLifecycle.kt`：批量删除入口

## 常见误区

1. **把 `BookLifecycle` 当成简单的 CRUD 服务**  
   其实不是。它包含了分析、缩略图、页读取、阅读进度、事件发布、文件删除，属于高层业务编排。

2. **以为 `deleteOne(book)` 会删磁盘文件**  
   不会。它只删数据库和关联记录。真正操作文件系统的是 `deleteBookFiles(book)`。

3. **以为缩略图只是一张图**  
   这里缩略图还有类型区分：`GENERATED`、`SIDECAR`、`USER_UPLOADED`，并且有“选中状态”和清理逻辑。

4. **以为外部阅读进度可以直接写入**  
   `markProgression(...)` 会校验时间、页码、资源存在性，还会把 EPUB 的位置映射回内部位置，不是直接存原始输入。

5. **忽略事务和事件的配合**  
   很多写操作在事务里做数据库更新，事务外再发布 `DomainEvent` 或写 `HistoricalEvent`。这说明它既关心一致性，也关心系统解耦。

6. **忽略库级配置对行为的影响**  
   `hashFiles`、`hashKoreader`、`hashPages`、`analyzeDimensions`、`thumbnailSize.maxEdge` 都会改变实际流程。  
   所以同一个方法在不同库里可能表现不同。

7. **误把 `thumbnailsHouseKeeping(...)` 当成可有可无的辅助函数**  
   它其实是在修复脏数据：删除不存在的缩略图、保证最多只有一个 selected、必要时自动补一个 selected。这个函数是缩略图一致性的关键。
