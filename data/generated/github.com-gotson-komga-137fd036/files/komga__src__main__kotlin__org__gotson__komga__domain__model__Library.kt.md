# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt

## 它负责什么

`Library.kt` 定义 Komga 领域层里的 `Library` 模型，也就是“书库”的核心数据结构。它不负责真正扫描文件、写数据库、处理 API 请求，而是集中描述一个书库应该具备的状态和配置：书库名称、根目录、导入哪些元数据、扫描哪些文件类型、扫描频率、封面策略、哈希策略、是否自动修复/转换、是否不可用等。

从分层上看，它位于 `org.gotson.komga.domain.model` 包，是一个纯领域模型。上层 REST API 会用请求数据构造或更新 `Library`，基础设施层会把数据库记录映射回 `Library`，服务层会根据它的字段决定是否触发扫描、哈希、转换、修复、封面选择等后续动作。

这个文件的特点是：逻辑很少，但字段非常关键。大量业务行为不是写在 `Library` 类内部，而是由其他服务读取它的配置字段后执行。

## 关键组成

### `data class Library`

核心声明是：

```kotlin
data class Library(...)
```

它是 Kotlin `data class`，因此天然拥有 `copy`、`equals`、`hashCode`、`toString` 等能力。对于这种配置型领域对象很合适，因为更新书库时通常会基于旧对象 `copy(...)` 出一个新对象，再交给生命周期服务持久化。

主要字段可以按用途分组理解。

### 基础身份字段

`name: String` 是书库名称。

`root: URL` 是书库根目录，类型选择了 `java.net.URL`，说明在模型层保存的是 URL 形式的路径，例如本地文件路径可能以 `file:` URL 表示。

`id: String = TsidCreator.getTsid256().toString()` 是书库唯一 ID。这里使用 `com.github.f4b6a3.tsid.TsidCreator` 生成 TSID，而不是数据库自增 ID。根据当前片段推断，Komga 倾向在领域对象创建时就拥有稳定 ID，随后由 DAO 写入数据库。

### 审计字段

`Library` 实现了 `Auditable`：

```kotlin
override val createdDate: LocalDateTime = LocalDateTime.now()
override val lastModifiedDate: LocalDateTime = createdDate
```

`Auditable` 只要求两个属性：`createdDate` 和 `lastModifiedDate`。这意味着 `Library` 对象本身携带创建时间和最后修改时间。默认情况下，刚创建的对象两者相同。

需要注意：`LibraryDao` 的插入片段中没有看到显式写入 `createdDate`、`lastModifiedDate` 的完整逻辑，可能由数据库默认值、jOOQ 生成字段、触发器或后续未读片段处理。根据当前片段只能确认模型层定义了这两个审计属性。

### 元数据导入开关

这些字段控制扫描书库时是否从不同来源导入元数据：

```kotlin
importComicInfoBook
importComicInfoSeries
importComicInfoCollection
importComicInfoReadList
importComicInfoSeriesAppendVolume
importEpubBook
importEpubSeries
importMylarSeries
importLocalArtwork
importBarcodeIsbn
```

从命名可以看出，Komga 支持多类元数据来源：

`ComicInfo` 用于漫画文件或旁路元数据，覆盖 book、series、collection、read list 等层级。

`Epub` 用于 EPUB 文件中的图书和系列元数据。

`Mylar` 用于 Mylar 风格的 series 元数据。

`LocalArtwork` 用于本地图片资源，比如封面或系列图。

`BarcodeIsbn` 用于从条形码或 ISBN 信息提取书籍信息。

这些字段默认大多为 `true`，说明 Komga 默认会尽量导入可识别的元数据。相关调用方包括 `BookMetadataLifecycle`、`SeriesMetadataLifecycle`、`LocalArtworkLifecycle`，以及 `infrastructure/metadata/...` 下的 provider，例如 `ComicInfoProvider`、`EpubMetadataProvider`、`MylarSeriesProvider`、`IsbnBarcodeProvider`。这些服务会根据 `Library` 的布尔开关判断是否跳过某类导入。

### 扫描策略字段

和扫描行为直接相关的字段包括：

