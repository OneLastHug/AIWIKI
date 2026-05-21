# 目录：komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest

## 它负责什么

这个目录是 Komga 后端的传统 REST API 接入层，包名是 `org.gotson.komga.interfaces.api.rest`。它的职责不是保存核心业务规则，而是把 HTTP 请求转换成应用内的查询、命令和任务，再把 domain、repository、service 返回的数据转换成 JSON、图片、文件流、CSS、WebPub/Divina/R2 positions 等 HTTP 响应。

从代码形态看，它是 Spring Boot MVC 风格：主类使用 `@RestController`、`@RequestMapping`、`@GetMapping`、`@PostMapping`、`@PatchMapping` 等注解暴露接口；用 `@AuthenticationPrincipal KomgaPrincipal` 获取当前用户；用 `@PreAuthorize` 做管理员或本人权限限制；用 `ResponseStatusException`、`@ResponseStatus` 把业务结果映射成 HTTP 状态码。

这个目录里的接口覆盖 Komga Web UI 和外部客户端常用能力：书籍、系列、书库、合集、阅读列表、用户、设置、字体、历史记录、任务、发布版本、登录辅助、服务器 claim、OAuth2 provider、文件系统浏览、页面哈希和临时书籍分析等。

## 关键组成

第一类是资源型 controller。`BookController.kt` 是最大的入口之一，暴露 `api/v1/books` 相关接口，包括书籍列表、详情、前后一本、缩略图、页面、manifest、metadata patch、阅读进度、导入、删除文件和重新生成封面。它注入 `BookRepository`、`BookMetadataRepository`、`BookLifecycle`、`BookAnalyzer`、`TaskEmitter`、`WebPubGenerator`、`ContentRestrictionChecker`、`CommonBookController` 等对象，说明它既负责读模型查询，也会触发后台任务和阅读器资源输出。`SeriesController.kt` 与它类似，围绕 `api/v1/series`、`api/v2/series/.../tachiyomi` 处理系列列表、封面、书籍、metadata、阅读进度和系列打包文件。`LibraryController.kt` 管理 `api/v1/libraries`，负责书库列表、创建、更新、删除、扫描、分析、刷新元数据、清空回收站等。

第二类是集合与组织接口。`SeriesCollectionController.kt` 处理 `api/v1/collections`，`ReadListController.kt` 处理 `api/v1/readlists`。它们都包含列表、详情、缩略图、创建、更新、删除，以及子资源查询。`ReadListController.kt` 还支持 ComicRack 匹配、Tachiyomi 阅读进度和阅读列表文件导出。

第三类是账户、权限与启动配置。`UserController.kt` 暴露 `api/v2/users`，包含当前用户、用户列表、创建、删除、修改角色/共享书库/内容限制、密码、认证活动、API key 等。`ClaimController.kt` 暴露 `api/v1/claim`，在服务器尚无用户时创建初始管理员，并通过 `@SecurityRequirements` 表示不要求常规安全认证。`LoginController.kt` 提供 `api/v1/login/set-cookie`，用于基于 `X-Auth-Token` 设置会话 cookie。`OAuth2Controller.kt` 返回 OAuth2 provider 信息。

第四类是配置和辅助接口。`SettingsController.kt` 管理服务端设置，`ClientSettingsController.kt` 管理前端全局/用户级客户端设置。`FileSystemController.kt` 提供文件系统目录浏览，主要服务于管理员选择书库路径。`FontsController.kt` 扫描内置字体和 `KomgaProperties.fonts.dataDirectory` 下的字体目录，提供字体 family 列表、字体文件下载和 CSS `@font-face` 输出，供 EPUB 阅读器使用。`ReferentialController.kt` 提供作者、标签、语言、出版社、年龄分级、发布日期等引用数据。`AnnouncementController.kt`、`HistoricalEventController.kt`、`ReleaseController.kt`、`TaskController.kt`、`SyncPointController.kt` 则分别对应公告、历史事件、版本发布、任务删除、同步点清理等较小功能。

第五类是 `dto` 子包。`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/dto` 下放了 REST 响应体、请求体和转换函数，例如 `BookDto.kt`、`SeriesDto.kt`、`LibraryDto.kt`、`UserDto.kt`、`SettingsDto.kt`、`BookMetadataUpdateDto.kt`。这里常见三种模式：纯 `data class` 定义 JSON 结构；`fun Domain.toDto()` 把 domain 模型转成 API 结构；`fun XxxDto.toDomain()` 或 `patch(...)` 把请求更新合并回 domain 模型。`BookDto.restrictUrl`、`Library.toDto(includeRoot)` 这类函数还会根据权限隐藏本地路径。

`ErrorHandlingControllerAdvice.kt` 是全局 REST 异常处理类，目前专门处理 `ConstraintViolationException` 和 `MethodArgumentNotValidException`，把 Bean Validation 错误统一转成 `ValidationErrorResponse`，内容是 `violations: List<Violation>`。

## 上下游关系

上游是 HTTP 客户端，包括 Komga Web UI、移动端/第三方客户端、Tachiyomi 兼容接口、EPUB/WebPub 阅读器和可能的脚本调用。Spring Boot 从 `Application.kt` 的 `@SpringBootApplication` 启动后扫描该包，Spring MVC 根据注解注册路由。

同层邻居主要在 `komga/src/main/kotlin/org/gotson/komga/interfaces/api`。`BookController.kt` 会复用 `CommonBookController` 输出原始页面、资源和文件；也会使用 `ContentRestrictionChecker` 检查用户内容限制；`WebPubGenerator`、`OpdsGenerator` 等接口层组件也复用 `rest.dto` 中的 DTO。

