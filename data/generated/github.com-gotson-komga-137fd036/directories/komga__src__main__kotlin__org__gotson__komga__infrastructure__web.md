# 目录：komga/src/main/kotlin/org/gotson/komga/infrastructure/web

## 它负责什么

`komga/src/main/kotlin/org/gotson/komga/infrastructure/web` 是 Komga 后端的 Web 基础设施层，主要围绕 Spring Boot / Spring MVC / Servlet 做“请求进入 Controller 前”和“响应返回客户端前”的通用处理。它不直接实现漫画、书籍、书库等业务逻辑，而是提供几类横切能力：

1. Web 服务器启动参数定制，例如端口、context path。
2. MVC 配置，例如静态资源映射、缓存策略、自定义参数解析器。
3. Servlet Filter，例如 ETag、请求日志、Kobo 端口修正、数组查询参数兼容。
4. Controller 工具函数，例如 `getMediaTypeOrDefault`、`getCurrentRequest`、`setCachePrivate`。
5. 特定查询参数的解析，例如 `author=name,role`、`search_regex=regex,field`。

换句话说，这个目录是接口层的“地基”：业务 Controller 依赖它来获得统一的请求格式、缓存行为、静态资源服务、参数绑定和服务器实际运行信息。

## 关键组成

`WebMvcConfiguration.kt` 是 MVC 入口配置。它实现 `WebMvcConfigurer`，做三件关键事：第一，注册 `/webjars/**`、`/swagger-ui.html**`、`/index.html`、`/favicon.ico`、`/css/**`、`/js/**` 等静态资源路径；第二，为 `/api/**`、`/opds/**` 添加 `WebContentInterceptor`，统一设置私有缓存策略 `cachePrivate`；第三，向 Spring MVC 注册两个自定义 `HandlerMethodArgumentResolver`：`AuthorsHandlerMethodArgumentResolver` 和 `DelimitedPairHandlerMethodArgumentResolver`。

`Authors.kt` 和 `AuthorsHandlerMethodArgumentResolver.kt` 配合使用。`@Authors` 是参数注解，标记 Controller 方法中的某个参数需要特殊解析。解析器从 query parameter `author` 中读取值，支持形如 `author=name,role` 的格式，然后转换成 `List<Author>`。如果请求是单个空值，例如 `author=`，则返回 `null`。在 `SeriesController`、`ReadListController`、`SeriesCollectionController` 中可以看到 `@Authors authors: List<Author>?` 的使用，用于系列、阅读列表、集合等列表查询中的作者过滤。

`DelimitedPair.kt` 和 `DelimitedPairHandlerMethodArgumentResolver.kt` 是另一个自定义参数解析器，但注解已经标记为 `@Deprecated("was used only for search_regex which is deprecated")`。它读取指定参数名，例如 `@DelimitedPair("search_regex")`，把 `search_regex=regex,field` 解析成 `Pair<String, String>`。目前主要服务于旧版 `SeriesController` 中已废弃的 `search_regex` 查询参数。

`BracketParamsFilterConfiguration.kt` 和 `BracketParamsRequestWrapper.kt` 用于兼容带方括号的数组参数。过滤器只注册到 `/api/*`。请求进入后，它把 `HttpServletRequest` 包装成 `BracketParamsRequestWrapper`。这个 wrapper 会把 `tag[]`、`tag` 看成同一个参数名，并在 `getParameter`、`getParameterValues`、`getParameterNames`、`getParameterMap` 中统一合并。这样前端或客户端无论传 `?tag=a&tag=b` 还是 `?tag[]=a&tag[]=b`，Controller 都更容易以同一种方式读取。

