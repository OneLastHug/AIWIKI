# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaSyncToken.kt

## 它负责什么

`KomgaSyncToken.kt` 定义了领域模型 `KomgaSyncToken`，它是 Komga 在 Kobo 同步流程中使用的同步状态载体。

这个文件本身没有业务方法，也没有数据库访问逻辑；它只负责描述“一次 Kobo/Komga 同步会话当前进行到哪里”。它会被序列化成字符串，放进 HTTP 响应头 `X-KOBO-SYNCTOKEN`，再由 Kobo 客户端在下一次请求时带回来。服务端读取这个 token 后，就能判断：

- 这是不是 Komga 自己生成的同步 token。
- 当前是否还有一个未完成的同步批次。
- 上一次完整成功的同步点是哪一个。
- 是否需要继续沿用原始 Kobo 官方商店的同步 token。

换句话说，`KomgaSyncToken` 是 Komga 对 Kobo 同步协议的一个“包装 token”：既保留 Kobo 官方 token，又加入 Komga 自己的同步点信息。

目标文件内容很短：

```kotlin
data class KomgaSyncToken(
  val version: Int = 1,
  val rawKoboSyncToken: String = "",
  val ongoingSyncPointId: String? = null,
  val lastSuccessfulSyncPointId: String? = null,
)
```

它位于包：

```kotlin
org.gotson.komga.domain.model
```

由于它只依赖 Kotlin 基础类型 `Int`、`String` 和可空类型语法，文件中没有额外 `import`。

## 关键组成

`KomgaSyncToken` 是一个 Kotlin `data class`。这意味着编译器会自动生成 `copy`、`equals`、`hashCode`、`toString`、解构等方法。在同步流程里，代码大量依赖 `copy(...)` 来更新部分字段，例如只更新 `ongoingSyncPointId`，或者只替换 `rawKoboSyncToken`。

### `version: Int = 1`

`version` 表示 Komga 自定义 token 格式的版本号。当前默认值是 `1`。

从当前片段看，业务代码还没有基于 `version` 做分支处理；它更像是为未来 token 格式升级预留的兼容字段。因为 token 会被序列化后交给客户端保存，再在之后的请求中带回来，一旦结构变更，版本号可以帮助服务端识别旧格式。

### `rawKoboSyncToken: String = ""`

`rawKoboSyncToken` 保存原始 Kobo 商店同步 token。

这是 Komga 做 Kobo 代理时很关键的字段。`KoboProxy` 在把请求转发给 `[URL已移除] 时，如果 `includeSyncToken = true`，会从当前请求头里解析出 `KomgaSyncToken`，然后把其中的 `rawKoboSyncToken` 作为真正的 `X-KOBO-SYNCTOKEN` 发给 Kobo 官方接口。

对应逻辑在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KoboProxy.kt`：

```kotlin
if (syncToken != null && syncToken.rawKoboSyncToken.isNotBlank()) {
  headersOut.add(X_KOBO_SYNCTOKEN, syncToken.rawKoboSyncToken)
}
```

也就是说，客户端看到的是 Komga 包装后的 token；Kobo 官方服务看到的仍然是原始 Kobo token。

### `ongoingSyncPointId: String? = null`

`ongoingSyncPointId` 表示“当前正在进行但尚未完整结束的同步点 ID”。

注释写得很直接：

```kotlin
/**
 * Only if a sync is currently ongoing, else null.
 */
```

在 Kobo 同步接口中，如果一次同步内容太多，服务端不会一次返回所有变更，而是分批返回，并在响应头中设置 `X-KOBO-SYNC: continue`。这时 Komga 会把本次生成的 `SyncPoint.id` 写入 `ongoingSyncPointId`，让下一次请求继续从同一个目标同步点取剩余数据。

调用方在 `KoboController.syncLibrary` 中使用这个字段：

```kotlin
val toSyncPoint =
  getSyncPointVerified(syncTokenReceived.ongoingSyncPointId, principal.user.id)
    ?: syncPointLifecycle.createSyncPoint(...)
```

含义是：

- 如果 token 中有 `ongoingSyncPointId`，并且这个同步点属于当前用户，就继续使用它。
- 如果没有，就创建一个新的 `SyncPoint` 作为本次同步目标。

### `lastSuccessfulSyncPointId: String? = null`

`lastSuccessfulSyncPointId` 表示“上一次完整成功完成的同步点 ID”。

注释是：

```kotlin
/**
 * The last successful SyncPoint ID.
 */
```

