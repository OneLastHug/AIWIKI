# 文件：build.gradle.kts

## 它负责什么

`build.gradle.kts` 是这个仓库的根级 Gradle 构建脚本，作用不是直接声明业务代码依赖，而是给整个多模块工程提供统一的构建基础、代码风格检查、依赖升级检查、Gradle Wrapper 版本，以及发布配置。

这个仓库的模块入口由 `settings.gradle` 声明：

```gradle
include 'komga'
include 'komga-tray'
```

也就是说，根 `build.gradle.kts` 主要覆盖 `komga`、`komga-tray` 两个子项目。其中 `komga` 是服务端主体模块，`komga-tray` 是桌面托盘/桌面端相关模块。根脚本还配置了 JReleaser，用于生成 GitHub Release 内容、更新 `CHANGELOG.md`、打包单 JAR、构建并发布 Docker 镜像。

版本号来自 `gradle.properties`：

```properties
version=1.24.4
org.gradle.jvmargs=-Xmx2G
```

因此根脚本中的发布标签、JAR 路径、Docker 镜像 tag 等都会围绕当前项目版本展开。

## 关键组成

第一部分是 import：

```kotlin
import com.github.benmanes.gradle.versions.updates.DependencyUpdatesTask
import org.jreleaser.model.Active
import org.jreleaser.model.Distribution.DistributionType.SINGLE_JAR
import org.jreleaser.model.api.common.Apply
import kotlin.io.path.Path
import kotlin.io.path.exists
```

这些 import 说明根脚本主要做三类事情：

- 使用 `DependencyUpdatesTask` 配置依赖升级检查规则；
- 使用 JReleaser 的 `Active`、`SINGLE_JAR`、`Apply` 配置发布行为；
- 使用 `Path(...).exists()` 判断本地是否存在额外的 release notes 文件。

第二部分是根级插件声明：

```kotlin
plugins {
  run {
    val kotlinVersion = "2.2.0"
    kotlin("jvm") version kotlinVersion
    kotlin("plugin.spring") version kotlinVersion
    kotlin("kapt") version kotlinVersion
  }
  id("org.jlleitschuh.gradle.ktlint") version "13.0.0"
  id("com.github.ben-manes.versions") version "0.52.0"
  id("org.jreleaser") version "1.19.0"
}
```

这里把 Kotlin 相关插件版本统一固定为 `2.2.0`，包括：

- `kotlin("jvm")`：Kotlin JVM 编译；
- `kotlin("plugin.spring")`：让 Kotlin 类更好地配合 Spring；
- `kotlin("kapt")`：Kotlin 注解处理。

另外三个插件分别用于：

- `org.jlleitschuh.gradle.ktlint`：Kotlin 代码格式检查；
- `com.github.ben-manes.versions`：检查依赖是否有新版本；
- `org.jreleaser`：发布、生成 changelog、打包分发、构建 Docker 镜像。

第三部分是 `isNonStable(version: String)`：

```kotlin
fun isNonStable(version: String): Boolean {
  val stableKeyword = listOf("RELEASE", "FINAL", "GA").any { version.uppercase().contains(it) }
  val unstableKeyword = listOf("ALPHA", "RC").any { version.uppercase().contains(it) }
  val regex = "^[0-9,.v-]+(-r)?$".toRegex()
  val isStable = stableKeyword || regex.matches(version)
  return unstableKeyword || !isStable
}
```

这是一个版本稳定性判断函数。它把包含 `RELEASE`、`FINAL`、`GA` 的版本视为稳定版本，也把纯数字、点号、逗号、`v`、短横线等组成的版本视为稳定版本；包含 `ALPHA`、`RC` 的版本视为不稳定版本。这个函数会被依赖升级检查任务调用，用来避免从稳定版本升级到候选版或 alpha 版。

第四部分是项目坐标：

```kotlin
group = "org.gotson"
```

这会给根项目设置 Maven group。子模块也可以自己设置，例如 `komga-tray/build.gradle.kts` 里也设置了 `group = "org.gotson"`。

第五部分是 `allprojects`：

