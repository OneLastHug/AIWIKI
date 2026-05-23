# 目录：komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration

## 它负责什么

这个目录是 Komga 后端的“配置承接层”和“运行时设置入口”。它不直接实现漫画/电子书业务，而是把外部配置、数据库内保存的服务端设置、少量静态 Bean 统一暴露给 Spring 容器和其他模块使用。

可以把这里分成两类配置：

一类是启动期配置，由 `KomgaProperties` 通过 Spring Boot 的 `@ConfigurationProperties(prefix = "komga")` 绑定 `komga.*` 配置项，例如数据库文件位置、Lucene 索引目录、字体目录、CORS、Kobo、SQLite 参数等。这些值通常来自 `application.yml`、用户配置目录下的 `application.yml` / `application.properties`、环境变量或命令行参数。

另一类是运行期设置，由 `KomgaSettingsProvider` 通过 `ServerSettingsDao` 从主数据库读取和保存，例如 `rememberMeKey`、`rememberMeDuration`、`thumbnailSize`、`taskPoolSize`、Kobo proxy 端口、`kepubifyPath` 等。这些设置可以被 REST 接口修改，并在部分字段变化时发布事件通知其他组件热更新。

此外，这个目录还承担两个辅助职责：`ConfigurationChecker` 在启动后检查数据库路径是否位于远程文件系统上，避免 SQLite 放在 CIFS/NFS 等不适合的位置；`StaticConfiguration` 注册缩略图、PDF 转图等固定 Bean。

## 关键组成

`KomgaProperties.kt` 是静态外部配置的核心类。它声明为 `@Component`、`@ConfigurationProperties(prefix = "komga")`、`@Validated`，说明 Spring 会把 `komga.*` 配置绑定到这个对象，并执行 Bean Validation。主要字段包括：

- `pageHashing`：页面哈希相关参数，默认 `3`，在 `BookAnalyzer` 注释中被引用。
- `epubDivinaLetterCountThreshold`：EPUB/Divina 分析相关阈值。
- `oauth2AccountCreation`、`oidcEmailVerification`：OAuth2/OIDC 行为开关。
- `database`、`tasksDb`：两个 SQLite 数据库配置，分别用于主业务数据库和任务数据库。
- `cors`：跨域允许来源。
- `lucene`：搜索索引目录、分词器 n-gram 参数、提交延迟。
- `fonts`：字体数据目录。
- `kobo`：Kobo 同步限制和 `kepubifyPath` 配置。
- `configDir`：配置目录路径，默认配置文件里还会通过它拼出数据库、日志、Lucene、字体等目录。

`KomgaProperties.Database` 里集中描述 SQLite 连接配置：`file`、`batchChunkSize`、`poolSize`、`maxPoolSize`、`journalMode`、`busyTimeout`、`pragmas`、`checkLocalFilesystem`。其中 `file`、部分数值字段带有 `@NotBlank`、`@Positive` 校验。`@PostConstruct makeDirs()` 会尝试创建 `database.file` 和 `tasksDb.file` 的父目录，异常被吞掉，说明它是“尽力而为”的目录准备，不负责完整报错处理。

`ConfigurationChecker.kt` 是启动期防护组件。它注入 `KomgaProperties`，在 `@PostConstruct checkDatabasesPath()` 中分别检查 `komgaProperties.database` 和 `komgaProperties.tasksDb`。如果对应数据库配置的 `checkLocalFilesystem` 为 true，它会把数据库文件路径转成 `Path`，再用 `Files.getFileStore(path).type()` 获取文件系统类型。若类型以 `cifs` 或 `nfs` 开头，就抛出 `ConfigurationException`，提示用户可以通过 `komga.database.check-local-filesystem: false` 或 `komga.tasks-db.check-local-filesystem: false` 关闭检查。这里的意图很明确：SQLite 数据库应尽量放在本地文件系统，远程挂载可能导致锁、性能或一致性问题。

`KomgaSettingsProvider.kt` 是运行时设置的门面服务。它声明为 `@Service`，注入 `ServerSettingsDao` 和 `ApplicationEventPublisher`。每个属性初始化时先从数据库读取，如果没有值则使用默认值；属性 setter 会把新值写回数据库，并更新内存字段。典型字段包括：

- `deleteEmptyCollections`、`deleteEmptyReadLists`：控制是否删除空集合、空阅读列表。
- `rememberMeKey`：记住登录的密钥；若数据库没有，则用 `RandomStringUtils.secure().nextAlphanumeric(32)` 生成并保存。
- `rememberMeDuration`：记住登录时长，数据库里保存天数 `Int`，代码中暴露为 Kotlin `Duration`。
- `thumbnailSize`：缩略图尺寸，数据库保存枚举名，代码中转换为 `ThumbnailSize`。
- `taskPoolSize`：任务线程池大小，修改后发布 `SettingChangedEvent.TaskPoolSize`。
- `serverPort`、`serverContextPath`：服务端端口和上下文路径，可保存或删除。
- `koboProxy`、`koboPort`、`kepubifyPath`：Kobo 相关运行时设置，`kepubifyPath` 修改后发布 `SettingChangedEvent.KepubifyPath`。

