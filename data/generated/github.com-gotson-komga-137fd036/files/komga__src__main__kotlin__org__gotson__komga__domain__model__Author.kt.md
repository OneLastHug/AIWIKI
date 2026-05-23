# 文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/Author.kt`

## 它负责什么

`Author` 是一个很轻量的领域值对象，用来统一表示“作者/贡献者”的两个核心字段：`name` 和 `role`。它本身不依赖数据库、控制器或序列化框架，只负责把外部传进来的作者信息规范化成稳定的内存表示，供元数据、搜索、接口返回和持久化映射复用。

它的设计重点不是“存数据”，而是“规范数据”：
- `name` 会去掉首尾空白
- `role` 会去掉首尾空白并转成小写
- `equals` / `hashCode` 基于规范化后的值工作

这意味着它适合做集合元素、去重键、比较对象，而不是一个带行为的复杂实体。

## 关键组成

这个文件非常短，核心就三部分：

1. 构造与规范化
   - 构造参数是 `name: String`、`role: String`
   - 内部实际保存的 `val name`、`val role` 是规范化后的结果
   - 这里没有空值处理，也没有 blank 校验，所以空字符串仍然可能存在

2. `toString()`
   - 输出格式固定为 `Author($name, $role)`
   - 方便日志、调试和排查元数据来源

3. `equals()` / `hashCode()`
   - 手写实现，不是 `data class`
   - 比较时只看规范化后的 `name` 和 `role`
   - `role` 已小写，因此 `Writer` 和 `writer` 会被视为同一个角色
   - `name` 只做 trim，不做大小写归一，所以名字比较仍然区分大小写

根据当前片段推断，这里没有使用 `data class`，大概率是为了把“构造时归一化”与“值语义比较”固定下来，避免不同调用点各自处理不一致。

## 上下游关系

上游，也就是谁在创建 `Author`：

- `infrastructure/web/AuthorsHandlerMethodArgumentResolver.kt`：把请求参数 `author=name,role` 解析成 `List<Author>`
- `infrastructure/metadata/epub/EpubMetadataProvider.kt`：从 EPUB 的 `creator` 和 `relator` 元数据里构造作者
- `infrastructure/jooq/main/ReferentialDao.kt`、`BookMetadataDao.kt`：把数据库记录映射回领域对象
- `interfaces/api/rest/dto/BookMetadataUpdateDto.kt`：把补丁 DTO 里的作者信息转成领域对象
- `interfaces/api/rest/ReadListController.kt`、`SeriesController.kt`、`SeriesCollectionController.kt`：把请求里的作者过滤条件转成 `SearchCondition`

下游，也就是谁在消费 `Author`：

- `BookMetadata`、`BookMetadataPatch`、`BookMetadataAggregation`：把作者作为书籍元数据的一部分持有
- `interfaces/api/rest/dto/AuthorDto.kt`：对外返回时直接用 `name`、`role`
- `SearchCondition.Author`：用于作者条件搜索
- `ReferentialRepository` / `ReferentialDao`：作者列表查询、分页查询、过滤查询

这条链路说明 `Author` 是系统里作者语义的统一中间层，连接了“导入”“查询”“展示”“存储”四个方向。

## 运行/调用流程

1. 外部输入进入系统
   - 例如查询参数 `author=Alan Moore,writer`
   - 或 EPUB 里的 `<creator>` 元数据
   - 或数据库中已经存好的作者记录

2. 解析阶段创建 `Author`
   - `AuthorsHandlerMethodArgumentResolver` 会按 `name,role` 拆分
   - `EpubMetadataProvider` 会把解析到的作者名和角色映射成 `Author`
   - `Dao` 层会把记录字段重建成 `Author`

3. 规范化生效
   - `name` 去首尾空白
   - `role` 去首尾空白并小写化
   - 这样后续比较、去重、存储都能保持一致

4. 进入业务对象
   - `BookMetadata.authors`、`BookMetadataPatch.authors` 直接保存 `List<Author>`
   - API 层把它转成 `AuthorDto` 返回前端
   - 搜索层把它拆成 `SearchCondition.Author(...)` 做匹配

5. 比较和集合操作
   - 因为 `equals` / `hashCode` 已定义，`List` 去重、`Set` 收集、缓存键比较时会按规范化后的值判断

## 小白阅读顺序

建议按这个顺序看：

1. `komga/src/main/kotlin/org/gotson/komga/domain/model/Author.kt`
   - 先看它怎么规范化字符串、怎么定义相等性

2. `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadata.kt`
   - 看作者如何作为书籍元数据的一部分被保存和复制

3. `komga/src/main/kotlin/org/gotson/komga/domain/model/BookMetadataPatch.kt`
   - 看作者如何作为“可部分更新”的补丁字段传递

4. `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/AuthorsHandlerMethodArgumentResolver.kt`
   - 看请求参数如何转成 `Author`

5. `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/epub/EpubMetadataProvider.kt`
   - 看外部文件元数据如何转成 `Author`

6. `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/AuthorDto.kt`
   - 看它如何对外输出

## 常见误区

1. 以为它是 `data class`
   - 不是。它手写了 `equals`、`hashCode`、`toString`，重点是控制规范化逻辑。

2. 以为 `role` 原样保留
   - 不是，`role` 会被转小写。这个细节很关键，影响搜索和比较。

3. 以为 `name` 也会大小写归一
   - 不会，只有 trim，没有 lowercase。

4. 以为构造时已经做了空值校验
   - 没有。`Author("   ", "writer")` 会变成空名字；是否允许要看上游调用点。

5. 以为它只在 API 层使用
   - 不是，它同时贯穿元数据导入、数据库映射、搜索条件和 DTO 返回，是一个典型的领域共享值对象。
