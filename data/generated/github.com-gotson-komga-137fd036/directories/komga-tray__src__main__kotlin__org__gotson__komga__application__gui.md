# 目录：komga-tray/src/main/kotlin/org/gotson/komga/application/gui

## 它负责什么

`komga-tray/src/main/kotlin/org/gotson/komga/application/gui` 是 `komga-tray` 桌面托盘模块里的 GUI 层。它不负责 Komga 的核心漫画服务、HTTP API、数据库或业务逻辑，而是负责桌面环境中的两个用户界面入口：

1. 启动成功后，在系统托盘或菜单栏中显示 Komga 图标，并提供快捷菜单。
2. 启动失败时，用 Compose Desktop 弹出错误对话框，向用户展示错误信息和可复制的堆栈。

这个目录只有两个 Kotlin 文件：

- `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`
- `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt`

从职责上看，它是 Spring Boot 应用生命周期与 Compose Desktop GUI 能力之间的适配层：Spring Boot 负责启动和注入配置，Compose Desktop 负责实际创建窗口、托盘图标和菜单。

## 关键组成

### `TrayIconRunner.kt`

`TrayIconRunner` 是托盘图标的启动器。它被标注为：

- `@Component`
- `@Profile("!test")`
- 实现 `ApplicationRunner`
- `run` 方法标注 `@Async`

这几个点说明它是一个 Spring Bean，会在 Spring Boot 应用启动完成后运行，但不会在 `test` profile 下启用；同时托盘 GUI 会异步启动，避免阻塞主应用启动流程。

构造函数接收几个关键依赖：

- `@Value("#{komgaProperties.configDir}") komgaConfigDir: String`
- `@Value($$"${logging.file.name}") logFileName: String`
- `serverSettings: WebServerEffectiveSettings`
- `env: Environment`

这些依赖让托盘菜单能够知道：

- Komga 配置目录在哪里。
- 日志文件在哪里。
- 当前 Web 服务监听端口是多少。
- 当前 servlet context path 是什么。
- 当前是否处于 `mac` profile。

核心属性包括：

- `komgaUrl`：懒加载生成 `[URL已移除]}${serverSettings.effectiveServletContextPath}`。
- `komgaConfigDir`：把配置目录字符串转成 `File`。
- `logFile`：把日志文件路径转成 `File`。
- `iconFileName`：如果激活 profile 包含 `mac`，使用 `komga-gray-minimal.svg`，否则使用 `komga-color.svg`。

`runTray()` 内部使用 Compose Desktop 的 `application { Tray(...) }` 创建系统托盘图标。托盘菜单包含四个 `Item`：

- `menu.open_komga`：调用 `openUrl(komgaUrl)`，打开 Komga Web 页面。
- `menu.show_log`：调用 `openExplorer(logFile)`，在系统文件管理器中显示日志文件。
- `menu.show_conf_dir`：调用 `openExplorer(komgaConfigDir)`，打开配置目录。
- `menu.quit`：调用 `exitApplication`，退出托盘 GUI 应用。

图标资源来自 classpath：

- `icons/komga-gray-minimal.svg`
- `icons/komga-color.svg`

加载方式是 `ClassPathResource(...).inputStream.readAllBytes().decodeToSvgPainter(LocalDensity.current)`，也就是读取 SVG 字节并转换成 Compose 可绘制对象。

### `ErrorDialog.kt`

`ErrorDialog.kt` 提供顶层函数：

```kotlin
fun showErrorDialog(
  text: String,
  stackTrace: String? = null,
)
```

它也是基于 Compose Desktop 的 `application { Window(...) }` 创建独立窗口。这个窗口用于 Komga 启动失败时显示错误。

窗口关键配置：

- `title = RB.getString("dialog_error.title")`
- `onCloseRequest = ::exitApplication`
- `visible = true`
- `resizable = false`
- `placement = WindowPlacement.Floating`
- `position = WindowPosition(alignment = Alignment.Center)`

如果传入 `stackTrace`，窗口宽度设为 `800.dp`；如果没有堆栈，则宽度使用 `Dp.Unspecified`，交给内容自然撑开。

窗口内容由 `Column` 组织：

1. 顶部 `Row` 显示 Komga 图标和错误文本。
2. 如果 `stackTrace != null`，显示一个多行 `TextField`，最多 15 行。
3. 底部按钮区：
   - 如果有堆栈，显示 `Copy to clipboard` 文本按钮，把堆栈复制到系统剪贴板。
   - 始终显示关闭按钮，点击后 `exitApplication()`。

这里的 `TextField` 设置了 `onValueChange = {}`，因此它更像只读展示框，而不是让用户编辑错误信息。代码没有显式设置 `readOnly = true`，但由于变更回调不更新状态，用户输入不会持久改变显示内容。