`SettingChangedEvent.kt` 定义了密封事件类型，目前只有两个事件：`TaskPoolSize` 和 `KepubifyPath`。这两个事件说明对应设置需要被其他组件即时感知，而不是等到下次重启。

`StaticConfiguration.kt` 是一个很小的 Spring `@Configuration`。它注册三个命名 Bean：

- `thumbnailType`：固定为 `ImageType.JPEG`。
- `pdfImageType`：固定为 `ImageType.JPEG`。
- `pdfResolution`：固定为 `3200F`。

这些 Bean 通过 `@Qualifier("thumbnailType")`、`@Qualifier("pdfImageType")`、`@Qualifier("pdfResolution")` 被图像、PDF、OPDS 等模块注入使用。

## 上下游关系

上游主要是 Spring Boot 配置系统、数据库设置表和应用启动生命周期。

`KomgaProperties` 的上游是 `application.yml`、`application-localdb.yml` 以及外部配置文件。默认资源配置中可以看到 `komga.config-dir` 被用于拼接日志、主数据库、任务数据库、Lucene、字体目录等路径；同时 Spring Boot 会额外导入用户配置目录下的 `application.yml`、`application.yaml`、`application.properties`。因此 `KomgaProperties` 是“文件/环境配置进入应用”的第一站。

`KomgaSettingsProvider` 的上游是 `ServerSettingsDao`，也就是主数据库中的 server settings 存储。它不是从 YAML 读取主要值，而是从数据库读取可变设置。REST 设置接口修改配置时，也会通过这个 provider 写回数据库。

下游分布很广：

- `DataSourcesConfiguration` 使用 `KomgaProperties.database` 和 `KomgaProperties.tasksDb` 创建主库、任务库的数据源，并根据 `journalMode` 等配置决定读写数据源策略。
- `TasksDao` 使用 `komgaProperties.tasksDb.batchChunkSize` 控制批量处理大小。
- `LuceneConfiguration` 使用 `komgaProperties.lucene` 创建搜索索引相关组件。
- `CorsConfiguration` 使用 `komgaProperties.cors.allowedOrigins` 配置 CORS。
- `FontsController` 使用 `komgaProperties.fonts.dataDirectory` 处理字体接口。
- `KoboController` 使用 `KomgaProperties` 读取 Kobo 同步限制等配置。
- `SecurityConfiguration` 使用 `KomgaSettingsProvider.rememberMeKey` 和 `rememberMeDuration` 配置 remember-me 登录。
- `SettingsController` 使用 `KomgaSettingsProvider` 对外提供设置读取和更新接口。
- `TaskProcessor` 读取 `taskPoolSize`，并监听 `SettingChangedEvent.TaskPoolSize` 动态调整线程池。
- `KepubConverter` 读取 `kepubifyPath`，并监听 `SettingChangedEvent.KepubifyPath` 重新配置转换器路径。
- `BookAnalyzer`、`MosaicGenerator`、`WebPubGenerator`、`OpdsController`、`PdfExtractor` 等通过 `StaticConfiguration` 的命名 Bean 获取图片格式或 PDF 分辨率。

根据当前片段推断，`KomgaSettingsProvider` 负责的是“可通过 UI/API 修改的服务端设置”，而 `KomgaProperties` 负责的是“部署级、启动级配置”。依据是前者通过 DAO 持久化并被 `SettingsController` 修改，后者通过 `@ConfigurationProperties` 从 `komga.*` 绑定。

## 运行/调用流程

应用启动时，Spring 创建 `KomgaProperties`，并把 `komga.*` 配置绑定进去。绑定完成后，`makeDirs()` 会尝试创建主数据库和任务数据库所在目录。随后 `ConfigurationChecker` 的 `checkDatabasesPath()` 运行：它会检查两个数据库路径是否位于 CIFS/NFS 这类远程文件系统。如果检测命中，会记录 error 并抛出 `ConfigurationException`，启动流程被中断；如果路径不存在，它还会尝试检查父目录的文件系统类型。

接着，数据源、Lucene、安全、CORS、Kobo、字体等配置类会注入 `KomgaProperties`，读取对应字段完成初始化。例如数据源模块根据 `database.file`、`journalMode`、`pragmas` 等建立 SQLite 连接；搜索模块根据 `lucene.dataDirectory` 和分词器参数建立索引能力；安全模块根据 OAuth2/OIDC 相关开关决定账号创建和邮箱验证行为。

`KomgaSettingsProvider` 创建时，会立即从 `ServerSettingsDao` 加载各项运行时设置。若某些键不存在，会使用代码默认值；其中 `rememberMeKey` 比较特殊，没有值时会立即生成一个随机 32 位字母数字串并保存。之后业务模块直接读取 provider 的属性，例如安全配置读取 remember-me 参数，任务处理器读取任务线程池大小，图像处理读取缩略图尺寸。

