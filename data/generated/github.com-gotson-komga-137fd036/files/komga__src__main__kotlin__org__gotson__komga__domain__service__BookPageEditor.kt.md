# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/BookPageEditor.kt

## 它负责什么

`BookPageEditor` 是一个专门处理“删除书籍内页”的领域服务。它的核心工作不是简单把某几张图片删掉，而是：

1. 先确认书籍文件还存在、磁盘上的版本没有被别的任务改动。
2. 只允许可转换的媒介类型，目前只支持 `MediaType.ZIP.type`。
3. 根据待删除页重建一个新的 ZIP/CBZ 文件。
4. 再次扫描并分析新文件，确认它仍然是可读、可解析、内容完整的。
5. 用新文件替换旧文件，同时更新数据库中的 `Book`、`Media` 和页哈希统计。
6. 记录历史事件，发布 `DomainEvent.BookUpdated`，必要时要求重新生成缩略图。

从职责上看，它是“文件级页面清理 + 数据一致性同步”的组合服务，而不是单纯的文件工具类。

## 关键组成

- `@Service class BookPageEditor(...)`：Spring 单例服务，说明它会被整个应用共享。
- 依赖注入的协作者：
  - `BookAnalyzer`：读取文件内容、重新分析新生成的书籍。
  - `FileSystemScanner`：扫描磁盘文件并得到 `Book`/文件元数据。
  - `BookRepository`、`MediaRepository`、`LibraryRepository`、`PageHashRepository`：更新领域数据。
  - `TransactionTemplate`：把数据库更新放进事务里。
  - `ApplicationEventPublisher`：发布书籍更新事件。
  - `HistoricalEventRepository`：记录“重复页被删除”这类可追溯事件。
- 关键常量：
  - `TEMP_PREFIX = "komga_page_removal_"`、`TEMP_SUFFIX = ".tmp"`：临时文件命名。
- 关键状态：
  - `convertibleTypes = listOf(MediaType.ZIP.type)`：当前只允许 ZIP。
  - `failedPageRemoval = mutableListOf<String>()`：记录曾经失败过的书籍 ID，后续直接跳过。

方法只有一个主入口：`removeHashedPages(book, pagesToDelete)`。

## 上下游关系

上游调用入口主要来自任务系统。`TaskHandler` 里处理 `Task.RemoveHashedPages` 时，会调用 `bookPageEditor.removeHashedPages(book, task.pages)`，如果返回 `BookAction.GENERATE_THUMBNAIL`，再继续触发缩略图生成。

再往上，`PageHashLifecycle.getBookPagesToDeleteAutomatically(...)` 会根据页哈希策略找出“应该自动删除的重复页”，这些结果通常会被任务系统转成删除任务，再流入 `BookPageEditor`。

下游影响则分成三层：

1. 文件层面：重写原书籍文件，完成页面删除。
2. 数据层面：更新 `Book`、`Media`、页哈希删除计数。
3. 事件层面：插入 `HistoricalEvent.DuplicatePageDeleted`，再发布 `DomainEvent.BookUpdated`，让其他模块感知书籍已变更。

根据当前片段推断，`BookPageEditor` 是“重复页清理”链路的末端执行者，真正决定删哪些页的是 `PageHashLifecycle` 和任务调度层。

## 运行/调用流程

1. `TaskHandler` 收到 `Task.RemoveHashedPages`。
2. 查到对应 `Book` 后，把书和页列表交给 `BookPageEditor`。
3. `BookPageEditor` 先做保护性检查：
   - 如果这本书曾经删除失败过，直接跳过。
   - 重新扫描磁盘文件，确认 `fileLastModified` 没变。
   - 检查媒体类型是否是 ZIP。
   - 检查媒体状态是否 `READY`。
4. 计算 `pagesToKeep`，也就是“不在删除列表中的页面”。
5. 校验页数总和是否对得上，避免误删或状态不一致。
6. 创建临时 ZIP 文件，把要保留的页和附属文件重新写进去。
7. 扫描临时文件并分析它：
   - 必须仍然可读。
   - 必须仍然是 ZIP。
   - 必须包含所有要保留的页。
   - 必须包含原始附属文件。
8. 校验失败则删除临时文件，把书籍 ID 记入失败列表，并抛出异常。
9. 校验成功后，用临时文件替换原文件。
10. 再次扫描替换后的文件，构造新的 `Book`。
11. 在事务里更新数据库：
   - `bookRepository.update(newBook)`
   - `mediaRepository.update(mediaWithHashes)`
   - 对相关页哈希的 `deleteCount` 做累加
12. 记录历史事件并发布 `DomainEvent.BookUpdated`。
13. 如果删除的页里包含第 1 页，返回 `BookAction.GENERATE_THUMBNAIL`，让上层再补一次封面/缩略图。

## 小白阅读顺序

建议按这个顺序读，最省力：

1. 先看 `BookAction`，理解这个方法为什么会返回 `GENERATE_THUMBNAIL`。
2. 再看 `BookPageNumbered`，搞清楚删除页是怎么定位的。
3. 接着看 `TaskHandler` 中 `Task.RemoveHashedPages` 的分支，理解调用入口。
4. 再看 `PageHashLifecycle`，知道自动删页的来源。
5. 最后回到 `BookPageEditor.kt`，按“检查 -> 重建 -> 验证 -> 替换 -> 回写数据库”这条线读。

如果先硬读这个文件，容易只看到 ZIP 重打包逻辑，看不到它其实是一个跨文件、跨数据库、跨事件的完整流程。

## 常见误区

- 误区一：以为它只是“删除图片文件”。实际上它是重建整个 ZIP/CBZ，再替换原文件。
- 误区二：以为支持所有书籍格式。这里明确只允许 `MediaType.ZIP.type`。
- 误区三：以为删完文件就结束了。其实后面还有扫描、分析、事务更新、历史记录和事件发布。
- 误区四：忽略 `failedPageRemoval`。这是一个服务内状态，`BookPageEditor` 又是 `@Service` 单例，所以失败记录会影响后续请求。
- 误区五：以为删任意页都一样。删除第 1 页会额外触发 `BookAction.GENERATE_THUMBNAIL`，因为封面通常依赖首页。
- 误区六：以为只要页内容一样就能匹配。这里匹配条件很严格，`fileHash`、`mediaType`、`fileName`、`pageNumber` 都要对得上。

如果你把它放回整个系统里看，它不是“编辑页面”的 UI 辅助逻辑，而是一个对磁盘文件和数据库状态都很敏感的后端修复/清理服务。