```kotlin
allprojects {
  repositories {
    mavenCentral()
  }
  apply(plugin = "org.jlleitschuh.gradle.ktlint")
  apply(plugin = "com.github.ben-manes.versions")
  ...
}
```

这是根脚本对所有项目，包括根项目和子项目的统一配置。它做了几件事：

- 所有项目都使用 `mavenCentral()`；
- 所有项目都应用 `ktlint`；
- 所有项目都应用依赖版本检查插件；
- 所有项目都共享 `dependencyUpdates` 的过滤规则；
- 所有项目都使用同一套 ktlint 版本和排除规则。

`dependencyUpdates` 的重点配置是：

```kotlin
rejectVersionIf {
  isNonStable(candidate.version) && !isNonStable(currentVersion)
}
gradleReleaseChannel = "current"
checkConstraints = true
```

意思是：如果当前依赖是稳定版，而候选升级版本是不稳定版，就拒绝这个候选版本。这样运行依赖升级检查时，不会轻易提示把稳定依赖升级到 `alpha`、`RC` 等版本。`checkConstraints = true` 表示依赖约束也会参与检查。

`ktlint` 的配置是：

```kotlin
configure<org.jlleitschuh.gradle.ktlint.KtlintExtension> {
  version = "1.7.1"
  filter {
    exclude("**/generated-src/**")
    exclude("**/generated/**")
  }
}
```

这表示格式检查使用 ktlint `1.7.1`，同时跳过生成代码目录。生成代码通常不是人工维护的，如果强行检查容易造成无意义失败。

第六部分是 Gradle Wrapper：

```kotlin
tasks.wrapper {
  gradleVersion = "8.14.3"
  distributionType = Wrapper.DistributionType.ALL
}
```

这会控制 `./gradlew wrapper` 生成或更新 Wrapper 时使用 Gradle `8.14.3`，并下载 `ALL` 发行包。`ALL` 包含源码和文档，比 `BIN` 更适合 IDE 跳转和调试 Gradle API。

第七部分是 `jreleaser`，这是文件中最大的一块。它包含项目元信息、GitHub Release、changelog、issue 处理、分发包和 Docker 打包配置。

项目元信息：

```kotlin
project {
  description = "Media server for comics/mangas/BDs with API and OPDS support"
  copyright = "Gauthier Roebroeck"
  authors.add("Gauthier Roebroeck")
  license = "MIT"
  links {
    homepage = "[URL已移除]"
  }
}
```

这说明 Komga 是一个面向 comics、mangas、BDs 的媒体服务器，提供 API 和 OPDS 支持，许可证是 MIT。

GitHub Release 配置中比较关键的是：

```kotlin
skipTag = true
tagName = "{{projectVersion}}"
```

这表示 JReleaser 使用项目版本作为 tag 名，但不负责创建 tag。根据当前片段推断，tag 可能由外部 CI 或其他发布流程提前创建，依据是 `skipTag = true` 明确关闭了 JReleaser 打 tag 的动作。

`changelog` 配置负责生成发布说明。它使用 `conventional-commits` 预设，跳过 merge commits，并启用链接。它还会在存在 `release_notes/release_notes.md` 时，把这个文件内容插入到 release note 前面：

```kotlin
content = (if (Path("./release_notes/release_notes.md").exists()) "{{#f_file_read}}{{basedir}}/release_notes/release_notes.md{{/f_file_read}}" else "") + ...
```

这是一种“手写发布说明 + 自动 changelog”的组合方式。如果没有手写文件，就只生成自动 changelog。

changelog 还定义了分类：

- `perf` 显示为 `🏎 Perf`；
- `i18n` 显示为 `🌐 Translation`；
- `dependencies` 显示为 `⚙️ Dependencies`。

对应的 `labeler` 会根据 commit title 的正则自动打标签。例如 `perf(...)` 会进入性能分类，`i18n(...)` 会进入翻译分类，`deps(...)` 会进入依赖分类。

`append` 配置会把 changelog 追加到根目录的 `CHANGELOG.md`：

```kotlin
target = rootDir.resolve("CHANGELOG.md")
```

