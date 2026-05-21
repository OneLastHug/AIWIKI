# 目录：komga/src/main/resources

## 它负责什么

`komga/src/main/resources` 是 Komga 后端应用的运行时资源目录，主要承担三类职责：

第一，提供 Spring Boot 默认配置。`application.yml` 是主配置入口，定义应用版本、日志、数据库、Lucene、字体目录、Flyway 迁移、Jackson、静态资源、服务端口、Actuator、Springdoc/OpenAPI 等默认行为。

第二，提供不同运行环境的覆盖配置。`application-dev.yml`、`application-docker.yml`、`application-localdb.yml` 分别面向开发、Docker 镜像和本地多数据库/工作区场景，用 profile 或打包环境覆盖主配置中的部分默认值。

第三，提供内置静态资源。`banner.txt` 是启动时展示的 ASCII banner；`embeddedFonts/OpenDyslexic` 下的 `.woff`、`.woff2` 字体文件是内置字体资源，会被字体 API 暴露给阅读器使用。

这个目录本身没有 Kotlin 业务逻辑，但它是应用启动、配置绑定、运行环境差异化和部分 API 资源输出的源头。

## 关键组成

`application.yml` 是最核心的文件。

它首先声明 `application.version: ${version}`，这个值会进入启动 banner，也会被 `OpenApiConfiguration` 通过 `@Value("${application.version}")` 注入，用于 OpenAPI 文档元信息。`${version}` 通常来自构建或运行环境注入。

`logging` 配置日志文件位置和滚动策略。日志默认写到 `${komga.config-dir}/logs/komga.log`，并限制历史数量、总大小、单文件大小。这里的 `komga.config-dir` 默认是 `${user.home}/.komga`，所以普通运行时会在用户主目录下形成 Komga 的数据目录。

`komga` 配置块是项目自己的配置命名空间，对应 `KomgaProperties`。其中：

- `komga.database.file` 默认是 `${komga.config-dir}/database.sqlite`
- `komga.tasks-db.file` 默认是 `${komga.config-dir}/tasks.sqlite`
- `komga.lucene.data-directory` 默认是 `${komga.config-dir}/lucene`
- `komga.fonts.data-directory` 默认是 `${komga.config-dir}/fonts`
- `komga.config-dir` 默认是 `${user.home}/.komga`

这些值会绑定到 `org.gotson.komga.infrastructure.configuration.KomgaProperties`。该类启动后会尝试创建数据库和任务数据库的父目录，并通过嵌套类表达 `database`、`tasksDb`、`cors`、`lucene`、`fonts`、`kobo` 等配置结构。

`spring.flyway` 指定数据库迁移从 `classpath:db/migration/{vendor}` 加载，并通过 placeholders 把一些 Komga 自定义开关传给迁移脚本，例如 `library-file-hashing`、`library-scan-startup`、`delete-empty-collections`、`delete-empty-read-lists`。虽然这些迁移脚本不在当前目录片段中，但从配置可见，数据库初始化依赖 classpath 下的迁移资源。

`spring.config.import` 是理解用户自定义配置的关键。它会从 `${komga.config-dir}` 额外导入 `application.yml`、`application.yaml`、`application.properties`，而且都是 `optional:file:`。也就是说，仓库内的 `application.yml` 给出默认值，用户配置目录中的同名文件可以覆盖这些默认值。

`server.port: 25600` 是默认服务端口。`server.shutdown: graceful` 表示应用倾向于优雅关闭。`server.forward-headers-strategy: framework` 表示它会按 Spring 的方式处理反向代理转发头。

`management` 暴露 Actuator endpoints，并对 `configprops`、`env`、`health` 等端点设置授权显示策略。`springdoc.paths-to-match: "/api/**"` 表明 OpenAPI 文档只覆盖 `/api/**` 路径。

