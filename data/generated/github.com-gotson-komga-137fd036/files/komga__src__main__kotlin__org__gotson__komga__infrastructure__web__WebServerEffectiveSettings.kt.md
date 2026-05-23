# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebServerEffectiveSettings.kt

## 它负责什么

`WebServerEffectiveSettings.kt` 定义了一个 Spring Bean：`WebServerEffectiveSettings`。它的职责很集中：记录 Web 服务器在运行时真正生效的两个值：

1. `effectiveServerPort`：应用启动后嵌入式 Web Server 实际监听的端口。
2. `effectiveServletContextPath`：Servlet 容器实际使用的 context path。

这里的“实际生效”很重要。Komga 的端口、context path 可能来自多个来源，例如：

- Spring Boot 配置项，如 `server.port`、`server.servlet.context-path`
- Komga 自己的持久化设置，如 `KomgaSettingsProvider.serverPort`、`KomgaSettingsProvider.serverContextPath`
- Spring Boot 启动时最终分配出来的运行时值，例如 `server.port=0` 时由系统随机分配端口

`WebServerEffectiveSettings` 不负责决定配置优先级，也不负责修改服务器配置。它只是在 Spring 容器中保存“运行后的结果”，供其他组件读取。

## 关键组成

文件内容很短，核心代码如下：

```kotlin
@Component
class WebServerEffectiveSettings(
  servletContext: ServletContext,
) {
  var effectiveServerPort: Int? = null
  val effectiveServletContextPath: String = servletContext.contextPath

  @EventListener
  fun onApplicationEvent(event: ServletWebServerInitializedEvent) {
    effectiveServerPort = event.webServer.port
  }
}
```

### `@Component`

`@Component` 表示这个类会被 Spring 扫描并注册为 Bean。

因此其他类可以通过构造函数注入：

```kotlin
private val serverSettings: WebServerEffectiveSettings
```

在当前仓库片段中，已看到它被这些位置使用：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt`
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/KoboMissingPortFilterConfiguration.kt`
- `komga/src/test/kotlin/org/gotson/komga/interfaces/api/kobo/KoboControllerTest.kt`

### 构造参数 `ServletContext`

```kotlin
servletContext: ServletContext
```

这是 Jakarta Servlet API 的上下文对象，由 Spring Web 环境提供。

本文件只读取了：

```kotlin
servletContext.contextPath
```

并保存为：

```kotlin
val effectiveServletContextPath: String = servletContext.contextPath
```

这意味着 `effectiveServletContextPath` 在 Bean 创建时就确定了。它代表当前 Servlet 容器实际使用的 context path。

如果应用部署在根路径，它通常是空字符串 `""`；如果配置了类似 `/komga` 的 context path，它可能是 `/komga`。

### `effectiveServerPort`

```kotlin
var effectiveServerPort: Int? = null
```

这个属性是可变的，并且初始值为 `null`。

原因是 Web Server 的实际端口并不是在 Bean 构造时就一定可知。Spring Boot 的内嵌 Web Server 初始化完成后，才会发布 `ServletWebServerInitializedEvent`，此时才能从事件对象中拿到真实端口。

特别是当配置中使用：

```properties
server.port=0
```

时，端口由操作系统动态分配。配置值是 `0`，但实际监听端口会是一个具体数字。`effectiveServerPort` 保存的就是后者。

### `@EventListener`

```kotlin
@EventListener
fun onApplicationEvent(event: ServletWebServerInitializedEvent) {
  effectiveServerPort = event.webServer.port
}
```

`@EventListener` 告诉 Spring：当容器中发布 `ServletWebServerInitializedEvent` 事件时，调用这个方法。

`ServletWebServerInitializedEvent` 来自：

```kotlin
org.springframework.boot.web.servlet.context.ServletWebServerInitializedEvent
```

它表示 Servlet Web Server 已经完成初始化。事件里可以拿到：

```kotlin
event.webServer.port
```

这就是服务器实际监听的端口。

## 上下游关系

### 上游：Spring Web / Servlet 容器

`WebServerEffectiveSettings` 的数据来源有两个：

1. `ServletContext.contextPath`
2. `ServletWebServerInitializedEvent.webServer.port`

对应关系如下：

| 属性 | 来源 | 获取时机 |
| --- | --- | --- |
| `effectiveServletContextPath` | `ServletContext.contextPath` | Bean 构造时 |
| `effectiveServerPort` | `ServletWebServerInitializedEvent.webServer.port` | Web Server 初始化完成后 |

因此它是一个典型的“运行时环境信息缓存 Bean”。

### 下游一：`SettingsController`

