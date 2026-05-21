# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt

## 它负责什么

`LibraryLifecycle.kt` 定义了领域服务 `LibraryLifecycle`，负责管理 `Library` 的生命周期：新增、更新、删除。

它处在 Komga 的“领域编排层”，本身不负责真正扫描文件系统、不负责解析书籍、不负责执行后台任务，也不直接处理 HTTP 请求。它的职责是把一次图书库操作拆成一组领域动作，例如：

- 校验图书库根目录是否存在、是否是目录。
- 校验图书库名称不能重复。
- 校验图书库路径不能和已有图书库互相包含。
- 新增图书库后发起首次扫描任务。
- 更新图书库后判断是否需要重新扫描、重新调度定时扫描、补发 hash/转换/修复类后台任务。
- 删除图书库时级联删除该库下的 series、sidecar 等数据。
- 在增删改完成后发布 `DomainEvent.LibraryAdded`、`DomainEvent.LibraryUpdated`、`DomainEvent.LibraryDeleted` 领域事件。

简单说，`LibraryLifecycle` 是“图书库配置被创建、修改、删除时，系统该做什么”的集中入口。

## 关键组成

这个文件的包名是：

`org.gotson.komga.domain.service`

它被标记为 Spring `@Service`，因此会由 Spring 容器创建并注入到调用方，例如 REST 控制器。

主要依赖如下：

- `LibraryRepository`：读写 `Library` 持久化数据，包括 `findAll`、`findById`、`insert`、`update`、`delete`。
- `SeriesLifecycle`：删除图书库时，委托它删除图书库下的所有 `Series` 及其关联书籍、元数据、缩略图、阅读进度等。
- `SeriesRepository`：查询某个 library 下的所有 series。
- `SidecarRepository`：删除图书库关联的 sidecar 数据。
- `TaskEmitter`：向后台任务系统提交任务，例如扫描图书库、补 hash、修复扩展名、转换 CBZ。
- `ApplicationEventPublisher`：发布领域事件。
- `TransactionTemplate`：删除图书库时包裹事务，保证一组删除操作在事务中执行。
- `LibraryScanScheduler`：当 `scanInterval` 改变时，重新安排该图书库的周期扫描任务。

文件内核心方法有四组。

`addLibrary(library: Library): Library`

负责新增图书库。流程是：

1. 打日志。
2. 读取全部已有图书库。
3. 调用 `checkLibraryValidity` 校验路径、目录、名称、路径嵌套关系。
4. 调用 `libraryRepository.insert(library)` 保存。
5. 调用 `taskEmitter.scanLibrary(library.id)` 触发扫描任务。
6. 发布 `DomainEvent.LibraryAdded(library)`。
7. 重新从仓储读取并返回保存后的 `Library`。

这里重新 `findById` 的意义通常是拿到持久化后的最终对象。根据当前片段推断，仓储层可能会补齐审计字段或返回数据库中的规范版本，依据是 `addLibrary` 插入后没有直接返回入参，而是再次 `findById(library.id)`。

`updateLibrary(toUpdate: Library)`

负责更新图书库配置。它先找出当前版本 `current`，再校验新版本是否合法。保存后，根据变更内容触发不同副作用：

- 如果 `scanInterval` 改了，调用 `libraryScanScheduler.scheduleScan(toUpdate)` 重新设置周期扫描。
- 如果根路径、oneshots 目录、扫描格式开关、强制修改时间扫描、目录排除规则等影响扫描结果的字段改了，调用 `taskEmitter.scanLibrary(toUpdate.id)`。
- 如果 `hashFiles` 从 `false` 变为 `true`，调用 `taskEmitter.hashBooksWithoutHash(toUpdate)`。
- 如果 `hashKoreader` 从 `false` 变为 `true`，调用 `taskEmitter.hashBooksWithoutHashKoreader(toUpdate)`。
- 如果 `hashPages` 从 `false` 变为 `true`，调用 `taskEmitter.findBooksWithMissingPageHash(toUpdate, LOWEST_PRIORITY)`。
- 如果 `repairExtensions` 从 `false` 变为 `true`，调用 `taskEmitter.repairExtensions(toUpdate, LOWEST_PRIORITY)`。
- 如果 `convertToCbz` 从 `false` 变为 `true`，调用 `taskEmitter.findBooksToConvert(toUpdate, LOWEST_PRIORITY)`。
- 最后发布 `DomainEvent.LibraryUpdated(toUpdate)`。

这里的判断重点是“只在功能开关从关闭变开启时补发存量任务”。如果用户把某个开关从 `true` 改回 `false`，它不会主动撤销已存在任务，也不会回滚已经生成的数据。

