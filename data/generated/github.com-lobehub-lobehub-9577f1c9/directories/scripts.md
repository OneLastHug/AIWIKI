# 目录：scripts

## 它可能负责什么
这个目录包含 84 个被抽样展示的文件。请从文件命名、子目录和关键源码入手理解它在项目中的职责。

## 文件列表节选
```text
scripts/generate-oidc-jwk.mjs
scripts/create-test-tasks.js
scripts/generateSpaTemplates.mts
scripts/countEnWord.ts
scripts/devStartupSequence.mts
scripts/setup-test-postgres-db.sh
scripts/checkConsoleLog.mts
scripts/dockerPrebuild.mts
scripts/replaceComponentImports.ts
scripts/registerDesktopEnv.cjs
scripts/vercelIgnoredBuildStep.js
scripts/runNextDesktop.mts
scripts/migrate-spa-navigation.ts
scripts/copySpaBuild.mts
scripts/i18nWorkflow/const.ts
scripts/i18nWorkflow/index.ts
scripts/i18nWorkflow/flattenLocaleKeys.ts
scripts/i18nWorkflow/utils.ts
scripts/i18nWorkflow/genDefaultLocale.ts
scripts/i18nWorkflow/protectedPatterns.ts
scripts/i18nWorkflow/genDiff.ts
scripts/i18nWorkflow/cleanUnusedKeys.ts
scripts/i18nWorkflow/i18nConfig.ts
scripts/i18nWorkflow/analyzeUnusedKeys.ts
scripts/serverLauncher/startServer.js
scripts/resetOnboarding/index.ts
scripts/nextauth-to-betterauth/index.ts
scripts/nextauth-to-betterauth/verify.ts
scripts/nextauth-to-betterauth/_internal/db.ts
scripts/nextauth-to-betterauth/_internal/config.ts
scripts/nextauth-to-betterauth/_internal/env.ts
scripts/seedUserInfo/index.ts
scripts/mobileSpaWorkflow/template.ts
scripts/mobileSpaWorkflow/index.ts
scripts/mobileSpaWorkflow/upload.ts
scripts/docsWorkflow/const.ts
scripts/docsWorkflow/autoCDN.ts
scripts/docsWorkflow/toc.ts
scripts/docsWorkflow/index.ts
scripts/docsWorkflow/utils.ts
scripts/docsWorkflow/optimized.ts
scripts/changelogWorkflow/const.ts
scripts/changelogWorkflow/index.ts
scripts/changelogWorkflow/generateChangelog.ts
scripts/changelogWorkflow/buildStaticChangelog.ts
scripts/cdnWorkflow/index.ts
scripts/cdnWorkflow/utils.ts
scripts/cdnWorkflow/uploader.ts
scripts/cdnWorkflow/optimized.ts
scripts/cdnWorkflow/s3/index.ts
scripts/cdnWorkflow/s3/utils.ts
scripts/cdnWorkflow/s3/types.ts
scripts/_shared/checkDeprecatedAuth.test.ts
scripts/_shared/checkDeprecatedAuth.js
scripts/clerk-to-betterauth/export-clerk-users-with-api.ts
scripts/clerk-to-betterauth/index.ts
scripts/clerk-to-betterauth/verify.ts
scripts/clerk-to-betterauth/__tests__/parseCsvLine.test.ts
scripts/clerk-to-betterauth/test/put_clerk_exported_users_csv_here.txt
scripts/clerk-to-betterauth/prod/put_clerk_exported_users_csv_here.txt
scripts/clerk-to-betterauth/_internal/db.ts
scripts/clerk-to-betterauth/_internal/config.ts
scripts/clerk-to-betterauth/_internal/utils.ts
scripts/clerk-to-betterauth/_internal/env.ts
scripts/clerk-to-betterauth/_internal/load-data-from-files.ts
scripts/clerk-to-betterauth/_internal/types.ts
scripts/hotfixWorkflow/index.ts
scripts/buildSitemapIndex/index.ts
scripts/mdxWorkflow/index.ts
scripts/releaseWorkflow/index.ts
scripts/migrateServerDB/errorHint.js
scripts/migrateServerDB/index.ts
scripts/migrateServerDB/docker.cjs
scripts/readmeWorkflow/const.ts
scripts/readmeWorkflow/index.ts
scripts/readmeWorkflow/syncAgentIndex.ts
scripts/readmeWorkflow/utlis.ts
scripts/readmeWorkflow/syncPluginIndex.ts
scripts/readmeWorkflow/syncProviderIndex.ts
scripts/dbmlWorkflow/index.ts
scripts/electronWorkflow/buildDesktopChannel.ts
scripts/electronWorkflow/mergeMacReleaseFiles.js
scripts/electronWorkflow/buildElectron.ts
scripts/electronWorkflow/setDesktopVersion.ts
```

## 小白阅读建议
- 先看项目说明、`index` 入口、路由、业务服务、类型/结构定义等文件。英文文件名只是代码命名，不要求先理解英文语义。
- 暂时跳过构建产物、测试快照和重复样板。
- 如果这里是业务目录，优先找“谁调用它”和“它调用谁”。
