# 文件：komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt

## 它负责什么

`BookMetadataLifecycle` 是书籍元数据刷新流程的编排服务。它不直接“解析元数据”，而是把下面几件事串起来：

1. 从 `MediaRepository` 取出这本书的媒体信息。
2. 从 `LibraryRepository` 取出所属书库，判断这个书库是否允许某个 provider 处理书籍元数据或阅读列表元数据。
3. 遍历所有 `BookMetadataProvider`，按能力集 `capabilities` 过滤。
4. 让 provider 基于 `BookWithMedia(book, media)` 生成 `BookMetadataPatch`。
5. 通过 `MetadataApplier` 把 patch 合并回现有 `BookMetadata`，再写回 `BookMetadataRepository`。
6. 如果 provider 同时返回了阅读列表信息，就委托 `ReadListLifecycle` 把书加入对应 read list。
7. 如果发生了书籍元数据更新，就发布 `DomainEvent.BookUpdated(book)`。

从职责上看，它是“刷新书籍元数据”的事务性编排点，而不是具体元数据规则的实现者。

## 关键组成

这个文件里最重要的成员和依赖如下。

- `refreshMetadata(book, capabilities)`  
  入口方法。外部传入目标 `Book` 和这次允许的 `BookMetadataPatchCapability` 集合。

- `bookMetadataProviders: List<BookMetadataProvider>`  
  所有元数据 provider 的集合。每个 provider 都声明自己支持的能力，并实现 `getBookMetadataFromBook(...)`。

- `metadataApplier: MetadataApplier`  
  负责把 `BookMetadataPatch` 合并进已有 `BookMetadata`。它会尊重字段锁定状态，例如 `titleLock`、`summaryLock` 等，锁住的字段不会被 patch 覆盖。

- `mediaRepository`  
  通过 `book.id` 获取媒体数据，用来构建 `BookWithMedia`。

- `bookMetadataRepository`  
  读写书籍元数据的持久层。这里先 `findById(book.id)`，再 `update(patched)`。

- `libraryRepository`  
  取出书籍所属书库。这里的作用不是找书，而是判断书库配置是否允许该 provider 处理 `MetadataPatchTarget.BOOK` 或 `MetadataPatchTarget.READLIST`。

- `readListLifecycle`  
  负责把书加入阅读列表。`BookMetadataLifecycle` 只负责触发，不负责 read list 的具体维护细节。

- `eventPublisher`  
  刷新完成后发布领域事件 `DomainEvent.BookUpdated(book)`，供系统里其他模块响应。

- 关键模型和枚举  
  `BookWithMedia`、`BookMetadataPatch`、`BookMetadataPatchCapability`、`MetadataPatchTarget`、`DomainEvent`。  
  它们分别表示“带媒体信息的书”、“待合并的元数据补丁”、“provider 能力标签”、“补丁目标类型”和“领域事件”。

## 上下游关系

上游入口很明确。根据当前片段推断，`TaskHandler` 是最直接的调用方：当任务类型是 `Task.RefreshBookMetadata` 时，它会调用 `bookMetadataLifecycle.refreshMetadata(book, task.capabilities)`，然后再继续触发系列元数据刷新流程。也就是说，这个类通常不是被 UI 直接调用，而是被任务系统间接驱动。

下游依赖也很清晰。

