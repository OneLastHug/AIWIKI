# 文件：openclaw.mjs

## 一句话定位

`openclaw.mjs` 是 OpenClaw 命令行的最外层 Node 启动器：它负责在真正进入 `dist/entry.js` 之前完成 Node 版本门禁、编译缓存策略、帮助文本快速输出、警告过滤安装，以及构建产物缺失时的友好报错。

## 它暴露/定义了什么

这个文件本身不导出业务 API，而是通过顶层执行逻辑承担 CLI wrapper 职责。`package.json` 中 `bin.openclaw` 指向 `openclaw.mjs`，`scripts.start` 也是 `node openclaw.mjs`，说明它是 npm 安装后 `openclaw` 命令的主入口。

文件内部定义了几类逻辑：Node 版本检查常量和函数、源码树/打包安装识别、Node compile cache 路径计算和重启监督、直接模块缺失判断、预计算 help 文本快速路径、用户配置路径解析、以及最终动态导入运行时入口的兜底流程。

## 谁调用它

主要调用方是用户或系统服务执行的 `openclaw` 命令。npm 安装后，包管理器会把 `openclaw` 可执行命令映射到 `openclaw.mjs`。开发场景中，`pnpm start`、文档里的 `node openclaw.mjs ...`、测试夹具和更新/doctor 相关逻辑也会直接使用它。

根据当前片段推断，daemon、gateway、node host、update runner 等并不把它当作库调用，而是把它当作进程入口或命令路径引用；依据是仓库中大量测试和脚本以 `node openclaw.mjs`、`/usr/local/bin/openclaw`、`package.json bin` 的形式覆盖行为。

## 它调用谁

它首先调用 Node 标准库：`child_process.spawn` 用于重启自身，`fs`/`fs.promises` 用于探测 `.git`、`src/entry.ts`、`package.json`、`dist/cli-startup-metadata.json`，`module` 用于读取和启用 Node compile cache，`os`、`path`、`url` 用于跨平台路径处理。

真正的业务入口是动态导入 `./dist/entry.js`，其次兼容 `./dist/entry.mjs`。在进入业务入口前，它可能导入 `./dist/warning-filter.js` 或 `./dist/warning-filter.mjs` 安装 warning filter，也可能导入 `./dist/cli/program/root-help.js` 或 `.mjs` 输出 root help。预计算帮助文本来自 `./dist/cli-startup-metadata.json`。

## 核心流程

启动后第一步是 `ensureSupportedNodeVersion()`，要求 Node 至少为 `22.19`。不满足时，它直接向 stderr 输出升级建议并 `process.exit(1)`，避免后续 ESM、compile cache 或运行时代码在低版本 Node 上产生更隐晦错误。

第二步判断当前是源码 checkout 还是打包安装。判断依据是当前入口旁边是否存在 `.git` 或 `src/entry.ts`。源码树里，如果已经启用了 Node compile cache 或用户显式请求了 `NODE_COMPILE_CACHE`，它会设置 `NODE_DISABLE_COMPILE_CACHE=1` 并重启自身，避免源码开发环境被 compile cache 干扰。打包安装里，如果当前 compile cache 目录不是 OpenClaw 按版本和安装标记计算出的目录，则用期望目录重启；若无需重启且环境允许，则调用 `module.enableCompileCache()`。

第三步是 help fast path。对于裸 `openclaw --help`，如果没有插件目录覆盖、禁用 bundled plugins、或配置中出现 `plugins`/`$include` 等会影响帮助文本的动态因素，它会优先读取 `dist/cli-startup-metadata.json` 里的 `rootHelpText`。对于 `browser --help`、`secrets --help`、`nodes --help`，也会尝试输出预计算帮助文本。这样可以避免为了显示简单帮助而加载完整 CLI 运行时。

第四步才进入完整运行时：安装 warning filter，然后依次尝试导入 `dist/entry.js`、`dist/entry.mjs`。如果两个入口都不存在，它会构造“missing dist/entry.(m)js”的错误；若当前看起来像未构建源码树，还会提示先执行 `pnpm install && pnpm build` 或安装已构建包。

## 关键函数的高层作用

`ensureSupportedNodeVersion()` 是硬门禁，保证 CLI 只在受支持 Node 版本上继续运行。

`isSourceCheckoutLauncher()` 区分开发源码树和发布包，后续 compile cache 策略完全依赖这个判断。

`resolvePackagedCompileCacheDirectory()` 生成打包安装专用 compile cache 目录，路径包含 OpenClaw 版本和 `package.json` 的 mtime/size 标记，用来隔离不同版本或不同安装内容的缓存。

`runRespawnedChild()` 是重启监督器：继承 stdio，转发终止信号，并设置两个 1 秒 grace timer，避免子进程忽略信号时 wrapper 永久挂住。

`respawnWithoutCompileCacheIfNeeded()` 和 `respawnWithPackagedCompileCacheIfNeeded()` 是两条互斥策略：源码树倾向禁用 compile cache，打包安装倾向使用稳定、版本化的 OpenClaw cache 目录。

`isDirectModuleNotFoundError()` 用于区分“入口文件本身缺失”和“入口内部依赖缺失”。只有前者会被吞掉并尝试下一个候选入口；后者会重新抛出，避免掩盖真实打包或依赖错误。

`tryOutputBareRootHelp()`、`tryOutputPrecomputedCommandHelp()` 是启动性能优化：能用预计算文本回答 help 时，不加载完整 `dist/entry.js`。

`shouldDeferRootHelpToRuntimeEntry()` 是安全阀：当环境或配置可能影响插件/命令集合时，放弃快速路径，交给完整运行时生成准确 help。

## 修改风险

最高风险是入口导入和错误吞吐逻辑。`tryImport()`、`isDirectModuleNotFoundError()` 如果误判，会把真实的依赖缺失伪装成“构建产物缺失”，或者反过来让合法 fallback 失效，直接影响所有 CLI 启动。

第二类风险是 compile cache 和 respawn。这里涉及 Node 版本差异、环境变量继承、信号转发、Windows 与 POSIX 信号差异。任何改动都可能造成重复启动、信号无法退出、源码树缓存污染，或打包安装性能回退。文件注释还说明它与 `src/entry.compile-cache.ts` 的监督行为需要保持同步，这意味着修改一边时必须检查另一边。

第三类风险是 help fast path。它为了性能绕过完整运行时，所以必须非常保守。只要插件、配置 include、bundled plugin 开关会改变命令集合或帮助内容，就应 defer 到 runtime。否则用户看到的 `--help` 可能与实际可用命令不一致。

第四类风险是路径和环境解析。`OPENCLAW_HOME`、`OPENCLAW_CONFIG_PATH`、`OPENCLAW_STATE_DIR`、`HOME`、`USERPROFILE` 都会影响是否启用快速 help。这里的兼容性覆盖到 Windows、类 Unix、显式 home、`~` 展开和旧 `clawdbot` 配置路径，修改时容易造成升级场景或旧配置用户行为变化。

最后，`MIN_NODE_MAJOR`/`MIN_NODE_MINOR` 必须与 `package.json` 的 engines 约束保持一致；测试中已有专门覆盖。改 Node 门槛不能只改启动器，否则发布包元数据、安装提示和真实运行门禁会不一致。
