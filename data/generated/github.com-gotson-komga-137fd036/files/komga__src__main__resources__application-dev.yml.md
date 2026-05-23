# 文件：komga/src/main/resources/application-dev.yml

## 它负责什么

`komga/src/main/resources/application-dev.yml` 是 Komga 后端的 Spring Boot 开发环境配置文件，对应 `dev` profile。它不是完整配置，而是在默认 `application.yml` 的基础上做开发期覆盖：把数据库切到内存 SQLite、开放本地前端调试所需的 CORS 来源、提高应用日志级别、禁用 OpenAPI 文档缓存，并把服务端口改为 `8080`。

从配置意图看，这个文件主要服务本地开发和调试，而不是生产部署。默认 `application.yml` 中的生产式配置会把主数据库放到 `${komga.config-dir}/database.sqlite`，任务数据库放到 `${komga.config-dir}/tasks.sqlite`，默认端口是 `25600`；而 `application-dev.yml` 将这些改成更适合反复启动、快速验证的形式。

核心作用可以概括为四点：

1. 让开发环境使用内存数据库，避免污染本地真实数据。
2. 允许本地前端开发服务器访问后端 API。
3. 打开更详细的 Komga 自身日志，方便定位问题。
4. 让 API 文档和服务端口更适合开发调试。

## 关键组成

第一组是 `komga` 自定义配置：

```yaml
komga:
  database:
    file: "file:database?mode=memory"
  tasks-db:
    file: "file:tasks?mode=memory"
```

这里覆盖了默认主数据库和任务数据库路径。默认配置中，`komga.database.file` 指向 `${komga.config-dir}/database.sqlite`，`komga.tasks-db.file` 指向 `${komga.config-dir}/tasks.sqlite`。dev 配置改为 `file:database?mode=memory` 和 `file:tasks?mode=memory`，根据当前片段推断，这是给 SQLite JDBC 使用的内存数据库 URI。这样每次启动开发环境时，数据不会长期保存在磁盘上。

```yaml
  cors.allowed-origins:
    - [URL已移除]
    - [URL已移除]
    - [URL已移除]
```

这是开发期 CORS 白名单。代码中 `komga.cors.allowed-origins` 会被 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/CorsConfiguration.kt` 读取，并绑定为允许跨域访问的 origin 列表。`localhost:8081` 和 `localhost:3000` 通常对应前端开发服务器或本地调试入口，`[URL已移除] 则允许官网域名访问相关接口。

```yaml
  oauth2-account-creation: false
```

这个配置控制 OAuth2 登录时是否允许自动创建账号。文件中明确关闭该能力。根据当前片段推断，它应当被安全或用户账号相关配置读取，用来避免开发环境中 OAuth2 登录自动生成用户造成状态不确定。

```yaml
  config-dir: ${rootDir}/config-dir
```

这会覆盖默认的 `${user.home}/.komga` 配置目录。默认配置里日志、数据库、Lucene、字体等路径都会依赖 `komga.config-dir`。dev 环境将它改到 `${rootDir}/config-dir`，通常是为了把开发运行产生的配置、日志或缓存放在项目根相关目录下。`rootDir` 在当前目标文件中没有定义，根据当前片段推断，它可能由 Gradle、IDE 启动参数或 Spring 运行环境注入。

第二组是日志配置：

```yaml
logging:
  level:
    org.apache.activemq.audit.message: WARN
    org.gotson.komga: DEBUG
```

`org.gotson.komga: DEBUG` 会把 Komga 自身包的日志提升到 DEBUG，便于观察业务逻辑、扫描、数据库访问或 API 行为。`org.apache.activemq.audit.message: WARN` 则压低 ActiveMQ audit message 日志，避免开发输出被消息审计日志刷屏。

下面的大量注释项是开发者临时排障开关，例如：

```yaml
#    org.jooq: DEBUG
#    com.zaxxer.hikari: DEBUG
#    org.springframework.security.web.FilterChainProxy: DEBUG
#    org.springframework.boot.context.config.ConfigDataEnvironment: TRACE
```

这些没有生效，但给开发者保留了常见调试方向：SQL/jOOQ、连接池、Spring Security 过滤链、Spring 配置加载过程等。

```yaml
  logback:
    rollingpolicy:
      max-history: 1
```

默认 `application.yml` 中日志滚动保留 `max-history: 7`，dev 环境改成 `1`，减少本地日志历史文件占用。

