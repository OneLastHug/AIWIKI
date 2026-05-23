# 文件：komga/src/main/kotlin/org/gotson/komga/domain/model/R2Progression.kt

## 它负责什么

这个文件定义了 Komga 里用于表示“阅读进度”的 Readium/OPDS 风格数据结构 `R2Progression`，并提供一个把内部领域模型 `ReadProgress` 转成该结构的扩展函数 `toR2Progression()`。

它的职责非常单一，就是做“内部读进度记录”到“对外进度表示”的映射。换句话说，这里不负责计算进度，也不负责持久化，只负责把已有的 `ReadProgress` 组织成 API 和阅读器能直接消费的格式。

根据当前片段推断，这个类型主要服务于进度同步和阅读器交互场景，尤其是 OPDS 2 / Readium 相关接口。

## 关键组成

这个文件只有两部分。

第一部分是数据类 `R2Progression`：

- `modified: ZonedDateTime`  
  表示这条进度最后一次修改的时间，使用带时区的时间类型，方便跨设备、跨时区传输。
- `device: R2Device`  
  表示产生这条进度的设备信息，包含设备 id 和名称。
- `locator: R2Locator`  
  表示当前阅读位置。它不是简单页码，而是 Readium Locator 语义下的一种位置描述，里面可能包含 `href`、`locations.progression`、`locations.position` 等信息。

第二部分是扩展函数：

- `fun ReadProgress.toR2Progression()`

它把内部的 `ReadProgress` 转成 `R2Progression`，映射规则很直接：

- `readDate` 通过 `toZonedDateTime()` 转成 `modified`
- `deviceId`、`deviceName` 组装成 `R2Device`
- `locator` 如果为空，就退化成 `R2Locator("", "")`

这里最值得注意的是这个默认值。也就是说，`R2Progression` 在输出时允许没有真实定位信息，但仍然保留一个空的 `R2Locator`，避免调用方处理空值分支。

## 上下游关系

上游输入主要来自 `ReadProgress`。

`ReadProgress` 定义在同目录下的 `ReadProgress.kt`，它是 Komga 内部保存阅读进度的领域对象，包含：

- `bookId`
- `userId`
- `page`
- `completed`
- `readDate`
- `deviceId`
- `deviceName`
- `locator`

也就是说，`R2Progression.kt` 不是孤立的，它依赖内部进度记录和时间转换工具 `org.gotson.komga.language.toZonedDateTime`。

下游主要有三个方向：

- `CommonBookController`  
  在 `GET /api/v1/books/{bookId}/progression` 和 `GET /opds/v2/books/{bookId}/progression` 中，把仓库里查到的 `ReadProgress` 通过 `toR2Progression()` 返回给前端或阅读器。
- `BookLifecycle`  
  在 `markProgression(book, user, newProgression)` 里接收外部传入的 `R2Progression`，再把它落回内部 `ReadProgress`。
- 其他对接阅读器的控制器  
  例如 `KoboController`、`KoreaderSyncController`，会直接构造或使用 `R2Progression` 作为同步协议的一部分。

所以这个文件位于一个很典型的双向转换节点上：一边把内部 `ReadProgress` 暴露出去，另一边又让外部 `R2Progression` 进入系统。

## 运行/调用流程

最常见的读取流程是这样：

1. 客户端请求书籍进度接口。
2. `CommonBookController.getBookProgression()` 先检查书籍是否存在，再检查内容权限。
3. 控制器从 `readProgressRepository` 里取出当前用户对应的 `ReadProgress`。
4. 调用 `it.toR2Progression()`。
5. `toR2Progression()` 把内部对象映射成 `R2Progression`：
   - 时间变成 `modified`
   - 设备信息变成 `R2Device`
   - 位置变成 `R2Locator`
6. 控制器返回这个对象作为 HTTP 响应体。

反向流程则在更新进度时发生：

1. 客户端提交 `R2Progression`。
2. `CommonBookController.updateBookProgression()` 收到请求体。
3. 控制器把对象交给 `BookLifecycle.markProgression()`。
4. `BookLifecycle` 根据 `R2Progression.locator`、`modified`、`device` 等字段校验并构造内部 `ReadProgress`。
5. 新进度被保存到仓库。

这个文件本身只参与第 4 步的“导出转换”，但它定义的数据结构也是第 2 步请求体和第 5 步内部建模的共同语言。

## 小白阅读顺序

如果你第一次读这块代码，建议按这个顺序看：

1. 先看 `ReadProgress.kt`  
   先理解 Komga 内部怎么保存阅读进度，这样才知道 `R2Progression` 是从哪里来的。
2. 再看 `R2Locator.kt` 和 `R2Device.kt`  
   这两个是 `R2Progression` 的组成部件，尤其是 `R2Locator.locations.progression`、`position` 这些字段很关键。
3. 然后看 `R2Progression.kt` 本身  
   重点看 `toR2Progression()` 的字段映射和默认值。
4. 接着看 `CommonBookController` 里进度查询接口  
   这里能看到它怎么从仓库数据变成 HTTP 响应。
5. 最后看 `BookLifecycle.markProgression()`  
   这里能反向理解 `R2Progression` 如何被消费并转回内部模型。

按这个顺序读，比较容易建立“内部记录”和“对外协议”之间的对应关系。

## 常见误区

第一，容易把 `R2Progression` 当成内部持久化模型。  
实际上不是。真正存储的是 `ReadProgress`，`R2Progression` 更像对外接口数据结构。

第二，容易误以为 `modified` 就等于数据库的 `createdDate` 或 `lastModifiedDate`。  
这里不是。`modified` 来自 `ReadProgress.readDate`，是阅读进度发生变化的业务时间，而不是审计字段。

第三，容易忽略 `locator` 的默认值。  
`toR2Progression()` 在 `ReadProgress.locator == null` 时会塞一个 `R2Locator("", "")`，这意味着调用方不能简单假设 locator 一定含有真实位置。

第四，容易把 `R2Locator` 理解成“页码对象”。  
从 `R2Locator.kt` 的定义看，它支持 `href`、`progression`、`position`、`totalProgression` 等多种定位方式，页码只是其中一种可能的表达。

第五，容易只看这个文件而忽略它的双向性。  
它不仅用于“返回进度”，也参与“接收进度”。如果只看 `toR2Progression()`，会漏掉它在 API 协议层的核心地位。
