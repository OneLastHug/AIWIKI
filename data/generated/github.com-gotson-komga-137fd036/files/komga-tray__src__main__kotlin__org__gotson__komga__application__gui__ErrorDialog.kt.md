# 文件：komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt

## 它负责什么

`ErrorDialog.kt` 负责在 Komga 桌面托盘版启动失败时，弹出一个独立的错误对话窗口。

它不是业务服务，也不参与 Web 服务运行；它的职责很集中：当 `komga-tray` 启动 Spring Boot 应用失败时，用 Compose Desktop 创建一个 GUI 窗口，把错误信息展示给用户，并在需要时提供堆栈信息复制功能。

从调用方 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt` 可以看到，主程序启动时会执行：

- `checkTempDirectory()` 检查临时目录；
- 设置若干系统属性；
- 通过 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动桌面版 Komga；
- 如果启动过程抛出异常，则根据异常类型组织错误文案；
- 最后调用 `showErrorDialog(message, stackTrace)` 显示错误窗口。

因此，这个文件可以理解为“桌面启动失败兜底 UI”。它让用户即使在服务没有正常启动时，也能看到明确的错误提示，而不是只在控制台或日志里留下异常。

## 关键组成

这个文件只有一个公开函数：

```kotlin
@Preview
fun showErrorDialog(
  text: String,
  stackTrace: String? = null,
)
```

参数含义如下：

- `text`：展示给用户看的主要错误信息，例如端口被占用、未知启动错误等。
- `stackTrace`：可选的异常堆栈字符串。为 `null` 时只展示简洁错误；不为 `null` 时展示完整堆栈，并提供复制按钮。

主要 import 可以分成几类理解。

第一类是 Compose Desktop 窗口与应用生命周期：

- `androidx.compose.ui.window.application`
- `androidx.compose.ui.window.Window`
- `WindowState`
- `WindowPlacement`
- `WindowPosition`
- `DpSize`

这些用于创建一个独立桌面窗口，并控制窗口是否可调整、初始位置、尺寸等。

第二类是 Compose UI 布局与控件：

- `Column`
- `Row`
- `Image`
- `Text`
- `TextField`
- `Button`
- `TextButton`
- `Modifier`
- `padding`
- `size`
- `fillMaxWidth`
- `Arrangement`
- `Alignment`

它们组成对话框内容：上方是 Komga 图标和错误文字，中间可选展示堆栈文本，下方是操作按钮。

第三类是资源与国际化：

- `org.gotson.komga.RB`
- `org.springframework.core.io.ClassPathResource`
- `org.jetbrains.compose.resources.decodeToSvgPainter`

`RB` 用于读取本地化字符串，例如：

- `dialog_error.title`
- `dialog_error.copy_clipboard`
- `dialog_error.close`

对应资源位于 `komga-tray/src/main/resources/org/gotson/komga/messages*.properties`。默认英文里是：

- `dialog_error.title=Komga failed to start`
- `dialog_error.copy_clipboard=Copy to clipboard`
- `dialog_error.close=Close`

`ClassPathResource("icons/komga-color.svg")` 用于从 classpath 读取 Komga 图标，再通过 `decodeToSvgPainter(LocalDensity.current)` 转换成 Compose 可绘制的 `Painter`。

第四类是剪贴板：

- `LocalClipboardManager`
- `AnnotatedString`

当存在 `stackTrace` 时，窗口会出现 `Copy to clipboard` 文本按钮，点击后把堆栈写入系统剪贴板。

`@Preview` 注解来自 `androidx.compose.desktop.ui.tooling.preview.Preview`。它通常用于 Compose 预览工具，但这里函数本身也被真实调用。不要因为看到 `@Preview` 就误以为它只是开发期预览代码。

## 上下游关系

上游调用方主要是 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`。

启动入口 `main(args: Array<String>)` 中包含如下错误处理逻辑：

```kotlin
try {
  SpringApplicationBuilder(DesktopApplication::class.java).apply {
    headless(false)
    run(*args)
  }
} catch (e: Exception) {
  val (message, stackTrace) =
    when (e.cause) {
      is PortInUseException -> RB.getString("error_message.port_in_use", (e.cause as PortInUseException).port) to null
      else -> RB.getString("error_message.unexpected") to e.stackTraceToString()
    }

  showErrorDialog(message, stackTrace)
}
```

