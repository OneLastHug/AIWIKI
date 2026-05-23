# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaSettingsProvider.kt

## 它负责什么

`KomgaSettingsProvider.kt` 定义了一个 Spring `@Service`：`KomgaSettingsProvider`。它的职责是把 Komga 的“服务器运行时设置”封装成一组 Kotlin 属性，供应用其他模块读取和修改。

这些设置不是普通的 `application.yml` 静态配置，而是保存在数据库表 `SERVER_SETTINGS` 中的动态设置。`KomgaSettingsProvider` 在启动时从数据库读取已有值；如果没有配置，则使用代码里的默认值。之后业务代码只需要访问类似 `komgaSettingsProvider.taskPoolSize`、`komgaSettingsProvider.koboProxy` 这样的属性，不需要直接关心数据库读写。

这个文件可以理解为“数据库持久化设置”和“应用运行时对象属性”之间的适配层。它既负责读取默认值，也负责在属性被赋新值时把新值写回数据库，还会在部分关键设置变化后发布 Spring 事件，让依赖模块即时响应。

## 关键组成

### `KomgaSettingsProvider`

主类声明如下：

```kotlin
@Service
class KomgaSettingsProvider(
  private val serverSettingsDao: ServerSettingsDao,
  private val eventPublisher: ApplicationEventPublisher,
)
```

它有两个依赖：

`ServerSettingsDao`：负责真正读写数据库中的 `SERVER_SETTINGS` 表。目标文件只调用它的 `getSettingByKey`、`saveSetting`、`deleteSetting` 方法，不直接写 SQL。

`ApplicationEventPublisher`：用于发布配置变更事件。目前目标文件只在 `taskPoolSize` 和 `kepubifyPath` 变化时发布事件。

### 布尔类清理设置

```kotlin
var deleteEmptyCollections: Boolean = ...
var deleteEmptyReadLists: Boolean = ...
```

这两个设置控制是否自动删除空集合、空阅读列表。它们从数据库读取布尔值，如果没有记录则默认 `false`。

setter 的逻辑很直接：调用 `serverSettingsDao.saveSetting(...)` 保存新值，然后更新内存字段 `field = value`。

### Remember-me 登录相关设置

```kotlin
var rememberMeKey: String = ...
fun renewRememberMeKey()
var rememberMeDuration: Duration = ...
```

`rememberMeKey` 是 Spring Security remember-me 功能使用的密钥。如果数据库里没有 `REMEMBER_ME_KEY`，代码会调用 `getRandomRememberMeKey()` 生成一个 32 位随机字母数字字符串，并立即通过 setter 保存到数据库。

这里有一个细节：

```kotlin
?: getRandomRememberMeKey().also { rememberMeKey = it }
```

初始化属性时，如果数据库没有 key，会生成一个新 key，并赋给 `rememberMeKey`。由于这是给同一个属性赋值，会触发 setter，把 key 持久化。这样应用第一次启动后不会每次重启都换 key。

`renewRememberMeKey()` 用于主动刷新 remember-me key，调用后旧的 remember-me token 通常会失效。根据调用方 `SettingsController` 可见，它可以通过 REST 设置接口触发。

`rememberMeDuration` 使用 Kotlin `Duration` 类型，对外表现为天数。数据库里保存的是整数天数，默认是 `365.days`。

### 缩略图尺寸

```kotlin
var thumbnailSize: ThumbnailSize = ...
```

该设置从数据库读取字符串，然后通过 `ThumbnailSize.valueOf(it)` 转成枚举。如果没有记录则使用 `ThumbnailSize.DEFAULT`。

保存时写入的是枚举名：

```kotlin
serverSettingsDao.saveSetting(Settings.THUMBNAIL_SIZE.name, value.name)
```

这意味着数据库里存储的是类似 `DEFAULT` 这样的字符串，而不是完整对象。

### 任务线程池大小

```kotlin
var taskPoolSize: Int = ...
```

`taskPoolSize` 控制后台任务处理线程池大小。默认值是 `1`。

它和前面简单设置不同，setter 除了保存数据库和更新字段，还会发布事件：

```kotlin
eventPublisher.publishEvent(SettingChangedEvent.TaskPoolSize)
```

调用方 `TaskProcessor` 监听 `SettingChangedEvent.TaskPoolSize`，收到事件后把 executor 的 `corePoolSize` 改成最新值。也就是说，这个设置支持运行时生效，不需要重启应用。

