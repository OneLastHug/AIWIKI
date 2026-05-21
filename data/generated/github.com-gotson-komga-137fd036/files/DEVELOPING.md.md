# 文件：DEVELOPING.md

## 它负责什么

`DEVELOPING.md` 是 Komga 仓库面向贡献者和本地开发者的开发入口文档。它不参与程序运行，也没有代码层面的 `import` / `export`，而是说明如何把这个多模块项目在本地跑起来、如何构建前后端、如何执行测试、如何打 Docker 包，以及提交信息需要遵循什么规范。

从内容看，它主要解决几个问题：

1. 说明开发环境要求：需要 `Java JDK 21+`，前端需要 `Nodejs 18+`，具体 Node 版本可参考 `.nvmrc`。
2. 说明项目结构：Komga 由 `komga`、`komga-webui`、`komga-tray` 三块组成。
3. 说明后端开发方式：通过 Gradle 任务运行 Spring Boot 后端，并用 Spring Profiles 控制开发行为。
4. 说明前端开发方式：在 `komga-webui` 下使用 `npm run serve` 启动 Vue 开发服务器。
5. 说明构建 Docker 镜像的前置步骤：先构建并复制前端资源，再用 JReleaser 生成 Docker 打包产物。
6. 说明提交规范：提交信息遵循 Conventional Commits，用于自动版本、发布和 release notes 生成。

它的角色更像“本地开发路线图”，不是完整架构文档。读它可以知道第一步怎么启动项目，但不能靠它理解所有业务模块。

## 关键组成

`DEVELOPING.md` 可以按章节拆成以下几部分。

第一部分是 `Requirements`。这里列出本地开发的基础依赖：`Java JDK version 21+` 和 `Nodejs version 18+`。后端是 Kotlin / Spring Boot / Gradle 生态，所以 JDK 是硬要求；前端在 `komga-webui` 目录下，由 `package.json` 管理依赖和脚本，所以需要 Node。

第二部分是 `Setting up the project`。它要求在 `komga-webui` 目录执行：

```bash
npm install
```

这个步骤只安装前端工具链和依赖。它不会安装 Gradle，因为项目使用仓库内的 `./gradlew` wrapper。小白容易误以为在根目录执行 `npm install`，但文档明确说的是 `komga-webui` 目录。

第三部分是 `Commit messages`。Komga 使用 `Conventional Commits`。根目录 `build.gradle.kts` 中的 JReleaser 配置也能印证这一点：发布 changelog 使用 `conventional-commits` 预设，并按 `perf`、`i18n`、`dependencies` 等标签分类。因此提交信息不是单纯的风格要求，而是会影响自动发布说明和版本管理。

第四部分是 `Project organization`。文档把仓库分为三个项目：

- `komga`：Spring Boot 后端，提供 API，同时在运行时托管前端构建后的静态资源。
- `komga-webui`：VueJS 前端，在编译期构建，运行时由后端服务静态文件。
- `komga-tray`：桌面托盘图标包装层。

根目录 `settings.gradle` 中实际 include 的 Gradle 模块是 `komga` 和 `komga-tray`；`komga-webui` 是独立的 Node/Vue 前端项目，不作为 Gradle 子模块直接 include。这一点有助于理解为什么前端需要单独在 `komga-webui` 下执行 `npm install` / `npm run serve`。

第五部分是 `Backend development`。这是文档最核心的一段，包含 Spring profiles 和 Gradle tasks。

Spring Profiles 包括：

- `dev`：增加日志、禁用周期扫描、使用内存数据库，并允许来自 `localhost:8081` 的 CORS 请求。这个 profile 是前后端分离开发时的关键。
- `localdb`：开发环境下把数据库存到 `./localdb`，适合保留本地数据反复调试。
- `noclaim`：启动时如果没有用户，则自动创建初始用户并输出用户名密码。配合 `dev` 时会创建固定账号 `admin@example.org` / `admin` 和 `user@example.org` / `user`；不配合 `dev` 时会创建随机密码并写入日志。

Gradle tasks 包括：

- `bootRun`：本地启动后端应用。
- `prepareThymeLeaf`：构建前端并把 bundle 复制到 `/resources/public`，用于测试由 Spring Boot 托管的最新前端构建产物。
- `test`：运行自动化测试，提交前应执行。
- `jooq-codegen-primary`：生成 jOOQ DSL，说明后端数据库访问层依赖 jOOQ 生成代码。

第六部分是 `Frontend development`。前端开发服务器在 `komga-webui` 下执行：

```bash
npm run serve
```

