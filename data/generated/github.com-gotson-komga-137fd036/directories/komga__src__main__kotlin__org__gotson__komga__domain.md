# 目录：komga/src/main/kotlin/org/gotson/komga/domain

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/domain` 是 Komga 后端的领域层，负责表达“漫画/书库系统里有哪些核心业务对象、这些对象如何被持久化访问、以及围绕这些对象的业务生命周期如何运转”。

它不是 HTTP API 层，也不是数据库实现层。它更像系统的业务内核：上层 REST、Kobo、OPDS、SSE、任务调度等入口会调用这里的 service；下层 jOOQ DAO、缓存、文件系统、图片处理、哈希计算、元数据解析等基础设施会被这里通过接口或依赖注入使用。

从结构看，这个目录只有三类内容：

- `model`：领域模型和值对象，例如 `Library`、`Series`、`Book`、`Media`、`BookMetadata`、`SeriesMetadata`、`ReadProgress`、`DomainEvent`。
- `persistence`：领域仓储接口，例如 `BookRepository`、`LibraryRepository`、`SeriesRepository`、`MediaRepository`。这里定义“领域层需要什么查询/保存能力”，但不关心 SQL 怎么写。
- `service`：领域服务和生命周期编排，例如 `LibraryLifecycle`、`LibraryContentLifecycle`、`SeriesLifecycle`、`BookLifecycle`、`FileSystemScanner`、`BookImporter`、`MetadataAggregator`。

一句话概括：这里定义 Komga 的业务语言，并把“扫描书库、导入书籍、维护系列和书籍、生成媒体信息、更新元数据、发布领域事件”等核心流程串起来。

## 关键组成

`model` 是阅读这个目录的基础。

`Library` 表示一个书库，字段里包含根目录 `root`、扫描选项 `scanCbx`/`scanPdf`/`scanEpub`、元数据导入开关、哈希开关、封面策略 `seriesCover`、扫描周期 `scanInterval` 等。它通过 `root.toURI().toPath()` 暴露 `path`，说明书库首先是一个文件系统目录。

`Series` 表示一个系列，核心字段是 `name`、`url`、`fileLastModified`、`libraryId`、`bookCount`、`deletedDate`、`oneshot`。它也是文件系统路径映射来的对象。

`Book` 表示一本书或一个文件，包含 `url`、`fileLastModified`、`fileSize`、`fileHash`、`fileHashKoreader`、`number`、`seriesId`、`libraryId`、`deletedDate` 等。`Book` 本身只描述文件级实体，不包含页列表和格式分析结果。

`Media` 承载书籍文件被分析后的结果，例如 `status`、`mediaType`、`pages`、`pageCount`、`files`、`extension`、`bookId`。`Media.Status` 有 `UNKNOWN`、`ERROR`、`READY`、`UNSUPPORTED`、`OUTDATED`，它是判断一本书是否已经成功解析的关键状态。

`BookMetadata` 和 `SeriesMetadata` 是书籍/系列的业务元数据。它们有大量 `xxxLock` 字段，表示某个字段是否被用户锁定，不应被自动元数据导入覆盖。构造时还会做规范化，例如标题 trim、标签 lower、`SeriesMetadata.language` 使用 `BCP47TagValidator.normalize`。

`DomainEvent` 是领域事件集合，包含 `LibraryAdded`、`LibraryUpdated`、`LibraryScanned`、`SeriesAdded`、`BookAdded`、`BookUpdated`、`ReadProgressChanged`、各种 thumbnail 事件、用户事件等。领域服务完成状态变化后会发布这些事件；SSE、搜索索引、指标等模块会监听它们。

`persistence` 目录是仓储接口层。比如 `BookRepository` 定义了按 id、library、series、URL、hash、media type、搜索条件查询书籍，以及 insert/update/delete/count 等方法；`LibraryRepository` 定义书库增删改查；`ReferentialRepository` 提供作者、标签、语言、出版社、年龄分级等参照数据查询。实际实现不在 domain 里，而是在类似 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDao.kt`、`LibraryDao.kt`、`SeriesDao.kt`、`MediaDao.kt` 这些基础设施文件中。

`service` 是业务动作所在。代表类包括：

