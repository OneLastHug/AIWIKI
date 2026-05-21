# Komga 源码学习入口

这组文档面向第一次阅读 Komga 仓库的中文读者。建议先把它当成“地图”而不是完整 API 手册：先理解项目要解决的问题、模块边界和运行时主线，再按兴趣进入具体包。本文档只基于仓库中的 `README.md`、`DEVELOPING.md`、Gradle/npm 配置、入口类、资源配置、测试规则和源码目录编写；没有证据的地方会在对应页面标注“根据当前文件推断”。

## 推荐阅读顺序

1. [00-overview.md](00-overview.md)：先了解 Komga 是什么、核心能力、后端/前端/托盘三部分各自承担什么职责。
2. [01-tech-stack.md](01-tech-stack.md)：再看技术栈和本地运行条件，尤其是 Gradle、Spring Boot、Kotlin、Vue 2、SQLite、jOOQ、Flyway、Lucene 等基础概念。
3. [02-architecture.md](02-architecture.md)：随后阅读源码分层，重点看 `domain`、`application`、`infrastructure`、`interfaces` 的依赖方向，以及 `komga-webui` 和 `komga-tray` 如何接入。
4. [03-runtime-flow.md](03-runtime-flow.md)：最后串起启动、配置加载、HTTP/API、任务队列、扫描、SSE、数据库迁移和前端运行流。
5. [critical_paths.json](critical_paths.json)：如果你想直接进源码，可把其中的目录和文件列表当作阅读清单。

## 后续最值得看的目录

- `komga/src/main/kotlin/org/gotson/komga`：后端主代码，包含 Spring Boot 入口和主要分层。
- `komga/src/main/kotlin/org/gotson/komga/domain/model`：领域对象，如 `Library`、`Series`、`Book`、`Media`、`ReadProgress`、`KomgaUser`。
- `komga/src/main/kotlin/org/gotson/komga/domain/service`：核心业务流程，如库管理、扫描、书籍分析、元数据刷新、导入、转换、缩略图、阅读列表。
- `komga/src/main/kotlin/org/gotson/komga/application/tasks`：异步任务队列的定义、提交、处理和调度入口。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest`：Web UI 使用的 REST API 控制器集合。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/opds`、`interfaces/api/kobo`、`interfaces/api/kosync`：对外阅读客户端协议入口。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/jooq`：SQLite 持久化实现和查询辅助。
- `komga/src/main/kotlin/org/gotson/komga/infrastructure/mediacontainer`、`infrastructure/metadata`、`infrastructure/image`、`infrastructure/search`：媒体解析、元数据导入、图片处理和 Lucene 搜索相关实现。
- `komga/src/flyway`：数据库 schema 演进和任务数据库迁移。
- `komga-webui/src`：Vue 2 前端入口、路由、插件、服务、视图和类型定义。
- `komga-tray/src/main/kotlin`：桌面托盘包装层，主要负责启动后端和显示系统托盘菜单。
- `komga/src/test/kotlin/org/gotson/komga/architecture`：架构规则测试，是理解包边界的高价值入口。

## 后续最值得看的文件

- `README.md`：项目定位和功能列表。
- `DEVELOPING.md`：本地开发要求、三项目组织、常用 Gradle/npm 命令和 Spring profiles。
- `settings.gradle`：确认 Gradle 模块只包含 `komga` 与 `komga-tray`，前端以独立 npm 项目被后端构建任务调用。
- `build.gradle.kts`、`komga/build.gradle.kts`、`komga-webui/package.json`、`komga-tray/build.gradle.kts`：构建、依赖和运行时形态的证据。
- `komga/src/main/kotlin/org/gotson/komga/Application.kt`：后端启动入口。
- `komga/src/main/resources/application.yml`：默认端口、配置目录、数据库文件、Lucene 目录、外部配置导入和 Spring/Flyway 设置。
- `komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/LibraryController.kt`：典型 REST 请求如何进入领域服务和任务队列。
- `komga/src/main/kotlin/org/gotson/komga/application/tasks/TaskHandler.kt`：后台任务如何落到扫描、分析、元数据、转换、索引等业务服务。
- `komga-webui/src/main.ts`、`komga-webui/src/router.ts`、`komga-webui/src/services/komga-libraries.service.ts`：前端启动、路由和调用 REST API 的典型路径。
