# 文件：komga/src/main/resources/application-docker.yml

## 它负责什么

`komga/src/main/resources/application-docker.yml` 是 Komga 在 Docker 镜像运行时加载的 Spring Boot profile 配置文件。它的职责非常单一：为 Docker 环境预设 `kepubify` 可执行文件的位置。

文件内容只有一项配置：

```yaml
komga:
  kobo.kepubify-path: /usr/bin/kepubify
```

这表示：当应用以 `docker` profile 启动时，Komga 会把 `komga.kobo.kepubify-path` 解析为 `/usr/bin/kepubify`。这个路径对应 Docker 镜像中预装的 `kepubify` 二进制程序，用于把普通 EPUB 转换为 Kobo 更友好的 KEPUB 格式。

从功能归属看，它不是通用业务配置，也不是数据库、端口、日志配置；它专门服务于 Kobo 集成功能中的 EPUB 到 KEPUB 转换能力。

## 关键组成

这个文件只有一个配置节点，但可以拆成两层理解。

第一层是根命名空间：

```yaml
komga:
```

`komga` 是项目自定义配置的命名空间。基础配置文件 `komga/src/main/resources/application.yml` 中也大量使用了这个命名空间，例如：

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

也就是说，`application-docker.yml` 并不是独立配置体系，而是给通用 `komga.*` 配置补充 Docker 专属默认值。

第二层是属性名：

```yaml
kobo.kepubify-path: /usr/bin/kepubify
```

这里使用了 YAML 的“点号属性”写法。它等价于更展开的结构：

```yaml
komga:
  kobo:
    kepubify-path: /usr/bin/kepubify
```

对应到 Spring Boot 的 relaxed binding / property resolution，最终属性键是：

```text
komga.kobo.kepubify-path
```

这个属性在代码里主要由 `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KepubConverter.kt` 读取：

```kotlin
@param:Value($$"${komga.kobo.kepubify-path:#{null}}") val kepubifyConfigurationPath: String?
```

含义是：如果配置中存在 `komga.kobo.kepubify-path`，就注入到 `kepubifyConfigurationPath`；如果不存在，就注入 `null`。

项目里还有一个配置类 `komga/src/main/kotlin/org/gotson/komga/infrastructure/configuration/KomgaProperties.kt`，其中也定义了 Kobo 相关属性：

```kotlin
class Kobo {
  @get:Positive
  var syncItemLimit: Int = 100

  var kepubifyPath: String? = null
}
```

不过当前片段显示，`KepubConverter` 对这个具体路径的读取使用的是 `@Value`，不是直接从 `KomgaProperties.kobo.kepubifyPath` 取值。`KomgaProperties.Kobo.kepubifyPath` 更像是配置模型中的对应字段，便于其他地方按结构化属性访问或暴露配置。

## 上下游关系

上游主要有三个来源。

第一个上游是 Docker 启动 profile。`komga/docker/Dockerfile.tpl` 的入口命令包含：

```text
-Dspring.profiles.include=docker
```

这会让 Spring Boot 启动时额外包含 `docker` profile。根据 Spring Boot 的配置文件约定，`application-docker.yml` 会在这个 profile 激活时参与配置加载。因此，在 Docker 镜像里运行 Komga 时，本文目标文件中的 `/usr/bin/kepubify` 会成为默认配置值。

第二个上游是 Docker 镜像本身安装了 `kepubify`。`komga/docker/Dockerfile.tpl` 针对不同 CPU 架构下载对应的 `kepubify` 可执行文件，并写入同一个位置：

```text
/usr/bin/kepubify
```

例如 amd64 镜像下载 `kepubify-linux-64bit`，arm64 镜像下载 `kepubify-linux-arm64`，arm 镜像下载 `kepubify-linux-arm`，然后都执行：

```text
chmod +x /usr/bin/kepubify
```

这解释了为什么 `application-docker.yml` 可以硬编码 `/usr/bin/kepubify`：Dockerfile 已经保证这个路径存在并且可执行。

第三个上游是通用应用配置 `application.yml`。基础配置负责数据库位置、日志、端口、Spring 行为、外部配置导入等，而 `application-docker.yml` 只覆盖/补充 Docker 场景下的一小部分。`application.yml` 中还配置了外部配置导入：

```yaml
spring:
  config:
    import:
      - "optional:file:${komga.config-dir}/application.yml"
      - "optional:file:${komga.config-dir}/application.yaml"
      - "optional:file:${komga.config-dir}/application.properties"
```

Dockerfile 又设置：

```text
KOMGA_CONFIGDIR="/config"
```

并通过启动参数追加：