在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt` 中，`WebServerEffectiveSettings` 被注入到设置接口控制器：

```kotlin
private val serverSettings: WebServerEffectiveSettings
```

`getServerSettings()` 中会把服务器端口和 context path 组织成 `SettingMultiSource` 返回：

```kotlin
SettingMultiSource(configServerPort, komgaSettingsProvider.serverPort, serverSettings.effectiveServerPort)
SettingMultiSource(configServerContextPath, komgaSettingsProvider.serverContextPath, serverSettings.effectiveServletContextPath)
```

这说明 Komga 的设置接口不只展示“配置里写了什么”，还会展示“当前实际生效的值”。

以端口为例，它可能同时关心三种来源：

- `configServerPort`：Spring 配置里的 `server.port`
- `komgaSettingsProvider.serverPort`：Komga 持久化设置里的端口
- `serverSettings.effectiveServerPort`：当前进程真正监听的端口

所以 `WebServerEffectiveSettings` 在这里承担的是“effective value 提供者”的角色。

### 下游二：`KoboMissingPortFilterConfiguration`

在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/KoboMissingPortFilterConfiguration.kt` 中，它被用于 Kobo 相关请求的端口修正逻辑：

```kotlin
KoboMissingPortFilter { komgaSettingsProvider.koboPort ?: serverSettings.effectiveServerPort }
```

这里的逻辑是：

1. 如果配置了 `koboPort`，优先使用 `koboPort`
2. 否则使用当前 Web Server 的实际端口 `effectiveServerPort`

这个值会传给 `KoboMissingPortFilter`。

### 下游三：`KoboMissingPortFilter`

`KoboMissingPortFilter` 是一个 `OncePerRequestFilter`。它会包装请求对象，并覆盖：

```kotlin
override fun getServerPort() = port() ?: request.serverPort
```

也就是说，当 Kobo 请求缺少端口信息时，过滤器可以用 `WebServerEffectiveSettings.effectiveServerPort` 补上当前服务真实端口。

这对于 Kobo 相关接口比较关键，因为一些客户端或代理环境可能不会在请求中正确携带端口。Komga 通过这个过滤器尽量让服务端看到正确的 `serverPort`。

### 测试关系

搜索结果显示 `WebServerEffectiveSettings` 也出现在：

```text
komga/src/test/kotlin/org/gotson/komga/interfaces/api/kobo/KoboControllerTest.kt
```

根据当前片段推断，这个测试应当与 Kobo 接口端口处理有关，因为生产代码里 `WebServerEffectiveSettings` 参与了 `KoboMissingPortFilter` 的端口补全逻辑。具体断言内容未展开阅读，因此不能进一步确认测试覆盖的细节。

## 运行/调用流程

### 应用启动阶段

1. Spring 启动并扫描 `org.gotson.komga.infrastructure.web` 包。
2. 发现 `@Component` 标注的 `WebServerEffectiveSettings`。
3. Spring 创建该 Bean，并注入当前 `ServletContext`。
4. 构造期间读取：

```kotlin
servletContext.contextPath
```

5. 将结果保存到：

```kotlin
effectiveServletContextPath
```

此时：

```kotlin
effectiveServerPort == null
```

因为 Web Server 实际端口还没有通过事件写入。

### Web Server 初始化完成

1. Spring Boot 的 Servlet Web Server 初始化完成。
2. Spring 发布 `ServletWebServerInitializedEvent`。
3. `WebServerEffectiveSettings.onApplicationEvent()` 被触发。
4. 方法读取：

```kotlin
event.webServer.port
```

5. 写入：

```kotlin
effectiveServerPort
```

从这一刻开始，其他组件读取 `serverSettings.effectiveServerPort` 就能拿到真实端口。

### 管理设置接口读取

当管理员调用 `GET /api/v1/settings` 时：

1. 请求进入 `SettingsController.getServerSettings()`。
2. 控制器读取 Spring 配置值：

```kotlin
configServerPort
configServerContextPath
```

3. 读取 Komga 持久化设置：

```kotlin
komgaSettingsProvider.serverPort
komgaSettingsProvider.serverContextPath
```

4. 读取运行时生效值：

```kotlin
serverSettings.effectiveServerPort
serverSettings.effectiveServletContextPath
```

5. 返回 `SettingsDto`，其中端口和 context path 使用 `SettingMultiSource` 表示多来源信息。

### Kobo 请求端口补全

当请求匹配 `/kobo/*` 时：

1. 请求进入 `KoboMissingPortFilter`。
2. 如果请求已经带有 Forwarded 相关头，例如 `Forwarded`、`X-Forwarded-Host`、`X-Forwarded-Port` 等，则跳过该过滤器。
3. 如果没有这些头，过滤器包装请求。
4. 包装后的请求覆盖 `getServerPort()`。
5. 端口来源是：

