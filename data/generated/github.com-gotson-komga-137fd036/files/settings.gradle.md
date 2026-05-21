# 文件：settings.gradle

## 它负责什么

`settings.gradle` 是这个仓库的 Gradle 多项目入口配置文件。Gradle 在加载任何 `build.gradle.kts` 之前，会先读取它，用来确定“这个构建包含哪些项目”。

当前文件内容非常短：

```groovy
include 'komga'
include 'komga-tray'
```

它的核心职责只有一个：把仓库中的两个子工程注册进同一个 Gradle build：

- `komga`：主应用工程，从 `README.md` 和 `komga/build.gradle.kts` 可见，它是 Komga 的核心服务端应用，基于 Kotlin、Spring Boot、jOOQ、Flyway、Lucene、SQLite、Web UI 构建流程等组成。
- `komga-tray`：桌面托盘/桌面包装工程，从 `komga-tray/build.gradle.kts` 可见，它使用 JetBrains Compose Desktop、Conveyor，并通过 `implementation(project(":komga"))` 依赖主应用工程。

也就是说，`settings.gradle` 本身不定义依赖、不声明插件、不配置任务，它只告诉 Gradle：“这个仓库不是单模块项目，而是包含 `:komga` 和 `:komga-tray` 两个 Gradle project 的多模块项目。”

## 关键组成

这个文件使用的是 Gradle Groovy DSL，而不是 Kotlin DSL。判断依据是文件名为 `settings.gradle`，不是 `settings.gradle.kts`，并且语法是：

```groovy
include 'komga'
```

而不是 Kotlin DSL 常见的：

```kotlin
include("komga")
```

关键语句有两行。

第一行：

```groovy
include 'komga'
```

它将仓库根目录下的 `komga/` 目录注册为 Gradle 子项目，项目路径为 `:komga`。之后 Gradle 才会去加载 `komga/build.gradle.kts`，并让用户可以执行类似：

```bash
./gradlew :komga:build
./gradlew :komga:bootJar
./gradlew :komga:test
```

这类带项目路径的任务。

第二行：

```groovy
include 'komga-tray'
```

它将仓库根目录下的 `komga-tray/` 目录注册为另一个 Gradle 子项目，项目路径为 `:komga-tray`。之后 Gradle 会加载 `komga-tray/build.gradle.kts`，使桌面端相关任务进入构建图中，例如 application、Compose Desktop、Conveyor 相关任务。

这个文件没有显式设置：

```groovy
rootProject.name = '...'
```

因此根据当前片段推断，Gradle 会使用根目录名作为默认 root project name。这里源码目录名是 `source`，但这通常只影响 Gradle 内部显示名称，不影响 `:komga`、`:komga-tray` 这两个子项目路径。

它也没有配置：

```groovy
pluginManagement { ... }
dependencyResolutionManagement { ... }
```

说明插件版本、仓库、依赖管理主要分散在根 `build.gradle.kts`、子工程 `build.gradle.kts`、`gradle/libs.versions.toml` 或相关 Gradle 默认机制中，而不是集中在 settings 文件里。

## 上下游关系

`settings.gradle` 的上游是 Gradle 启动流程本身。当执行任意 Gradle 命令时，例如：

```bash
./gradlew build
./gradlew projects
./gradlew :komga:bootRun
```

Gradle 会先读取 `settings.gradle`，建立项目结构。只有项目结构建立后，Gradle 才知道有哪些 `Project` 对象需要创建，哪些 `build.gradle.kts` 文件需要参与配置。

它的直接下游是三个层级。

第一层是根构建脚本 `build.gradle.kts`。根脚本里配置了全局插件、`allprojects`、仓库、ktlint、dependency updates、Gradle wrapper、JReleaser 发布逻辑等。由于 `settings.gradle` 把 `komga` 和 `komga-tray` 纳入构建，根脚本中的：

```kotlin
allprojects {
  repositories {
    mavenCentral()
  }
  apply(plugin = "org.jlleitschuh.gradle.ktlint")
  apply(plugin = "com.github.ben-manes.versions")
}
```