`checkLibraryShouldRescan(existing: Library, updated: Library): Boolean`

这是一个私有判断函数，用来决定更新后是否需要重新扫描。它比较这些字段：

- `root`
- `oneshotsDirectory`
- `scanCbx`
- `scanPdf`
- `scanEpub`
- `scanForceModifiedTime`
- `scanDirectoryExclusions`

这些字段会影响扫描能看到哪些文件、如何解释目录、哪些内容被排除，因而变更后需要重新扫描。

值得注意的是，很多导入类配置没有放进这个判断，例如 `importComicInfoBook`、`importEpubBook`、`importLocalArtwork` 等。根据当前片段推断，这些字段更多影响后续导入/解析策略，不一定要求立即重扫；或者重扫触发点在其他流程中处理。依据是 `checkLibraryShouldRescan` 明确只列出了扫描边界和扫描文件类型相关字段。

`checkLibraryValidity(library: Library, existing: Collection<Library>)`

这是图书库合法性校验函数。它检查：

- `Files.exists(library.path)`：根路径必须存在，否则抛 `FileNotFoundException`。
- `Files.isDirectory(library.path)`：根路径必须是目录，否则抛 `DirectoryNotFoundException`。
- 已有图书库名称不能包含同名，否则抛 `DuplicateNameException`。
- 新图书库路径不能是已有图书库路径的子目录。
- 新图书库路径不能是已有图书库路径的父目录。

最后两条都抛 `PathContainedInPath`。这样可以避免两个 library 扫描范围重叠，导致同一本书被多个图书库重复管理。

`deleteLibrary(library: Library)`

负责删除图书库。流程是：

1. 查询该图书库下所有 series：`seriesRepository.findAllByLibraryId(library.id)`。
2. 在事务中执行：
   - `seriesLifecycle.deleteMany(series)`；
   - `sidecarRepository.deleteByLibraryId(library.id)`；
   - `libraryRepository.delete(library.id)`。
3. 发布 `DomainEvent.LibraryDeleted(library)`。

`SeriesLifecycle.deleteMany` 内部还会继续删除 series 下的 book、阅读进度、collection 关联、series 缩略图、series metadata、book metadata aggregation 等。因此 `LibraryLifecycle.deleteLibrary` 是图书库删除的上层入口，实际深层清理由 `SeriesLifecycle` 和更下游生命周期服务完成。

## 上下游关系

