# 文件：komga-tray/src/main/resources/application-windows.yml

## 它负责什么

这个文件是 `komga-tray` 在 Windows 平台上的专用 Spring Boot 配置层。它的核心作用有两个：

1. 把桌面版 Komga 的用户配置目录改到 Windows 的常用位置 `LOCALAPPDATA/Komga`。
2. 指定 Windows 下 `kepubify` 可执行文件的默认名字为 `kepubify.exe`，让 KEPUB 转换功能能在桌面端自动找到工具。

从结构上看，它不是业务逻辑文件，而是“平台环境适配文件”。它负责把 Windows 运行环境、外部配置目录、以及依赖的命令行工具名称对齐。

## 关键组成

这个文件只有两块关键配置：

- `komga.config-dir: ${LOCALAPPDATA}/Komga`
  - 把 Komga 的配置目录定到 Windows 用户环境变量 `LOCALAPPDATA` 下。
  - 这意味着用户自己的 `application.yml`、数据库、日志、临时文件等，都会围绕这个目录展开。

- `komga.kobo.kepubify-path: kepubify.exe`
  - 给 `KepubConverter` 提供默认工具名。
  - 在 Windows 安装包里，这个文件名通常会被放进应用目录或随安装包分发，所以这里不写绝对路径，而是依赖可执行文件名。

另外还有：

- `spring.config.import`
  - 依次导入 `optional:file:${komga.config-dir}/application.yml`
  - `optional:file:${komga.config-dir}/application.yaml`
  - `optional:file:${komga.config-dir}/application.properties`

这表示桌面版启动时，会自动把用户自己的外部配置文件叠加进来；没有这些文件也不会报错，因为用了 `optional:`。

## 上下游关系

上游主要有两层：

- 启动层：`komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`
  - 这个入口通过 `SpringApplicationBuilder` 启动桌面应用。
  - 根据当前仓库片段推断，Windows 包装配置由发行打包层注入 profile，见 `conveyor.conf` 里的 `windows.options += "-Dspring.profiles.include=windows"`。
  - 也就是说，这个文件通常是 Windows 发行版启动时被激活的。

- 基础默认配置层：`komga/src/main/resources/application.yml`
  - 主工程里定义了默认的 `komga.config-dir: ${user.home}/.komga`。
  - Windows 版在这里把默认路径改写掉，避免和跨平台默认值混在一起。

下游主要有：

- `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KepubConverter.kt`
  - 这里通过 `@Value("${komga.kobo.kepubify-path:#{null}}")` 读取该配置。
  - 如果用户没有在设置里单独指定路径，就会回退到这里给的 `kepubify.exe`。
  - 这说明这个文件直接影响 KEPUB 转换功能是否可用。

- `spring.config.import` 导入的外部配置文件
  - 用户在 `LOCALAPPDATA/Komga` 下放的配置，会覆盖或补充默认值。
  - 所以这个文件既是默认值来源，也是用户配置的挂载点。

## 运行/调用流程

1. Windows 版桌面程序启动，入口是 `DesktopApplication.kt`。
2. 发行打包配置 `conveyor.conf` 为 Windows 注入 `-Dspring.profiles.include=windows`。
3. Spring Boot 读取通用配置，再加载 `application-windows.yml`。
4. `komga.config-dir` 被设为 `%LOCALAPPDATA%/Komga`。
5. Spring 再从这个目录尝试导入用户自定义配置文件：
   - `application.yml`
   - `application.yaml`
   - `application.properties`
6. `KepubConverter` 启动时读取 `komga.kobo.kepubify-path`：
   - 若用户设置里已经指定路径，优先用用户设置；
   - 否则退回到这里的 `kepubify.exe`。
7. 如果 `kepubify.exe` 真存在且可执行，转换功能启用；否则功能关闭或继续尝试回退逻辑。

## 小白阅读顺序

1. 先看 `komga-tray/src/main/resources/application-windows.yml`
   - 先记住它只做两件事：改配置目录、设 `kepubify` 默认名。

2. 再看 `komga/src/main/resources/application.yml`
   - 理解主配置默认值是什么。
   - 这样你能看出 Windows 文件到底覆盖了哪一部分。

3. 然后看 `conveyor.conf`
   - 重点看 Windows 构建时如何注入 `spring.profiles.include=windows`。
   - 这一步能解释为什么这个文件只在 Windows 版生效。

4. 接着看 `komga-tray/src/main/kotlin/org/gotson/komga/DesktopApplication.kt`
   - 搞清楚桌面版启动入口。

5. 最后看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/kobo/KepubConverter.kt`
   - 理解 `komga.kobo.kepubify-path` 是怎么被消费的。

## 常见误区

- 误区一：把它当成业务配置文件。
  - 其实它更像“Windows 平台适配层”，不是核心领域逻辑。

- 误区二：以为 `kepubify.exe` 一定是固定安装路径。
  - 不是。这里仅仅给了默认文件名，真正怎么找到它，还要看进程工作目录、打包方式和用户设置。

- 误区三：以为 `spring.config.import` 会强制要求这些文件存在。
  - 不会，前面有 `optional:`，所以文件不存在时是允许的。

- 误区四：以为这个文件会自动在任何 Windows 环境生效。
  - 根据当前片段推断，它依赖打包/启动时把 `windows` profile 激活；仓库里的 `conveyor.conf` 明确做了这件事。

- 误区五：忽略用户配置覆盖顺序。
  - `application-windows.yml` 给的是默认值，`LOCALAPPDATA/Komga` 下的外部配置和运行时设置，可能继续覆盖它。
