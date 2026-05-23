# 文件：komga/src/test/kotlin/org/gotson/komga/domain/service/LibraryLifecycleTest.kt

## 它负责什么

`LibraryLifecycleTest.kt` 是 `LibraryLifecycle` 领域服务的集成测试文件，重点验证“创建库”和“更新库”时的合法性校验规则是否正确。

这里的 “library” 可以理解为 Komga 中的一个漫画/书籍库，它有一个名称 `name` 和一个根目录 `root`。根目录必须是真实存在的文件夹，多个库之间不能重名，也不能出现路径嵌套，例如一个库指向 `/books`，另一个库指向 `/books/manga`。

这个测试文件主要覆盖两类操作：

- `libraryLifecycle.addLibrary(...)`：新增一个库。
- `libraryLifecycle.updateLibrary(...)`：更新一个已经存在的库。

它不是测试扫描、导入、删除、任务调度等完整行为，而是集中测试 `LibraryLifecycle.checkLibraryValidity(...)` 这类“库定义是否合法”的约束。

## 关键组成

这个测试类位于包：

`org.gotson.komga.domain.service`

它使用 `@SpringBootTest`：

```kotlin
@SpringBootTest
class LibraryLifecycleTest(
  @Autowired private val libraryRepository: LibraryRepository,
  @Autowired private val libraryLifecycle: LibraryLifecycle,
)
```

这说明它不是纯单元测试，而是启动 Spring 测试上下文，真实注入 `LibraryRepository` 和 `LibraryLifecycle`。因此测试更接近领域服务层的集成测试。

### 注入对象

`LibraryRepository`

用于测试前后管理库数据。测试中通过它清空仓储：

```kotlin
@AfterEach
fun `clear repositories`() {
  libraryRepository.deleteAll()
}
```

这样每个测试用例之间不会互相污染。

`LibraryLifecycle`

被测对象。测试中的所有核心行为都通过它完成：

```kotlin
libraryLifecycle.addLibrary(...)
libraryLifecycle.updateLibrary(...)
```

### 测试工具

`assertThat`

来自 AssertJ，用于断言异常类型、异常信息或确认没有异常。

`catchThrowable`

用于捕获某段代码抛出的异常，而不是让测试直接失败。例如：

```kotlin
val thrown = catchThrowable {
  libraryLifecycle.addLibrary(...)
}
```

之后再断言：

```kotlin
assertThat(thrown).isInstanceOf(FileNotFoundException::class.java)
```

`@TempDir`

来自 JUnit Jupiter，用于为每个测试提供临时目录。测试路径相关逻辑时非常关键，因为它能创建真实存在的目录，同时测试结束后由框架清理。

### 被验证的异常

测试文件中主要验证这些异常：

`FileNotFoundException`

当库根路径不存在时抛出。对应生产代码中：

```kotlin
if (!Files.exists(library.path))
  throw FileNotFoundException(...)
```

`DirectoryNotFoundException`

当路径存在，但不是目录时抛出。例如测试中通过 `Files.createTempFile(...)` 创建一个临时文件，再把它当作库根目录传入。

`DuplicateNameException`

当已有库和待新增/待更新库名称相同，并且不是同一个库自身时抛出。

`PathContainedInPath`

当两个库的根目录出现父子嵌套关系时抛出。

生产代码中判断逻辑在 `komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`：

```kotlin
if (library.path.startsWith(it.path))
  throw PathContainedInPath(...)

if (it.path.startsWith(library.path))
  throw PathContainedInPath(...)
```

也就是说，既禁止“新库是已有库的子目录”，也禁止“新库是已有库的父目录”。

## 上下游关系

### 上游：谁会触发这些逻辑

测试直接调用的是 `LibraryLifecycle`，但真实业务入口通常来自 REST API。

