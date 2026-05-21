# 目录：komga-tray/src/main/kotlin/org

## 它负责什么

`komga-tray/src/main/kotlin/org` 是 Komga 桌面托盘版本的 Kotlin 源码入口目录。它不是 Komga 的核心业务实现目录，而是把主服务模块 `:komga` 包装成一个可带系统托盘、桌面窗口错误提示、本地资源和桌面操作能力的应用壳。

从 `komga-tray/build.gradle.kts` 可以看出，`komga-tray` 依赖 `implementation(project(":komga"))`，并把 `application.mainClass` 设置为 `org.gotson.komga.DesktopApplicationKt`。因此这个目录中的 `DesktopApplication.kt` 是桌面版启动入口，真正的服务端能力来自主模块中的 `org.gotson.komga.Application` 及其 Spring Boot 生态。

这个目录主要负责四类事情：

1. 启动桌面版 Spring Boot 应用，并把 AWT/Compose 环境设置成非 headless。
2. 在启动失败时显示 Compose Desktop 错误窗口。
3. 启动系统托盘图标，提供打开 Komga、打开日志、打开配置目录、退出等桌面菜单。
4. 提供国际化文案读取和少量桌面工具函数，例如打开 URL、打开文件管理器。

## 关键组成

`komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt` 是启动入口。它定义了 `DesktopApplication : Application()`，并带有 `@EnableAsync`。这里的 `Application` 来自主模块 `org.gotson.komga.Application`，说明桌面版不是重新实现服务端，而是在主服务基础上增加桌面能力。`main(args)` 中先调用 `checkTempDirectory()` 检查临时目录，然后设置几个系统属性：`apple.awt.UIElement=true` 让 macOS 下应用更接近托盘/后台应用形态，`org.jooq.no-logo` 和 `org.jooq.no-tips` 用于关闭 jOOQ 输出。随后通过 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动 Spring，关键点是 `headless(false)`，这允许 AWT、Compose Desktop、系统托盘等桌面 UI 能力正常工作。

`komga-tray/src/main/kotlin/org/gotson/komga/RB.kt` 是资源文案读取工具。`RB` 使用 `ResourceBundle.getBundle("org.gotson.komga.messages")` 加载 `komga-tray/src/main/resources/org/gotson/komga/messages*.properties`。`getString(key, vararg args)` 支持无参数文案读取，也支持用 SLF4J `MessageFormatter.arrayFormat` 做 `{}` 风格占位符替换。托盘菜单、错误弹窗标题、按钮文字、端口占用错误等都依赖它。

`komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt` 提供两个桌面辅助函数。`openUrl(url)` 使用 `java.awt.Desktop` 的 `BROWSE` 动作打开浏览器。`openExplorer(file)` 尝试打开系统文件管理器并定位到日志文件或配置目录；如果当前 Java Desktop API 支持 `BROWSE_FILE_DIR` 就直接使用，否则在 Windows 上退回到 `explorer.exe /select, ...`，其他系统不支持时只记录 warning。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt` 定义 `showErrorDialog(text, stackTrace)`。它使用 Compose Desktop 的 `application { Window { ... } }` 创建错误窗口，加载 `icons/komga-color.svg` 作为窗口和内容图标。窗口中固定显示错误文案；如果传入 `stackTrace`，会额外显示一个多行 `TextField`，并提供复制到剪贴板按钮。普通关闭按钮会调用 `exitApplication()` 退出 Compose 应用。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt` 是托盘入口组件。它被标记为 `@Component` 和 `@Profile("!test")`，说明在非测试环境中由 Spring 扫描并创建。它实现 `ApplicationRunner`，Spring Boot 启动完成后会调用 `run(args)`。由于类所在应用启用了 `@EnableAsync`，且 `run` 标记为 `@Async`，托盘 Compose 循环会在异步线程中运行，避免阻塞主 Spring Boot 启动流程。

`TrayIconRunner` 构造参数体现了它和主服务配置的连接点：`komgaProperties.configDir` 提供配置目录，`logging.file.name` 提供日志文件路径，`WebServerEffectiveSettings` 提供实际服务端口和 context path，`Environment` 用于判断 active profile。它拼出 `komgaUrl`，形如 `[URL已移除]}${effectiveServletContextPath}`。托盘菜单包含 `open_komga`、`show_log`、`show_conf_dir`、`quit` 四项，分别调用浏览器、文件管理器或 `exitApplication()`。

## 上下游关系

上游入口来自 Gradle `application` 插件。`komga-tray/build.gradle.kts` 指定主类为 `org.gotson.komga.DesktopApplicationKt`，所以打包或运行桌面版时会进入 `DesktopApplication.kt` 的顶层 `main` 函数。

核心上游依赖是主模块 `:komga`。`DesktopApplication : Application()`、`checkTempDirectory()`、`WebServerEffectiveSettings`、`komgaProperties.configDir`、`logging.file.name` 等都不是这个目录独立产生的能力，而是从主服务模块和 Spring 配置体系继承或注入进来的。根据当前片段推断，`komga-tray` 的定位是“桌面启动器 + 托盘外壳”，主业务如书库、Web API、数据库、Web 服务端口等仍由 `:komga` 负责。

下游主要是桌面运行时和操作系统能力。`ErrorDialog.kt`、`TrayIconRunner.kt` 依赖 Compose Desktop；`Utils.kt` 依赖 `java.awt.Desktop` 和操作系统文件管理器；资源下游依赖 `komga-tray/src/main/resources/icons/komga-color.svg`、`komga-tray/src/main/resources/icons/komga-gray-minimal.svg` 以及 `messages*.properties` 国际化文件。

