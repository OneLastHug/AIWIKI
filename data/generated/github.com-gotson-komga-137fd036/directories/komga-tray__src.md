# 目录：komga-tray/src

## 它负责什么

`komga-tray/src` 是 Komga 的桌面托盘启动层。它本身不实现漫画/书库管理、API、数据库、扫描等核心业务，而是依赖主模块 `:komga`，把原本的 Spring Boot 服务包装成一个可在 macOS、Windows 等桌面环境中运行的应用入口，并提供系统托盘菜单、错误弹窗、平台默认配置和本地化文案。

从 `komga-tray/build.gradle.kts` 可以看出，该子模块使用 Kotlin JVM、Spring 插件、Compose Desktop、Conveyor 打包插件，并声明 `implementation(project(":komga"))`。因此它的定位是“桌面外壳”：启动 Komga 服务、显示托盘图标、打开浏览器访问本地 Web 服务、打开日志文件和配置目录、在启动失败时显示图形化错误窗口。

## 关键组成

`komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt` 是桌面版主入口。`mainClass` 在 `build.gradle.kts` 中配置为 `org.gotson.komga.DesktopApplicationKt`，对应这个文件里的顶层 `main(args)`。它先调用 `checkTempDirectory()` 检查临时目录，再设置若干系统属性，例如 macOS 上的 `apple.awt.UIElement=true`，以及关闭 jOOQ logo/tips。之后通过 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动 Spring Boot，并显式设置 `headless(false)`，说明桌面模式需要 AWT/Compose 图形能力。

`DesktopApplication : Application()` 是桌面启动类，继承自主模块 `komga/src/main/kotlin/org/gotson/komga/Application.kt` 中的 `Application`。根据当前片段推断，主模块的 `Application` 承担 Komga 后端应用的 Spring Boot 配置和组件扫描，`komga-tray` 只是扩展出一个桌面启动变体。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt` 是托盘菜单的核心。它是 Spring `@Component`，实现 `ApplicationRunner`，并带有 `@Profile("!test")`，表示测试 profile 下不运行。`run()` 被 `@Async` 标记，启动后异步调用 `runTray()`，避免 Compose 托盘事件循环阻塞 Spring Boot 主流程。它通过 `WebServerEffectiveSettings` 拼出 `[URL已移除]}{contextPath}`，再把“打开 Komga”“显示日志”“打开配置目录”“退出”挂到托盘菜单上。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt` 负责启动失败时的图形错误窗口。`DesktopApplication.kt` 捕获异常后，如果原因是 `PortInUseException`，显示“端口已占用”的本地化消息；其他异常则显示通用错误，并把 `stackTrace` 放入窗口中的 `TextField`，同时提供复制到剪贴板按钮。

`komga-tray/src/main/kotlin/org/gotson/komga/RB.kt` 是资源文案访问工具。它用 `ResourceBundle.getBundle("org.gotson.komga.messages")` 加载 `src/main/resources/org/gotson/komga/messages*.properties`，并用 SLF4J 的 `MessageFormatter` 支持 `{}` 参数替换。

`komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt` 封装桌面系统交互。`openUrl(url)` 使用 `java.awt.Desktop` 的 `BROWSE` 打开浏览器；`openExplorer(file)` 优先使用 `BROWSE_FILE_DIR` 定位文件，Windows 下退回到 `explorer.exe /select, "path"`，否则记录不支持的警告。

`komga-tray/src/main/resources/application-mac.yml` 和 `application-windows.yml` 是平台 profile 配置。macOS 默认日志在 `${user.home}/Library/Logs/Komga/komga.log`，配置目录在 `${user.home}/Library/Application Support/Komga`；Windows 默认配置目录在 `${LOCALAPPDATA}/Komga`。两者都会从 `${komga.config-dir}` 下可选导入 `application.yml`、`application.yaml`、`application.properties`，允许用户覆盖配置。

资源目录还包含 `icons/komga-color.svg`、`icons/komga-gray-minimal.svg` 和大量 `messages_*.properties` 翻译文件。托盘图标选择逻辑在 `TrayIconRunner.kt`：如果 active profile 包含 `mac`，使用灰色极简图标，否则使用彩色图标。

## 上下游关系

上游入口是构建和运行系统。`komga-tray/build.gradle.kts` 把应用入口指向 `DesktopApplicationKt`，并通过 Compose Desktop 和 Conveyor 支持不同桌面平台分发。运行时，JVM 进入 `main(args)`，再交给 Spring Boot。

