# 目录：komga-tray/src/main/kotlin/org/gotson/komga/application

## 它负责什么

这个目录是 `komga-tray` 桌面端的 GUI 应用层，目前实际代码都在子包 `org.gotson.komga.application.gui` 下。它不负责 Komga 的漫画库、用户、数据库、Web API 等核心业务，而是负责“桌面壳”相关能力：系统托盘菜单，以及启动失败时给用户看的错误弹窗。

从模块关系看，`komga-tray` 是对主模块 `komga` 的桌面封装。`komga-tray/build.gradle.kts` 里依赖了 `project(":komga")`，同时引入 `compose.desktop.currentOs` 和 `compose.components.resources`。这说明它复用主服务端应用能力，再用 JetBrains Compose Desktop 提供桌面 UI。入口类在 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`，而本目录提供入口启动后需要调用的 GUI 组件。

这个目录的核心职责可以概括为两点：

1. 正常启动后，在系统托盘或菜单栏显示 Komga 图标和菜单。
2. 启动失败时，用桌面窗口显示错误原因，并在必要时提供堆栈复制能力。

它是一个很薄的 UI 适配层，上游接 Spring Boot 启动生命周期和配置，下游接操作系统桌面能力、浏览器、文件管理器、Compose Desktop 窗口系统。

## 关键组成

目标目录的直接结构很简单：

`komga-tray/src/main/kotlin/org/gotson/komga/application`
下面只有一个子目录 `gui`，包含两个文件：

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt`

这个文件定义 `showErrorDialog(text: String, stackTrace: String? = null)`。它是一个 Compose Desktop 函数，用 `application { Window(...) { ... } }` 创建独立错误窗口。

关键点如下：

- `@Preview` 标注说明它也可被 Compose 工具预览。
- 窗口标题来自 `RB.getString("dialog_error.title")`，也就是资源包中的 `dialog_error.title=Komga failed to start`。
- 窗口不可缩放，居中浮动显示。
- 如果传入 `stackTrace != null`，窗口宽度设为 `800.dp`，并显示一个最多 15 行的 `TextField` 展示堆栈。
- 如果没有 `stackTrace`，只显示简短错误消息和关闭按钮。
- 当有堆栈时，会额外显示 “Copy to clipboard” 按钮，通过 `LocalClipboardManager.current.setText(AnnotatedString(stackTrace))` 写入剪贴板。
- 图标和窗口内 logo 都从 classpath 读取 `icons/komga-color.svg`，再用 `decodeToSvgPainter(LocalDensity.current)` 转成 Compose painter。

