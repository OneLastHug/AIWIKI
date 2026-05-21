# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt

## 它负责什么

`SseController.kt` 是 Komga 后端的 Server-Sent Events 控制器，负责把服务端内部的领域事件 `DomainEvent` 转换成浏览器可以订阅的 SSE 事件。

它做的事情可以概括为三类：

1. 提供 SSE 连接入口：`GET sse/v1/events`
2. 监听后端领域事件：`@EventListener fun handleSseEvent(event: DomainEvent)`
3. 向已连接的前端用户推送 JSON 事件，例如 `BookAdded`、`ReadProgressChanged`、`TaskQueueStatus`、`SessionExpired`

它不是业务逻辑的生产者。图书导入、阅读进度修改、书库变化等业务事件是在其他 domain/service 层产生的，例如 `BookImporter`、`BookLifecycle`、`LibraryLifecycle` 等。`SseController` 的职责是“转发与过滤”：收到领域事件后，决定推送什么事件名、什么 DTO、推送给哪些用户。

## 关键组成

### 包与定位

文件位于：

`komga/src/main/kotlin/org/gotson/komga/interfaces/sse/SseController.kt`

包名是：

`org.gotson.komga.interfaces.sse`

从路径和包名看，它属于 `interfaces` 层，也就是对外接口层。它面对的是 Web 客户端，不直接承担核心领域规则。

### 主要依赖 import

这个文件的 import 可以分成几组理解：

第一组是 Spring Web / Spring 生命周期相关：

- `@Controller`：声明这是 Spring MVC 控制器。
- `@GetMapping`：声明 HTTP 路由。
- `@AuthenticationPrincipal`：从 Spring Security 当前认证信息中取出用户主体。
- `SseEmitter`：Spring MVC 提供的 SSE 连接对象。
- `@EventListener`：监听 Spring 应用事件。
- `@Scheduled`：定时任务，用于心跳和任务队列状态推送。
- `SmartLifecycle`：让该组件参与 Spring 容器生命周期，在停止时关闭 SSE 连接。

第二组是 Komga 领域与基础设施：

- `DomainEvent`：后端内部的领域事件总类型。
- `KomgaUser`：当前连接对应的用户信息。
- `KomgaPrincipal`：认证主体，里面包含 `user`。
- `BookRepository`：在缩略图事件中根据 `bookId` 查询 `seriesId`。
- `TasksRepository`：定时统计任务队列数量。
- `toFilePath`：把导入事件中的 `URL` 转换成适合前端展示/传输的文件路径字符串。

第三组是 SSE DTO：

- `LibrarySseDto`
- `SeriesSseDto`
- `BookSseDto`
- `BookImportSseDto`
- `CollectionSseDto`
- `ReadListSseDto`
- `ReadProgressSseDto`
- `ReadProgressSeriesSseDto`
- `ThumbnailBookSseDto`
- `ThumbnailSeriesSseDto`
- `ThumbnailSeriesCollectionSseDto`
- `ThumbnailReadListSseDto`
- `TaskQueueSseDto`
- `SessionExpiredDto`

这些 DTO 都在 `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/dto/` 下，基本都是很薄的 `data class`，只承载前端需要的 id、状态和计数。

### 类定义

核心类是：

```kotlin
@Controller
class SseController(
  private val bookRepository: BookRepository,
  private val tasksRepository: TasksRepository,
) : SmartLifecycle
```

它是一个 Spring MVC `@Controller`，同时实现了 `SmartLifecycle`。

构造函数注入了两个仓储：

- `bookRepository`：只在图书缩略图事件中使用，用来补充 `seriesId`。
- `tasksRepository`：定时推送任务队列状态时使用。

### 连接状态

类中有两个重要字段：

```kotlin
private var acceptingConnections = true
private val emitters = Collections.synchronizedMap(HashMap<SseEmitter, KomgaUser>())
```

`acceptingConnections` 用来控制服务关闭阶段是否还接受新的 SSE 连接。

`emitters` 保存当前所有 SSE 连接。它的 key 是 `SseEmitter`，value 是该连接对应的 `KomgaUser`。这很关键，因为后续推送事件时需要根据用户权限或用户 id 做过滤。

例如：