`EtagFilterConfiguration.kt` 注册 `ShallowEtagHeaderFilter`，作用范围是 `/api/*`、`/opds/*`、`/kobo/*`。它会为普通响应生成浅 ETag，帮助客户端缓存和条件请求。但它排除了大文件下载路径，例如 `/api/v1/books/*/file/**`、`/opds/v1.2/books/*/file/**`、`/api/v1/readlists/*/file/**`、`/api/v1/series/*/file/**`、`/kobo/*/v1/books/*/file/**`。这是合理的：文件流响应通常体积大，浅 ETag 需要读取响应体，可能带来内存和性能问题。

`KoboMissingPortFilter.kt` 和 `KoboMissingPortFilterConfiguration.kt` 是 Kobo API 相关的特殊处理。过滤器只挂到 `/kobo/*`，并且优先级是 `Ordered.HIGHEST_PRECEDENCE`。如果请求没有任何 forwarded header，它会包装请求并覆盖 `getServerPort()`，端口来自 `komgaSettingsProvider.koboPort`，如果没配置则使用 `WebServerEffectiveSettings.effectiveServerPort`。如果请求已经带有 `Forwarded`、`X-Forwarded-Host`、`X-Forwarded-Port` 等代理头，则跳过处理。配置类还会在 `@PostConstruct` 中把 `ForwardedHeaderFilter` 的顺序调整到它之后，因为 `ForwardedHeaderFilter` 会消费或改写 forwarded header，而该过滤器需要先基于这些 header 判断是否跳过。

`RequestLoggingFilterConfig.kt` 是按条件启用的请求日志配置。只有当 `logging.level.org.springframework.web.filter.CommonsRequestLoggingFilter=debug` 时才注册 `CommonsRequestLoggingFilter`，并记录 query string、payload、headers，payload 最大长度为 10000。它是调试工具，不是默认请求链的必然组成。

`WebServerConfiguration.kt` 实现 `WebServerFactoryCustomizer<ConfigurableServletWebServerFactory>`，从 `KomgaSettingsProvider` 读取 `serverPort` 和 `serverContextPath`，在内嵌 Web 服务器启动时设置端口和 context path。它会校验端口大于 1，context path 必须以 `/` 开头且不能以 `/` 结尾；不合法时只记录 warning，不应用配置。

`WebServerEffectiveSettings.kt` 记录运行时实际生效的服务器信息。它通过 `ServletWebServerInitializedEvent` 获取真实端口，通过 `ServletContext` 获取 context path。`SettingsController` 注入它后，可以把配置文件值、Komga 设置值、实际生效值一起返回给管理端。

`Utils.kt` 提供零散但常用的 Web 工具：`URL.toFilePath()` 把 URL 转成本地路径字符串，`filePathToUrl()` 反向转换；`ResponseEntity.BodyBuilder.setCachePrivate()` 设置统一私有缓存；`getMediaTypeOrDefault()` 安全解析 media type，失败时退回 `application/octet-stream`；`getCurrentRequest()` 从 `RequestContextHolder` 中取当前 `HttpServletRequest`。这些工具被 `CommonBookController`、`BookController`、`KoboController`、`KoboProxy`、`LibraryController`、DTO 转换和 JOOQ DAO 使用。

## 上下游关系

上游主要是 Spring Boot 自动配置、Servlet 容器、`KomgaSettingsProvider`、`ForwardedHeaderFilter`、`ServletContext`、`ServletWebServerInitializedEvent`。这些组件向本目录提供运行环境、配置值和请求对象。

下游主要是 `interfaces/api`、`interfaces/api/rest`、`interfaces/api/kobo`、`interfaces/sse` 等接口层代码。Controller 不需要自己处理 `author` 参数格式、`search_regex` 拆分、`tag[]` 兼容、静态资源缓存、Kobo 端口补全等细节，而是通过这里的配置自动获得这些能力。

其中比较典型的链路是：`WebMvcConfiguration` 注册 `AuthorsHandlerMethodArgumentResolver`，然后 `SeriesController` 中的 `@Authors authors: List<Author>?` 自动接收到解析后的 `List<Author>`。另一个链路是：`KoboMissingPortFilterConfiguration` 注册 `/kobo/*` 过滤器，`KoboController` 和 `KoboProxy` 在处理 Kobo 请求时看到的 `request.serverPort` 已经可能被修正。