### Web 服务器相关设置

```kotlin
var serverPort: Int?
var serverContextPath: String?
```

这两个是可空设置。可空的语义是：数据库里存在值时覆盖某些服务器设置；值为 `null` 时删除数据库记录，回到其他来源的配置或默认行为。

setter 中的逻辑是：

```kotlin
if (value != null)
  serverSettingsDao.saveSetting(...)
else
  serverSettingsDao.deleteSetting(...)
```

从 `SettingsController` 的使用方式看，这两个设置会和 `server.port`、`server.servlet.context-path` 等配置源一起组成 `SettingMultiSource`，对前端展示“配置文件值、数据库值、最终生效值”。

### Kobo 相关设置

```kotlin
var koboProxy: Boolean = ...
var koboPort: Int?
var kepubifyPath: String?
```

`koboProxy` 控制 Kobo 代理功能是否启用，默认 `false`。调用方 `KoboProxy.isEnabled()` 直接返回 `komgaSettingsProvider.koboProxy`。

`koboPort` 是可空端口配置，和 `serverPort` 类似，设置为 `null` 时删除数据库记录。

`kepubifyPath` 是外部工具 `kepubify` 的路径。它在读取时有一个额外处理：

```kotlin
serverSettingsDao.getSettingByKey(..., String::class.java)?.ifBlank { null }
```

也就是说，如果数据库里保存了空白字符串，内存中会视为 `null`。setter 中，非空则保存，空则删除设置，并发布：

```kotlin
eventPublisher.publishEvent(SettingChangedEvent.KepubifyPath)
```

调用方 `KepubConverter` 监听该事件，重新验证并配置 `kepubify` 可执行文件路径。如果数据库路径无效，它还可能回退到 `komga.kobo.kepubify-path` 这个静态配置值。

### 私有枚举 `Settings`

文件底部有一个私有枚举：

```kotlin
private enum class Settings {
  DELETE_EMPTY_COLLECTIONS,
  DELETE_EMPTY_READLISTS,
  REMEMBER_ME_KEY,
  REMEMBER_ME_DURATION,
  THUMBNAIL_SIZE,
  TASK_POOL_SIZE,
  SERVER_PORT,
  SERVER_CONTEXT_PATH,
  KOBO_PROXY,
  KOBO_PORT,
  KEPUBIFY_PATH,
}
```

它集中定义数据库设置 key。代码使用 `Settings.X.name` 作为数据库中的 key 字符串。

这个枚举是 `private`，说明它只是 `KomgaSettingsProvider.kt` 内部实现细节，其他类不能直接依赖这些 key 名称。外部模块应通过 `KomgaSettingsProvider` 的属性访问设置，而不是拼字符串访问数据库。

## 上下游关系

上游主要是 `ServerSettingsDao` 和 Spring 容器。

`ServerSettingsDao` 位于 `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ServerSettingsDao.kt`，它封装了 `SERVER_SETTINGS` 表的读写。核心方法包括：

`getSettingByKey(key, clazz)`：从只读 DSLContext 查询 `VALUE`，并转换成指定类型。

`saveSetting(key, value)`：使用 insert + on duplicate key update 保存配置。也就是说，同一个 key 已存在时会更新，不存在时会插入。

`deleteSetting(key)`：删除某个 key。

`KomgaSettingsProvider` 依赖这个 DAO，但没有关心表结构之外的细节。

另一个上游是 Spring 的 `ApplicationEventPublisher`。它不是配置来源，而是事件发布能力。目标文件通过它通知其他模块“某个设置已经变了”。

下游调用方比较多，代表性关系如下：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt`：REST API 层。管理员通过 `GET api/v1/settings` 读取当前设置，通过 `PATCH api/v1/settings` 更新设置。它是外部用户修改 `KomgaSettingsProvider` 的主要入口。

`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt`：后台任务处理器。启动时用 `settingsProvider.taskPoolSize` 构建线程池，后续监听 `SettingChangedEvent.TaskPoolSize` 动态调整线程池大小。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KepubConverter.kt`：Kobo EPUB 到 KEPUB 转换器。启动时读取 `settingsProvider.kepubifyPath`，设置变化时监听 `SettingChangedEvent.KepubifyPath`，重新配置外部转换工具路径。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/security/SecurityConfiguration.kt`：安全配置。它读取 `rememberMeKey` 和 `rememberMeDuration`，用于 Spring Security remember-me 服务。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KoboProxy.kt`：Kobo 代理。它通过 `komgaSettingsProvider.koboProxy` 判断代理功能是否启用。