```kotlin
komgaSettingsProvider.koboPort ?: serverSettings.effectiveServerPort
```

6. 如果两者都没有值，则退回原始请求的 `request.serverPort`。

这里 `WebServerEffectiveSettings` 提供的是 fallback 端口来源。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先读 `WebServerEffectiveSettings.kt`

   重点看三个点：

   ```kotlin
   @Component
   val effectiveServletContextPath
   @EventListener fun onApplicationEvent(...)
   ```

   先理解它不是 Controller，也不是 Filter，而是一个保存运行时 Web Server 信息的 Spring Bean。

2. 再读 `SettingsController.kt`

   重点看构造函数里的三个端口/context path 来源：

   ```kotlin
   configServerPort
   komgaSettingsProvider.serverPort
   serverSettings.effectiveServerPort
   ```

   这里能看出为什么需要 `effective` 概念：配置值和最终运行值不一定相同。

3. 再读 `KoboMissingPortFilterConfiguration.kt`

   重点看：

   ```kotlin
   KoboMissingPortFilter { komgaSettingsProvider.koboPort ?: serverSettings.effectiveServerPort }
   ```

   它说明 `effectiveServerPort` 不只是展示给管理员看，还参与实际请求处理。

4. 最后读 `KoboMissingPortFilter.kt`

   重点看内部 wrapper：

   ```kotlin
   override fun getServerPort() = port() ?: request.serverPort
   ```

   这里可以理解端口补全是怎么影响后续业务代码读取请求端口的。

## 常见误区

### 误区一：以为 `effectiveServerPort` 一定马上有值

不是。

它初始是：

```kotlin
var effectiveServerPort: Int? = null
```

只有收到 `ServletWebServerInitializedEvent` 后才会赋值。

如果某个组件在 Web Server 初始化事件之前读取它，理论上可能读到 `null`。当前看到的主要使用场景是设置接口和请求过滤器，通常发生在应用已经启动后，所以一般能拿到值。但类型设计成 `Int?` 正是在表达“它可能暂时没有值”。

### 误区二：以为 `server.port` 就是实际端口

不一定。

如果配置：

```properties
server.port=8080
```

多数情况下实际端口也是 `8080`。

但如果配置：

```properties
server.port=0
```

Spring Boot 会让系统分配一个可用端口。此时配置值是 `0`，实际端口是运行后才知道的具体数字。

`WebServerEffectiveSettings.effectiveServerPort` 解决的就是这个差异。

### 误区三：以为 context path 和端口获取方式一样

不一样。

端口通过事件获取：

```kotlin
ServletWebServerInitializedEvent
```

context path 直接从 `ServletContext` 获取：

```kotlin
servletContext.contextPath
```

所以 `effectiveServletContextPath` 是 `val`，创建后不再变化；`effectiveServerPort` 是 `var`，启动事件到来后更新。

### 误区四：以为这个类负责应用配置

不是。

它不读取配置文件，不写配置文件，也不负责配置优先级。

配置读取和持久化主要在其他组件中，例如 `SettingsController.kt` 注入的：

```kotlin
KomgaSettingsProvider
```

`WebServerEffectiveSettings` 只关心运行时实际结果。

### 误区五：忽略反向代理场景

`KoboMissingPortFilter` 中有一段逻辑：如果请求带有 Forwarded 相关头，就不应用端口补全。

这些头包括：

```text
Forwarded
X-Forwarded-Host
X-Forwarded-Port
X-Forwarded-Proto
X-Forwarded-Prefix
X-Forwarded-Ssl
X-Forwarded-For
```

这说明 Komga 区分了两类场景：

1. 没有代理头：可以用 `koboPort` 或 `effectiveServerPort` 补端口。
2. 有代理头：交给后续的 forwarded header 处理逻辑。

`KoboMissingPortFilterConfiguration.kt` 还调整了 `ForwardedHeaderFilter` 的顺序，让 `KoboMissingPortFilter` 先执行，因为后者的判断依赖 forwarded headers，而 `ForwardedHeaderFilter` 可能会消费或移除这些头。

### 误区六：以为 `effectiveServletContextPath` 一定是 `/`

Servlet context path 的根路径通常是空字符串 `""`，不是 `/`。

所以在消费这个字段时，不能简单假设它一定以 `/` 表示根路径。当前 `SettingsController` 只是把它作为值返回，没有拼接 URL；如果未来代码拿它拼路径，需要注意空字符串和带前缀路径的差异。
