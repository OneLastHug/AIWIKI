# 文件：`komga/src/main/kotlin/org/gotson/komga/domain/model/HistoricalEvent.kt`

## 它负责什么
这个文件定义的是 Komga 的“历史事件”领域模型，本质上是一个可持久化的审计日志对象。它记录了系统里和文件、目录、导入、转换、重复页清理有关的关键动作，方便后续在历史页面里回看“发生过什么”。

它不是业务实体本身，而是围绕业务实体的事件记录。比如书文件被删除、系列目录被删空、书从旧格式转换为 CBZ、导入了一本书、删除了重复页，这些动作都会被包装成一个 `HistoricalEvent` 并写入历史表。

## 关键组成
- `sealed class HistoricalEvent`：这是核心基类，说明所有历史事件类型都被限定在这个文件里定义，外部不能随意扩展。
- 基础字段：
  - `type: String`：事件类型名，使用硬编码字符串，例如 `"BookImported"`。
  - `bookId: String?`：关联的书籍 ID，可空。
  - `seriesId: String?`：关联的系列 ID，可空。
  - `properties: Map<String, String>`：附加属性，全部以字符串形式存储。
  - `timestamp: LocalDateTime`：事件时间，默认是创建对象时的 `LocalDateTime.now()`。
  - `id: String`：事件 ID，默认使用 `TsidCreator.getTsid256()` 生成 TSID。
- 子类事件：
  - `BookFileDeleted(book, reason)`：记录书文件被删除，附带 `reason` 和 `name`，其中 `name` 实际上是 `book.path.toString()`。
  - `SeriesFolderDeleted(seriesId, seriesPath, reason)`：记录系列目录被删除，附带原因和目录路径；还提供了一个便捷构造函数 `SeriesFolderDeleted(series: Series, reason: String)`。
  - `BookConverted(book, previous)`：记录书文件转换，附带当前文件名和旧文件名。
  - `BookImported(book, series, source, upgrade)`：记录书导入，附带来源路径和是否升级，`upgrade` 被编码成 `"Yes"` 或 `"No"`。
  - `DuplicatePageDeleted(book, page)`：记录删除重复页，附带页码、文件名、hash、大小和媒体类型。
- 依赖的模型：
  - `Book` 和 `Series` 都通过 `url` 派生出 `path`。
  - `BookPageNumbered` 提供页码、文件名、hash、大小和媒体类型。

## 上下游关系
上游是“谁创建这些事件”：
- `BookImporter`：导入书籍、升级旧书文件时写入 `BookImported`、`BookFileDeleted`。
- `BookConverter`：转换格式并删除旧文件时写入 `BookConverted`、`BookFileDeleted`。
- `BookLifecycle`：用户删除书文件时写入 `BookFileDeleted`。
- `SeriesLifecycle`：系列目录被清空删除时写入 `SeriesFolderDeleted`。
- `BookPageEditor`：清理重复页时写入 `DuplicatePageDeleted`。

下游是“谁保存和展示这些事件”：
- `HistoricalEventRepository` 定义了持久化入口，只有一个方法 `insert(event)`。
- `HistoricalEventDao` 负责真正写库：先写主表 `historical_event`，再把 `properties` 拆成多行写入 `historical_event_properties`。
- `HistoricalEventController` 对外提供 `/api/v1/history`，返回 `HistoricalEventDto` 分页数据。
- `HistoricalEventDtoRepository` 和对应 DAO 负责查询历史列表。根据当前片段推断，DTO 层会把主表和属性表重新组装成接口返回结构。

## 运行/调用流程
1. 业务服务先执行真实动作，比如删除文件、导入文件、转换格式、删除重复页。
2. 动作成功后，服务创建一个具体的 `HistoricalEvent` 子类实例。
3. 调用 `historicalEventRepository.insert(event)`。
4. `HistoricalEventDao` 把事件主信息写入 `historical_event`，包括 `id`、`type`、`bookId`、`seriesId`、`timestamp`。
5. 如果 `properties` 不为空，再把每个键值对写入 `historical_event_properties`。
6. 之后历史接口通过分页查询把这些记录展示给管理员。

## 小白阅读顺序
1. 先看 `komga/src/main/kotlin/org/gotson/komga/domain/model/Book.kt`、`Series.kt`、`BookPageNumbered.kt`，弄清楚事件里用到的对象字段和 `path` 从哪来。
2. 再看 `HistoricalEvent.kt`，重点理解每个子类代表什么场景。
3. 然后看 `komga/src/main/kotlin/org/gotson/komga/domain/persistence/HistoricalEventRepository.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/HistoricalEventDao.kt`，理解事件如何落库。
4. 接着看 `BookImporter`、`BookConverter`、`BookLifecycle`、`SeriesLifecycle`、`BookPageEditor` 里的调用点，确认事件是在什么业务节点生成的。
5. 最后看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/HistoricalEventController.kt` 和 `HistoricalEventDto.kt`，理解历史记录如何对外展示。

## 常见误区
- 不要把 `HistoricalEvent` 和 `DomainEvent` 混为一谈。前者是持久化历史审计，后者更像运行时业务事件。
- `properties` 虽然是 Map，但值全部是字符串，像 `upgrade` 这种布尔信息也被编码成 `"Yes"` / `"No"`，不能按强类型去读。
- `name` 这个属性名容易误导，它在这里并不是书名，而是文件路径字符串，例如 `book.path.toString()`。
- `type` 不是枚举，而是手写字符串；一旦拼写不一致，下游查询和展示就会出问题。
- `timestamp` 默认在对象创建时生成，不是由数据库回填，所以事件时间反映的是构造时刻。
- `SeriesFolderDeleted(series, reason)` 这个便捷构造函数只是语法糖，实际仍然会把系列的 `id` 和 `path` 写进事件。