```kotlin
scanForceModifiedTime: Boolean = false
scanOnStartup: Boolean = false
scanInterval: ScanInterval = ScanInterval.EVERY_6H
scanCbx: Boolean = true
scanPdf: Boolean = true
scanEpub: Boolean = true
scanDirectoryExclusions: Set<String> = emptySet()
```

`scanForceModifiedTime` 表示扫描时是否强制根据修改时间判断。具体判断逻辑不在本文件中，而在扫描相关服务中使用。

`scanOnStartup` 表示应用启动时是否扫描该书库。对应的调用方在调度或启动扫描控制器中。

`scanInterval` 表示周期扫描频率，默认每 6 小时。

`scanCbx`、`scanPdf`、`scanEpub` 控制扫描时是否纳入不同文件类型。CBX 通常泛指漫画压缩包格式，比如 CBZ、CBR 等；PDF 和 EPUB 单独作为开关。

`scanDirectoryExclusions` 是需要排除的目录集合。`LibraryDao` 中通过 `LIBRARY_EXCLUSIONS` 表单独保存这些排除项，读取时再聚合回 `Set<String>`。

### 自动维护字段

```kotlin
repairExtensions: Boolean = false
convertToCbz: Boolean = false
emptyTrashAfterScan: Boolean = false
```

`repairExtensions` 表示是否自动修复扩展名不匹配的书籍文件。

`convertToCbz` 表示是否自动转换为 CBZ。

`emptyTrashAfterScan` 表示扫描后是否清空回收站或删除已标记移除的内容。

这些字段不是在 `Library` 内部执行动作，而是由 `LibraryLifecycle`、`TaskEmitter`、`BookConverter`、`LibraryContentLifecycle` 等服务读取后触发任务。

在 `LibraryLifecycle.updateLibrary` 中可以看到：当 `repairExtensions` 从 `false` 变为 `true` 时，会触发 `taskEmitter.repairExtensions(...)`；当 `convertToCbz` 从 `false` 变为 `true` 时，会触发查找可转换书籍的任务。

### 封面策略字段

```kotlin
seriesCover: SeriesCover = SeriesCover.FIRST
```

它决定系列封面从哪本书中选取。内部枚举 `SeriesCover` 有四个值：

```kotlin
FIRST
FIRST_UNREAD_OR_FIRST
FIRST_UNREAD_OR_LAST
LAST
```

含义分别可以理解为：

`FIRST`：使用系列第一本。

`FIRST_UNREAD_OR_FIRST`：优先使用第一本未读书；如果没有未读，则回退到第一本。

`FIRST_UNREAD_OR_LAST`：优先使用第一本未读书；如果没有未读，则回退到最后一本。

`LAST`：使用系列最后一本。

调用方之一是 `SeriesLifecycle`，它会根据 `Library.SeriesCover` 选择对应的 book ID 作为系列封面来源。

### 哈希和分析字段

```kotlin
hashFiles: Boolean = true
hashPages: Boolean = false
hashKoreader: Boolean = false
analyzeDimensions: Boolean = true
```

`hashFiles` 控制是否计算文件级哈希，默认开启。

`hashPages` 控制是否计算页面级哈希，默认关闭。

`hashKoreader` 控制是否计算 KOReader 相关哈希，默认关闭。

`analyzeDimensions` 控制是否分析页面尺寸，默认开启。

在 `LibraryLifecycle.updateLibrary` 中，如果某个哈希开关从关闭变为开启，会触发对应任务，例如 `hashBooksWithoutHash`、`hashBooksWithoutHashKoreader`、`findBooksWithMissingPageHash`。这说明这些字段不仅影响未来扫描，也会在配置变化时补跑已有数据的处理任务。

### 特殊目录和可用性字段

```kotlin
oneshotsDirectory: String? = null
unavailableDate: LocalDateTime? = null
```

`oneshotsDirectory` 用于配置 one-shot 单本作品目录。相关 provider 有 `OneShotSeriesProvider`，它可能根据这个目录把单本书组织成系列。根据当前片段推断，更新这个字段会导致重新扫描，因为 `LibraryLifecycle.checkLibraryShouldRescan` 明确比较了 `oneshotsDirectory`。