第三组是 `springdoc`：

```yaml
springdoc:
  cache:
    disabled: true
```

这会禁用 springdoc 缓存。对开发来说，接口、DTO、注解频繁变化，如果 OpenAPI 文档缓存不刷新，Swagger UI 或生成的 API 描述可能滞后。禁用缓存能让文档更及时反映代码变化。项目中存在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/openapi/OpenApiConfiguration.kt`，说明 OpenAPI 配置是应用的一部分；默认 `application.yml` 还配置了 `springdoc.paths-to-match: "/api/**"`、`springdoc.writer-with-order-by-keys: true` 等文档行为。

第四组是服务端口：

```yaml
server:
  port: 8080
#  servlet:
#    context-path: /komga
```

默认端口是 `25600`，dev profile 改成常见的 `8080`。注释掉的 `server.servlet.context-path: /komga` 是一个备用调试项，如果打开，应用路径会挂到 `/komga` 前缀下，例如 API 路径可能从 `/api/...` 变为 `/komga/api/...`。

## 上下游关系

上游主要是 Spring Boot 配置加载机制。应用启动时会先加载 `application.yml`，再根据激活的 profile 叠加 `application-dev.yml`。如果启动参数、环境变量或 IDE 配置中设置了 `spring.profiles.active=dev`，这个文件才会参与最终配置合并。

`application-dev.yml` 与同目录配置的关系如下：

- `komga/src/main/resources/application.yml`：基础配置，定义默认数据库路径、日志策略、Spring MVC/Jackson/Flyway、管理端点、默认端口、springdoc 基础行为等。
- `komga/src/main/resources/application-dev.yml`：开发环境覆盖配置，重点覆盖数据库、CORS、日志、springdoc 缓存和端口。
- `komga/src/main/resources/application-localdb.yml`：另一个本地数据库 profile，使用 `${komga.workspace}` 区分本地 SQLite 文件和 Lucene 目录，更适合保留本地开发数据。
- `komga/src/main/resources/application-docker.yml`：Docker 环境补充配置，目前只配置 `komga.kobo.kepubify-path: /usr/bin/kepubify`。

下游主要包括以下模块：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaProperties.kt`：使用 `@ConfigurationProperties(prefix = "komga")` 绑定 `komga.*` 配置。`komga.database.file`、`komga.tasks-db.file`、`komga.config-dir` 等会进入这个属性类，供数据源、目录初始化和其他基础设施使用。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/ConfigurationChecker.kt`：会检查 `komgaProperties.database` 和 `komgaProperties.tasksDb`，确认数据库配置是否符合本地文件系统要求。dev 使用内存数据库时，这里的检查逻辑需要能识别或放行对应 URI；具体细节需继续阅读该文件。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/CorsConfiguration.kt`：读取并绑定 `komga.cors.allowed-origins`，决定哪些前端 origin 能跨域访问后端。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/openapi/OpenApiConfiguration.kt`：负责 OpenAPI 相关配置，受到 `springdoc.*` 和 active profiles 影响。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/InitialUserController.kt`：搜索结果显示里面存在 `@Profile("dev")` 和 `@Profile("!dev")`，说明 dev profile 还会影响初始用户相关行为。也就是说，激活 dev 不只是加载这个 YAML，还会改变部分 Bean 的启用条件。

需要注意，`application-dev.yml` 本身没有 import/export 语法。它的“导入”关系来自 Spring Boot 的 profile 配置合并；它的“导出”效果则体现为运行时 Environment 中的一组 property，被 `@ConfigurationProperties`、`@Value`、自动配置和条件注解消费。

## 运行/调用流程

典型运行流程如下：