这个字段用于增量同步。Komga 会把它作为 `fromSyncPoint`，再把当前同步点作为 `toSyncPoint`，然后计算两者之间新增、变更、删除的书籍、阅读进度、书单等。

在 `KoboController.syncLibrary` 中：

```kotlin
val fromSyncPoint = getSyncPointVerified(syncTokenReceived.lastSuccessfulSyncPointId, principal.user.id)
```

如果 `fromSyncPoint` 存在，就走增量同步；如果不存在，就认为这是首次同步或无法定位历史同步点，于是走全量同步。

## 上下游关系

`KomgaSyncToken.kt` 处在领域模型层，直接上游和下游主要集中在 Kobo 同步相关代码中。

### 上游：HTTP 请求头和 token 解析器

客户端请求 Komga 的 Kobo API 时，会带上 `X-KOBO-SYNCTOKEN` 请求头。这个请求头先由 `KomgaSyncTokenGenerator` 解析。

相关文件：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KomgaSyncTokenGenerator.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KoboProxy.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`

`KomgaSyncTokenGenerator.fromRequestHeaders(request)` 会读取 `X-KOBO-SYNCTOKEN`，然后调用 `fromBase64(...)`。

`fromBase64(...)` 支持三类 token：

1. Komga 自己生成的 token：以 `KOMGA.` 开头。
2. Calibre Web token：单段 base64 字符串。
3. Kobo 官方商店 token：形如 `base64.base64`。

如果是 Komga token，代码会去掉 `KOMGA.` 前缀，base64 解码，然后用 Jackson 反序列化成 `KomgaSyncToken`：

```kotlin
objectMapper.readValue(...)
```

如果是 Kobo 官方 token，代码会创建：

```kotlin
KomgaSyncToken(rawKoboSyncToken = base64Token)
```

如果无法识别，最后退回默认值：

```kotlin
KomgaSyncToken()
```

所以 `KomgaSyncToken` 既可以表示 Komga 自己的同步状态，也可以临时包住外部 Kobo token。

### 下游：KoboController 的同步决策

最核心下游是 `KoboController.syncLibrary`。

它从请求中解析 token：

```kotlin
val syncTokenReceived = komgaSyncTokenGenerator.fromRequestHeaders(getCurrentRequest()) ?: KomgaSyncToken()
```

然后根据 token 中的两个同步点字段决定同步范围：

- `ongoingSyncPointId` 决定是否继续一个未完成同步。
- `lastSuccessfulSyncPointId` 决定从哪个历史同步点开始计算增量。

如果 `fromSyncPoint != null`，则取两个同步点之间的差异，包括：

- 新增书籍。
- 变更书籍。
- 删除书籍。
- 阅读进度变更。
- 新增书单。
- 变更书单。
- 删除书单。

如果 `fromSyncPoint == null`，则走全量同步，取当前同步点下所有书籍和书单。

### 下游：KoboProxy 与官方 Kobo token 合并

当 Komga 自己的数据同步完成后，如果 Kobo 代理开启，`KoboController` 会调用 `KoboProxy.proxyCurrentRequest(includeSyncToken = true)`，把请求继续转发给 Kobo 官方商店接口。

此时 `KoboProxy` 会：

1. 从 Komga token 中取出 `rawKoboSyncToken`。
2. 把它作为官方 `X-KOBO-SYNCTOKEN` 发给 Kobo。
3. 如果 Kobo 响应中返回了新的官方 sync token，则把它写回 `KomgaSyncToken.rawKoboSyncToken`。
4. 再用 `KomgaSyncTokenGenerator.toBase64(...)` 重新包装成 `KOMGA.` token 返回给设备。

这使 Komga 能够同时维护两套同步状态：

- Komga 自己的图书馆同步点。
- Kobo 官方商店的同步 token。

### 邻近模型：SyncPoint

`KomgaSyncToken` 中保存的是 `SyncPoint.id`，真正的同步快照模型在：

`komga/src/main/kotlin/org/gotson/komga/domain/model/SyncPoint.kt`

`SyncPoint` 包含：

```kotlin
data class SyncPoint(
  val id: String,
  val userId: String,
  val apiKeyId: String?,
  val createdDate: ZonedDateTime,
)
```

它下面还有嵌套模型：

- `SyncPoint.Book`
- `SyncPoint.ReadList`
- `SyncPoint.ReadList.Book`

这些结构记录某个同步点下的书籍、书单、文件哈希、修改时间、是否已同步等信息。`KomgaSyncToken` 不保存这些详细数据，只保存同步点 ID，用来让服务端回查完整同步快照。

## 运行/调用流程

一个典型的 Kobo library sync 流程如下。

### 1. 客户端首次请求同步接口

客户端请求：

```text
/kobo/{apiKey}/v1/library/sync
```

如果请求头里没有 `X-KOBO-SYNCTOKEN`，`KoboController` 会使用默认 token：

```kotlin
KomgaSyncToken()
```

此时：

```kotlin
version = 1
rawKoboSyncToken = ""
ongoingSyncPointId = null
lastSuccessfulSyncPointId = null
```

因为 `ongoingSyncPointId` 为空，控制器会创建新的 `SyncPoint`，作为本次同步目标。

因为 `lastSuccessfulSyncPointId` 也为空，控制器认为没有可用的历史成功同步点，于是走全量同步。

### 2. 如果数据没有一次返回完

Komga 会根据配置限制单次同步返回数量。若还有剩余内容，变量 `shouldContinueSync` 会为 `true`。

响应时，控制器会更新 token：

```kotlin
syncTokenMerged.copy(ongoingSyncPointId = toSyncPoint.id)
```

并设置响应头：

```text
X-KOBO-SYNC: continue
X-KOBO-SYNCTOKEN: KOMGA.{base64-json}
```

此时 token 中：

```kotlin
ongoingSyncPointId = 当前 SyncPoint.id
lastSuccessfulSyncPointId = null
```

测试 `KoboControllerTest` 中也验证了这一点：第一次同步后，`ongoingSyncPointId` 非空，`lastSuccessfulSyncPointId` 为空。

### 3. 客户端带着 token 再次请求

第二次请求时，客户端会把上一次响应里的 `X-KOBO-SYNCTOKEN` 放回请求头。

`KomgaSyncTokenGenerator` 识别到 `KOMGA.` 前缀后，还原出 `KomgaSyncToken`。`KoboController` 用 `ongoingSyncPointId` 找回同一个目标同步点，于是继续同步剩余项目，而不是重新创建同步点。

这就是 `ongoingSyncPointId` 的作用：它让多批次同步保持在同一个“目标快照”上。

### 4. 当同步全部完成

如果没有剩余项目，`shouldContinueSyncMerged` 为 `false`。控制器会：

```kotlin
syncTokenMerged.copy(
  ongoingSyncPointId = null,
  lastSuccessfulSyncPointId = toSyncPoint.id,
)
```

同时如果存在旧的 `fromSyncPoint`，还会删除旧同步点：

```kotlin
fromSyncPoint?.let { syncPointRepository.deleteOne(it.id) }
```

最终返回的新 token 中：

```kotlin
ongoingSyncPointId = null
lastSuccessfulSyncPointId = 当前 SyncPoint.id
```

这表示本轮同步已经完整成功。下一次同步时，Komga 就能从这个成功同步点开始做增量比较。

测试中也验证了第二次同步后的状态：`ongoingSyncPointId` 为空，`lastSuccessfulSyncPointId` 等于第一次同步时的 `ongoingSyncPointId`。

### 5. 如果 Kobo 官方代理开启

当 Komga 自己没有剩余同步项，并且 Kobo proxy 开启时，控制器会把同步请求继续转发给 Kobo 官方商店。

此时 `rawKoboSyncToken` 开始发挥作用：

- 转发请求时，Komga 把 `rawKoboSyncToken` 放进发往 Kobo 官方接口的 `X-KOBO-SYNCTOKEN`。
- Kobo 官方接口返回新的 token 后，Komga 把它写回 `rawKoboSyncToken`。
- 最后再把整个 `KomgaSyncToken` 编码成 `KOMGA.` token 返回给设备。

这样设备端只需要保存一个 token，Komga 内部却能同时追踪 Komga 图书库同步和 Kobo 官方商店同步。

## 小白阅读顺序

建议按下面顺序理解，不要直接从 `KoboController` 大段逻辑开始读。

1. 先读 `komga/src/main/kotlin/org/gotson/komga/domain/model/KomgaSyncToken.kt`

   先记住四个字段的含义：`version` 是格式版本，`rawKoboSyncToken` 是官方 Kobo token，`ongoingSyncPointId` 是进行中的同步点，`lastSuccessfulSyncPointId` 是上次成功同步点。

2. 再读 `komga/src/main/kotlin/org/gotson/komga/domain/model/SyncPoint.kt`

   理解 `KomgaSyncToken` 中保存的两个 ID 指向什么。`SyncPoint` 才是真正描述同步快照的领域模型，`KomgaSyncToken` 只是保存快照 ID。

3. 再读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KomgaSyncTokenGenerator.kt`

   重点看 `fromBase64(...)` 和 `toBase64(...)`。这里能理解为什么响应头里的 token 不是普通 JSON，而是 `KOMGA.` 加 base64 后的 JSON。

