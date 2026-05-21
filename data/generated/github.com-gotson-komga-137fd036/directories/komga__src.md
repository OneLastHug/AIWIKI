# 目录：komga/src

## 它负责什么

`komga/src` 是整个 Komga 服务的源码与配套资源目录，承载了应用启动、运行时配置、数据库迁移、测试代码和基准测试代码。  
从当前片段看，它不是一个单纯的业务代码目录，而是一个完整的 Spring Boot 应用源码树：`main` 负责线上运行，`flyway` 负责数据库演进，`test` 负责验证，`benchmark` 负责性能基准。

## 关键组成

- `komga/src/main/kotlin/org/gotson/komga/Application.kt`：应用入口。`@SpringBootApplication` 负责装配 Spring 容器，`@EnableScheduling` 打开定时任务，`main()` 里先执行 `checkTempDirectory()`，再设置 jOOQ 相关系统属性，最后调用 `runApplication<Application>()`。
- `komga/src/main/resources/application.yml`：默认运行配置，包含数据库文件位置、Lucene、字体目录、日志、Spring Flyway、Thymeleaf、HTTP 编解码、Actuator、Springdoc 等。
- `komga/src/main/resources/application-dev.yml`：开发环境覆盖配置，默认使用内存数据库，开发端口是 `8080`。
- `komga/src/main/resources/application-docker.yml`、`application-localdb.yml`：不同部署形态的补充配置。
- `komga/src/flyway/resources/db/migration/sqlite`、`komga/src/flyway/kotlin/db/migration/sqlite`：SQLite 数据库迁移脚本与 Kotlin migration。
- `komga/src/flyway/resources/tasks/migration/sqlite`：任务库 `tasks` 的迁移脚本。
- `komga/src/test/kotlin/...`：单元测试、架构约束测试、DAO 测试、控制器测试等。
- `komga/src/benchmark/kotlin/...`：JMH 基准测试，覆盖 REST 与核心流程。
- `komga/src/test/resources`、`komga/src/benchmark/resources`：测试样本、压缩包、OPF/EPUB 资源、测试专用配置。

## 上下游关系

这层目录的上游是 Gradle 构建脚本，尤其是 `komga/build.gradle.kts`。它定义了几个关键链路：

- `flywayMigrateMain`、`flywayMigrateTasks` 先把 SQLite 迁移跑起来。
- `generateJooq`、`generateTasksJooq` 依赖迁移结果，生成 `org.gotson.komga.jooq.main` 和 `org.gotson.komga.jooq.tasks`。
- `main` source set 依赖 `flyway` source set 的输出，也把生成的 jOOQ 代码接进来。
- `benchmark` source set 复用 `main` 的输出和 `testImplementation` 依赖。
- `src/main/resources/public/` 还会接收前端构建产物，说明后端同时托管 Web UI。

下游则是整个应用运行时：Spring Boot 启动后读取 `application.yml`，Flyway 建库，jOOQ 提供类型安全数据库访问，测试与基准测试验证这些层的行为。根据当前片段推断，真正的业务实现主要分布在更深的 `org/gotson/komga/...` 包下，而不仅是顶层入口文件。

## 运行/调用流程

1. JVM 进入 `komga/src/main/kotlin/org/gotson/komga/Application.kt` 的 `main()`。
2. 先执行 `checkTempDirectory()`，确保临时目录可用。
3. 设置 `org.jooq.no-logo` 和 `org.jooq.no-tips`，避免启动时打印干扰信息。
4. `runApplication<Application>()` 启动 Spring 容器。
5. Spring 读取 `application.yml`，再叠加环境文件和用户自定义配置。
6. Flyway 根据 `src/flyway` 下的脚本完成数据库迁移。
7. jOOQ 生成或加载数据库访问类，供业务代码使用。
8. `@EnableScheduling` 让定时任务随容器一起生效。

## 小白阅读顺序

1. 先看 `komga/src/main/kotlin/org/gotson/komga/Application.kt`，抓住启动入口。
2. 再看 `komga/src/main/resources/application.yml` 和 `application-dev.yml`，理解默认配置和开发覆盖。
3. 接着回到 `komga/build.gradle.kts`，把 `flyway`、jOOQ、`benchmark`、Web UI 这些构建链路串起来。
4. 然后抽读 `komga/src/flyway/resources/db/migration/sqlite/V20200706141854__initial_migration.sql` 这类早期迁移，理解表结构如何起步。
5. 最后看 `komga/src/test/kotlin/org/gotson/komga/architecture/*` 和一个控制器测试，补齐分层与约束。

## 常见误区

- 误以为 `src/main/kotlin` 只有一个启动类就说明项目很简单。实际上，核心业务大概率在更深层包里，当前只是顶层入口可见。
- 误把 `flyway` 当作普通测试资源。它是构建链路的一部分，会直接影响数据库结构和 jOOQ 生成结果。
- 误忽略 `main/resources/application.yml` 的作用。这里不仅是日志和端口配置，还决定了数据库文件、Lucene、Thymeleaf、Actuator 等关键行为。
- 误把 `dev` 配置当作生产默认值。`application-dev.yml` 里端口是 `8080`，而默认 `application.yml` 里是 `25600`。
- 误以为测试资源只放断言数据。这里还包含大量压缩包、EPUB、RAR、ZIP 样本，明显是为解析器与导入流程准备的。
