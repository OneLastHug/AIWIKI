# 文件：komga/build.gradle.kts

## 它负责什么

`komga/build.gradle.kts` 是 Komga 主后端模块的 Gradle Kotlin DSL 构建脚本。它不直接实现业务逻辑，而是定义这个模块如何被编译、测试、打包、生成代码、迁移数据库 schema、整合前端资源，以及生成 OpenAPI 文档。

从内容看，`komga` 是一个 Kotlin + Spring Boot 后端应用模块，同时承担以下职责：

- 配置 Kotlin/JVM、Spring Boot、KAPT、KSP、JaCoCo、Flyway、jOOQ、OpenAPI、ktlint 等构建插件。
- 声明后端运行所需依赖，包括 Spring Web、WebFlux、Security、OAuth2、Thymeleaf、jOOQ、SQLite、Lucene、Tika、PDFBox、图片解码库、缓存、测试库等。
- 定义 JVM 17 编译目标和 Kotlin 编译参数。
- 定义测试、benchmark、资源处理、JAR manifest 等任务行为。
- 调用 `komga-webui` 的 npm 构建流程，把前端产物复制到后端 `src/main/resources/public/`。
- 用 Flyway 在构建期迁移 SQLite 数据库，再用 jOOQ 从迁移后的数据库生成 Kotlin/Java 可用的数据库访问代码。
- 配置 OpenAPI 生成输出到 `komga/docs`。
- 调整 ktlint、KAPT、Kotlin 编译任务与 jOOQ 生成任务之间的依赖顺序。

简单说，这个文件是 `komga` 模块的“构建中枢”：源码能不能编译、数据库访问代码怎么生成、前端资源怎么进入后端包、测试和文档怎么跑，大多由它协调。

## 关键组成

### 1. import 区域

文件顶部导入了几个 Gradle 任务和工具类：

- `nu.studer.gradle.jooq.JooqGenerate`：用于配置 jOOQ 代码生成任务，例如 `generateJooq`、`generateTasksJooq`。
- `org.apache.tools.ant.taskdefs.condition.Os`：用于判断当前系统是否是 Windows，从而选择 `npm` 或 `npm.cmd`。
- `org.flywaydb.gradle.task.FlywayMigrateTask`：用于注册自定义 Flyway 迁移任务。
- `org.jetbrains.kotlin.gradle.dsl.JvmTarget`：用于声明 Kotlin 编译目标为 JVM 17。
- `org.jetbrains.kotlin.util.prefixIfNot`：在处理前端 `index.html` 时给资源路径补 `/`。
- `org.springframework.boot.gradle.plugin.SpringBootPlugin`：用于引用 Spring Boot BOM 坐标。

这里没有传统意义上的 `export`。Gradle 构建脚本通过插件、任务、source set、configuration 等方式把配置暴露给 Gradle 构建生命周期。

### 2. plugins：构建能力入口

`plugins` 块启用了这个模块需要的构建能力：

- `kotlin("jvm")`：Kotlin JVM 编译。
- `kotlin("plugin.spring")`：让 Kotlin 更好地适配 Spring，例如处理 Spring 代理需要的 open class。
- `kotlin("kapt")`：Kotlin 注解处理，主要用于 Spring 配置处理器、JMH 等。
- `org.springframework.boot`：Spring Boot 打包、运行、build info 等能力。
- `gradleGitProperties`：根据 Git 信息生成构建属性。
- `nu.studer.jooq`：jOOQ 代码生成。
- `org.flywaydb.flyway`：数据库迁移。
- `com.github.johnrengelman.processes`：支持 forked Spring Boot run 等进程相关任务，后文 `forkedSpringBootRun` 会被排序。
- `org.springdoc.openapi-gradle-plugin`：生成 OpenAPI 文档。
- `com.google.devtools.ksp`：Kotlin Symbol Processing，这里在特定版本条件下用于 `bestbefore` 处理器。
- `jacoco`：测试覆盖率报告。

这些插件决定了后面可以出现 `springBoot {}`、`jooq {}`、`openApi {}`、`tasks.jacocoTestReport`、`ksp(...)`、`kapt(...)` 等 DSL。

