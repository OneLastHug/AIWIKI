# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/R2Device.kt

## 它负责什么
`R2Device` 是一个非常轻量的领域模型，用来表示 Readium 2 Progression 里的“设备信息”。它只有两个字段：`id` 和 `name`，分别标识设备唯一性和设备显示名。

从用途上看，它不是业务规则承载者，而是一个协议层的数据载体。它会被包装进 `R2Progression`，和 `R2Locator`、`modified` 一起组成阅读进度对象，供 OPDS / Readium / Kobo 相关接口传输。

## 关键组成
这个文件本身几乎没有逻辑，只有一个 Kotlin `data class`：

- `id: String`：设备标识
- `name: String`：设备名称

它没有注解、没有方法、没有默认值，也没有序列化定制。也就是说，它的职责就是“存数据”，并依赖 Kotlin `data class` 自动提供 `equals`、`hashCode`、`toString`、`copy` 等能力。

根据当前片段推断，这个类的稳定性很高，因为它属于协议 DTO 风格的数据结构，字段很少、语义固定，通常只会在协议演进时才改动。

## 上下游关系
上游主要有两类来源：

- `komga/src/main/kotlin/org/gotson/komga/domain/model/R2Progression.kt`  
  `ReadProgress.toR2Progression()` 会把数据库里的 `deviceId`、`deviceName` 映射成 `R2Device(deviceId, deviceName)`。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/kosync/KoreaderSyncController.kt`  
  这两个控制器在接收外部阅读器同步请求时，会直接构造 `R2Device`，再塞进 `R2Progression`。

下游主要是 `R2Progression` 和它对应的 API 返回值：

- `komga/src/main/kotlin/org/gotson/komga/domain/model/R2Progression.kt`  
  `R2Device` 是 `R2Progression` 的组成部分。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/CommonBookController.kt`  
  `getBookProgression()` 会返回 `R2Progression`，因此最终对外的 JSON 中会带上 `device` 字段。
- `bookLifecycle.markProgression(...)` 这类流程  
  会把携带设备信息的阅读进度写回系统，用于后续查询和同步。

## 运行/调用流程
典型流程可以按“读”和“写”两条线理解：

1. 读取进度时，`ReadProgress` 从存储层取出 `deviceId`、`deviceName`。
2. `ReadProgress.toR2Progression()` 把这两个字段映射成 `R2Device`。
3. `CommonBookController` 将 `R2Progression` 返回给客户端，外部阅读器能看到设备信息。

写入进度时，流程相反：

1. `KoboController` 或 `KoreaderSyncController` 接收到阅读器上报。
2. 控制器解析出设备 ID 和设备名，构造 `R2Device`。
3. 再把它放进 `R2Progression`，连同 `R2Locator` 一起交给 `bookLifecycle.markProgression(...)`。
4. 系统保存这次进度，后续读接口再把同样的设备信息返回出去。

## 小白阅读顺序
建议按这个顺序读：

1. `komga/src/main/kotlin/org/gotson/komga/domain/model/R2Device.kt`  
   先确认它只是一个两字段数据类。
2. `komga/src/main/kotlin/org/gotson/komga/domain/model/R2Progression.kt`  
   看它如何被组合进完整的 progression 对象。
3. `komga/src/main/kotlin/org/gotson/komga/domain/model/ReadProgress.kt`  
   看数据库里的持久化字段如何映射到协议对象。
4. `komga/src/main/kotlin/org/gotson/komga/interfaces/api/CommonBookController.kt`  
   看对外读取 progression 的返回路径。
5. `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt` 和 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kosync/KoreaderSyncController.kt`  
   看外部阅读器如何把设备信息写回系统。

## 常见误区
- 容易把 `R2Device` 当成“设备实体”，其实它更像协议 DTO，不负责设备管理。
- 容易忽略它和 `ReadProgress.deviceId/deviceName` 的对应关系；真正的持久化来源在 `ReadProgress`，`R2Device` 只是对外表达形式。
- 容易只盯着 `R2Device` 本身，忘了它必须和 `R2Locator`、`modified` 一起看，因为它只是 `R2Progression` 的一部分。
- 容易误以为它有复杂逻辑；实际上这个文件没有行为，理解重点应放在“谁构造它、谁消费它、它被序列化到哪里”。
