# 目录：`komga-tray/src/main/resources`
## 它负责什么
这个目录是 `komga-tray` 桌面壳模块的资源层，主要放运行时会被直接打进包里的静态配置和图标资产。它本身不写业务逻辑，但会影响应用启动后的默认环境、日志位置、外部配置加载方式，以及系统托盘和错误弹窗的视觉呈现。

从当前片段看，这个目录的职责很明确：  
- 给 Windows 和 macOS 提供不同的 Spring Boot 默认配置。  
- 提供托盘图标和弹窗图标的 SVG 资源。  
- 让桌面程序在打包后仍然能通过 classpath 读取这些资源。

## 关键组成
- `application-windows.yml`：Windows 平台的默认配置。
  - `komga.config-dir` 默认指向 `${LOCALAPPDATA}/Komga`。
  - `komga.kobo.kepubify-path` 默认是 `kepubify.exe`。
  - `spring.config.import` 会继续尝试读取该配置目录下的 `application.yml`、`application.yaml`、`application.properties`。
- `application-mac.yml`：macOS 平台的默认配置。
  - `logging.file.name` 默认写到 `${user.home}/Library/Logs/Komga/komga.log`。
  - `komga.config-dir` 默认是 `${user.home}/Library/Application Support/Komga`。
  - `komga.kobo.kepubify-path` 默认是 `kepubify`。
  - 同样通过 `spring.config.import` 引入用户目录里的外部配置。
- `icons/komga-color.svg`：彩色版图标，给非 mac 视图或通用场景使用。
- `icons/komga-gray-minimal.svg`：灰度极简版图标，给 mac 托盘使用。

## 上下游关系
上游是构建配置和启动代码。`komga-tray/build.gradle.kts` 把 `compose.desktop.currentOs` 和 `compose.components.resources` 引进来，说明这些资源会随桌面应用一起被打包并在运行时从 classpath 读取。  
下游主要有两个消费点：

- `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`  
  这里通过 `ClassPathResource("icons/$iconFileName")` 直接读取图标；`env.activeProfiles.contains("mac")` 时选 `komga-gray-minimal.svg`，否则选 `komga-color.svg`。  
- `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/ErrorDialog.kt`  
  这里也从 `ClassPathResource("icons/komga-color.svg")` 读取图标，用在错误弹窗里。

从配置角度看，`spring.config.import` 指向的外部文件目录，则会被 Spring Boot 后续配置解析链消费；也就是说，这个目录定义的是“默认值和入口”，真正的用户覆盖值来自外部配置目录。

## 运行/调用流程
1. 应用启动时，`DesktopApplication` 通过 Spring Boot 拉起桌面程序。  
2. Spring 根据当前平台装配对应 profile，加载 `application-windows.yml` 或 `application-mac.yml`。  
3. 配置里的 `komga.config-dir`、`logging.file.name` 等值成为默认运行环境。  
4. `spring.config.import` 再去读取用户配置目录下的外部文件，形成“内置默认值 + 用户覆盖值”的组合。  
5. 启动到托盘阶段时，`TrayIconRunner` 根据 active profile 选择图标文件名。  
6. `TrayIconRunner` 或 `ErrorDialog` 再从 `resources/icons/` 下按 classpath 读取 SVG，转换成 Compose 可用的 painter。  

根据当前片段推断，这套资源设计的目标是让同一份桌面程序在 Windows/macOS 上表现出不同的默认路径、日志位置和托盘外观，同时保持配置可覆盖。

## 小白阅读顺序
1. 先看 `komga-tray/build.gradle.kts`，确认这个模块是桌面应用资源包，不是普通后端模块。  
2. 再看 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`，理解启动入口。  
3. 接着看 `komga-tray/src/main/kotlin/org/gotson/komga/application/gui/TrayIconRunner.kt`，看图标资源是怎么被选中和读取的。  
4. 再看 `komga-tray/src/main/resources/application-windows.yml`、`application-mac.yml`，理解平台差异和外部配置注入。  
5. 最后看 `icons/komga-color.svg` 和 `icons/komga-gray-minimal.svg`，把文件名和运行时效果对应起来。

## 常见误区
- 容易把这里当成“纯静态图片目录”，其实它还承担平台默认配置的职责。  
- 容易忽略 `spring.config.import`，以为应用只认打包内配置；实际上它还会读取用户本地配置目录。  
- 容易以为图标只在某一个地方使用，但 `TrayIconRunner` 和 `ErrorDialog` 都会消费它。  
- 容易误读 `komga-config-dir` 之类路径值为固定常量；它们是按平台和用户环境展开的变量，不是硬编码绝对路径。  
- 容易忽略 mac 与 Windows 的差异：mac 还额外定义了日志文件默认位置，而 Windows 这里没有同等字段。