这里的设计意图很明确：端口占用这类用户可理解的错误只显示短消息；未知异常则显示完整 stack trace，方便用户复制到 issue 或日志分析场景。

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`

这个文件定义 `TrayIconRunner`，它是一个 Spring Bean：

```kotlin
@Profile("!test")
@Component
class TrayIconRunner(...) : ApplicationRunner
```

它实现 `ApplicationRunner`，意味着 Spring Boot 应用上下文启动完成后会调用它的 `run(args)`。但 `run` 上标了 `@Async`，所以托盘 UI 会异步启动，不阻塞主应用线程。这个异步能力来自 `DesktopApplication.kt` 上的 `@EnableAsync`。

构造参数说明了它依赖哪些上游信息：

- `@Value("#{komgaProperties.configDir}") komgaConfigDir: String`：从主应用配置对象中取 Komga 配置目录。
- `@Value($$"${logging.file.name}") logFileName: String`：从 Spring 配置中取日志文件路径。
- `serverSettings: WebServerEffectiveSettings`：来自主模块 `komga`，用于获取实际监听端口和 Servlet context path。
- `env: Environment`：读取当前 profile，用来判断是否是 `mac` profile。

它内部派生出几个懒加载属性：

- `komgaUrl`：拼出 `[URL已移除]}${serverSettings.effectiveServletContextPath}`。
- `komgaConfigDir`：把配置目录字符串转成 `File`。
- `logFile`：把日志路径字符串转成 `File`。
- `iconFileName`：如果 active profiles 包含 `mac`，使用 `komga-gray-minimal.svg`；否则使用 `komga-color.svg`。

`runTray()` 中通过 Compose Desktop 的 `Tray` 创建托盘图标和菜单。菜单项包括：

- `menu.open_komga`：调用 `openUrl(komgaUrl)`，用系统浏览器打开 Komga Web UI。
- `menu.show_log`：调用 `openExplorer(logFile)`，在文件管理器里定位日志文件。
- `menu.show_conf_dir`：调用 `openExplorer(komgaConfigDir)`，打开配置目录。
- `menu.quit`：调用 `exitApplication` 退出 Compose 托盘应用。

这些菜单文案来自 `komga-tray/src/main/resources/org/gotson/komga/messages.properties` 及多语言变体。

## 上下游关系

上游入口是 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。这个文件定义：

```kotlin
@EnableAsync
class DesktopApplication : Application()
```

`DesktopApplication` 继承主模块中的 `Application`，所以桌面版本质上仍是 Komga 的 Spring Boot 应用，只是加了桌面 UI 外壳。

`main(args)` 启动前先调用 `checkTempDirectory()`，再设置几个系统属性：

- `apple.awt.UIElement=true`：让 macOS 下应用更像菜单栏/托盘后台应用。
- `org.jooq.no-logo=true`
- `org.jooq.no-tips=true`

随后用 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动，并显式设置 `headless(false)`。这里非常关键：Compose Desktop、AWT、托盘、窗口都需要非 headless 环境。

如果启动抛异常，`DesktopApplication.kt` 会捕获：

- 若 `e.cause is PortInUseException`，从 `RB` 取 `error_message.port_in_use`，传入端口号，并且不给 `stackTrace`。
- 其他异常则取 `error_message.unexpected`，同时把 `e.stackTraceToString()` 传给 `showErrorDialog`。

因此 `ErrorDialog.kt` 的直接调用方就是 `DesktopApplication.kt`，它是启动失败路径的最后兜底 UI。

`TrayIconRunner.kt` 的上游是 Spring Boot 的 `ApplicationRunner` 生命周期。只要 profile 不是 `test`，且 Spring 上下文正常启动，它就会作为 `@Component` 被发现并运行。它还依赖主模块的 `WebServerEffectiveSettings`。该类在 `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebServerEffectiveSettings.kt` 中监听 `ServletWebServerInitializedEvent`，把实际 Web server 端口写入 `effectiveServerPort`。这使托盘菜单能打开真实端口，而不是只看静态配置；如果端口为 `0` 或被环境改写，这种方式仍能拿到运行时端口。

下游方面，两个 GUI 文件都依赖 Compose Desktop：

- `Window` 和 `application` 用于错误弹窗。
- `Tray` 用于系统托盘。
- `LocalDensity`、`decodeToSvgPainter` 用于 SVG 图标渲染。
- `LocalClipboardManager` 用于复制堆栈。

`TrayIconRunner` 还调用 `komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt` 中的工具函数：

- `openUrl(url: String)`：如果 `java.awt.Desktop` 支持 `BROWSE`，就调用系统浏览器打开 URL。
- `openExplorer(file: File)`：优先用 `Desktop.Action.BROWSE_FILE_DIR` 打开文件位置；Windows 下退回到 `explorer.exe /select, "..."`；其他不支持平台记录 warning。

资源上，它依赖：

- `komga-tray/src/main/resources/icons/komga-color.svg`
- `komga-tray/src/main/resources/icons/komga-gray-minimal.svg`
- `komga-tray/src/main/resources/org/gotson/komga/messages.properties` 及多语言文件
- `komga-tray/src/main/resources/application-mac.yml`
- `komga-tray/src/main/resources/application-windows.yml`

其中 `application-mac.yml` 定义了 macOS 下日志路径和配置目录，例如 `${user.home}/Library/Logs/Komga/komga.log`、`${user.home}/Library/Application Support/Komga`。`application-windows.yml` 定义 Windows 下 `komga.config-dir: ${LOCALAPPDATA}/Komga`，并设置 `kepubify.exe` 路径。根据当前片段推断，平台 profile 由打包或启动参数注入，因为本目录只读取 `env.activeProfiles.contains("mac")`，没有看到 profile 设置逻辑。

## 运行/调用流程

正常启动流程如下：

1. 用户启动桌面版 Komga，进入 `DesktopApplicationKt.main`。
2. `main` 检查临时目录，设置 AWT/JOOQ 相关系统属性。
3. `SpringApplicationBuilder` 以 `headless(false)` 启动 `DesktopApplication`。
4. 主模块 `komga` 的 Spring Boot 服务开始启动，包括 Web server、配置、数据库、接口等。
5. Web server 初始化完成后，`WebServerEffectiveSettings.onApplicationEvent` 接收 `ServletWebServerInitializedEvent`，记录实际端口。
6. Spring 上下文启动完成后，`TrayIconRunner.run` 作为 `ApplicationRunner` 被调用。
7. 因为 `run` 标了 `@Async`，它在异步线程中执行 `runTray()`。
8. `runTray()` 创建 Compose `application`，并通过 `Tray` 注册系统托盘图标和菜单。
9. 用户点击 “Open Komga” 时，托盘根据 `effectiveServerPort` 和 context path 拼出本地 URL，并用系统浏览器打开。
10. 用户点击 “Show log” 或 “Open configuration directory” 时，调用系统文件管理器打开对应位置。
11. 用户点击 “Quit Komga” 时，调用 `exitApplication` 退出 Compose 托盘应用。

异常启动流程如下：

1. `SpringApplicationBuilder(...).run(*args)` 抛出异常。
2. `main` 捕获异常。
3. 如果根因是 `PortInUseException`，生成端口占用文案，不展示堆栈。
4. 如果是其他异常，生成通用错误文案，并附带完整 stack trace。
5. 调用 `showErrorDialog(message, stackTrace)`。
6. `showErrorDialog` 创建 Compose Desktop 窗口，展示 Komga logo、错误文案、可选堆栈文本框。
7. 用户可复制堆栈到剪贴板，或点击 Close 退出应用。

需要注意，`TrayIconRunner` 和 `showErrorDialog` 都用了 Compose 的 `application { ... }`。它们不会同时服务同一个场景：托盘是启动成功后的常驻 UI，错误弹窗是启动失败后的兜底 UI。

## 小白阅读顺序

建议按下面顺序读：

1. 先读 `komga-tray/build.gradle.kts`。理解这是一个依赖主模块 `:komga` 的桌面启动模块，主类是 `org.gotson.komga.DesktopApplicationKt`，并使用 Compose Desktop。
2. 再读 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。这是整个桌面版的入口，能看清正常启动和失败兜底两条路线。
3. 然后读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`。重点看 `ApplicationRunner`、`@Async`、`Tray` 菜单项和 `komgaUrl` 的构造。
4. 接着读 `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebServerEffectiveSettings.kt`。理解为什么托盘能知道真实 Web 端口。
5. 再读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt`。重点看 `stackTrace == null` 和 `stackTrace != null` 两种 UI 分支。
6. 最后读 `komga-tray/src/main/kotlin/org/gotson/komga/RB.kt`、`komga-tray/src/main/resources/org/gotson/komga/messages.properties`、`komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt`。这些文件分别解释文案来源、国际化 key、打开浏览器/文件管理器的系统适配。

如果只想快速理解本目录，最短路径是：`DesktopApplication.kt` → `TrayIconRunner.kt` → `ErrorDialog.kt`。

## 常见误区

第一个误区是把这个目录当成 Komga 的主业务入口。实际上它只是桌面 GUI 外壳。真正的服务端应用、API、数据库、领域逻辑主要在 `komga` 模块中。`komga-tray` 通过 `implementation(project(":komga"))` 复用这些能力。

第二个误区是以为 `TrayIconRunner` 手动启动 Web 服务。它没有启动服务，只是在 Spring Boot 启动完成后作为 `ApplicationRunner` 启动托盘 UI。Web server 的端口来自 `WebServerEffectiveSettings`，不是 `TrayIconRunner` 自己绑定出来的。

第三个误区是忽略 `@Async`。`TrayIconRunner.run` 如果不异步，Compose `application` 的事件循环可能影响 Spring Boot 启动流程或 runner 执行链。这里配合 `DesktopApplication` 上的 `@EnableAsync`，让托盘 UI 在后台线程中运行。

第四个误区是认为 `komgaUrl` 一定立即有端口。根据当前片段推断，`komgaUrl` 是 lazy 属性，只有菜单点击时才计算；这给 `WebServerEffectiveSettings` 足够时间在 `ServletWebServerInitializedEvent` 中填充 `effectiveServerPort`。如果过早访问，端口可能还是 `null`，但当前代码只在菜单点击回调中使用，风险较低。

第五个误区是认为错误弹窗总会显示堆栈。端口占用是特殊处理，只显示用户可读消息，不显示 stack trace；未知异常才显示堆栈和复制按钮。

第六个误区是把 `exitApplication` 理解成完整关闭 Spring Boot 服务。它来自 Compose Desktop，用于退出 Compose application。根据当前片段只能确认它关闭 Compose 事件循环；整个桌面进程如何随之结束，要结合 Compose runtime 和 Spring Boot 进程生命周期判断。当前代码中托盘的 “Quit Komga” 没有显式调用 Spring `ApplicationContext.close()`。

第七个误区是忽略平台 profile 对图标和配置的影响。`TrayIconRunner` 在 `mac` profile 下使用灰色极简图标，其他平台用彩色图标；`application-mac.yml` 和 `application-windows.yml` 也分别定义了不同配置目录和日志路径。平台差异不是写在 GUI 逻辑里硬编码完成的，而是部分交给 Spring profile 配置。