```text
--spring.config.additional-location=file:/config/
```

所以 Docker 用户仍然可以通过 `/config` 下的外部配置覆盖部分行为。根据当前片段推断，如果外部配置或应用内设置提供了另一个 `kepubify` 路径，运行时可能不一定使用 `application-docker.yml` 的默认值，具体优先级取决于 Spring 配置加载顺序和 `KepubConverter` 内部 fallback 逻辑。

下游主要是 `KepubConverter`。

`komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KepubConverter.kt` 是这个配置的直接消费者。它在构造函数中注入 `kepubifyConfigurationPath`，启动后执行：

```kotlin
@PostConstruct
private fun configureKepubifyOnStartup() {
  if (!settingsProvider.kepubifyPath.isNullOrBlank())
    configureKepubify(settingsProvider.kepubifyPath, true)
  else if (!kepubifyConfigurationPath.isNullOrBlank())
    configureKepubify(kepubifyConfigurationPath)
  else
    logger.info { "Kepub conversion unavailable. kepubify path is not set" }
}
```

这里能看出优先级：

1. 如果 `KomgaSettingsProvider` 中保存了用户设置的 `kepubifyPath`，优先使用用户设置。
2. 如果用户设置为空，再使用配置文件中的 `kepubifyConfigurationPath`，也就是 Docker profile 下的 `/usr/bin/kepubify`。
3. 如果两者都没有，EPUB 到 KEPUB 转换能力不可用。

此外，`SettingsController` 也和这个能力有关。`komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt` 会向前端/REST API 暴露多来源设置：

```kotlin
SettingMultiSource(
  kepubConverter.kepubifyConfigurationPath,
  komgaSettingsProvider.kepubifyPath,
  kepubConverter.kepubifyPath?.toString()
)
```

这说明用户界面或 API 可以看到：配置文件中的路径、用户保存的路径、当前实际生效路径。

## 运行/调用流程

Docker 场景下的典型流程如下。

1. 镜像构建阶段安装 `kepubify`

`komga/docker/Dockerfile.tpl` 根据目标架构下载 `kepubify`，统一放到：

```text
/usr/bin/kepubify
```

并赋予可执行权限。

2. 容器启动时激活 `docker` profile

Dockerfile 的 `ENTRYPOINT` 中包含：

```text
-Dspring.profiles.include=docker
```

因此 Spring Boot 启动时会加载基础的 `application.yml`，同时加载 `application-docker.yml`。

3. Spring 解析配置属性

`application-docker.yml` 提供：

```text
komga.kobo.kepubify-path=/usr/bin/kepubify
```

`KepubConverter` 构造时通过 `@Value` 得到这个值：

```kotlin
kepubifyConfigurationPath = "/usr/bin/kepubify"
```

4. `KepubConverter` 初始化转换能力

应用启动后，`KepubConverter.configureKepubifyOnStartup()` 执行。它先检查 `KomgaSettingsProvider.kepubifyPath` 是否有用户设置。如果没有用户设置，就使用 Docker 配置注入的 `/usr/bin/kepubify`。

随后进入：

```kotlin
configureKepubify(kepubifyConfigurationPath)
```

这个方法会把字符串转成 `Path`，并调用 `isExecutable()` 验证路径是否可执行。如果验证成功：

```kotlin
isAvailable = true
kepubifyPath = newPath
```

如果验证失败，会记录警告，并把转换能力标记为不可用。

5. Kobo 下载或 EPUB 处理时触发转换

`KepubConverter` 提供两个主要转换入口：

```kotlin
convertEpubToKepub(bookWithMedia, destinationDir)
convertEpubToKepubWithoutChecks(epub, destinationDir)
```

转换前会检查：

```kotlin
check(isAvailable) { "Kepub conversion is not available, kepubify path may not be set, or may be invalid" }
```

如果 Docker 中 `/usr/bin/kepubify` 可用，就会组装命令：

```text
/usr/bin/kepubify <source.epub> -o <destination.kepub.epub>
```

然后通过 `Runtime.getRuntime().exec(command)` 执行外部进程，等待最多 10 秒。成功后返回生成的 `.kepub.epub` 文件路径，失败则记录错误并返回 `null`。

6. 设置变更时重新配置

`KepubConverter` 还监听：

```kotlin
@EventListener(SettingChangedEvent.KepubifyPath::class)
```

当用户通过设置修改 `kepubifyPath` 时，会重新调用：

```kotlin
configureKepubify(settingsProvider.kepubifyPath, true)
```

