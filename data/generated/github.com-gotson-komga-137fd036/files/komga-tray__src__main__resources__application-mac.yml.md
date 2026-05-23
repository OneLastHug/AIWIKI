# 文件：komga-tray/src/main/resources/application-mac.yml

## 它负责什么
这是 `komga-tray` 的 macOS 专属 Spring Boot 配置文件。它不是业务代码，而是给启动阶段的配置系统看的：当程序以 `mac` profile 运行时，Spring 会自动加载它，用来规定 mac 上的日志位置、用户配置目录，以及某些外部工具路径。

从当前片段看，它主要解决三件事：

1. 把日志写到 macOS 习惯的位置：`${user.home}/Library/Logs/Komga/komga.log`
2. 把用户配置目录固定到：`${user.home}/Library/Application Support/Komga`
3. 让应用在启动时自动合并用户自己放在配置目录里的 `application.yml`、`application.yaml`、`application.properties`

## 关键组成
- `logging.file.name`
  - 指定日志文件路径。
  - 这里把日志放到 `Library/Logs/Komga/komga.log`，符合 macOS 的用户级应用数据布局。

- `komga.config-dir`
  - 定义 Komga 的配置目录。
  - 后续 `spring.config.import` 会引用它，所以这是一个核心锚点变量。

- `komga.kobo.kepubify-path`
  - mac 版默认值是 `kepubify`。
  - 这说明 tray 程序会依赖一个名为 `kepubify` 的外部命令或可执行文件，mac 下不带 `.exe` 后缀。

- `spring.config.import`
  - 导入三个外部配置文件，而且都用了 `optional:`。
  - 这意味着这些文件存在就加载，不存在也不报错，适合首次启动或未做用户自定义配置的场景。

## 上下游关系
上游是启动时的 profile 选择机制。根据 `conveyor.conf` 里的 `-Dspring.profiles.include=mac`，打包后的 mac 版本会把 `mac` profile 加进去，所以 Spring Boot 会自动读取 `application-mac.yml`。

同目录下还有 `application-windows.yml`，结构几乎相同，但路径和可执行文件名不同，说明这两个文件是按平台拆分的系统配置层。

下游是整个 `komga-tray` 应用启动过程中的环境配置。`DesktopApplication.kt` 里通过 `SpringApplicationBuilder(DesktopApplication::class.java)` 启动 Spring 容器，容器初始化时会把这里的配置合并进来，再影响日志、外部配置加载和后续依赖这些配置的组件。

## 运行/调用流程
1. 打包或启动 mac 版 tray 程序。
2. 启动参数或打包配置注入 `spring.profiles.include=mac`。
3. Spring Boot 识别到 `mac` profile，自动加载 `application-mac.yml`。
4. 这里定义的 `komga.config-dir`、`logging.file.name` 等值进入环境。
5. `spring.config.import` 继续尝试读取用户目录下的 `application.yml`、`application.yaml`、`application.properties`。
6. 如果这些外部文件存在，它们会补充或覆盖默认配置。
7. 最终 `DesktopApplication.kt` 启动出来的容器，就在这套 mac 专属配置上运行。

## 小白阅读顺序
1. 先看 `komga-tray/src/main/resources/application-mac.yml`，建立“这是什么配置文件”的直觉。
2. 再对照 `komga-tray/src/main/resources/application-windows.yml`，看平台差异。
3. 读 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`，确认它是在 Spring 容器启动时生效，而不是某个普通函数调用。
4. 最后看 `conveyor.conf` 里的 `spring.profiles.include=mac`，理解这个文件是怎么被选中的。

## 常见误区
- 它不是业务逻辑文件。这里不会直接处理漫画库、扫描、同步之类功能，只负责启动配置。
- `spring.config.import` 里的文件是 `optional`，所以“没有这些文件”不是错误，这是设计好的。
- `komga.config-dir` 不是程序内部硬编码路径，而是给 Spring 配置系统和外部用户配置共用的变量。
- 不要把它和 `application.yml` 混为一谈。`application-mac.yml` 是平台覆盖层，`application.yml` 通常才是更通用的基础配置。
- `kepubify` 在 mac 和 windows 的默认值不同；mac 这里没有 `.exe`，这不是漏写，而是平台差异。
