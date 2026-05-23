# 目录：komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main

## 它负责什么

这个目录是一组围绕 `org.gotson.komga.infrastructure.jooq.main` 的集成测试，核心目标不是实现业务，而是验证这一层的 jOOQ 持久化访问代码是否正确。

从文件命名和内容看，它覆盖了几类对象：

- 基础实体 DAO：`BookDaoTest.kt`、`SeriesDaoTest.kt`、`KomgaUserDaoTest.kt`、`LibraryDaoTest.kt`、`MediaDaoTest.kt`、`ReadProgressDaoTest.kt` 等
- DTO / 投影 DAO：`BookDtoDaoTest.kt`、`SeriesDtoDaoTest.kt`、`ClientSettingsDtoDaoTest.kt`
- 搜索相关测试：`BookSearchTest.kt`、`SeriesSearchTest.kt`、`BookSearchTest.kt`
- 聚合与元数据：`BookMetadataDaoTest.kt`、`SeriesMetadataDaoTest.kt`、`BookMetadataAggregationDaoTest.kt`
- 其它辅助表/关系：`ReadListDaoTest.kt`、`SeriesCollectionDaoTest.kt`、`PageHashDaoTest.kt`、`ServerSettingsDaoTest.kt`

根据当前片段推断，这个目录的职责可以概括为：用真实的 Spring 容器和数据库上下文，验证主库 `jooq` 层的增删改查、复杂查询、排序分页、关联映射、读进度计算、设置存取等行为。

## 关键组成

这个目录里的测试大多是 `@SpringBootTest`，说明它们不是单元测试，而是带上下文的集成测试。

几个代表性文件的关注点很清楚：

- `BookDaoTest.kt`
  - 验证 `Book` 的插入、更新、按 id 查找、按 libraryId / seriesId 查询、删除
  - 关注时间字段、文件大小、hash、删除时间等持久化字段是否正确落库
- `SeriesDaoTest.kt`
  - 验证 `Series` 的基础 CRUD
  - 关注 `bookCount`、`deletedDate`、`fileLastModified` 等字段
- `ReadProgressDaoTest.kt`
  - 验证阅读进度的新增和覆盖更新
  - 关注 `page`、`completed`、`readDate` 和时间戳一致性
- `ServerSettingsDaoTest.kt`
  - 验证服务端设置的键值写入、读取、覆盖、删除
  - 是最轻量的一类设置 DAO 测试
- `ClientSettingsDtoDaoTest.kt`
  - 验证全局和按用户保存的客户端设置 DTO
  - 说明这个目录不只测实体表，也测面向 API DTO 的持久化映射
- `BookMetadataAggregationDaoTest.kt`
  - 验证书籍元数据聚合表的作者、标签、发布日期、摘要等字段
  - 还覆盖最小对象、完整对象、更新回写和异常场景
- `BookSearchTest.kt`、`BookDtoDaoTest.kt`
  - 验证复杂搜索条件，例如 `SearchCondition.LibraryId`、`SearchCondition.SeriesId`、`SearchCondition.ReadListId`
  - 验证多条件组合、去重、排序、分页、`SearchContext` 对查询结果的影响
- `SeriesDtoDaoTest.kt`
  - 验证按阅读状态筛选系列，以及按标题排序
  - 说明 DTO 层不仅是字段搬运，还承载了查询视图和聚合统计
- `KomgaUserDaoTest.kt`
  - 验证用户角色、共享库、内容限制、邮箱大小写查找等行为
  - 这类测试能看出用户模型比普通 CRUD 更复杂

这些测试普遍使用 `makeBook`、`makeSeries`、`makeLibrary` 之类的测试工厂函数，说明它们依赖领域层的构造器来生成基础数据，再通过 repository、lifecycle 或 DAO 完成入库和查询。

## 上下游关系

上游是领域模型与服务层，下游是 `jooq main` 的生产实现。

上游输入主要有三类：

- 领域模型：`Book`、`Series`、`KomgaUser`、`ReadProgress`、`BookMetadataAggregation`、`ReadList` 等
- 查询条件模型：`BookSearch`、`SeriesSearch`、`SearchCondition`、`SearchOperator`、`SearchContext`
- 领域服务和仓储接口：`BookRepository`、`SeriesRepository`、`LibraryRepository`、`ReadProgressRepository`、`BookLifecycle`、`SeriesLifecycle`、`LibraryLifecycle`、`KomgaUserLifecycle`

下游主要是这些生产类：

- `BookDao`、`SeriesDao`、`KomgaUserDao`
- `BookDtoDao`、`SeriesDtoDao`、`ClientSettingsDtoDao`
- `BookMetadataDao`、`SeriesMetadataDao`、`BookMetadataAggregationDao`
- `ServerSettingsDao`
- 以及其它同包的 DAO / 查询对象

从测试写法可以看出，它们还依赖一些横切基础设施：

- `ApplicationEventPublisher`，在 `BookSearchTest.kt`、`BookDtoDaoTest.kt`、`SeriesDtoDaoTest.kt` 中被 mock 掉
- `SearchIndexLifecycle`，搜索类测试会在清理后重建索引
- `UnpagedSorted`，用于在不分页的情况下强制带排序查询

根据当前片段推断，这些测试验证的是“领域服务已经把数据准备好之后，DAO 层是否能正确读写和投影”，而不是验证领域规则本身。领域规则更多在 `domain.service` 和 `domain.model` 一侧。

