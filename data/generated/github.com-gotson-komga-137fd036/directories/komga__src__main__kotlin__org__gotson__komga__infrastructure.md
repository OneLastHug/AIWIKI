# 目录：komga/src/main/kotlin/org/gotson/komga/infrastructure

## 它负责什么

`infrastructure` 是 Komga 后端里“连接外部世界和底层技术栈”的基础设施层。它不主要表达漫画、书籍、书库、阅读进度这些业务概念本身，而是为业务层和接口层提供可运行的技术能力：Spring Boot 配置、SQLite 数据源、jOOQ 查询支撑、Lucene 搜索索引、Spring Security 认证授权、Web MVC 适配、图片处理、媒体类型探测、元数据读取、Kobo/KOReader 集成、OpenAPI、事务、缓存、校验和 XML 支持。

从 `komga/src/main/kotlin/org/gotson/komga/Application.kt` 可以看到应用入口是标准 Spring Boot：`@SpringBootApplication` 加 `@EnableScheduling`，启动前会执行 `checkTempDirectory()`，并关闭 jOOQ logo/tips。由于 `infrastructure` 下大量类带有 `@Configuration`、`@Component`、`@Service`，它们会在 Spring Boot 启动扫描时自动装配，成为整个服务运行时的底座。

简单理解：`domain` 定义“Komga 是什么”，`application` 编排“Komga 要做什么”，`interfaces` 暴露 API，而 `infrastructure` 负责“这些事情如何落到数据库、HTTP、安全、文件、图片、搜索引擎和第三方协议上”。

## 关键组成

`configuration` 目录保存全局配置模型和运行时设置。`KomgaProperties` 通过 `@ConfigurationProperties(prefix = "komga")` 绑定配置文件中的 `komga.*` 属性，包含数据库、任务数据库、CORS、Lucene、Kobo、字体目录等配置。它的 `@PostConstruct` 会尝试创建主数据库和任务数据库所在目录。`StaticConfiguration` 提供固定 Bean，例如 `thumbnailType`、`pdfImageType`、`pdfResolution`。`ConfigurationChecker` 在启动后检查数据库路径是否位于 `cifs`、`nfs` 这类远程文件系统上，默认会阻止 SQLite 数据库存放在远程文件系统，以降低锁和一致性风险。`KomgaSettingsProvider` 则是运行时设置入口，它从 `ServerSettingsDao` 读写设置，例如 remember-me key、缩略图大小、任务池大小、服务端口、context path、Kobo 代理和 `kepubifyPath`，部分设置变化会发布 `SettingChangedEvent`。

`datasource` 和 `jooq` 是持久化基础。`DataSourcesConfiguration` 创建主库和任务库的读写数据源：`sqliteDataSourceRW`、`sqliteDataSourceRO`、`tasksDataSourceRW`、`tasksDataSourceRO`。当 SQLite 不是内存库且 journal mode 为 WAL 时，会拆分读写池；写池通常限制为 1，避免 SQLite 写并发问题。`KomgaJooqConfiguration` 基于这些 `DataSource` 创建 `dslContextRW`、`dslContextRO`、`tasksDslContextRW`、`tasksDslContextRO`，SQL 方言固定为 `SQLDialect.SQLITE`。`SplitDslDaoBase` 是 DAO 基类，它会在有非只读事务时强制使用 `dslRW`，否则使用 `dslRO`。`SeriesSearchHelper`、`BookSearchHelper`、`ContentRestrictionsSearchHelper` 等辅助类负责把领域层的 `SearchCondition`、`SearchContext` 转为 jOOQ `Condition` 和必要 join 信息。

`security` 是认证授权中心。`SecurityConfiguration` 定义多条 `SecurityFilterChain`：普通 `/api/**`、`/opds/**`、`/sse/**` 使用 HTTP Basic、remember-me、OAuth2/OIDC 和 API Key；`/kobo/**` 使用从 URI 中解析出的 API Key；`/koreader/**` 使用 `X-Auth-User` 请求头。它允许匿名访问少数端点，如 `/api/v1/claim`、OAuth2 providers、部分资源字体、OPDS auth 文档和 KOReader 创建用户接口，其余 API 默认需要认证。`KomgaUserDetailsService` 通过 `KomgaUserRepository.findByEmailIgnoreCaseOrNull` 查找用户并包装为 `KomgaPrincipal`。

`web` 负责 Spring MVC 与 Servlet 层适配。`WebMvcConfiguration` 注册静态资源路径、缓存策略、API/OPDS 的私有缓存头，以及自定义参数解析器 `AuthorsHandlerMethodArgumentResolver`、`DelimitedPairHandlerMethodArgumentResolver`。`WebServerConfiguration` 从 `KomgaSettingsProvider` 读取 `serverPort` 和 `serverContextPath` 动态定制内嵌 Web Server。其他过滤器配置包括 bracket 参数兼容、ETag、请求日志、Kobo 缺失端口修正等。

