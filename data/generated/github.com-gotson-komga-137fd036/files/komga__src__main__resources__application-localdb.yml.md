# 文件：komga/src/main/resources/application-localdb.yml

## 它负责什么

`komga/src/main/resources/application-localdb.yml` 是 Komga 的一个 Spring Boot profile 配置文件，对应 profile 名称为 `localdb`。当应用启动时激活 `localdb` profile，Spring Boot 会在基础配置 `application.yml` 之上叠加读取这个文件，用它覆盖默认数据库、Lucene 索引目录和任务数据库的位置。

这个文件的核心作用是：把 Komga 的运行数据切换到一个名为 `localdb` 的独立工作区里，方便开发者或测试者使用本地持久化数据库，而不是默认的生产数据库文件名，也不是 `dev` profile 中的内存数据库。

目标文件内容很短：

```yaml
komga:
  workspace: localdb
  database:
    file: ${komga.config-dir}/${komga.workspace}.sqlite
  lucene:
    data-directory: ${komga.config-dir}/lucene/${komga.workspace}
  tasks-db:
    file: ${komga.config-dir}/${komga.workspace}-tasks.sqlite
```

它不定义端口、不定义日志级别、不定义安全策略，也不直接启动任何组件。它只负责为 `komga.*` 这组应用自定义配置提供 profile 级别的覆盖值。

## 关键组成

`komga.workspace: localdb`

这是这个 profile 的工作区名称。后续多个路径都通过 `${komga.workspace}` 引用它，因此实际文件名会带上 `localdb`。

例如：

```yaml
komga:
  workspace: localdb
```

这会让 `${komga.workspace}` 解析为 `localdb`。

`komga.database.file`

```yaml
komga:
  database:
    file: ${komga.config-dir}/${komga.workspace}.sqlite
```

这是 Komga 主业务数据库文件的位置。结合 `workspace: localdb` 后，实际形式是：

```text
${komga.config-dir}/localdb.sqlite
```

`komga.config-dir` 并不在本文件里定义，而是在基础配置 `komga/src/main/resources/application.yml` 中默认定义为：

```text
${user.home}/.komga
```

所以如果只激活 `localdb`，不叠加其他 profile，主数据库默认会落在：

```text
~/.komga/localdb.sqlite
```

如果同时激活 `dev` profile，则 `komga/src/main/resources/application-dev.yml` 会把 `komga.config-dir` 改成：

```text
${rootDir}/config-dir
```

此时主数据库会变成：

```text
${rootDir}/config-dir/localdb.sqlite
```

`komga.lucene.data-directory`

```yaml
komga:
  lucene:
    data-directory: ${komga.config-dir}/lucene/${komga.workspace}
```

这是 Lucene 索引数据目录。Lucene 通常用于全文搜索、书籍元数据搜索、索引加速等场景。结合 `workspace: localdb` 后，目录形式是：

```text
${komga.config-dir}/lucene/localdb
```

它和主数据库文件分开存放，避免多个 profile 或多个工作区共用同一套索引目录。

`komga.tasks-db.file`

```yaml
komga:
  tasks-db:
    file: ${komga.config-dir}/${komga.workspace}-tasks.sqlite
```

这是任务数据库文件的位置。结合 `workspace: localdb` 后，实际形式是：

```text
${komga.config-dir}/localdb-tasks.sqlite
```

从命名上看，它用于存放任务、后台作业或队列相关的数据，和主业务数据库拆开。基础配置 `application.yml` 中默认任务数据库是：

```text
${komga.config-dir}/tasks.sqlite
```

而 `localdb` profile 将它改成带工作区前缀的 `localdb-tasks.sqlite`，这样可以避免不同运行模式共用任务状态。

## 上下游关系

上游配置来源主要有三个层次。

第一层是 `komga/src/main/resources/application.yml`。这是全局基础配置，提供默认值，包括：

