# 文件：package.json

## 一句话定位

`package.json` 是 OpenClaw 根包的“发布契约 + 工作流总开关”：它定义 npm 包身份、CLI 入口、ESM 导出面、可发布文件集合、依赖边界，以及构建、测试、校验、发布、插件同步、文档和多平台任务的统一脚本入口。

## 它暴露/定义了什么

这个文件首先定义根包 `openclaw` 的基本元信息、版本 `2026.5.26`、`type: module`、Node 版本要求 `>=22.19.0`、包管理器 `pnpm@11.2.2...`，并通过 `bin` 把命令 `openclaw` 指向 `openclaw.mjs`。`main` 指向 `dist/index.js`，`exports` 则暴露根入口和大量 `./plugin-sdk/...` 子路径。根据当前片段可见，`exports` 有 318 个入口，说明它不只是应用包，也承担插件 SDK 的公共 API 分发面。

它还定义 `files` 发布白名单/黑名单。这里既包含 `dist/`、`docs/`、`scripts/npm-runner.mjs`、`patches/`、`skills/` 等必须随包发布的内容，也显式排除 sourcemap、构建戳、测试 QA SDK、若干外部化或非根包拥有的 `dist/extensions/*`。这和根 `AGENTS.md` 中“插件边界、外部官方插件排除核心 dist、SDK 通过 documented barrels 暴露”的架构约束一致。

依赖层面，`dependencies` 放运行时会用到的网关、模型、消息通道、SDK、媒体解析、数据库、CLI、schema、WebSocket 等库；`devDependencies` 放构建、测试、格式化、类型和 UI 开发工具；`optionalDependencies` 仅有 `sqlite-vec`，表示某些能力可选启用。

## 谁调用它

调用者主要有四类。第一类是 Node/npm/pnpm 生态：安装时读取 `engines`、`packageManager`、`bin`、`files`、依赖和 lifecycle scripts。第二类是用户和 CI：通过 `pnpm build`、`pnpm test`、`pnpm check`、`pnpm docs:list`、`pnpm release:check` 等脚本进入仓库工作流。第三类是外部插件或下游 TypeScript 项目：通过 `openclaw/plugin-sdk` 及其子路径导入 SDK 类型和运行时代码。第四类是发布流程：`prepack`、shrinkwrap 生成、release 校验、插件 catalog 同步等脚本都会以这里的字段为契约源。

## 它调用谁

`package.json` 自身不执行代码，但通过 scripts 委派给仓库脚本。核心入口包括 `scripts/build-all.mjs`、`scripts/test-projects.mjs`、`scripts/check.mjs`、`scripts/check-changed.mjs`、`scripts/openclaw-prepack.ts`、`scripts/sync-plugin-sdk-exports.mjs`、`scripts/generate-npm-shrinkwrap.mjs`、`scripts/release-check.ts`、`scripts/docs-list.js`、`scripts/ui.js`。运行入口 `start`、`openclaw`、`dev` 会转到 `openclaw.mjs` 或 `scripts/run-node.mjs`。安装阶段还调用 `scripts/preinstall-package-manager-warning.mjs`、`scripts/prepare-git-hooks.mjs`、`scripts/postinstall-bundled-plugins.mjs`。

依赖治理不只在本文件，`pnpm-workspace.yaml` 进一步定义 workspace 范围 `.`、`ui`、`packages/*`、`extensions/*`，并维护 overrides、patchedDependencies、allowBuilds 和安全相关的 release-age 策略；因此根包依赖调整通常要同时理解 `pnpm-workspace.yaml` 和锁文件/ shrinkwrap。

## 核心流程

安装流程是：pnpm 读取包元数据和 workspace 规则，先运行 `preinstall` 给出包管理器提示，再解析根依赖、workspace 包和 overrides，之后 `postinstall` 处理 bundled plugins，`prepare` 安装或准备 git hooks。

开发/运行流程是：用户执行 `pnpm openclaw`、`pnpm dev` 或 `pnpm start`，脚本进入 `scripts/run-node.mjs` 或 `openclaw.mjs`。`openclaw.mjs` 会检查 Node 版本，并处理源码 checkout 与发布包场景下的 Node compile cache 行为，最后把控制权交给实际入口。

构建发布流程是：`pnpm build` 调用 `scripts/build-all.mjs` 生成 `dist/`；`prepack` 调用 `scripts/openclaw-prepack.ts` 做打包前整理；`files` 决定 npm 包最终带哪些产物；`exports` 决定下游可 import 的公共面；shrinkwrap、release check 和 plugin-sdk export 同步脚本负责验证发布产物与 SDK 契约一致。

校验流程是：`pnpm test` 进入 `scripts/test-projects.mjs`，`pnpm check` 进入 `scripts/check.mjs`；`check:changed`、`test:changed` 面向增量验证；大量 `lint:*`、`tsgo:*`、`deps:*`、`plugin-sdk:*`、`config:*`、`protocol:*` 脚本把架构边界、依赖归属、导出面、配置 schema、协议生成等规则固化为命令。

## 关键函数的高层作用

`package.json` 没有函数，关键“可执行单元”是脚本名。`build` 是总构建入口；`test` 和 `test:changed` 是测试调度入口；`check` 和 `check:changed` 是综合质量门；`plugin-sdk:sync-exports` 与 `plugin-sdk:check-exports` 维护 `exports` 中 SDK 子路径和实际 SDK 产物的一致性；`prepack` 是发布前最后整理点；`deps:shrinkwrap:*` 维护 npm 发布锁定面；`release:check` 聚合生成物和发布规则校验。辅助脚本如 `docs:list`、`ui:build`、`config:*`、`protocol:*` 分别服务文档、UI、配置和协议子系统。

## 修改风险

最高风险是 `exports`、`files`、`bin`、`main`、`type`、`engines` 和依赖区。改 `exports` 可能直接破坏外部插件导入路径或 TypeScript 类型解析；改 `files` 可能让发布包缺失 CLI、SDK、docs、patches、catalog 或运行时脚本，也可能误把内部插件、测试资产、sourcemap 带入包；改 `bin`/`main` 会影响用户命令和包入口；改 `engines` 会改变安装兼容性。

依赖修改同样敏感。根依赖代表核心运行时或内置发布面，插件专属依赖不应随意上移到根包；安全 override、patched dependency、shrinkwrap 相关字段还涉及供应链和发布可复现性。脚本修改的风险在于它们是 CI 和维护者日常操作的稳定入口，尤其 `build`、`test`、`check`、`prepack`、`release:*`、`plugin-sdk:*`。新增公开插件、通道、配置或 SDK 表面时，不能只改 `package.json`，通常还要同步源码 barrel、生成脚本、文档、测试、labeler 或 catalog。根据当前片段推断，本文件是仓库多条自动化链路的汇合点，任何“看似只是元数据”的改动都应跑对应的构建、导出检查、依赖检查和发布包验证。
