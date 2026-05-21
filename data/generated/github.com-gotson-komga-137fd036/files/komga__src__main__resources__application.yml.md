# 文件：komga/src/main/resources/application.yml

## 它负责什么

`komga/src/main/resources/application.yml` 是 Komga 服务端的默认 Spring Boot 配置入口。它不包含业务逻辑，但决定了应用启动时的一批基础行为：版本号注入、日志文件位置、Komga 数据目录、SQLite 数据库位置、Lucene 索引目录、Flyway 数据库迁移、Jackson JSON 行为、HTTP 服务端口、Actuator 管理端点以及 OpenAPI 文档暴露范围。

这个文件可以理解为“运行时默认配置表”。代码启动后，Spring Boot 会先读取它，再叠加 profile 配置，例如 `application-dev.yml`、`application-docker.yml`、`application-localdb.yml`，最后还会尝试读取用户配置目录下的外部配置文件。也就是说，它提供的是默认值，而不是所有部署场景下的最终值。

目标文件中最核心的自定义命名空间是 `komga.*`。这些配置会被绑定到 `org.gotson.komga.infrastructure.configuration.KomgaProperties`，再被数据库、搜索、字体、CORS、OAuth2、Kobo 等基础设施代码消费。根据当前片段推断，`application.yml` 是 Komga 自身配置体系与 Spring Boot 标准配置体系的交汇点。

## 关键组成

第一块是版本号：

```yaml
application.version: ${version}
```

这里的 `${version}` 不是用户运行时随便填的变量，而通常来自构建流程注入。相邻文件 `banner.txt` 也引用了 `${application.version}`，`OpenApiConfiguration.kt` 中也通过 `@Value("${application.version}")` 读取应用版本，用于 OpenAPI 信息。测试环境中 `komga/src/test/resources/application-test.yml` 会把它改成 `TESTING`。

第二块是日志配置：

```yaml
logging:
  logback:
    rollingpolicy:
      max-history: 7
      total-size-cap: 1GB
      clean-history-on-start: true
      max-file-size: 10MB
  file:
    name: ${komga.config-dir}/logs/komga.log
```

它设置了日志文件路径和滚动策略。默认日志写到 `komga.config-dir` 下的 `logs/komga.log`，保留最多 7 个历史周期，总大小上限 1GB，单个文件 10MB。`logging.level` 还压低了一些第三方组件的日志噪声，例如 ActiveMQ audit、fontbox、Spring Security 初始化相关日志。

第三块是 Komga 自定义配置：

```yaml
komga:
  database:
    file: ${komga.config-dir}/database.sqlite
  lucene:
    data-directory: ${komga.config-dir}/lucene
  fonts:
    data-directory: ${komga.config-dir}/fonts
  config-dir: ${user.home}/.komga
  tasks-db:
    file: ${komga.config-dir}/tasks.sqlite
```

默认情况下，Komga 会把配置、主数据库、任务数据库、Lucene 索引和字体缓存都放在用户主目录下的 `.komga` 目录里。主数据库是 `database.sqlite`，任务数据库是 `tasks.sqlite`，搜索索引目录是 `lucene`，字体相关数据目录是 `fonts`。

源码中 `KomgaProperties.kt` 使用 `@ConfigurationProperties(prefix = "komga")` 接收这些配置。`DataSourcesConfiguration.kt` 使用 `komga.database.file` 和 `komga.tasks-db.file` 创建数据源；`LuceneConfiguration.kt` 使用 `komga.lucene.data-directory` 打开 Lucene 的 `FSDirectory`；`FontsController.kt`、`KoboController.kt`、`CorsConfiguration.kt` 等也会读取同一个属性对象中的不同字段。

需要注意，源码文件里很多 Spring 占位符写成了类似 `\${komga.config-dir}` 的形式。这通常是为了在构建资源处理阶段避免被 Gradle 过早展开，让最终运行时仍由 Spring 解析 `${...}`。阅读源文件时不要误以为反斜杠是业务路径的一部分。

第四块是 Spring Boot 基础配置：

```yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration/{vendor}
    mixed: true
    placeholders:
      library-file-hashing: ${komga.file-hashing:true}
      library-scan-startup: ${komga.libraries-scan-startup:false}
      delete-empty-collections: ${komga.delete-empty-collections:true}
      delete-empty-read-lists: ${komga.delete-empty-read-lists:true}
```