上游主要是 API 层。

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt` 注入了 `LibraryLifecycle`，并在管理员接口中调用它：

- `POST /api/v1/libraries` 对应 `addLibrary`。
- `PATCH /api/v1/libraries/{libraryId}` 对应 `updateLibrary`。
- 已废弃的 `PUT /api/v1/libraries/{libraryId}` 也复用更新逻辑。
- `DELETE /api/v1/libraries/{libraryId}` 对应 `deleteLibrary`。

`LibraryController` 负责把 DTO 转成领域模型 `Library`，也负责把 `FileNotFoundException`、`DirectoryNotFoundException`、`DuplicateNameException`、`PathContainedInPath` 这类领域/校验异常转成 HTTP `400 BAD_REQUEST`。如果找不到 library，则在控制器层返回 `404 NOT_FOUND`。

中间模型是 `komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`。

`Library` 是一个 data class，包含大量图书库配置，例如：

- 基础信息：`name`、`root`、`id`。
- 导入配置：`importComicInfoBook`、`importEpubBook`、`importLocalArtwork` 等。
- 扫描配置：`scanInterval`、`scanCbx`、`scanPdf`、`scanEpub`、`scanDirectoryExclusions` 等。
- 后处理配置：`repairExtensions`、`convertToCbz`、`hashFiles`、`hashPages`、`hashKoreader`。
- 展示/封面配置：`seriesCover`。
- 审计字段：`createdDate`、`lastModifiedDate`。

其中 `path` 是从 `root: URL` 懒加载转换得到的 `Path`：

`val path: Path by lazy { this.root.toURI().toPath() }`

这解释了为什么 `LibraryLifecycle` 用 `library.path` 做文件系统校验，而不是直接操作 `root` 字符串。

下游主要有四类。

第一类是持久化仓储：

- `LibraryRepository`：保存、更新、删除 library。
- `SeriesRepository`：查询 library 下的 series。
- `SidecarRepository`：删除 library 相关 sidecar。

第二类是后台任务系统：

`TaskEmitter` 会把动作转换成 `Task` 并提交到任务仓储/事件系统。`LibraryLifecycle` 用到的任务包括：

- `Task.ScanLibrary`
- `Task.HashBook`
- `Task.HashBookKoreader`
- `Task.FindBooksWithMissingPageHash`
- `Task.RepairExtension`
- `Task.FindBooksToConvert`

第三类是定时扫描：

`LibraryScanScheduler.scheduleScan(library)` 会先取消旧的定时任务，再根据 `library.scanInterval` 创建新的 fixed-rate task。如果 `scanInterval == DISABLED`，则不会注册新的周期任务。

第四类是领域事件：

`DomainEvent.kt` 中定义了：

- `DomainEvent.LibraryAdded`
- `DomainEvent.LibraryUpdated`
- `DomainEvent.LibraryDeleted`
- `DomainEvent.LibraryScanned`

`LibraryLifecycle` 只发布前三个。`LibraryScanned` 应该由实际扫描流程发布，而不是由生命周期服务发布。

## 运行/调用流程

新增图书库时，典型流程如下：

1. 用户通过 REST API 提交创建请求。
2. `LibraryController.addLibrary` 把 `LibraryCreationDto` 转成领域模型 `Library`。
3. 调用 `LibraryLifecycle.addLibrary`。
4. `LibraryLifecycle` 查询已有图书库，并校验新图书库：
   - 根目录存在；
   - 根目录是文件夹；
   - 名称不重复；
   - 路径不和已有图书库互相包含。
5. 插入 `LibraryRepository`。
6. 提交一次扫描任务 `taskEmitter.scanLibrary(library.id)`。
7. 发布 `DomainEvent.LibraryAdded`。
8. 返回持久化后的 `Library` 给控制器，再转成 DTO 返回客户端。

更新图书库时，典型流程如下：

1. 用户通过 `PATCH /api/v1/libraries/{libraryId}` 提交部分字段。
2. `LibraryController` 先读取现有 `Library`。
3. 控制器使用 `existing.copy(...)` 合成完整的 `toUpdate`。
4. 调用 `LibraryLifecycle.updateLibrary(toUpdate)`。
5. `LibraryLifecycle` 读取所有图书库，分离当前图书库和其他图书库。
6. 用其他图书库集合校验 `toUpdate`，避免自己和自己比较导致名称重复或路径冲突。
7. 保存更新。
8. 如果 `scanInterval` 改变，重新调度周期扫描。
9. 如果扫描范围相关字段改变，提交一次扫描任务。
10. 如果某些后处理开关从关闭变为开启，补发对应后台任务。
11. 发布 `DomainEvent.LibraryUpdated`。

删除图书库时，典型流程如下：

1. 用户通过 `DELETE /api/v1/libraries/{libraryId}` 请求删除。
2. `LibraryController` 读取目标 library，不存在则返回 `404`。
3. 调用 `LibraryLifecycle.deleteLibrary(library)`。
4. 查询该 library 下全部 series。
5. 开启事务。
6. 调用 `SeriesLifecycle.deleteMany(series)` 删除 series 及其下游数据。
7. 删除该 library 的 sidecar 数据。
8. 删除 library 记录本身。
9. 事务结束后发布 `DomainEvent.LibraryDeleted`。

一个细节是：`deleteLibrary` 外层开启了 `transactionTemplate.executeWithoutResult`，而 `SeriesLifecycle.deleteMany` 内部也使用了事务模板。根据当前片段推断，在 Spring 默认事务传播行为下，内层事务通常会参与外层事务，保证删除链路整体一致；依据是两者都使用 Spring `TransactionTemplate`，且没有看到自定义传播配置。

## 小白阅读顺序

建议按下面顺序读。

第一步，先读 `Library.kt`。

重点理解 `Library` 有哪些配置项，尤其是这些字段：

- `root`
- `path`
- `scanInterval`
- `scanCbx`
- `scanPdf`
- `scanEpub`
- `scanDirectoryExclusions`
- `hashFiles`
- `hashPages`
- `hashKoreader`
- `repairExtensions`
- `convertToCbz`

只有先知道这些字段代表什么，才能理解 `updateLibrary` 为什么要对不同字段做不同处理。

第二步，读 `LibraryLifecycle.addLibrary`。

这是最容易理解的一条主线：校验、保存、扫描、发事件。它能帮助你建立这个类的基本模式：领域服务不直接做所有事情，而是协调仓储、任务、事件。

第三步，读 `checkLibraryValidity`。

这里是新增和更新都复用的核心校验。特别要注意路径包含关系：

- 新路径在旧路径里面，不允许。
- 旧路径在新路径里面，也不允许。

这不是简单的字符串比较，而是 `Path.startsWith`，语义上是文件路径层级判断。

第四步，读 `updateLibrary` 和 `checkLibraryShouldRescan`。

这里是全文件最重要也最容易漏细节的地方。阅读时可以把字段分成三类：

- 改了会重新调度：`scanInterval`。
- 改了会重新扫描：`root`、`oneshotsDirectory`、扫描格式和排除规则等。
- 从关闭变开启时会补发后台任务：hash、page hash、repair、convert。

第五步，读 `TaskEmitter.kt` 中对应方法。

重点不是看完整任务系统，而是理解 `LibraryLifecycle` 发出去的任务到底是什么。例如：

- `scanLibrary` 只是提交 `Task.ScanLibrary`。
- `hashBooksWithoutHash` 会查出缺少 hash 的 book，然后提交多个 `Task.HashBook`。
- `repairExtensions` 会先找扩展名不匹配的 book，再提交修复任务。

这能帮助你理解 `LibraryLifecycle` 为什么叫 lifecycle，而不是 scanner：它只是发起任务，不执行任务。

第六步，读 `LibraryController.kt` 里的增删改接口。

这样可以把“HTTP 请求 -> DTO -> Library -> LibraryLifecycle -> repository/task/event”的链路串起来。对于初学者来说，这比只读领域服务更容易理解真实调用路径。

第七步，读 `SeriesLifecycle.deleteMany`。

这个方法解释了删除 library 为什么只显式删除了 series、sidecar、library 三类东西，却能连带清理书籍、阅读进度、集合关联、缩略图和元数据。真正的深层删除逻辑在 series 生命周期里。

## 常见误区

误区一：以为 `LibraryLifecycle` 会执行扫描。

它不会。`addLibrary` 和部分 `updateLibrary` 场景只是调用 `taskEmitter.scanLibrary(...)` 提交扫描任务。真正扫描通常由后台任务处理器、扫描服务等其他组件完成。这个文件只负责“何时应该发起扫描”。

误区二：以为更新任何字段都会重新扫描。

不是。`checkLibraryShouldRescan` 只关心会影响扫描输入或扫描范围的字段，例如根路径、oneshots 目录、扫描文件类型、强制修改时间、目录排除规则。导入元数据相关配置变更不在这个函数中。

误区三：以为 `scanInterval` 改变会立刻扫描。

`scanInterval` 改变只会调用 `libraryScanScheduler.scheduleScan(toUpdate)` 重新设置周期任务。是否立即扫描取决于其他字段是否触发 `checkLibraryShouldRescan`。如果只是从 `EVERY_6H` 改成 `DAILY`，它主要影响后续周期任务，不等同于立即提交扫描。

误区四：以为打开 `hashPages`、`convertToCbz` 等开关会同步处理所有书。

不是同步处理。它们都是通过 `TaskEmitter` 发后台任务，而且部分任务使用 `LOWEST_PRIORITY`。这意味着用户更新配置后，实际处理会异步发生，并且可能排在低优先级队列中。

误区五：以为关闭某个开关会撤销任务或删除结果。

`updateLibrary` 只处理“从 `false` 变为 `true`”的补发任务逻辑。比如 `hashPages` 从 `true` 改成 `false`，这里不会删除已有 page hash，也不会取消已经提交的任务。是否存在取消机制要看任务系统其他部分，不能从这个文件推断出会自动撤销。

误区六：以为图书库可以嵌套管理。

不可以。`checkLibraryValidity` 明确禁止路径互相包含。比如已有图书库 `/books`，再新增 `/books/manga` 会失败；反过来已有 `/books/manga`，再新增 `/books` 也会失败。这样做是为了避免扫描范围重叠。

误区七：以为删除 library 只是删一条 library 记录。

不是。`deleteLibrary` 会先找出该 library 下所有 series，交给 `SeriesLifecycle.deleteMany` 删除。根据读取到的代码，series 删除会进一步删除 book、阅读进度、collection 关联、series 缩略图、series metadata、book metadata aggregation 等。然后才删除 sidecar 和 library 自身。

误区八：忽略事件发布的边界。

`LibraryLifecycle` 在新增、更新、删除后发布的是领域事件，不是 HTTP 响应事件，也不是任务完成事件。比如 `LibraryAdded` 表示 library 已创建并已提交扫描任务，但不表示扫描已经完成。

误区九：以为 `checkLibraryValidity` 只在新增时使用。

它也在更新时使用。更新时会先把当前 library 从已有集合中排除，然后校验新配置和其他 library 是否冲突。这可以防止改名成别的 library 名称，或把路径改到别的 library 里面。

误区十：把 `root` 和 `path` 混为一谈。

`Library.root` 是 `URL`，而 `Library.path` 是从 `root.toURI().toPath()` 懒加载得到的 `Path`。文件系统校验使用的是 `path`，API 层则从用户提交的文件路径转换为 URL。理解这一点有助于解释为什么代码里既有 `root`，又有 `path`。
