# 文件：komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/ResourceNotFoundController.kt

## 它负责什么

`ResourceNotFoundController.kt` 是 Komga 后端 MVC 层里的“未匹配路由兜底控制器”。

它处理的不是普通业务接口，而是 Spring MVC 在找不到任何 handler 时抛出的 `NoHandlerFoundException`。它根据请求路径做两种分流：

1. 如果请求的是后端接口类路径，例如 `/api`、`/opds`、`/sse`，就明确返回 HTTP `404 Not Found`。
2. 如果请求的不是这些 API 路径，就把请求转发到 `/`，让前端应用入口页面处理。

这类逻辑通常用于单页应用，也就是 SPA。用户直接访问前端路由，例如 `/book/0DBTWY6S0KNX9`，后端本身没有这个 MVC handler，但这不应该返回后端 404，而应该返回前端 `index` 页面，让浏览器里的前端路由接管。

从测试 `komga/src/test/kotlin/org/gotson/komga/interfaces/mvc/ResourceNotFoundControllerTest.kt` 可以确认它的设计意图：

- `/api/v1/doesnotexist` 返回 404
- `/opds/v2/doesnotexist` 返回 404
- `/sse/v1/doesnotexist` 返回 404
- `/book/0DBTWY6S0KNX9` 返回 200，说明被转发到了前端入口

## 关键组成

这个文件的包名是：

```kotlin
package org.gotson.komga.interfaces.mvc
```

说明它属于 `interfaces.mvc` 层，主要处理面向 Web/MVC 的请求适配逻辑，而不是领域模型或业务服务。

它的主要 import 有：

```kotlin
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Component
import org.springframework.web.bind.annotation.ControllerAdvice
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.server.ResponseStatusException
import org.springframework.web.servlet.NoHandlerFoundException
```

这些 import 对应的职责如下：

- `HttpServletRequest`：读取当前请求的 URI。
- `HttpStatus`：使用 Spring 的 HTTP 状态码枚举。
- `Component`：把当前类注册为 Spring Bean。
- `ControllerAdvice`：让这个类成为全局 MVC 控制器增强器，可以集中处理 controller 层异常。
- `ExceptionHandler`：声明某个方法处理指定异常。
- `ResponseStatusException`：主动抛出带 HTTP 状态码的异常。
- `NoHandlerFoundException`：Spring MVC 没有找到匹配 handler 时的异常。

核心类是：

```kotlin
@Component
@ControllerAdvice
class ResourceNotFoundController {
  val apis = listOf("/api", "/opds", "/sse")

  @ExceptionHandler(NoHandlerFoundException::class)
  fun notFound(request: HttpServletRequest): String {
    if (apis.any { request.requestURI.startsWith(it, true) }) throw ResponseStatusException(HttpStatus.NOT_FOUND)
    return "forward:/"
  }
}
```

### `@Component`

`@Component` 让 Spring 自动扫描并注册 `ResourceNotFoundController`。如果没有被注册为 Bean，`@ControllerAdvice` 的异常处理逻辑也不会生效。

### `@ControllerAdvice`

`@ControllerAdvice` 表示这是一个全局 controller 增强类。它不是普通的页面 controller，也不直接声明 `@GetMapping`、`@PostMapping` 这类路由，而是集中处理 MVC 层发生的异常。

这里它专门处理 `NoHandlerFoundException`，也就是“后端没有找到任何匹配路由”的情况。

### `apis`

```kotlin
val apis = listOf("/api", "/opds", "/sse")
```

这是一个 API 前缀白名单，或者更准确地说，是“不能 fallback 到前端页面”的路径前缀列表。

这三个路径分别代表不同类型的后端接口入口：

- `/api`：常规 REST API。
- `/opds`：OPDS 相关接口，常用于阅读器/书库聚合客户端访问。
- `/sse`：Server-Sent Events 事件流接口。

这些路径如果找不到 handler，应该告诉客户端“接口不存在”，而不是返回前端 HTML 页面。否则 API 客户端可能会收到一个 `200 OK` 的 HTML 页面，导致错误更隐蔽。

### `notFound`

```kotlin
@ExceptionHandler(NoHandlerFoundException::class)
fun notFound(request: HttpServletRequest): String {
  if (apis.any { request.requestURI.startsWith(it, true) }) throw ResponseStatusException(HttpStatus.NOT_FOUND)
  return "forward:/"
}
```

这是整个文件的核心方法。

它通过 `@ExceptionHandler(NoHandlerFoundException::class)` 绑定到 `NoHandlerFoundException`。当 Spring MVC 无法找到请求对应的 controller handler 时，会进入这个方法。

方法参数 `request: HttpServletRequest` 由 Spring 注入，用来读取当前请求信息。

判断逻辑是：

```kotlin
apis.any { request.requestURI.startsWith(it, true) }
```

含义是：只要当前请求 URI 以 `/api`、`/opds`、`/sse` 中任意一个开头，就认为这是接口请求。