这里的 `fallback = true` 很关键：如果用户设置为空或无效，并且配置文件中的 Docker 默认路径存在，就会回退到 `/usr/bin/kepubify`。因此 Docker 配置不仅是启动默认值，也可以作为用户设置失效时的 fallback。

## 小白阅读顺序

建议按下面顺序读，不要一开始就陷进 Kobo API 的大量控制器代码里。

1. 先读 `komga/src/main/resources/application-docker.yml`

确认它只有一个目的：给 Docker profile 设置 `komga.kobo.kepubify-path`。

2. 再读 `komga/docker/Dockerfile.tpl`

重点看两处：一处是构建阶段把 `kepubify` 下载到 `/usr/bin/kepubify`；另一处是 `ENTRYPOINT` 中的 `-Dspring.profiles.include=docker`。这两处合起来解释了“为什么这个 YAML 会生效”以及“为什么路径写死为 `/usr/bin/kepubify`”。

3. 再读 `komga/src/main/resources/application.yml`

不要逐行背配置，只看它和目标文件的关系：它提供通用默认配置、`komga.config-dir`、外部配置导入、服务端口等。这样能理解 `application-docker.yml` 是 Docker 环境的增量配置，而不是完整配置。

4. 然后读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KepubConverter.kt`

这是最重要的下游。重点看构造函数里的 `@Value`、`configureKepubifyOnStartup()`、`configureKepubify()`、`convertEpubToKepubWithoutChecks()`。读完这几个方法，就能知道配置如何变成可执行命令。

5. 最后读 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/SettingsController.kt`

这个文件帮助理解用户设置和配置文件默认值之间的关系。它不是转换逻辑本身，但会暴露 `kepubifyPath` 的多来源状态，也允许更新用户设置。

如果还想继续深入 Kobo 功能，再去看 `komga/src/main/kotlin/org/gotson/komga/interfaces/api/kobo/KoboController.kt`。这个文件很大，初学时只需要关注它注入了 `KepubConverter`，以及哪些下载/同步路径最终可能需要 EPUB 到 KEPUB 的转换。

## 常见误区

误区一：以为 `application-docker.yml` 是完整的 Docker 配置。

它不是。它只配置了 `kepubify` 路径。Docker 环境下的数据库目录、配置目录、端口、日志等主要来自 `application.yml`、Dockerfile 环境变量和外部 `/config` 配置。

误区二：以为 `kobo.kepubify-path` 是给 Kobo 设备看的。

不是。这个配置不会直接发给 Kobo 设备。它是服务端 Komga 自己使用的本地可执行文件路径。Komga 在服务器/容器里调用 `kepubify`，把 EPUB 转换成 KEPUB，再供 Kobo 相关接口使用。

误区三：以为只要配置了路径，转换就一定可用。

不一定。`KepubConverter` 会验证路径是否可执行。即使配置值存在，如果文件不存在、没有执行权限、架构不匹配，或者执行验证失败，`isAvailable` 仍然会是 `false`，转换时会报“转换不可用”。

误区四：以为 Docker 用户不能覆盖这个路径。

可以覆盖。代码里存在 `KomgaSettingsProvider.kepubifyPath`，并且启动时优先级高于 `kepubifyConfigurationPath`。也就是说，用户设置的路径优先于 `application-docker.yml` 中的 `/usr/bin/kepubify`。不过在标准 Docker 镜像里通常不需要改，因为镜像已经内置了正确路径。

误区五：看到 `KomgaProperties.Kobo.kepubifyPath` 就以为 `KepubConverter` 直接使用它。

从当前代码片段看，`KepubConverter` 直接通过 `@Value(${"komga.kobo.kepubify-path:#{null}"})` 注入配置值，而不是通过 `KomgaProperties.kobo.kepubifyPath` 读取。`KomgaProperties` 中的字段说明这个属性属于项目配置模型，但直接消费点仍然要看 `KepubConverter.kt`。

误区六：忽略 `fallback` 行为。

当用户设置变更时，`KepubConverter` 调用 `configureKepubify(settingsProvider.kepubifyPath, true)`。如果用户设置为空或无效，且配置文件里有 `/usr/bin/kepubify`，它会尝试回退到 Docker 默认路径。这使得 `application-docker.yml` 不只是首次启动默认值，也承担了“保底路径”的角色。

误区七：以为这个配置在非 Docker 环境也默认生效。

通常不会。文件名是 `application-docker.yml`，需要 `docker` profile 被激活才会加载。普通本地运行如果没有包含 `docker` profile，就不会自动使用 `/usr/bin/kepubify` 这个默认值；此时需要通过本地配置、环境变量或应用设置提供 `kepubify` 路径。
