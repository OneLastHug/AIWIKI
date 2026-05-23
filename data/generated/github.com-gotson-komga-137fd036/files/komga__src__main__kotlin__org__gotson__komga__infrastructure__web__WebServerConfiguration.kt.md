# 文件：komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebServerConfiguration.kt

## 它负责什么

`WebServerConfiguration.kt` 负责在 Spring Boot 内嵌 Web 服务器启动时，根据 Komga 自己保存在数据库里的服务器设置，动态调整两个 Web 容器级参数：

- `serverPort`：Komga 监听的 HTTP 端口。
- `serverContextPath`：Komga 挂载的 Servlet context path，例如 `/komga`。

它不是普通的 MVC 路由配置，也不是 REST API 控制器，而是一个 Spring Boot Web 服务器工厂定制器。它实现了：

```kotlin
WebServerFactoryCustomizer<ConfigurableServletWebServerFactory>
```

这意味着 Spring Boot 创建内嵌 Servlet Web 服务器工厂时，会回调它的 `customize(factory)` 方法，让应用有机会在服务器真正启动前修改端口、context path 等底层属性。

这个文件的主要价值是：让 Komga 的端口和 context path 可以来自应用自己的数据库设置，而不只依赖 `application.yml`、环境变量或启动参数。

## 关键组成

文件内容很短，但每个组成部分都有明确职责。

`package org.gotson.komga.infrastructure.web`

说明它属于基础设施层的 Web 配置区域。同目录还有 `WebMvcConfiguration.kt`、`WebServerEffectiveSettings.kt`、若干 Filter 配置类等，都是偏 Web 基础设施的代码。

导入部分：

```kotlin
import io.github.oshai.kotlinlogging.KotlinLogging
import org.gotson.komga.infrastructure.configuration.KomgaSettingsProvider
import org.springframework.boot.web.server.WebServerFactoryCustomizer
import org.springframework.boot.web.servlet.server.ConfigurableServletWebServerFactory
import org.springframework.stereotype.Component
```

几个关键依赖分别是：

- `KotlinLogging`：用于记录无效配置的 warning。
- `KomgaSettingsProvider`：读取 Komga 保存的服务器设置。
- `WebServerFactoryCustomizer`：Spring Boot 提供的扩展点。
- `ConfigurableServletWebServerFactory`：可配置的 Servlet Web 服务器工厂，常见底层实现可能是 Tomcat、Jetty、Undertow 等。
- `@Component`：让 Spring 自动扫描并注册这个类。

日志对象：

```kotlin
private val logger = KotlinLogging.logger {}
```

这是文件级私有 logger，只在本文件内使用。

核心类：

```kotlin
@Component
class WebServerConfiguration(
  private val settingsProvider: KomgaSettingsProvider,
) : WebServerFactoryCustomizer<ConfigurableServletWebServerFactory>
```

这里有两个重点：

1. `@Component` 让它成为 Spring Bean。
2. 构造函数注入 `KomgaSettingsProvider`，表示这个类不直接访问数据库，而是通过设置提供者读取当前配置。

核心方法：

```kotlin
override fun customize(factory: ConfigurableServletWebServerFactory) {
  settingsProvider.serverPort?.let {
    if (it > 1)
      factory.setPort(it)
    else
      logger.warn { "Ignoring invalid server port: $it" }
  }
  settingsProvider.serverContextPath?.let {
    if (it.startsWith("/") && !it.endsWith("/"))
      factory.setContextPath(it)
    else
      logger.warn { "Ignoring invalid server context path: $it" }
  }
}
```

它分两段处理。

第一段处理 `serverPort`：

- 如果 `settingsProvider.serverPort` 为 `null`，什么都不做，继续使用 Spring Boot 默认配置或外部配置。
- 如果不为 `null` 且 `it > 1`，调用 `factory.setPort(it)`。
- 如果端口小于等于 `1`，不设置端口，只打印 warning。

这里的校验比较宽松，只检查 `> 1`。不过在 REST 更新入口 `SettingsUpdateDto.kt` 中，`serverPort` 使用了 `@Positive` 和 `@Max(65535)`，所以通过 API 保存时会限制在合法端口范围内。目标文件里的检查更像是启动期的兜底保护。

第二段处理 `serverContextPath`：

- 如果 `settingsProvider.serverContextPath` 为 `null`，什么都不做。
- 如果字符串以 `/` 开头，且不以 `/` 结尾，则调用 `factory.setContextPath(it)`。
- 否则记录 warning，忽略该值。

例如：

- `/komga`：会生效。
- `/komga/subpath`：会生效。
- `komga`：不会生效，因为没有以 `/` 开头。
- `/komga/`：不会生效，因为以 `/` 结尾。
- `/`：不会生效，因为同时以 `/` 开头和结尾。

同样，REST 更新 DTO 里对 `serverContextPath` 有更严格的正则：

```kotlin
^/[\w-/]*[a-zA-Z0-9]$
```

