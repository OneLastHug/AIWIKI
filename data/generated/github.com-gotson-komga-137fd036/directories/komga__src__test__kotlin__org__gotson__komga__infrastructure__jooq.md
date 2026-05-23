# 目录：komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq

## 它负责什么

这个目录是 Komga 项目中 `infrastructure.jooq` 持久化层的集成测试集合，核心目标是验证基于 jOOQ 实现的 DAO、搜索查询、DTO 聚合查询、任务队列持久化等行为是否符合领域模型和 repository 接口的预期。

它不是单元测试目录，而是典型的 `@SpringBootTest` 集成测试：测试类会启动 Spring 上下文，注入真实的 DAO、Repository、Lifecycle 服务，在测试数据库中插入领域对象，然后通过 jOOQ DAO 查询、更新、删除，再用 AssertJ 断言结果。也就是说，这里的测试重点不是“某个函数内部怎么写”，而是“数据库表、jOOQ 映射、领域对象、查询条件、排序、分页、生命周期清理”能否串起来正常工作。

目标目录对应的生产代码主要在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq`，其中 `main` 子包覆盖主业务数据库访问，`tasks` 子包覆盖后台任务队列数据库访问。测试目录保持了类似结构：`main` 下是一组主业务 DAO 测试，`tasks` 下是任务 DAO 测试，根部的 `TestUtils.kt` 提供测试辅助常量。

## 关键组成

根目录下的 `TestUtils.kt` 很小，只定义了一个 `offset: TemporalUnitOffset = within(3, ChronoUnit.SECONDS)`。它用于时间字段断言，例如 `createdDate`、`lastModifiedDate`，避免数据库写入时间和测试执行时间之间的秒级误差导致测试不稳定。`BookDaoTest` 中就用它断言新增或更新后的时间接近当前时间。

`main/BookDaoTest.kt` 是基础 CRUD 型测试代表。它注入 `BookDao`、`SeriesRepository`、`LibraryRepository`，先创建 `Library` 和 `Series` 作为外键依赖，再测试 `BookDao.insert`、`update`、`findByIdOrNull`、`findAll`、`findAll(search, context, pageable)`、`findAllIdsByLibraryId`、`findAllIdsBySeriesId`、`deleteAll` 等行为。它说明 DAO 层直接面对数据库字段映射，例如 `url`、`fileLastModified`、`fileSize`、`fileHash`、`deletedDate`，同时也要维护审计字段 `createdDate`、`lastModifiedDate`。

`main/BookSearchTest.kt` 和 `main/SeriesSearchTest.kt` 是搜索逻辑测试代表。它们覆盖的不是简单 CRUD，而是复杂 `SearchCondition` 如何被 jOOQ 转成 SQL 条件。测试中会构造 `BookSearch` 或 `SeriesSearch`，使用 `SearchOperator.Is`、`IsNot`、布尔条件、组合条件等，再分别调用实体 DAO 和 DTO DAO，例如 `BookDao`/`BookDtoDao`、`SeriesDao`/`SeriesDtoDao`。从片段看，测试覆盖了 library、series、read list、collection、deleted 状态等维度，还会校验 `UnpagedSorted(Sort.by(...))` 对 read list 或 collection 序号排序的影响。这里的一个重要细节是：基础实体 DAO 的排序有时“不保证”，而 DTO DAO 会保留 read list 或 collection 中的顺序，这在测试注释中有明确体现。

`main` 目录还包括大量按聚合或实体划分的测试文件，例如 `LibraryDaoTest.kt`、`SeriesDaoTest.kt`、`SeriesDtoDaoTest.kt`、`BookDtoDaoTest.kt`、`BookMetadataDaoTest.kt`、`SeriesMetadataDaoTest.kt`、`BookMetadataAggregationDaoTest.kt`、`MediaDaoTest.kt`、`ReadProgressDaoTest.kt`、`ReadListDaoTest.kt`、`SeriesCollectionDaoTest.kt`、`PageHashDaoTest.kt`、`KomgaUserDaoTest.kt`、`ServerSettingsDaoTest.kt`、`ClientSettingsDtoDaoTest.kt`。这些名字基本对应生产目录里的 DAO，例如 `BookDao.kt`、`BookDtoDao.kt`、`SeriesDao.kt`、`SeriesDtoDao.kt`、`BookMetadataDao.kt`、`ReadProgressDao.kt` 等。根据当前片段推断，这些测试大多采用同一种模板：准备领域对象，调用 repository/DAO/lifecycle 写入数据，再断言 DAO 查询、更新、删除、聚合或排序结果。

`tasks/TasksDaoTest.kt` 是任务队列持久化测试。它注入 `TasksDao`，操作领域任务 `Task.AnalyzeBook`、`Task.ConvertBook`、`Task.ScanLibrary`、`Task.HashBookPages` 等。测试重点包括：保存多个任务后能恢复正确子类型和字段；相同唯一任务再次保存会覆盖；空队列 `takeFirst()` 返回 `null`；`takeFirst(owner)` 会把任务标记为指定线程 owner；`findAllGroupedByOwner()` 能按 owner 分组；有 `groupId` 的任务同一组同时只能被一个 owner 占用；没有 group 的任务可以全部被并发领取；`deleteAllWithoutOwner()` 只删除未被 owner 占用的任务。这个文件直接反映 Komga 后台任务调度的持久化语义。

## 上下游关系

上游输入主要来自领域层模型和查询对象，包括 `Book`、`Series`、`Library`、`ReadList`、`SeriesCollection`、`KomgaUser`、`ReadProgress`、`Media`、`Task`、`SearchCondition`、`SearchOperator`、`SearchContext`、`BookSearch`、`SeriesSearch` 等。测试通过 `makeBook`、`makeSeries`、`makeLibrary` 这类工厂函数快速构造领域对象。

被测对象位于基础设施层，主要是 `org.gotson.komga.infrastructure.jooq.main` 和 `org.gotson.komga.infrastructure.jooq.tasks` 下的 DAO。主业务 DAO 对接领域 repository 接口，例如 `BookRepository`、`SeriesRepository`、`LibraryRepository`、`ReadProgressRepository`、`BookMetadataRepository`、`SeriesCollectionRepository` 等；任务 DAO 则服务于应用任务系统 `org.gotson.komga.application.tasks.Task`。

测试还会调用 `BookLifecycle`、`SeriesLifecycle`、`LibraryLifecycle`、`KomgaUserLifecycle`、`SeriesMetadataLifecycle` 等领域服务。它们不是被测核心，但用于创建或删除带有副作用的聚合对象。例如搜索测试中使用 lifecycle 创建 series、添加 books、删除用户和 library，是为了让数据库状态更接近真实业务流程，而不是只插单表数据。

下游结果是数据库中的记录和查询返回的领域对象/DTO。测试断言这些结果的字段、数量、顺序、分组、时间戳和空值行为。对于会发布事件的生命周期操作，测试中通过 `@MockkBean ApplicationEventPublisher` 屏蔽真实事件发布，并用 `every { mockEventPublisher.publishEvent(any()) } just Runs` 保持流程可执行。

## 运行/调用流程

典型测试流程可以概括为五步。

第一步，Spring Boot 启动测试上下文。测试类通过构造函数注入 DAO、Repository、Lifecycle 服务。因为使用 `@SpringBootTest`，这些测试依赖完整的应用配置、jOOQ 配置、事务/数据源和数据库 schema。

第二步，在 `@BeforeAll` 或测试方法内部准备基础数据。比如 `BookDaoTest` 先插入 `Library`，再插入属于该 library 的 `Series`，之后才能插入 `Book`。搜索测试会准备两个 library、两个 user、多个 series 或 book，用于验证正反条件。

第三步，调用被测 DAO。简单测试直接调用 `insert`、`update`、`findByIdOrNull`、`findAll`、`deleteAll`；搜索测试调用 `findAll(search.condition, SearchContext(user), Pageable或UnpagedSorted)`；任务测试调用 `save`、`takeFirst`、`hasAvailable`、`findAllGroupedByOwner`、`deleteAllWithoutOwner`。

第四步，用 AssertJ 验证行为。字段断言会检查 URL、文件大小、hash、删除时间等持久化字段；时间断言使用 `offset` 忽略少量时间漂移；搜索断言常用 `containsExactlyInAnyOrder` 或 `containsExactly` 区分“只关心集合内容”和“必须保序”；任务断言还会检查返回对象的实际子类。

第五步，清理数据。多数测试在 `@AfterEach` 删除测试中创建的聚合，并断言 count 归零；在 `@AfterAll` 删除跨测试复用的 library、user 等基础数据。这个清理模式很关键，因为这些是集成测试，共享测试数据库状态会影响后续用例。

## 小白阅读顺序

建议先看 `komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/TestUtils.kt`，理解为什么时间断言要允许几秒偏差。

然后看 `komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDaoTest.kt`。这个文件最接近传统 DAO 学习路径：插入、更新、按 id 查询、查询全部、按外键查询、删除。读完它后，你会明白测试数据如何依赖 `Library`、`Series`、`Book` 三层关系，也能看到领域对象和数据库字段的映射方式。

第三步看 `komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main/BookSearchTest.kt` 或 `SeriesSearchTest.kt`。重点不是逐行背测试，而是观察 `SearchCondition`、`SearchOperator`、`SearchContext`、`Pageable`、`Sort` 如何组合。这里能学到 Komga 的动态搜索系统怎样被 DAO 层消费。

第四步看 DTO 相关测试，例如 `BookDtoDaoTest.kt`、`SeriesDtoDaoTest.kt`，再回头对照生产代码中的 `BookDtoDao.kt`、`SeriesDtoDao.kt`。DTO DAO 往往比实体 DAO 多拿一些聚合信息或用户相关状态，因此更接近 API 层实际要返回的数据。

第五步看 `tasks/TasksDaoTest.kt`。它和主业务 DAO 不同，关注后台任务队列的领取、owner、优先级、group 限制和覆盖保存。这个文件适合理解 Komga 如何把后台任务持久化，并防止同一组任务被并发处理。

最后再按业务兴趣阅读其他测试：想看书籍元数据就读 `BookMetadataDaoTest.kt`、`BookMetadataAggregationDaoTest.kt`；想看阅读状态就读 `ReadProgressDaoTest.kt`；想看用户设置和服务器设置就读 `KomgaUserDaoTest.kt`、`ServerSettingsDaoTest.kt`、`ClientSettingsDtoDaoTest.kt`。

## 常见误区

第一个误区是把这些测试当成纯单元测试。它们使用 `@SpringBootTest`，注入真实 Spring bean，并依赖数据库 schema 和 jOOQ 映射，性质上是集成测试。阅读时要关注“对象如何穿过 Spring、repository、DAO、数据库再回来”，而不是只盯单个函数。

第二个误区是忽略外键和生命周期。比如 book 不能孤立存在，通常要先有 library 和 series；删除 series、library、user 时也经常通过 lifecycle 完成，因为真实业务里可能伴随事件、级联清理或关联表维护。测试里 mock 掉 `ApplicationEventPublisher`，并不表示事件机制不存在，只是避免事件副作用干扰 DAO 验证。

第三个误区是认为 `BookDao` 和 `BookDtoDao`、`SeriesDao` 和 `SeriesDtoDao` 完全等价。根据当前片段，实体 DAO 和 DTO DAO 都能搜索，但在 read list、collection 这类带序号的关联场景中，DTO DAO 更强调返回顺序和聚合信息，实体 DAO 有时只保证结果集合正确。

第四个误区是把 `SearchContext.empty()` 和 `SearchContext(user)` 看成无关紧要。搜索测试引入 user、read progress、内容限制等上下文，说明查询结果可能和当前用户有关。即使某些用例只测 library 或 series，真实搜索链路仍可能使用上下文判断可见性、阅读状态或限制条件。

第五个误区是忽略任务的 `groupId`。`TasksDaoTest` 明确验证了有 group 的任务同一时间不能被多个 owner 大量领取，而无 group 的任务可以全部并发领取。这不是普通队列的先入先出测试，而是 Komga 后台任务调度策略的一部分。

第六个误区是用纳秒级精度理解时间字段。数据库、JVM 和测试执行之间会有时间精度差异，所以测试用 `offset` 和 `isEqualToIgnoringNanos`。如果新增 DAO 测试时直接比较完整 `LocalDateTime`，很容易得到偶发失败。
