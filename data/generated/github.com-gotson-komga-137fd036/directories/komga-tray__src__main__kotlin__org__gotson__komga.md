# 目录：komga-tray/src/main/kotlin/org/gotson/komga

## 它负责什么

`komga-tray/src/main/kotlin/org/gotson/komga` 是 Komga 的桌面托盘启动层。它不是 Komga 服务器核心业务代码，而是在 `komga` 主模块之上包装出一个带系统托盘图标、桌面窗口错误提示、打开浏览器/文件管理器能力的桌面版入口。

这个目录的核心职责可以概括为三件事：

1. 启动完整的 Komga Spring Boot 应用，但以桌面程序方式运行。
2. 在系统托盘中提供常用操作：打开 Komga Web UI、打开日志文件位置、打开配置目录、退出。
3. 当启动失败时，用 Compose Desktop 弹出错误窗口，而不是只把异常打印到终端。

它依赖主模块 `komga` 的 `Application`、配置属性、Web 服务设置、工具函数等能力；自身主要处理桌面环境相关逻辑。

## 关键组成

直接文件结构很小：

`komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt` 是桌面版主入口。它定义：

- `class DesktopApplication : Application()`
- `fun main(args: Array<String>)`

`DesktopApplication` 继承主模块里的 `org.gotson.komga.Application`，从而复用 Komga 服务端的 Spring Boot 配置与组件扫描能力。它额外加了 `@EnableAsync`，用于支持托盘启动器里的异步运行。

`main` 方法先调用 `checkTempDirectory()`，再设置几个系统属性：

- `apple.awt.UIElement=true`：让 macOS 下应用更像后台菜单栏程序，避免普通窗口应用形态。
- `org.jooq.no-logo=true`
- `org.jooq.no-tips=true`

随后通过 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动 Spring，并调用 `headless(false)`。这个点很关键：托盘和 Compose Desktop 都需要 AWT/桌面图形环境，不能以纯 headless 模式运行。

启动异常会被捕获。如果根因是 `PortInUseException`，说明服务端口被占用，会用资源文本生成“端口占用”类错误；其他异常则显示通用错误，并附带 `stackTrace`。最终统一调用 `showErrorDialog(message, stackTrace)`。

`komga-tray/src/main/kotlin/org/gotson/komga/RB.kt` 是资源文本读取工具。`RB.getString(key, vararg args)` 从 `org.gotson.komga.messages` 这个 `ResourceBundle` 读取文案。如果传入参数，则使用 SLF4J 的 `MessageFormatter.arrayFormat` 做 `{}` 风格占位替换。托盘菜单、错误窗口标题、按钮文案和错误消息都通过它取值。

`komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt` 提供两个桌面操作函数：

- `openUrl(url: String)`：如果当前平台支持 `Desktop.Action.BROWSE`，就调用系统默认浏览器打开 URL。
- `openExplorer(file: File)`：尝试打开文件所在位置。优先使用 Java Desktop API 的 `BROWSE_FILE_DIR`；如果是 Windows，则退回到 `explorer.exe /select, "path"`；否则记录 warning。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt` 是托盘核心。它是一个 Spring `@Component`，实现 `ApplicationRunner`，并带有 `@Profile("!test")`，测试环境不会启用。构造参数注入了：

- `komgaProperties.configDir`：Komga 配置目录。
- `logging.file.name`：日志文件路径。
- `WebServerEffectiveSettings`：用于拿到实际服务端口和 servlet context path。
- `Environment`：用于判断 active profiles，比如 mac profile。

它构造出的 `komgaUrl` 形如：

`[URL已移除]}${effectiveServletContextPath}`

`run(args)` 标记为 `@Async`，内部调用 `runTray()`。`runTray()` 用 Compose Desktop 的 `application { Tray(...) }` 创建系统托盘图标。托盘菜单包含：

- `menu.open_komga`：调用 `openUrl(komgaUrl)`。
- `menu.show_log`：调用 `openExplorer(logFile)`。
- `menu.show_conf_dir`：调用 `openExplorer(komgaConfigDir)`。
- `menu.quit`：调用 `exitApplication`。

图标选择也在这里完成：如果 active profiles 包含 `mac`，使用 `icons/komga-gray-minimal.svg`；否则使用 `icons/komga-color.svg`。这是为了适配 macOS 菜单栏图标风格。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt` 负责启动失败时的错误窗口。`showErrorDialog(text, stackTrace)` 使用 Compose Desktop 创建一个不可调整大小的 `Window`，窗口标题来自 `dialog_error.title`。窗口里展示 Komga 图标、错误文本；如果有 `stackTrace`，则额外显示一个多行 `TextField`，并提供复制到剪贴板按钮。最后有关闭按钮，点击后 `exitApplication()`。

## 上下游关系

上游入口来自构建配置。`komga-tray/build.gradle.kts` 中 `application.mainClass` 指向：

`org.gotson.komga.DesktopApplicationKt`

也就是说，打包后的桌面程序会执行 `DesktopApplication.kt` 里的顶层 `main` 函数。

`komga-tray` 依赖主模块：

`implementation(project(":komga"))`

所以它不是另起一套服务端，而是复用 `komga` 模块的 Spring Boot 应用、配置、Web 服务、日志和业务组件。主模块里的 `org.gotson.komga.Application` 是标准 Spring Boot 应用入口，包含 `@SpringBootApplication` 和 `@EnableScheduling`；桌面版通过 `DesktopApplication : Application()` 复用这套基础配置，同时补上桌面需要的异步和非 headless 设置。

