# 技术栈和运行环境

本文从仓库中的构建配置、开发文档和入口文件解释 Komga 的技术栈。最重要的事实是：这是一个 Kotlin/Spring Boot 后端、Vue 2 前端、Compose Desktop 托盘包装、SQLite 本地数据库、jOOQ/Flyway 持久化、Lucene 搜索的多项目仓库。`DEVELOPING.md` 给出运行要求：Java JDK 21+，Node.js 18+，并提示 Node 版本可查看 `.nvmrc`。同时，`komga/build.gradle.kts` 将 Kotlin 编译目标和 Java 编译目标设为 JVM 17；这说明开发环境要求使用 JDK 21+，但产物字节码目标是 17。这个差异应以开发文档和 Gradle 配置共同理解。

## 构建和包管理信号

根目录 `build.gradle.kts` 声明 Kotlin `2.2.0`、`org.jlleitschuh.gradle.ktlint`、`com.github.ben-manes.versions`、`org.jreleaser`，并配置 Gradle wrapper 版本 `8.14.3`。根目录 `settings.gradle` 只包含 `komga` 和 `komga-tray` 两个 Gradle 子项目。根目录 `gradle/libs.versions.toml` 固定了 Spring Boot `3.5.14`、SQLite JDBC `3.50.2.0`、Lucene `9.9.1`、jOOQ `3.19.32` 等版本。JReleaser 配置里有 single jar 分发和 Docker 镜像打包，Docker 模板目录是 `komga/docker`。

后端模块 `komga/build.gradle.kts` 使用 `org.springframework.boot`、`kotlin("plugin.spring")`、`kotlin("kapt")`、`nu.studer.jooq`、`org.flywaydb.flyway`、`org.springdoc.openapi-gradle-plugin`、KSP、Jacoco。依赖包括 `spring-boot-starter-web`、`webflux`、`validation`、`actuator`、`security`、`oauth2-client`、`thymeleaf`、`jooq`、`spring-session-core`、Caffeine session、Spring Data Commons、Flyway、springdoc-openapi、Jackson Kotlin/XML、Lucene、ICU4J、Tika、commons-compress、junrar、nightcompress、PDFBox、jsoup、Thumbnailator、TwelveMonkeys、NightMonkeys、ZXing、SQLite JDBC、Caffeine、ArchUnit 和 MockK 等。由此可见，后端同时承担 HTTP API、静态资源托管、认证授权、数据库访问、文件解析、图片处理、搜索索引和后台任务。

前端模块 `komga-webui/package.json` 是 Vue CLI 项目。脚本包括 `serve`、`build`、`test:unit`、`lint`，其中 `serve` 固定使用 `vue-cli-service serve --port 8081`。依赖显示它使用 Vue 2.6、Vue Router 3、Vuex 3、Vuetify 2、Axios、vue-i18n、Vuelidate、Chart.js、date-fns、lodash、marked、screenfull、R2D2BC 阅读器 fork 等。TypeScript 版本为 4.9，单元测试使用 Jest 与 Vue Test Utils。后端 Gradle 的 `npmInstall`、`npmBuild`、`copyWebDist`、`prepareThymeLeaf` 任务负责调用 npm 构建并把 dist 复制到 Spring Boot 的 `resources/public`。

托盘模块 `komga-tray/build.gradle.kts` 使用 Kotlin、Spring 插件、JetBrains Compose `1.8.2`、Kotlin Compose plugin `2.2.0`、Hydraulic Conveyor 和 application 插件。它依赖 `project(":komga")`，并按平台声明 Compose Desktop 运行时。`application.mainClass` 指向 `org.gotson.komga.DesktopApplicationKt`。这说明桌面版不是重写服务端，而是把同一个 Spring Boot 应用嵌入桌面启动器，加系统托盘菜单和打包能力。

## 运行配置和 Spring profiles

默认后端配置在 `komga/src/main/resources/application.yml`。它设置 `server.port: 25600`，默认 `komga.config-dir` 为 `${user.home}/.komga`，主数据库文件为 `${komga.config-dir}/database.sqlite`，任务数据库为 `${komga.config-dir}/tasks.sqlite`，Lucene 目录为 `${komga.config-dir}/lucene`，字体目录为 `${komga.config-dir}/fonts`。Spring 配置还导入配置目录下可选的 `application.yml`、`application.yaml`、`application.properties`，这意味着用户或部署环境可以用外部配置覆盖默认值。Flyway 默认启用，迁移位置是 `classpath:db/migration/{vendor}`，并带有 library scan、hashing、删除空 collection/read list 等 placeholders。