这说明 `ErrorDialog.kt` 只处理“如何显示”，不负责“如何判断错误类型”。错误分类发生在 `DesktopApplication.kt`：

- 如果 `e.cause` 是 `PortInUseException`，说明端口被占用，只显示友好错误文案，不展示堆栈。
- 其他异常统一视为未知错误，显示通用错误文案，并把 `e.stackTraceToString()` 传给 `showErrorDialog`。

下游依赖主要是 Compose Desktop、资源文件和 classpath 图标：

- Compose Desktop 负责创建窗口、布局和按钮交互。
- `RB` 负责读取本地化文案。
- `icons/komga-color.svg` 负责窗口图标和内容区 logo。
- 系统剪贴板用于复制堆栈。

同目录还有 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`。它和 `ErrorDialog.kt` 都属于 `org.gotson.komga.application.gui` 包，但职责不同：

- `TrayIconRunner.kt`：应用正常启动后，创建系统托盘图标和菜单。
- `ErrorDialog.kt`：应用启动失败后，创建错误窗口。

两者都使用 Compose Desktop 的 `application { ... }`，也都通过 `ClassPathResource` 加载 SVG 图标，但触发时机完全不同。`TrayIconRunner` 是 Spring Bean，正常进入 Spring 生命周期后运行；`showErrorDialog` 是启动异常捕获后直接调用，通常发生在 Spring 应用未能成功起来的时候。

## 运行/调用流程

完整流程可以按“启动失败路径”理解：

1. 用户启动 Komga 桌面版。
2. `DesktopApplication.main` 开始执行。
3. 程序先检查临时目录，并设置系统属性，例如 `apple.awt.UIElement`、`org.jooq.no-logo`、`org.jooq.no-tips`。
4. 程序通过 `SpringApplicationBuilder` 启动 Spring Boot 应用，并设置 `headless(false)`，表示允许使用图形界面。
5. 如果 Spring 启动成功，错误窗口不会出现；后续正常流程会进入托盘相关逻辑，例如 `TrayIconRunner`。
6. 如果 Spring 启动抛出异常，进入 `catch (e: Exception)`。
7. `DesktopApplication.kt` 判断异常原因：
   - `PortInUseException`：生成端口占用提示，`stackTrace` 为 `null`。
   - 其他异常：生成通用错误提示，`stackTrace` 为完整堆栈。
8. 调用 `showErrorDialog(message, stackTrace)`。
9. `showErrorDialog` 调用 Compose Desktop 的 `application { ... }`，开启一个 Compose 应用事件循环。
10. 在 `Window` 中创建错误窗口：
    - 标题来自 `RB.getString("dialog_error.title")`；
    - 关闭窗口时调用 `exitApplication`；
    - 窗口不可调整大小；
    - 窗口居中显示；
    - 如果存在堆栈，宽度设置为 `800.dp`；
    - 如果不存在堆栈，宽度使用 `Dp.Unspecified`，由内容自然决定。
11. 窗口内容使用 `Column` 纵向排列：
    - 第一行 `Row` 显示 Komga logo 和错误文字。
    - 如果有 `stackTrace`，中间显示一个多行 `TextField`，最多 15 行。
    - 底部显示按钮区域。
12. 底部按钮区域根据是否有堆栈采用不同布局：
    - 有堆栈：`Arrangement.SpaceBetween`，左侧复制按钮，右侧关闭按钮。
    - 无堆栈：`Arrangement.End`，只有关闭按钮靠右。
13. 点击 `Copy to clipboard` 时：
    - 读取 `LocalClipboardManager.current`；
    - 调用 `clipboardManager.setText(AnnotatedString(stackTrace))`；
    - 把完整堆栈复制到系统剪贴板。
14. 点击 `Close` 或窗口关闭按钮时：
    - 调用 `exitApplication()`；
    - 结束这个 Compose Desktop 应用。

这里有一个细节：`TextField` 的 `onValueChange = {}` 是空实现，所以它虽然使用的是输入框组件，但用户修改内容不会改变 `value`。从效果上看，它更像一个可选中、可复制的只读堆栈展示框。代码没有显式设置 `readOnly = true`，但因为状态不更新，用户输入不会被保存到 UI 状态里。

## 小白阅读顺序

建议按下面顺序读，不要一上来陷入 Compose 的每个 modifier 细节。

第一步，先看函数签名：

```kotlin
fun showErrorDialog(
  text: String,
  stackTrace: String? = null,
)
```

先确认这个文件只暴露一个能力：给一段错误文字，以及可选的堆栈，弹出窗口。

第二步，看最外层结构：

```kotlin
application {
  Window(...) {
    Column(...) {
      ...
    }
  }
}
```

这三个层级分别对应：

- `application`：启动 Compose Desktop 应用循环；
- `Window`：创建桌面窗口；
- `Column`：窗口内部纵向布局。

第三步，看 `Window` 参数：

```kotlin
title = RB.getString("dialog_error.title")
onCloseRequest = ::exitApplication
resizable = false
state = WindowState(...)
icon = ...
```

这里能理解窗口的“外壳”：标题、关闭行为、是否可调整大小、位置、尺寸、窗口图标。

第四步，看第一段内容区：

```kotlin
Row {
  Image(...)
  Text(text)
}
```

这是最核心的用户提示：左边 Komga 图标，右边错误信息。

第五步，看 `stackTrace != null` 的两个分支。

第一个分支控制是否显示堆栈：

```kotlin
if (stackTrace != null)
  TextField(...)
