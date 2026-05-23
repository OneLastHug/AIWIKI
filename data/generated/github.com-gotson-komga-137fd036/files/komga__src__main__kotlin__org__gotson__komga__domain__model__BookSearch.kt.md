# 文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/BookSearch.kt`

## 它负责什么

`BookSearch` 是书籍检索请求的领域模型封装，作用很单纯：把“结构化筛选条件”和“全文检索字符串”放在同一个对象里，作为书籍查询的统一输入。

它只有两个字段：

- `condition: SearchCondition.Book?`：结构化搜索条件，类型受 `SearchCondition.Book` 这组封闭接口约束。
- `fullTextSearch: String?`：全文检索文本，通常用于模糊搜索、关键词搜索或带语法的检索表达式。

类上使用了 `@JsonInclude(JsonInclude.Include.NON_NULL)`，意思是序列化成 JSON 时会省略 `null` 字段。这样请求和响应都更简洁，也适合 API 场景里按需传参。

## 关键组成

- `data class BookSearch(...)`：Kotlin 数据类，天然支持值语义、`equals`、`copy`、反序列化。
- `condition: SearchCondition.Book?`：这是核心的结构化过滤入口。
- `fullTextSearch: String?`：这是全文搜索入口，和结构化条件并存，不互斥。
- `@JsonInclude(JsonInclude.Include.NON_NULL)`：Jackson 序列化配置，避免把未设置的字段输出到 JSON。

这个文件本身不包含任何查询逻辑，它只是一个“请求载体”。真正的条件解析、SQL 生成、全文索引检索，都在别的层完成。

## 上下游关系

上游主要是 API 层和内部服务层构造它：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ReadListController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v1/OpdsController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds/v2/Opds2Controller.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/service/SyncPointLifecycle.kt`

这些地方会把用户输入、OPDS 参数或内部筛选条件组装成 `BookSearch` 再往下传。

下游主要是仓储和查询实现：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/persistence/BookDtoRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/BookRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/domain/persistence/SyncPointRepository.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDtoDao.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDao.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SyncPointDao.kt`

`SearchCondition.Book` 决定了能筛哪些字段；`fullTextSearch` 则会进入 DAO 的全文检索分支。根据当前片段推断，`BookSearch` 是把这两条查询通道统一起来的边界对象。

测试也围绕它做序列化和查询验证：

- `komga/src/test/kotlin/org/gotson/komga/domain/model/BookSearchTest.kt`
- `komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main/BookSearchTest.kt`
- `komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDtoDaoTest.kt`

## 运行/调用流程

1. API 或服务层接收请求参数。
2. 调用方构造 `BookSearch(condition = ..., fullTextSearch = ...)`。
3. 把 `BookSearch` 传给仓储接口，例如 `BookDtoRepository.findAll(search, context, pageable)` 或 `BookRepository.findAll(searchCondition, searchContext, pageable)` 这一类入口。
4. `BookSearchHelper` 读取 `SearchCondition.Book`，把结构化条件翻译成 JOOQ `Condition`，同时补齐需要的 join。
5. DAO 层根据 `fullTextSearch` 决定是否启用全文检索、相关性排序或额外的索引查询。
6. 最终返回分页结果。

`BookSearchTest` 证明了这个对象支持完整的 JSON round-trip：序列化后再反序列化，字段和值应保持一致。`BookSearchHelper` 则负责把结构化条件落到数据库查询。

## 小白阅读顺序

1. 先看 `komga/src/main/kotlin/org/gotson/komga/domain/model/BookSearch.kt`，确认它只有两个字段，没有隐藏逻辑。
2. 再看 `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchCondition.kt`，理解 `SearchCondition.Book` 支持哪些筛选项。
3. 接着看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/BookSearchHelper.kt`，搞清楚条件如何变成 SQL。
4. 然后看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/persistence/BookDtoRepository.kt` 和 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/BookRepository.kt`，了解它在哪里被当作查询参数使用。
5. 最后看 `komga/src/test/kotlin/org/gotson/komga/domain/model/BookSearchTest.kt` 和 `komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main/BookDtoDaoTest.kt`，把输入、序列化、查询结果串起来。

## 常见误区

- 误以为 `BookSearch` 自己负责搜索逻辑。实际上它只是参数对象，真正的检索逻辑在 `BookSearchHelper`、DAO 和全文索引层。
- 误以为 `condition` 和 `fullTextSearch` 是二选一。实际上它们可以同时存在，系统通常会把结构化过滤和全文搜索一起叠加。
- 误把 `SearchCondition.Book` 和 `SearchCondition.Series` 混为一谈。前者只能用于书籍查询，类型层面已经区分开了。
- 误以为 `@JsonInclude(NON_NULL)` 会改变查询语义。它只影响 JSON 输出格式，不影响业务逻辑。
- 误以为这个文件很“简单”就没有上下游关系。实际上它是 API、仓储、JOOQ、全文搜索之间的统一入口，位置很小，作用不小。
