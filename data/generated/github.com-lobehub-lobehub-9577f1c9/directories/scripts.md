# 目录：scripts

## 它负责什么

`scripts` 是仓库根部的工程自动化脚本集合，服务对象不是某一个运行时业务模块，而是整个 LobeHub monorepo 的“辅助流水线层”。它把常见的开发、构建、发布、迁移、文档同步、国际化生成、桌面端打包、移动端 SPA 资源上传等流程封装成可由 `package.json` scripts、CI 或开发者手动调用的入口。

从 `package.json` 的命令绑定看，`scripts` 主要承担五类职责：第一类是构建辅助，例如 `scripts/copySpaBuild.mts`、`scripts/generateSpaTemplates.mts`、`scripts/buildSitemapIndex/index.ts`；第二类是工作流生成，例如 `workflow:docs`、`workflow:i18n`、`workflow:readme`、`workflow:changelog`；第三类是发布与分支流程，例如 `releaseWorkflow`、`hotfixWorkflow`；第四类是运行环境与数据库，例如 `devStartupSequence.mts`、`migrateServerDB`、`setup-test-postgres-db.sh`；第五类是平台特定流程，例如 `electronWorkflow` 和 `mobileSpaWorkflow`。

因此，阅读这个目录时不要把它理解为应用源码的一层。它更像“仓库运维脚本层”：消费 `src`、`docs`、`locales`、`packages/database`、`apps/desktop`、`public` 等目录的产物或配置，再输出构建结果、生成文件、同步内容或执行外部命令。

## 直接子目录地图

`scripts/_shared` 放共享检查逻辑，目前可见的是认证相关的废弃配置检查，如 `checkDeprecatedAuth.js` 及其测试。

`scripts/buildSitemapIndex` 负责生成站点地图索引，入口是 `scripts/buildSitemapIndex/index.ts`，由 `build-sitemap` 命令调用。

`scripts/cdnWorkflow` 是文档或变更日志图片 CDN 处理流程。根据入口文件可见，它会扫描内容中的图片链接、使用缓存文件、下载或上传资源，并通过 `uploader.ts`、`optimized.ts`、`utils.ts`、`s3` 子目录协作完成 CDN 化。

`scripts/changelogWorkflow` 负责 changelog 相关生成。它包含 `generateChangelog.ts` 和 `buildStaticChangelog.ts`，总入口 `index.ts` 主要触发静态 changelog 构建。

`scripts/clerk-to-betterauth` 和 `scripts/nextauth-to-betterauth` 是认证体系迁移脚本。前者结构更完整，包含 `_internal`、`prod`、`test`、`__tests__`，说明它既有内部通用逻辑，也有生产、测试和验证入口。后者也有 `_internal` 与 `verify.ts`，用于 NextAuth 到 Better Auth 的迁移和校验。

`scripts/dbmlWorkflow` 用于数据库模型文档或 DBML 生成，入口是 `scripts/dbmlWorkflow/index.ts`。

`scripts/docsWorkflow` 负责文档索引和侧边栏一类的自动生成。入口 `index.ts` 读取文档目录、TOC 配置和标题，再更新文档首页与侧边栏；`autoCDN.ts`、`optimized.ts`、`utils.ts` 是相关辅助流程。

`scripts/electronWorkflow` 面向桌面端发布与打包，包含 `buildElectron.ts`、`buildDesktopChannel.ts`、`setDesktopVersion.ts`、`mergeMacReleaseFiles.js`。它会联动 `apps/desktop` 下的 Electron 打包命令。

`scripts/hotfixWorkflow` 和 `scripts/releaseWorkflow` 分别封装 hotfix 分支与 release 分支流程，入口均为 `index.ts`。

`scripts/i18nWorkflow` 是国际化主流程目录，包含默认语言生成、差异分析、未使用 key 分析和清理、扁平化 key、保护模式等脚本。它对应 `workflow:i18n`、`i18n:unused`、`i18n:unused-clean`。

