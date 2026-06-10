# 文件：src/entry.ts

## 一句话定位

`src/entry.ts` 是 `openclaw` CLI 的启动入口：它负责把“进程刚被执行”到“真正加载 CLI 主程序 `runCli`”之间的启动准备、快速路径、重启分流和错误兜底串起来。

## 它暴露/定义了什么

这个文件主要定义两类东西。

一类是顶层入口副作用：当该模块确认为主模块时，设置 `process.title`、标准化环境变量和 Windows 参数、启用编译缓存、处理 CLI 重新拉起、解析 `--container`、`--profile/--dev`，最后进入主 CLI。

另一类是可测试的 fast path API：`tryHandleRootHelpFastPath` 和 `tryHandlePrecomputedCommandHelpFastPath`。它们被导出给测试覆盖，用于在不加载完整 CLI 程序的情况下输出部分帮助文本，降低启动开销。

文件内还定义了少量辅助逻辑，例如 `shouldForceReadOnlyAuthStore`、`createGatewayEntryStartupTrace`、`resolvePrecomputedCommandHelpName`、`runMainOrRootHelp`。其中前几个服务于启动阶段判断和观测，真正的业务分流集中在 `runMainOrRootHelp`。

## 谁调用它

运行时入口来自包级 bin 配置：`package.json` 中 `bin.openclaw` 指向 `openclaw.mjs`，根据 `ENTRY_WRAPPER_PAIRS` 和注释可知，包装入口最终会对应到构建后的 `entry.js`。开发模式中也会直接使用 `src/entry.ts`，例如 `src/daemon/program-args.ts` 会构造 dev CLI 路径，相关测试也验证了 `src/entry.ts` 作为 dev 入口。

测试层面，`src/entry.test.ts` 直接导入 `tryHandleRootHelpFastPath`、`tryHandlePrecomputedCommandHelpFastPath`，验证帮助文本 fast path、禁用开关、容器目标绕过、插件配置影响等行为。

## 它调用谁

启动准备依赖 `src/entry.compile-cache.ts` 处理安装根目录、编译缓存和必要的无缓存重启；依赖 `src/entry.respawn.ts` 生成并执行 CLI respawn 计划；依赖 `src/entry.version-fast-path.ts` 处理根级版本输出快速路径。

参数和环境相关逻辑来自 `src/cli/argv.ts`、`src/cli/container-target.ts`、`src/cli/profile.ts`、`src/cli/windows-argv.ts`、`src/infra/env.ts`、`src/infra/is-main.ts`、`src/infra/openclaw-exec-env.ts`、`src/infra/warning-filter.ts`。真正主程序通过动态导入 `src/cli/run-main.ts` 的 `runCli` 执行；错误输出通过动态导入 `src/cli/failure-output.ts` 格式化。

帮助 fast path 会按需动态导入 `src/cli/root-help-live-config.ts`、`src/cli/root-help-metadata.ts`、`src/cli/program/root-help.ts`。

## 核心流程

首先，文件用 `isMainModule` 判断当前模块是否真的是进程主入口。注释说明这是为了避免构建产物中 `dist/index.js` 导入 `entry.js` 时重复执行入口逻辑，进而重复启动 gateway。

确认是主入口后，它解析当前入口文件和安装根，先让 `respawnWithoutOpenClawCompileCacheIfNeeded` 判断是否需要为了编译缓存状态重新拉起。如果父进程已经等待重启，就停止当前路径；否则继续初始化进程标题、执行标记、warning filter、环境归一化和 compile cache。

随后处理几个非常早期的 CLI 语义：`secrets audit` 强制 `OPENCLAW_AUTH_STORE_READONLY=1`，`--no-color` 设置颜色相关环境变量。接着执行 `buildCliRespawnPlan` / `runCliRespawnPlan`，如果需要 respawn，父进程不再继续加载 CLI。

之后标准化 Windows argv，解析 container 参数和 profile 参数。非法参数会直接打印 `[openclaw] ...` 并以 `2` 退出；`--container` 与 `--profile/--dev` 同时出现也会直接失败。profile 生效后会改写环境，并把 stripped argv 回写到 `process.argv`，保证后续 Commander 和手写 argv 判断看到一致输入。

最后先走 `tryHandleRootVersionFastPath`，再进入 `runMainOrRootHelp`。后者依次尝试 root help fast path、命令级预计算 help fast path，均未命中时才动态导入完整 `runCli`。

## 关键函数的高层作用

`tryHandleRootHelpFastPath` 只处理根级 help，例如 `openclaw --help`。它会先避开容器目标，再判断是否为 root help。若插件配置不会改变 help 渲染选项，就优先输出预计算 root help；否则加载 live options 并调用 `outputRootHelp`。异常会被格式化为 “Failed to display help”，并设置失败退出码。

`tryHandlePrecomputedCommandHelpFastPath` 处理少数一级命令的预计算 help，目前限于 `browser`、`secrets`、`nodes`。它尊重 `OPENCLAW_DISABLE_CLI_STARTUP_HELP_FAST_PATH=1`，遇到 container target 会跳过。`nodes` 额外检查插件配置是否可能改变命令元数据；若会改变，则回退到完整 CLI。

`runMainOrRootHelp` 是最终分流点：先尝试轻量帮助输出，再加载 `runCli`。它把完整 CLI import 包在 startup trace 里，失败时用 `formatCliFailureLines` 输出统一错误并 `process.exit(1)`。

`createGatewayEntryStartupTrace` 是观测辅助，仅当 `OPENCLAW_GATEWAY_STARTUP_TRACE` 为真且 argv 包含 `gateway` 时向 stderr 打印 entry 阶段耗时。

## 修改风险

这个文件处在 CLI 最早期启动路径，风险集中在“顺序”和“是否过早加载完整程序”。例如把 `runCli` 改成静态导入，可能破坏 help/version 快速路径的启动性能，也可能提前触发配置、插件或 gateway 相关副作用。

`isMainModule` guard 不能轻易改。当前注释明确指出，构建产物可能把 `entry.js` 当共享依赖导入；如果 guard 失效，会重复调用 `runCli`，造成 gateway 锁或端口冲突。

参数处理顺序也敏感。`--container`、`--profile/--dev`、Windows argv 归一化、颜色环境变量、只读 auth store 都在 Commander 之前发生；调整顺序可能导致 Commander、手写 fast path 和实际运行环境看到不同 argv/env。

帮助 fast path 的修改需要同时考虑插件配置敏感性。`nodes` 的特殊处理说明部分命令 help 可能受 live plugin config 影响，不能一律使用预计算文本。相关行为已有 `src/entry.test.ts` 覆盖，改动后至少应验证这些 fast path 测试，并根据触及范围补充 `src/entry.compile-cache.test.ts`、`src/entry.respawn.test.ts` 或 `src/entry.version-fast-path.test.ts`。
