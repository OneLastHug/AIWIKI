# 目录：komga-tray/src/main

## 它负责什么

`komga-tray/src/main` 是 Komga 桌面托盘版本的主程序源码目录，主要负责把原本偏服务端形态的 Komga 包装成一个桌面应用入口。它不是 Web 前端，也不是核心业务服务实现，而是“桌面启动器 + 系统托盘 + 错误窗口 + 平台配置”的组合层。

从目录结构和构建入口看，`komga-tray` 使用 Kotlin/JVM 与 JetBrains Compose Desktop。`komga-tray/build.gradle.kts` 中的 `application.mainClass` 指向 `org.gotson.komga.DesktopApplicationKt`，因此 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt` 是这个模块的应用入口。该入口向下连接 Komga 主应用或服务启动逻辑，向上提供桌面用户可见的托盘图标、菜单和错误提示窗口。

这个目录解决的问题可以概括为：

- 在 Windows/macOS 等桌面系统中启动 Komga。
- 通过系统托盘提供常驻入口。
- 在启动失败或运行异常时展示图形化错误信息。
- 加载平台相关配置，例如 `application-mac.yml`、`application-windows.yml`。
- 提供图标资源和多语言文案资源。

## 关键组成

`komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt` 是桌面应用的主入口。构建脚本把它编译后的 `DesktopApplicationKt` 作为 `mainClass`，说明它里面大概率定义了 Kotlin 顶层 `main` 函数。根据当前片段可见，它会导入 `org.gotson.komga.application.gui.showErrorDialog`，因此入口启动过程中如果发生异常，会转入 Compose Desktop 的错误弹窗逻辑。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt` 是托盘图标运行器。它位于 `application.gui` 包下，使用 `androidx.compose.ui.window.Tray`、`androidx.compose.ui.window.application`，并通过 `org.jetbrains.compose.resources.decodeToSvgPainter` 加载 SVG 图标。它的职责是创建系统托盘图标、绑定托盘菜单动作，并维持桌面 Compose 应用事件循环。根据文件名和依赖推断，`TrayIconRunner` 不是核心服务，而是 GUI 包装层。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt` 是错误弹窗组件。它使用 Compose Desktop 的 `Window`、`WindowState`、`Button`、`TextButton`、`TextField`、`Image` 等组件，并使用 `LocalClipboardManager`。这说明错误窗口不只是显示一行错误，还可能展示异常详情，并提供复制错误信息的能力。它同样使用 `decodeToSvgPainter` 读取 Komga 图标，让错误窗口与托盘应用保持一致的视觉身份。

`komga-tray/src/main/kotlin/org/gotson/komga/RB.kt` 从命名看是 resource bundle 的缩写，通常用于读取 `messages.properties` 这类国际化资源。该目录下存在大量 `messages_*.properties` 文件，例如 `messages_fr.properties`、`messages_ja.properties`、`messages_zh` 未在当前片段中出现，但有多语言集合。根据当前片段推断，`RB.kt` 为托盘菜单、按钮、错误窗口标题等文本提供本地化读取能力。

`komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt` 是工具函数集合。由于当前任务限制下没有展开源码内容，只能根据位置和命名推断：它可能包含平台判断、资源读取、URL 打开、进程退出、路径处理或 Compose 图标加载辅助方法。判断依据是它位于顶层包 `org.gotson.komga`，而 GUI 子包只保留具体界面组件。

`komga-tray/src/main/resources/application-mac.yml` 和 `komga-tray/src/main/resources/application-windows.yml` 是平台相关 Spring/应用配置。片段显示它们包含对 `${komga.config-dir}` 下 `application.yml`、`application.yaml`、`application.properties` 的 optional import。这表示托盘应用仍然遵循 Komga 的外部配置覆盖机制：打包内置默认配置，同时允许用户在配置目录中放置自定义配置文件。

`komga-tray/src/main/resources/icons/komga-color.svg` 和 `komga-tray/src/main/resources/icons/komga-gray-minimal.svg` 是托盘和窗口使用的图标资源。`TrayIconRunner.kt` 和 `ErrorDialog.kt` 都使用 Compose resources 的 SVG 解码能力，说明这些图标会在运行时作为桌面 UI 资源加载。

`komga-tray/src/main/resources/org/gotson/komga/messages*.properties` 是国际化文案。它们和 `RB.kt` 形成配套关系：资源文件存储不同语言的 key-value 文案，Kotlin 代码通过 resource bundle 按当前 locale 读取。

## 上下游关系

上游入口来自构建和启动系统。`komga-tray/build.gradle.kts` 使用 `application` 插件，并声明 `mainClass = "org.gotson.komga.DesktopApplicationKt"`。当用户运行桌面包、Gradle application 任务，或者最终通过打包工具生成安装包时，JVM 首先进入这个 main class。

`DesktopApplication.kt` 的下游有两类。

第一类是 Komga 核心服务。根据模块名 `komga-tray` 和包名 `org.gotson.komga` 推断，桌面入口会启动或委托启动 Komga 后端应用，让用户访问本机运行的 Komga 服务。这个核心服务的具体实现不在 `komga-tray/src/main` 目录内，而是在仓库其他模块中。`komga-tray/src/main` 更像是外壳层。

第二类是桌面 GUI 层，包括 `TrayIconRunner.kt` 和 `ErrorDialog.kt`。成功启动时进入托盘常驻逻辑；失败时进入错误窗口逻辑。`DesktopApplication.kt` 导入 `showErrorDialog` 是一个明确证据，说明错误展示是主入口异常处理链路的一部分。

资源层是这些 Kotlin 文件的共同下游依赖。GUI 代码读取 `icons/*.svg`；文案读取 `messages*.properties`；运行配置读取 `application-*.yml`。这些资源不直接包含业务逻辑，但会影响托盘行为、窗口显示和平台默认配置。

平台层也参与关系链。`application-mac.yml` 和 `application-windows.yml` 说明托盘应用在不同操作系统下有不同配置入口。结合 `komga-tray/conveyor/required-jdk-modules.txt` 可知，该模块还面向桌面分发/安装包场景，需要显式控制运行时 JDK 模块集合。

## 运行/调用流程

典型运行流程如下：

1. 启动器进入 `org.gotson.komga.DesktopApplicationKt`。
2. `DesktopApplication.kt` 初始化桌面版 Komga 的运行环境。
3. 根据当前平台或 profile 读取 `application-mac.yml`、`application-windows.yml` 这类配置。
4. 配置文件继续尝试导入 `${komga.config-dir}/application.yml`、`${komga.config-dir}/application.yaml`、`${komga.config-dir}/application.properties`，让用户配置覆盖内置配置。
5. 主入口启动 Komga 后端服务。此处根据模块定位推断，实际服务实现来自仓库其他 Komga 模块，而不是 `komga-tray/src/main` 本身。
6. GUI 层启动 `TrayIconRunner`，通过 Compose Desktop 的 `application { ... }` 创建桌面事件循环。
7. `TrayIconRunner` 使用 `Tray` 创建系统托盘图标，图标资源来自 `icons/komga-color.svg` 或 `icons/komga-gray-minimal.svg`。
8. 托盘菜单中的文本通过 `RB.kt` 和 `messages*.properties` 获取，以适配不同语言。
9. 如果启动过程或托盘运行过程出现异常，入口调用 `showErrorDialog`。
10. `ErrorDialog.kt` 使用 Compose Desktop 创建错误窗口，展示错误说明和详情，并可能允许复制错误信息到剪贴板。

可以把它理解成三层：

- 启动层：`DesktopApplication.kt`
- 桌面交互层：`TrayIconRunner.kt`、`ErrorDialog.kt`
- 资源/配置层：`application-*.yml`、`icons/*.svg`、`messages*.properties`

## 小白阅读顺序

建议先看 `komga-tray/build.gradle.kts`。重点关注插件、依赖和 `application.mainClass`。这里能确认这个模块是 Compose Desktop + Kotlin 应用，也能确认真正入口是 `DesktopApplication.kt`。

第二步看 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。阅读时只抓三个问题：main 函数在哪里、它如何启动 Komga、异常时如何处理。看到 `showErrorDialog` 时不要急着深入 Compose 细节，先确认它在什么 catch 或错误分支里被调用。

第三步看 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`。重点理解 `application {}` 和 `Tray` 的关系：前者是 Compose Desktop 的应用生命周期，后者是系统托盘组件。托盘菜单项一般会对应打开浏览器、退出程序、显示状态等动作。

第四步看 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt`。这里可以学习 Compose Desktop 窗口如何写：`Window` 管窗口，`WindowState` 管大小和位置，`Column`、`Row` 管布局，`Button` 和 `TextButton` 管操作，`LocalClipboardManager` 管复制。

第五步看 `komga-tray/src/main/kotlin/org/gotson/komga/RB.kt` 和 `komga-tray/src/main/resources/org/gotson/komga/messages.properties`。先看默认英文或主语言资源，再对照其他 `messages_*.properties`，理解 key 如何映射到不同语言文案。

第六步看 `komga-tray/src/main/resources/application-mac.yml` 和 `komga-tray/src/main/resources/application-windows.yml`。重点看配置导入路径和平台差异。这里不需要一开始就深挖所有 Spring 配置项，先理解“内置配置 + 用户配置覆盖”的机制。

## 常见误区

不要把 `komga-tray/src/main` 当成 Komga 的核心业务实现目录。它主要是桌面托盘壳层，真正的漫画库管理、API、数据库、扫描、元数据等逻辑应在仓库其他模块中。

不要以为 Compose Desktop 这里负责渲染 Komga Web UI。`TrayIconRunner.kt` 和 `ErrorDialog.kt` 只负责系统托盘与错误窗口。Komga 的主要 Web 界面大概率仍由浏览器访问本地服务来完成。

不要忽略 `application-mac.yml` 和 `application-windows.yml`。桌面应用启动失败时，很多问题可能来自平台配置、配置目录、端口、数据目录，而不一定是托盘 UI 代码错误。

不要把 `messages*.properties` 看成无关文件。托盘菜单、错误按钮、窗口标题这类文案如果通过 `RB.kt` 读取，改代码时必须同步维护资源 key，否则会出现缺文案或回退显示的问题。

不要把 SVG 图标路径随意改名。`TrayIconRunner.kt` 和 `ErrorDialog.kt` 通过 Compose resources 读取图标，资源路径变化会直接影响托盘图标或错误窗口图标加载。

不要在阅读 `ErrorDialog.kt` 时陷入所有 Compose 布局细节。对这个目录的主线理解来说，先抓住“异常进入图形化错误展示”即可；布局尺寸、按钮排列、预览函数是第二层细节。

不要假设所有平台行为一致。这个目录明确存在 macOS 和 Windows 的独立配置文件，托盘、退出、窗口、配置目录等行为在桌面系统之间可能不同。根据当前片段推断，平台差异是 `komga-tray` 设计时已经考虑的内容。