`komga/src/main/kotlin/org/gotson/komga/domain/service/LibraryContentLifecycle.kt`：领域生命周期逻辑。它读取 `deleteEmptyCollections`，决定扫描或维护库内容后是否删除空集合。

`BookLifecycle`、`BookAnalyzer`、`MosaicGenerator`、`OpdsController`、Web 相关配置也会读取其中部分设置。根据当前片段推断，`KomgaSettingsProvider` 在项目里是动态服务器设置的统一访问点。

它和 `KomgaProperties` 的关系也容易混淆。`KomgaProperties` 位于同目录的 `KomgaProperties.kt`，绑定的是 `komga.*` 这类配置文件属性，例如数据库路径、Lucene 目录、Kobo 静态配置等。`KomgaSettingsProvider` 绑定的是数据库里的运行时设置。两者都叫 configuration，但来源不同、生命周期不同。

## 运行/调用流程

应用启动时，Spring 创建 `KomgaSettingsProvider` bean。构造参数 `ServerSettingsDao` 和 `ApplicationEventPublisher` 由 Spring 注入。

创建对象过程中，每个属性会按声明顺序初始化。例如：

1. 读取 `DELETE_EMPTY_COLLECTIONS`，没有则使用 `false`。
2. 读取 `DELETE_EMPTY_READLISTS`，没有则使用 `false`。
3. 读取 `REMEMBER_ME_KEY`，没有则生成随机 key 并保存。
4. 读取 `REMEMBER_ME_DURATION`，没有则使用 `365.days`。
5. 读取 `THUMBNAIL_SIZE`，没有则使用 `ThumbnailSize.DEFAULT`。
6. 读取 `TASK_POOL_SIZE`，没有则使用 `1`。
7. 读取端口、上下文路径、Kobo、kepubify 等设置。

初始化完成后，其他 bean 可以注入并读取它。例如 `TaskProcessor` 在构造线程池时读取 `settingsProvider.taskPoolSize`，`SecurityConfiguration` 在配置 remember-me 时读取 `rememberMeKey`。

当管理员通过 `SettingsController` 更新配置时，流程大致是：

1. 前端或客户端发送 `PATCH api/v1/settings`。
2. `SettingsController.updateServerSettings()` 接收 `SettingsUpdateDto`。
3. 对于请求中出现的字段，调用对应属性 setter，例如 `komgaSettingsProvider.taskPoolSize = it`。
4. setter 负责保存数据库并更新内存字段。
5. 如果是 `taskPoolSize` 或 `kepubifyPath`，setter 还会发布对应的 `SettingChangedEvent`。
6. 监听该事件的组件立即调整自身状态。

例如修改 `taskPoolSize`：

1. API 层执行 `komgaSettingsProvider.taskPoolSize = 4`。
2. `KomgaSettingsProvider` 保存 `TASK_POOL_SIZE=4` 到数据库。
3. 内存字段更新为 `4`。
4. 发布 `SettingChangedEvent.TaskPoolSize`。
5. `TaskProcessor.taskPoolSizeChanged()` 被调用。
6. `executor.corePoolSize` 更新为最新的 `settingsProvider.taskPoolSize`。

再例如修改 `kepubifyPath`：

1. API 层设置 `komgaSettingsProvider.kepubifyPath`。
2. provider 保存或删除 `KEPUBIFY_PATH`。
3. 发布 `SettingChangedEvent.KepubifyPath`。
4. `KepubConverter.configureKepubifyOnSettingsChange()` 调用 `configureKepubify(...)`。
5. `KepubConverter` 检查新路径是否可执行，并设置 `isAvailable` 与 `kepubifyPath`。

对于 `serverPort`、`serverContextPath`、`koboPort` 这类可空设置，调用流程里还有一个“删除配置”的分支：如果传入 `null`，不是把字符串 `"null"` 保存到数据库，而是调用 `deleteSetting` 删除该 key。

## 小白阅读顺序

建议先读 `KomgaSettingsProvider.kt` 本身，不要急着跳到所有调用方。重点看每个 `var` 的初始化表达式和 setter，因为这个文件的主要逻辑都藏在属性声明里，而不是普通函数里。

