# 文件：package.json

## 一句话定位

`package.json` 是这个仓库的根级 npm 工作区清单，负责定义 `pi-monorepo` 的包管理边界、统一脚本入口、根级开发依赖、Node 版本约束、发布/版本流程入口，以及部分依赖版本覆盖策略。

## 它暴露/定义了什么

这个文件首先把仓库声明为私有 ESM monorepo：`"private": true`、`"type": "module"`。它不作为可发布 npm 包本身对外暴露，而是作为根工作区编排层存在。

它定义的核心内容有四类：

1. `workspaces`：声明 `packages/*` 以及若干 `packages/coding-agent/examples/extensions/...` 示例扩展也参与 npm workspace 管理。根据当前片段推断，主包包括 `tui`、`ai`、`agent`、`coding-agent`，示例扩展也需要共享根依赖、锁文件和 npm workspace 解析。
2. `scripts`：提供构建、检查、测试、发布、版本同步、shrinkwrap 生成、性能分析等统一入口。
3. `devDependencies`：集中固定根级工具链版本，例如 `@biomejs/biome`、`typescript`、`@typescript/native-preview`、`tsx`、`esbuild`、`husky`。
4. `engines` 与 `overrides`：约束 Node 必须为 `>=22.19.0`，并强制部分依赖链使用指定 `rimraf` 版本。

## 谁调用它

主要调用者是开发者、CI、发布脚本和 npm 本身。

开发者会直接运行 `npm run check`、`npm run build`、`npm run release:local`、`npm run shrinkwrap:coding-agent` 等命令。CI 通常会依赖 `npm ci` 读取该文件和 lockfile，再执行根脚本完成检查、发布或构建。npm workspace 机制会读取 `workspaces`，决定哪些子包参与 `--workspaces` 操作。`husky` 会通过 `prepare` 脚本安装 Git hooks。

根据当前片段推断，仓库内发布相关自动化也以这里的 `release:*`、`version:*`、`publish:*` 脚本作为入口，因为根脚本串联了版本变更、锁文件刷新、本地发布产物、GitHub release 链接修复等流程。

## 它调用谁

`package.json` 本身不执行逻辑，但它的 scripts 会调用多个内部脚本、工具和子包脚本。

内部脚本包括 `scripts/check-browser-smoke.mjs`、`scripts/check-pinned-deps.mjs`、`scripts/check-ts-relative-imports.mjs`、`scripts/generate-coding-agent-shrinkwrap.mjs`、`scripts/profile-coding-agent-node.mjs`、`scripts/sync-versions.js`、`scripts/publish.mjs`、`scripts/local-release.mjs`、`scripts/release.mjs`、`scripts/release-notes.mjs`。

外部工具包括 `biome`、`tsgo`、`npm version`、`npm install --package-lock-only --ignore-scripts`、`husky`。`build` 脚本还会进入 `packages/tui`、`packages/ai`、`packages/agent`、`packages/coding-agent` 并调用各自的 `npm run build`。

## 核心流程

日常质量检查流程集中在 `check`：先运行 `biome check --write --error-on-warnings .` 做格式化/静态检查并将警告视为错误，然后检查依赖是否固定版本，再检查 TypeScript 相对导入规范，接着验证 `coding-agent` shrinkwrap 是否最新，再用 `tsgo --noEmit` 做类型检查，最后运行浏览器 smoke 检查。这个脚本是根级质量门禁，修改代码后风险最高也最常被调用。

构建流程由 `build` 串行执行四个核心包的构建：`packages/tui`、`packages/ai`、`packages/agent`、`packages/coding-agent`。顺序看起来是有意安排的，根据当前片段推断可能反映包间依赖关系：UI、AI、agent、coding-agent 需要按固定顺序产出。

版本流程由 `version:patch`、`version:minor`、`version:major` 负责，它们通过 npm workspace 批量更新版本，再运行 `scripts/sync-versions.js` 同步版本信息，最后刷新 `package-lock.json`。发布流程则分为 `publish`、`publish:dry` 和 `release:*`：前者会先执行 `prepublishOnly`，后者调用 `scripts/release.mjs` 执行更完整的 release 自动化。

## 关键函数的高层作用

这个文件没有 JavaScript 函数，关键“函数”可理解为根脚本入口。

`check` 是质量总入口，聚合格式、依赖、导入、shrinkwrap、类型和浏览器 smoke 检查。它的作用不是单一测试，而是维护整个 monorepo 的提交健康度。

`build` 是核心包构建入口，串行调用子包 `build`，适合生成发布前产物。

`prepublishOnly` 是发布前门禁，先清理、再构建、再检查，保证发布命令不会跳过基础验证。

`release:patch`、`release:minor`、`release:major` 是正式发布入口，只把版本类型传给 `scripts/release.mjs`。真正的发布细节不在本文件内。

`version:*` 是低层版本变更入口，负责 workspace 版本号、内部同步和 lockfile 刷新。

`check:shrinkwrap` 与 `shrinkwrap:coding-agent` 围绕 `packages/coding-agent` 的 npm shrinkwrap 产物，一个用于校验，一个用于生成。

## 修改风险

修改 `workspaces` 风险较高。新增、删除或移动 workspace 会影响依赖安装、workspace 链接、lockfile 内容、`npm run ... --workspaces` 覆盖范围，也可能影响示例扩展是否能被正确解析。

修改 `check` 风险最高。它是仓库统一质量门禁，删除某一步会降低检查覆盖；调整顺序也可能改变失败暴露方式。例如先运行类型检查还是先运行格式检查，会影响开发者和 CI 看到的首个失败点。

修改 `build` 需要确认包间依赖关系。若构建顺序错误，可能出现某些包读取旧产物或缺失产物的问题。添加新核心包时，也要考虑是否应加入根 `build`，而不仅是加入 `workspaces`。

修改 `version:*`、`release:*`、`publish:*` 风险很高，因为它们会影响版本号、lockfile、发布产物和标签流程。尤其是 `npm install --package-lock-only --ignore-scripts`、`scripts/sync-versions.js`、`scripts/release.mjs` 之间可能存在约定，不能只看命令表面含义修改。

修改 `devDependencies` 和 `overrides` 会改变整个 monorepo 的工具链行为。这里的依赖版本是精确固定的，说明仓库倾向于可复现工具链；升级 `biome`、`typescript`、`tsgo`、`@types/node` 可能带来大量格式、类型或标准库差异。`engines.node` 也不宜随意降低，因为代码和工具链可能依赖 Node `22.19.0` 及以上能力。
