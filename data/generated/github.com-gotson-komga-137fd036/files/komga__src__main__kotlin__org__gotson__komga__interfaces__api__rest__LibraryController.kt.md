# 文件：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`

## 它负责什么

`LibraryController` 是 Komga 里“图库”相关的 REST 入口，挂在 `api/v1/libraries` 下面。它负责把外部 HTTP 请求转成对库的查询、创建、更新、删除，以及触发扫描、分析、刷新元数据、清空回收站等异步任务。

它本身不是核心业务层，更多是编排层。真正的规则校验、持久化、任务投递，分别落在 `LibraryLifecycle`、`TaskEmitter`、`LibraryRepository`、`BookRepository`、`SeriesRepository` 这些组件里。根据当前片段推断，它的职责边界就是“接请求、做权限判断、把 DTO 变成领域对象，再把工作交给下游”。

## 关键组成

- 类注解：`@RestController`、`@RequestMapping("api/v1/libraries")`、`@Tag(...)`
- 安全控制：`@AuthenticationPrincipal KomgaPrincipal`、`@PreAuthorize("hasRole('ADMIN')")`
- 核心依赖：
  - `LibraryRepository`：读写图库记录
  - `LibraryLifecycle`：处理库的新增、更新、删除，以及相关领域校验和事件
  - `TaskEmitter`：投递后台任务
  - `BookRepository`、`SeriesRepository`：按库批量查书、查系列
- DTO 转换：
  - `LibraryCreationDto`：创建库请求
  - `LibraryUpdateDto`：更新库请求
  - `LibraryDto`：对外返回
  - `toDto(...)`、`filePathToUrl(...)`、`toDomain()`：做类型和路径转换
- 异常映射：
  - `FileNotFoundException`
  - `DirectoryNotFoundException`
  - `DuplicateNameException`
  - `PathContainedInPath`
  这些会被转成 `400 Bad Request`，其他未知错误通常走 `500`

一个很容易忽略的点是 `LibraryUpdateDto` 不是普通 data class，而是为了区分“字段没传”和“字段传了 null/空值”做的特殊写法。这里的 `isSet("scanDirectoryExclusions")`、`isSet("oneshotsDirectory")` 就是关键。

## 上下游关系

上游主要是外部调用者，也就是前端、管理界面、OpenAPI 客户端，以及任何访问 `api/v1/libraries` 的 HTTP 请求方。这个 controller 也是 OpenAPI 文档里“Libraries”标签下的入口。

下游关系比较清楚：

- `LibraryRepository`
  - `findAll()`
  - `findAllByIds(...)`
  - `findByIdOrNull(...)`
  - 负责读写图库基本记录
- `LibraryLifecycle`
  - `addLibrary(...)`
  - `updateLibrary(...)`
  - `deleteLibrary(...)`
  - 负责校验库路径、名称冲突、触发扫描、发领域事件
- `TaskEmitter`
  - `scanLibrary(...)`
  - `analyzeBook(...)`
  - `refreshBookMetadata(...)`
  - `refreshBookLocalArtwork(...)`
  - `refreshSeriesLocalArtwork(...)`
  - `emptyTrash(...)`
  - 负责把动作变成后台任务
- `BookRepository`、`SeriesRepository`
  - 用于把“库级操作”展开成具体的 book/series 集合

权限上下游也很明确：`KomgaPrincipal` 决定当前用户能看哪些库。`getLibraries` 和 `getLibraryById` 会按用户权限过滤；写操作则要求管理员角色。

## 运行/调用流程

1. **列出所有库**
   - `GET /api/v1/libraries`
   - 先取当前用户 `KomgaPrincipal`
   - 如果用户能访问全部库，就查 `libraryRepository.findAll()`
   - 否则只查共享库 `findAllByIds(...)`
   - 按名称排序后转成 `LibraryDto`
   - 非管理员看不到真实 root，`includeRoot = false` 时 `root` 会被置为空字符串