`@Preview` 标注说明这个函数也可以用于 Compose Desktop 预览工具，不过它在实际运行中也会被调用。

### `RB` 与本地化文案

两个 GUI 文件都通过 `RB.getString(...)` 获取文案，而不是直接写死字符串。根据资源扫描结果，相关 key 位于 `komga-tray/src/main/resources/org/gotson/komga/messages.properties` 以及多语言 `messages_xx.properties` 文件中。

默认英文文案包括：

- `dialog_error.close=Close`
- `dialog_error.copy_clipboard=Copy to clipboard`
- `dialog_error.title=Komga failed to start`
- `menu.open_komga=Open Komga`
- `menu.quit=Quit Komga`
- `menu.show_conf_dir=Open configuration directory`
- `menu.show_log=Show log file`

因此，这个目录的界面文字全部走资源包，天然支持国际化。

## 上下游关系

### 上游：Spring Boot 启动流程

`TrayIconRunner` 的上游是 Spring Boot 应用启动生命周期。它实现 `ApplicationRunner`，意味着 Spring Boot 容器准备好后会调用它的 `run(args: ApplicationArguments)`。

它还依赖 Spring 注入：

- `komgaProperties.configDir`
- `logging.file.name`
- `WebServerEffectiveSettings`
- `Environment`

其中 `WebServerEffectiveSettings` 来自 `org.gotson.komga.infrastructure.web`，不在本目录内。根据字段名和使用方式，它提供最终生效的服务端口和 servlet context path。`TrayIconRunner` 用这些值拼出本机访问地址。

### 上游：启动失败处理

`ErrorDialog.kt` 的调用方在 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。扫描结果显示：

- `DesktopApplication.kt` import 了 `showErrorDialog`
- 在约第 31 行调用 `showErrorDialog(message, stackTrace)`

根据当前片段推断，`DesktopApplication.kt` 是 `komga-tray` 的桌面入口或启动包装器。当底层 Komga 应用启动异常时，它会捕获错误信息和堆栈，然后交给 `showErrorDialog` 弹窗展示。依据是该文件名、导入关系，以及 `showErrorDialog(message, stackTrace)` 的调用形式。

### 下游：系统浏览器与文件管理器

`TrayIconRunner` 不直接操作系统 API，而是调用：

- `org.gotson.komga.openUrl`
- `org.gotson.komga.openExplorer`

这两个函数定义在 `komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt`。根据函数名和调用参数可以判断：

- `openUrl(url: String)` 用于打开系统默认浏览器。
- `openExplorer(file: File)` 用于打开系统文件管理器并定位或显示文件/目录。

根据当前片段推断，这两个函数封装了跨平台桌面操作，避免 `TrayIconRunner` 直接处理 Windows、macOS、Linux 差异。依据是它们位于 `Utils.kt`，且托盘菜单只关心“打开 URL / 打开文件管理器”这两个抽象动作。

### 下游：Compose Desktop 运行时

两个文件都依赖 Compose Desktop：

- `androidx.compose.ui.window.application`
- `androidx.compose.ui.window.Tray`
- `androidx.compose.ui.window.Window`
- `androidx.compose.material.*`
- `androidx.compose.foundation.*`

因此本目录虽然处在 Spring Boot 项目中，但 GUI 实现不是 Swing 或 JavaFX，而是 JetBrains Compose Desktop。

### 下游：Classpath 资源

GUI 图标依赖 classpath 下的 SVG 资源：

- `icons/komga-color.svg`
- `icons/komga-gray-minimal.svg`

菜单和弹窗文案依赖资源包：

- `komga-tray/src/main/resources/org/gotson/komga/messages.properties`
- 各语言 `messages_*.properties`

如果这些资源缺失，托盘图标、弹窗图标或本地化文案都会受到影响。

## 运行/调用流程

### 正常启动并显示托盘

1. 用户启动 Komga tray 应用。
2. Spring Boot 初始化应用上下文。
3. Spring 扫描到 `TrayIconRunner`，因为它是 `@Component`。
4. 如果当前不是 `test` profile，`TrayIconRunner` 生效。
5. Spring Boot 启动完成后调用 `ApplicationRunner.run(...)`。
6. `run(...)` 因为有 `@Async`，在异步线程中执行。
7. `run(...)` 调用 `runTray()`。
8. `runTray()` 进入 Compose Desktop 的 `application { ... }`。
9. Compose 创建 `Tray`：
   - 根据 profile 选择图标。
   - 从 classpath 加载 SVG。
   - 注册托盘菜单项。
10. 用户点击托盘菜单：
   - `Open Komga` 打开 `[URL已移除]><context-path>`。
   - `Show log file` 打开日志文件位置。
   - `Open configuration directory` 打开配置目录。
   - `Quit Komga` 退出 Compose application。

