# 目录：komga/src/main/kotlin/org/gotson/komga/interfaces/mvc

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/interfaces/mvc` 是 Komga 后端里非常薄的一层 Spring MVC Web 入口，主要服务浏览器访问的前端页面，而不是业务 API。

它的职责可以概括为两件事：

1. 当用户访问站点根路径 `/` 时，返回前端应用入口视图 `index`。
2. 当浏览器刷新某个前端路由、但后端找不到对应 handler 时，把非 API 请求转发回 `/`，让单页应用继续接管路由。

这类目录常见于“后端打包前端静态资源”的应用：Spring Boot 负责提供 `/api/**`、`/opds/**`、`/sse/**` 等后端接口，同时也负责把 Vue/React/Svelte 一类前端应用的入口页面交给浏览器。

这里的 `mvc` 不负责图书、书库、用户、阅读进度等核心业务逻辑。那些业务 REST 接口主要在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest`，OPDS 接口在 `interfaces/api/opds`，SSE 推送在 `interfaces/sse`。

## 关键组成

这个目录只有两个 Kotlin 文件。

`IndexController.kt` 定义了 `IndexController`：

- 使用 `@Controller` 注册为 Spring MVC 控制器。
- 构造函数注入 `jakarta.servlet.ServletContext`。
- 读取 `servletContext.contextPath`，拼出 `baseUrl`，形式是 `"${servletContext.contextPath}/"`。
- 使用 `@GetMapping("/")` 处理根路径访问。
- 在 `index(model: Model)` 中写入 `model.addAttribute("baseUrl", baseUrl)`。
- 返回字符串 `"index"`，交给 Spring MVC 的视图解析机制处理。

这里的返回值不是 JSON，也不是直接返回 HTML 字符串，而是一个视图名。根据当前片段推断，`index` 对应最终前端入口页面，且 `baseUrl` 会被页面模板或构建产物使用，用来适配应用部署在非根 context path 的场景。例如服务部署在 `/komga` 下时，前端需要知道资源和路由基准路径。

`ResourceNotFoundController.kt` 定义了 `ResourceNotFoundController`：

- 同时标注 `@Component` 和 `@ControllerAdvice`。
- 使用 `@ExceptionHandler(NoHandlerFoundException::class)` 捕获 Spring MVC 找不到 handler 的异常。
- 内部维护 `apis = listOf("/api", "/opds", "/sse")`。
- 如果请求 URI 以这些 API 前缀开头，则抛出 `ResponseStatusException(HttpStatus.NOT_FOUND)`。
- 如果不是这些 API 前缀，则返回 `"forward:/"`。

这个类的核心是区分“真正的后端接口 404”和“前端路由刷新造成的后端 404”。例如 `/api/v1/books/xxx` 找不到时应该返回 HTTP 404；但 `/series/123` 这类前端页面路由刷新时，后端可能没有对应 handler，此时应转发到 `/`，再由前端路由渲染页面。

邻近配置 `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebMvcConfiguration.kt` 也很关键。它通过 `addResourceHandlers` 映射静态资源：

- `/index.html`、`/favicon.ico`、`/manifest.json` 等入口和图标资源来自 `classpath:public/`，并设置 `CacheControl.noStore()`。
- `/css/**`、`/fonts/**`、`/img/**`、`/js/**` 来自对应的 `classpath:public/...`，并设置一年公共缓存。
- `/webjars/**` 和 `/swagger-ui.html**` 单独映射到 classpath 资源。

这说明 `mvc` 目录与 `infrastructure/web/WebMvcConfiguration.kt` 配合，形成了 Komga 的浏览器入口和静态资源分发机制。

## 上下游关系

上游是浏览器或 HTTP 客户端请求：

- 访问 `/` 时进入 `IndexController.index()`。
- 访问某个不存在的路径时，如果 Spring MVC 抛出 `NoHandlerFoundException`，会进入 `ResourceNotFoundController.notFound()`。
- 访问静态资源时，例如 `/js/...`、`/css/...`、`/index.html`，主要由 `WebMvcConfiguration` 配置的 resource handler 处理。

下游主要是 Spring MVC 视图解析和静态资源系统：

- `IndexController` 返回视图名 `index`。
- `ResourceNotFoundController` 对非 API 404 返回 `forward:/`，于是请求重新走根路径，再由 `IndexController` 返回前端入口。
- 对 API、OPDS、SSE 请求，`ResourceNotFoundController` 不兜底到前端，而是保持 404 语义。

它和其他接口层的边界也很清楚：

- `interfaces/api/rest`：业务 REST API，例如图书、书库、用户、设置等。
- `interfaces/api/opds`：OPDS feed/API。
- `interfaces/sse`：服务端事件推送。
- `interfaces/mvc`：浏览器页面入口与 SPA fallback。

因此，`mvc` 是“页面入口层”，不是“业务接口层”。

## 运行/调用流程

典型根路径访问流程：

1. 浏览器请求 `/`。
2. Spring MVC 找到 `IndexController.index()`。
3. `index()` 往 `Model` 中放入 `baseUrl`。
4. 方法返回 `"index"`。
5. Spring MVC 解析并返回前端入口页面。
6. 浏览器加载 `/js/**`、`/css/**`、`/img/**` 等静态资源。
7. 前端应用启动，后续通过 `/api/**`、`/opds/**`、`/sse/**` 与后端通信。

典型前端路由刷新流程：

1. 用户在浏览器直接打开或刷新 `/libraries/abc`、`/books/123` 这类前端路径。
2. 后端没有对应 controller handler。
3. Spring MVC 抛出 `NoHandlerFoundException`。
4. `ResourceNotFoundController.notFound()` 捕获异常。
5. 它检查 `request.requestURI` 是否以 `/api`、`/opds`、`/sse` 开头。
6. 如果不是，则返回 `"forward:/"`。
7. 请求转发到 `/`，再进入 `IndexController.index()`。
8. 前端应用根据浏览器地址栏中的路径渲染对应页面。

典型 API 404 流程：

1. 客户端请求 `/api/...`、`/opds/...` 或 `/sse/...` 下不存在的地址。
2. Spring MVC 找不到 handler。
3. `ResourceNotFoundController.notFound()` 捕获异常。
4. 因为 URI 命中 API 前缀，所以抛出 `ResponseStatusException(HttpStatus.NOT_FOUND)`。
5. 客户端得到真正的 404，而不是前端首页 HTML。

这个分支很重要，否则 API 客户端请求错误地址时可能拿到 `index.html`，导致调试困难，也破坏接口语义。

## 小白阅读顺序

建议先读 `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt`。这个文件最短，能马上看到 Spring MVC 如何把 `/` 映射到前端入口视图。

然后读 `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/ResourceNotFoundController.kt`。重点看 `@ControllerAdvice`、`@ExceptionHandler(NoHandlerFoundException::class)`、`forward:/` 和 `apis` 列表。理解这个文件后，就能明白为什么前端深层路由刷新不会直接 404。

接着读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebMvcConfiguration.kt`。它不在目标目录内，但与目标目录强相关。重点看 `addResourceHandlers` 中对 `/index.html`、图标、`/css/**`、`/fonts/**`、`/img/**`、`/js/**` 的映射，以及缓存策略差异：入口资源不缓存，带 hash 或可长期缓存的静态资源缓存一年。

最后再浏览 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds`、`komga/src/main/kotlin/org/gotson/komga/interfaces/sse` 的文件列表即可。目的不是深入业务，而是建立边界感：`mvc` 负责页面入口，其他目录负责真正的数据接口和实时推送。

## 常见误区

第一个误区是把 `IndexController` 当作业务首页接口。它不是返回首页数据的 API，而是返回前端应用入口视图。业务数据仍然要由前端通过 `/api/**` 等接口获取。

第二个误区是认为 `ResourceNotFoundController` 会吞掉所有 404。实际上它明确排除了 `/api`、`/opds`、`/sse`。这些路径下的错误请求仍然返回 404，不会被转发成前端页面。

第三个误区是忽略 `contextPath`。`IndexController` 注入 `ServletContext` 并生成 `baseUrl`，说明应用可能支持部署在非根路径下。阅读前端资源路径或反向代理配置时，要考虑这个变量的影响。

第四个误区是把 `"forward:/"` 理解为 HTTP 重定向。`forward:/` 是服务端内部转发，浏览器地址栏通常不会变；它的目的是让同一个请求交给 `/` 处理，从而返回前端入口。

第五个误区是只看 `mvc` 目录就试图理解静态资源加载。静态资源路径和缓存策略主要在 `infrastructure/web/WebMvcConfiguration.kt`，`mvc` 只负责入口视图和 fallback。两者合起来才构成完整的 Web 页面访问链路。

第六个误区是把 `index` 视图和 `/index.html` 静态资源完全等同。当前代码显示 controller 返回视图名 `"index"`，配置里又单独映射了 `/index.html` 到 `classpath:public/`。根据当前片段推断，它们共同服务前端入口，但具体视图解析如何把 `index` 映射到实际资源，还要结合项目的模板引擎配置、构建产物和 Spring Boot 自动配置继续确认。