`DEVELOPING.md` 说明项目大量使用 Spring Profiles。`dev` profile 会增加日志、禁用周期扫描、使用内存数据库，并允许来自 `localhost:8081` 的前端开发服务器 CORS；`localdb` 把数据库放到 `./localdb`；`noclaim` 在没有用户时创建初始用户，dev 下创建 `admin@example.org/admin` 和 `user@example.org/user`，非 dev 下创建随机密码管理员。源码中 `application-dev.yml` 与这个描述匹配：数据库和 tasks-db 使用内存模式，允许 `[URL已移除] `8080`。`application-localdb.yml` 则把 workspace 设置为 `localdb` 并改变数据库、Lucene、任务数据库路径。`application-docker.yml` 配置 `kobo.kepubify-path` 为 `/usr/bin/kepubify`。

## 数据库、迁移和查询

Komga 使用 SQLite。`DataSourcesConfiguration.kt` 创建主库读写数据源、主库只读数据源、任务库读写数据源、任务库只读数据源，底层是 SQLite JDBC、HikariCP 和自定义 `SqliteUdfDataSource`。如果数据库是内存库，pool size 固定为 1；如果开启 WAL，则可能拆分读写池，写池仍限制为 1。`FlywaySecondaryMigrationInitializer.kt` 说明 Spring Boot 默认只迁移 primary datasource，所以任务数据库需要手工执行 `classpath:tasks/migration/sqlite`。`komga/src/flyway/resources/db/migration/sqlite` 保存主数据库 SQL 迁移，`komga/src/flyway/kotlin/db/migration/sqlite` 保存 Kotlin 迁移，`komga/src/flyway/resources/tasks/migration/sqlite/V20231013114850__tasks.sql` 保存任务表迁移。

jOOQ 是主要查询层。`komga/build.gradle.kts` 配置 `jooqGenerator("org.xerial:sqlite-jdbc...")` 和多组 Flyway/jOOQ 任务；`infrastructure/jooq/main` 下有 `BookDao.kt`、`SeriesDao.kt`、`LibraryDao.kt`、`KomgaUserDao.kt`、`ReadProgressDao.kt`、`PageHashDao.kt`、`ServerSettingsDao.kt` 等。`domain/persistence` 下是仓储接口，`infrastructure/jooq/main` 是实现。读源码时要注意，复杂搜索并不一定在控制器中拼 SQL，而可能通过 `SearchCondition`、`SearchContext`、`BookSearchHelper`、`SeriesSearchHelper` 和 DAO 组合出来。

## Web、认证和实时通信

Web 层使用 Spring MVC。`SecurityConfiguration.kt` 启用 Spring Security 和 method security，定义多个 `SecurityFilterChain`：普通 `/api/**`、`/opds/**`、`/sse/**`、OAuth2 和 actuator 相关端点走一个链；`/kobo/**` 使用 Kobo API key 认证；`/koreader/**` 使用 KOReader 相关 header 认证。普通 REST API 支持 HTTP Basic、remember-me、session、API key header `X-API-Key`，健康端点允许匿名，其他 actuator 端点要求 ADMIN。`WebMvcConfiguration.kt` 设置静态资源、Swagger UI 资源、前端 assets 缓存、API/OPDS cache header 和自定义参数解析器。

实时通信使用 Spring MVC 的 `SseEmitter`。`SseController.kt` 暴露 `sse/v1/events`，对已连接用户推送 domain event 和任务队列计数。前端 `komga-sse.plugin.ts` 注册 Vuex 模块保存任务计数，并创建 `KomgaSseService`。这套设计让 UI 可以在后台扫描、分析、缩略图生成或元数据更新时收到变化。

## 读源码前需要知道的概念

第一，Komga 的“任务”不是普通线程随手启动，而是以 `Task` 类型保存到 `TasksRepository`，由 `TaskProcessor` 根据 `KomgaSettingsProvider.taskPoolSize` 的线程池并发处理，再由 `TaskHandler` 分派到具体服务。第二，领域事件 `DomainEvent` 是跨边界通知的重要机制，SSE、缩略图变化、阅读进度变化等都依赖它。第三，前端并不直接访问文件系统，它通过 `src/services` 调后端 REST API，后端再由 `FileSystemController`、`LibraryController` 或任务系统操作服务器文件。第四，Komga 同时有 Web UI REST API、OPDS、Kobo Sync、KOReader Sync，接口包各自隔离；共享逻辑要去 domain 或 infrastructure 查。第五，默认部署形态是后端服务前端静态资源，开发形态可以用前端 8081 加后端 dev profile 分开跑。