### 3. benchmark source set

文件创建了一个额外的 source set：

```kotlin
sourceSets.create("benchmark")
```

它让 `src/benchmark` 成为单独的 benchmark 源码集合，并让它复用 `main` 的输出和运行时 classpath。

相关配置包括：

- `benchmarkImplementation` 继承 `testImplementation`。
- `kaptBenchmark` 继承 `kaptTest`。
- 注册 `benchmark` 测试任务，使用 `benchmarkSourceSet.output.classesDirs` 和 `benchmarkSourceSet.runtimeClasspath`。

这说明 benchmark 代码不是普通生产代码，也不是普通测试代码，而是一个独立构建入口，依赖主代码和测试相关工具。

### 4. dependencies：后端依赖全景

依赖块是这个文件最大的一部分，大致可以分成几类。

Kotlin 与 Spring 基础：

- `kotlin("stdlib")`
- `kotlin("reflect")`
- Spring Boot BOM：`api(platform(SpringBootPlugin.BOM_COORDINATES))`
- `spring-boot-starter-web`
- `spring-boot-starter-webflux`
- `spring-boot-starter-validation`
- `spring-boot-starter-actuator`
- `spring-boot-starter-security`
- `spring-boot-starter-oauth2-client`
- `spring-boot-starter-thymeleaf`
- `spring-boot-starter-jooq`
- `spring-session-core`
- `spring-session-caffeine`
- `spring-data-commons`

这表明后端是 Spring Boot Web 应用，既有 MVC/Web，也引入了 WebFlux，具备安全认证、OAuth2、Actuator、Thymeleaf、Session、jOOQ 等能力。

数据库与迁移：

- `org.flywaydb:flyway-core`
- `org.xerial:sqlite-jdbc`
- `jooqGenerator("org.xerial:sqlite-jdbc:...")`

核心数据库是 SQLite。Flyway 负责迁移，jOOQ 从迁移后的 SQLite 数据库反向生成类型安全访问代码。

搜索、文本、元数据与文件处理：

- Lucene：`lucene-core`、`lucene-analysis-common`、`lucene-queryparser`、`lucene-backward-codecs`
- ICU4J：`com.ibm.icu:icu4j`
- Tika：`org.apache.tika:tika-core`
- 压缩/归档：`commons-compress`、`junrar`、`nightcompress`
- PDF：`pdfbox`
- HTML：`jsoup`
- 文件工具：`commons-io`、`commons-lang3`、`commons-validator`

根据当前片段推断，Komga 需要扫描、解析、索引漫画/书籍相关文件，因此引入了大量文件格式、归档、文本处理和搜索依赖。

图片处理：

- `thumbnailator`
- TwelveMonkeys ImageIO：JPEG、TIFF、WebP
- NightMonkeys：JXL、HEIF、WebP
- JPEG2000：`jai-imageio-jpeg2000`
- JBIG2：`jbig2-imageio`

这些依赖让后端能读取和生成多种图片格式缩略图。对漫画/电子书服务器来说，这是核心基础能力。

其他业务基础设施：

- `kotlin-logging-jvm`
- `springdoc-openapi-starter-webmvc-ui`
- Jackson Kotlin/XML
- `zxing` 条码扫描
- `byteunits`
- `tsid-creator`
- `caffeine`

测试依赖：

- Spring Boot Test，但排除了 `mockito-core`
- `spring-security-test`
- `springmockk`
- `mockk`
- `jimfs`
- `archunit-junit5`

说明测试风格偏 Kotlin/MockK，并且用 ArchUnit 检查架构约束，用 Jimfs 模拟文件系统。

开发与注解处理：

- `kapt("spring-boot-configuration-processor")`
- `developmentOnly("spring-boot-devtools")`
- 如果项目版本以 `.0.0` 结尾，则启用 `bestbefore-processor-kotlin`

`bestbefore` 这段是条件式依赖，说明只有某类版本构建才需要额外 KSP 处理器。具体含义要结合项目中的注解使用点继续确认；根据当前片段推断，它可能用于提醒或处理弃用/过期代码策略。