当管理员通过设置接口更新配置时，`SettingsController` 会把 DTO 中显式设置的字段写入 `KomgaSettingsProvider`。Provider 的 setter 负责保存到数据库。普通字段只保存并更新内存值；有热更新需求的字段会额外发布事件：`taskPoolSize` 发布 `TaskPoolSize`，`kepubifyPath` 发布 `KepubifyPath`。监听者收到事件后再调整自身状态，例如 `TaskProcessor` 修改 executor 的 core pool size，`KepubConverter` 重新解析和验证 kepubify 可执行文件路径。

`StaticConfiguration` 的流程更简单：Spring 启动时注册三个固定 Bean，下游通过名称注入。因为 `thumbnailType` 和 `pdfImageType` 都是 `ImageType.JPEG`，所以当前系统默认缩略图和 PDF 页面导出/转换都偏向 JPEG 输出；`pdfResolution` 固定为 `3200F`，用于 PDF 提取场景。

## 小白阅读顺序

建议先读 `KomgaProperties.kt`。这是理解整个目录的入口，因为它列出了 Komga 自定义配置的“菜单”：数据库、任务库、Lucene、字体、Kobo、CORS、安全相关开关都在这里。读的时候重点看类结构和默认值，不需要一开始纠结每个字段在哪里使用。

第二步读 `ConfigurationChecker.kt`。它很短，但能帮助你理解为什么数据库配置不是普通路径字符串：Komga 对 SQLite 文件位置有启动期校验，尤其关注 CIFS/NFS 远程文件系统。这里还能看到 `komga.database.check-local-filesystem` 和 `komga.tasks-db.check-local-filesystem` 这类配置开关的用途。

第三步读 `KomgaSettingsProvider.kt`。注意它和 `KomgaProperties` 的区别：`KomgaProperties` 是外部配置绑定，`KomgaSettingsProvider` 是数据库持久化设置。阅读时可以按“初始化值来自哪里、setter 做了什么、哪些字段会发布事件”三条线看。

第四步读 `SettingChangedEvent.kt`。虽然只有两个事件，但它揭示了哪些设置被设计成运行时热更新。读完后再去看调用方会更清楚，例如 `TaskProcessor` 对 `TaskPoolSize` 的监听，`KepubConverter` 对 `KepubifyPath` 的监听。

第五步读 `StaticConfiguration.kt`。这个文件不是业务逻辑入口，而是给图像/PDF/OPDS 等模块提供固定 Bean。读完它之后，可以顺着 `@Qualifier("thumbnailType")`、`@Qualifier("pdfImageType")`、`@Qualifier("pdfResolution")` 去看图像处理链路。

最后再看代表调用方：`komga/src/main/kotlin/org/gotson/komga/infrastructure/datasource/DataSourcesConfiguration.kt`、`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt`、`komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskProcessor.kt`、`komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KepubConverter.kt`。这几处能覆盖静态配置绑定、运行时设置修改、事件监听和热更新。

## 常见误区

第一个误区是把 `KomgaProperties` 和 `KomgaSettingsProvider` 混为一谈。前者来自 `komga.*` 外部配置，偏部署和启动；后者来自数据库设置表，偏运行时和管理界面。修改 YAML 通常影响 `KomgaProperties`，调用设置 API 通常影响 `KomgaSettingsProvider`。

第二个误区是以为 `KomgaProperties.Database.checkLocalFilesystem` 会检查所有路径。实际上它只围绕主数据库和任务数据库路径做本地文件系统检查，且只拦截文件系统类型以 `cifs`、`nfs` 开头的情况。其他数据目录，例如 Lucene、fonts，不在这个 checker 中。

第三个误区是认为 `makeDirs()` 能保证数据库路径一定可用。它只是尝试创建父目录，并且吞掉异常。真正的数据源能否建立、文件是否可写，还要看后续 datasource 初始化和 SQLite 打开文件时的结果。

第四个误区是忽略 setter 的副作用。`KomgaSettingsProvider` 的属性不是普通内存字段，赋值会写数据库；`taskPoolSize` 和 `kepubifyPath` 还会发布事件。测试或业务代码中直接赋值时，也是在改变持久化设置。

第五个误区是认为 `StaticConfiguration` 里的值可以像普通常量一样随便改。它们是 Spring Bean，下游通过名字注入。如果修改 Bean 名称或类型，会影响所有使用 `@Qualifier("thumbnailType")`、`@Qualifier("pdfImageType")`、`@Qualifier("pdfResolution")` 的组件。当前命名 Bean 是图像和 PDF 处理链路的隐式契约。

第六个误区是把 `kepubifyPath` 的两个来源看成同一个。`KomgaProperties.Kobo.kepubifyPath` 或 `@Value("${komga.kobo.kepubify-path:...}")` 属于配置文件来源，而 `KomgaSettingsProvider.kepubifyPath` 属于数据库设置来源。根据当前片段推断，`KepubConverter` 会综合配置文件路径和运行时设置路径，并在设置变化后重新配置。