4. 再读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt` 中的 `syncLibrary`

   重点看三段：

   - 读取 token。
   - 根据 `ongoingSyncPointId` 和 `lastSuccessfulSyncPointId` 找同步点。
   - 根据 `shouldContinueSyncMerged` 更新 token。

5. 最后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KoboProxy.kt`

   这部分用于理解 `rawKoboSyncToken` 为什么存在。没有 Kobo 官方代理场景时，容易误以为这个字段没有用；读完代理逻辑后会发现它负责和官方 Kobo 同步协议衔接。

6. 可以用测试辅助理解

   `komga/src/test/kotlin/org/gotson/komga/interfaces/api/kobo/KoboControllerTest.kt` 中有同步两次的测试，清楚展示了：

   - 第一次响应要求继续同步，token 中有 `ongoingSyncPointId`。
   - 第二次同步完成后，`ongoingSyncPointId` 清空，`lastSuccessfulSyncPointId` 更新为上一次的同步点 ID。

## 常见误区

### 误区一：把 `KomgaSyncToken` 当成数据库实体

它不是数据库实体。文件中没有 JPA、Spring Data、表名、主键注解，也没有 repository 直接存取它。它主要通过 HTTP header 在客户端和服务端之间往返，并由 Jackson 序列化/反序列化。

