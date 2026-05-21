# 文件：README.md
## 它负责什么
`README.md` 是仓库的入口说明页，面向第一次接触项目的人，先回答“这是什么、能做什么、去哪里找更详细资料”。从内容看，它不是实现逻辑文件，而是项目级导航页，核心职责是把 Komga 这个媒体服务器的定位、能力范围、安装入口、开发入口和致谢信息集中放在最前面。

它明确说明 Komga 是面向 comics、mangas、BDs、magazines 和 eBooks 的 media server，并通过一组功能清单把产品边界讲清楚：Web UI 浏览、元数据管理、OPDS、Kobo Sync、KOReader Sync、REST API、重复检测、导入读列表等。根据当前片段推断，它的角色更像“项目首页”，而不是“用户手册”或“开发规范”的承载点。

## 关键组成
这个文件主要由几块组成：

1. 顶部徽章区：展示 OpenCollective、GitHub Sponsors、Discord、CI 状态、最新发布、Docker 下载量、翻译状态等外部信息入口。
2. 项目标题与简介：`Komga` 名称、app icon，以及一句简短定位说明。
3. Features：列出产品能力，帮助读者快速判断这个项目适不适合自己的需求。
4. Installation：只给出安装文档入口，没有把安装步骤全文放在 README 里。
5. Documentation：引导到官网获取更完整资料。
6. Develop in Komga：引导开发者查看 `DEVELOPING.md`。
7. Translation、Powered by、Credits：说明翻译渠道、开发支持和图标来源。

结合仓库上下文，`README.md` 还承担“把仓库结构的关键外部入口串起来”的作用。根 `build.gradle.kts` 指向主模块 `komga` 和桌面模块 `komga-tray`，`komga-webui/package.json` 则说明前端是独立的 Vue 2 工程。README 自身不展开这些模块，但它把项目门面和主要外部路径放在一起。

## 上下游关系
上游是项目本身的构建、发布和文档体系。README 的内容来自产品和工程事实，但它不直接定义这些事实。真正的实现和打包逻辑分布在 `build.gradle.kts`、`settings.gradle`、`komga/build.gradle.kts`、`komga-webui/package.json` 等文件里。比如根 `settings.gradle` 只包含 `komga` 和 `komga-tray` 两个模块，而 `komga/build.gradle.kts` 负责 Spring Boot 后端、Web UI 构建、资源打包和发布配置。

下游是三类读者：
1. 普通用户：从 README 判断产品能力，再跳转到官网安装文档。
2. 开发者：从 README 进入 `DEVELOPING.md`，再去看源码结构和构建方式。
3. 贡献者和翻译者：通过翻译徽章和相关链接进入协作流程。

所以 README 充当的是“分发层入口”，而不是业务层或框架层。它向下只负责导流，不直接实现功能。根据当前片段推断，真正的运行路径大概率是后端 `komga` 提供 API 和静态资源，前端 `komga-webui` 构建后被复制进后端资源目录，由 Spring Boot 对外服务。

## 运行/调用流程
如果把它当作“阅读流程”，顺序大致是：

1. 打开 `README.md`，先看标题和简介，确认项目定位。
2. 看 Features，判断是否覆盖自己的使用场景。
3. 需要安装时，跳转到官网安装文档。
4. 需要了解开发时，进入 `DEVELOPING.md`。
5. 需要参与翻译时，走 Weblate 的入口。
6. 需要了解项目支持和致谢时，再看顶部徽章和底部 Credits。

如果把它放到仓库实际运行链路里看，README 本身不参与调用，但它隐含了一个上下游路径：用户从文档进入项目 -> 选择安装或开发入口 -> 后端 `komga` 和前端 `komga-webui` 按各自构建流程产出成品 -> 最终形成可部署的 Komga 服务。根据当前片段推断，`README.md` 是这个链路的起点，而不是执行环节。

## 小白阅读顺序
1. 先读标题和一句简介，建立“这是个什么项目”的印象。
2. 再看 Features，理解它是给漫画、图像小说、杂志和电子书用的媒体服务器。
3. 接着看 Installation 和 Documentation，区分“项目介绍”与“安装细节”的边界。
4. 如果你关心开发，再去看 `DEVELOPING.md`，不要在 README 里硬找实现细节。
5. 如果你想理解工程结构，再顺着 `settings.gradle`、`build.gradle.kts`、`komga/build.gradle.kts`、`komga-webui/package.json` 看模块怎么拆。

## 常见误区
1. 把 README 当成完整手册：它只负责总览和入口，不会替代官网文档。
2. 把功能清单当成实现细节：Features 说明“支持什么”，不是“怎么实现”。
3. 只看 README 就判断工程结构：真正的模块划分要看 `settings.gradle` 和各子模块的构建文件。
4. 误以为前端和后端是同一个工程：从 `komga-webui/package.json` 可以看出前端是独立的 Vue 工程，后端在 `komga/build.gradle.kts` 里负责集成。
5. 忽略开发入口：README 已经把 `DEVELOPING.md` 作为开发指南入口，开发者不该在这里猜流程。