## 运行/调用流程

这一目录里的测试流程基本一致，可以按下面理解：

1. Spring 启动测试容器  
   `@SpringBootTest` 加载完整上下文，注入 DAO、repository、lifecycle、事件发布器等组件。

2. 预置公共数据  
   在 `@BeforeAll` 中插入库、系列、用户等公共前置数据，保证后续用例能引用有效外键。

3. 每个用例构造业务数据  
   例如插入书籍、写入阅读进度、更新元数据、创建阅读列表、保存设置。

4. 调用目标 DAO 或查询对象  
   例如：
   - `bookDao.insert(...)`
   - `bookDtoDao.findAll(...)`
   - `seriesDao.findAllByLibraryId(...)`
   - `serverSettingsDao.saveSetting(...)`

5. 断言落库结果或查询结果  
   重点检查：
   - 主键是否生成
   - 时间字段是否接近当前时间
   - 更新后是否保留创建时间、刷新修改时间
   - 查询结果是否符合条件、排序和分页
   - DTO 是否带上关联字段、阅读状态、聚合统计

6. 清理测试数据  
   `@AfterEach` / `@AfterAll` 中删除 books、series、users、libraries、read progress、settings 等，避免样例互相污染。

搜索类测试的调用链会更长一点：

- 先通过 `seriesLifecycle.createSeries(...)`、`seriesLifecycle.addBooks(...)` 等把书系和书籍建立起来
- 再通过 `readProgressRepository.save(...)`、`bookMetadataRepository.update(...)` 等补充可搜索属性
- 然后用 `BookSearch` 或 `SeriesSearch` 组装条件
- 最后调用 `bookDao.findAll(...)` 或 `bookDtoDao.findAll(...)`、`seriesDtoDao.findAll(...)`

这里的关键点是，`SearchContext(user)` 会影响可见性和筛选结果，`SearchCondition` 决定过滤逻辑，`Pageable` / `UnpagedSorted` 决定排序分页策略。

## 小白阅读顺序

如果你是第一次看这个目录，建议按下面顺序读：

1. `ServerSettingsDaoTest.kt`
   - 最简单，先理解“保存、读取、覆盖、删除”这种最基础的 DAO 形态

2. `ClientSettingsDtoDaoTest.kt`
   - 看清楚“全局设置”和“用户设置”两套键值空间的区别

3. `KomgaUserDaoTest.kt`
   - 了解用户实体比普通记录复杂在哪里，比如角色、共享库、内容限制

4. `SeriesDaoTest.kt`、`BookDaoTest.kt`
   - 先理解基础实体的 CRUD 和时间字段规则

5. `ReadProgressDaoTest.kt`
   - 观察“同一条记录重复写入时是更新而不是新增”的模式

6. `BookMetadataAggregationDaoTest.kt`
   - 了解聚合表是怎么存作者、标签、摘要、发布日期的

7. `BookDtoDaoTest.kt`、`SeriesDtoDaoTest.kt`
   - 进入 DTO / 查询投影层，理解为什么同一批数据会有“实体 DAO”和“DTO DAO”两套读法

8. `BookSearchTest.kt`、`SeriesSearchTest.kt`
   - 最后看复杂搜索，重点关注 `SearchCondition`、`SearchContext` 和排序分页组合

如果想建立全局心智模型，最好同时盯着：
- 领域模型：`Book`、`Series`、`KomgaUser`
- 查询模型：`BookSearch`、`SeriesSearch`、`SearchCondition`
- 生命周期服务：`BookLifecycle`、`SeriesLifecycle`、`LibraryLifecycle`
- 仓储接口：`BookRepository`、`SeriesRepository` 等

## 常见误区

1. 把这里当成业务实现目录  
   这是测试目录，不是生产代码。真正的实现一般在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main`。

2. 以为它们是纯单元测试  
   不是。`@SpringBootTest` 说明它们跑在 Spring 容器里，通常会连到测试数据库，依赖真实 bean 协作。

3. 只看 `DAO` 名字，不看 `DTO` 名字  
   `BookDao` 和 `BookDtoDao` 不是一回事。前者偏实体表，后者偏查询投影和联表结果，字段和排序语义都可能不同。

4. 忽略 `SearchContext`  
   搜索测试里用户上下文很关键，它会影响权限、可见性、读取状态等过滤结果。

5. 忽略清理和索引重建  
   这类测试常常在 `@AfterEach` 清数据，有些还要 `searchIndexLifecycle.rebuildIndex()`。如果漏掉这个步骤，测试之间会互相污染。

6. 把排序断言写死成唯一顺序  
   有些测试明确写了 `containsExactlyInAnyOrder`，说明底层查询顺序未必稳定，或者业务只关心集合内容不关心顺序。

7. 误读时间断言  
   这里常用 `isCloseTo(now, offset)`、`isEqualToIgnoringNanos(...)`，说明数据库写入会带纳秒误差或时间精度裁剪，不能直接做完全相等比较。

8. 以为搜索结果和实体读取一定一致  
   `BookDao` 和 `BookDtoDao`、`SeriesDao` 和 `SeriesDtoDao` 的结果集不一定完全相同，DTO 层通常会带聚合字段、排序字段和关联状态。根据当前片段推断，测试就是在专门防止这两层行为漂移。