```text
komga.database.file = ${komga.config-dir}/database.sqlite
komga.lucene.data-directory = ${komga.config-dir}/lucene
komga.config-dir = ${user.home}/.komga
komga.tasks-db.file = ${komga.config-dir}/tasks.sqlite
```

第二层是当前文件 `komga/src/main/resources/application-localdb.yml`。当 `localdb` profile 激活后，它覆盖主数据库文件、Lucene 数据目录、任务数据库文件，并新增或覆盖 `komga.workspace`。

第三层可能是外部用户配置。基础配置 `application.yml` 中声明了：

```yaml
spring:
  config:
    import:
      - "optional:file:${komga.config-dir}/application.yml"
      - "optional:file:${komga.config-dir}/application.yaml"
      - "optional:file:${komga.config-dir}/application.properties"
```

这意味着 Komga 还会尝试从 `${komga.config-dir}` 下加载外部配置文件。外部配置如果存在，可能继续覆盖这里的值。因此 `application-localdb.yml` 是内置 profile 默认值，不一定是最终运行值。

下游消费方主要是应用的配置绑定和初始化逻辑。

从仓库搜索结果看，`komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaProperties.kt` 会读取 `komga.database.file` 等属性，并创建数据库父目录：

```text
Path(database.file).parent.createDirectories()
```

