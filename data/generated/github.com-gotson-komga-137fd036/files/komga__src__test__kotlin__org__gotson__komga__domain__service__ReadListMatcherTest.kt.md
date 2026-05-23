# 文件：`komga/src/test/kotlin/org/gotson/komga/domain/service/ReadListMatcherTest.kt`

## 它负责什么
这个文件是 `ReadListMatcher` 的集成测试，验证“读书清单请求”在进入服务层后，能否正确完成两类判断：

1. 读书清单名字是否已经存在。
2. 请求里的每一条书目条件，是否能被匹配到具体的系列和书本。

它不是纯单元测试，而是 `@SpringBootTest` 方式起 Spring 上下文，真实注入了 `SeriesLifecycle`、各类 Repository、`ReadListLifecycle`、`ReadListMatcher` 等对象，用数据库状态来构造匹配场景。

## 关键组成
- `@SpringBootTest`：说明这是整合 Spring 容器的测试。
- `@MockkBean private lateinit var mockTaskEmitter: TaskEmitter`：把任务发布器替换成 mock，避免测试数据准备过程中触发额外任务。
- `@BeforeAll setup library`：先插入一个 library，作为后续系列和书本的归属容器。
- `@BeforeEach`：把 `refreshBookMetadata(any<Book>(), any())` stub 掉，返回 `Runs`，防止生命周期操作触发真正的元数据刷新。
- `@AfterEach`：清空 `ReadListRepository`，并删除当前测试中创建的 series，保证每个用例独立。
- `nested class Match`：所有断言都集中在“匹配行为”这一组用例里。
- `mapIds()` 辅助函数：把复杂的匹配结果压平为 `seriesId -> bookId列表`，方便断言。

从内容上看，三个核心用例分别覆盖：
- 全部请求都能匹配到单一结果。
- 读书清单名字已存在时，返回错误码 `ERR_1009`，但书目匹配仍然正常。
- 只有部分请求能匹配时，返回部分空结果、部分命中结果。

## 上下游关系
上游是测试自己搭出来的数据环境：

- `SeriesLifecycle` 创建系列、挂书、排序。
- `SeriesMetadataRepository` 修改系列标题，模拟外部可见名称变化。
- `BookMetadataRepository` 修改书号，模拟书本编号归一化或外部元数据覆盖。
- `ReadListLifecycle.addReadList(...)` 创建一个同名读书清单，用来触发重复名称错误。
- `LibraryRepository` 提供基础 library。

下游是被测服务 `ReadListMatcher`，它本身位于 `komga/src/main/kotlin/org/gotson/komga/domain/service/ReadListMatcher.kt`。根据实现可知，它只做两件事：

- 用 `ReadListRepository.existsByName(request.name)` 判断名字冲突。
- 把 `request.books` 交给 `ReadListRequestRepository.matchBookRequests(...)` 去做书目匹配。

再往下，`ReadListLifecycle.matchComicRackList(...)` 会调用 `ReadListMatcher.matchReadListRequest(...)`，所以这个测试实际上也覆盖了“导入 ComicRack 读书清单时，匹配结果是否合理”的核心链路。

## 运行/调用流程
1. 测试启动后，`BeforeAll` 先插入一个 library。
2. 每个用例先构造系列、书本和元数据。
3. 需要冲突时，先通过 `ReadListLifecycle.addReadList(...)` 放入一个同名读书清单。
4. 构造 `ReadListRequest`，其中每条 `ReadListRequestBook` 包含 `series: Set<String>` 和 `number: String`。
5. 调用 `readListMatcher.matchReadListRequest(request)`。
6. 断言返回值中的 `readListMatch.name`、`readListMatch.errorCode`，以及 `requests` 的匹配结果。
7. 通过 `mapIds()` 检查每条请求最终命中了哪些 series 和 book。

从三个用例可以看出，这里的匹配不是简单字符串直比，而是会结合系列标题、系列名、书号以及大小写差异来做归并。比如测试里同时用了 `"Batman: White Knight"`、`"batman"`、`"BATMAN: WHITE KNIGHT"`，以及 `"02"`、`"25"` 这类书号写法，说明底层匹配逻辑具有一定的归一化能力。根据当前片段推断，这部分归一化主要发生在 `ReadListRequestRepository.matchBookRequests(...)` 的实现里，而不是测试文件本身。

## 小白阅读顺序
1. 先看 `ReadListRequest.kt`，弄清楚 `ReadListRequest`、`ReadListMatch`、`ReadListRequestBookMatches` 这些数据结构分别装什么。
2. 再看 `ReadListMatcher.kt`，确认服务层只负责“名字冲突判断 + 调用匹配仓库”。
3. 然后回到这个测试文件，看三个用例各自构造了什么数据。
4. 最后对照 `ReadListLifecycle.kt` 的 `matchComicRackList(...)`，理解它在真实导入流程中的位置。

## 常见误区
- 以为这个测试在验证完整读书清单导入流程。实际上它只验证“请求匹配”阶段，不负责持久化读书清单。
- 以为 `ReadListMatcher` 自己实现了复杂匹配算法。实际上它只做编排，真正的书目匹配被委托给 `ReadListRequestRepository`。
- 以为重复名字会直接让整条请求失败。测试显示它仍然会返回书目匹配结果，只是 `readListMatch.errorCode` 变成 `ERR_1009`。
- 以为 `TaskEmitter` 在这个文件里有业务断言价值。它更像是测试环境里的副作用屏蔽器，重点不在它本身。