下游主要是桌面系统能力：

- Java AWT `Desktop`：打开浏览器、文件管理器。
- Compose Desktop `Tray`、`Window`：托盘图标和错误窗口。
- classpath 资源：`icons/*.svg`、`org.gotson.komga.messages`。
- Spring 配置：`komga.config-dir`、`logging.file.name`、server port/context path。

资源层还包括 `komga-tray/src/main/resources` 下的平台配置。根据已读片段，macOS 配置会把日志放在 `${user.home}/Library/Logs/Komga/komga.log`，配置目录放在 `${user.home}/Library/Application Support/Komga`；Windows 配置会把配置目录放在 `${LOCALAPPDATA}/Komga`，并设置 `kepubify.exe`。这些配置通过 Spring profile 或平台打包环境参与运行。

## 运行/调用流程

桌面版启动的大致流程是：

1. 操作系统或打包器启动 `org.gotson.komga.DesktopApplicationKt`。
2. `main(args)` 调用 `checkTempDirectory()`，检查临时目录可用性。
3. 设置 macOS UI、jOOQ logo/tips 等系统属性。
4. 创建 `SpringApplicationBuilder(DesktopApplication::class.java)`。
5. 设置 `headless(false)`，允许桌面 UI 能力。
6. 启动 Spring Boot 应用，主模块里的 Komga 服务端组件随之启动。
7. Spring 容器创建 `TrayIconRunner` bean。
8. Spring 在应用启动完成阶段调用 `ApplicationRunner.run`。
9. 因为 `run` 有 `@Async`，托盘 Compose 事件循环不会直接卡住主启动流程。
10. `TrayIconRunner.runTray()` 创建系统托盘菜单。
11. 用户点击菜单项时，分别打开 Web UI、日志位置、配置目录，或退出应用。

异常流程也很清晰：

1. Spring 启动过程中抛出异常。
2. `DesktopApplication.main` 的 `catch` 捕获。
3. 如果 `e.cause` 是 `PortInUseException`，用端口号生成本地化错误消息，不展示堆栈。
4. 其他异常生成通用错误消息，并把 `stackTraceToString()` 传给窗口。
5. `showErrorDialog` 创建 Compose Desktop 错误窗口。
6. 用户可以复制堆栈或关闭窗口退出。

这里有一个值得注意的设计：正常运行时用户主要通过托盘控制程序；异常时才出现窗口。也就是说，`komga-tray` 的 UI 不是完整客户端，而是“桌面外壳 + 本地管理入口”。

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `komga-tray/build.gradle.kts`，确认这是一个单独桌面应用模块，入口是 `org.gotson.komga.DesktopApplicationKt`，并且依赖 `project(":komga")`。
2. 再读 `komga/src/main/kotlin/org/gotson/komga/Application.kt`，理解真正的 Komga 服务端 Spring Boot 应用来自主模块。
3. 接着读 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`，看桌面版如何启动主应用、如何处理启动失败。
4. 然后读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`，这是正常运行时最重要的桌面交互逻辑。
5. 再读 `komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt`，理解托盘菜单背后的系统调用。
6. 最后读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt` 和 `RB.kt`，补齐错误窗口与本地化文案机制。

如果只想快速理解，可以优先看 `DesktopApplication.kt` 和 `TrayIconRunner.kt`。前者解释“怎么启动”，后者解释“启动后桌面端能做什么”。

## 常见误区

第一个误区是把 `komga-tray` 当成 Komga 的前端客户端。它不是漫画阅读 UI，也不是 Web 前端；真正的用户界面仍然是浏览器里的 Komga Web UI。托盘菜单的 `Open Komga` 只是打开本机服务地址。

第二个误区是以为 `TrayIconRunner` 负责启动 Web 服务器。它不负责。Web 服务器由主模块的 Spring Boot 应用启动；`TrayIconRunner` 只是等 Spring 应用起来后，根据 `WebServerEffectiveSettings` 拼出本地访问 URL。

第三个误区是忽略 `headless(false)`。普通服务端程序常常可以 headless 运行，但这个模块要用 AWT 和 Compose Desktop。如果没有图形环境，托盘和错误窗口都可能无法工作。

第四个误区是认为 `@Async` 可有可无。`runTray()` 里的 Compose `application { ... }` 本质上会进入 UI 事件循环。如果同步执行，可能影响 Spring 启动后续流程。`DesktopApplication` 上的 `@EnableAsync` 和 `TrayIconRunner.run` 上的 `@Async` 是配套设计。

第五个误区是把 `RB.getString` 理解成普通字符串常量。它读取的是 `ResourceBundle`，并支持 SLF4J `{}` 占位格式。因此像端口占用这种错误可以通过 `RB.getString("error_message.port_in_use", port)` 注入动态值。

第六个误区是认为打开日志和配置目录在所有平台都完全一致。`openExplorer` 已经体现了平台差异：支持 `BROWSE_FILE_DIR` 时走 Java Desktop API；Windows 有 `explorer.exe /select` 兜底；其他不支持的平台只记录 warning。根据当前片段推断，Linux 等环境下某些“打开文件所在位置”的行为可能取决于 JDK 和桌面环境支持情况。
