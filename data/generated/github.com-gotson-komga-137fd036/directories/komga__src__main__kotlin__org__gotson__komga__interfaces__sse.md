# 目录：komga/src/main/kotlin/org/gotson/komga/interfaces/sse

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/interfaces/sse` 是 Komga 后端的 Server-Sent Events 输出层。它把服务端内部发生的 `DomainEvent` 转换成浏览器可订阅的 SSE 事件，让 Web UI 不需要频繁轮询就能感知书库、系列、书籍、阅读进度、缩略图、任务队列、会话状态等变化。

这个目录本身不负责“产生业务变化”。例如新增书籍、修改阅读进度、上传封面这些动作发生在 domain service 或 REST controller 中；这里负责在这些动作发布 `DomainEvent` 之后，把事件分发给当前已连接的用户浏览器。

核心入口是 `SseController.kt`，暴露的 HTTP 端点是：

```text
GET /sse/v1/events
```

前端对应代码在 `komga-webui/src/services/komga-sse.service.ts`，通过 `new EventSource(..., {withCredentials: true})` 连接这个端点，并按事件名注册监听器。

## 关键组成

`SseController.kt` 是唯一的控制器，主要包含四类职责。

第一类是连接管理。`sse()` 方法通过 `@GetMapping("sse/v1/events")` 创建 `SseEmitter`，并把它和当前登录用户 `KomgaUser` 绑定保存到 `emitters` 中。`emitters` 是一个 `Collections.synchronizedMap(HashMap<SseEmitter, KomgaUser>())`，用于记录“哪个 SSE 连接属于哪个用户”。当连接完成、超时或出错时，控制器会从 map 中移除对应 emitter。

第二类是保活。`heartbeat()` 每 15 秒遍历当前连接，发送一个 SSE comment：`heartbeat`。这不是业务事件，只是为了维持连接活跃，降低代理、浏览器或服务器中间层因为长时间无数据而断开连接的概率。

第三类是任务队列状态。`taskCount()` 每 10 秒调用 `TasksRepository.countBySimpleType()`，生成 `TaskQueueSseDto(count, countByType)`，然后用事件名 `TaskQueueStatus` 推送给管理员用户。这里设置了 `adminOnly = true`，所以普通用户不会收到任务队列统计。

第四类是领域事件转发。`handleSseEvent(event: DomainEvent)` 使用 `@EventListener` 监听 Spring 应用上下文中的 `DomainEvent`。它通过 `when (event)` 把不同领域事件映射成 SSE 事件名和 DTO。例如：

```text
DomainEvent.LibraryAdded -> "LibraryAdded" + LibrarySseDto
DomainEvent.SeriesUpdated -> "SeriesChanged" + SeriesSseDto
DomainEvent.BookDeleted -> "BookDeleted" + BookSseDto
DomainEvent.ReadProgressChanged -> "ReadProgressChanged" + ReadProgressSseDto
DomainEvent.UserDeleted -> "SessionExpired" + SessionExpiredDto
```

`dto` 子目录里的类都是简单的 Kotlin `data class`，用于定义发送给前端的 JSON 结构。它们和前端 `komga-webui/src/types/komga-sse.ts` 中的 TypeScript interface 基本一一对应。

主要 DTO 可以按资源类型理解：

- `LibrarySseDto`：只包含 `libraryId`。
- `SeriesSseDto`：包含 `seriesId`、`libraryId`。
- `BookSseDto`：包含 `bookId`、`seriesId`、`libraryId`。
- `ReadListSseDto`：包含 `readListId` 和相关 `bookIds`。
- `CollectionSseDto`：包含 `collectionId` 和相关 `seriesIds`。
- `ReadProgressSseDto`：包含 `bookId`、`userId`。
- `ReadProgressSeriesSseDto`：包含 `seriesId`、`userId`。
- `ThumbnailBookSseDto`、`ThumbnailSeriesSseDto`、`ThumbnailReadListSseDto`、`ThumbnailSeriesCollectionSseDto`：描述缩略图所属资源和是否选中。
- `BookImportSseDto`：包含导入结果、来源文件、可选的 `bookId` 和错误/提示信息。
- `TaskQueueSseDto`：包含任务总数和按任务类型分组的数量。
- `SessionExpiredDto`：包含需要被踢下线的 `userId`。

## 上下游关系

上游是领域层和部分接口层发布的 `DomainEvent`。例如 `komga/src/main/kotlin/org/gotson/komga/domain/service/SeriesLifecycle.kt` 在创建 series 后发布 `DomainEvent.SeriesAdded`，在新增 books 后发布 `DomainEvent.BookAdded`；`komga/src/main/kotlin/org/gotson/komga/domain/service/BookLifecycle.kt` 在保存阅读进度后发布 `DomainEvent.ReadProgressChanged`，在新增或删除书籍缩略图后发布 thumbnail 相关事件；`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/BookController.kt` 在标记书籍封面为 selected 后也会发布 `DomainEvent.ThumbnailBookAdded`。

中间层就是 `SseController.handleSseEvent()`。它不修改领域对象，也不重新执行业务逻辑，只做事件名转换、DTO 组装和按用户过滤。

下游是 Web UI 的 SSE 服务：`komga-webui/src/services/komga-sse.service.ts`。前端连接 `/sse/v1/events` 后，注册 `LibraryAdded`、`BookChanged`、`ReadProgressChanged`、`ThumbnailBookAdded`、`TaskQueueStatus`、`SessionExpired` 等事件监听器。普通事件会被 `JSON.parse(event.data)` 后转发到 Vue 的 `$eventHub`；`TaskQueueStatus` 会直接提交到 Vuex store 的 `setTaskCount`；`SessionExpired` 在 `komga-webui/src/App.vue` 中会触发 logout 并跳转到 login 页面。

权限关系也值得注意。SSE 连接方法需要 `@AuthenticationPrincipal principal: KomgaPrincipal`，说明连接依赖当前认证用户。具体端点授权由 Spring Security 全局配置负责；从 `SecurityConfiguration.kt` 的搜索结果看，除显式放行的端点外，其他端点要求 authenticated。因此根据当前片段推断，`/sse/v1/events` 是登录后使用的连接。

## 运行/调用流程

一个典型流程如下。

1. 用户登录 Web UI 后，前端 store 的 `authenticated` 变为 true。
2. `KomgaSseService` 监听到认证状态变化，调用 `connect()`。
3. 前端创建 `EventSource(urls.originNoSlash + "/sse/v1/events", {withCredentials: true})`，浏览器带 cookie 建立 SSE 长连接。
4. 后端 `SseController.sse()` 创建 `SseEmitter`，把 emitter 和 `principal.user` 放入 `emitters`。
5. 业务操作发生。例如扫描书库新增书籍，`SeriesLifecycle` 写入数据后发布 `DomainEvent.BookAdded`。
6. Spring 调用 `SseController.handleSseEvent()`。
7. 控制器把 `BookAdded` 转成事件名 `"BookAdded"` 和 `BookSseDto(bookId, seriesId, libraryId)`。
8. `emitSse()` 遍历所有 emitter，按 `adminOnly` 或 `userIdOnly` 过滤目标用户，然后用 `emitter.send(SseEmitter.event().name(name).data(data, MediaType.APPLICATION_JSON))` 发送 JSON。
9. 前端对应的 `addEventListener("BookAdded", ...)` 收到事件，把 JSON 解析后通过 `$eventHub` 广播给页面组件。
10. 页面组件或全局逻辑根据事件刷新局部数据，例如重新拉取书库列表、更新任务数量、刷新封面或处理登出。

过滤逻辑是理解这个目录的重点之一。`emitSse()` 支持两个过滤参数：

```text
adminOnly = true
```

只推送给 `KomgaUser.isAdmin == true` 的连接，当前用于 `BookImported` 和 `TaskQueueStatus`。

```text
userIdOnly = someUserId
```

只推送给指定用户，当前用于阅读进度和会话过期事件。例如 `ReadProgressChanged` 只推送给拥有该阅读进度的用户；`UserDeleted` 或带 `expireSession` 的 `UserUpdated` 只向对应用户发送 `SessionExpired`。

还有一个生命周期处理点：`SseController` 实现了 `SmartLifecycle`。在 `stop()` 中，它会先把 `acceptingConnections` 设为 false，随后 complete 所有现有 emitter。这样服务关闭时不会继续接受新的 SSE 连接，也会主动结束已有连接。

## 小白阅读顺序

建议先看 `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt`，不要一开始钻 DTO。重点看三个方法：`sse()`、`handleSseEvent()`、`emitSse()`。这三个方法分别对应“建立连接”、“接收内部事件”、“发给浏览器”。

第二步看 `komga/src/main/kotlin/org/gotson/komga/domain/model/DomainEvent.kt`。它定义了所有可能被 SSE 转发的领域事件。读完这里，再回到 `handleSseEvent()`，就能理解为什么 `when` 分支覆盖了 library、series、book、read list、collection、read progress、thumbnail、user 等类别。

第三步看 `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/dto`。这些文件都很短，不需要逐行深挖业务，只要记住它们是“后端发给前端的 JSON shape”。如果要改字段，通常还要同步改 `komga-webui/src/types/komga-sse.ts`。

第四步看前端消费端 `komga-webui/src/services/komga-sse.service.ts`。这里能看到后端事件名是否真的被前端监听，以及事件最后是进入 Vue event hub 还是 Vuex store。

第五步再抽样看事件发布者，例如 `SeriesLifecycle.kt`、`BookLifecycle.kt`、`BookController.kt`。这一步的目的不是学完整业务，而是确认某类 SSE 事件在什么业务动作后产生。

## 常见误区

第一个误区是把 SSE 当成 REST API。`/sse/v1/events` 不是一次请求一次响应的查询接口，而是长连接。建立连接后，服务端可以持续推送多个事件。前端也不是用 `fetch` 调它，而是用浏览器原生 `EventSource`。

第二个误区是认为 `SseController` 会决定业务是否成功。它不会。业务成功与否发生在 domain service 或 REST controller 中；`SseController` 只是在业务事件已经发布之后，把结果通知给客户端。比如书籍新增、阅读进度保存、缩略图选择，这些都不是在 SSE 层完成的。

第三个误区是忽略事件名的兼容性。后端发送的是字符串事件名，例如 `"BookChanged"`、`"ReadProgressSeriesDeleted"`、`"ThumbnailSeriesCollectionAdded"`。前端必须用完全相同的名字注册 `addEventListener`。改事件名会直接影响前端实时更新。

第四个误区是认为所有用户都会收到所有事件。实际上有两层过滤：`adminOnly` 限制管理员事件，`userIdOnly` 限制用户私有事件。阅读进度和会话过期不应该广播给所有人；任务队列和导入结果则偏管理员视角。

第五个误区是误解 heartbeat。`heartbeat()` 发送的是 SSE comment，不是有业务 payload 的命名事件。前端服务没有为 heartbeat 注册业务监听器，它主要用于保持连接活跃。

第六个误区是只改后端 DTO。这个目录的 DTO 与前端 `komga-webui/src/types/komga-sse.ts` 有对应关系。如果新增字段、删除字段或改变可空性，前端类型和消费逻辑也可能需要同步调整。对于新增事件，还需要同时更新后端 `handleSseEvent()`、前端 `komga-sse.service.ts` 的监听器，以及实际使用该事件的页面或 store。