也就是说，发布流程不仅生成 GitHub Release 内容，还会维护仓库内的 changelog 文件。

`issues` 配置表示发布后会处理 GitHub issue：

```kotlin
enabled = true
comment = "🎉 This issue has been resolved in `{{tagName}}` ([Release Notes]({{releaseNotesUrl}}))"
applyMilestone = Apply.ALWAYS
```

当 changelog 识别到关联 issue 时，JReleaser 可以评论 issue、设置 milestone，并添加 `released` 标签。

`distributions` 定义了一个名为 `komga` 的分发：

```kotlin
create("komga") {
  active = Active.RELEASE
  distributionType = SINGLE_JAR
  artifact {
    path = rootDir.resolve("komga/build/libs/komga-{{projectVersion}}.jar")
  }
}
```

这说明发布产物是 `komga` 模块构建出来的单个 JAR，路径形如：

```text
komga/build/libs/komga-1.24.4.jar
```

其中 `1.24.4` 来自 `gradle.properties` 的 `version`。

`packagers.docker` 配置 Docker 镜像构建：

```kotlin
templateDirectory = rootDir.resolve("komga/docker")
imageNames =
  listOf(
    "komga:latest",
    "komga:{{projectVersion}}",
    "komga:{{projectVersionMajor}}.x",
  )
```

Docker 模板目录在 `komga/docker`，镜像 tag 包括：

- `komga:latest`
- `komga:<完整版本号>`
- `komga:<主版本>.x`

它启用了 buildx，并构建三个平台：

```kotlin
"linux/amd64",
"linux/arm/v7",
"linux/arm64/v8"
```

镜像注册表配置了 `docker.io` 和 `ghcr.io`，并且 `externalLogin = true`，说明登录凭据应由外部环境或 CI 提供，而不是在这个脚本里硬编码。

## 上下游关系

上游配置主要来自几个文件和目录。

`settings.gradle` 决定根脚本覆盖哪些子项目：

```gradle
include 'komga'
include 'komga-tray'
```

所以 `allprojects` 中的仓库、ktlint、依赖升级检查会作用到根项目、`komga` 和 `komga-tray`。

`gradle.properties` 提供项目版本：

```properties
version=1.24.4
```

JReleaser 使用这个版本生成 release tag、changelog 标题、单 JAR 路径和 Docker 镜像标签。

`gradle/libs.versions.toml` 虽然当前没有展开读取，但从子模块脚本可以看到 `libs.versions.springboot`、`libs.plugins.gradleGitProperties` 等写法，因此依赖版本目录也是构建系统的重要上游。根据当前片段推断，版本目录被 Gradle 自动加载，子模块通过 `libs` 访问统一版本。

下游主要是两个子模块。

`komga/build.gradle.kts` 是服务端主体模块。它应用根脚本声明过版本的 Kotlin 插件：

```kotlin
plugins {
  kotlin("jvm")
  kotlin("plugin.spring")
  kotlin("kapt")
  ...
}
```

因为根脚本已经在 `plugins` 块里声明了这些插件版本，子模块可以直接使用插件而不重复写版本。`komga` 还应用 Spring Boot、jOOQ、Flyway、OpenAPI、KSP、JaCoCo 等插件，说明它承担主要服务端构建、数据库迁移、代码生成、测试覆盖率和 API 文档任务。

`komga` 模块还和前端目录 `komga-webui` 有构建关系。它定义了 `npmInstall`、`npmBuild`、`copyWebDist`、`prepareThymeLeaf` 等任务，把 `komga-webui/dist` 复制进 `komga/src/main/resources/public/`，再处理 `index.html` 中的资源路径，使其适配 Thymeleaf。根脚本的 JReleaser 最后引用的 JAR 正是 `komga/build/libs/komga-{{projectVersion}}.jar`。

`komga-tray/build.gradle.kts` 是桌面端/托盘端模块。它依赖：

```kotlin
implementation(project(":komga"))
```

这表示 `komga-tray` 直接复用 `komga` 模块。它还使用 JetBrains Compose、Conveyor 和 `application` 插件，入口类是：