会作用到根项目和这些子项目上。

第二层是 `komga/build.gradle.kts`。它是主服务工程的构建定义，包含 Kotlin、Spring Boot、jOOQ、Flyway、OpenAPI、KSP、Jacoco、前端构建集成等大量配置。没有 `include 'komga'`，这个文件就不会作为 `:komga` 项目的构建脚本进入当前 Gradle build。

第三层是 `komga-tray/build.gradle.kts`。它是桌面端工程的构建定义，使用 Compose Desktop 和 Conveyor，并且声明：

```kotlin
implementation(project(":komga"))
```

这说明 `:komga-tray` 是 `:komga` 的下游消费者。它依赖 `:komga` 产出的代码或类路径，把主应用能力包装到桌面入口中。如果 `settings.gradle` 没有包含 `komga`，那么 `project(":komga")` 将无法解析；如果没有包含 `komga-tray`，桌面端项目则不会出现在构建中。

从产品层面看，`README.md` 描述 Komga 是面向 comics、mangas、BDs、magazines、eBooks 的媒体服务器。`settings.gradle` 把这个产品拆成两个构建单元：一个核心服务端应用，一个桌面托盘/桌面包装应用。

## 运行/调用流程

一次典型 Gradle 调用可以按下面顺序理解。

1. 用户在仓库根目录执行 Gradle 命令，例如：

```bash
./gradlew build
```

2. Gradle wrapper 启动指定版本的 Gradle。根 `build.gradle.kts` 中的 wrapper 配置显示该仓库使用 Gradle `8.14.3`：

```kotlin
tasks.wrapper {
  gradleVersion = "8.14.3"
  distributionType = Wrapper.DistributionType.ALL
}
```

3. Gradle 进入 initialization 阶段，读取 `settings.gradle`。

4. `settings.gradle` 执行两条 `include` 语句，注册两个子项目：

```text
:komga
:komga-tray
```

5. Gradle 进入 configuration 阶段，依次配置根项目、`:komga`、`:komga-tray`。这时才会读取：

```text
build.gradle.kts
komga/build.gradle.kts
komga-tray/build.gradle.kts
```

6. 根项目的 `allprojects` 配置会应用到所有项目，例如仓库、ktlint、dependencyUpdates 等。

7. 子项目自己的构建脚本继续补充各自特有任务和依赖。比如 `:komga` 配置 Spring Boot、数据库迁移、前端构建；`:komga-tray` 配置 Compose Desktop、application，并声明依赖 `project(":komga")`。

8. Gradle 根据用户请求的任务构建任务图。如果执行：

```bash
./gradlew :komga-tray:build
```

那么由于 `komga-tray/build.gradle.kts` 中有：

```kotlin
implementation(project(":komga"))
```

Gradle 会把 `:komga` 的相关编译产物纳入 `:komga-tray` 的 classpath，必要时先构建 `:komga`。

如果执行：

```bash
./gradlew :komga:build
```

则主要进入服务端应用构建链，包括 Kotlin 编译、测试、资源处理、可能的前端资源准备等。

如果执行：

```bash
./gradlew projects
```

Gradle 会基于 `settings.gradle` 输出当前 build 中的项目树，理论上能看到根项目以及 `:komga`、`:komga-tray` 两个子项目。

## 小白阅读顺序

建议先不要急着看 `komga/build.gradle.kts` 里的大量依赖和任务。这个仓库的 Gradle 结构可以按从小到大的顺序读。

第一步，读 `settings.gradle`。先记住这个仓库只有两个被 Gradle 注册的子项目：

```text
:komga
:komga-tray
```

这一步的目的不是理解业务，而是建立构建地图。

第二步，读根目录 `README.md`。它告诉你 Komga 是什么：一个 comics、mangas、BDs、magazines、eBooks 的媒体服务器，提供 Web UI、REST API、OPDS、Kobo Sync、KOReader Sync、用户权限、元数据管理等能力。这样再看构建文件时，就知道 `komga` 不是普通库，而是主应用。

