# 目录：komga/src/main/kotlin/org/gotson/komga/domain/service

## 它负责什么

`domain/service` 是 Komga 后端领域层的“业务编排”目录。它不直接承担 HTTP 路由，也不只是简单 CRUD，而是把领域模型、仓储接口、文件系统扫描、媒体解析、元数据刷新、缩略图、阅读进度、用户、同步点等动作组合成完整业务流程。

这个目录里的类大多被标注为 Spring `@Service`，位于包 `org.gotson.komga.domain.service`。它们的共同特点是：输入通常是领域对象，例如 `Library`、`Series`、`Book`、`ReadList`、`KomgaUser`；内部调用 `domain.persistence` 仓储读写数据库；必要时调用 `infrastructure` 层处理文件、图片、压缩包、EPUB/PDF、哈希、安全会话；最后通过 `TaskEmitter` 或 `ApplicationEventPublisher` 触发异步任务和领域事件。

简单说，这里是“Komga 知道一本漫画书、一个书库、一个用户应该怎样被处理”的地方。

## 关键组成

`LibraryContentLifecycle.kt` 是书库内容扫描的核心编排器。`scanRootFolder(library, scanDeep)` 调用 `FileSystemScanner.scanRootFolder` 扫描磁盘，得到 series、books、sidecars，然后和数据库现状对比：新增 series/book、软删除磁盘上消失的内容、检测文件修改时间、必要时重置 `Media.Status.OUTDATED`、刷新元数据和本地 artwork。它还负责恢复逻辑：通过文件大小和 hash 尝试把新发现的 series/book 与已删除记录匹配，恢复 metadata、thumbnail、read progress、read list 关系等。

`FileSystemScanner.kt` 负责把真实文件系统转成领域对象雏形。它识别根目录下的 series、book 文件、sidecar 文件，并根据配置判断是否扫描 CBX、PDF、EPUB、oneshots、排除目录等。它偏“发现文件”，而 `LibraryContentLifecycle` 偏“把发现结果落库并维护一致性”。

`BookLifecycle.kt` 是单本书生命周期服务。它围绕 `BookAnalyzer` 做媒体分析、hash、页 hash、缩略图生成、页面读取、阅读进度更新、删除/软删除、文件删除等。上层 API 读取页面、OPDS/Kobo/Koreader 同步、后台任务都会进入这里。

`BookAnalyzer.kt` 是媒体解析核心。它先用 `ContentDetector` 判断媒体类型，再按 `MediaProfile.DIVINA`、`PDF`、`EPUB` 分支处理。CBZ/ZIP/RAR 等图像容器通过 `DivinaExtractor` 提取页面；PDF 通过 `PdfExtractor` 获取页面和图片；EPUB 通过 `EpubExtractor` 读取资源、TOC、landmarks、page list、positions、封面等。它还提供 `generateThumbnail`、`getPoster`、`getPageContent`、`getFileContent`、`hashPages`、`hashPage`、`getPdfPagesDynamic` 等能力。

`SeriesLifecycle.kt` 管理 series 级别行为：排序书籍、添加书籍、创建 series、软删除/硬删除、阅读进度批量完成或删除、series thumbnail 管理、删除 series 文件等。它会调用 `BookLifecycle` 处理 series 内的 book。

`LibraryLifecycle.kt` 管理书库本身：新增、更新、删除书库。它与 `SeriesLifecycle` 联动，删除书库时需要处理书库下的 series/book 数据。

`BookMetadataLifecycle.kt`、`SeriesMetadataLifecycle.kt`、`MetadataAggregator.kt`、`MetadataApplier.kt` 组成元数据处理链。`MetadataApplier` 的逻辑很小但关键：patch 只有在字段未 lock 时才覆盖原 metadata。`MetadataAggregator` 根据多本书 metadata 聚合 series 级信息。两个 `*MetadataLifecycle` 则负责读取供应商或本地 sidecar 的结果、应用 patch、保存并触发相关刷新。

`LocalArtworkLifecycle.kt` 处理本地 artwork 刷新。扫描发现 artwork sidecar 变化时，`LibraryContentLifecycle` 会通过 `TaskEmitter` 间接触发它，最后落到 book 或 series 的 thumbnail/artwork 更新。

`ReadListLifecycle.kt` 和 `ReadListMatcher.kt` 管理阅读列表。前者负责新增、更新、删除、添加 book、清理空列表、thumbnail，以及 ComicRack list 匹配；后者根据请求内容匹配现有书籍。`SeriesCollectionLifecycle.kt` 做类似事情，但对象是 series collection。