### 5. kotlin 编译配置

```kotlin
kotlin {
  compilerOptions {
    jvmTarget = JvmTarget.JVM_17
    freeCompilerArgs = listOf(...)
  }
}
```

核心点：

- JVM 目标是 17。
- `-Xjsr305=strict`：严格处理 Java nullability 注解。
- `-Xemit-jvm-type-annotations`：输出 JVM 类型注解。
- `-opt-in=kotlin.time.ExperimentalTime`：允许使用 Kotlin 实验性时间 API。
- `-Xannotation-default-target=param-property`：调整注解默认目标。

这会影响整个模块 Kotlin 源码的编译语义。阅读业务代码时，如果看到 nullability、时间 API、注解目标相关行为，要知道这里已经做了全局配置。

### 6. tasks：构建任务编排

`tasks` 块里配置了多类任务。

Java 编译：

- 所有 `JavaCompile` 使用 Java 17。

测试：

- 所有 `Test` 使用 JUnit Platform。
- 设置 `spring.profiles.active=test`。
- 最大堆内存为 `1G`。

JAR：

- 所有 `Jar` manifest 添加 `Enable-Native-Access: ALL-UNNAMED`。
- 普通 `jar` 任务被显式启用。

前端构建链：

- `npmInstall`
- `npmBuild`
- `copyWebDist`
- `prepareThymeLeaf`

其中 `webui` 指向：

```kotlin
val webui = "$rootDir/komga-webui"
```

流程是：

1. `npmInstall` 在 `komga-webui` 下执行 `npm install`。
2. `npmBuild` 依赖 `npmInstall`，执行 `npm run build`。
3. `copyWebDist` 依赖 `npmBuild`，把 `komga-webui/dist/` 复制到 `komga/src/main/resources/public/`。
4. `prepareThymeLeaf` 再处理 `dist/index.html`，给 `src`、`content`、`href` 这类资源引用注入 Thymeleaf 的 `th:` 属性。

`prepareThymeLeaf` 里的核心逻辑是用正则匹配资源路径，然后生成类似 Thymeleaf `@{...}` 的表达式。这说明前端产物不是简单静态复制，还要适配 Spring Boot + Thymeleaf 的上下文路径或资源解析方式。

资源处理：

- `ProcessResources` 会对 `application*.yml` 执行 `expand(project.properties)`，把 Gradle 项目属性展开进配置文件。
- `ProcessResources` 被设置为 `mustRunAfter(prepareThymeLeaf)`，保证资源处理顺序不会早于前端/Thymeleaf 准备任务。

benchmark：

- 注册 `benchmark` 测试任务，绑定前面创建的 `benchmark` source set。

### 7. springBoot buildInfo

```kotlin
springBoot {
  buildInfo {
    excludes = setOf("time")
    properties {
      inputs.file("$rootDir/gradle.properties")
    }
  }
}
```

这里生成 Spring Boot build info，但排除了 `time` 字段。目的写在注释里：避免 `bootBuildInfo` 每次都因为时间变化而重新运行。

同时把 `gradle.properties` 作为输入，这样版本号或项目属性变化时，build info 仍然会正确更新。

### 8. Flyway 与 SQLite 迁移

文件定义了两个 SQLite URL：

- `main`：`build/generated/flyway/main/database.sqlite`
- `tasks`：`build/generated/flyway/tasks/tasks.sqlite`

对应迁移目录：

- `main`：
  - `komga/src/flyway/resources/db/migration/sqlite`
  - `komga/src/flyway/kotlin/db/migration/sqlite`
- `tasks`：
  - `komga/src/flyway/resources/tasks/migration/sqlite`

然后注册两个任务：

- `flywayMigrateMain`
- `flywayMigrateTasks`

它们都是 `FlywayMigrateTask`，构建期会创建临时 SQLite 数据库并执行迁移。

`flywayMigrateMain` 的特点：

- 使用 `classpath:db/migration/sqlite`
- 设置多个 placeholders：
  - `library-file-hashing`
  - `library-scan-startup`
  - `delete-empty-collections`
  - `delete-empty-read-lists`