另一个重要关系是 profile 和平台差异。`TrayIconRunner` 如果检测到 active profile 包含 `mac`，托盘图标使用 `komga-gray-minimal.svg`，否则使用 `komga-color.svg`。资源目录中还有 `application-mac.yml`、`application-windows.yml`，说明不同平台的运行配置不完全相同；但根据当前片段，只能确认托盘图标选择直接依赖 `mac` profile。

## 运行/调用流程

桌面版启动时，流程大致如下：

1. JVM 进入 `org.gotson.komga.DesktopApplicationKt.main(args)`。
2. `main` 调用 `checkTempDirectory()`，提前检查临时目录可用性。
3. 设置 macOS、jOOQ 相关系统属性。
4. 使用 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动 Spring Boot，并显式设置 `headless(false)`。
5. Spring 创建 `DesktopApplication`，它继承主模块的 `Application`，因此会加载 Komga 主服务上下文。
6. 启动完成后，Spring 调用实现了 `ApplicationRunner` 的 `TrayIconRunner.run(args)`。
7. `TrayIconRunner.run` 因为 `@Async` 在异步执行，进入 `runTray()`。
8. `runTray()` 创建 Compose Desktop `application`，注册系统托盘 `Tray`。
9. 用户点击托盘菜单：
   - `menu.open_komga` 调用 `openUrl(komgaUrl)`，打开本地 Web UI。
   - `menu.show_log` 调用 `openExplorer(logFile)`，定位日志文件。
   - `menu.show_conf_dir` 调用 `openExplorer(komgaConfigDir)`，打开配置目录。
   - `menu.quit` 调用 `exitApplication()`，退出托盘 Compose 应用。

异常流程也很关键。`DesktopApplication.main` 包了一层 `try/catch`。如果 Spring 启动失败，并且 `e.cause` 是 `PortInUseException`，会通过 `RB.getString("error_message.port_in_use", port)` 生成端口占用提示，不显示堆栈。如果是其他异常，则使用 `error_message.unexpected`，同时把 `e.stackTraceToString()` 传给错误弹窗。`showErrorDialog` 会显示错误窗口，并在有堆栈时提供复制按钮，方便用户反馈或排查。

## 小白阅读顺序

建议先读 `komga-tray/build.gradle.kts`。它能回答“这个模块怎么启动”“依赖谁”“入口类是谁”。尤其注意 `implementation(project(":komga"))` 和 `mainClass = "org.gotson.komga.DesktopApplicationKt"`，这两行决定了 `komga-tray` 不是主业务模块，而是桌面版包装模块。

第二步读 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。这是理解全目录的中心。重点看 `DesktopApplication : Application()`、`@EnableAsync`、`headless(false)`、异常捕获和 `showErrorDialog(...)`。读完这一个文件，就能明白服务端启动、桌面 UI、错误处理三者如何接在一起。

第三步读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`。它是正常启动成功后的桌面体验入口。重点关注构造参数注入、`komgaUrl` 的拼接、`@Profile("!test")`、`@Async`、`Tray` 菜单项。这里能看出托盘菜单其实只是对主服务 URL、日志文件、配置目录的快捷访问。

第四步读 `komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt`。这个文件代码少，但能解释托盘菜单点击后为什么能打开浏览器和文件管理器。小白容易忽略 `Desktop.isDesktopSupported()` 这类平台能力判断，实际它决定了功能在不同系统上的可用性。

第五步读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt` 和 `komga-tray/src/main/kotlin/org/gotson/komga/RB.kt`。前者解释启动失败时用户看到什么，后者解释文案从哪里来。再结合 `komga-tray/src/main/resources/org/gotson/komga/messages.properties` 及各语言文件，就能理解国际化链路。

## 常见误区

第一个误区是把 `komga-tray/src/main/kotlin/org` 当成 Komga 主服务源码。实际上它只是桌面托盘模块的 Kotlin 包根。主服务能力来自 `:komga`，这里通过 `DesktopApplication : Application()` 复用主应用，而不是重写服务端。

第二个误区是认为 `TrayIconRunner` 会启动 Web 服务。它不会。Web 服务已经由 Spring Boot 主应用启动；`TrayIconRunner` 只是读取 `WebServerEffectiveSettings`，拼出 `[URL已移除]

第三个误区是忽略 `headless(false)`。普通服务端 Spring Boot 常常可以 headless 运行，但这里需要 Compose Desktop、AWT Desktop、系统托盘和窗口图标。如果没有非 headless 环境，托盘和错误窗口这类 UI 能力可能无法正常工作。

第四个误区是把 `exitApplication()` 理解成完整的服务端优雅关闭逻辑。根据当前片段，它是 Compose Desktop 的退出函数，用于关闭托盘或错误窗口应用。它和 Spring Boot 应用上下文、进程生命周期之间的完整关系需要结合 Compose Desktop 与主应用运行方式进一步确认；仅从当前目录看，菜单的退出动作没有显式调用 Spring 的 shutdown API。

第五个误区是认为国际化字符串在 Kotlin 代码里硬编码。实际菜单、错误标题、按钮文案都通过 `RB.getString(...)` 从 `messages*.properties` 读取。修改文案时应该先找资源文件，而不是只搜索 Kotlin 字符串。

第六个误区是以为打开日志和配置目录是跨平台完全一致的。`openExplorer(file)` 优先使用 Java Desktop API，但如果不支持，只对 Windows 做了 `explorer.exe /select` 兜底，其他平台会记录 warning。因此在 Linux 或某些桌面环境里，文件管理器打开能力可能取决于 Java 与系统桌面集成情况。