真正持久化或可查询的同步数据在 `SyncPoint` 及其 repository/lifecycle 相关逻辑中。`KomgaSyncToken` 只是携带 `SyncPoint.id`。

### 误区二：以为 `ongoingSyncPointId` 和 `lastSuccessfulSyncPointId` 可以同时表示同一件事

这两个字段语义不同。

`ongoingSyncPointId` 表示“这轮同步还没结束，请下一次继续用这个目标同步点”。它只应该在同步尚未完成时存在。

`lastSuccessfulSyncPointId` 表示“上一轮完整同步已经成功，可以作为下一次增量同步的起点”。它只在完整同步结束后更新。

如果把二者混用，会导致增量范围错误：要么重复同步，要么漏掉变更。

### 误区三：以为 `rawKoboSyncToken` 是 Komga 自己的 token

`rawKoboSyncToken` 不是 Komga 包装 token，而是官方 Kobo 商店的原始 sync token。

Komga 自己返回给设备的是 `KOMGA.` 前缀加 base64 编码后的 JSON。这个 JSON 里面才包含 `rawKoboSyncToken`。当请求需要转发到 Kobo 官方商店时，Komga 会把 `rawKoboSyncToken` 取出来，作为官方接口能识别的 `X-KOBO-SYNCTOKEN`。

### 误区四：以为没有 token 就无法同步

没有 token 时，Komga 会创建默认的 `KomgaSyncToken()`，然后走首次同步或全量同步路径。也就是说，token 缺失不是错误场景，而是首次同步的正常入口之一。

`KomgaSyncTokenGenerator.fromBase64(...)` 在无法识别 token 时也会退回默认 token。根据当前片段推断，这是为了兼容不同来源的 Kobo/Calibre Web token，同时避免同步流程因为 token 格式异常直接中断。

### 误区五：以为 `version` 当前控制了业务逻辑

当前代码中没有看到基于 `version` 的条件分支。它目前只是数据结构中的版本字段。根据当前片段推断，它的价值主要在未来兼容：如果以后 `KomgaSyncToken` 增加字段或改变编码结构，`version` 可以作为迁移判断依据。

### 误区六：忽略 Kotlin `data class copy(...)` 的作用

同步流程里并不是手动重新构造所有字段，而是用 `copy(...)` 在保留原字段的基础上改动少数字段。例如：

- 同步未完成时，只设置 `ongoingSyncPointId`。
- 同步完成时，清空 `ongoingSyncPointId`，更新 `lastSuccessfulSyncPointId`。
- Kobo 官方返回新 token 时，只替换 `rawKoboSyncToken`。

这正是 `KomgaSyncToken` 设计成不可变 `data class` 的原因之一：每次状态变化都产生一个新的 token 对象，逻辑更清晰，也更适合序列化后返回给客户端。