- 依赖 `flywayClasses`
- `mixed = true`，允许 SQL 和 Java/Kotlin migration 混合。

`flywayMigrateTasks` 的特点：

- 使用 `classpath:tasks/migration/sqlite`
- 同样依赖 `flywayClasses`
- 同样开启 `mixed = true`

两个任务在 `doFirst` 中都会删除旧输出目录并重新创建，保证生成的数据库 schema 是干净的。

### 9. jOOQ 代码生成

`buildscript` 里强制 jOOQ 相关 classpath 依赖使用 `libs.versions.jooq.get()`，避免插件或传递依赖带来版本不一致。

`jooq` 块配置了两个生成目标：

- `main`
  - JDBC driver：`org.sqlite.JDBC`
  - URL：`sqliteUrls["main"]`
  - database：`org.jooq.meta.sqlite.SQLiteDatabase`
  - package：`org.gotson.komga.jooq.main`
- `tasks`
  - URL：`sqliteUrls["tasks"]`
  - package：`org.gotson.komga.jooq.tasks`

然后配置生成任务：

- `generateJooq` 依赖 `flywayMigrateMain`
- `generateTasksJooq` 依赖 `flywayMigrateTasks`

这条链路非常关键：jOOQ 不是直接读取手写实体类，而是先运行 Flyway，把迁移脚本应用到临时 SQLite 数据库，再从数据库 schema 生成代码。

### 10. sourceSets：flyway 与生成代码进入 main

文件后半段重新配置了 `sourceSets`：

- 创建 `flyway` source set。
- `flyway` 复用 `main` 的 compile/runtime classpath。
- `main` 的 Java 输出包含 `flyway.output`。
- `main` 增加源码目录 `build/generated-src/jooq/tasks`。

这表示 Flyway migration 代码需要参与构建；同时至少 `tasks` 这组 jOOQ 生成代码会进入主源码编译范围。

另外：

- `tasks.whenTaskAdded` 中，如果任务名是 `kaptGenerateStubsKotlin`，就让它依赖 `generateTasksJooq`。
- `runKtlintFormatOverMainSourceSet`、`runKtlintCheckOverMainSourceSet`、`compileKotlin` 都依赖 `generateTasksJooq`。

这说明项目中某些 Kotlin 源码或注解处理需要先看到 `org.gotson.komga.jooq.tasks` 生成代码，否则编译、KAPT 或 lint 可能找不到类型。

### 11. OpenAPI、JaCoCo、ktlint 与任务排序

OpenAPI：

```kotlin
openApi {
  outputDir = file("$projectDir/docs")
  customBootRun {
    args.add("--spring.profiles.active=claim,generate-openapi")
    args.add("--server.port=8080")
  }
}
```

生成 OpenAPI 时会启动 Spring Boot，并使用 `claim,generate-openapi` profiles，端口为 `8080`，输出到 `komga/docs`。

JaCoCo：

- `jacocoTestReport` 依赖 `test`，即生成覆盖率报告前会先跑测试。

ktlint：

- 排除 `**/db/migration/**`。
- 这通常是因为 migration 代码可能有特殊格式，或不希望被统一格式化影响历史迁移文件。

任务排序：

```kotlin
project.afterEvaluate {
  tasks.named("forkedSpringBootRun") {
    mustRunAfter(tasks.bootJar)
    mustRunAfter(tasks.jar)
  }
}
```

`forkedSpringBootRun` 必须在 `bootJar` 和 `jar` 之后运行。这通常是为了避免 OpenAPI 或 forked run 类任务与打包任务并发冲突。

## 上下游关系

上游输入主要来自这些位置：

- 根级版本和依赖目录：`gradle.properties`、版本 catalog 中的 `libs.versions.*`、`libs.plugins.*`。
- 后端源码：`komga/src/main/kotlin`。
- 后端资源：`komga/src/main/resources`。
- 测试源码和资源：`komga/src/test`。
- benchmark 源码：`komga/src/benchmark`。
- Flyway 迁移：`komga/src/flyway/resources/db/migration/sqlite`、`komga/src/flyway/kotlin/db/migration/sqlite`、`komga/src/flyway/resources/tasks/migration/sqlite`。
- 前端项目：`komga-webui`。
- 插件生态：Spring Boot、Flyway、jOOQ、OpenAPI、ktlint、KSP、KAPT 等 Gradle 插件。