- 管理员专属事件：只发给 `user.isAdmin == true` 的连接。
- 阅读进度事件：只发给对应 `userId` 的连接。
- 会话过期事件：只发给被更新或删除的那个用户。

### SSE 入口：`sse`

```kotlin
@GetMapping("sse/v1/events")
fun sse(
  @AuthenticationPrincipal principal: KomgaPrincipal,
): SseEmitter
```

这是前端建立 SSE 长连接的入口。

处理流程：

1. 如果 `acceptingConnections == false`，说明服务正在关闭，直接抛出 `IllegalStateException`。
2. 创建一个新的 `SseEmitter()`。
3. 注册 `onCompletion`、`onTimeout`、`onError` 回调。
4. 任何结束、超时、错误发生时，都从 `emitters` 移除该连接。
5. 把 `emitter -> principal.user` 保存到连接表。
6. 返回 `SseEmitter` 给 Spring MVC，由框架保持 HTTP SSE 连接。

这里没有显式设置超时时间，所以使用 Spring `SseEmitter()` 默认行为。具体超时策略还可能受 Spring MVC 配置、容器和代理影响。

### 心跳：`heartbeat`

```kotlin
@Scheduled(fixedRate = 15_000)
fun heartbeat()
```

每 15 秒执行一次。

如果存在连接，就遍历所有 `SseEmitter`，发送一个 SSE comment：

```kotlin
SseEmitter.event().comment("heartbeat")
```

这不是业务事件，不会被前端当成 `BookAdded` 之类的事件处理。它主要用于保持连接活跃，降低中间代理或浏览器认为连接空闲而断开的概率。

发送时如果遇到 `IOException`，代码会忽略异常。连接真正移除依赖 `onError`、`onTimeout`、`onCompletion`，或者下一次生命周期清理。

### 任务队列状态：`taskCount`

```kotlin
@Scheduled(fixedRate = 10_000)
fun taskCount()
```

每 10 秒执行一次。

如果存在 SSE 连接，则调用：

```kotlin
val tasksCount = tasksRepository.countBySimpleType()
```

然后推送：

```kotlin
emitSse("TaskQueueStatus", TaskQueueSseDto(tasksCount.values.sum(), tasksCount), adminOnly = true)
```

注意这里 `adminOnly = true`，所以任务队列状态只发给管理员用户。DTO 内容包括：

- `count`：所有任务数量总和。
- `countByType`：按任务类型分组的数量。

前端 `komga-webui/src/services/komga-sse.service.ts` 中监听 `TaskQueueStatus` 后，会提交到 store：

```ts
this.store.commit('setTaskCount', data)
```

### 领域事件处理：`handleSseEvent`

```kotlin
@EventListener
fun handleSseEvent(event: DomainEvent)
```

这是文件中最核心的方法。它监听所有 Spring 发布出来的 `DomainEvent`，然后通过 `when` 分支转换成 SSE 事件。

`DomainEvent` 定义在：

`komga/src/main/kotlin/org/gotson/komga/domain/model/DomainEvent.kt`

它是一个 `sealed class`，包含书库、系列、图书、合集、阅读列表、阅读进度、缩略图、用户等领域事件。

`SseController` 做的映射大致如下。

书库事件：

- `DomainEvent.LibraryAdded` -> `LibraryAdded`
- `DomainEvent.LibraryUpdated` -> `LibraryChanged`
- `DomainEvent.LibraryDeleted` -> `LibraryDeleted`
- `DomainEvent.LibraryScanned` -> 不推送，直接 `Unit`

系列事件：

- `SeriesAdded` -> `SeriesAdded`
- `SeriesUpdated` -> `SeriesChanged`
- `SeriesDeleted` -> `SeriesDeleted`

图书事件：

- `BookAdded` -> `BookAdded`
- `BookUpdated` -> `BookChanged`
- `BookDeleted` -> `BookDeleted`
- `BookImported` -> `BookImported`，并且 `adminOnly = true`

阅读列表事件：

- `ReadListAdded` -> `ReadListAdded`
- `ReadListUpdated` -> `ReadListChanged`
- `ReadListDeleted` -> `ReadListDeleted`

合集事件：

- `CollectionAdded` -> `CollectionAdded`
- `CollectionUpdated` -> `CollectionChanged`
- `CollectionDeleted` -> `CollectionDeleted`