```

第二个分支控制底部按钮：

```kotlin
if (stackTrace != null) {
  TextButton(...)
}
Button(...)
```

这说明 `stackTrace` 是这个 UI 的关键开关：有堆栈就展示详情和复制按钮，没有堆栈就只展示简洁错误和关闭按钮。

第六步，再回头看调用方 `DesktopApplication.kt`。这样能明白为什么端口占用错误没有堆栈，而未知错误有堆栈。端口占用是用户可理解、可处理的常见错误；未知错误需要保留堆栈，方便排查和反馈。

## 常见误区

误区一：以为 `@Preview` 表示这个函数只用于预览。

不是。虽然 `showErrorDialog` 标了 `@Preview`，但它被 `DesktopApplication.kt` 的 `main` 函数真实调用。这里的 `@Preview` 只是让 Compose 工具可能识别它为预览入口，不改变它作为普通 Kotlin 函数的运行方式。

误区二：以为这个错误窗口属于 Spring 管理的组件。

不是。`showErrorDialog` 不是 `@Component`，也没有依赖注入。它是一个普通顶层函数，在 Spring Boot 启动失败的 `catch` 分支中直接调用。这个设计很合理，因为此时 Spring 容器可能根本没有成功创建，不能依赖 Spring Bean 来显示错误。

误区三：以为 `stackTrace` 一定会展示。

不是。`stackTrace` 是可空参数。端口占用这类已知错误会传 `null`，窗口只显示友好提示和关闭按钮。只有未知异常才会传入 `e.stackTraceToString()`，窗口才显示多行堆栈和复制按钮。

误区四：以为 `TextField` 是给用户编辑堆栈用的。

从代码行为看，它不是为了编辑。`value = stackTrace` 固定传入，`onValueChange = {}` 不更新任何状态，因此用户输入不会改变显示数据。它主要利用 `TextField` 的多行文本展示和选择能力。根据当前片段推断，作者选择 `TextField` 是为了让堆栈更容易被选中或复制，同时又额外提供了完整复制按钮。

误区五：以为关闭窗口只是隐藏对话框。

不是。关闭窗口、点击 `Close` 按钮都会调用 `exitApplication()`。因为这是启动失败后的兜底应用窗口，关闭它就意味着结束这个 Compose Desktop 应用。此时主 Spring 应用已经启动失败，不存在继续后台运行的正常服务。

误区六：以为它和托盘图标是同一套流程。

不是。`TrayIconRunner.kt` 是正常启动后的托盘入口，依赖 Spring 成功创建 Bean，并通过 `ApplicationRunner` 执行。`ErrorDialog.kt` 是启动失败后的兜底窗口，不依赖 Spring Bean。两者都在 `application.gui` 包下，也都使用 Compose Desktop，但一个处理正常运行态，一个处理失败态。

误区七：忽略国际化资源。

窗口标题、按钮文字并没有硬编码成英文，而是通过 `RB.getString(...)` 读取资源。修改显示文案时，应该关注 `komga-tray/src/main/resources/org/gotson/komga/messages*.properties` 中的 `dialog_error.*` 键，而不是只改 Kotlin 文件。