- `LibraryLifecycle`：新增、更新、删除书库，校验路径和重名，触发扫描任务，发布书库事件。
- `LibraryContentLifecycle`：扫描书库目录并同步数据库，是“文件系统变化 -> 领域数据变化”的核心编排。
- `FileSystemScanner`：只负责遍历文件系统，把目录和文件识别成临时的 `Series`、`Book`、`Sidecar`，返回 `ScanResult`。
- `SeriesLifecycle`：创建系列、添加书籍、排序书籍、软删除/硬删除系列、处理系列阅读进度和缩略图。
- `BookLifecycle`：分析书籍、计算哈希、生成缩略图、读取缩略图字节、维护阅读进度、删除书籍等。
- `BookImporter`：从外部文件导入、复制/移动/硬链接书籍文件，处理升级替换、sidecar、旧书数据迁移。
- `MetadataAggregator`、`MetadataApplier`：聚合和应用元数据。
- `ReadListLifecycle`、`SeriesCollectionLifecycle`、`KomgaUserLifecycle`、`PageHashLifecycle`、`SyncPointLifecycle`：分别管理阅读列表、合集、用户、页面哈希、同步点等业务对象。

## 上下游关系

上游主要是接口层和任务层。

REST API 位于 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest`，例如 `LibraryController`、`BookController`、`SeriesController`、`ReadListController` 会调用 domain service 或 repository。Kobo、KOReader、OPDS 等接口也会访问 `BookLifecycle`、`BookRepository`、`ReadProgressRepository` 等领域能力。应用任务层位于 `komga/src/main/kotlin/org/gotson/komga/application/tasks`，`TaskEmitter` 负责提交扫描、分析、哈希、元数据刷新等任务，`TaskHandler` 再调用对应的领域服务执行。

下游主要是基础设施层。

持久化实现位于 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main`，如 `BookDao` 实现 `BookRepository`，`LibraryDao` 实现 `LibraryRepository`，`MediaDao` 实现 `MediaRepository`。文件、图片、哈希、元数据解析、sidecar 识别等能力也来自 infrastructure，例如 `Hasher`、`KoreaderHasher`、`ImageConverter`、`SidecarBookConsumer`、`SidecarSeriesConsumer`。

横向依赖是事件系统。domain service 使用 Spring 的 `ApplicationEventPublisher` 发布 `DomainEvent`。这些事件被 `interfaces/sse/SseController` 转换成前端 SSE 消息，也被 `infrastructure/search/SearchIndexLifecycle` 用来更新 Lucene 搜索索引，还会影响指标发布等模块。

因此 domain 的位置可以理解为：

接口层/任务层 -> `domain.service` -> `domain.persistence` 接口 -> infrastructure 实现  
同时 `domain.service` -> `DomainEvent` -> SSE/搜索索引/指标等监听者。

## 运行/调用流程

最典型流程是“新增书库并扫描”。

用户通过 API 创建一个 `Library` 后，上层调用 `LibraryLifecycle.addLibrary`。这个方法会读取现有书库，执行 `checkLibraryValidity`：检查路径存在、路径是目录、书库名不重复、书库路径不能包含已有书库路径或被已有书库路径包含。校验通过后调用 `libraryRepository.insert` 保存书库，然后通过 `taskEmitter.scanLibrary(library.id)` 提交扫描任务，最后发布 `DomainEvent.LibraryAdded`。

扫描任务执行时会进入 `LibraryContentLifecycle.scanRootFolder`。它调用 `FileSystemScanner.scanRootFolder` 遍历书库目录。`FileSystemScanner` 根据 `scanCbx`、`scanPdf`、`scanEpub` 决定识别哪些扩展名；每个目录先临时视为一个 `Series`；每个符合扩展名的文件会转为 `Book`；同时识别 series/book sidecar 文件。扫描结果是 `ScanResult(series, sidecars)`。

`LibraryContentLifecycle` 拿到扫描结果后，会把扫描到的 `Series`、`Book` 补上 `libraryId`，再与数据库现有数据比较：

- 磁盘上不存在的系列会被 `seriesLifecycle.softDeleteMany` 软删除。
- 磁盘上不存在的书会被 `bookLifecycle.softDeleteMany` 软删除。
- 新系列会通过 `seriesLifecycle.createSeries` 创建，并初始化 `SeriesMetadata` 和 `BookMetadataAggregation`。
- 新书会通过 `seriesLifecycle.addBooks` 插入，同时创建对应的 `Media` 和 `BookMetadata`。
- 已存在但修改时间变化的书，会更新 `Book`，并在必要时把 `Media.status` 置为 `OUTDATED`。
- 系列书籍增删后，会调用 `seriesLifecycle.sortBooks` 重新自然排序，并触发 `taskEmitter.refreshSeriesMetadata`。
- sidecar 变化会触发本地封面或元数据刷新任务。

扫描结束后发布 `DomainEvent.LibraryScanned`。

