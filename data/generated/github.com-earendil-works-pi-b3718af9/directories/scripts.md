# 目录：scripts

## 它负责什么

`scripts` 是这个 monorepo 的“工程自动化层”，本身不承载业务运行时逻辑，而是围绕构建、检查、发布、版本同步、二进制打包、浏览器兼容烟测、会话统计与开发辅助任务提供命令入口。它和根 `package.json` 的 `scripts` 字段绑定很紧：例如 `npm run check` 会串起 `biome check`、依赖版本校验、TypeScript 相对导入校验、coding-agent shrinkwrap 校验、`tsgo --noEmit` 以及浏览器打包烟测；发布相关的 `release:*`、`publish:*`、`version:*` 也大多落到这里。

从职责上看，这个目录可以分成四类：

第一类是质量门禁脚本，例如 `check-pinned-deps.mjs`、`check-ts-relative-imports.mjs`、`check-browser-smoke.mjs`、`check-lockfile-commit.mjs`、`generate-coding-agent-shrinkwrap.mjs`。它们服务于本地检查、CI 或 git hook，目标是把依赖、导入格式、浏览器可打包性、lockfile 变更、shrinkwrap 一致性这些规则自动化。

第二类是发布与版本脚本，例如 `release.mjs`、`release-notes.mjs`、`publish.mjs`、`local-release.mjs`、`sync-versions.js`、`build-binaries.sh`。这些脚本连接 workspace version bump、changelog、release artifacts、npm package 发布、GitHub release notes、跨平台二进制产物等流程。

第三类是统计与诊断脚本，例如 `stats.ts`、`cost.ts`、`tool-stats.ts`、`edit-tool-stats.mjs`、`read-tool-stats.mjs`、`session-context-stats.mjs`、`session-transcripts.ts`。它们读取 `~/.pi/agent/sessions` 下的 session JSONL，产出 token、费用、工具调用、编辑工具使用、上下文规模、转录文本等分析结果。

第四类是迁移或专项维护脚本，例如 `update-source-imports-to-ts.sh`，用于把 package 源码目录里的相对 `.js` import 改写为 `.ts` import，以配合当前 TypeScript 输出策略。

## 直接子目录地图

`scripts` 当前没有直接子目录，所有脚本都平铺在目录根部。根据当前片段推断，这是一种有意的工具箱式布局：脚本数量不算少，但每个脚本都是独立命令入口，根 `package.json` 直接引用具体文件，例如 `node scripts/check-browser-smoke.mjs`、`node scripts/release.mjs patch`、`node scripts/local-release.mjs`。

这种布局的阅读重点不是“目录分层”，而是按流程把脚本分组：检查链路、发布链路、统计链路、维护链路。不要因为它没有子目录就认为它是杂项垃圾桶；相反，很多仓库级规则都集中在这里。

## 关键入口

最重要的入口首先是根 `package.json` 的 `scripts` 字段。它定义了外部开发者实际会调用的命令，并把命令分发到 `scripts` 目录。常见入口包括：

`npm run check` 是主质量门禁入口。它调用 `check:pinned-deps`、`check:ts-imports`、`check:shrinkwrap`、`check:browser-smoke`，再配合 `biome check --write --error-on-warnings .` 和 `tsgo --noEmit`。如果要理解本仓库“提交前必须满足什么”，应从这里进入。

`npm run release:patch`、`npm run release:minor`、`npm run release:major` 都进入 `scripts/release.mjs`。这个脚本注释里列出完整发布步骤：检查未提交变更、bump version 或设置显式版本、更新 changelog、重新生成 release artifacts、运行检查、提交并打 tag、添加下一轮 `Unreleased` changelog、推送 main 和 tag。

`npm run release:local` 进入 `scripts/local-release.mjs`，用于本地构建未发布 release 并做 smoke test。虽然当前只读取到入口名，结合仓库发布说明和命令名可推断它服务于正式发布前的本地包验证。

`npm run publish` 和 `npm run publish:dry` 进入 `scripts/publish.mjs`，前置执行 `prepublishOnly`，也就是 clean、build、check。它是 npm 发布入口之一。

`npm run shrinkwrap:coding-agent` 和 `npm run check:shrinkwrap` 都进入 `scripts/generate-coding-agent-shrinkwrap.mjs`，前者生成，后者带 `--check` 做一致性验证。

`npm run profile:tui`、`npm run profile:rpc` 进入 `scripts/profile-coding-agent-node.mjs`，用于 profiling coding-agent 的 TUI 或 RPC 模式。

## 主流程位置