2. **查看单个库**
   - `GET /api/v1/libraries/{libraryId}`
   - 先按 ID 查库
   - 查不到返回 `404`
   - 查到后再做权限判断，不能访问就返回 `403`
   - 通过 `toDto(includeRoot = principal.user.isAdmin)` 输出

3. **创建库**
   - `POST /api/v1/libraries`
   - 仅管理员可用
   - 请求体是 `LibraryCreationDto`
   - controller 把 DTO 转成领域对象 `Library`
   - 关键转换点包括：
     - `root` 通过 `filePathToUrl(...)` 规范化
     - `scanInterval`、`seriesCover` 通过 `toDomain()` 转换
     - `oneshotsDirectory` 会把空串归一为 `null`
   - 再交给 `libraryLifecycle.addLibrary(...)`
   - 若路径不存在、不是目录、名称重复、路径嵌套冲突，会被映射成 `400`

4. **更新库**
   - `PUT /api/v1/libraries/{libraryId}` 是旧接口，已经废弃
   - `PATCH /api/v1/libraries/{libraryId}` 是推荐方式
   - 先查旧库，不存在返回 `404`
   - 再把 `LibraryUpdateDto` 和现有库合并成一个新对象
   - 这里最关键的是“有没有传字段”和“字段值是什么”要区分开：
     - 普通 `Boolean?` 字段：没传就沿用旧值
     - `scanDirectoryExclusions`、`oneshotsDirectory`：要靠 `isSet(...)` 判断是否显式设置
   - 合并后交给 `libraryLifecycle.updateLibrary(...)`
   - 更新后可能触发重新扫描、补 hash、修复扩展名、转换任务等

5. **删除库**
   - `DELETE /api/v1/libraries/{libraryId}`
   - 仅管理员
   - 先查库，不存在返回 `404`
   - 存在则交给 `libraryLifecycle.deleteLibrary(...)`

6. **库级后台动作**
   - `POST /{libraryId}/scan`：触发扫描，支持 `deep` 参数，返回 `202 Accepted`
   - `POST /{libraryId}/analyze`：查出该库下所有书并投递分析任务，返回 `202 Accepted`
   - `POST /{libraryId}/metadata/refresh`：批量刷新书元数据、局部封面、系列局部封面，返回 `202 Accepted`
   - `POST /{libraryId}/empty-trash`：清空该库垃圾，返回 `202 Accepted`
   - 这些接口都偏“发任务”，不是同步执行结果
   - 根据当前片段推断，`libraryAnalyze` 和 `metadata/refresh` 更像是直接按 `libraryId` 找书后投递任务，不像 `scan` 那样先显式检查库是否存在

## 小白阅读顺序

1. 先看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/LibraryCreationDto.kt`、`LibraryUpdateDto.kt`、`LibraryDto.kt`
2. 再看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt` 里的 GET、POST、PATCH 这三类接口
3. 接着看 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`
4. 然后看 `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskEmitter.kt`
5. 最后补 `LibraryRepository.kt`、`BookRepository.kt`、`SeriesRepository.kt` 和 `KomgaUser.kt`，把权限和数据查找规则补齐

## 常见误区

- 把 `LibraryController` 当成业务核心。它其实只是入口层，真正的规则主要在 `LibraryLifecycle` 和 `TaskEmitter`
- 以为 PATCH 和 PUT 是两套不同逻辑。这里 `PUT` 只是旧接口，内部直接调用 `PATCH`
- 忽略 `LibraryUpdateDto` 的 `isSet` 机制。对于某些字段，不是“值为 null”那么简单，而是要区分“没传”和“显式清空”
- 以为所有接口都返回完整 root。实际上 `LibraryDto.root` 只在管理员或 `includeRoot = true` 时才会返回真实路径，其他用户会拿到空字符串
- 误解 `analyze`、`metadata/refresh` 的时序。这些是异步任务投递，不是同步计算结果
- 认为所有库操作都会先检查库是否存在。实际上不同接口行为不完全一样，`scan`、`empty-trash` 会先查库，而 `analyze` 更像是按 `libraryId` 直接组织任务
- 忽略异常映射。路径/名称/目录相关问题会被转成 `400`，不是直接暴露底层异常