第一步，看构造函数：

```kotlin
private val serverSettingsDao: ServerSettingsDao
private val eventPublisher: ApplicationEventPublisher
```

理解这个类只有两个能力：持久化设置、发布事件。

第二步，看一个最简单的属性，例如 `deleteEmptyCollections`。它展示了标准模式：启动读取数据库，缺省使用默认值；设置新值时保存数据库并更新字段。

第三步，看 `rememberMeKey`。它比普通属性多了“缺省时生成并保存”的逻辑。理解这个模式后，就能明白为什么 remember-me key 不应该每次启动都随机变化。

第四步，看 `serverPort` 或 `koboPort`。它们展示了可空设置的模式：`null` 表示删除数据库设置，而不是保存一个空值。

第五步，看 `taskPoolSize` 和 `kepubifyPath`。它们展示了事件机制：某些设置变化后，除了保存，还要通知运行中的组件重新配置。

第六步，再看同目录的 `SettingChangedEvent.kt`。这个文件很短，只定义了两个事件：`TaskPoolSize` 和 `KepubifyPath`。读完它可以回到 `KomgaSettingsProvider.kt`，确认哪些 setter 会发布事件。

第七步，看 `ServerSettingsDao.kt`。重点理解 `saveSetting` 是 upsert，`getSettingByKey` 会把字符串值转换成目标类型。这样就能理解为什么 provider 可以用 `Boolean::class.java`、`Int::class.java`、`String::class.java` 读取不同类型。

第八步，看调用方。优先看 `SettingsController.kt`，因为它展示了管理员如何通过 REST API 读取和修改这些设置。然后看 `TaskProcessor.kt` 和 `KepubConverter.kt`，它们展示了事件变化如何影响运行中组件。

## 常见误区

第一个误区：以为这些设置来自 `application.yml`。实际上，`KomgaSettingsProvider` 主要读取数据库里的 `SERVER_SETTINGS`。`KomgaProperties` 才是绑定 `komga.*` 配置文件属性的类。某些地方会把两种来源一起展示或做 fallback，例如 `kepubifyPath` 和服务器端口相关设置。

第二个误区：以为修改属性只是改内存。这里每个 setter 都会写数据库。比如执行 `komgaSettingsProvider.koboProxy = true`，会保存 `KOBO_PROXY=true` 到数据库，并更新当前对象字段。

第三个误区：以为所有设置变化都会发布事件。当前文件只有 `taskPoolSize` 和 `kepubifyPath` 的 setter 会发布事件。其他设置虽然会保存和更新内存字段，但没有通过 `ApplicationEventPublisher` 通知监听器。是否能即时影响运行中行为，要看具体调用方是每次读取 provider，还是只在启动时读取一次。

第四个误区：把 `null` 和空字符串混为一谈。`serverPort`、`serverContextPath`、`koboPort`、`kepubifyPath` 这类可空属性中，`null` 通常表示删除数据库配置。`kepubifyPath` 读取时还会把空白字符串转成 `null`，避免空字符串被当作有效路径。

第五个误区：忽略 Kotlin 属性初始化会执行逻辑。`rememberMeKey` 的默认生成逻辑就在属性初始化表达式里，而且 `also { rememberMeKey = it }` 会触发 setter 保存数据库。读这个文件时不能只看显式函数，也要仔细看属性右侧表达式和 setter。

第六个误区：以为 `Settings` 枚举是公共配置模型。它是 `private enum class Settings`，只在当前文件内部用于规范数据库 key 名称。外部代码应该依赖 `KomgaSettingsProvider` 的属性，而不是直接依赖这些枚举值。

第七个误区：认为 `rememberMeDuration` 在数据库里保存的是 Kotlin `Duration`。实际上数据库保存的是整数天数，读取时用 `.days` 转成 `Duration`，保存时用 `value.inWholeDays.toInt()` 写回。

第八个误区：认为 `thumbnailSize` 可以保存任意字符串。它读取时调用 `ThumbnailSize.valueOf(it)`，因此数据库中的字符串必须匹配 `ThumbnailSize` 枚举名。如果数据库里出现非法枚举名，根据当前片段推断，启动或读取初始化时可能抛出异常，依据是 `valueOf` 对未知名称不会返回默认值。