`komga-webui/package.json` 中对应脚本是 `vue-cli-service serve --port 8081`，所以开发服务器默认跑在 `localhost:8081`。文档还说明这个开发服务器会把 API 目标指向 `localhost:25600`，也就是本地后端服务。因此前端开发通常需要同时启动后端 `bootRun`，并且后端必须启用 `dev` profile，否则浏览器请求会被 CORS 拦截。

第七部分是 `Docker`。构建 Docker 镜像前需要两步：

```bash
./gradlew prepareThymeLeaf
./gradlew jreleaserPackage
```

第一步确保前端静态资源已构建并复制到后端资源目录；第二步通过 JReleaser 准备 Docker 打包产物。根目录 `build.gradle.kts` 中存在 JReleaser 的 Docker packager 配置，镜像名包括 `komga:latest`、`komga:{{projectVersion}}` 和 `komga:{{projectVersionMajor}}.x`，目标平台包括 `linux/amd64`、`linux/arm/v7`、`linux/arm64/v8`。文档说最终 `Dockerfile` 会出现在 `komga/build/jreleaser/package/docker/`。

## 上下游关系

`DEVELOPING.md` 的上游主要是仓库的实际构建配置和项目结构：

- `settings.gradle` 定义 Gradle 子模块：`komga`、`komga-tray`。
- `build.gradle.kts` 定义根构建逻辑、Kotlin 版本、Gradle wrapper 版本、ktlint、dependency updates、JReleaser 发布和 Docker 打包配置。
- `komga/build.gradle.kts` 定义后端模块的 Spring Boot、jOOQ、资源构建等任务。文档中提到的 `prepareThymeLeaf`、`bootRun`、`jooq-codegen-primary` 都属于这里或相关 Gradle 任务体系。
- `komga-webui/package.json` 定义前端脚本，其中 `serve` 对应文档里的 `npm run serve`。
- `.nvmrc` 给 Node 版本提供本地依据，文档要求开发者查看它。

它的下游是开发者的操作流程：

- 新贡献者根据它安装 JDK、Node 和前端依赖。
- 后端开发者根据它选择 `dev`、`localdb`、`noclaim` profile。
- 前端开发者根据它知道前端 dev server 在 `localhost:8081`，后端 API 在 `localhost:25600`。
- 发布或打包人员根据它知道 Docker 构建前要先运行 `prepareThymeLeaf`，再运行 `jreleaserPackage`。
- 提交代码的人根据它使用 Conventional Commits，从而让自动 changelog 和 release notes 正常工作。

因为它是 Markdown 文档，所以没有运行时调用方。所谓“调用方”更准确地说是人和 CI/release 流程：人读它执行命令，构建脚本则由这些命令间接触发。

## 运行/调用流程

本地开发的典型流程可以按后端、前端、Docker 三条线理解。

后端单独开发流程：

1. 确认本机安装 `Java JDK 21+`。
2. 在仓库根目录使用 Gradle wrapper。
3. 选择 Spring profiles。最常见的是：

```bash
./gradlew bootRun --args='--spring.profiles.active=dev,noclaim'
```

如果希望使用持久化本地数据库，则使用：

```bash
./gradlew bootRun --args='--spring.profiles.active=dev,localdb,noclaim'
```

4. `dev` profile 会让本地开发更方便：更多日志、禁用周期扫描、内存数据库、允许 `localhost:8081` CORS。
5. `noclaim` profile 会在无用户时创建初始用户，便于本地登录测试。
6. 修改后端代码后，提交前运行：

```bash
./gradlew test
```

前后端联调流程：

1. 进入 `komga-webui`。
2. 第一次开发先安装依赖：

```bash
npm install
```

3. 启动前端开发服务器：

```bash
npm run serve
```

4. 前端会运行在 `localhost:8081`。
5. 同时在仓库根目录启动后端，通常需要 `dev` profile。
6. 浏览器访问前端 dev server，前端请求会指向 `localhost:25600` 的后端 API。
7. 如果后端没有启用 `dev`，CORS 不允许来自 `localhost:8081` 的请求，前端联调会失败。

测试后端托管前端构建产物的流程：

1. 在根目录运行：

```bash
./gradlew prepareThymeLeaf
```

2. 该任务会构建 `komga-webui`，并把前端 bundle 复制到后端的 public resources。
3. 再启动 Spring Boot 后端。
4. 此时访问后端服务时，看到的是后端托管的静态前端，而不是 Vue dev server。

Docker 构建流程：

1. 先构建并复制前端资源：

```bash
./gradlew prepareThymeLeaf
```

2. 再通过 JReleaser 准备 Docker 打包内容：

```bash
./gradlew jreleaserPackage
```

3. 生成的 Dockerfile 位于：