第三步，读根目录 `build.gradle.kts`。重点看这些部分：

```kotlin
plugins { ... }
allprojects { ... }
tasks.wrapper { ... }
jreleaser { ... }
```

这里能理解全仓库共享的构建规则：Kotlin 版本、ktlint、依赖更新检查、Maven 仓库、发布配置、Docker 打包等。

第四步，读 `komga/build.gradle.kts`。这是主工程。建议先看顶部 `plugins`，再看 `dependencies`，最后看 `tasks`。不要一开始就陷入每个依赖的细节，先把它分成几块：Spring Boot 服务端、数据库与 jOOQ/Flyway、文件/图片/压缩处理、搜索、测试、Web UI 构建集成。

第五步，读 `komga-tray/build.gradle.kts`。这个文件比主工程小很多，重点看：

```kotlin
implementation(project(":komga"))
application {
  mainClass = "org.gotson.komga.DesktopApplicationKt"
}
```

这两处能说明桌面工程不是独立重写业务，而是复用 `:komga`，再提供桌面启动入口和平台打包能力。

第六步，如果继续深入源码，再从 `komga/src` 和 `komga-tray/src` 找应用入口类、Spring Boot 配置、桌面入口。`settings.gradle` 只提供项目边界，不负责具体业务入口。

## 常见误区

第一个误区：以为 `settings.gradle` 是依赖管理文件。  
它不是。当前文件没有声明任何 Maven 依赖，也没有版本号。依赖主要在 `komga/build.gradle.kts`、`komga-tray/build.gradle.kts` 以及版本目录相关文件中维护。`settings.gradle` 只决定哪些目录是 Gradle 项目。

第二个误区：以为目录存在就会自动成为 Gradle 子项目。  
不会。Gradle 多项目构建需要通过 `include` 显式注册。仓库里即使有其他目录，比如前端、文档、脚本、Docker 相关目录，只要没有在 `settings.gradle` 中 `include`，它们就不是独立 Gradle 子项目。它们可以被任务使用，例如 `komga/build.gradle.kts` 中通过 `webui = "$rootDir/komga-webui"` 使用前端目录，但这不等于 `komga-webui` 是 Gradle project。

第三个误区：以为 `include 'komga'` 会自动建立 `komga-tray` 对 `komga` 的依赖。  
不会。`include` 只是注册项目。真正的项目依赖写在 `komga-tray/build.gradle.kts` 中：

```kotlin
implementation(project(":komga"))
```

如果只有 `include 'komga'` 和 `include 'komga-tray'`，但没有这条依赖声明，Gradle 只知道两个项目同属一个 build，并不知道它们的编译依赖关系。

第四个误区：以为 `settings.gradle` 会配置 Spring Boot、Compose、Kotlin 编译参数。  
不会。这些配置分别在根 `build.gradle.kts`、`komga/build.gradle.kts`、`komga-tray/build.gradle.kts` 中。比如 JVM 目标版本 `17` 是在子项目构建脚本的 Kotlin/Java 配置里设置的，不在 `settings.gradle`。

第五个误区：看到根构建脚本是 `build.gradle.kts`，就以为 settings 也一定是 Kotlin DSL。  
当前不是。`settings.gradle` 使用 Groovy DSL，而其他构建脚本使用 Kotlin DSL。这种混用是 Gradle 支持的。阅读时要注意语法差异：`include 'komga'` 是 Groovy 写法，`include("komga")` 才是 Kotlin 写法。

第六个误区：忽略没有 `rootProject.name` 的影响。  
当前文件没有显式命名根项目。根据当前片段推断，Gradle 会采用根目录名作为 root project name。这通常不影响日常执行 `:komga:build`、`:komga-tray:build`，但在 IDE 导入、Gradle 输出、构建扫描或发布元数据中可能会看到默认根项目名。项目真正的 Maven/group 信息则由根 `build.gradle.kts` 中的：

```kotlin
group = "org.gotson"
```

以及子项目自身配置共同决定。