阅读进度事件：

- `ReadProgressChanged` -> `ReadProgressChanged`
- `ReadProgressDeleted` -> `ReadProgressDeleted`
- `ReadProgressSeriesChanged` -> `ReadProgressSeriesChanged`
- `ReadProgressSeriesDeleted` -> `ReadProgressSeriesDeleted`

这些事件都带有 `userIdOnly`，只推送给对应用户。原因是阅读进度是用户私有状态，不应该广播给所有连接用户。

缩略图事件：

- `ThumbnailBookAdded` -> `ThumbnailBookAdded`
- `ThumbnailBookDeleted` -> `ThumbnailBookDeleted`
- `ThumbnailSeriesAdded` -> `ThumbnailSeriesAdded`
- `ThumbnailSeriesDeleted` -> `ThumbnailSeriesDeleted`
- `ThumbnailSeriesCollectionAdded` -> `ThumbnailSeriesCollectionAdded`
- `ThumbnailSeriesCollectionDeleted` -> `ThumbnailSeriesCollectionDeleted`
- `ThumbnailReadListAdded` -> `ThumbnailReadListAdded`
- `ThumbnailReadListDeleted` -> `ThumbnailReadListDeleted`

其中 `ThumbnailBookSseDto` 需要 `seriesId`，但缩略图事件本身只有 `bookId`，所以这里通过：

```kotlin
bookRepository.getSeriesIdOrNull(event.thumbnail.bookId).orEmpty()
```

补充系列 id。如果查不到，就用空字符串。

用户事件：

- `UserUpdated`：只有 `event.expireSession == true` 时才推送 `SessionExpired`
- `UserDeleted`：推送 `SessionExpired`

并且都使用 `userIdOnly = event.user.id`，只通知被影响的用户退出或刷新认证状态。

### 推送函数：`emitSse`

```kotlin
private fun emitSse(
  name: String,
  data: Any,
  adminOnly: Boolean = false,
  userIdOnly: String? = null,
)
```

这是所有业务 SSE 事件的统一发送出口。

它的逻辑是：

1. 打 debug 日志：`Publish SSE: '事件名':数据`
2. 对 `emitters` 加锁。
3. 根据 `adminOnly` 过滤连接。
4. 根据 `userIdOnly` 过滤连接。
5. 对每个符合条件的 `SseEmitter` 发送事件。

发送格式是：

```kotlin
SseEmitter
  .event()
  .name(name)
  .data(data, MediaType.APPLICATION_JSON)
```

所以前端收到的是一个带事件名的 SSE 消息，数据部分是 JSON。

例如服务端发送：

```kotlin
emitSse("BookAdded", BookSseDto(bookId, seriesId, libraryId))
```

前端就可以用：

```ts
eventSource.addEventListener('BookAdded', ...)
```

来监听，然后 `JSON.parse(event.data)` 得到 DTO。

### 生命周期方法

`SseController` 实现了 `SmartLifecycle`：

```kotlin
override fun start() = Unit
override fun stop()
override fun isRunning(): Boolean = true
override fun getPhase(): Int = SmartLifecycle.DEFAULT_PHASE
```

这里最重要的是 `stop()`：

```kotlin
acceptingConnections = false
synchronized(emitters) {
  emitters.forEach { (emitter, _) -> emitter.complete() }
}
```

服务停止时：

1. 不再接受新的 SSE 连接。
2. 完成所有已有 `SseEmitter`。
3. 让客户端连接正常关闭。

`start()` 没有额外动作，`isRunning()` 永远返回 `true`，说明这个组件在容器运行期间一直被视为运行中。

## 上下游关系

### 上游：领域事件发布者

`SseController` 的直接上游是 Spring 事件机制中的 `DomainEvent`。

`DomainEvent` 定义在：

`komga/src/main/kotlin/org/gotson/komga/domain/model/DomainEvent.kt`

它包含大量后端业务事件，例如：

- `LibraryAdded`
- `SeriesUpdated`
- `BookDeleted`
- `BookImported`
- `ReadProgressChanged`
- `ThumbnailSeriesAdded`
- `UserDeleted`

这些事件通常由 domain/service 层发布。根据当前片段可见：

