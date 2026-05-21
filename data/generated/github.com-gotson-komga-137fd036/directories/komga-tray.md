# 目录：komga-tray

## 它负责什么

`komga-tray` 是 Komga 的桌面托盘包装层，职责不是再做一套后端，而是把已有的 `komga` Spring Boot 应用包装成一个可桌面启动的程序。根据 `DEVELOPING.md` 的描述，它是一个 “thin desktop wrapper”，核心体验是常驻系统托盘或菜单栏，方便用户在本机启动、查看和管理 Komga，而不是通过命令行直接跑服务。

它还承担了平台差异化启动配置、桌面入口类、以及随包分发的原生依赖整理。也就是说，这个目录更像“桌面发行版工程”，而不是业务代码主仓库。

## 关键组成

这个目录下的直接内容主要是几块：

- `build.gradle.kts`：子工程构建入口，声明依赖 `:komga`，并接入 Compose Desktop、Conveyor 和应用启动配置。
- `src/main/kotlin/org/gotson/komga/DesktopApplication.kt`：真正的桌面启动入口，`main()` 在这里。
- `src/main/resources/application-mac.yml`、`src/main/resources/application-windows.yml`：平台专用配置，主要是日志位置、配置目录、`kepubify` 路径，以及从用户配置目录继续导入 Spring 配置。
- `src/main/resources/icons/komga-color.svg`、`src/main/resources/icons/komga-gray-minimal.svg`：桌面端图标资源。
- `lib/mac/...`、`lib/windows/...`：打包时随应用携带的原生动态库，明显是为了桌面端相关依赖的运行时完整性。
- `conveyor/required-jdk-modules.txt`：打包工具 Conveyor 所需的 JDK 模块清单。

从 `build.gradle.kts` 可以看出，这个目录并不独立实现完整功能，而是复用 `project(":komga")` 里的业务与服务器逻辑，再叠加桌面运行时和发行打包能力。

## 上下游关系

上游是 `komga` 主工程。`komga-tray` 通过 `implementation(project(":komga"))` 直接依赖它，所以桌面程序的应用上下文、异常处理、资源消息、以及可能的 UI/服务能力，主要都来自 `komga` 模块。

它的下游主要有两个方向：

- 运行时下游：桌面应用本身，启动后会跑 `org.gotson.komga.DesktopApplicationKt`。
- 打包下游：`conveyor.conf` 和 `conveyor/required-jdk-modules.txt` 这类配置，说明它还被纳入安装包/分发包的构建流程。

另外，`DEVELOPING.md` 把它和 `komga-webui`、`komga` 一起列为项目三大部分，这说明它不是附属样例，而是正式发行链路的一环。

## 运行/调用流程

根据当前片段推断，它的启动链路大致是：

1. 用户从桌面图标或打包后的启动器进入 `komga-tray`。
2. `main()` 先调用 `checkTempDirectory()`，确保临时目录状态可用。
3. 代码设置桌面相关系统属性，比如 `apple.awt.UIElement=true`，避免在 macOS 上表现成普通前台窗口程序，同时关闭 jOOQ 的 logo 和提示输出。
4. 通过 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动 Spring 容器，并显式 `headless(false)`，说明它允许桌面 UI 能力存在。
5. 如果启动异常，按异常类型分支处理：
   - `PortInUseException`：说明 Komga 可能已经在运行，弹出端口占用提示。
   - 其他异常：显示通用错误对话框，并带堆栈信息。
6. `DesktopApplication` 继承自 `Application`，并加了 `@EnableAsync`，说明桌面入口仍复用主应用的大部分配置，只是换了启动形态。

平台配置的作用也很明确：`application-mac.yml` 和 `application-windows.yml` 把日志、配置目录和 `kepubify` 路径按系统区分开，同时继续从用户配置目录导入外部配置文件。

## 小白阅读顺序

1. 先看 `DEVELOPING.md`，确认 `komga-tray` 在整个仓库里的定位。
2. 再看 `komga-tray/build.gradle.kts`，理解它如何依赖 `:komga` 和 Compose Desktop。
3. 接着读 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`，把启动流程抓住。
4. 然后看 `src/main/resources/application-mac.yml`、`application-windows.yml`，理解平台差异。
5. 最后扫一下 `lib/` 和 `conveyor/required-jdk-modules.txt`，把“为什么要带这些原生库”与“怎么打包”补齐。

## 常见误区

- 误以为 `komga-tray` 是另一套完整应用。实际上它更像桌面启动壳，核心业务仍在 `komga`。
- 误以为这里会有大量业务逻辑。当前证据显示，这里主要是启动、配置、图标和原生依赖。
- 误把 `application-mac.yml`、`application-windows.yml` 当成全局配置。它们更像桌面发行版的默认运行参数，真正用户配置仍会从 `${komga.config-dir}` 下继续导入。
- 误认为 `DesktopApplication.kt` 自己实现了托盘逻辑。根据当前片段推断，它主要负责启动 Spring 应用和异常兜底，托盘相关行为更可能分布在 `komga` 主模块中。
