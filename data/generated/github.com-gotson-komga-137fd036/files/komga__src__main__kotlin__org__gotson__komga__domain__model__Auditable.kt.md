# 文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/Auditable.kt`
## 它负责什么
这个文件定义了一个很轻量的领域接口 `Auditable`，只做一件事：统一约束所有“可审计对象”必须提供两个时间字段，`createdDate` 和 `lastModifiedDate`，类型都是 `LocalDateTime`。

它本身不包含业务逻辑，也不负责自动写库、自动更新时间戳，更多是一个领域层的共同契约。根据当前片段推断，它的作用是让大量模型在“创建时间 / 最后修改时间”这件事上保持一致，方便后续在 API、数据库映射、排序和同步逻辑里复用。

## 关键组成
文件内容非常短，核心只有三部分：

- 包名：`org.gotson.komga.domain.model`
- 唯一导入：`java.time.LocalDateTime`
- 接口定义：
  - `val createdDate: LocalDateTime`
  - `val lastModifiedDate: LocalDateTime`

它没有伴生对象、没有默认实现、没有注解、没有扩展函数，也没有任何状态。  
从代码风格看，它是给 `data class` 们统一实现的公共接口，而不是一个独立功能模块。

## 上下游关系
上游是领域模型的构造方式。仓库里很多模型在构造参数中直接实现这个接口，并给出默认值，例如 `Book`、`Library`、`ApiKey`、`ReadList`、`SeriesMetadata`、`BookMetadata`、`ThumbnailBook` 等。它们通常写成：

- `override val createdDate: LocalDateTime = LocalDateTime.now()`
- `override val lastModifiedDate: LocalDateTime = createdDate`

这说明时间戳大多在对象创建时初始化，而不是由这个接口统一注入。

下游是所有读取这些字段的地方。搜索结果里能看到它们被用于：

- API 层：`KoboController`、`OpdsController` 等会读取 `createdDate`、`lastModifiedDate` 来生成响应或元数据。
- DTO 层：如 `ApiKeyDto`、`CollectionDto`、`ReadListDto`、`PageHashKnownDto` 会把这些时间转成对外格式。
- 持久化层：如 `LibraryDao`、`ReadListDao`、`PageHashDao`、`MediaDao`、`ThumbnailBookDao` 等会把字段映射到数据库列。
- 排序/检索：例如 `OpdsController` 里会按 `createdDate` 排序。

也就是说，`Auditable` 是一个横切式的领域约束，连接了模型、接口层和数据层。

## 运行/调用流程
这个文件本身没有运行逻辑，所以更适合按“对象生命周期”理解：

1. 业务代码实例化某个领域模型，比如 `Book` 或 `Library`。
2. 构造函数给 `createdDate` 一个默认值 `LocalDateTime.now()`。
3. `lastModifiedDate` 默认继承 `createdDate`，表示新对象刚创建时没有被修改过。
4. 这些对象在后续被 API 层、DAO 层、DTO 映射层读取。
5. 当对象被更新、持久化或导出时，其他层会继续使用这两个字段进行展示、排序、同步或转换时区。

这里要注意：接口本身不会自动更新 `lastModifiedDate`。  
根据当前片段推断，更新时间应该由具体模型的创建/复制逻辑、DAO 写入逻辑或业务服务负责，而不是 `Auditable` 自动完成。

## 小白阅读顺序
建议按这个顺序看：

1. 先看 `Auditable.kt` 本身，确认它只定义了两个字段。
2. 再看一个典型实现，比如 `komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt` 或 `Library.kt`，理解默认值是怎么写的。
3. 再看一个会输出这些字段的 DTO，比如 `ApiKeyDto`、`CollectionDto` 或 `ReadListDto`，看它们如何对外暴露时间。
4. 再看一个 DAO，比如 `LibraryDao` 或 `ReadListDao`，理解它们如何和数据库字段对应。
5. 最后看控制器，比如 `OpdsController` 或 `KoboController`，理解这些时间在接口响应里怎么被使用。

这样能从“接口契约”一路串到“真实调用场景”。

## 常见误区
- 误以为 `Auditable` 会自动帮对象打时间戳。实际上它只是字段契约，不负责自动写入。
- 误以为它是数据库层注解模型。实际上这个文件里没有 JPA、Spring Data 或其他审计注解。
- 误以为所有实现类的时间语义完全一致。实际上不同模型可能在更新时由不同层维护这些值，具体行为要看实现类、DAO 和服务代码。
- 误以为 `createdDate` 和 `lastModifiedDate` 一定不同。对新建对象来说，很多实现类会把两者初始化为相同值。
- 误把它当成业务能力接口。它不表达“如何审计”，只表达“这个对象应该有审计时间字段”。