- `BookMetadataProvider` 是元数据来源。这个接口定义在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/BookMetadataProvider.kt`，只有一个核心方法 `getBookMetadataFromBook(book: BookWithMedia): BookMetadataPatch?`，外加能力集合 `capabilities`。
- `MetadataApplier` 负责把 patch 应用到已有元数据对象上。它的实现很直接：如果某字段有 patch 且没有 lock，就用 patch 值，否则保留原值。
- `BookMetadataRepository` 保存最终结果。
- `ReadListLifecycle` 处理阅读列表副作用。
- `ApplicationEventPublisher` 把“书已更新”变成系统事件。

这意味着 `BookMetadataLifecycle` 的位置是典型的“协调层”：它决定谁参与、什么时候写库、什么时候发事件，但不负责具体字段规则。

## 运行/调用流程

整个流程可以按一次 `refreshMetadata` 调用理解：

1. 入口收到 `book` 和 `capabilities`。
2. 先打印日志，便于追踪刷新任务。
3. 通过 `mediaRepository.findById(book.id)` 取出媒体信息。
4. 通过 `libraryRepository.findById(book.libraryId)` 取出所属书库。
5. 初始化 `changed = false`。
6. 遍历每个 `BookMetadataProvider`：
   - 先检查 provider 支持的能力是否与本次请求的 `capabilities` 有交集。
   - 再检查该书库是否允许这个 provider 处理 `MetadataPatchTarget.BOOK` 或 `MetadataPatchTarget.READLIST`。
   - 如果都满足，就调用 `provider.getBookMetadataFromBook(BookWithMedia(book, media))`。
   - 调用失败会被 `try/catch` 捕获，记录错误后继续下一个 provider，不会中断整个刷新流程。
7. 如果书库允许处理 `BOOK`：
   - 调用 `handlePatchForBookMetadata(patch, book)`。
   - 这个方法会先从 `bookMetadataRepository.findById(book.id)` 取当前元数据。
   - 再用 `metadataApplier.apply(bPatch, it)` 合并 patch。
   - 最后 `bookMetadataRepository.update(patched)` 写回。
   - 然后把 `changed = true`。
8. 如果书库允许处理 `READLIST`：
   - 读取 `patch?.readLists`。
   - 对每个 read list 调用 `readListLifecycle.addBookToReadList(readList.name, book, readList.number)`。
9. 所有 provider 处理完后，如果 `changed` 为真，就发布 `DomainEvent.BookUpdated(book)`。

这里有一个值得注意的实现细节：`changed = true` 是在“进入 BOOK 分支”时就设置的，不是等到真正检测到字段变更后才设置。根据当前片段推断，这意味着只要某个 provider 走到了 book 处理分支，就会认为 book 更新过，并发布事件，即使 `patch` 最终是 `null` 或实际没有字段变化。

## 小白阅读顺序

建议按下面顺序读，会比较顺：

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/service/BookMetadataLifecycle.kt` 本身，抓住入口、provider 循环、持久化和事件发布。
2. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/metadata/BookMetadataProvider.kt`，理解 provider 需要提供什么、能力怎么声明。
3. 接着读 `komga/src/main/kotlin/org/gotson/komga/domain/service/MetadataApplier.kt`，看 patch 是如何受 lock 约束地合并到现有元数据中的。
4. 然后看 `TaskHandler` 里 `Task.RefreshBookMetadata` 的分支，确认它是怎么被任务系统触发的。
5. 最后再看 `ReadListLifecycle` 和 `BookMetadataRepository` 的实现或接口，理解写库和副作用如何落地。

如果只想先建立最小心智模型，可以记成一句话：`TaskHandler` 触发刷新，`BookMetadataLifecycle` 协调 provider，`MetadataApplier` 合并字段，`BookMetadataRepository` 落库，`ReadListLifecycle` 处理阅读列表，`eventPublisher` 通知系统其他部分。

## 常见误区

1. 以为这个类“负责解析元数据”  
   不是。真正解析逻辑在各个 `BookMetadataProvider` 里，这个类只做编排和落库。

2. 以为它只更新书籍元数据  
   不是。它还会根据 `READLIST` 目标把书加入阅读列表。

3. 以为 provider 只要实现接口就一定会执行  
   不一定。它还要同时满足两层过滤：`capabilities` 要有交集，书库配置也必须允许对应的 `MetadataPatchTarget`。

4. 以为 `patch == null` 就不会产生任何后续影响  
   对 `READLIST` 来说是的，但对 `BOOK` 分支未必。根据当前代码，只要进入 `BOOK` 分支就会走 `changed = true`，后面仍可能发布 `DomainEvent.BookUpdated(book)`。

5. 以为更新会直接覆盖全部字段  
   不会。`MetadataApplier` 会检查字段 lock，锁住的字段保持原值，patch 不会强行覆盖。

6. 以为 provider 异常会中断整个刷新任务  
   不会。单个 provider 抛异常只会被记录，后面的 provider 仍继续执行。