下游分三层：一是 `domain.persistence` 仓储，如 `BookRepository`、`LibraryRepository`、`SeriesRepository`、`KomgaUserRepository`，负责读写领域数据；二是 `domain.service` 生命周期服务，如 `BookLifecycle`、`LibraryLifecycle`、`KomgaUserLifecycle`，负责业务状态变更；三是 `application.tasks.TaskEmitter`，用于把扫描、分析、元数据刷新、导入、缩略图重建、删除文件等耗时操作投递成后台任务。再往下还有 `infrastructure`，例如 `jooq` DTO DAO、`security`、`openapi`、`web` 路径转换、`image` 分析、`mediacontainer` 内容检测。

安全链路由 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/SecurityConfiguration.kt` 配置。那里启用了 `@EnableMethodSecurity(prePostEnabled = true)`，因此 controller 上的 `@PreAuthorize` 生效；同时配置了部分公开路径，例如 `api/v1/claim`、`api/v1/oauth2/providers`、`api/v1/client-settings/global/list`、`api/v1/books/{bookId}/resource/**`、`api/v1/fonts/resource/**`。

## 运行/调用流程

典型读接口流程是：客户端请求 `GET /api/v1/libraries` 或 `POST /api/v1/books/list`；Spring MVC 根据 mapping 找到 controller 方法；安全过滤器先完成认证，方法参数注入 `KomgaPrincipal`、`Pageable`、`@RequestBody`、`@RequestParam`；controller 根据当前用户构造 `SearchContext` 或权限判断；调用 repository 或 DTO repository 查询；返回 `LibraryDto`、`BookDto`、`Page<BookDto>` 等对象；Jackson 序列化为 JSON。

典型写接口流程是：客户端提交 `POST`、`PATCH`、`DELETE`；请求体先经过 `jakarta.validation` 校验；controller 检查 `@PreAuthorize` 和资源存在性；简单更新会直接调用 lifecycle/repository，例如用户密码、metadata patch、设置更新；耗时操作会调用 `TaskEmitter`，例如扫描书库、分析书籍、刷新元数据、导入书籍、重新生成缩略图。很多任务接口返回 `202 ACCEPTED`，表示请求已接受但实际处理在后台完成。

二进制/阅读器接口略不同。书籍页面、缩略图、字体文件、系列/阅读列表文件导出会返回 `ResponseEntity<Resource>` 或图片媒体类型，不一定是 JSON。部分接口还会处理缓存相关逻辑，例如 `ETag`、`Last-Modified`、`304 Not Modified`，具体公共逻辑在 `interfaces/api/CommonBookController.kt` 和 `infrastructure/web/EtagFilterConfiguration.kt` 附近。

## 小白阅读顺序

1. 先看 `LibraryController.kt`。它中等规模，能看到最典型的 REST controller 写法：`@RestController`、路径映射、当前用户权限、DTO 转换、调用 lifecycle、异常转 HTTP 状态。

2. 再看 `dto/LibraryDto.kt`、`dto/ScanIntervalDto.kt`、`dto/SeriesCoverDto.kt`。这样能理解 REST 层为什么不直接暴露 domain model，而是用 DTO 控制字段、格式和权限隐藏。

3. 接着看 `BookController.kt` 的开头、列表接口、metadata patch、read-progress、import/delete 这些片段。它展示了查询、内容限制、后台任务、文件/manifest 输出这些复杂场景。

4. 然后看 `UserController.kt` 和 `ClaimController.kt`。这两者能帮助理解用户身份、管理员权限、共享书库、内容限制、初始管理员创建这些系统级概念。

5. 再看 `ErrorHandlingControllerAdvice.kt`。它很短，但能解释为什么请求校验失败时返回统一的 `violations` 结构。

6. 最后按功能补读 `SeriesController.kt`、`ReadListController.kt`、`SeriesCollectionController.kt`、`SettingsController.kt`、`FontsController.kt`。这些文件很多模式重复，带着前面的框架感去看会更快。

## 常见误区

不要把这个目录理解成“业务核心”。它会组装参数、做权限判断、触发任务、合并 patch，但真正的业务生命周期在 `domain.service`，持久化在 `domain.persistence` 和 `infrastructure.jooq`，后台调度在 `application.tasks`。

不要以为所有接口都只返回 JSON。虽然很多 controller 的 `@RequestMapping` 默认 `produces = application/json`，但书籍页面、封面缩略图、字体文件、CSS、WebPub manifest、文件下载会覆盖 `produces` 或返回 `Resource`。

不要忽略 `@PreAuthorize` 和 `KomgaPrincipal`。很多接口是否能访问并不只由 URL 决定，还取决于当前用户角色、共享书库、内容限制和是否为本人。例如普通用户可能能读书籍，但不能看到本地 root 路径，也不能执行管理员任务。

不要把 `api/v1`、`api/v2` 当成完全分离的新旧系统。这个目录中同时存在 v1、v2，甚至有 `@Deprecated` 的旧接口，例如书籍/系列早期 GET 列表接口提示改用 POST list。阅读时应以具体 controller 和 `@Operation` 描述为准。

不要误解 `PATCH` DTO 中的 nullable 字段。部分更新 DTO 需要区分“字段没传”和“字段传了 null”，代码里会用 `isSet("fieldName")` 或 `patch(...)` 处理。直接按 Kotlin nullable 理解，容易漏掉“清空字段”和“不修改字段”的差别。

不要认为 DTO 只被 REST controller 使用。根据当前片段推断，`rest.dto` 已被 `interfaces/api`、`interfaces/api/persistence`、`infrastructure/jooq/main`、`infrastructure/search` 等包引用，说明这些 DTO 也承担了一部分接口层读模型和搜索索引的数据结构角色。