Flyway 开启数据库迁移，迁移脚本位置按数据库 vendor 匹配。`placeholders` 把若干 Komga 开关传给 SQL 迁移脚本，例如是否启用文件哈希、是否启动时扫描媒体库、是否删除空集合和空阅读列表。这里的默认值通过 `${key:default}` 表达，例如 `komga.file-hashing` 默认是 `true`，`komga.libraries-scan-startup` 默认是 `false`。

```yaml
spring:
  thymeleaf:
    prefix: classpath:/public/
  mvc:
    async:
      request-timeout: 1h
  web:
    resources:
      add-mappings: false
```

这部分控制 Web 层。Thymeleaf 从 `classpath:/public/` 找模板或静态前端入口；MVC 异步请求超时设为 1 小时；`spring.web.resources.add-mappings: false` 关闭 Spring Boot 默认静态资源映射，说明 Komga 很可能有自己的资源处理方式或前端分发策略。

```yaml
spring:
  jackson:
    deserialization:
      FAIL_ON_NULL_FOR_PRIMITIVES: true
    mapper:
      accept-case-insensitive-properties: true
      accept-case-insensitive-values: true
```

Jackson 配置影响 REST API 的 JSON 解析。`FAIL_ON_NULL_FOR_PRIMITIVES: true` 让基本类型收到 `null` 时直接失败，避免 Kotlin/Java 基本类型出现隐式默认值导致数据不准确。大小写不敏感的属性和值则提高 API 入参兼容性。

```yaml
spring:
  config:
    import:
      - "optional:file:${komga.config-dir}/application.yml"
      - "optional:file:${komga.config-dir}/application.yaml"
      - "optional:file:${komga.config-dir}/application.properties"
```

这是很关键的外部配置入口。应用启动后，会尝试读取 `${komga.config-dir}` 目录下的三个配置文件。`optional:file:` 表示文件不存在也不报错。用户部署时常见做法就是在 `~/.komga/application.yml` 或容器挂载目录下提供覆盖配置。

```yaml
spring:
  http:
    codecs:
      max-in-memory-size: 10MB
```

这限制 WebFlux 或相关 HTTP codec 在内存中缓存的最大数据量，避免某些请求或响应体无限占用内存。

第五块是服务端配置：

```yaml
server:
  servlet.session.timeout: 7d
  forward-headers-strategy: framework
  shutdown: graceful
  error:
    include-message: always
  port: 25600
```

Komga 默认监听 `25600` 端口。Session 超时是 7 天。`forward-headers-strategy: framework` 让应用理解反向代理传来的 `X-Forwarded-*` 等头部，对部署在 Nginx、Traefik、Caddy 等代理后面很重要。`shutdown: graceful` 表示优雅关闭，应用停止时会尽量让进行中的请求完成。错误响应包含 message，便于 API 客户端或前端显示具体错误。

第六块是 Actuator 管理端点：

```yaml
management:
  endpoints.web.exposure.include: "*"
  endpoint:
    configprops:
      roles: ADMIN
      show-values: when_authorized
    env:
      roles: ADMIN
      show-values: when_authorized
    health:
      roles: ADMIN
      show-details: when_authorized
    shutdown:
      access: unrestricted
```

这里暴露所有 Web 管理端点，但对敏感信息展示加了角色约束。`configprops`、`env`、`health` 只有授权用户才能看到具体值或细节。`SecurityConfiguration.kt` 中有注释提到 health 端点会受 `management.endpoint.health.show-details` 影响，因此这里和安全配置是联动的。

`shutdown.access: unrestricted` 表示 shutdown 端点访问策略在 Actuator 层面不限制，但实际是否能调用还要结合 Spring Security 配置判断。不要只看这一行就认为任何外部请求都能关闭服务，需要继续看安全链。

第七块是 Springdoc / OpenAPI 配置：

```yaml
springdoc:
  swagger-ui:
    disable-swagger-default-url: true
  paths-to-match: "/api/**"
  writer-with-order-by-keys: true
```

它限制 OpenAPI 文档只匹配 `/api/**` 路径，并让输出 key 有序。`OpenApiConfiguration.kt` 会进一步定制 OpenAPI 信息，并读取 `application.version`。`disable-swagger-default-url` 用于避免 Swagger UI 默认加载示例地址。