在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt` 中：

- `POST /api/v1/libraries` 会调用 `libraryLifecycle.addLibrary(...)`
- `PATCH /api/v1/libraries/{libraryId}` 会调用 `libraryLifecycle.updateLibrary(...)`
- 已废弃的 `PUT /api/v1/libraries/{libraryId}` 也会走更新逻辑

控制器会把 API DTO 转成领域模型 `Library`，然后交给 `LibraryLifecycle`。如果 `LibraryLifecycle` 抛出 `FileNotFoundException`、`DirectoryNotFoundException`、`DuplicateNameException`、`PathContainedInPath`，控制器会把它们转换成 `400 BAD_REQUEST`。

所以这个测试虽然写在 domain service 层，但它保护的是用户在前端/API 创建或修改库时能看到的核心校验行为。

### 下游：它依赖哪些领域对象和仓储

测试直接涉及：

`komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`

`Library` 是领域模型，关键字段包括：

- `name`：库名称。
- `root`：库根路径，类型是 `URL`。
- `id`：库 ID，默认由 TSID 生成。
- `path`：从 `root` 转换得到的 `Path`，用于文件系统判断。

其中：

```kotlin
val path: Path by lazy { this.root.toURI().toPath() }
```

说明业务校验最终不是直接比较字符串 URL，而是把 URL 转成 `java.nio.file.Path` 后再使用 `Files.exists`、`Files.isDirectory`、`Path.startsWith`。

`komga/src/main/kotlin/org/gotson/komga/domain/persistence/LibraryRepository.kt`

测试用到的仓储方法包括：

- `findAll()`：`LibraryLifecycle` 校验重名和路径包含关系时读取所有库。
- `insert(library)`：新增库时保存。
- `update(library)`：更新库时保存。
- `deleteAll()`：测试后清理数据。
- `findById(library.id)`：新增后重新读取库。

`komga/src/main/kotlin/org/gotson/komga/domain/model/Exceptions.kt`

定义了 `DirectoryNotFoundException`、`DuplicateNameException`、`PathContainedInPath` 等领域异常。这些异常继承自 `CodedException`，但本测试主要关心异常类型和部分 message，不关心错误码。

### 与生产实现的对应关系

目标测试文件实际覆盖的是 `LibraryLifecycle` 中的私有方法 `checkLibraryValidity(...)`，但它不是直接测试私有方法，而是通过公共方法间接覆盖：

- 新增时：`addLibrary(...)` 调用 `checkLibraryValidity(library, existing)`
- 更新时：`updateLibrary(...)` 先排除当前库，再调用 `checkLibraryValidity(toUpdate, otherLibraries)`

这个区别非常重要。

新增库时，所有已有库都算“冲突对象”。

更新库时，当前正在更新的库自身不算冲突对象：

```kotlin
val otherLibraries = libraries.filter { it.id != toUpdate.id }
checkLibraryValidity(toUpdate, otherLibraries)
```

所以测试中才会出现这样的差异：

- 单个已有库更新成自己的子目录：允许。
- 单个已有库更新成自己的父目录：允许。
- 但如果这个路径和另一个库形成父子关系：不允许。

## 运行/调用流程

### 新增库测试流程

`Add` 嵌套类覆盖 `addLibrary(...)`。

第一个用例：

```kotlin
Library("test", URL("file:/non-existent"))
```

传入不存在的路径，期望抛出 `FileNotFoundException`。

流程是：

1. 构造 `Library`。
2. 调用 `libraryLifecycle.addLibrary(...)`。
3. `LibraryLifecycle` 读取已有库。
4. 校验 `Files.exists(library.path)`。
5. 因路径不存在，抛出 `FileNotFoundException`。
6. 测试断言异常类型。

第二个用例创建的是临时文件，不是目录：

```kotlin
Files.createTempFile(null, null)
```

路径存在，所以不会触发 `FileNotFoundException`；但它不是目录，所以触发 `DirectoryNotFoundException`。

第三个用例先新增一个名为 `test` 的库，再用另一个路径新增同名库：

```kotlin
libraryLifecycle.addLibrary(Library("test", path1.toUri().toURL()))
libraryLifecycle.addLibrary(Library("test", path2.toUri().toURL()))
```

期望抛出 `DuplicateNameException`。

后两个新增用例测试路径包含关系：

- 已有库是父目录，新库是其子目录：抛出 `PathContainedInPath`，message 中包含 `"child"`。
- 已有库是子目录，新库是其父目录：抛出 `PathContainedInPath`，message 中包含 `"parent"`。

这里断言 message 包含 `"child"` 或 `"parent"`，不是为了测试完整文案，而是确认异常来自正确的路径方向。

### 更新库测试流程

`Update` 嵌套类覆盖 `updateLibrary(...)`。

它有一组共享字段：

```kotlin
private lateinit var rootFolder: Path
private lateinit var library: Library
```

并在 `@BeforeAll` 中初始化：

```kotlin
rootFolder = root
library = Library("Existing", rootFolder.toUri().toURL())
```

这个 `library` 是更新测试里的默认基础库，名称是 `"Existing"`，根目录是一个临时目录。

更新测试首先会通过 `addLibrary(library)` 创建已有库，然后用 `copy(...)` 构造更新后的对象：

```kotlin
val existing = libraryLifecycle.addLibrary(library)
val toUpdate = existing.copy(...)
libraryLifecycle.updateLibrary(toUpdate)
```

这里使用 `copy(...)` 很重要，因为 `Library` 是 Kotlin `data class`。更新时需要保留原来的 `id`，否则 `LibraryLifecycle.updateLibrary(...)` 会找不到当前库，或者把它当成另一个库处理。通过 `existing.copy(...)` 可以改变某些字段，同时保留原对象身份。

更新测试覆盖的重点包括：

1. 更新到不存在路径：抛出 `FileNotFoundException`。
2. 更新到非目录路径：抛出 `DirectoryNotFoundException`。
3. 单个库用相同名称更新自己：不抛异常。
4. 更新成另一个已有库的名称：抛出 `DuplicateNameException`。
5. 单个库更新成自己原目录下的子目录：不抛异常。
6. 单个库更新成自己原目录的父目录：不抛异常。
7. 更新后路径成为另一个库的子目录：抛出 `PathContainedInPath`。
8. 更新后路径成为另一个库的父目录：抛出 `PathContainedInPath`。

这些用例共同说明：更新逻辑校验的是“更新后的库”和“其他库”之间的冲突，而不是和自己的旧路径冲突。

### 生产代码中的完整行为

虽然测试主要关注异常，但 `LibraryLifecycle` 的真实方法还会做更多事。

`addLibrary(...)` 成功后会：

1. 插入库：`libraryRepository.insert(library)`
2. 触发扫描任务：`taskEmitter.scanLibrary(library.id)`
3. 发布领域事件：`DomainEvent.LibraryAdded(library)`
4. 重新按 ID 查询并返回保存后的库

`updateLibrary(...)` 成功后会：

1. 更新库：`libraryRepository.update(toUpdate)`
2. 如果扫描间隔变化，重新调度扫描：`libraryScanScheduler.scheduleScan(toUpdate)`
3. 如果根路径、扫描格式、排除目录等变化，触发重新扫描
4. 如果开启了 hash、修复扩展名、转换 CBZ 等选项，触发相应后台任务
5. 发布 `DomainEvent.LibraryUpdated(toUpdate)`

当前测试没有断言这些任务和事件。根据当前片段推断，这是因为本文件的职责被限定在“库配置合法性”，任务调度和事件发布应该由其他测试覆盖，或者在这里通过 Spring 上下文隐式保证服务能正常运行。

## 小白阅读顺序

1. 先读 `Library` 模型：`komga/src/main/kotlin/org/gotson/komga/domain/model/Library.kt`

   重点看 `name`、`root`、`id` 和 `path`。理解 `root` 是 URL，而真正用于文件判断的是 `path`。

2. 再读异常定义：`komga/src/main/kotlin/org/gotson/komga/domain/model/Exceptions.kt`

   重点看 `DirectoryNotFoundException`、`DuplicateNameException`、`PathContainedInPath`。它们是领域层对非法库配置的表达。

3. 然后读生产服务：`komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryLifecycle.kt`

   重点看三个方法：

   - `addLibrary(...)`
   - `updateLibrary(...)`
   - `checkLibraryValidity(...)`

   其中 `checkLibraryValidity(...)` 是理解本测试的核心。

4. 最后读目标测试：`komga/src/test/kotlin/org/gotson/komga/domain/service/LibraryLifecycleTest.kt`

   建议先看 `Add`，再看 `Update`。因为新增逻辑更直观；更新逻辑多了“排除当前库自身”的概念。

5. 如果想理解 API 怎么进来，再读 `LibraryController`：

   `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`

   重点看 `addLibrary(...)` 和 `updateLibraryById(...)`，它们会把 REST 请求转换成 `Library`，然后调用 `LibraryLifecycle`。

## 常见误区

### 误区一：不存在路径和非目录路径是同一种错误

不是。

如果路径根本不存在，抛出的是 Java 标准异常 `FileNotFoundException`。

如果路径存在，但它是文件而不是目录，抛出的是领域异常 `DirectoryNotFoundException`。

测试中专门把这两种情况拆开，是为了保证 API 层能给出更准确的错误原因。

### 误区二：更新库时不能把路径改成原路径的子目录或父目录

单个库更新自己时，这种情况在当前测试中是允许的。

原因是 `updateLibrary(...)` 会先排除当前库：

```kotlin
val otherLibraries = libraries.filter { it.id != toUpdate.id }
```

因此路径包含关系只会拿“更新后的库”和“其他库”比较，不会拿它和自己的旧路径比较。

这也是为什么测试中有两个 “given single existing library ... then no exception is thrown” 用例。

### 误区三：`DuplicateNameException` 是数据库唯一约束触发的

从当前代码看，重名校验发生在领域服务层：

```kotlin
if (existing.map { it.name }.contains(library.name))
  throw DuplicateNameException(...)
```

也就是说，测试关注的是 `LibraryLifecycle` 主动读取已有库并判断名称冲突，而不是等数据库插入失败。

### 误区四：路径比较只是字符串前缀比较

不是简单字符串比较，而是使用 `Path.startsWith(...)`。

`Library.root` 是 `URL`，随后通过：

```kotlin
this.root.toURI().toPath()
```

转换为 `Path`。路径包含关系依赖 Java NIO 的 `Path` 语义。

### 误区五：这个测试验证了新增库后的扫描任务一定执行成功

没有。

`addLibrary(...)` 成功后确实会调用 `taskEmitter.scanLibrary(library.id)`，但本测试并没有断言任务队列、扫描结果或事件发布。它只在成功路径上间接要求方法不要因为校验失败而抛异常。

所以不要把这个测试理解成“库扫描功能测试”。它是“库生命周期中的合法性校验测试”。

### 误区六：`@TempDir` 创建的是虚拟路径

不是。`@TempDir` 创建的是真实临时目录，因此可以用于 `Files.exists(...)`、`Files.isDirectory(...)` 和 `Path.startsWith(...)` 这类真实文件系统判断。

这也是本测试选择 `@TempDir` 的原因：它可以稳定模拟存在目录、父子目录、临时文件等场景。