- `BookImporter` 会发布 `DomainEvent.BookImported`
- `LibraryLifecycle` 会发布 `DomainEvent.LibraryAdded`
- `BookLifecycle` 会发布 `DomainEvent.ReadProgressChanged`
- `SeriesLifecycle` 也会发布阅读进度相关事件

也就是说，`SseController` 不关心“图书为什么被导入”“阅读进度为什么改变”，它只关心“有事件发生后，应该怎么通知前端”。

### 下游：前端 SSE 服务

直接下游是：

`komga-webui/src/services/komga-sse.service.ts`

前端在用户认证状态变为已登录时调用：

```ts
this.connect()
```

然后创建：

```ts
new EventSource(urls.originNoSlash + API_SSE, {withCredentials: true})
```

其中：

```ts
const API_SSE = '/sse/v1/events'
```

这正好对应后端的：

```kotlin
@GetMapping("sse/v1/events")
```

前端对后端事件名逐个注册监听，例如：

- `LibraryAdded`
- `BookChanged`
- `ReadProgressDeleted`
- `ThumbnailSeriesAdded`
- `TaskQueueStatus`
- `SessionExpired`

普通事件会通过 `eventHub.$emit(...)` 分发给 Vue 应用内部其他组件；`TaskQueueStatus` 会更新 Vuex store 里的任务数量。

### DTO 契约

后端 DTO 位于：

`komga/src/main/kotlin/org/gotson/komga/interfaces/sse/dto/`

前端类型位于：

`komga-webui/src/types/komga-sse.ts`

二者字段基本一一对应。例如后端：

```kotlin
data class BookSseDto(
  val bookId: String,
  val seriesId: String,
  val libraryId: String,
)
```

前端：

```ts
export interface BookSseDto {
  bookId: string,
  seriesId: string,
  libraryId: string,
}
```

这里没有使用 OpenAPI 或自动生成类型，至少从当前片段看，后端 Kotlin DTO 和前端 TypeScript interface 是手工保持一致的。因此修改 DTO 字段时，需要同步检查前端类型和消费代码。

## 运行/调用流程

以用户打开 Web UI 后监听图书变化为例：

1. 用户登录 Komga Web UI。
2. 前端认证状态变为 `authenticated = true`。
3. `KomgaSseService` 创建 `EventSource`，连接 `/sse/v1/events`。
4. 后端 `SseController.sse()` 被调用。
5. Spring Security 把当前认证主体注入为 `KomgaPrincipal`。
6. 后端创建 `SseEmitter`，并把它和 `principal.user` 存入 `emitters`。
7. 前端注册各种事件监听器，例如 `BookAdded`、`BookChanged`。
8. 后端某个业务服务发布 `DomainEvent.BookUpdated`。
9. `SseController.handleSseEvent()` 收到该事件。
10. `when` 分支把它转换成：
    ```kotlin
    emitSse("BookChanged", BookSseDto(...))
    ```
11. `emitSse()` 遍历所有连接用户。
12. 如果没有特殊过滤条件，就向所有连接发送 JSON SSE 消息。
13. 前端 `EventSource` 收到 `BookChanged`。
14. `KomgaSseService.emit()` 执行 `JSON.parse(event.data)`。
15. Vue 的 `eventHub` 把事件分发给页面、组件或 store。
16. UI 根据事件刷新局部状态或提示用户。

再看一个带权限过滤的流程：图书导入事件。

1. `BookImporter` 导入成功或失败。
2. 它发布 `DomainEvent.BookImported`。
3. `SseController` 转成：
   ```kotlin
   emitSse("BookImported", BookImportSseDto(...), adminOnly = true)
   ```
4. `emitSse()` 只保留 `KomgaUser.isAdmin == true` 的连接。
5. 只有管理员前端收到导入结果。
6. 前端可在通知组件中展示导入成功或失败信息。

再看一个用户隔离事件：阅读进度变化。

1. 某用户更新阅读进度。
2. 后端发布 `DomainEvent.ReadProgressChanged(progress)`。
3. `SseController` 转成：
   ```kotlin
   emitSse(
     "ReadProgressChanged",
     ReadProgressSseDto(event.progress.bookId, event.progress.userId),
     userIdOnly = event.progress.userId,
   )
   ```