## 上下游关系

上游主要有四类。

第一类是构建系统。`application.version: ${version}` 依赖构建时提供版本号。源文件中对其他 `${...}` 的转义也说明它要兼顾构建期资源处理和运行期 Spring 占位符解析。

第二类是 Spring Boot 配置加载机制。`application.yml` 会被 Spring Boot 自动加载；`spring.config.import` 又把外部配置纳入配置链。profile 文件会覆盖默认配置，例如 `application-dev.yml` 把端口改成 `8080`，把数据库改成内存 SQLite，把 `komga.config-dir` 改到 `${rootDir}/config-dir`；`application-localdb.yml` 引入 `komga.workspace`，把数据库、Lucene、任务库按 workspace 分目录；`application-docker.yml` 只覆盖 `komga.kobo.kepubify-path` 为 `/usr/bin/kepubify`。

第三类是系统环境。默认 `komga.config-dir` 使用 `${user.home}/.komga`，所以运行用户不同，默认数据目录也不同。部署环境也可以通过外部配置文件、环境变量或命令行参数覆盖这些值。

第四类是 Spring Boot / Actuator / Springdoc / Jackson / Flyway 等框架默认机制。文件中的很多键不是 Komga 自己发明的，而是这些框架的标准配置项。

下游主要是应用基础设施代码。

`KomgaProperties.kt` 是 `komga.*` 的主要绑定入口。`DataSourcesConfiguration.kt` 读取数据库路径并创建主库和任务库数据源。根据搜索结果，`FlywaySecondaryMigrationInitializer.kt` 与 `TasksDao.kt` 相关，说明任务数据库可能有独立迁移初始化流程。`ConfigurationChecker.kt` 会检查数据库路径是否在本地文件系统，并提示类似 `komga.tasks-db.check-local-filesystem: false` 的绕过开关。

`LuceneConfiguration.kt` 读取 `komga.lucene.data-directory`，用 `FSDirectory.open(Paths.get(...), SingleInstanceLockFactory())` 打开磁盘索引目录。`SearchIndexLifecycle.kt`、`LuceneHelper.kt`、各类 DAO 会进一步使用 Lucene 做全文搜索，例如书籍、系列、集合、阅读列表搜索。

`OpenApiConfiguration.kt` 读取 `application.version` 并定制 API 文档。`SecurityConfiguration.kt` 与 management health 细节显示联动。`CorsConfiguration.kt`、`KomgaOAuth2UserServiceConfiguration.kt`、`KoboController.kt` 等读取 `KomgaProperties` 中的其他配置字段，虽然这些字段未必都在本文件里显式列出，可能由类默认值或外部配置提供。

## 运行/调用流程

应用启动时，Spring Boot 首先加载 classpath 下的 `application.yml`。此时默认端口是 `25600`，默认配置目录是 `${user.home}/.komga`，默认主数据库和任务数据库都位于该目录下。

随后 Spring 解析 profile。如果启用了 `dev`、`docker`、`localdb` 等 profile，对应的 `application-*.yml` 会参与合并。比如开发环境可能改用内存数据库和 `8080` 端口；Docker profile 会设置 Kobo 相关外部工具路径；localdb profile 会让数据库文件名带上 workspace。

接着 `spring.config.import` 尝试读取外部配置文件：`${komga.config-dir}/application.yml`、`${komga.config-dir}/application.yaml`、`${komga.config-dir}/application.properties`。这些文件是 optional，所以首次启动没有它们也不会失败。用户在这里写的配置可以覆盖默认值。

配置合并完成后，Spring 会把 `komga.*` 绑定到 `KomgaProperties`。这个对象被注入到多个配置类和控制器中。数据库配置类使用其中的 `database.file` 和 `tasksDb.file` 创建 SQLite 数据源；Lucene 配置类使用 `lucene.dataDirectory` 打开索引目录；字体、Kobo、CORS、OAuth2 等功能也从同一个配置对象读取各自开关。

然后 Flyway 开始执行数据库迁移。迁移脚本位置是 `classpath:db/migration/{vendor}`，其中 `{vendor}` 会根据数据库类型解析。迁移脚本还能读取 `spring.flyway.placeholders` 里的值，从而在迁移阶段根据 `komga.file-hashing`、`komga.libraries-scan-startup` 等配置决定初始化行为。