```text
komga/build/jreleaser/package/docker/
```

根据当前片段推断，Docker 镜像依赖后端 jar 和已打包好的前端静态资源；依据是文档要求先执行 `prepareThymeLeaf`，根目录 JReleaser 配置又把 `komga/build/libs/komga-{{projectVersion}}.jar` 作为发布 artifact，并配置了 Docker packager。

## 小白阅读顺序

建议不要从命令开始死记，而是按“项目是什么、怎么跑、怎么联调、怎么打包”的顺序读。

1. 先读 `Project organization`。先搞清楚 `komga` 是后端，`komga-webui` 是前端，`komga-tray` 是桌面托盘包装。否则后面看到 Gradle、npm、Docker 混在一起会很容易混乱。
2. 再读 `Requirements`。确认 JDK 和 Node 版本。后端看 JDK，前端看 Node。
3. 再读 `Setting up the project`。记住 `npm install` 是在 `komga-webui` 目录执行，不是在根目录。
4. 接着读 `Backend development` 的 Spring profiles。尤其要理解 `dev`、`localdb`、`noclaim` 的区别：`dev` 是开发便利配置，`localdb` 是持久化本地库，`noclaim` 是自动创建初始用户。
5. 然后读 `Gradle tasks`。先掌握 `bootRun` 和 `test`，再理解 `prepareThymeLeaf` 和 `jooq-codegen-primary`。
6. 再读 `Frontend development`。理解 `localhost:8081` 是前端开发服务器，`localhost:25600` 是后端 API 目标；前端联调必须让后端启用 `dev`。
7. 最后读 `Docker`。Docker 构建不是第一天必须掌握的内容，它依赖你先理解前端如何被构建进后端资源目录。

如果要结合源码继续看，建议顺序是：

1. `settings.gradle`：确认 Gradle 模块边界。
2. `build.gradle.kts`：看根构建、发布、Docker/JReleaser 配置。
3. `komga/build.gradle.kts`：看后端任务、依赖、jOOQ、Spring Boot 配置。
4. `komga-webui/package.json`：看前端脚本和 Vue 技术栈。
5. `komga/src/main/resources/application-*.yml`：看各 profile 的具体配置，例如 `localdb`、`dev` 等。

## 常见误区

误区一：以为 `DEVELOPING.md` 是架构文档。  
它只是开发指南，告诉你怎么配置环境、启动、测试和打包。业务领域模型、API 设计、数据库访问、前端路由等都不在这个文件里。

误区二：在仓库根目录执行 `npm install`。  
文档明确要求在 `komga-webui` 目录执行。根目录是 Gradle 构建入口，前端依赖由 `komga-webui/package.json` 管理。

误区三：以为 `komga-webui` 是 Gradle 子模块。  
`settings.gradle` 只 include 了 `komga` 和 `komga-tray`。`komga-webui` 是前端工程，通过 npm/Vue CLI 管理；它和后端的连接点主要是开发时的 API 代理，以及构建后由 `prepareThymeLeaf` 复制到后端静态资源目录。

误区四：前端开发时只启动 `npm run serve`。  
前端页面可以起来，但 API 请求需要后端。文档说明前端 dev server 会连接 `localhost:25600`，所以还需要启动后端 `bootRun`。

误区五：后端不启用 `dev` profile 就做前端联调。  
这样通常会遇到 CORS 问题，因为 `dev` profile 才允许来自 `localhost:8081` 的前端请求。

误区六：混淆 `dev,noclaim` 和 `dev,localdb,noclaim`。  
`dev,noclaim` 适合空数据库快速测试；`dev,localdb,noclaim` 适合保留已有本地数据。是否使用 `localdb` 会影响数据是否存到 `./localdb`。

误区七：以为 `prepareThymeLeaf` 会启动前端开发服务器。  
它不是 `npm run serve`。它的作用是构建前端并复制 bundle，让 Spring Boot 后端可以托管静态前端资源。

误区八：直接运行 `jreleaserPackage` 打 Docker。  
文档要求先运行 `./gradlew prepareThymeLeaf`，确保前端资源已经构建并进入后端资源目录，然后再运行 `./gradlew jreleaserPackage`。

误区九：忽略 Conventional Commits。  
这里的提交规范会影响自动版本、发布和 release notes。根构建配置中的 JReleaser changelog 也依赖 conventional commits 进行分类和生成。

误区十：把 `noclaim` 当成生产默认配置。  
`noclaim` 会在没有用户时创建初始用户并输出密码，适合本地开发或特殊初始化场景。尤其配合 `dev` 时会创建固定弱密码账号，不能把它理解成生产安全默认值。