## 运行/调用流程

应用启动时，Spring 扫描 `@Configuration`、`@Component` 类。`WebServerConfiguration` 在内嵌服务器创建阶段定制端口和 context path。服务器真正初始化完成后，`WebServerEffectiveSettings.onApplicationEvent` 捕获实际端口。

MVC 初始化时，`WebMvcConfiguration` 注册静态资源路径、缓存拦截器和参数解析器。Filter 初始化时，`BracketParamsFilterConfiguration`、`EtagFilterConfiguration`、`KoboMissingPortFilterConfiguration` 根据 URL pattern 注册各自过滤器；`RequestLoggingFilterConfig` 则只有在指定日志级别为 debug 时才注册。

请求进入时，如果路径匹配 `/api/*`，会先经过 bracket 参数 wrapper，把 `xxx[]` 和 `xxx` 统一。如果路径匹配 `/api/*`、`/opds/*`、`/kobo/*`，普通响应可能被 ETag 过滤器处理。如果路径是 `/kobo/*`，且没有代理转发头，则 Kobo 过滤器会补足 server port。随后请求进入 Spring MVC，Controller 参数绑定阶段会检查是否有 `@Authors` 或 `@DelimitedPair`，有则交给本目录中的解析器处理。Controller 返回响应后，缓存拦截器、ETag filter 等再影响最终响应头。

## 小白阅读顺序

建议先看 `WebMvcConfiguration.kt`，它是最像“目录总开关”的文件，能看到静态资源、缓存和参数解析器如何挂进 Spring MVC。

第二步看 `Utils.kt`，理解哪些工具函数被 Controller、DAO、DTO 复用，尤其是 `getMediaTypeOrDefault` 和 `setCachePrivate`。

第三步看 `Authors.kt`、`AuthorsHandlerMethodArgumentResolver.kt`，再对照 `SeriesController` 或 `ReadListController` 中的 `@Authors` 参数，理解自定义注解如何影响 Controller 方法入参。

第四步看 `BracketParamsRequestWrapper.kt` 和 `BracketParamsFilterConfiguration.kt`，重点理解为什么要兼容 `param[]` 这种前端常见数组写法。

第五步看 `EtagFilterConfiguration.kt`，关注它为什么排除文件下载接口。

最后看 Kobo 相关的 `KoboMissingPortFilter.kt`、`KoboMissingPortFilterConfiguration.kt`，这部分依赖反向代理、Kobo API 和端口推断背景，适合放在基础 Web 流程理解之后阅读。

## 常见误区

不要把这个目录理解成业务接口目录。真正的 REST API 多在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest`，Kobo API 在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo`。这里更多是接口层的基础设施。

不要以为 `@Authors` 是普通 Spring 注解。它只有在 `WebMvcConfiguration.addArgumentResolvers` 注册了解析器后才会生效，否则 Spring 不知道如何把 `author=name,role` 转成 `List<Author>`。

不要忽略 `BracketParamsRequestWrapper` 对参数名的改写。Controller 看到的参数名可能已经把 `[]` 后缀去掉了，所以排查查询参数问题时，需要记住 `/api/*` 下请求会被这个 filter 包装。

不要把 `ShallowEtagHeaderFilter` 当成所有接口都适合的缓存优化。该配置明确排除了文件下载路径，说明大响应体使用浅 ETag 可能不划算。

不要认为 `KoboMissingPortFilter` 总会改端口。只要请求存在 `Forwarded` 或 `X-Forwarded-*` 等代理头，它就会跳过，让代理头处理链路负责端口和协议信息。

不要把 `WebServerConfiguration` 中的设置值等同于实际运行值。实际端口要看 `WebServerEffectiveSettings.effectiveServerPort`，因为配置可能为空、非法、被环境覆盖，或者由容器最终决定。