Web 服务启动后，Servlet session 默认 7 天过期，异步 MVC 请求最多等待 1 小时，服务监听 `25600` 端口。前端或 API 请求进入 Spring MVC / Security / Controller 链路；API 文档只收集 `/api/**`；Actuator 管理端点全部暴露，但敏感值和健康详情依赖 ADMIN 权限与安全配置。

关闭应用时，`server.shutdown: graceful` 让 Spring Boot 走优雅停机流程。日志则写入 `${komga.config-dir}/logs/komga.log`，并按 rolling policy 清理历史文件。

## 小白阅读顺序

第一步，先把这个文件当成“默认配置清单”读，不要急着找函数调用。重点看三类键：`komga.*` 是 Komga 自己的配置；`spring.*` 是 Spring Boot 生态配置；`server.*`、`management.*`、`springdoc.*` 是 Web 服务、管理端点和 API 文档配置。

第二步，先理解 `komga.config-dir`。这个值是很多路径的根：数据库、任务库、Lucene、字体、日志都默认挂在它下面。只要理解它，文件里一半路径配置就串起来了。

第三步，看相邻 profile 文件：`komga/src/main/resources/application-dev.yml`、`komga/src/main/resources/application-docker.yml`、`komga/src/main/resources/application-localdb.yml`。它们展示了“默认配置如何被场景覆盖”。尤其是 `application-dev.yml`，能看到开发环境端口、数据库和日志级别都与默认环境不同。

第四步，去看 `org.gotson.komga.infrastructure.configuration.KomgaProperties`。这是从 YAML 到 Kotlin 对象的桥。看它能知道 `komga.*` 下还支持哪些字段，以及字段默认值、类型、初始化逻辑是什么。

第五步，再看几个消费方：`DataSourcesConfiguration.kt` 理解数据库路径如何变成数据源；`LuceneConfiguration.kt` 理解搜索索引目录如何被使用；`OpenApiConfiguration.kt` 理解 `application.version` 和 `springdoc.*` 如何影响 API 文档；`SecurityConfiguration.kt` 理解 Actuator 端点暴露后如何被安全策略兜住。

第六步，如果要研究启动过程，再顺着 Flyway 看数据库迁移目录 `db/migration/{vendor}`。本文件里的 `spring.flyway.placeholders` 不是给普通业务代码用的，而是给迁移脚本用的，这一点容易忽略。

## 常见误区

误区一：以为 `application.yml` 里的值就是最终运行值。实际 Spring Boot 会叠加 profile、环境变量、命令行参数和 `spring.config.import` 引入的外部文件。线上部署时最终值经常不等于这里的默认值。

误区二：看到 `\${komga.config-dir}` 就以为路径里真的有反斜杠。根据当前片段推断，这里的反斜杠主要是源码层面对构建期变量替换的转义，目的是让 Spring 在运行期解析 `${komga.config-dir}`。实际运行路径应按 Spring placeholder 解析后的结果理解。

误区三：把 `komga.database.file` 和 `komga.tasks-db.file` 当成同一个数据库。它们是两个不同配置项，默认分别指向 `database.sqlite` 和 `tasks.sqlite`。从 `DataSourcesConfiguration.kt`、`FlywaySecondaryMigrationInitializer.kt`、`TasksDao.kt` 的命名看，任务相关数据源有独立处理。

误区四：认为 `management.endpoints.web.exposure.include: "*"` 等于所有管理信息无保护。这个配置只说明 Actuator 端点在 Web 层暴露；具体能看到多少值，还受 `roles: ADMIN`、`show-values: when_authorized`、`show-details: when_authorized` 和 Spring Security 配置共同约束。

误区五：忽略 `spring.config.import`。这是用户配置覆盖默认配置的关键入口。很多“为什么我改了外部 application.yml 生效了”的答案就在这里。

误区六：把 `spring.flyway.placeholders` 当成普通运行时 feature flag。它们主要在数据库迁移阶段使用，影响迁移脚本行为；业务代码是否也读取同名 `komga.*` 配置，需要继续看对应 Kotlin 代码，不能只凭这里判断。

误区七：只看默认端口 `25600`，忽略 profile。开发配置 `application-dev.yml` 会把端口改成 `8080`，所以本地开发、测试、Docker、正式部署看到的端口可能不同。
