# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq/main/ServerSettingsDao.kt

## 它负责什么

`ServerSettingsDao.kt` 是 Komga 后端里“服务器级设置”的数据库访问层，也就是一个很薄的 DAO。它只负责把配置项按 `key -> value` 的形式保存到数据库表 `SERVER_SETTINGS`，以及按 key 读取、更新、删除这些配置。

它不负责决定有哪些设置项、不负责默认值、不负责业务事件，也不负责校验端口、路径、缩略图大小等业务含义。这些逻辑主要在上层 `KomgaSettingsProvider`、REST Controller 或 DTO 层完成。

从代码看，它的定位非常明确：

- 使用 jOOQ 访问 `Tables.SERVER_SETTINGS`。
- 读操作走 `dslRO`，写操作走 `dslRW`。
- 所有值最终都以字符串形式存入表的 `VALUE` 字段。
- 读取时通过 `fetchOneInto(clazz)` 交给 jOOQ 做类型转换。
- `saveSetting` 使用 upsert 语义：key 不存在就插入，key 已存在就更新 `VALUE`。

相关表来自 jOOQ 生成对象 `org.gotson.komga.jooq.main.Tables.SERVER_SETTINGS`。仓库中还能看到迁移文件 `komga/src/flyway/resources/db/migration/sqlite/V20230922143307__server_settings.sql` 创建了 `SERVER_SETTINGS` 表，因此这个 DAO 是 Flyway 数据库结构、jOOQ 生成代码和 Spring Bean 之间的连接点。

## 关键组成

这个文件主要由一个 Spring 组件类组成：

```kotlin
@Component
class ServerSettingsDao(
  dslRW: DSLContext,
  @Qualifier("dslContextRO") dslRO: DSLContext,
) : SplitDslDaoBase(dslRW, dslRO)
```

`@Component` 说明它会被 Spring 扫描为 Bean，供其他服务注入使用。构造函数接收两个 `DSLContext`：

- `dslRW`：读写数据库上下文，主要用于 insert、update、delete。
- `dslRO`：只读数据库上下文，通过 `@Qualifier("dslContextRO")` 指定注入只读版本。

它继承自 `SplitDslDaoBase`。这个父类有一个关键行为：当当前线程处于非只读事务中时，`dslRO` 实际会返回 `dslRW`；否则返回真正的只读 `_dslRO`。这可以避免在写事务中读到旧数据，也能在普通读场景下使用只读连接。

类内部保存了表引用：

```kotlin
private val s = Tables.SERVER_SETTINGS
```

这里的 `s` 是 jOOQ 生成表对象的短别名，后续方法用 `s.KEY` 和 `s.VALUE` 引用列。

核心方法有五类。

第一类是读取：

```kotlin
fun <T> getSettingByKey(
  key: String,
  clazz: Class<T>,
): T?
```

它按 `KEY = key` 查询 `VALUE`，并把结果转换成调用方指定的类型。返回值是 `T?`，表示没有该配置时返回 `null`。例如上层可以读取：

- `String::class.java`
- `Boolean::class.java`
- `Int::class.java`

测试文件 `ServerSettingsDaoTest.kt` 覆盖了这三种类型，说明这是它当前明确支持和预期使用的类型范围。

第二类是保存字符串：

```kotlin
fun saveSetting(
  key: String,
  value: String,
)
```

它执行：

```kotlin
insertInto(s)
  .values(key, value)
  .onDuplicateKeyUpdate()
  .set(s.VALUE, value)
  .execute()
```

这表示如果数据库里还没有这个 key，就插入新记录；如果已经有这个 key，就更新 `VALUE`。根据当前片段推断，`SERVER_SETTINGS.KEY` 应该是主键或唯一键，否则 `onDuplicateKeyUpdate()` 没有触发依据。这个推断依据是：DAO 使用了 duplicate key 语义，测试也验证了“同一个 key 保存两次时第二次会覆盖第一次”。

第三类是保存布尔值和整数：

```kotlin
fun saveSetting(key: String, value: Boolean)
fun saveSetting(key: String, value: Int)
```

这两个重载只是把值转成字符串后复用 `saveSetting(key, value: String)`。因此数据库层面并没有真正的 Boolean 或 Int 字段，类型信息来自调用方读取时传入的 `clazz`。

第四类是删除单个设置：

```kotlin
fun deleteSetting(key: String)
```

它按 key 删除一行。上层在某些可空配置被设置为 `null` 时会调用它，例如 `serverPort`、`serverContextPath`、`koboPort`、`kepubifyPath`。

第五类是删除全部设置：

```kotlin
fun deleteAll()
```

它直接清空 `SERVER_SETTINGS` 表。这个方法在测试里用于 `@AfterEach` 清理测试数据，不一定是业务运行时常用方法。