下游产物主要包括：

- 编译后的 `komga` 后端 classes。
- Spring Boot 可运行包和普通 jar。
- `build/generated/flyway/main/database.sqlite` 与 `build/generated/flyway/tasks/tasks.sqlite`。
- jOOQ 生成源码，例如 `build/generated-src/jooq/tasks`。
- 复制进后端资源目录的前端静态文件：`komga/src/main/resources/public/`。
- 处理过的 Thymeleaf `index.html`。
- OpenAPI 文档输出：`komga/docs`。
- JaCoCo 测试覆盖率报告。
- benchmark 测试任务输出。

与其他模块的关系方面，仓库中还存在根级 `build.gradle.kts`、`settings.gradle`、`gradle.properties` 和另一个模块构建文件 `komga-tray/build.gradle.kts`。由于当前任务只读取了目标文件和有限上下文，模块包含关系只能根据当前片段推断：`komga` 是主服务端模块，`komga-tray` 可能是桌面托盘/客户端辅助模块，`komga-webui` 是被主后端构建流程消费的前端模块。

## 运行/调用流程

可以把这个构建脚本理解成几条主要流水线。

第一条是普通后端编译流水线：

1. Gradle 读取根构建配置和 `komga/build.gradle.kts`。
2. 应用 Kotlin、Spring Boot、KAPT、KSP、jOOQ、Flyway 等插件。
3. 解析 dependencies。
4. 执行 jOOQ 相关前置任务，特别是 `generateTasksJooq`。
5. `generateTasksJooq` 先触发 `flywayMigrateTasks`。
6. `flywayMigrateTasks` 运行 Flyway，把 tasks migration 应用到临时 SQLite 数据库。
7. jOOQ 从该 SQLite schema 生成 `org.gotson.komga.jooq.tasks` 代码。
8. `compileKotlin` 在生成代码可用后编译主源码。
9. `processResources` 处理 `application*.yml`。
10. 最终由 `jar` 或 `bootJar` 打包。

第二条是主数据库 jOOQ 生成流水线：

1. `generateJooq` 被调用。
2. 它依赖 `flywayMigrateMain`。
3. `flywayMigrateMain` 创建并迁移 `main` 临时 SQLite 数据库。
4. jOOQ 从 `main` schema 生成 `org.gotson.komga.jooq.main` 包下的代码。

需要注意的是，目标文件里显式让 `compileKotlin` 依赖 `generateTasksJooq`，但没有在当前片段中看到它显式依赖 `generateJooq`。这可能说明 `tasks` 这组生成代码在主编译路径上更直接，`main` 生成代码可能由插件默认接入或在其他任务中使用。这里应以实际 Gradle task graph 为准。

第三条是前端资源整合流水线：

1. 调用 `npmInstall`，在 `komga-webui` 中安装依赖。
2. 调用 `npmBuild`，执行前端构建。
3. 调用 `copyWebDist`，把 `dist` 复制到 `komga/src/main/resources/public/`。
4. 调用 `prepareThymeLeaf`，处理 `index.html` 中的资源路径，注入 Thymeleaf `th:` 属性。
5. 后端资源处理和打包时，这些静态资源会被带进 Spring Boot 应用。

第四条是测试与覆盖率流水线：

1. `test` 使用 JUnit Platform。
2. 测试 profile 固定为 `test`。
3. `jacocoTestReport` 依赖 `test`，所以覆盖率报告会在测试之后生成。

第五条是 OpenAPI 生成流水线：

1. OpenAPI 插件启动定制的 Spring Boot run。
2. 使用 profiles：`claim,generate-openapi`。
3. 监听端口 `8080`。
4. 输出文档到 `komga/docs`。

## 小白阅读顺序

建议按下面顺序读这个文件，不要从第一行一路硬啃。

1. 先看 `plugins`  
   先知道这个模块用了哪些构建能力。看到 Spring Boot、Kotlin、Flyway、jOOQ、OpenAPI，就能判断它不是单纯库模块，而是一个完整服务端应用模块。