`application-dev.yml` 面向开发环境。它把数据库和任务数据库改成 SQLite 内存模式：`file:database?mode=memory`、`file:tasks?mode=memory`；设置 CORS 允许 `[URL已移除] `8080`；并提高 `org.gotson.komga` 日志级别到 `DEBUG`。这说明前端开发服务器或本地 API 调试通常会走 dev profile。

`application-docker.yml` 很短，只设置 `komga.kobo.kepubify-path: /usr/bin/kepubify`。这会被 `KepubConverter` 的 `@Value("${komga.kobo.kepubify-path:#{null}}")` 读取，用作 Docker 环境中 `kepubify` 可执行文件的默认路径。

`application-localdb.yml` 提供一个 `workspace: localdb` 维度，把数据库、Lucene、任务数据库路径都按 `${komga.workspace}` 分隔。它适合在同一个 `config-dir` 下切换或并行维护不同本地工作区数据。

`banner.txt` 是启动 banner，包含 `Version: ${application.version}`。Spring Boot 启动时会解析这个占位符，所以它和 `application.version` 有直接关系。

`embeddedFonts/OpenDyslexic` 包含四种字重/样式组合的 OpenDyslexic 字体，分别有 `.woff` 和 `.woff2` 版本：Regular、Italic、Bold、Bold-Italic。

## 上下游关系

上游主要是 Spring Boot 的配置加载机制、构建系统注入的 `${version}`、运行时 profile，以及用户配置目录中的外部配置文件。

启动时，Spring Boot 先加载 classpath 下的 `application.yml`，再根据激活的 profile 加载 `application-dev.yml`、`application-docker.yml`、`application-localdb.yml` 等变体。随后 `spring.config.import` 会尝试读取 `${komga.config-dir}` 里的用户配置文件，让部署者覆盖仓库默认值。

下游主要有这些代码模块：

`org.gotson.komga.infrastructure.configuration.KomgaProperties` 绑定 `komga.*` 配置。它定义数据库路径、任务数据库路径、Lucene 目录、字体目录、CORS、Kobo 等结构，是业务代码读取配置的统一入口之一。

`org.gotson.komga.infrastructure.configuration.ConfigurationChecker` 使用 `KomgaProperties.database` 和 `KomgaProperties.tasksDb` 检查数据库路径是否位于远程文件系统。它会识别类似 `cifs`、`nfs` 的文件系统类型；如果检测到数据库放在远程文件系统上，并且没有关闭检查，就抛出 `ConfigurationException`。这解释了为什么数据库路径配置不是单纯的字符串，而会影响启动安全检查。

`org.gotson.komga.infrastructure.security.CorsConfiguration` 读取 `komga.cors.allowed-origins`。只有该列表非空时，才注册 CORS 配置；注册后会允许所有 HTTP method、允许 credentials，并暴露 `Content-Disposition` 和 session header。`application-dev.yml` 中的 CORS 默认值就是给本地开发跨域请求使用的。

`org.gotson.komga.interfaces.api.rest.FontsController` 同时读取 classpath 内置字体和外部字体目录。它通过 `PathMatchingResourcePatternResolver().getResources("/embeddedFonts/**/*.*")` 扫描当前目录里的 `embeddedFonts`，再读取 `komga.fonts.data-directory` 下的额外字体目录。最终对外提供 `/api/v1/fonts/families`、`/api/v1/fonts/resource/{fontFamily}/{fontFile}`、`/api/v1/fonts/resource/{fontFamily}/css` 等接口，供 EPUB Reader 切换字体。

`org.gotson.komga.infrastructure.kobo.KepubConverter` 读取 `komga.kobo.kepubify-path`。如果用户设置中的 `kepubifyPath` 为空，它会回退到配置文件里的路径；Docker 配置正是通过这个方式让容器内默认使用 `/usr/bin/kepubify`。

`org.gotson.komga.infrastructure.openapi.OpenApiConfiguration` 读取 `application.version`，用于生成 API 文档信息。`banner.txt` 同样消费这个版本值。

## 运行/调用流程

应用启动时，Spring Boot 从 classpath 加载 `komga/src/main/resources/application.yml`。如果激活了特定 profile，会继续合并对应的 `application-*.yml`。例如开发环境加载 `application-dev.yml` 后，端口会从 `25600` 覆盖为 `8080`，数据库会从磁盘 SQLite 覆盖为内存 SQLite。

配置加载完成后，`spring.config.import` 指向的外部用户配置会参与合并。默认位置由 `komga.config-dir` 决定，即 `${user.home}/.komga`；用户可以在这个目录下放置 `application.yml`、`application.yaml` 或 `application.properties` 来覆盖默认配置。

随后 Spring 容器创建 `KomgaProperties`，把 `komga.*` 绑定成 Kotlin 对象。`KomgaProperties` 的 `@PostConstruct` 会尝试创建数据库文件和任务数据库文件的父目录。接着 `ConfigurationChecker` 在初始化阶段检查数据库路径是否在本地文件系统上，避免 SQLite 运行在 NFS/CIFS 这类不可靠路径上。

如果配置了 `komga.cors.allowed-origins`，`CorsConfiguration` 会注册 CORS 规则。默认主配置没有设置 allowed origins，所以生产环境默认不主动开放跨域；dev 配置则显式开放几个本地和站点来源。

字体相关流程发生在 `FontsController` 初始化时。它先扫描 classpath 下的 `/embeddedFonts/**/*.*`，把 `OpenDyslexic` 这样的目录名识别为 font family；再扫描 `${komga.config-dir}/fonts` 或用户覆盖后的 `komga.fonts.data-directory`。请求字体列表时返回所有 family；请求字体文件时返回对应资源；请求 CSS 时动态生成 `@font-face`，供阅读器加载。

Kobo 转换相关流程发生在 `KepubConverter` 初始化时。它先看设置中心里的 `kepubifyPath`，如果没有，再看配置文件中的 `komga.kobo.kepubify-path`。在 Docker profile 下，这个值是 `/usr/bin/kepubify`。组件会验证路径是否可执行，然后决定 kepub conversion 是否可用。

## 小白阅读顺序

建议先读 `komga/src/main/resources/application.yml`。重点看 `komga`、`spring.config.import`、`server`、`management`、`springdoc` 这些块，先建立“默认运行时配置从哪里来”的概念。

第二步读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaProperties.kt`。把 `application.yml` 里的 YAML 层级和 Kotlin 属性一一对应起来，例如 `komga.database.file` 对应 `KomgaProperties.database.file`，`komga.fonts.data-directory` 对应 `KomgaProperties.fonts.dataDirectory`。

