# 目录：komga-tray/src/main/kotlin

## 它负责什么

`komga-tray/src/main/kotlin` 是 Komga 的桌面托盘启动层。它不是主业务服务本身，而是在桌面环境中包装并启动主 Komga Spring Boot 应用，同时提供系统托盘菜单、错误弹窗、打开浏览器、打开日志文件所在目录、打开配置目录等桌面集成功能。

从 `komga-tray/build.gradle.kts` 看，`komga-tray` 依赖 `project(":komga")`，也就是复用主模块里的 `Application`、配置、Web 服务、日志和业务能力；本目录只补充桌面壳层。应用入口配置为：

`application.mainClass = "org.gotson.komga.DesktopApplicationKt"`

因此真正的启动函数在 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt` 的顶层 `main(args: Array<String>)`。

## 关键组成

本目录主要分两层：

第一层是 `org.gotson.komga` 包下的启动与工具代码：

`DesktopApplication.kt` 定义桌面版 Spring Boot 入口。`DesktopApplication : Application()` 继承主模块的 `Application`，并标注 `@EnableAsync`，让托盘组件可以用异步方式启动，避免阻塞 Spring Boot 启动流程。`main` 中先调用 `checkTempDirectory()` 检查临时目录，然后设置几个系统属性：`apple.awt.UIElement=true` 用于 macOS 上把程序作为无 Dock 图标的 UI 元素运行；`org.jooq.no-logo`、`org.jooq.no-tips` 用于关闭 jOOQ 控制台提示。随后通过 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动应用，并设置 `headless(false)`，表示这是有图形界面的进程，不是纯后台服务。

`RB.kt` 是资源文案读取工具。它使用 `ResourceBundle.getBundle("org.gotson.komga.messages")` 读取 `komga-tray/src/main/resources/org/gotson/komga/messages*.properties`。`RB.getString(key, vararg args)` 支持无参数取文案，也支持用 SLF4J 的 `MessageFormatter.arrayFormat` 替换 `{}` 占位符。例如端口占用错误会使用 `error_message.port_in_use` 并传入端口号。

`Utils.kt` 是平台能力工具。`openUrl(url)` 使用 `java.awt.Desktop` 的 `BROWSE` 动作打开浏览器。`openExplorer(file)` 优先使用 `Desktop.Action.BROWSE_FILE_DIR` 打开文件所在位置；如果平台是 Windows，则回退到 `explorer.exe /select, "文件路径"`；如果都不支持，则只记录 warning 日志。

第二层是 `org.gotson.komga.application.gui` 包下的 Compose Desktop UI：

`ErrorDialog.kt` 提供 `showErrorDialog(text, stackTrace)`。当启动失败时，它会用 Compose Desktop 创建一个不可调整大小的窗口，显示 Komga 图标、错误文案、可选堆栈信息，以及关闭按钮。如果存在 `stackTrace`，窗口宽度设为 `800.dp`，并显示一个 `TextField`，同时提供 `Copy to clipboard` 按钮。

`TrayIconRunner.kt` 是托盘菜单核心。它是 Spring 组件：`@Component`，并通过 `@Profile("!test")` 排除测试环境。它实现 `ApplicationRunner`，Spring Boot 启动完成后会调用 `run(args)`。该方法标注 `@Async`，实际进入 `runTray()`，由 Compose Desktop 的 `application { Tray(...) }` 创建系统托盘图标和菜单。

托盘菜单包括四项：`Open Komga`、`Show log file`、`Open configuration directory`、`Quit Komga`。对应动作分别是打开本地 Komga URL、在文件管理器中定位日志文件、打开配置目录、退出 Compose 应用。

## 上下游关系

上游入口来自桌面打包或命令行启动。`komga-tray/build.gradle.kts` 的 `application.mainClass` 指向 `DesktopApplicationKt`，因此构建出的桌面程序会先进入 `DesktopApplication.kt` 的 `main`。

本目录向下游依赖主 Komga 服务模块。`DesktopApplication : Application()` 中的 `Application` 来自主模块 `:komga`，说明桌面版并没有重新定义 Spring Boot 应用主体，而是在主应用外面加了一层桌面启动器。`TrayIconRunner` 注入的 `WebServerEffectiveSettings` 也来自主模块，用于读取最终生效的服务端口和 servlet context path，然后拼出：

`[URL已移除]}${effectiveServletContextPath}`

这个 URL 就是托盘菜单里 `Open Komga` 打开的地址。

它还依赖 Spring 配置属性。`TrayIconRunner` 通过 `@Value("#{komgaProperties.configDir}")` 获取 Komga 配置目录，通过 `@Value("${logging.file.name}")` 获取日志文件路径。也就是说，托盘菜单中的“打开配置目录”和“显示日志文件”不是硬编码路径，而是读取运行期配置。

资源层位于 `komga-tray/src/main/resources`。文案来自 `org/gotson/komga/messages.properties` 及多语言变体，图标来自 `icons/komga-color.svg` 和 `icons/komga-gray-minimal.svg`。`TrayIconRunner` 会根据 active profile 是否包含 `mac` 决定使用灰色简化图标还是彩色图标。

## 运行/调用流程

启动流程可以按以下顺序理解：

1. 桌面程序进入 `DesktopApplicationKt.main(args)`。
2. `checkTempDirectory()` 先检查临时目录是否可用。这一步来自主模块的 `org.gotson.komga.infrastructure.util`，本目录只是调用。
3. 设置 macOS UI、jOOQ 输出相关系统属性。
4. 使用 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动 Spring Boot，并设置 `headless(false)`。
5. Spring Boot 启动主 Komga 应用，包括 Web 服务、配置、日志等主模块能力。
6. Spring 容器加载 `TrayIconRunner`。在非 `test` profile 下，它作为 `ApplicationRunner` 在应用启动完成后执行。
7. `TrayIconRunner.run()` 因为有 `@Async`，会异步调用 `runTray()`。
8. `runTray()` 创建 Compose Desktop `Tray`，加载图标，并注册菜单项。
9. 用户点击 `Open Komga` 时调用 `openUrl(komgaUrl)`，通过系统默认浏览器打开本机 Web UI。
10. 用户点击日志或配置目录菜单时调用 `openExplorer(file)`，交给系统文件管理器处理。
11. 用户点击 `Quit Komga` 时调用 `exitApplication()`，退出 Compose Desktop 托盘应用。

异常流程也很重要。`DesktopApplication.kt` 捕获 Spring 启动过程中的 `Exception`，然后看 `e.cause` 是否为 `PortInUseException`。如果是端口占用，显示本地化端口占用提示，不显示堆栈；如果是其他异常，显示通用错误，并把 `e.stackTraceToString()` 传给 `showErrorDialog`，让用户可以查看和复制堆栈信息。

## 小白阅读顺序

建议先读 `komga-tray/build.gradle.kts`，确认这个子模块的定位：它依赖 `:komga`，使用 Kotlin JVM、Compose Desktop、Conveyor，并把入口指向 `DesktopApplicationKt`。这能避免误以为这里包含完整后端业务。

第二步读 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。这是主线入口，重点看 `DesktopApplication : Application()`、`SpringApplicationBuilder`、`headless(false)`、异常捕获和 `showErrorDialog`。

第三步读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`。重点理解它如何从 Spring 注入配置、如何计算 `komgaUrl`、为什么 `run` 要标 `@Async`、托盘菜单每一项对应哪个工具函数。