这里有一个重要细节：`komgaUrl` 使用的是 `localhost`，说明托盘菜单面向本机用户打开本机服务，不负责暴露公网地址、局域网地址或反向代理地址。

### 启动失败并显示错误弹窗

1. `DesktopApplication.kt` 启动 Komga。
2. 启动过程中发生异常。
3. 调用方准备 `message` 和可选 `stackTrace`。
4. 调用 `showErrorDialog(message, stackTrace)`。
5. `showErrorDialog` 启动 Compose Desktop `application`。
6. 创建居中、不可调整大小的 `Window`。
7. 窗口顶部显示 Komga 图标和错误消息。
8. 如果有堆栈：
   - 展示多行堆栈文本。
   - 显示复制按钮。
   - 用户点击后通过 `LocalClipboardManager` 写入剪贴板。
9. 用户点击关闭按钮或窗口关闭事件后，调用 `exitApplication()`。

这个流程和正常托盘流程是两个不同入口：正常情况下用户看到的是托盘；启动失败时用户看到的是错误窗口。

## 小白阅读顺序

1. 先读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`  
   这是最核心的文件。重点看 `ApplicationRunner`、构造函数注入、`komgaUrl`、`iconFileName` 和 `runTray()`。读完后应该能理解“应用启动后为什么会出现托盘图标”。

2. 再读 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt`  
   关注 `showErrorDialog` 的参数、`Window` 配置、`stackTrace != null` 时的分支，以及复制到剪贴板的逻辑。读完后应该能理解“启动失败时用户看到的窗口从哪里来”。

3. 然后看 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`  
   这里是 `showErrorDialog` 的调用方。重点找启动主流程、异常捕获、`message` 和 `stackTrace` 如何生成。

4. 接着看 `komga-tray/src/main/kotlin/org/gotson/komga/Utils.kt`  
   这里定义 `openUrl` 和 `openExplorer`。理解这两个函数后，就能知道托盘菜单点击后如何调用系统浏览器和文件管理器。

5. 最后看资源文件 `komga-tray/src/main/resources/org/gotson/komga/messages.properties`  
   对照 `RB.getString("...")` 的 key，确认菜单和弹窗显示文本来自哪里。如果要改界面文案或补翻译，需要从这里入手。

## 常见误区

1. 误以为这里是 Komga Web UI  
   这个目录不是浏览器里的前端页面，也不是 Komga 的 Web 管理界面。它只负责桌面托盘和错误弹窗。真正的 Web UI 不在 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui`。

2. 误以为 `TrayIconRunner` 启动 Web 服务  
   `TrayIconRunner` 不启动服务器。它只是读取 `WebServerEffectiveSettings`，拼出访问地址，然后在菜单里提供“打开 Komga”的入口。Web 服务的启动在其他模块或配置中完成。

3. 误以为 `Quit Komga` 一定等价于优雅关闭整个 Spring Boot 应用  
   代码里菜单项调用的是 Compose Desktop 的 `exitApplication`。根据当前片段只能确认它会退出 Compose application。它是否连带关闭整个 JVM 或 Spring Boot 上下文，需要结合桌面启动入口和运行环境判断，当前目录片段不能单独证明完整关闭语义。

4. 误以为错误弹窗只显示固定文本  
   `showErrorDialog` 接收 `text` 和可选 `stackTrace`。没有堆栈时窗口更简单；有堆栈时窗口变宽，并额外提供复制按钮。

5. 误以为 `TextField` 是可编辑日志输入框  
   这里的 `TextField` 用来展示堆栈。虽然没有显式 `readOnly = true`，但 `onValueChange = {}` 不更新状态，所以它实际更接近只读文本展示区域。

6. 误以为托盘图标总是彩色  
   `TrayIconRunner` 会检查 `env.activeProfiles.contains("mac")`。在 `mac` profile 下使用 `komga-gray-minimal.svg`，其他环境使用 `komga-color.svg`。这是为了适配不同系统菜单栏/托盘视觉风格。

7. 误以为菜单文字在 Kotlin 代码里维护  
   菜单和弹窗文字通过 `RB.getString(...)` 从资源包读取。修改文字或翻译时，应优先查 `komga-tray/src/main/resources/org/gotson/komga/messages.properties` 和对应语言文件，而不是在 `TrayIconRunner.kt` 或 `ErrorDialog.kt` 中搜索硬编码字符串。

8. 误以为这个目录可以脱离 Spring 单独理解完整行为  
   `ErrorDialog.kt` 相对独立，但 `TrayIconRunner.kt` 强依赖 Spring 注入、profile、日志配置和 Web server effective settings。理解托盘 URL、配置目录、日志路径时，必须把它放回 Spring Boot 应用上下文里看。