下游主要是主模块 `:komga`。`DesktopApplication` 继承主模块的 `Application`，`TrayIconRunner` 注入主模块提供的 `WebServerEffectiveSettings`，并读取 `komgaProperties.configDir`、`logging.file.name` 等配置值。也就是说，真实 Web 服务端口、Servlet context path、配置目录、日志文件路径都不是托盘层自己硬编码出来的，而是从 Spring 环境和 Komga 主配置体系中取得。

横向依赖是桌面 UI 与系统 API。Compose Desktop 提供 `application {}`、`Tray`、`Window`、`Button`、`TextField` 等 UI 构件；`java.awt.Desktop` 负责浏览器和文件管理器交互；`ClassPathResource` 负责从 classpath 加载 SVG 图标；`ResourceBundle` 提供国际化文案。

## 运行/调用流程

1. 操作系统或打包后的启动器执行 `org.gotson.komga.DesktopApplicationKt`。
2. `main(args)` 调用 `checkTempDirectory()`，然后设置桌面和 jOOQ 相关系统属性。
3. `SpringApplicationBuilder(DesktopApplication::class.java)` 以非 headless 模式启动 Komga。
4. 主模块 `:komga` 的 Spring Boot 应用启动 Web 服务、配置系统、日志系统和业务组件。
5. Spring 容器创建 `TrayIconRunner`。它从配置中拿到配置目录、日志文件路径，并从 `WebServerEffectiveSettings` 拿到实际端口和 context path。
6. `TrayIconRunner.run()` 异步执行 Compose `application { Tray(...) }`，系统托盘出现 Komga 图标。
7. 用户点击托盘菜单：
   - `Open Komga` 调用 `openUrl(komgaUrl)` 打开本地 Web UI。
   - `Show log file` 调用 `openExplorer(logFile)` 定位日志文件。
   - `Open configuration directory` 调用 `openExplorer(komgaConfigDir)` 打开配置目录。
   - `Quit Komga` 调用 Compose 的 `exitApplication` 退出托盘应用。
8. 如果 Spring Boot 启动阶段抛异常，`main()` 捕获后调用 `showErrorDialog()`，在 Compose 窗口中展示错误。端口占用会显示专门提示，其他错误会显示 stack trace 并允许复制。

## 小白阅读顺序

先读 `komga-tray/build.gradle.kts`，确认这是一个依赖 `:komga` 的 Compose Desktop 子模块，并记住入口类是 `DesktopApplicationKt`。

第二步读 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。重点看 `main()` 如何启动 Spring Boot，以及异常如何转成错误弹窗。这里能建立“桌面壳启动后端服务”的主线。

第三步读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`。这是最能代表该目录职责的文件：它说明托盘菜单有哪些功能、URL 如何生成、配置目录和日志文件如何取得、图标如何按平台切换。

第四步读 `komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt` 和 `RB.kt`。前者解释菜单动作如何落到浏览器/文件管理器，后者解释所有菜单和错误文案从哪里来。

第五步读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt`。这里可以了解 Compose Desktop 窗口写法，以及启动失败时用户看到的界面。

最后看 `komga-tray/src/main/resources/application-mac.yml`、`application-windows.yml`、`org/gotson/komga/messages.properties` 和其他翻译文件。它们不改变主流程，但解释了平台默认目录、本地配置导入方式和多语言文案来源。

## 常见误区

不要把 `komga-tray/src` 理解成 Komga 的完整桌面客户端。它没有重写一套原生 UI，也不直接展示书库内容；真正的阅读、管理、API 和后台逻辑仍在主模块 `:komga` 中，托盘层只是帮助用户启动服务并打开浏览器访问本地 Web UI。

不要以为托盘中的 URL 是固定端口。`TrayIconRunner` 使用 `WebServerEffectiveSettings` 生成 `komgaUrl`，端口和 context path 来自实际生效的 Spring 配置，因此用户改过 `server.port` 或 context path 后，托盘菜单仍应指向正确地址。

不要忽略 `@Async`。Compose 的 `application {}` 会进入 UI 事件循环，如果同步运行在 Spring 启动回调里，可能影响应用启动流程。这里用异步方式把托盘 UI 和后端启动生命周期解耦。

不要把 `application-mac.yml`、`application-windows.yml` 当成唯一配置来源。它们提供平台默认值，并通过 `spring.config.import` 可选导入用户配置目录下的配置文件；最终生效配置可能来自用户自定义文件。

不要误解错误弹窗只处理端口冲突。`DesktopApplication.kt` 对 `PortInUseException` 做了特殊文案，但其他异常也会进入 `showErrorDialog()`，并展示 stack trace。端口占用只是被单独优化过的常见启动失败场景。