第四步读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt`。这部分主要是 Compose Desktop UI 代码，理解窗口、图标、错误文本、堆栈复制按钮即可，不需要一开始深挖 Compose 布局细节。

第五步读 `RB.kt` 和 `Utils.kt`。`RB.kt` 解释所有菜单和错误文案从哪里来；`Utils.kt` 解释浏览器和文件管理器是如何被系统调用的。

最后再看 `komga-tray/src/main/resources/org/gotson/komga/messages.properties`、`komga-tray/src/main/resources/application-mac.yml`、`komga-tray/src/main/resources/application-windows.yml`、`komga-tray/src/main/resources/icons`。这些资源决定了不同平台的显示文案、profile 行为和托盘图标。

## 常见误区

第一个误区是把 `komga-tray` 当成 Komga 的后端核心。实际上它只是桌面入口和系统托盘层，真正的 Web 服务、业务逻辑、配置模型大多来自 `:komga` 主模块。本目录里的 `DesktopApplication` 继承主模块 `Application`，正说明它是在复用主应用。

第二个误区是认为 `Quit Komga` 一定等价于完整关闭 Spring Boot 服务。代码里菜单项调用的是 Compose Desktop 的 `exitApplication()`。根据当前片段推断，它主要退出 Compose 应用循环；是否会连带结束整个 JVM 和 Spring 上下文，需要结合 Compose Desktop 运行机制和打包方式确认，不能只从这一行绝对判断。

第三个误区是忽略 `@Async`。`TrayIconRunner.run()` 如果同步进入 Compose 的 `application { ... }` 事件循环，可能阻塞 Spring Boot 的 runner 流程。这里通过 `@EnableAsync` 和 `@Async` 配合，让托盘 UI 在异步线程中运行，是桌面壳层能和 Spring Boot 共存的关键。

第四个误区是把错误弹窗当成普通业务弹窗。`showErrorDialog` 只在启动异常捕获中被调用，特别是端口占用或未知启动失败。它不是 Web UI 的错误处理，也不是运行期业务错误提示。

第五个误区是认为文案硬编码在 Kotlin 里。实际菜单和错误文案通过 `RB.getString` 读取 `messages.properties` 及多语言资源。新增文案时需要同时考虑资源 key 和翻译文件，而不只是改 Kotlin 字符串。

第六个误区是认为打开文件管理器是跨平台完全一致的。`openExplorer` 优先使用 Java Desktop API，但 Windows 有专门的 `explorer.exe /select` 回退逻辑；其他不支持的平台只记录 warning。也就是说，这块行为依赖操作系统和 JVM 桌面能力。