`KomgaUserLifecycle.kt` 管理用户：创建、更新、删除、修改密码、失效 session、创建 API key 等。它被 REST 用户接口、初始用户创建、密码重置、OAuth2 用户服务等调用。

`BookImporter.kt`、`BookConverter.kt` 是文件操作型服务。`BookImporter` 根据当前片段推断用于把外部 book 导入到指定 library/series，并调用 book/series 生命周期完成落库与分析；依据是它依赖 `BookLifecycle`、`SeriesLifecycle` 且暴露 `importBook`。`BookConverter` 负责找出可转换书籍、转成 CBZ、修复扩展名不匹配的问题，并依赖 `BookAnalyzer` 判断媒体内容。

`TransientBookLifecycle.kt` 处理临时书籍：扫描并持久化临时文件、分析临时 book、读取 metadata、读取页面。它服务于上传/临时预览类 API，不一定进入正式 library。

`BookPageEditor.kt` 和 `PageHashLifecycle.kt` 与页面 hash 相关。前者可移除已 hash 页面，后者查找缺失页 hash 的 book、读取页面、管理已知 page hash 和自动删除规则。

`SyncPointLifecycle.kt` 管理同步点，提供 `createSyncPoint`、`takeBooksAdded`、`takeBooksChanged`、`takeBooksRemoved`、`takeBooksReadProgressChanged`、`takeReadListsAdded/Changed/Removed` 等方法，用来给客户端增量同步 book、read list、阅读进度变化。

## 上下游关系

上游主要来自三类入口。

第一类是后台任务：`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt` 注入 `LibraryContentLifecycle`、`BookLifecycle`、`BookMetadataLifecycle`、`SeriesLifecycle`、`SeriesMetadataLifecycle`、`BookImporter`、`BookConverter`，说明扫描、分析、元数据刷新、导入、转换等重活通常由任务系统调度。

第二类是 REST/OPDS/Kobo/Koreader API：例如 `interfaces/api/rest/BookController.kt`、`CommonBookController.kt`、`SeriesController.kt`、`ReadListController.kt`、`UserController.kt`、`KoboController.kt`、`KoreaderSyncController.kt` 会调用 `BookLifecycle`、`BookAnalyzer`、`SeriesLifecycle`、`ReadListLifecycle`、`KomgaUserLifecycle`。这些 API 不直接解析文件，而是通过 service 层拿页面、缩略图、进度、列表和用户结果。

第三类是基础设施或启动器：`PasswordResetRunner.kt`、`InitialUserController.kt`、OAuth2 配置会进入 `KomgaUserLifecycle`；元数据 provider 如 `ComicInfoProvider.kt`、`IsbnBarcodeProvider.kt` 会使用 `BookAnalyzer` 获取页面或内容。

下游则主要是：`domain.persistence` 仓储负责数据库读写；`domain.model` 提供 `Book`、`Series`、`Library`、`Media`、`ThumbnailBook` 等领域对象；`infrastructure` 提供文件内容探测、图片转换、EPUB/PDF/Divina 提取、hash、配置、安全 session；`application.tasks.TaskEmitter` 负责继续投递刷新任务；Spring `ApplicationEventPublisher` 发布 `DomainEvent.LibraryUpdated`、`DomainEvent.LibraryScanned` 等事件。

## 运行/调用流程

典型书库扫描流程是：

1. 上层任务调用 `LibraryContentLifecycle.scanRootFolder(library, scanDeep)`。
2. `FileSystemScanner` 扫描磁盘，返回发现的 series、books、sidecars。
3. 如果根目录不存在，更新 `library.unavailableDate` 并发布 `DomainEvent.LibraryUpdated`。
4. 将扫描结果补上 `libraryId`，与数据库中未删除 series/book 按 `url` 对比。
5. 数据库存在但磁盘不存在的 series/book 被软删除，便于 trash bin 和恢复。
6. 新 series 调用 `SeriesLifecycle.createSeries`，新 book 调用 `SeriesLifecycle.addBooks`。
7. 已存在 book 如果修改时间变化，会根据文件大小和 hash 判断是否只更新文件信息，还是把对应 `Media` 标为 `OUTDATED`。
8. 新增或变动的 series 会排序，并通过 `TaskEmitter.refreshSeriesMetadata` 触发元数据刷新。
9. sidecar 变化会触发 book/series 的本地 artwork 或 metadata 刷新。
10. 根据书库配置执行 `emptyTrash` 或清理空 collection/read list。
11. 最后发布 `DomainEvent.LibraryScanned`。