这里 `startsWith(it, true)` 的第二个参数 `true` 表示忽略大小写。例如根据 Kotlin 标准库语义，`/API/xxx` 也会被认为匹配 `/api`。这能避免路径大小写导致的兜底误判。

如果匹配 API 前缀：

```kotlin
throw ResponseStatusException(HttpStatus.NOT_FOUND)
```

它不返回视图，而是抛出 `ResponseStatusException`，让 Spring 响应 HTTP 404。

如果不匹配 API 前缀：

```kotlin
return "forward:/"
```

返回 Spring MVC 的特殊视图名 `forward:/`。这不是 HTTP 重定向，而是服务端内部转发。请求会被转发到根路径 `/`，再由同目录的 `IndexController.kt` 接住。

## 上下游关系

上游是 Spring MVC 的请求分发机制。

当一个 HTTP 请求进入应用后，Spring 会尝试找到匹配的 controller handler。如果找不到，并且应用配置让 Spring 抛出 `NoHandlerFoundException`，这个异常会被 `ResourceNotFoundController` 捕获。

当前片段中没有直接看到 `throw-exception-if-no-handler` 等配置项；根据测试能触发该行为可以推断，测试环境或应用上下文中已经满足让 `NoHandlerFoundException` 被抛出并进入该 `@ExceptionHandler` 的条件。

同目录下游是：

```text
komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt
```

`IndexController` 的核心代码是：

```kotlin
@Controller
class IndexController(
  servletContext: ServletContext,
) {
  private val baseUrl: String = "${servletContext.contextPath}/"

  @GetMapping("/")
  fun index(model: Model): String {
    model.addAttribute("baseUrl", baseUrl)
    return "index"
  }
}
```

所以 `ResourceNotFoundController.kt` 中的：

```kotlin
return "forward:/"
```

最终会进入 `IndexController.index()`，返回 `index` 视图。

两者配合起来形成一个前端路由 fallback：

- `/` 正常渲染前端入口。
- `/book/xxx` 这类前端路由没有后端 handler，于是被 `ResourceNotFoundController` 转发到 `/`。
- `/api/xxx` 这类后端接口路径没有 handler，不转发，直接 404。

测试文件 `ResourceNotFoundControllerTest.kt` 是它最明确的行为说明。测试使用 `MockMvc` 发起请求，验证未知 API、OPDS、SSE 路径返回 404，而未知普通路径返回 200。

相关路径包括：

- `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/ResourceNotFoundController.kt`
- `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt`
- `komga/src/test/kotlin/org/gotson/komga/interfaces/mvc/ResourceNotFoundControllerTest.kt`

## 运行/调用流程

一个未知请求进入时，大致流程如下。

1. 浏览器或客户端发起请求。

例如：

```text
GET /book/0DBTWY6S0KNX9
```

或：

```text
GET /api/v1/doesnotexist
```

2. Spring MVC 尝试查找 controller handler。

如果路径有明确的 `@GetMapping`、`@PostMapping` 等 handler，就走对应业务 controller。

如果找不到 handler，则产生 `NoHandlerFoundException`。

3. `ResourceNotFoundController.notFound()` 捕获异常。

因为类上有：

```kotlin
@ControllerAdvice
```

方法上有：

```kotlin
@ExceptionHandler(NoHandlerFoundException::class)
```

所以 Spring 会调用：

```kotlin
fun notFound(request: HttpServletRequest): String
```

4. 方法读取请求 URI。

```kotlin
request.requestURI
```

然后判断是否以这些路径开头：

```kotlin
/api
/opds
/sse
```

5. 如果是接口路径，返回真正的 404。

例如：

```text
GET /api/v1/doesnotexist
```

满足：

```kotlin
request.requestURI.startsWith("/api", true)
```

于是执行：

```kotlin
throw ResponseStatusException(HttpStatus.NOT_FOUND)
```

最终客户端收到 HTTP 404。

这对 API 客户端很重要。API 客户端期望得到明确的 HTTP 状态码，而不是一个前端 HTML 页面。

6. 如果不是接口路径，转发到 `/`。

例如：

```text
GET /book/0DBTWY6S0KNX9
```

它不以 `/api`、`/opds`、`/sse` 开头，于是返回：

```kotlin
"forward:/"
```

Spring 在服务端内部把请求转发给 `/`。

7. `IndexController.index()` 处理 `/`。

`IndexController` 给模型添加：

```kotlin
baseUrl
```

然后返回：

```kotlin
"index"
```

最终前端入口页面返回给浏览器。

8. 前端路由接管。

浏览器拿到前端页面后，前端应用根据当前 URL，例如 `/book/0DBTWY6S0KNX9`，渲染对应页面。

因此，这个类的价值在于区分“真实后端接口不存在”和“前端路由需要回到 SPA 入口”。

## 小白阅读顺序

建议按下面顺序读：

1. 先看 `ResourceNotFoundController.kt` 的注解。

重点理解：

```kotlin
@Component
@ControllerAdvice
```

