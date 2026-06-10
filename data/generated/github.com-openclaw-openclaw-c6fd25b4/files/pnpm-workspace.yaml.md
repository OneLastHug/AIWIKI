# 文件：pnpm-workspace.yaml

## 一句话定位

`pnpm-workspace.yaml` 是 OpenClaw 仓库的 pnpm 工作区与依赖治理入口：它决定哪些目录被纳入 monorepo，哪些依赖版本被强制覆盖，哪些安装脚本允许执行，以及哪些第三方补丁被接受。

## 它暴露/定义了什么

这个文件主要定义五类配置。第一类是 `packages`，把根包 `.`、`ui`、`packages/*`、`extensions/*` 纳入同一个 workspace，因此核心包、UI、共享包和插件包会被 pnpm 统一解析。第二类是发布与安装安全策略，例如 `minimumReleaseAge: 2880`、`minimumReleaseAgeExclude`、`blockExoticSubdeps: true`，用于限制刚发布依赖的引入，并阻断异常子依赖形态。第三类是依赖版本约束，`overrides` 固定 `hono`、`axios`、`protobufjs`、AWS SDK 等关键依赖版本。第四类是构建脚本白名单 `allowBuilds`，显式允许或拒绝 native/postinstall 构建，例如 `@discordjs/opus: false`、`esbuild: true`。第五类是 `packageExtensions` 和 `patchedDependencies`，前者补充第三方包缺失的依赖元数据，后者声明允许的 pnpm patch 文件。

## 谁调用它

直接调用者首先是 pnpm 本身：执行 `pnpm install`、`pnpm build`、`pnpm test` 等仓库命令时，pnpm 会读取它来发现 workspace 包、解析覆盖版本、应用 patch、决定构建脚本策略。仓库脚本也把它当作审计对象读取：`scripts/check-dependency-pins.mjs` 检查 `overrides` 和 `packageExtensions.*.dependencies` 是否精确 pin；`scripts/check-package-patches.mjs` 检查 `patchedDependencies` 是否在允许清单内；`test/package-manager-config.test.ts` 验证构建策略、override 与 `npm-shrinkwrap.json` 的一致性。发布打包层也会关注它，因为根 `package.json` 的 `files` 把 `pnpm-workspace.yaml` 和 `patches/` 纳入 npm 包，保证下游安装能解析 patch。

## 它调用谁

它本身是声明式 YAML，不主动调用代码。根据当前片段推断，它的“下游”主要是 pnpm 的 workspace/install 解析器、pnpm lockfile 生成逻辑、仓库内依赖审计脚本，以及 npm shrinkwrap 生成/校验流程。`patchedDependencies` 会间接引用 `patches/@agentclientprotocol__claude-agent-acp@0.37.0.patch`；`packageExtensions` 会影响 pnpm 对 `baileys`、`@earendil-works/pi-coding-agent` 的依赖图补全。

## 核心流程

安装或校验开始时，pnpm 先读取 `packages`，确定根包、UI、共享包、所有 `extensions/*` 都在同一依赖图中。随后它按 `overrides` 重写依赖版本，避免各子包漂移到不一致或不安全版本。解析依赖时，`minimumReleaseAge` 会延迟接受新发布包，排除清单中的特定包或版本则允许绕过等待期。进入构建阶段时，`allowBuilds` 控制哪些依赖可以执行安装构建脚本，`blockExoticSubdeps` 用于收紧不常规子依赖。最后，pnpm 应用 `patchedDependencies` 指向的 patch，并把结果反映到 `pnpm-lock.yaml`。测试和脚本再反向读取该文件，确认这些策略没有被绕过。

## 关键函数的高层作用

本文件没有函数。与它关系最密切的函数在消费脚本中：`collectWorkspaceViolations` 读取 `pnpm-workspace.yaml`，检查 workspace 级 `overrides` 和 `packageExtensions` 依赖是否精确固定版本；`collectWorkspacePatchViolations` 读取 `patchedDependencies`，确认新增 patch 没有绕过允许列表；`collectPnpmLockPackages` 从 `pnpm-lock.yaml` 汇总锁定包版本，用来证明 shrinkwrap 中的包仍来自 pnpm 依赖图。测试里的 `readJson`、YAML `parse` 只是辅助读取，不承载业务决策。

## 修改风险

修改 `packages` 风险最高，会改变 pnpm 看到的工作区边界，可能导致插件包不再参与安装、测试、构建或发布校验。修改 `overrides` 会影响全仓依赖版本，可能破坏运行时兼容性、修复回退或安全修复；还需要同步检查 `pnpm-lock.yaml`、`npm-shrinkwrap.json` 和相关插件 shrinkwrap。修改 `allowBuilds` 或 `blockExoticSubdeps` 属于安装安全面变更，可能让 native 包构建失败，也可能放开不应执行的 install script。修改 `minimumReleaseAgeExclude` 会影响供应链风险控制，新增例外应能说明为什么必须绕过等待期。修改 `patchedDependencies` 或新增 `patches/*.patch` 会触发专门审计，因为 patch 是发布包行为的一部分；仓库已有脚本只允许少数明确列出的补丁。总体上，这个文件不是普通配置清单，而是 monorepo 包发现、安装安全、依赖固定和发布可复现性的共同控制面。