`search` 封装 Lucene。`LuceneConfiguration` 创建索引 analyzer、搜索 analyzer、Lucene `Directory`、`IndexWriter` 和 `SearcherManager`。测试环境用 `ByteBuffersDirectory`，非测试环境用 `FSDirectory`，目录来自 `komga.lucene.dataDirectory`。`SearchIndexLifecycle` 维护索引版本，支持重建 Book、Series、Collection、ReadList 索引，并监听 `DomainEvent`，在书籍、系列、集合、阅读列表增删改时更新 Lucene 文档。

`mediacontainer`、`image` 和 `metadata` 负责文件内容理解。`ContentDetector` 使用 Apache Tika 根据路径或流检测媒体类型，并能判断是否图片、把 media type 转扩展名。`TikaConfiguration` 提供 `TikaConfig` Bean。`ImageAnalyzer` 用 ImageIO 读取图片尺寸。`ImageConverter` 负责图片格式转换和缩放，使用 Thumbnailator，同时处理 WebP reader 优先级、透明通道转非透明格式时的白底合成。`metadata` 定义 `BookMetadataProvider`、`SeriesMetadataProvider` 等接口，子目录如 `comicrack`、`epub`、`mylar`、`barcode`、`localartwork`、`oneshot` 根据不同来源抽取书籍或系列元数据。由于本次只抽样读取了接口和部分目录结构，具体每个 provider 的解析规则需继续进入对应子目录查看。

其他支撑目录也很重要：`cache/TransientBookCache.kt` 用 Caffeine 实现一小时过期的临时书缓存，并实现 `TransientBookRepository`；`hash/Hasher.kt` 使用 `XXH3_128` 计算文件、字符串或流的哈希；`kobo` 处理 Kobo 同步、代理、kepub 转换和同步 token；`openapi` 配置接口文档；`transaction` 配置事务；`validation` 提供 BCP47、ISBN、空白字符串等 Bean Validation 注解；`xml` 处理 XML message converter 和命名空间工厂；`util` 放临时目录检查、Zip 工具；`sidecar` 根据当前片段推断是消费 sidecar 元数据文件的组件，依据是目录下存在 `SidecarBookConsumer.kt`、`SidecarSeriesConsumer.kt`。

## 上下游关系

上游主要来自 Spring Boot 启动、配置文件、HTTP 请求、领域事件和业务服务调用。启动阶段，`Application.kt` 触发组件扫描，`KomgaProperties` 绑定配置，`ConfigurationChecker` 校验数据库路径，`DataSourcesConfiguration` 和 `KomgaJooqConfiguration` 建立数据库访问能力，`LuceneConfiguration` 建立搜索能力，`SecurityConfiguration` 和 `WebMvcConfiguration` 建立 Web 请求处理链。

下游主要是外部技术组件：SQLite、HikariCP、jOOQ、Lucene、Spring Security、Spring MVC、Apache Tika、ImageIO、Thumbnailator、Caffeine、OAuth2/OIDC、Kobo/KOReader 客户端协议等。`infrastructure` 把这些库封装成 Spring Bean，让领域仓库、接口 DTO repository、REST controller、任务服务可以使用更稳定的内部抽象。

与领域层的关系体现为“实现或支撑领域端口”。例如 `TransientBookCache` 实现 `TransientBookRepository`；`KomgaUserDetailsService` 依赖 `KomgaUserRepository` 查询领域用户；`SearchIndexLifecycle` 监听 `DomainEvent` 并从 repository 读取实体；jOOQ helper 把 `SearchCondition` 转为 SQL 条件。它既依赖领域模型，也服务于领域流程。

与接口层的关系也很密切。`WebMvcConfiguration` 直接影响 REST 参数解析和静态资源；`SecurityConfiguration` 决定 API、OPDS、Kobo、KOReader 的认证边界；`OpenApiConfiguration` 和 openapi 注解类辅助生成 API 文档；Lucene 索引重建使用 `BookDtoRepository`、`SeriesDtoRepository` 读取接口层 DTO，说明搜索文档更偏向 API 展示模型而不是纯领域模型。

## 运行/调用流程

启动流程大致如下：

1. `Application.main` 先检查临时目录，再设置 jOOQ 系统属性，最后调用 `runApplication<Application>(*args)`。
2. Spring Boot 扫描 `org.gotson.komga` 包下组件，加载 `infrastructure` 中的配置类和服务类。
3. `KomgaProperties` 绑定 `komga.*` 配置并创建数据库目录；`ConfigurationChecker` 检查主库和任务库是否误放在远程文件系统。
4. `DataSourcesConfiguration` 根据 SQLite journal mode、是否内存库、pool size 等配置创建读写数据源。
5. `KomgaJooqConfiguration` 基于数据源创建多个 `DSLContext`，供 DAO 使用。
6. `LuceneConfiguration` 创建索引目录、analyzer、writer、searcher manager。
7. `SecurityConfiguration` 建立不同 URL 空间的认证过滤链；`WebMvcConfiguration` 注册静态资源、缓存策略和参数解析器。
8. 业务服务、controller、repository 开始正常使用这些 Bean。