## 上下游关系

这个 DAO 的下游是数据库和 jOOQ 生成代码。

下游包括：

- `SERVER_SETTINGS` 数据表。
- jOOQ 生成对象 `org.gotson.komga.jooq.main.Tables.SERVER_SETTINGS`。
- `DSLContext` 提供的 fluent SQL API。
- `SplitDslDaoBase` 提供的读写上下文选择策略。

它的直接上游主要是 `KomgaSettingsProvider`：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaSettingsProvider.kt`

这个服务把底层 key-value DAO 包装成更有业务含义的 Kotlin 属性，例如：

- `deleteEmptyCollections: Boolean`
- `deleteEmptyReadLists: Boolean`
- `rememberMeKey: String`
- `rememberMeDuration: Duration`
- `thumbnailSize: ThumbnailSize`
- `taskPoolSize: Int`
- `serverPort: Int?`
- `serverContextPath: String?`
- `koboProxy: Boolean`
- `koboPort: Int?`
- `kepubifyPath: String?`

`KomgaSettingsProvider` 内部定义了私有枚举 `Settings`，枚举名会作为数据库 key：

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

因此 `ServerSettingsDao` 并不知道这些 key 的含义，它只接收字符串 key。真正的“哪些 key 合法”“默认值是什么”“设置变更后要不要发布事件”，都在 `KomgaSettingsProvider` 中完成。

更上层还有 REST API 和前端页面。搜索结果显示：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt` 暴露服务器设置接口。
- `komga-webui/src/views/ServerSettings.vue` 是 Web UI 的服务器设置页面。
- `OpenApiConfiguration` 中有 `SERVER_SETTINGS` 标签，描述为 “Store and retrieve server settings”。

根据当前片段推断，典型链路是：

`ServerSettings.vue` 用户操作  
-> REST API `SettingsController`  
-> `KomgaSettingsProvider` 读取或修改业务属性  
-> `ServerSettingsDao` 持久化 key-value  
-> `SERVER_SETTINGS` 表保存实际值

测试上游是：

`komga/src/test/kotlin/org/gotson/komga/infrastructure/jooq/main/ServerSettingsDaoTest.kt`

测试验证了：

- 保存 String 后能读回。
- 保存 Int 后能读回。
- 保存 Boolean 后能读回。
- 重复保存同一个 key 会覆盖旧值。
- 删除已有 key 后读取为 `null`。
- 每个测试后通过 `deleteAll()` 清理表。

## 运行/调用流程

读取流程可以按一条配置项来理解。

例如上层要读取任务线程池大小 `taskPoolSize`：

1. `KomgaSettingsProvider` 初始化属性时调用：

   ```kotlin
   serverSettingsDao.getSettingByKey(Settings.TASK_POOL_SIZE.name, Int::class.java)
   ```

2. `ServerSettingsDao` 使用 `dslRO` 查询：

   ```kotlin
   select(s.VALUE)
     .from(s)
     .where(s.KEY.eq(key))
   ```

3. jOOQ 从 `SERVER_SETTINGS.VALUE` 取出一列。
4. `fetchOneInto(Int::class.java)` 把数据库里的字符串值转换为 `Int`。
5. 如果数据库没有该 key，返回 `null`。
6. `KomgaSettingsProvider` 使用默认值，例如 `?: 1`。

写入流程也很直接。

例如上层修改 `taskPoolSize`：

1. `KomgaSettingsProvider.taskPoolSize` 的 setter 被调用。
2. setter 调用：

   ```kotlin
   serverSettingsDao.saveSetting(Settings.TASK_POOL_SIZE.name, value)
   ```

3. `Int` 重载把整数转成字符串。
4. 字符串重载执行 insert/upsert。
5. 如果 key 不存在，插入 `(KEY, VALUE)`。
6. 如果 key 已存在，更新 `VALUE`。
7. `KomgaSettingsProvider` 更新内存字段 `field = value`。
8. 对 `taskPoolSize` 这类需要通知其他组件的配置，还会发布事件：

   ```kotlin
   eventPublisher.publishEvent(SettingChangedEvent.TaskPoolSize)
   ```

删除流程主要用于可空配置。

例如 `serverPort` 被设为 `null`：

1. `KomgaSettingsProvider.serverPort` 的 setter 判断 `value == null`。
2. 调用：

   ```kotlin
   serverSettingsDao.deleteSetting(Settings.SERVER_PORT.name)
   ```

3. DAO 执行：

   ```kotlin
   deleteFrom(s).where(s.KEY.eq(key)).execute()
   ```