```kotlin
mainClass = "org.gotson.komga.DesktopApplicationKt"
```

因此根脚本的全局插件和仓库配置为 `komga-tray` 提供基础环境，但桌面应用的具体打包逻辑主要在 `komga-tray/build.gradle.kts`。

发布侧的下游是：

- GitHub Release；
- GitHub Issues；
- `CHANGELOG.md`；
- `komga/build/libs/komga-{{projectVersion}}.jar`；
- `komga/docker`；
- Docker Hub；
- GitHub Container Registry。

## 运行/调用流程

普通开发构建时，流程大致是：

1. Gradle 读取 `settings.gradle`，知道当前构建包含 `komga` 和 `komga-tray`。
2. Gradle 加载根 `build.gradle.kts`，注册 Kotlin、ktlint、versions、jreleaser 等插件版本。
3. `allprojects` 对根项目和所有子项目统一配置 `mavenCentral()`、`ktlint` 和依赖升级检查。
4. Gradle 加载子模块脚本，例如 `komga/build.gradle.kts`、`komga-tray/build.gradle.kts`。
5. 子模块声明自己的插件、依赖、编译目标、测试任务和应用入口。
6. 执行具体任务，例如 `build`、`test`、`ktlintCheck`、`dependencyUpdates`、`jreleaserRelease` 等。

执行依赖升级检查时，核心流程是：

1. `com.github.ben-manes.versions` 插件提供 `dependencyUpdates` 任务。
2. 根脚本对所有项目的 `dependencyUpdates` 任务进行配置。
3. 插件扫描依赖的新版本。
4. `rejectVersionIf` 调用 `isNonStable(candidate.version)` 和 `isNonStable(currentVersion)`。
5. 如果当前版本稳定、候选版本不稳定，就拒绝这个候选升级建议。
6. 最终报告更偏向稳定升级路径。

执行代码风格检查时，流程是：

1. 所有项目都应用 `org.jlleitschuh.gradle.ktlint`。
2. ktlint 版本固定为 `1.7.1`。
3. 扫描 Kotlin 源码。
4. 跳过 `**/generated-src/**` 和 `**/generated/**`。
5. 报告格式问题，或配合格式化任务修复问题。

执行发布时，流程大致是：

1. 先由 `komga` 模块构建出 JAR，例如 `komga/build/libs/komga-1.24.4.jar`。
2. JReleaser 读取根脚本中的 `project` 元信息。
3. GitHub release 使用 `version` 作为 `tagName`。
4. 如果存在 `release_notes/release_notes.md`，先把手写发布说明插入 release 内容。
5. JReleaser 根据 conventional commits 生成 changelog。
6. changelog 追加写入 `CHANGELOG.md`。
7. 根据 issue 关联信息评论 issue、应用 milestone、添加 `released` 标签。
8. JReleaser 把 `komga` 分发定义为 `SINGLE_JAR`。
9. Docker packager 使用 `komga/docker` 模板，通过 buildx 构建多架构镜像。
10. 镜像按 `latest`、完整版本、主版本 `.x` 打 tag，并推送到外部登录好的 registry。

## 小白阅读顺序

建议先读 `settings.gradle`。这个文件只有两行，但它告诉你整个 Gradle 工程由哪些模块组成：`komga` 和 `komga-tray`。理解模块边界之后，再看根脚本会容易很多。

第二步读 `gradle.properties`。重点看 `version=1.24.4`，因为根 `build.gradle.kts` 的发布配置大量使用 `{{projectVersion}}`。如果不知道版本来自哪里，很容易误以为版本写死在发布脚本里。

第三步读 `build.gradle.kts` 的 `plugins` 块。这里能看出整个仓库的基础技术栈：Kotlin JVM、Kotlin Spring、kapt、ktlint、dependency versions、JReleaser。读完这一段，就知道根脚本不是业务模块脚本，而是全局构建和发布脚本。

第四步读 `isNonStable` 和 `dependencyUpdates` 配置。这个部分很适合理解“工具任务如何被定制”。它展示了项目如何避免依赖升级报告推荐不稳定版本。