也就是说，这些 YAML 配置最终会绑定到 Kotlin 配置类中，被应用启动阶段使用。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/ConfigurationChecker.kt` 会检查数据库配置是否位于本地文件系统，搜索结果中可以看到它检查 `komgaProperties.tasksDb`，并提示可通过：

```text
komga.tasks-db.check-local-filesystem: false
```

来关闭某类本地文件系统检查。根据当前片段推断，主数据库和任务数据库路径不仅用于连接 SQLite，也会参与启动前的环境合法性检查。

此外，开发文档 `DEVELOPING.md` 中提到：

```text
localdb: a dev profile that stores the database in ./localdb
dev,localdb,noclaim: when testing with an existing database
```

这里说明 `localdb` 主要是开发场景 profile，常和 `dev`、`noclaim` 一起使用，用于测试已有数据库或保留本地数据。需要注意的是，目标文件本身并没有把 `config-dir` 设置为 `./localdb`；最终目录还取决于是否同时激活 `dev` profile、运行目录和外部配置。文档中的 `./localdb` 描述需要结合实际启动脚本或 Gradle 配置理解。

## 运行/调用流程

1. 应用启动时，Spring Boot 读取 `komga/src/main/resources/application.yml`。

基础配置先提供默认路径：

```text
${user.home}/.komga/database.sqlite
${user.home}/.komga/lucene
${user.home}/.komga/tasks.sqlite
```

2. 如果启动参数、环境变量或运行配置激活了 `localdb` profile，Spring Boot 继续读取：

```text
komga/src/main/resources/application-localdb.yml
```

3. 当前文件设置：

```text
komga.workspace = localdb
```

然后通过占位符展开路径：

```text
komga.database.file = ${komga.config-dir}/localdb.sqlite
komga.lucene.data-directory = ${komga.config-dir}/lucene/localdb
komga.tasks-db.file = ${komga.config-dir}/localdb-tasks.sqlite
```

4. 如果同时激活 `dev` profile，`komga/src/main/resources/application-dev.yml` 也会参与配置合并。

`dev` profile 中比较关键的是：

```text
komga.config-dir = ${rootDir}/config-dir
```

以及它默认把数据库设置成内存数据库：

```text
komga.database.file = file:database?mode=memory
komga.tasks-db.file = file:tasks?mode=memory
```

当同时激活 `dev` 和 `localdb` 时，最终哪个值生效取决于 Spring Boot profile 加载顺序。常见用法是通过 profile 顺序让 `localdb` 覆盖 `dev` 的内存数据库配置，从而在开发环境中使用本地 SQLite 文件。`DEVELOPING.md` 中给出的 `dev,localdb,noclaim` 用法也支持这个理解。

5. 配置绑定到 `KomgaProperties.kt` 这类配置属性对象。

根据搜索片段，应用会基于 `database.file` 创建父目录，并把数据库路径传给底层数据库连接或迁移逻辑。

6. Flyway 迁移、数据库连接、任务存储和 Lucene 索引初始化使用这些最终路径。

基础配置中启用了 Flyway：

```yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration/{vendor}
```

因此，当 `localdb` 指向一个新的 SQLite 文件时，应用启动阶段通常会对这个数据库执行必要的 schema migration。Lucene 目录也会根据配置指向独立的 `lucene/localdb` 目录，避免和默认索引混用。

## 小白阅读顺序

1. 先读 `komga/src/main/resources/application.yml`

理解默认的 `komga.config-dir`、`komga.database.file`、`komga.lucene.data-directory`、`komga.tasks-db.file` 是什么。这个文件是所有 profile 的基础。

2. 再读 `komga/src/main/resources/application-localdb.yml`

重点看它覆盖了哪些默认值。这个文件最重要的思路是：用 `workspace` 变量统一生成主数据库、任务数据库和 Lucene 索引目录。

3. 对比 `komga/src/main/resources/application-dev.yml`

`dev` profile 使用内存数据库，而 `localdb` profile 使用本地 SQLite 文件。理解这两个 profile 的差异，就能明白为什么开发时会需要 `dev,localdb` 这种组合。

4. 查看 `DEVELOPING.md`

这里能看到官方开发场景对 profile 的说明，例如 `localdb` 和 `dev,localdb,noclaim` 的用途。它可以帮助你理解这个 YAML 不是生产部署配置，而是偏开发和本地测试场景的配置。

5. 最后看 `KomgaProperties.kt` 和 `ConfigurationChecker.kt`

这两个文件是配置的下游使用点。前者负责把 `komga.*` 配置绑定成应用可用的对象，并处理目录创建；后者负责检查数据库路径是否符合运行要求。

## 常见误区

误区一：以为 `application-localdb.yml` 会自动生效。

不会。它只有在 `localdb` profile 被激活时才会参与配置合并。没有激活 `localdb` 时，应用只使用默认的 `application.yml` 以及其他已激活 profile。

误区二：以为这个文件定义了数据库类型。

它没有显式写数据库驱动、JDBC URL 或数据库方言。它只是定义 SQLite 文件路径。真正如何连接数据库，要看 Komga 的数据库配置类、Spring Boot 自动配置和相关依赖。

误区三：以为 `localdb` 一定把数据放到仓库根目录。

目标文件本身没有定义 `komga.config-dir`。它只是使用 `${komga.config-dir}`。如果没有其他 profile 覆盖，默认来自 `application.yml`：

```text
${user.home}/.komga
```

如果和 `dev` profile 一起使用，`application-dev.yml` 会把 `config-dir` 改成 `${rootDir}/config-dir`。所以实际位置取决于最终配置合并结果。

误区四：忽略 `tasks-db`。

很多人只关注主数据库 `database.file`，但 Komga 还单独配置了 `tasks-db.file`。如果主数据库切到 `localdb.sqlite`，任务数据库也要切到 `localdb-tasks.sqlite`，否则可能出现不同工作区共用任务状态的问题。

误区五：以为 Lucene 索引可以随便共用。

`localdb` profile 把 Lucene 目录改成 `${komga.config-dir}/lucene/localdb`，这是为了让搜索索引跟当前工作区绑定。不同数据库对应不同索引目录，可以减少索引内容和数据库内容不一致的风险。

误区六：把 `${komga.workspace}` 当成系统环境变量。

这里的 `${komga.workspace}` 是 Spring 配置占位符，来自同一个配置树中的 `komga.workspace: localdb`。它不是操作系统环境变量，也不是 shell 变量。

误区七：认为 `application-localdb.yml` 是生产部署推荐配置。

从 `DEVELOPING.md` 的描述看，`localdb` 是开发 profile，常用于本地保留数据库或测试已有数据库。生产部署更应该结合正式部署方式、外部配置文件、Docker 配置和实际数据目录规划来设置。
