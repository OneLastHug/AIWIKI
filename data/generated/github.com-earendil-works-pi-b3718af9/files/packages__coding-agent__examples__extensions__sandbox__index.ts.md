# 文件：packages/coding-agent/examples/extensions/sandbox/index.ts

## 一句话定位

`packages/coding-agent/examples/extensions/sandbox/index.ts` 是一个示例扩展，用 `@anthropic-ai/sandbox-runtime` 替换或拦截 Pi 内置的 `bash` 执行路径，把模型触发的 shell 命令和用户手动 bash 命令放进操作系统级沙箱中运行。

## 它暴露/定义了什么

这个文件默认导出一个 extension factory：`export default function (pi: ExtensionAPI)`。扩展被加载后会向 Pi 注册一个 `no-sandbox` 布尔 flag、一个覆盖内置 `bash` 行为的工具、若干 extension event handler，并根据文件头注释还提供 `/sandbox` 命令用于查看当前沙箱配置。

文件内部还定义了：

- `SandboxConfig`：在 `SandboxRuntimeConfig` 基础上增加 `enabled` 开关。
- `DEFAULT_CONFIG`：默认网络白名单、文件系统读写限制和敏感文件写入黑名单。
- `loadConfig(cwd)`：读取并合并全局配置与项目配置。
- `deepMerge(base, overrides)`：按网络、文件系统、扩展字段做浅层合并。
- `createSandboxedBashOps()`：构造一组替换 `bash` 底层执行逻辑的 `BashOperations`。

## 谁调用它

直接调用者不是业务代码，而是 Pi 的 extension 加载系统。根据仓库中 `packages/coding-agent/examples/sdk/06-extensions.ts` 和 `packages/coding-agent/src/main.ts` 的上下文，扩展可以来自命令行 `-e/--extension`、标准 extension 目录或 SDK 配置；加载后 runtime 会执行默认导出的函数，并把 `ExtensionAPI` 传入。

运行期还有三类间接调用：

- 工具系统在模型调用 `bash` 工具时调用这里注册的 `execute`。
- 扩展事件系统在 `session_start`、`user_bash` 等事件发生时调用对应 handler。
- 交互式命令系统在用户输入 `/sandbox` 时调用该扩展注册的命令 handler。

## 它调用谁

它主要调用四组外部能力：

- Node 标准库：`spawn` 启动子进程，`existsSync`、`readFileSync` 读取配置，`join` 拼路径。
- `@anthropic-ai/sandbox-runtime`：`SandboxManager` 负责把原始命令包装成沙箱命令，并在会话开始时根据配置初始化或配置沙箱运行时。
- `@earendil-works/pi-coding-agent`：`createBashTool` 创建 Pi 内置风格的 bash 工具，`getAgentDir` 找全局 agent 配置目录，`ExtensionAPI` 提供注册 flag、tool、event、command 的入口。
- Pi UI 上下文：通过 `ctx.ui.notify` 把启用、禁用、不支持平台或初始化失败等状态反馈给用户。

## 核心流程

扩展加载时，先注册 `--no-sandbox`。随后以 `process.cwd()` 创建一个原始 `localBash`，再用 `pi.registerTool` 注册同名或等价的 `bash` 工具替代实现。这个工具的 `execute` 会检查 `sandboxEnabled` 和 `sandboxInitialized`：如果沙箱未启用，直接回退到原始 `localBash.execute`；如果沙箱已启用，则用 `createBashTool(localCwd, { operations: createSandboxedBashOps() })` 创建沙箱版 bash 工具并执行。

会话启动时，`session_start` handler 读取 `--no-sandbox`，再读取配置文件。配置来源是全局 `~/.pi/agent/extensions/sandbox.json` 和项目内 `<cwd>/.pi/sandbox.json`，且项目配置优先。之后它检查 `enabled`、当前平台是否为 `darwin` 或 `linux`，再把合并后的网络和文件系统规则交给 `SandboxManager`。根据当前片段推断，初始化成功后会把 `sandboxEnabled` 和 `sandboxInitialized` 置为 true，并通知用户；失败则保持关闭并提示原因，依据是前半段已经声明了这两个状态位并在 `execute`、`user_bash` 中作为总开关。

用户手动 bash 路径通过 `pi.on("user_bash")` 处理：沙箱启用后返回 `{ operations: createSandboxedBashOps() }`，让用户发起的 bash 命令也使用相同执行后端，而不只保护模型工具调用。

## 关键函数的高层作用

`loadConfig(cwd)` 是配置入口。它按固定位置读取全局和项目 JSON，解析失败只打印 warning，不中断扩展加载。最后用 `deepMerge(DEFAULT_CONFIG, globalConfig)` 再叠加 `projectConfig`，形成最终运行配置。

`deepMerge(base, overrides)` 控制配置覆盖语义。它不是递归深合并所有字段，而是针对 `enabled`、`network`、`filesystem` 做一层对象合并，并额外透传 `ignoreViolations`、`enableWeakerNestedSandbox` 这类 `sandbox-runtime` 扩展字段。修改这里会直接改变项目配置覆盖默认安全策略的方式。

`createSandboxedBashOps()` 是执行隔离的核心。它返回 `BashOperations.exec`，先确认 `cwd` 存在，再调用 `SandboxManager.wrapWithSandbox(command)` 得到包装后的命令，然后用 `spawn("bash", ["-c", wrappedCommand])` 执行。它把 stdout 和 stderr 都转发给 `onData`，支持超时后杀进程组，支持 `AbortSignal` 取消，并按退出、超时、取消分别 resolve 或 reject。

默认导出的 extension factory 是集成层。它把配置初始化、工具替换、用户 bash 拦截和 UI 通知串起来，是这个示例真正接入 Pi runtime 的地方。

## 修改风险

最大风险是安全边界被意外放宽。`DEFAULT_CONFIG`、`deepMerge`、`loadConfig` 的任何改动都会影响默认可联网域名、敏感路径读写限制，以及项目配置覆盖全局配置的优先级。尤其是 `allowWrite`、`denyRead`、`denyWrite` 的合并方式如果改成拼接或完全覆盖，都会改变用户对安全策略的预期。

第二类风险是命令执行语义。`createSandboxedBashOps()` 需要保持与 Pi 内置 `bash` 工具兼容：输出流、退出码、超时、取消、工作目录和进程组清理都影响上层工具 UI 和 agent 行为。比如不再使用 `detached: true` 或不杀负 PID，可能导致子进程残留；改变错误文本如 `timeout:${timeout}` 可能破坏调用方对超时的识别。

第三类风险是扩展加载时机。沙箱状态在 `session_start` 中初始化，而 `bash` 工具在扩展加载时就已注册，因此 `execute` 必须保留未初始化时回退原始 bash 的逻辑。删除回退会让初始化失败变成工具不可用；无条件启用则可能在不支持的平台或用户显式 `--no-sandbox` 时违反预期。

最后，这个文件是示例但覆盖内置 `bash`，影响面比普通 demo 大。改动时应同时考虑模型工具调用和 `user_bash` 两条路径，避免只保护其中一条造成安全策略不一致。