第五步读 `allprojects`。这里是根脚本影响子模块的关键。凡是写在 `allprojects` 里的配置，都会传递到 `komga` 和 `komga-tray`。阅读时要特别注意哪些配置是全局共享的，哪些配置只属于子模块。

第六步读 `tasks.wrapper`。这段很短，但能知道团队期望使用的 Gradle 版本是 `8.14.3`，并且使用 `ALL` 发行包。

第七步读 `jreleaser.project` 和 `jreleaser.release.github`。先理解发布元信息和 GitHub Release 行为，再看 changelog 的格式、分类和 issue 自动处理。

第八步读 `jreleaser.distributions`。这里连接到了 `komga/build/libs/komga-{{projectVersion}}.jar`，因此你需要再去看 `komga/build.gradle.kts`，理解这个 JAR 是如何由服务端模块构建出来的。

第九步读 `jreleaser.packagers.docker`。这部分连接到 `komga/docker`，并解释为什么发布流程会生成多架构 Docker 镜像。

第十步再回头读 `komga/build.gradle.kts` 和 `komga-tray/build.gradle.kts`。此时你会更容易区分：根脚本负责统一规则和发布，子模块脚本负责具体应用的依赖、编译、测试、打包和运行入口。

## 常见误区

第一个误区是把根 `build.gradle.kts` 当成 `komga` 服务端模块的构建脚本。实际上，服务端主体依赖、Spring Boot 插件、数据库迁移、OpenAPI、前端构建集成都在 `komga/build.gradle.kts`。根脚本只提供全局规则和发布配置。

第二个误区是认为 `plugins` 里声明了 Kotlin 插件，就等于根项目一定编译业务代码。根脚本声明插件版本，子模块可以复用这些版本。真正的业务代码编译主要发生在 `komga` 和 `komga-tray`。

第三个误区是忽略 `allprojects` 的影响范围。`allprojects` 不只影响当前根项目，也影响子项目。因此 `mavenCentral()`、ktlint、依赖升级检查都会作用到 `komga` 和 `komga-tray`。

第四个误区是以为 `dependencyUpdates` 会推荐所有最新版本。实际上它通过 `rejectVersionIf` 过滤掉了一类升级：当前版本稳定、候选版本不稳定时，不推荐升级。这能降低误升到 alpha、RC 的风险。

第五个误区是以为 `isNonStable` 能精确理解所有版本语义。它只是基于字符串规则判断稳定性，例如包含 `ALPHA`、`RC` 视为不稳定，匹配数字型版本或包含 `RELEASE`、`FINAL`、`GA` 视为稳定。特殊版本命名可能被误判，这是这种轻量规则的天然限制。

第六个误区是认为 JReleaser 会创建 Git tag。这里配置了 `skipTag = true`，说明它不会负责创建 tag，只会使用 `{{projectVersion}}` 作为 tag 名参与发布流程。tag 的创建很可能由外部流程完成，这是根据当前片段推断，依据是脚本明确跳过 tag 创建。

第七个误区是把 `release_notes/release_notes.md` 当成必需文件。脚本会先检查它是否存在，存在时才读取并插入发布说明；不存在时自动 changelog 仍然可以生成。

第八个误区是认为 Docker 发布只构建当前机器架构。这里启用了 `buildx`，并声明了 `linux/amd64`、`linux/arm/v7`、`linux/arm64/v8` 三个平台，所以发布目标是多架构镜像。

第九个误区是认为 Docker registry 登录信息在 Gradle 脚本中配置。这里 `docker.io` 和 `ghcr.io` 都设置了 `externalLogin = true`，说明认证来自外部环境，通常是开发者本机或 CI 的登录状态/密钥。

第十个误区是忽略 `komga-webui`。虽然 `settings.gradle` 没有 include `komga-webui`，但 `komga/build.gradle.kts` 通过 npm 任务构建前端，并把产物复制到服务端资源目录。因此它不是 Gradle 子模块，却仍然参与最终 `komga` JAR 的构建内容。
