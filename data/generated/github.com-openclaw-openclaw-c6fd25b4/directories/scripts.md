# 目录：scripts

## 它负责什么

`scripts` 是 OpenClaw 仓库的“工程操作层”：它不承载核心产品运行时业务逻辑，而是把构建、检查、测试、发布、安装、Docker/E2E、文档生成、插件边界校验、CI 辅助、平台打包等重复性操作沉淀成可复用入口。根目录 `package.json` 中大量 npm scripts 都直接落到这里，例如 `pnpm build` 调用 `scripts/build-all.mjs`，`pnpm check` 调用 `scripts/check.mjs`，`pnpm check:changed` 调用 `scripts/check-changed.mjs`，`pnpm changed:lanes` 调用 `scripts/changed-lanes.mjs`，测试包装入口则是 `scripts/run-vitest.mjs`。

这个目录的定位可以概括为三层：第一层是面向开发者和 CI 的命令入口，如 `run-node.mjs`、`run-oxlint.mjs`、`run-tsgo.mjs`、`run-vitest.mjs`、`crabbox-wrapper.mjs`；第二层是工程规则检查与生成器，如 `check-*.mjs`、`generate-*.ts`、`sync-*.ts`、`write-*.ts`；第三层是特定环境或发布路径的流程脚本，如 `docker-e2e.mjs`、`test-docker-all.mjs`、`release-check.ts`、`openclaw-npm-publish.sh`、`install.sh`、`install.ps1`。根据 `scripts/AGENTS.md`，这里的核心原则是优先使用仓库已有 wrapper，不直接绕过 curated seam；重型本地检查还要尊重 `scripts/lib/local-heavy-check-runtime.mjs` 的锁和调度逻辑。

## 直接子目录地图

`scripts/lib` 是共享工具库，也是理解整个目录的中心。它放置 Docker E2E 组装、插件构建路径、边界扫描、测试计划、release 计划、Vitest 调度、错误格式化、生成产物工具等共用模块。很多根层脚本只是入口，实际复杂逻辑会下沉到这里。

`scripts/e2e` 是 Docker、安装、插件、网关、Telegram、OpenAI、升级、release 用户旅程等端到端场景集合。它包含 `Dockerfile`、若干 `*-docker.sh`、客户端驱动脚本和测试种子文件，通常配合 `scripts/docker-e2e.mjs`、`scripts/test-docker-all.mjs` 与 GitHub Actions 使用。

`scripts/docker`、`scripts/podman`、`scripts/k8s` 是容器和部署辅助区。`scripts/docker` 下还有安装脚本 smoke、sandbox、cleanup 等子目录；`scripts/podman` 放容器模板和 setup；`scripts/k8s` 放 kind 创建、部署脚本和 manifests。

`scripts/dev` 是本地开发和手动 smoke 工具区，覆盖 gateway、Discord ACP、iOS、realtime talk、Telegram 设备配对、TUI PTY 等开发态验证。它更像工程师调试入口，不是稳定产品 API。

`scripts/docs-i18n` 是一个 Go 工具模块，包含 `go.mod`、`main.go`、翻译、分段、占位符、链接本地化、术语表和测试文件。它服务文档国际化流程，和根层 `check-docs-i18n-glossary.mjs`、文档检查脚本属于同一类文档工具链。

`scripts/github`、`scripts/pr-lib`、`scripts/pre-commit` 处理 GitHub/PR/本地提交前流程。`scripts/pr-lib` 是 shell helper 集合，支撑 `scripts/pr`、`scripts/pr-review`、`scripts/pr-prepare`、`scripts/pr-merge` 等根层命令。`scripts/github` 放自动响应、真实行为证明策略、ref 解析、跨 OS release check wrapper。

`scripts/mantis` 放 Telegram 或 PR evidence 的生成与发布辅助；`scripts/perf` 放性能调查材料；`scripts/repro`、`scripts/secrets`、`scripts/systemd`、`scripts/test-planner`、`scripts/clawdock` 则分别偏向复现、安全/凭据、systemd、测试规划和本地封装环境。根据当前片段推断，这些目录多是专题工具集合，规模小于 `lib` 与 `e2e`。

## 关键入口

最先看的入口是命令 wrapper：`scripts/run-node.mjs` 对应 `pnpm openclaw`、`pnpm dev` 等本地运行；`scripts/run-vitest.mjs` 是测试包装入口；`scripts/run-oxlint.mjs` 和 `scripts/run-oxlint-shards.mjs` 负责 lint；`scripts/run-tsgo.mjs` 负责类型检查通道；`scripts/run-with-env.mjs` 用来组合环境变量和子命令。这些 wrapper 体现了仓库不鼓励直接调用底层工具的设计。

第二组是检查总线：`scripts/check.mjs` 是全量检查入口，`scripts/check-changed.mjs` 是变更感知检查入口，`scripts/changed-lanes.mjs` 负责把变更映射到检查 lane。它们和 `scripts/lib/local-heavy-check-runtime.mjs`、`scripts/lib/*test-plan*`、`scripts/lib/vitest-local-scheduling.mjs` 共同决定“改了什么、该跑什么、如何避免本地重型任务互相踩踏”。