`unavailableDate` 表示书库不可用的时间。如果不为 `null`，在 REST DTO 中会映射成 `unavailable = true`。这通常用于标记根目录不可访问、磁盘未挂载或远程路径暂时不可用等状态。

### `ScanInterval` 枚举

```kotlin
enum class ScanInterval {
  DISABLED,
  HOURLY,
  EVERY_6H,
  EVERY_12H,
  DAILY,
  WEEKLY,
}
```

这是周期扫描的领域枚举。

`LibraryScanScheduler` 会把它转换为 `Duration`：

`HOURLY` 对应 1 小时。

`EVERY_6H` 对应 6 小时。

`EVERY_12H` 对应 12 小时。

`DAILY` 对应 1 天。

`WEEKLY` 对应 7 天。

`DISABLED` 不会注册定时任务，且不能转换成 `Duration`。

### `path` 派生属性

```kotlin
@delegate:Transient
val path: Path by lazy { this.root.toURI().toPath() }
```

这是一个从 `root` 派生出的本地文件系统路径。

它有几个重要点：

`path` 不是构造参数，而是类体里的只读属性。

它通过 `lazy` 延迟计算，只有访问 `library.path` 时才会把 `URL` 转成 `URI`，再转成 `Path`。

`@delegate:Transient` 标记的是 lazy delegate，避免序列化框架或持久化工具误处理这个委托对象。这里不是说 `path` 业务上不重要，而是说它是可由 `root` 重新计算出来的派生值。

`LibraryLifecycle.checkLibraryValidity` 会使用 `library.path` 检查根目录是否存在、是否为目录，以及是否与已有书库路径互相包含。

## 上下游关系

### 上游：谁创建或更新 `Library`

REST API 是一个主要入口。`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt` 中会构造 `Library(...)`，然后调用 `LibraryLifecycle.addLibrary(...)` 或 `LibraryLifecycle.updateLibrary(...)`。