一次普通 API 请求的路径通常是：HTTP 请求进入 Servlet 容器，先经过 `SecurityFilterChain` 判断 URL、认证方式和角色，再进入 Spring MVC；如 controller 方法参数包含自定义类型，`AuthorsHandlerMethodArgumentResolver` 等解析器会参与解析；业务层调用 repository 或 DTO repository 时，DAO 通过 `SplitDslDaoBase.dslRO` 或 `dslRW` 选择读写 `DSLContext`；最终 SQL 通过 jOOQ 到 SQLite。

一次搜索索引更新流程通常是：业务操作产生 `DomainEvent`，`SearchIndexLifecycle.consumeEvents` 监听到书籍、系列、集合或阅读列表的增删改事件；它从对应 repository 重新读取实体或 DTO，转换成 Lucene `Document`；然后调用 `LuceneHelper.addDocument`、`updateDocument` 或 `deleteDocuments`。如果是重建索引，则按 5000 条一批分页读取数据，先删除目标类型旧文档，再批量写入新文档。

一次媒体处理流程通常是：业务层拿到书籍或资源文件路径后，调用 `ContentDetector` 用 Tika 检测 media type；如果是图片，可能继续调用 `ImageAnalyzer` 获取尺寸，或调用 `ImageConverter` 转格式、缩略图缩放；元数据导入场景下，`BookMetadataProvider`、`SeriesMetadataProvider` 的具体实现会从 EPUB、ComicRack、Mylar、sidecar 文件或本地 artwork 中抽取可打补丁的元数据。

## 小白阅读顺序

建议先从 `komga/src/main/kotlin/org/gotson/komga/Application.kt` 开始，理解应用如何启动，以及 `infrastructure` 为什么会被 Spring 自动扫描。

第二步读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaProperties.kt`。这个文件是很多基础设施配置的索引，能快速知道 Komga 关心哪些外部资源：主数据库、任务数据库、CORS、Lucene、Kobo、字体、配置目录等。

第三步读数据库链路：`datasource/DataSourcesConfiguration.kt`、`jooq/KomgaJooqConfiguration.kt`、`jooq/SplitDslDaoBase.kt`。读完这三个文件，就能理解为什么项目里有 RW/RO 两套 `DSLContext`，以及 SQLite WAL 模式下为什么要拆读写池。

第四步读 Web 和安全：`security/SecurityConfiguration.kt`、`security/KomgaUserDetailsService.kt`、`web/WebMvcConfiguration.kt`、`web/WebServerConfiguration.kt`。这一组能解释 API、OPDS、Kobo、KOReader、OAuth2、API Key、remember-me、静态资源和缓存头是如何被统一接入的。

第五步读搜索：`search/LuceneConfiguration.kt`、`search/SearchIndexLifecycle.kt`。这里能看到配置如何变成 Lucene writer/searcher，以及领域事件如何驱动索引增量更新。

第六步再按兴趣读媒体和元数据：`mediacontainer/ContentDetector.kt`、`image/ImageAnalyzer.kt`、`image/ImageConverter.kt`、`metadata/BookMetadataProvider.kt` 以及 `metadata/comicrack`、`metadata/epub`、`metadata/mylar` 等子目录。它们更贴近“漫画文件如何被识别、转换、解析”。

最后再补看支撑类：`hash/Hasher.kt`、`cache/TransientBookCache.kt`、`validation`、`xml`、`openapi`、`kobo`。这些通常不是主流程入口，但能解释很多边缘行为。

## 常见误区

不要把 `infrastructure` 理解成“无业务含义的工具包”。它确实封装了技术库，但里面很多逻辑会直接影响业务行为，例如数据库是否允许远程文件系统、搜索条件如何转 SQL、哪些接口允许匿名访问、Kobo/KOReader 如何认证、缩略图如何生成。

不要以为所有设置都来自配置文件。`KomgaProperties` 绑定的是启动配置，而 `KomgaSettingsProvider` 读写的是数据库里的运行时设置。比如 `serverPort`、`serverContextPath`、`rememberMeKey`、`thumbnailSize`、`kepubifyPath` 都通过 `ServerSettingsDao` 管理。

不要忽略读写数据源拆分。`SplitDslDaoBase` 在非只读事务中会让读操作也走 `dslRW`，这是为了保证事务一致性；如果只看 `dslRO` 名字，容易误判某些 DAO 永远走只读连接。

不要把 Lucene 当成数据库替代品。`SearchIndexLifecycle` 显示 Lucene 文档来自 repository/DTO repository，并由领域事件维护。真实数据仍在 SQLite，Lucene 是搜索索引，需要版本升级和重建机制。

不要认为图片转换只是简单 `ImageIO.write`。`ImageConverter` 还处理 WebP reader 选择、透明通道、避免无意义放大、源图小于目标尺寸时跳过重采样等细节，这些都会影响封面、缩略图和阅读资源质量。

不要把安全配置只看成 `/api/**` 登录保护。这里至少有普通 API/OPDS/SSE、Kobo、KOReader 三套过滤链，认证来源包括 HTTP Basic、OAuth2/OIDC、remember-me cookie、`X-API-Key`、URI token、`X-Auth-User`。阅读接口行为时必须先确认请求路径落在哪条 filter chain 上。