第三组是构建与生成：`scripts/build-all.mjs`、`scripts/tsdown-build.mjs`、`scripts/runtime-postbuild.mjs`、`scripts/build-stamp.mjs`、`scripts/bundled-plugin-assets.mjs`、`scripts/copy-bundled-plugin-metadata.mjs`、`scripts/write-build-info.ts` 等构成 build 主线。插件 SDK、配置 schema、文档 baseline、prompt snapshot、协议生成则由 `generate-*`、`sync-*`、`write-*` 脚本承担。

第四组是发布、安装与远端验证：`scripts/install.sh`、`scripts/install-cli.sh`、`scripts/install.ps1` 是用户安装面；`scripts/release-check.ts`、`scripts/release-candidate-checklist.mjs`、`scripts/openclaw-npm-prepublish-verify.ts`、`scripts/openclaw-npm-publish.sh` 是 release/npm 发布面；`scripts/crabbox-wrapper.mjs` 是远端验证 wrapper。

## 主流程位置

日常开发主流程通常从 `package.json` 进入 `scripts/run-node.mjs`、`scripts/check-changed.mjs`、`scripts/run-vitest.mjs`。源码变更后，`changed-lanes.mjs` 判断影响面，`check-changed.mjs` 调度 lint、类型、测试或脚本检查，具体复用 `scripts/lib` 下的计划与调度工具。

构建主流程从 `scripts/build-all.mjs` 开始，随后进入 `tsdown-build`、runtime postbuild、build stamp、插件资产构建和复制、hook metadata、HTML template、build info、CLI startup metadata 等阶段。根据 `package.json` 的 build 命令可见，构建不是单一步骤，而是一串显式生成与校验动作。

Docker/E2E 主流程围绕 `scripts/test-docker-all.mjs`、`scripts/docker-e2e.mjs`、`scripts/e2e/*` 和 `scripts/lib/docker-*` 展开。`scripts/e2e` 提供场景，根层 orchestrator 负责计划、分片、汇总和 CI 输出。

发布主流程分散在 `release-*`、`openclaw-npm-*`、`plugin-npm-*`、`plugin-clawhub-*`、`generate-npm-shrinkwrap.mjs` 等脚本中。这里同时覆盖主包、插件包、ClawHub、shrinkwrap、依赖证据、beta smoke 和候选版本检查。

## 推荐阅读顺序

1. 先读 `scripts/AGENTS.md`，理解 wrapper、heavy-check lock、生成产物对齐这些本目录规则。
2. 再读 `package.json` 的 `scripts` 字段，只看命令如何映射到 `scripts/*`，不要先陷入单个脚本细节。
3. 接着读四个总入口：`scripts/run-node.mjs`、`scripts/check.mjs`、`scripts/check-changed.mjs`、`scripts/build-all.mjs`。
4. 然后进入 `scripts/lib`，重点看 `local-heavy-check-runtime.mjs`、`vitest-local-scheduling.mjs`、`docker-e2e-plan.mjs`、`extension-*`、`plugin-*`、`generated-output-utils.mjs` 这类被多处复用的模块。
5. 最后按任务域选择专题目录：做 E2E 看 `scripts/e2e`，做文档国际化看 `scripts/docs-i18n`，做 PR/CI 看 `scripts/github` 和 `scripts/pr-lib`，做容器部署看 `scripts/docker`、`scripts/podman`、`scripts/k8s`。

## 常见误区

不要把 `scripts` 理解成零散杂物目录。它虽然文件多，但很多脚本是仓库政策的可执行表达，例如插件边界、SDK 导出、动态 import、配置 schema、依赖 ownership、Docker E2E、release metadata 都通过这里固化。

不要绕过 wrapper 直接跑底层工具。`scripts/AGENTS.md` 明确要求测试优先用 `scripts/run-vitest.mjs` 或根层 `pnpm test`，lint/typecheck 优先用 `scripts/run-oxlint.mjs`、`scripts/run-tsgo.mjs`，变更检查优先用 `scripts/check-changed.mjs` 和 `scripts/changed-lanes.mjs`。直接调用 `vitest`、`oxlint` 或自写路径规则，容易跳过仓库的隔离、调度和边界约束。

不要以为 `check-*` 都是同一类简单 grep。这里的检查有些是架构边界，有些是生成产物一致性，有些是 CI/workflow 策略，有些是安全或发布门禁。阅读时应先判断它服务哪个主流程，再看它依赖 `scripts/lib` 的哪部分。

不要把 `scripts/e2e` 当成普通单元测试目录。它包含 Docker、真实安装、升级、插件生命周期、live provider、Telegram 用户证明等重场景，通常需要特定环境、凭据或 CI/Crabbox/Testbox 配合。对应的轻量单元覆盖主要在 `test/scripts`。

不要随意改生成输出或 baseline。目录规则要求生成器、package script 和 check 命令保持一致；如果看到 `generate-* --write` 与 `--check` 成对出现，应先理解源头、输出文件和验证命令，而不是只改结果文件。