1. 开发者用 Gradle、IDE 或命令行启动 Komga 后端，并激活 `dev` profile，例如通过 `spring.profiles.active=dev`。
2. Spring Boot 先读取 `application.yml`，建立默认配置：端口 `25600`、配置目录 `${user.home}/.komga`、磁盘 SQLite 数据库、日志滚动策略、Flyway、Jackson、springdoc 等。
3. Spring Boot 发现 `dev` profile 后，继续加载 `application-dev.yml`，用其中的值覆盖或追加默认配置。
4. `komga.database.file` 被覆盖为 `file:database?mode=memory`，`komga.tasks-db.file` 被覆盖为 `file:tasks?mode=memory`。
5. `KomgaProperties` 绑定最终的 `komga.*` 配置，数据源配置再使用这些属性创建主数据库和任务数据库连接。
6. Flyway 根据默认 `application.yml` 中的配置继续启用，并对当前数据库执行迁移。因为 dev 数据库是内存库，所以通常每次启动都需要重新建表和迁移。
7. Spring Security/CORS 配置读取 `komga.cors.allowed-origins`，允许本地前端 origin 调用后端。
8. OpenAPI/springdoc 使用禁用缓存后的配置生成 API 文档，便于开发期间即时查看接口变化。
9. 嵌入式 Web 服务器使用 `server.port: 8080` 启动，而不是默认的 `25600`。
10. 因为 active profile 包含 `dev`，被 `@Profile("dev")` 标记的 Bean 会启用，被 `@Profile("!dev")` 限制的替代实现会停用或反向启用。

从调用方向看，业务代码通常不会直接“调用”这个 YAML 文件；它们读取的是 Spring Environment 中已经合并完成的配置值。因此阅读这个文件时，要把它理解成“运行时参数覆盖层”，而不是普通代码模块。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先读 `komga/src/main/resources/application.yml`，了解默认配置是什么。尤其关注 `komga.database.file`、`komga.tasks-db.file`、`komga.config-dir`、`server.port`、`springdoc.*` 和 `logging.*`。
2. 再读 `komga/src/main/resources/application-dev.yml`，逐项对比它覆盖了哪些默认值。重点看数据库从磁盘变内存、端口从 `25600` 变 `8080`、日志从默认级别变 DEBUG。
3. 接着读 `komga/src/main/resources/application-localdb.yml`，理解它和 dev 的区别：`localdb` 更像“保留本地数据的开发环境”，而 `dev` 更像“每次干净启动的开发环境”。
4. 再看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaProperties.kt`，确认 `komga.*` 配置如何绑定到 Kotlin 对象。
5. 然后看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/security/CorsConfiguration.kt`，理解 `komga.cors.allowed-origins` 如何影响浏览器跨域请求。
6. 最后看 `komga/src/main/kotlin/org/gotson/komga/interfaces/scheduler/InitialUserController.kt` 和 `komga/src/main/kotlin/org/gotson/komga/infrastructure/openapi/OpenApiConfiguration.kt`，理解 active profile 对 Bean 和 OpenAPI 行为的额外影响。

如果只想快速把应用跑起来，优先理解三件事即可：`server.port: 8080` 决定访问端口，`komga.database.file` 决定数据是否持久化，`cors.allowed-origins` 决定本地前端能否调用后端。

## 常见误区

第一个误区是把 `application-dev.yml` 当成生产配置。这个文件使用内存数据库，数据通常不会持久保存；如果用它保存真实书库、用户、阅读进度，重启后可能丢失。生产或长期本地使用应优先看默认配置或 `application-localdb.yml`。

第二个误区是以为 `server.port: 8080` 是 Komga 永远的默认端口。实际默认端口在 `application.yml` 中是 `25600`，只有激活 `dev` profile 后才会被覆盖为 `8080`。

第三个误区是认为注释掉的日志配置已经生效。比如 `org.jooq: DEBUG`、`com.zaxxer.hikari: DEBUG`、`FilterChainProxy: DEBUG` 都只是保留的调试开关，前面有 `#` 时不会生效。需要排查 SQL、连接池或安全过滤链时，才临时取消对应注释。

第四个误区是忽略 `config-dir` 的连锁影响。`komga.config-dir` 不只影响一个目录，默认配置里日志文件、数据库、Lucene、字体目录等都会间接依赖它。dev 配置把它改成 `${rootDir}/config-dir`，意味着相关运行产物可能集中到开发项目相关目录下。

第五个误区是只看 YAML，不看 active profile 影响。搜索结果显示项目中有 `@Profile("dev")` 和 `@Profile("!dev")`，所以启用 dev profile 不仅会改变配置值，还会改变某些 Bean 的启用条件。调试初始用户、认证或启动行为时，要同时检查相关 `@Profile` 注解。

第六个误区是把 CORS 当成后端 API 权限控制。`komga.cors.allowed-origins` 主要影响浏览器是否允许某些网页 origin 调用 API，它不是用户认证、授权或接口访问控制本身。即使某个 origin 被允许，具体 API 仍然应受到 Spring Security 和业务权限逻辑约束。