第三步读 `ConfigurationChecker.kt`。它能帮助理解为什么数据库配置会影响启动检查，也能看出 Komga 对 SQLite 文件位置的约束。

第四步读三个 profile 文件：`application-dev.yml`、`application-docker.yml`、`application-localdb.yml`。对比它们和主配置的差异，理解同一个应用在开发、Docker、本地多工作区下如何改变行为。

第五步读 `FontsController.kt`，再回到 `embeddedFonts/OpenDyslexic`。这样能把“资源目录里的字体文件”与“API 如何对外提供字体”连起来。

最后再看 `banner.txt` 和 `OpenApiConfiguration`、`KepubConverter` 这类消费者，理解 `application.version` 和 `komga.kobo.kepubify-path` 这种单点配置如何进入具体功能。

## 常见误区

不要以为 `application.yml` 是唯一配置来源。它只是 classpath 默认配置；`${komga.config-dir}` 下的外部 `application.yml`、`application.yaml`、`application.properties` 也会被导入，并且通常用于真实部署覆盖默认值。

不要把 `application-dev.yml` 当成生产默认配置。dev profile 使用内存数据库，并开放本地 CORS，适合开发调试，不适合作为持久化生产配置。

不要认为 `embeddedFonts` 是前端静态目录。它位于后端 classpath 资源中，由 `FontsController` 扫描后通过 API 暴露，不是直接依赖 Spring 的默认静态资源映射。事实上主配置里 `spring.web.resources.add-mappings: false`，说明默认静态资源映射被关闭了。

不要忽略 `komga.config-dir` 的连锁影响。日志、主数据库、任务数据库、Lucene 索引、额外字体目录都默认挂在这个目录下面。改动它会同时改变多个运行数据位置。

不要把 `application-docker.yml` 理解成完整 Docker 配置。当前片段中它只设置了 `kepubify` 路径。Docker 环境里的更多行为可能来自镜像启动参数、环境变量或外部配置；根据当前片段推断，仓库资源目录只负责给 Kobo 转换提供容器内默认可执行文件路径。

不要认为字体只有内置的 OpenDyslexic。`embeddedFonts` 提供默认字体，但 `FontsController` 还会读取 `komga.fonts.data-directory` 下的额外字体 family。也就是说，运行时用户可以通过配置目录扩展字体。