这说明 API 层会限制 context path 必须以 `/` 开头，最后一个字符必须是英文字母或数字，中间允许 word 字符、连字符、斜杠等。目标文件里的判断则是启动期兜底，避免明显不符合 Spring Boot context path 预期的值被塞进 Web 容器。

## 上下游关系

上游主要是 `KomgaSettingsProvider`。

路径：`komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaSettingsProvider.kt`

其中相关字段是：

```kotlin
var serverPort: Int? =
  serverSettingsDao.getSettingByKey(Settings.SERVER_PORT.name, Int::class.java)

var serverContextPath: String? =
  serverSettingsDao.getSettingByKey(Settings.SERVER_CONTEXT_PATH.name, String::class.java)
```

`KomgaSettingsProvider` 通过 `ServerSettingsDao` 从数据库读取配置项。对应的内部枚举 key 是：

```kotlin
SERVER_PORT,
SERVER_CONTEXT_PATH,
```

也就是说，`WebServerConfiguration.kt` 不关心设置具体怎么持久化，只关心 `settingsProvider` 当前暴露出来的值。

另一个上游是 REST 设置接口。

路径：`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt`

`SettingsController` 暴露了 `api/v1/settings`，管理员可以通过 PATCH 更新设置：

```kotlin
if (newSettings.isSet("serverPort")) komgaSettingsProvider.serverPort = newSettings.serverPort
if (newSettings.isSet("serverContextPath")) komgaSettingsProvider.serverContextPath = newSettings.serverContextPath
```

这说明端口和 context path 可以通过 API 写入 `KomgaSettingsProvider`，最终保存到数据库。下一次应用启动时，`WebServerConfiguration` 会读取这些数据库值并应用到 Web 服务器工厂。

DTO 校验在：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/SettingsUpdateDto.kt`

相关字段：

```kotlin
@get:Positive
@get:Max(65535)
var serverPort: Int?

@get:Pattern(regexp = "^/[\\w-/]*[a-zA-Z0-9]$")
var serverContextPath: String?
```

这说明通过 REST API 写入时已经做了合法性校验。

下游主要是 Spring Boot 的内嵌 Servlet Web 服务器工厂：

```kotlin
ConfigurableServletWebServerFactory
```

目标文件调用：

```kotlin
factory.setPort(it)
factory.setContextPath(it)
```

这两个调用会影响最终 Web 服务监听地址和 URL 根路径。

同目录里还有一个相关的“生效值读取器”：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebServerEffectiveSettings.kt`

它通过 `ServletWebServerInitializedEvent` 记录真实启动后的端口：

```kotlin
effectiveServerPort = event.webServer.port
```

并通过 `ServletContext` 读取实际 context path：

```kotlin
val effectiveServletContextPath: String = servletContext.contextPath
```

`SettingsController` 在 GET 设置时会把三类来源一起返回：

- configuration source：来自 `server.port`、`server.servlet.context-path` 这类 Spring 配置。
- database source：来自 `KomgaSettingsProvider`。
- effective value：实际运行中的值，来自 `WebServerEffectiveSettings`。

这能帮助前端或管理员区分“配置里写了什么”和“当前进程实际用了什么”。

同目录的 `WebMvcConfiguration.kt` 与目标文件容易混淆，但职责不同：

- `WebServerConfiguration.kt`：配置 Web 容器本身，如端口、context path。
- `WebMvcConfiguration.kt`：配置 Spring MVC 层，如静态资源、缓存策略、参数解析器、拦截器。

## 运行/调用流程

整体流程可以按应用启动和运行期设置更新分开理解。

应用启动时：

1. Spring 创建 `KomgaSettingsProvider`。
2. `KomgaSettingsProvider` 通过 `ServerSettingsDao` 从数据库读取 `SERVER_PORT` 和 `SERVER_CONTEXT_PATH`。
3. Spring Boot 创建内嵌 Servlet Web 服务器工厂。
4. 因为 `WebServerConfiguration` 是 `@Component`，且实现了 `WebServerFactoryCustomizer<ConfigurableServletWebServerFactory>`，Spring Boot 会调用它的 `customize(factory)`。
5. `customize` 读取 `settingsProvider.serverPort`。
6. 如果端口存在且大于 `1`，调用 `factory.setPort(port)`。
7. 如果端口无效，打印 warning，并忽略这个数据库值。
8. `customize` 读取 `settingsProvider.serverContextPath`。
9. 如果 context path 以 `/` 开头且不以 `/` 结尾，调用 `factory.setContextPath(path)`。
10. 如果 context path 无效，打印 warning，并忽略这个数据库值。
11. Web 服务器启动。
12. `WebServerEffectiveSettings` 监听 `ServletWebServerInitializedEvent`，记录实际端口。

运行期通过 REST API 修改设置时：