2. 再看 `dependencies` 的大类  
   不需要记住每个依赖版本，重点看依赖类别：Web、安全、数据库、搜索、文件解析、图片处理、测试。这样能快速理解 Komga 后端解决的问题域。

3. 看 `kotlin` 和 Java 编译目标  
   记住项目目标是 JVM 17，并且 Kotlin nullability 规则较严格。

4. 看 `tasks` 里的前端相关任务  
   从 `npmInstall`、`npmBuild`、`copyWebDist`、`prepareThymeLeaf` 这四个任务理解：前端项目 `komga-webui` 的产物最终会进入后端资源目录。

5. 看 Flyway 部分  
   理解 `sqliteUrls`、`sqliteMigrationDirs`、`flywayMigrateMain`、`flywayMigrateTasks`。这里说明构建时会创建临时 SQLite 数据库用于 schema 生成。

6. 看 jOOQ 部分  
   重点看 `jooq { configurations { create("main") ... create("tasks") ... } }`，理解数据库 schema 如何变成 `org.gotson.komga.jooq.main` 和 `org.gotson.komga.jooq.tasks` 包下的代码。

7. 最后看 sourceSets 和任务依赖  
   重点理解为什么 `compileKotlin`、ktlint、KAPT 要依赖 `generateTasksJooq`。这是排查“找不到 jOOQ 生成类”这类构建问题的关键。

## 常见误区

1. 误以为 `build.gradle.kts` 只是依赖清单  
   这个文件不只是列依赖。它还定义前端构建、数据库迁移、jOOQ 代码生成、资源加工、OpenAPI 生成、benchmark source set、测试 profile 等完整构建流程。

2. 误以为 jOOQ 代码是手写的  
   `org.gotson.komga.jooq.main` 和 `org.gotson.komga.jooq.tasks` 是根据 SQLite schema 生成的。schema 又来自 Flyway migration。改数据库结构时，正确入口通常是 migration，而不是直接改生成代码。

3. 误以为 Flyway 只在应用运行时使用  
   这里 Flyway 明确参与构建期流程：`flywayMigrateMain` 和 `flywayMigrateTasks` 会创建临时数据库，供 jOOQ 读取 schema。运行时是否也用 Flyway，需要结合应用配置和启动代码继续看，但构建期使用是确定的。

4. 误以为前端和后端完全分离  
   构建脚本会进入 `komga-webui` 执行 npm 构建，并把 `dist` 放入 `komga/src/main/resources/public/`。所以后端包可能包含前端静态资源。

5. 误以为 `prepareThymeLeaf` 是普通复制  
   它会修改 `index.html` 中的资源引用，给 `src`、`content`、`href` 注入 Thymeleaf 属性。这一步关系到部署在不同上下文路径时前端资源能否正确加载。

6. 误以为所有 source set 都是默认的  
   这里额外定义了 `benchmark` 和 `flyway` source set。`src/benchmark`、`src/flyway` 不是随便放的目录，而是被构建脚本明确接入的源码集合。

7. 误以为 `compileKotlin` 可以独立运行  
   文件中显式声明 `compileKotlin` 依赖 `generateTasksJooq`。也就是说，编译 Kotlin 前必须先完成 tasks 数据库的 Flyway 迁移和 jOOQ 生成。

8. 误以为 ktlint 会格式化所有 Kotlin 文件  
   ktlint 配置排除了 `**/db/migration/**`。数据库迁移相关代码不会按普通主源码规则处理，阅读或修改时要注意这一点。

9. 误以为 Spring Boot build info 每次都应该变化  
   这里排除了 `time`，是为了避免构建缓存失效或任务每次重跑。build info 仍会受 `gradle.properties` 影响。

10. 误以为 Windows 和 Unix 构建命令完全一样  
   `npmInstall` 和 `npmBuild` 用 `Os.isFamily(Os.FAMILY_WINDOWS)` 判断命令名，Windows 下会调用 `npm.cmd`，其他系统调用 `npm`。这类细节会影响跨平台构建问题排查。