4. `emitSse()` 只向 `user.id == progress.userId` 的连接发送。
5. 其他用户不会收到这个阅读进度事件。

## 小白阅读顺序

建议按下面顺序读，不要一开始陷入所有事件分支。

1. 先看 `sse()` 方法  
   理解 `/sse/v1/events` 是怎么建立连接的，以及为什么要保存 `SseEmitter -> KomgaUser`。

2. 再看 `emitters` 字段  
   这是整个文件的核心状态。理解它之后，就能明白后面为什么可以按管理员和用户 id 过滤事件。

3. 再看 `emitSse()`  
   这是统一发送函数。重点看 `adminOnly`、`userIdOnly`、`.name(name)`、`.data(data, MediaType.APPLICATION_JSON)`。

4. 然后看 `handleSseEvent()` 的 `when`  
   不需要逐行背事件名，只要理解模式：`DomainEvent.Xxx` 被映射成前端监听的字符串事件名和一个轻量 DTO。

5. 接着看 `dto/` 目录  
   这些 DTO 很简单，适合快速建立“后端发给前端的数据长什么样”的直觉。

6. 再看前端 `komga-webui/src/services/komga-sse.service.ts`  
   对照后端事件名，看前端如何 `addEventListener`、`JSON.parse`、`eventHub.$emit` 或更新 store。

7. 最后看 `DomainEvent.kt`  
   这能帮助你理解这些 SSE 事件的来源。但领域事件本身属于更底层的业务模型，不必一开始就深入所有发布点。

## 常见误区

### 误区一：以为 `SseController` 负责产生业务事件

不是。它只是监听 `DomainEvent` 并转发给前端。

真正产生事件的是业务服务，例如导入、扫描、修改阅读进度、删除用户等逻辑所在的 service/lifecycle 类。`SseController` 不决定一本书是否应该被添加，也不修改阅读进度。

### 误区二：以为所有事件都会广播给所有用户

不是。

这个文件里有两种过滤：

- `adminOnly = true`：只发给管理员，例如 `BookImported`、`TaskQueueStatus`。
- `userIdOnly = xxx`：只发给指定用户，例如阅读进度和会话过期。

没有这两个参数时，才是发给所有当前连接用户。

### 误区三：以为 `heartbeat` 是业务事件

`heartbeat()` 发送的是 SSE comment：

```kotlin
.comment("heartbeat")
```

它主要用于维持连接，不是前端业务事件。前端不需要注册 `heartbeat` 事件监听。

### 误区四：以为 `LibraryScanned` 会通知前端

`DomainEvent.LibraryScanned` 在这里被处理为：

```kotlin
is DomainEvent.LibraryScanned -> Unit
```

也就是明确不推送 SSE。扫描过程中的可见状态可能通过其他事件体现，例如图书、系列、任务队列状态变化。根据当前片段推断，`LibraryScanned` 更像内部生命周期事件，不直接对应前端通知。

### 误区五：忽略后端 DTO 和前端 interface 的同步

后端 DTO 在 `komga/src/main/kotlin/org/gotson/komga/interfaces/sse/dto/`。

前端类型在 `komga-webui/src/types/komga-sse.ts`。

两边字段需要保持一致。如果后端给 `BookSseDto` 改字段名，前端 `JSON.parse(event.data)` 虽然仍能运行，但后续组件读取旧字段时可能得到 `undefined`。

### 误区六：以为 `SseEmitter` 发送失败一定会立刻清理连接

`emitSse()` 和 `heartbeat()` 捕获 `IOException` 后没有在 catch 中主动移除 emitter。连接清理主要依赖：

- `onCompletion`
- `onTimeout`
- `onError`
- 服务停止时 `stop()`

因此阅读时不要把 `catch IOException` 理解为完整的连接回收逻辑。它这里只是避免一次发送失败打断整个遍历。

### 误区七：忽略服务关闭阶段的处理

`SseController` 实现 `SmartLifecycle`，在 `stop()` 中：

1. 设置 `acceptingConnections = false`
2. 完成所有已有 emitter

这表示服务关闭期间不会再接受新 SSE 连接，并且会主动关闭已有连接。这个逻辑和普通事件推送同样重要，否则客户端可能在服务停止时挂着长连接。