4. 表中对应 key 被删除。
5. 下次读取时 `getSettingByKey` 返回 `null`。
6. 上层可以把 `null` 解释为“没有数据库覆盖值，使用其他配置来源或默认行为”。

这里还要注意 `SplitDslDaoBase` 的读写切换。表面上 `getSettingByKey` 总是用 `dslRO`，但如果它运行在一个正在进行的非只读事务里，父类会让 `dslRO` 返回 `dslRW`。这避免了“刚写入同一事务内再读取，却从只读连接读不到”的问题。

## 小白阅读顺序

建议按下面顺序读，不要一开始就陷入 jOOQ 细节。

第一步，先读 `ServerSettingsDao.kt` 的类声明。

重点看它是 `@Component`，并且继承 `SplitDslDaoBase`。这说明它不是普通工具类，而是 Spring 管理的数据库访问组件。

第二步，看这一行：

```kotlin
private val s = Tables.SERVER_SETTINGS
```

这说明整个文件操作的核心对象就是 `SERVER_SETTINGS` 表。后面看到 `s.KEY`、`s.VALUE` 时，就知道它们是表字段。

第三步，看 `getSettingByKey`。

这是唯一的读取方法。理解它时只要抓住一句话：按 key 查 value，然后把 value 转成调用方要求的类型。这里的泛型 `<T>` 不代表数据库里真的有多种类型，而是读取时的转换目标。

第四步，看三个 `saveSetting`。

先看 `String` 版本，因为它是真正执行 SQL 的版本。再看 `Boolean` 和 `Int` 版本，会发现它们只是 `toString()` 后委托给 `String` 版本。

第五步，看 `deleteSetting` 和 `deleteAll`。

`deleteSetting` 是业务可用的单项删除。`deleteAll` 在测试里用于清理数据，阅读时不要误以为业务功能经常会清空服务器设置。

第六步，跳到 `KomgaSettingsProvider.kt`。

这个文件能解释 DAO 为什么要支持 `String`、`Boolean`、`Int`，也能看到默认值在哪里处理。例如：

- `deleteEmptyCollections` 默认 `false`
- `rememberMeDuration` 默认 `365.days`
- `thumbnailSize` 默认 `ThumbnailSize.DEFAULT`
- `taskPoolSize` 默认 `1`

第七步，看 `ServerSettingsDaoTest.kt`。

测试是理解这个 DAO 行为最直接的材料。它确认了保存、读取、覆盖、删除的预期行为，也说明 `fetchOneInto` 至少在当前测试环境中能把字符串值转换成 `Int` 和 `Boolean`。

## 常见误区

误区一：以为 `ServerSettingsDao` 定义了服务器设置的业务规则。

实际上它不关心配置项含义。它只保存 key-value。哪些 key 合法、默认值是什么、哪些设置修改后要发事件，主要在 `KomgaSettingsProvider` 或更上层处理。

误区二：以为数据库里按真实类型保存 Boolean 和 Int。

不是。`saveSetting(Boolean)` 和 `saveSetting(Int)` 都调用 `toString()`，最终写入的是字符串。读取时再通过 `fetchOneInto(clazz)` 转成目标类型。因此如果数据库里存了无法转换的字符串，比如某个需要 `Int` 的 key 存成 `"abc"`，读取阶段就可能出问题。这个文件本身没有做格式校验。

误区三：以为 `saveSetting` 每次都是新增。

不是。它使用 `onDuplicateKeyUpdate()`，同一个 key 再保存会覆盖旧值。测试 `given existing setting when saving again then it is overridden` 专门验证了这一点。

误区四：以为 `getSettingByKey` 没查到会抛异常。

从签名 `T?` 和测试看，没查到时返回 `null`。上层依赖这个行为来提供默认值，或者表达“该配置没有数据库覆盖”。

误区五：忽略读写 DSLContext 的区别。

这个 DAO 同时接收 `dslRW` 和 `dslRO`。读方法写的是 `dslRO`，写方法写的是 `dslRW`。但由于继承 `SplitDslDaoBase`，非只读事务内的 `dslRO` 会自动落到 `dslRW`。所以不能简单理解成“读永远走只读连接”。

误区六：把 `deleteAll()` 当成普通业务 API。

`deleteAll()` 会清空整张 `SERVER_SETTINGS` 表。当前看到的明确用途是在测试的 `@AfterEach` 中清理数据。业务代码如果调用它，影响范围会非常大。

误区七：以为这个 DAO 和客户端设置是一套东西。

不是。这个文件处理的是服务器设置 `SERVER_SETTINGS`。搜索结果里还有 `ClientSettingsController`、`ClientSettingsDtoDao` 等客户端/用户设置相关代码，它们是另一条设置链路。不要把服务器级设置和用户级/客户端级设置混在一起。