1. 管理员请求 `PATCH api/v1/settings`。
2. 请求体被绑定到 `SettingsUpdateDto`。
3. Bean Validation 校验 `serverPort`、`serverContextPath`。
4. `SettingsController.updateServerSettings` 判断字段是否显式传入。
5. 如果传入 `serverPort`，写入 `komgaSettingsProvider.serverPort`。
6. 如果传入 `serverContextPath`，写入 `komgaSettingsProvider.serverContextPath`。
7. `KomgaSettingsProvider` 把值保存到 `ServerSettingsDao` 对应的数据库设置项。
8. 当前已经启动的 Web 服务器不会因为这个文件立即重新绑定端口或 context path。
9. 根据当前片段推断，这些 Web 容器级设置通常需要应用重启后才会通过 `WebServerConfiguration.customize` 生效。依据是目标文件只在 Web server factory 创建阶段设置 `factory`，没有看到运行期重启 Web 容器或重新绑定端口的逻辑。

GET 设置时：

1. 管理员请求 `GET api/v1/settings`。
2. `SettingsController` 返回 `SettingsDto`。
3. 对 `serverPort` 和 `serverContextPath`，返回 `SettingMultiSource`。
4. `SettingMultiSource` 包含外部配置源、数据库配置源、实际生效值。
5. 这样用户可以看到数据库里保存的值是否已经是当前进程实际使用的值。

## 小白阅读顺序

建议按下面顺序读，不要一上来就陷进 Spring Boot 生命周期细节。

第一步，读目标文件：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebServerConfiguration.kt`

先只关注一件事：它拿 `settingsProvider.serverPort` 和 `settingsProvider.serverContextPath` 去改 `factory`。

第二步，读设置来源：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaSettingsProvider.kt`

重点看这两个属性：

```kotlin
serverPort
serverContextPath
```

理解它们是从 `ServerSettingsDao` 读取、再写回数据库的。

第三步，读 API 更新入口：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt`

重点看：

```kotlin
getServerSettings()
updateServerSettings()
```

这里能看到管理员如何读取和修改这些设置。

第四步，读 DTO 校验：

`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto/SettingsUpdateDto.kt`

重点看 `@Positive`、`@Max(65535)`、`@Pattern`。这能解释为什么目标文件里校验看起来简单，因为更严格的输入校验已经在 REST DTO 层做了。

第五步，读实际生效值：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebServerEffectiveSettings.kt`

它告诉你当前进程真正启动后的端口和 context path 是什么，也解释了 `SettingsController` 为什么能返回 effective value。

第六步，再对比 MVC 配置：

`komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebMvcConfiguration.kt`

这一步是为了建立边界感：Web server 配置和 Spring MVC 配置不是一回事。前者处理容器端口和 context path，后者处理静态资源、缓存、参数解析器等 MVC 行为。

## 常见误区

误区一：以为修改 `serverPort` 后当前进程会立刻换端口。

从当前代码看，`WebServerConfiguration.customize(factory)` 是 Web 服务器工厂创建阶段的回调。运行期通过 `SettingsController` 修改数据库设置，只是保存了新值。根据当前片段推断，端口和 context path 这类容器级配置需要重启应用后才会被目标文件重新读取并应用。

误区二：以为 `WebServerConfiguration.kt` 读取的是 `application.yml`。

它直接读取的是 `KomgaSettingsProvider`，而 `KomgaSettingsProvider` 的 `serverPort` 和 `serverContextPath` 来源是 `ServerSettingsDao`，也就是 Komga 自己的服务端设置存储。`application.yml` 或环境变量中的 `server.port`、`server.servlet.context-path` 在 `SettingsController` 中作为 configuration source 展示，但目标文件本身没有直接注入这些 Spring 配置项。

误区三：以为 `serverContextPath` 可以随便写。

目标文件要求它必须以 `/` 开头，且不能以 `/` 结尾。REST DTO 里还有更严格的正则校验。合法例子是 `/komga`、`/komga/subpath`。不合法例子是 `komga`、`/komga/`、`/`。

误区四：以为目标文件负责所有 Web 行为。

它只负责 Web 服务器工厂层面的端口和 context path。静态资源路径、缓存策略、API 缓存、参数解析器在 `WebMvcConfiguration.kt` 中。请求日志、ETag、Kobo 相关过滤器在同目录其他 Filter 配置中。

误区五：以为 `it > 1` 就是完整端口校验。

目标文件里对端口只做了 `> 1` 的兜底判断，但 API DTO 层使用了 `@Positive` 和 `@Max(65535)`。所以完整约束要结合 `SettingsUpdateDto.kt` 看。目标文件不是唯一的校验点。

误区六：以为 `null` 是错误值。

在这里 `null` 表示“不使用数据库覆盖值”。如果 `serverPort` 为 `null`，目标文件不会调用 `factory.setPort`，Spring Boot 会继续使用默认端口或外部配置。如果 `serverContextPath` 为 `null`，也不会覆盖 context path。

误区七：混淆 database source 和 effective value。

`KomgaSettingsProvider.serverPort` 是数据库中保存的期望值；`WebServerEffectiveSettings.effectiveServerPort` 是当前进程真正启动后的值。两者可能不同，尤其是在刚通过 API 修改设置但还没有重启应用时。
