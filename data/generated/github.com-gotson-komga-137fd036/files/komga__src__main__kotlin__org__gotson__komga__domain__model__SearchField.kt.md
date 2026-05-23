# 文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/SearchField.kt`

## 它负责什么
`SearchField` 是一个很小的枚举，用来表示“正则搜索要落在哪个系列字段上”。当前只定义了两个可选值：

- `TITLE`
- `TITLE_SORT`

从代码状态看，它已经被标记为 `@Deprecated("use SearchOperator.BeginsWith instead")`，说明它是旧的搜索表达方式，主要用于兼容历史接口或旧数据结构。  
根据当前片段推断，它的职责不是承载完整搜索逻辑，而只是作为“字段标识”在搜索请求、控制器和 DAO 之间传递。

## 关键组成
这个文件本身只有三层信息：

- `package org.gotson.komga.domain.model`：说明它属于领域模型层。
- `@Deprecated(...)`：表明它不建议继续作为新接口的首选方案。
- `enum class SearchField`：枚举主体，只有两个成员：
  - `TITLE`
  - `TITLE_SORT`

它本身没有方法、没有扩展属性，也没有序列化注解，功能非常单一。

## 上下游关系
它的上游主要有两处：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
  - 控制器接收搜索参数时，会把字符串字段名 `"title"`、`"title_sort"` 映射成 `SearchField.TITLE`、`SearchField.TITLE_SORT`。
  - 其他字段名会被丢弃为 `null`，说明这里只允许这两个历史字段。

- `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesSearch.kt`
  - `SeriesSearch.regexSearch` 的类型是 `Pair<String, SearchField>?`。
  - 也就是说，`SearchField` 只是旧版正则搜索条件的一部分。

它的下游主要有一处：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesDtoDao.kt`
  - 这里有 `SearchField.toColumn()` 的映射。
  - `TITLE` 对应数据库列 `d.TITLE`，`TITLE_SORT` 对应 `d.TITLE_SORT`。
  - 随后会把这个列拿去做 `likeRegex(...)` 过滤。

因此它实际连接的是“请求参数”与“数据库列”。

## 运行/调用流程
可以把它理解成一条旧版兼容链路：

1. 客户端发起系列搜索请求，并带上 regex 搜索参数。
2. `SeriesController` 读取参数，把字段名解析成 `SearchField`。
3. 生成 `SeriesSearch(regexSearch = Pair(pattern, field))`。
4. `SeriesDtoDao` 接收 `SeriesSearch`。
5. DAO 通过 `SearchField.toColumn()` 把枚举映射到 jOOQ 字段。
6. 最终用 `likeRegex(...)` 生成数据库条件并执行查询。

同时，文件上的弃用提示说明：新式搜索更推荐走 `SearchOperator.BeginsWith` 等操作符体系，而不是继续扩展 `SearchField`。

## 小白阅读顺序
建议按这个顺序看：

1. `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchField.kt`
2. `komga/src/main/kotlin/org/gotson/komga/domain/model/SeriesSearch.kt`
3. `komga/src/main/kotlin/org/gotson/komga/domain/model/SearchOperator.kt`
4. `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SeriesController.kt`
5. `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/SeriesDtoDao.kt`

这样能先理解“这个枚举是什么”，再看“它怎么被组装进请求”，最后看“它怎么落到数据库查询”。

## 常见误区
- 误区一：`SearchField` 还是当前主流搜索模型。  
  实际上它已经被 `@Deprecated` 标记，属于兼容旧接口的字段标识。

- 误区二：`TITLE_SORT` 是新的展示字段。  
  这里它只是一个搜索目标列，最终映射到数据库列 `TITLE_SORT`，不是 UI 展示逻辑。

- 误区三：它和 `SearchOperator` 是同一层概念。  
  不是。`SearchOperator` 描述的是“怎么比对”，`SearchField` 描述的是“比对哪个字段”。

- 误区四：它支持很多搜索字段。  
  不是，当前只有 `TITLE` 和 `TITLE_SORT` 两个值，控制器里也只接受这两个字段名。

- 误区五：弃用后就没用了。  
  也不是。根据当前代码，它仍然参与系列搜索的旧参数兼容和数据库查询映射。
