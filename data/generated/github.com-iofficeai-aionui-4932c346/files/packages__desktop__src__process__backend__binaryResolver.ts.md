# 文件：packages/desktop/src/process/backend/binaryResolver.ts

## 一句话定位

`binaryResolver.ts` 是桌面端主进程里负责定位后端可执行文件 `aioncore` 的解析器：它把“当前平台应该运行哪个二进制文件、从哪里找、找不到时如何诊断”集中封装起来，供应用启动后端服务前使用。

## 它暴露/定义了什么

这个文件对外主要暴露 `resolveBinaryPath()`，返回 `aioncore` 可执行文件的绝对路径；如果无法找到，则抛出带诊断信息的 `BackendBinaryResolveError`。

它还导出类型 `BackendBinaryResolveDiagnostics`，用于描述解析过程中的关键信息，包括 `resourcesPath`、`runtimeKey`、`binaryName`、检查过的 bundled 路径、目录是否存在、目录条目快照、PATH 查找命令、PATH 查找结果或错误。

文件内部定义了几个辅助概念：固定二进制基础名 `BINARY_NAME = 'aioncore'`；目录枚举和命令输出的长度上限；`getBinaryName()` 用于处理 Windows 的 `.exe` 后缀；`getRuntimeKey()` 用于生成类似 `linux-x64`、`darwin-arm64`、`win32-x64` 的运行时目录 key。

## 谁调用它

从仓库引用关系看，`packages/desktop/src/process/backend/index.ts` 重新导出 `resolveBinaryPath()`，`packages/desktop/src/index.ts` 引入 `resolveBinaryPath` 并在应用主入口附近使用。根据当前片段推断，它应该参与 Electron 主进程启动阶段的后端进程拉起流程：主入口先解析 `aioncore` 路径，再把该路径交给后续启动逻辑。

测试文件 `packages/desktop/src/process/backend/binaryResolver.test.ts` 直接覆盖 `resolveBinaryPath()`，说明它是一个相对独立、可单测的基础设施模块，而不是与具体 UI 或 IPC 逻辑耦合的模块。

## 它调用谁

它依赖 Node.js 标准库：`node:fs` 的 `existsSync()`、`readdirSync()` 检查文件和目录；`node:path` 的 `join()` 拼接跨平台路径；`node:child_process` 的 `execSync()` 执行系统命令。它还读取 `process.platform`、`process.arch` 判断平台和架构，并读取 Electron/打包环境中常见的 `process.resourcesPath` 来寻找随应用分发的资源目录。

系统 PATH 查找通过平台分支实现：Windows 使用 `where aioncore`，其他平台使用 `which aioncore`。

## 核心流程

整体解析顺序非常明确：先找随应用打包的二进制，再退回到系统 PATH。

`resolveBinaryPath()` 首先计算 `runtimeKey` 和 `binaryName`，并初始化一份 `diagnostics`。随后调用 `bundledPath()`，在 `process.resourcesPath/bundled-aioncore/{platform}-{arch}/aioncore[.exe]` 下构造候选路径。如果候选文件存在，直接返回。

如果 bundled 路径不存在或当前环境没有 `resourcesPath`，它继续调用 `resolveFromSystemPATH()`。这个函数执行 `which` 或 `where`，取命令输出的第一条非空路径，并再次用 `existsSync()` 确认文件真实存在；确认成功才返回。

两个来源都失败时，`resolveBinaryPath()` 抛出 `BackendBinaryResolveError`。这个错误不是只给出一句“找不到”，而是携带 `diagnostics`：例如检查过的 bundled 路径、资源目录内容、运行时目录内容、PATH 查找命令和错误。这对生产环境定位“包内缺文件”“平台目录名不匹配”“PATH 环境缺失”等问题很关键。

## 关键函数的高层作用

`resolveBinaryPath()` 是唯一核心入口，负责组织解析策略、维护诊断信息、决定成功返回还是失败抛错。修改调用方通常只应依赖它，不应绕过它直接拼路径。

`bundledPath()` 负责生产环境优先路径。它假设打包布局为 `bundled-aioncore/{platform}-{arch}/aioncore[.exe]`，并在诊断对象中记录资源目录和运行时目录的存在性及部分目录条目。这个函数体现了项目对二进制随包分发结构的约定。

`resolveFromSystemPATH()` 是开发环境或兜底路径。它通过系统命令查找 `aioncore`，设置了 5 秒超时，并截断输出，避免异常信息过长。辅助函数 `getBinaryName()`、`getRuntimeKey()`、`listDirEntries()`、`trimLookupText()` 分别处理平台差异、运行时 key、有限目录快照和诊断文本裁剪。

## 修改风险

最大风险是破坏打包路径约定。`bundledPath()` 中的 `bundled-aioncore/{platform}-{arch}` 必须与构建、复制、发布脚本保持一致；如果改了目录名、runtime key 或文件名，但没有同步打包逻辑，生产环境会直接找不到后端二进制。

第二类风险是跨平台兼容性。`process.platform` 的值是 Node.js 语义，例如 Windows 是 `win32`，macOS 是 `darwin`；`process.arch` 也有固定枚举。手写映射、改后缀规则或改 `where/which` 命令时，容易让某个平台失效。

第三类风险是诊断能力退化。这个文件不仅解析路径，也在失败时提供排障证据。删除 `resourcesDirEntries`、`runtimeDirEntries`、`pathLookupError` 等字段，短期不影响成功路径，但会显著增加生产问题定位成本。

第四类风险是同步阻塞。当前使用 `existsSync()`、`readdirSync()`、`execSync()`，适合启动阶段的简单解析；如果未来在频繁路径、IPC 请求或渲染相关流程中调用，需要注意同步 IO 和 5 秒命令超时带来的卡顿。当前根据引用推断它主要在主进程启动阶段使用，因此这个取舍是可接受的。

最后，异常类型 `BackendBinaryResolveError` 未导出，只导出诊断类型。调用方如果需要区分错误类型，当前只能通过 `name` 或错误结构判断；贸然改为普通 `Error` 会让测试和潜在错误处理逻辑失去结构化诊断。