`scripts/mdxWorkflow` 用于 MDX 内容处理，入口是 `scripts/mdxWorkflow/index.ts`。

`scripts/migrateServerDB` 是服务端数据库迁移执行器。它加载多层 `.env`，根据 `DATABASE_DRIVER` 在 Drizzle 的 `node-postgres` 和 `neon-serverless` migrator 间选择，并使用 `packages/database/migrations` 作为迁移目录。

`scripts/mobileSpaWorkflow` 负责移动端 SPA 发布流程。入口 `index.ts` 先执行 `vite build`，再上传 `dist/mobile/assets`，最后生成移动端 HTML 模板源文件。

`scripts/readmeWorkflow` 用于 README 相关内容同步，例如模型供应商、插件、Agent 索引等，入口是 `scripts/readmeWorkflow/index.ts`。

`scripts/resetOnboarding`、`scripts/seedUserInfo` 更偏维护或数据初始化任务，分别对应 onboarding 状态重置和用户信息种子数据处理。

`scripts/serverLauncher` 存放服务启动封装，目前可见入口是 `startServer.js`。

## 关键入口

最重要的入口不是所有文件，而是 `package.json` 中暴露出来的命令。开发启动入口是 `scripts/devStartupSequence.mts`，对应 `dev`，它会先处理环境变量，再启动 Next.js 与 Vite SPA 的开发进程，并等待 Next 服务就绪。

构建相关入口包括 `scripts/copySpaBuild.mts`、`scripts/generateSpaTemplates.mts`、`scripts/buildSitemapIndex/index.ts`、`scripts/dockerPrebuild.mts`。其中 `build:spa:copy` 串联 SPA 构建产物复制与模板生成，`build-sitemap` 负责 sitemap。

数据库入口是 `scripts/migrateServerDB/index.ts`，对应 `db:migrate`。它是理解仓库服务端数据库迁移时最应先看的脚本。

国际化入口有三层：总流程 `scripts/i18nWorkflow/index.ts`，未使用 key 分析 `scripts/i18nWorkflow/analyzeUnusedKeys.ts`，清理入口 `scripts/i18nWorkflow/cleanUnusedKeys.ts`。总流程先做 diff analysis，再生成默认 locale，最后生成 i18n 文件。

文档与内容入口集中在 `scripts/docsWorkflow/index.ts`、`scripts/docsWorkflow/autoCDN.ts`、`scripts/changelogWorkflow/index.ts`、`scripts/changelogWorkflow/generateChangelog.ts`、`scripts/readmeWorkflow/index.ts`、`scripts/mdxWorkflow/index.ts`。

桌面端入口是 `scripts/electronWorkflow/buildElectron.ts`、`scripts/electronWorkflow/buildDesktopChannel.ts`、`scripts/electronWorkflow/setDesktopVersion.ts`。其中 `buildElectron.ts` 会按当前 OS 选择 `apps/desktop` 下的 macOS、Windows 或 Linux 打包命令。

移动端 SPA 入口是 `scripts/mobileSpaWorkflow/index.ts`，它要求存在移动端 S3 相关环境变量，并按“构建、上传、生成模板”的顺序执行。

## 主流程位置

日常开发主流程在 `scripts/devStartupSequence.mts`。它体现了本仓库的双服务开发形态：Next.js 后端或 SSR 侧先启动，Vite SPA 再接入；端口和环境变量来自 CLI 参数、`PORT`、`.env`、`.env.[env]`、`.env.[env].local` 的组合。

数据库迁移主流程在 `scripts/migrateServerDB/index.ts`。它的核心路径是加载环境变量，判断 `DATABASE_URL` 是否存在，动态导入 `packages/database/src/server`，再执行 `packages/database/migrations`。如果缺少数据库连接，它会跳过迁移，这一点对 desktop 或无数据库环境很重要。