这说明它不是普通业务 controller，而是全局异常处理器。

2. 再看 `@ExceptionHandler`。

```kotlin
@ExceptionHandler(NoHandlerFoundException::class)
```

这行决定了它只处理“没有匹配到后端 handler”的场景。它不是处理所有 404，也不是处理业务里主动抛出的所有异常。

3. 看 `apis` 列表。

```kotlin
val apis = listOf("/api", "/opds", "/sse")
```

先记住这三个路径代表“后端接口区域”。这些区域不能走前端 fallback。

4. 看 `notFound()` 的 if 判断。

```kotlin
if (apis.any { request.requestURI.startsWith(it, true) }) throw ResponseStatusException(HttpStatus.NOT_FOUND)
```

这句可以拆成两步理解：

- `apis.any { ... }`：只要命中任意一个 API 前缀。
- `throw ResponseStatusException(HttpStatus.NOT_FOUND)`：就返回 404。

5. 看最后一行。

```kotlin
return "forward:/"
```

这句是 SPA fallback 的关键。它不是跳转到首页，而是在服务端内部把请求交给 `/` 的 handler。

6. 接着看 `IndexController.kt`。

重点看：

```kotlin
@GetMapping("/")
fun index(model: Model): String {
  model.addAttribute("baseUrl", baseUrl)
  return "index"
}
```

这样就能明白 `forward:/` 后面是谁在接。

7. 最后看 `ResourceNotFoundControllerTest.kt`。

测试比实现更容易建立直觉：

- 未知 `/api` 返回 404。
- 未知 `/opds` 返回 404。
- 未知 `/sse` 返回 404。
- 未知 `/book/...` 返回 200。

把这四个测试和 `apis` 列表对照起来，就能掌握这个文件的完整行为。

## 常见误区

### 误区一：以为这个类负责所有 404

它只声明处理：

```kotlin
NoHandlerFoundException
```

也就是 Spring MVC 没有找到 handler 的情况。

如果业务代码主动抛出别的异常，或者某个 controller 内部返回 404，不一定会经过这里。这个类不是全局错误页控制器，也不是完整的异常处理中心。

### 误区二：以为 `forward:/` 是浏览器重定向

`forward:/` 是服务端内部转发，不是 HTTP 302/301 重定向。

浏览器地址栏仍然可以保持原来的路径，例如 `/book/0DBTWY6S0KNX9`。服务端只是内部把请求交给 `/` 处理，然后返回前端入口页面。

这正是 SPA 深链接需要的效果：用户直接打开某个前端页面 URL 时，后端仍然返回前端应用。

### 误区三：以为所有未知路径都应该返回 404

对传统后端页面应用来说，未知路径通常应该 404。

但 Komga 这里存在前端路由。像 `/book/0DBTWY6S0KNX9` 可能是前端页面路径，不是后端接口路径。如果后端直接 404，用户刷新页面或直接打开书籍详情链接就会失败。

所以这里的策略是：

```text
API 未知路径：404
前端未知路径：返回 index
```

### 误区四：忽略 `/opds` 和 `/sse`

很多人只会注意 `/api`，但这个文件把 `/opds` 和 `/sse` 也当作接口区域。

原因是它们虽然不一定属于普通 REST API，但也是后端提供给客户端消费的接口入口：

- `/opds` 面向 OPDS 客户端。
- `/sse` 面向事件流连接。

这些路径如果不存在，应返回协议/客户端能理解的 404，而不是 HTML 页面。

### 误区五：认为 `startsWith("/api")` 只匹配 `/api/`

当前代码使用的是：

```kotlin
request.requestURI.startsWith(it, true)
```

这意味着只要 URI 以 `/api` 开头就会匹配，包括：

```text
/api
/api/v1/doesnotexist
/API/v1/doesnotexist
```

根据当前片段推断，它也会匹配类似 `/apixxx` 这种以 `/api` 字符串开头的路径，因为代码没有要求后面必须是 `/` 或路径结束。这可能是可接受的简化，因为正常路由命名不会使用这种前缀冲突；但阅读时要知道它是字符串前缀判断，不是严格的路径段匹配。

### 误区六：以为这个类单独就能渲染首页

`ResourceNotFoundController.kt` 本身不渲染 `index`，它只返回：

```kotlin
"forward:/"
```

真正处理 `/` 并返回 `index` 视图的是 `IndexController.kt`。

所以这个文件的角色更像“分流器”：

- 接口路径：抛出 404。
- 非接口路径：交给首页 controller。

### 误区七：把测试里的 200 理解成资源真实存在

测试中：

```kotlin
.get("/book/0DBTWY6S0KNX9")
.andExpect {
  status { isOk() }
}
```

这并不代表后端真的存在 `/book/0DBTWY6S0KNX9` 这个资源 handler。

它表示这个路径被当成前端路由处理，后端返回了前端入口页，所以 HTTP 状态是 200。具体书籍是否存在，通常要等前端加载后再调用 API 判断。