典型单本书分析流程是：

1. `BookLifecycle.analyzeAndPersist(book)` 调用 `BookAnalyzer.analyze(book, analyzeDimensions)`。
2. `BookAnalyzer` 用 `ContentDetector` 得到媒体类型。
3. 按 profile 分支：Divina 容器提取图片页面；PDF 生成页面列表；EPUB 读取资源、目录、页列表、positions 和固定布局信息。
4. 生成 `Media`，状态可能是 `READY`、`UNSUPPORTED`、`ERROR`、`OUTDATED`。
5. 后续可由 `BookLifecycle.generateThumbnailAndPersist` 生成缩略图，由 `hashPagesAndPersist` 计算页 hash。
6. API 请求页面时通常进入 `BookLifecycle.getBookPage`，再委托 `BookAnalyzer.getPageContent` 或 PDF/EPUB 专用读取逻辑。

元数据流程则是：扫描或任务发现需要刷新后，进入 `BookMetadataLifecycle` 或 `SeriesMetadataLifecycle`；读取 provider/local sidecar 的 patch；`MetadataApplier` 根据 lock 字段决定哪些字段能覆盖；保存后可能影响 series 聚合、read list 匹配和缩略图刷新。

## 小白阅读顺序

建议先读 `LibraryContentLifecycle.kt`，它能建立“扫描磁盘到数据库状态变化”的整体地图。重点看 `scanRootFolder`，暂时不用深挖每个 repository 方法。

第二步读 `FileSystemScanner.kt`，理解 Komga 如何把目录、文件、sidecar 识别成 `Series`、`Book`、`Sidecar`。这能解释为什么 `LibraryContentLifecycle` 主要按 `url`、`fileLastModified`、`fileSize`、`fileHash` 做对比。

第三步读 `BookAnalyzer.kt`，重点看 `analyze`、`analyzeDivina`、`analyzePdf`、`analyzeEpub`、`getPageContent`。这会帮助你理解 `Media` 为什么是 book 的核心派生数据。

第四步读 `BookLifecycle.kt` 和 `SeriesLifecycle.kt`。这两个文件较长，阅读时按公开方法分组：分析/缩略图/页面读取/阅读进度/删除；series 创建/排序/加书/缩略图/删除。

第五步读元数据相关：`MetadataApplier.kt` 最容易，先理解 lock 规则；再读 `BookMetadataLifecycle.kt`、`SeriesMetadataLifecycle.kt`、`MetadataAggregator.kt`。

第六步读外围服务：`ReadListLifecycle.kt`、`SeriesCollectionLifecycle.kt`、`KomgaUserLifecycle.kt`、`SyncPointLifecycle.kt`、`BookConverter.kt`、`BookImporter.kt`、`TransientBookLifecycle.kt`。这些更像具体功能模块，不必一开始就全读完。

## 常见误区

不要把 `domain/service` 理解成 Controller。Controller 在 `interfaces/api` 下，任务调度在 `application/tasks` 下；这里是业务规则和领域状态转换的位置。

不要以为扫描等于分析。`FileSystemScanner` 只发现文件并生成初始对象；`BookAnalyzer` 才解析媒体内容；`LibraryContentLifecycle` 负责把两者和数据库旧状态合并。

不要以为删除都是硬删除。扫描发现文件消失时，很多地方先做 soft delete，以支持 trash bin、恢复阅读进度、恢复 metadata 和 read list 关系。真正清理可能由 `emptyTrash` 或 lifecycle 的 `deleteMany/deleteOne` 完成。

不要忽略 `fileHash`。恢复 series/book、判断文件是否真的变化、页 hash 去重或删除规则，都依赖 hash。`fileLastModified` 只是快速判断线索，不是唯一依据。

不要以为 metadata patch 会无条件覆盖。`MetadataApplier` 明确检查每个字段的 lock，例如 `titleLock`、`summaryLock`、`authorsLock`、`statusLock`。锁住的字段会保留原值。

不要把 `BookAnalyzer` 当成纯图片工具。它同时处理 Divina 容器、PDF、EPUB，并且会返回 `Media`、页面、文件资源、EPUB 扩展信息、封面、动态 PDF 页面、页 hash 等。

不要忽略异步任务。很多方法不会在当前调用栈里完成所有后续动作，而是通过 `TaskEmitter` 继续刷新 metadata、artwork、thumbnail 或分析任务。理解调用链时要同时看 `application/tasks/TaskHandler.kt`。