DTO 层负责 API 对象和领域对象之间的转换。相关文件包括 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryDto.kt`、`ScanIntervalDto.kt`、`SeriesCoverDto.kt`。其中 `Library.toDto(includeRoot: Boolean)` 会把领域模型转换为接口返回值，并把 `scanInterval`、`seriesCover` 映射成对应 DTO 枚举。

数据库读取也是上游之一。`komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/LibraryDao.kt` 从 `LIBRARY` 表和 `LIBRARY_EXCLUSIONS` 表读取数据，然后映射成 `Library`。也就是说，应用启动、查询书库列表、处理扫描任务时拿到的 `Library` 通常来自这个 DAO。

### 下游：谁消费 `Library`

`LibraryLifecycle` 是最核心的领域服务消费者。它负责添加、更新、删除书库，并根据 `Library` 的字段判断后续任务。

添加书库时，`LibraryLifecycle.addLibrary` 会：

先验证路径和名称。

调用 `libraryRepository.insert(library)` 持久化。

调用 `taskEmitter.scanLibrary(library.id)` 触发扫描。

发布 `DomainEvent.LibraryAdded(library)`。

更新书库时，`LibraryLifecycle.updateLibrary` 会：

读取当前书库和其他书库。

重新校验路径、名称、路径嵌套关系。

调用 `libraryRepository.update(toUpdate)`。

如果 `scanInterval` 改变，调用 `libraryScanScheduler.scheduleScan(toUpdate)` 重建定时任务。

如果根路径、one-shot 目录、扫描文件类型、强制修改时间、目录排除项等变化，则触发重新扫描。

如果哈希、修复、转换开关从关闭变为开启，则触发对应补跑任务。

`LibraryScanScheduler` 消费 `Library.scanInterval` 和 `Library.id`。它用 `library.id` 作为注册表 key，并在定时任务触发时调用 `taskEmitter.scanLibrary(library.id)`。

`SeriesLifecycle` 消费 `Library.seriesCover`，决定系列封面来源。

`BookConverter`、`PageHashLifecycle`、`TaskEmitter` 等消费 `hashFiles`、`hashPages`、`hashKoreader`、`repairExtensions`、`convertToCbz` 等配置。

元数据 provider 和 lifecycle 消费各种 `import...` 字段，决定是否读取 ComicInfo、EPUB、Mylar、本地图片、ISBN 条码等元数据。

权限模型也会引用 `Library`。`KomgaUser.canAccessLibrary(library: Library)` 通过 `library.id` 判断用户是否可访问该书库。

## 运行/调用流程

### 新增书库流程

1. 用户通过 REST API 提交书库名称、根目录和扫描/导入配置。
2. `LibraryController` 根据请求构造 `Library` 对象。
3. `LibraryLifecycle.addLibrary(library)` 接管业务处理。
4. `checkLibraryValidity` 访问 `library.path`，把 `root` 转成 `Path`，检查路径是否存在、是否为目录、名称是否重复、路径是否与已有书库互相嵌套。
5. 校验通过后，`LibraryRepository.insert(library)` 保存书库。实际实现是 `LibraryDao`，它把大部分字段写入 `LIBRARY` 表，把 `scanDirectoryExclusions` 写入 `LIBRARY_EXCLUSIONS` 表。
6. `TaskEmitter.scanLibrary(library.id)` 发出扫描任务。
7. 发布 `DomainEvent.LibraryAdded(library)`，让其他监听者知道书库已添加。

这个流程里，`Library` 自己不做校验、不访问数据库、不发任务。它只是承载配置；真正的动作由 `LibraryLifecycle` 编排。

### 更新书库流程

1. API 或其他服务提交更新后的 `Library`。
2. `LibraryLifecycle.updateLibrary(toUpdate)` 读取当前所有书库，找出当前版本和其他书库。
3. 再次调用 `checkLibraryValidity` 校验路径、名称和嵌套关系。
4. `LibraryRepository.update(toUpdate)` 写回数据库。
5. 如果 `scanInterval` 改变，`LibraryScanScheduler.scheduleScan(toUpdate)` 会取消旧任务并按新频率注册定时扫描。
6. 如果影响扫描结果的字段发生变化，例如 `root`、`oneshotsDirectory`、`scanCbx`、`scanPdf`、`scanEpub`、`scanForceModifiedTime`、`scanDirectoryExclusions`，则触发一次重新扫描。
7. 如果某些后处理开关从关闭变为开启，例如 `hashFiles`、`hashKoreader`、`hashPages`、`repairExtensions`、`convertToCbz`，则触发相应补处理任务。
8. 发布 `DomainEvent.LibraryUpdated(toUpdate)`。

这里有一个重要设计：不是所有字段变化都会触发重扫。例如导入元数据开关变化是否触发立即重扫，从当前片段看不在 `checkLibraryShouldRescan` 中；根据当前片段推断，它可能只影响后续扫描或由其他入口触发元数据刷新。

### 周期扫描流程

1. 某个 `Library` 的 `scanInterval` 不是 `DISABLED`。
2. `LibraryScanScheduler.scheduleScan(library)` 注册一个 fixed-rate 任务。
3. 到时间后，定时任务记录日志并调用 `taskEmitter.scanLibrary(library.id)`。
4. 扫描任务处理器根据 `library.id` 再从仓储加载对应 `Library`，然后执行实际扫描。

`DISABLED` 是一个特殊值：它表示不注册周期扫描任务。`toDuration()` 对 `DISABLED` 会抛出异常，因此调度器必须先判断不是 `DISABLED`。

### 持久化读取流程

1. `LibraryDao.findAll()`、`findById()` 等方法查询 `LIBRARY` 表。
2. 查询会 left join `LIBRARY_EXCLUSIONS` 表。
3. `fetchGroups` 按主表记录分组，把多条 exclusion 聚合成 `Set<String>`。
4. `LibraryRecord.toDomain(...)` 构造 `Library`。
5. 字符串形式保存的 `scanInterval` 和 `seriesCover` 会通过 `Library.ScanInterval.valueOf(...)`、`Library.SeriesCover.valueOf(...)` 转回枚举。

这意味着数据库中的枚举值字符串必须和 Kotlin 枚举常量名一致，例如 `EVERY_6H`、`FIRST_UNREAD_OR_FIRST`。如果重命名枚举值，需要同步处理数据库兼容性或迁移。

## 小白阅读顺序

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt` 的构造参数，不要急着看服务层。把字段按“基础信息、导入开关、扫描开关、后处理开关、封面策略、哈希策略”分组理解。
2. 再看同目录的 `Auditable.kt`，确认 `Library` 为什么必须有 `createdDate` 和 `lastModifiedDate`。
3. 接着看 `Library.kt` 底部的两个 enum：`SeriesCover` 和 `ScanInterval`。这两个枚举虽然短，但会影响封面选择和周期扫描。
4. 然后看 `path` 属性，理解 `root: URL` 和 `path: Path` 的关系：`root` 是保存的原始根目录，`path` 是运行时派生出来用于文件系统检查的对象。
5. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`。这里能看到 `Library` 字段什么时候触发校验、扫描、哈希、修复和转换。
6. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/LibraryDao.kt`。重点看字段如何写入数据库，以及 `scanDirectoryExclusions` 为什么需要单独表。
7. 最后读 DTO 和调度相关文件：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryDto.kt`、`ScanIntervalDto.kt`、`SeriesCoverDto.kt`、`komga/src/main/kotlin/org/gotson/komga/application/scheduler/LibraryScanScheduler.kt`。这样可以把“API 展示”和“后台定时任务”串起来。

## 常见误区

### 误区一：以为 `Library` 会执行扫描

`Library` 不执行扫描。它只是描述“这个书库应该如何被扫描”。真正触发扫描的是 `TaskEmitter`，真正编排新增/更新后是否扫描的是 `LibraryLifecycle`，周期扫描由 `LibraryScanScheduler` 负责。

### 误区二：以为所有字段变化都会自动重扫

不是。`LibraryLifecycle.checkLibraryShouldRescan` 只比较了一部分字段：`root`、`oneshotsDirectory`、`scanCbx`、`scanPdf`、`scanEpub`、`scanForceModifiedTime`、`scanDirectoryExclusions`。这些字段变化会触发重新扫描。

而像 `importComicInfoBook`、`importEpubSeries` 这类元数据导入开关是否立即导致全库重扫，当前片段没有显示。根据当前片段推断，它们主要控制扫描或元数据处理时是否导入，而不一定在开关变化瞬间自动补跑。

### 误区三：把 `root` 和 `path` 当成同一个东西

`root` 是构造参数，类型是 `URL`，会被保存到数据库。

`path` 是派生属性，类型是 `Path`，由 `root.toURI().toPath()` 延迟计算得到，主要用于文件系统操作，比如 `Files.exists(library.path)` 和 `Files.isDirectory(library.path)`。

如果 `root` 不是能转换成本地文件系统路径的 URL，访问 `path` 时就可能出问题。根据当前服务逻辑，书库根目录明显被当成本地文件系统目录来校验。

### 误区四：忽略默认值的业务含义

`Library` 的默认值不是随便填的。比如：

`scanInterval` 默认 `EVERY_6H`，说明新书库默认会周期扫描。

`scanCbx`、`scanPdf`、`scanEpub` 默认都是 `true`，说明三类主流格式默认纳入扫描。

`hashFiles` 默认 `true`，说明文件哈希是基础能力。

`hashPages` 默认 `false`，说明页面级哈希成本可能更高或不是默认需求。

`analyzeDimensions` 默认 `true`，说明页面尺寸分析被视为常规处理。

读这类配置模型时，默认值往往比字段名更能体现产品行为。

### 误区五：认为 enum 可以随意改名

`ScanInterval` 和 `SeriesCover` 会通过 `toString()` 写入数据库，并通过 `valueOf(...)` 从数据库读回。也就是说，枚举常量名是持久化格式的一部分。随意把 `EVERY_6H` 改成 `EVERY_SIX_HOURS`，老数据就可能无法反序列化，除非同时写数据库迁移或兼容逻辑。

### 误区六：以为 `@delegate:Transient` 表示字段没有用

`@delegate:Transient` 标记的是 `lazy` 委托对象不参与序列化，不代表 `path` 没有业务价值。相反，`path` 在书库有效性校验中非常关键，只是它可以从 `root` 重新计算，不需要作为独立状态保存。