文档生成主流程在 `scripts/docsWorkflow/index.ts`。它读取 `docsFiles` 和 `toc`，为中英文文档生成首页和侧边栏内容。根据当前片段推断，它是文档导航结构的自动化来源之一，依据是入口中存在对 `HOME_PATH`、`SIDEBAR_PATH` 的更新调用。

国际化主流程在 `scripts/i18nWorkflow/index.ts`。这个文件很短，但它是编排点：先 `genDiff()`，再 `genDefaultLocale()`。要理解具体生成规则，需要继续看 `genDiff.ts`、`genDefaultLocale.ts`、`i18nConfig.ts` 和 `utils.ts`。

发布主流程分散在 `scripts/releaseWorkflow/index.ts`、`scripts/hotfixWorkflow/index.ts`、`scripts/changelogWorkflow`、`scripts/electronWorkflow`。其中 release/hotfix 更偏 Git 分支操作，changelog 更偏内容产物，electron 更偏桌面端包产物。

CDN 主流程在 `scripts/cdnWorkflow/index.ts` 和 `scripts/mobileSpaWorkflow/index.ts`。前者面向文档、changelog 等内容资源，后者面向移动端构建产物。二者都不是普通本地开发必经路径，通常依赖环境变量或外部对象存储配置。

## 推荐阅读顺序

1. 先读 `package.json` 中所有包含 `scripts/` 的命令，建立“哪些脚本被正式暴露”的入口地图。
2. 再读根部单文件入口：`scripts/devStartupSequence.mts`、`scripts/checkConsoleLog.mts`、`scripts/copySpaBuild.mts`、`scripts/generateSpaTemplates.mts`。这些文件能帮助理解本仓库开发、检查和 SPA 模板产物的基础流程。
3. 接着看高频工作流目录：`scripts/i18nWorkflow/index.ts`、`scripts/docsWorkflow/index.ts`、`scripts/changelogWorkflow/index.ts`、`scripts/readmeWorkflow/index.ts`。
4. 如果关注后端和部署，再看 `scripts/migrateServerDB/index.ts`、`scripts/dockerPrebuild.mts`、`scripts/vercelIgnoredBuildStep.js`。
5. 如果关注客户端分发，再看 `scripts/electronWorkflow/buildElectron.ts`、`scripts/mobileSpaWorkflow/index.ts`、`scripts/cdnWorkflow/index.ts`。
6. 最后再读迁移类脚本 `scripts/clerk-to-betterauth`、`scripts/nextauth-to-betterauth`，因为它们更像阶段性工程迁移工具，阅读成本较高，也不一定是日常主流程。

## 常见误区

不要把 `scripts` 当作线上应用运行时代码。它大量使用 `execSync`、文件系统读写、环境变量和构建产物路径，主要运行在开发机、CI 或发布流程中。

不要看到 `index.ts` 就认为它一定是唯一入口。有些目录的关键入口通过 `package.json` 直接暴露到子文件，例如 `scripts/changelogWorkflow/generateChangelog.ts`、`scripts/docsWorkflow/autoCDN.ts`、`scripts/i18nWorkflow/analyzeUnusedKeys.ts`。

不要忽略环境变量。`migrateServerDB`、`mobileSpaWorkflow`、CDN 上传和部分发布流程都依赖外部配置；缺少变量时可能跳过、失败或生成不同产物。

不要把认证迁移目录当成当前认证系统的主实现。`clerk-to-betterauth`、`nextauth-to-betterauth` 从命名和结构看是迁移工具，真正的认证运行时代码应回到 `src`、`packages` 或相关服务模块中查找。

不要逐文件背诵这个目录。对于 overview 级阅读，更重要的是把它分成“开发启动、构建产物、文档内容、国际化、数据库、发布、平台打包、迁移工具”几条主线，再沿 `package.json` 命令反查具体入口。