另一个典型流程是“分析书籍”。任务层调用 `BookLifecycle.analyzeAndPersist(book)`，它通过 `BookAnalyzer.analyze` 分析文件，得到新的 `Media`。如果之前的 `Media` 是 `OUTDATED` 且页数变化，会调整阅读进度，避免进度页码越界。随后更新 `mediaRepository`，发布 `DomainEvent.BookUpdated`。如果分析结果是 `Media.Status.READY`，返回 `BookAction.GENERATE_THUMBNAIL` 和 `BookAction.REFRESH_METADATA`，交给任务层继续生成缩略图和刷新元数据。

导入流程则由 `BookImporter.importBook` 负责：它先检查源文件不在已有书库内，再按 `CopyMode.MOVE`、`COPY`、`HARDLINK` 将文件放入目标系列目录，扫描新文件生成 `Book`，调用 `seriesLifecycle.addBooks` 入库。如果是升级已有书籍，还会迁移旧书的 `Media`、`BookMetadata`、用户上传缩略图、阅读进度、阅读列表引用，然后删除旧书。

## 小白阅读顺序

建议先读 `model`，不要直接跳进 service。

第一步看三个核心实体：`komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`、`Series.kt`、`Book.kt`。理解 Komga 的基本层级是 Library -> Series -> Book，而且它们都和文件系统路径绑定。

第二步看 `Media.kt`、`BookMetadata.kt`、`SeriesMetadata.kt`。这会解释为什么 `Book` 不直接包含页数、格式、作者、标签等信息：文件实体、媒体分析结果、业务元数据是分开的。

第三步看 `DomainEvent.kt`。它能快速告诉你系统关心哪些业务变化，也能反推哪些流程会通知前端、搜索索引和其他监听者。

第四步看 `persistence/BookRepository.kt`、`LibraryRepository.kt`、`SeriesRepository.kt`。重点不是背方法，而是理解 domain 通过接口依赖持久化，不直接写 SQL。

第五步看 `service/FileSystemScanner.kt`。这个文件相对独立，容易理解“目录和文件如何变成 `ScanResult`”。

第六步看 `service/LibraryLifecycle.kt` 和 `service/LibraryContentLifecycle.kt`。前者负责书库生命周期入口，后者负责扫描后同步，是理解 Komga 后台自动整理书库的核心。

第七步看 `service/SeriesLifecycle.kt` 和 `service/BookLifecycle.kt`。这两个文件较大，建议按方法读：先看 `createSeries`、`addBooks`、`sortBooks`、`analyzeAndPersist`、`generateThumbnailAndPersist`，再看删除、阅读进度、缩略图等辅助流程。

最后再读 `BookImporter.kt`、`MetadataAggregator.kt`、`MetadataApplier.kt`、`PageHashLifecycle.kt` 等专项服务。

## 常见误区

不要把 `domain/persistence` 当成数据库实现。这里全是接口，真正 jOOQ 实现在 `infrastructure/jooq/main`。例如 `BookRepository` 的实现要去找 `BookDao`，不是在 domain 目录里找 SQL。

不要认为 `Book` 就代表一本书的全部信息。`Book` 主要是文件实体；页数、页面、媒体类型在 `Media`；标题、作者、标签、ISBN 在 `BookMetadata`；阅读进度在 `ReadProgress`；缩略图在 `ThumbnailBook`。

不要把扫描和分析混为一谈。`FileSystemScanner` 只识别文件路径、扩展名、修改时间、大小和 sidecar；真正打开压缩包/PDF/EPUB、计算页数、生成封面，是 `BookAnalyzer` 和 `BookLifecycle` 后续任务完成的。

不要忽略软删除。扫描时磁盘上找不到的系列或书，通常先通过 `deletedDate` 软删除，而不是马上从数据库硬删。这样才有恢复、回收站、迁移匹配等能力。

不要以为 service 只是 CRUD 包装。比如 `LibraryContentLifecycle.scanRootFolder` 会处理新增、变更、软删除、恢复匹配、sidecar 刷新、元数据刷新、清理空集合、发布事件等多个业务动作；`SeriesLifecycle.addBooks` 插入书籍时还会同步创建 `Media` 和 `BookMetadata`。

不要忽略 `xxxLock` 字段。`BookMetadata`、`SeriesMetadata` 中的 lock 字段决定自动元数据导入能否覆盖用户手动编辑内容。阅读元数据逻辑时，如果不考虑 lock，很容易误判为什么某些字段没有被更新。

不要把 `DomainEvent` 当成可有可无的日志。它是领域层和外部响应机制的连接点：前端实时更新、搜索索引刷新、指标变化都可能依赖这些事件。