检查主流程位于 `package.json` 的 `check` 脚本和几个 `check-*` 文件之间。`check-pinned-deps.mjs` 会递归收集 `package.json`，要求直接外部依赖使用精确版本，内部 workspace 依赖和非 registry specifier 例外。`check-ts-relative-imports.mjs` 使用 TypeScript AST 扫描 `.ts` 文件，禁止非声明文件中出现相对 `.js` import/export/import type。`check-browser-smoke.mjs` 用 `esbuild` 将 `scripts/browser-smoke-entry.ts` 以 `platform: "browser"` 打包，捕获浏览器导出链路中误引入 Node-only runtime 的问题。`browser-smoke-entry.ts` 本身故意导入 `@earendil-works/pi-ai` 和 `@earendil-works/pi-agent-core` 的一组浏览器侧 API，作为烟测覆盖面。

发布主流程在 `scripts/release.mjs`。它是一个串行脚本，使用 `execSync` 调用 git、npm、检查命令，并维护版本、changelog、tag、提交和 push。`sync-versions.js` 是它背后的版本同步工具之一：它读取 `packages/*/package.json`，确认所有 workspace package 使用 lockstep version，并把内部包依赖版本同步到当前版本。`release-notes.mjs` 则处理 coding-agent changelog 到 GitHub release notes 的抽取，以及历史 release note 链接修复。注意文档中不需要展开外部链接，理解它处理“发布说明文本和链接重写”即可。

二进制构建流程主要在 `build-binaries.sh`。脚本注释说明它本地镜像 `.github/workflows/build-binaries.yml`，支持 `--skip-install`、`--skip-deps`、`--skip-build`、`--platform`、`--out`，目标产物包括 darwin、linux、windows 的 x64/arm64 压缩包，默认输出到 `packages/coding-agent/binaries`。

统计分析主流程围绕 session 文件。`stats.ts`、`cost.ts`、`tool-stats.ts`、`session-context-stats.mjs` 等都默认读 `~/.pi/agent/sessions`，区别在输出维度：token/费用、工具调用大小、上下文报告、会话转录等。`session-transcripts.ts` 还会复用 `packages/coding-agent/src/core/session-manager.ts` 的 `parseSessionEntries`，说明它不是简单按行拼接，而是用核心包的 session parser 还原消息。

## 推荐阅读顺序

1. 先读根 `package.json` 的 `scripts` 字段，建立“外部命令到脚本文件”的索引。尤其关注 `check`、`release:*`、`publish:*`、`version:*`、`shrinkwrap:coding-agent`。
2. 再读检查链路：`check-pinned-deps.mjs`、`check-ts-relative-imports.mjs`、`check-browser-smoke.mjs`、`browser-smoke-entry.ts`。这组最能体现仓库编码规则。
3. 然后读版本与发布链路：`release.mjs`、`sync-versions.js`、`release-notes.mjs`、`local-release.mjs`、`publish.mjs`、`build-binaries.sh`。阅读时把它们和 changelog、workspace package、CI 发布流程联系起来。
4. 最后读统计与诊断脚本：`stats.ts`、`cost.ts`、`tool-stats.ts`、`edit-tool-stats.mjs`、`read-tool-stats.mjs`、`session-context-stats.mjs`、`session-transcripts.ts`。这组更多服务维护者理解真实使用数据，不是普通开发的第一入口。
5. 如果要理解导入扩展名策略，再补读 `update-source-imports-to-ts.sh` 和 `check-ts-relative-imports.mjs` 的关系：一个负责机械迁移，一个负责持续阻止回退。

## 常见误区

不要把 `scripts` 当成应用代码入口。真正的包源码在 `packages/*`，这里主要是仓库级自动化和维护工具。

不要绕过根 `package.json` 直接猜脚本用途。很多脚本的真实语义来自 npm script 的组合关系，例如 `check-browser-smoke.mjs` 只有和 `browser-smoke-entry.ts` 以及 `npm run check` 放在一起看才完整。

不要误以为 `release.mjs` 只是改版本号。它还处理 changelog、artifacts、检查、提交、tag、下一轮 changelog 和 push，是高影响脚本。

不要把 `sync-versions.js` 理解为普通依赖更新器。它服务于 monorepo lockstep version，重点是内部 workspace 包之间的版本一致性，而不是升级外部依赖。

不要忽视 `.mjs`、`.ts`、`.sh` 的执行环境差异。`.mjs` 多数直接由 Node 执行；`.ts` 脚本依赖项目的 TypeScript/运行器配置；`.sh` 是 shell 自动化，尤其 `build-binaries.sh` 和 `update-source-imports-to-ts.sh` 会对平台、路径和文件改写更敏感。

不要把统计脚本输出当成源代码事实。`stats.ts`、`cost.ts`、`session-*` 系列依赖本机 `~/.pi/agent/sessions` 数据，结果随用户机器和历史会话变化。它们适合诊断和观察，不适合作为构建产物或发布依据。
