# 子系统：packages/agent/src/harness/env

## 解决什么问题

`packages/agent/src/harness/env` 是 agent harness 的“执行环境适配层”。它把模型运行过程中需要的本地能力统一封装成 `ExecutionEnv` 接口的实现，主要包括路径解析、文件读写、目录枚举、临时文件创建、shell 命令执行、取消与超时控制、错误归一化等。

从当前代码看，这个目录只有 `nodejs.ts` 一个实现文件，核心类是 `NodeExecutionEnv`。它不是业务编排层，也不是工具定义层，而是把 Node.js 的 `fs`、`child_process`、`path`、`os` 等能力转换成 harness 内部可控、可测试、类型化的环境 API。上层 harness 不直接依赖 Node 原生错误和进程细节，而是通过 `Result<T, E>`、`FileError`、`ExecutionError` 这组类型处理预期失败。

这个目录解决的关键问题是：agent 需要读写工作区文件、执行命令、保存大输出、响应 abort，但这些能力必须被统一抽象，否则上层逻辑会散落大量平台判断、异常捕获和路径处理。

## 相关目录和文件

`packages/agent/src/harness/env/nodejs.ts` 是当前子系统的主体，实现 `NodeExecutionEnv`。它负责本地 Node 环境下的所有文件系统和命令执行操作。

`packages/agent/src/harness/types.ts` 定义该层依赖的抽象类型，包括 `ExecutionEnv`、`Result`、`FileError`、`ExecutionError`、`FileInfo`、`FileKind`、`ok`、`err`、`toError` 等。`env` 目录本身不定义协议，而是实现协议。

`packages/agent/src/harness/agent-harness.ts` 是上层编排核心，负责会话、模型调用、队列、事件、工具和资源管理。根据当前片段推断，`ExecutionEnv` 会作为 harness 运行时资源被工具执行、shell 捕获、文件访问等逻辑使用。

`packages/agent/src/harness/utils/shell-output.ts` 是重要邻近模块。测试里 `executeShellWithCapture(env, ...)` 通过 `ExecutionEnv.exec` 执行 shell，并在输出过大时使用 `env.writeFile`、`env.readTextFile` 等能力保存完整输出。

`packages/agent/test/harness/nodejs-env.test.ts` 是该子系统的行为规格，覆盖文件读写、目录操作、符号链接、错误映射、取消、命令超时、流式 stdout/stderr、callback 失败和大输出捕获。

## 核心对象

`NodeExecutionEnv` 是核心对象，构造参数包含 `cwd`、可选 `shellPath`、可选 `shellEnv`。`cwd` 是相对路径解析基准；`shellPath` 用于指定自定义 shell；`shellEnv` 用于注入基础环境变量。

路径相关方法包括 `absolutePath`、`joinPath`、`canonicalPath`。其中相对路径通过 `cwd` 解析，绝对路径保持原样；`canonicalPath` 使用真实路径解析，适合处理 symlink 的最终目标。

文件相关方法包括 `readTextFile`、`readTextLines`、`readBinaryFile`、`writeFile`、`appendFile`、`fileInfo`、`listDir`、`exists`、`createDir`、`remove`。`writeFile` 和 `appendFile` 会自动创建父目录；`fileInfo` 和 `listDir` 使用 `lstat`，因此符号链接会被识别为 `symlink`，不会被当作目标文件或目录跟随。

执行相关方法是 `exec`。它通过 shell 执行命令，收集完整 `stdout`、`stderr`，同时支持 `onStdout`、`onStderr` 分块回调。非零退出码不是异常，而是成功的执行结果 `{ stdout, stderr, exitCode }`；只有 spawn 失败、shell 不可用、超时、abort、回调抛错等才返回 `ExecutionError`。

错误对象以 `FileError` 和 `ExecutionError` 为边界。`toFileError` 会把 Node 的 `ENOENT`、`EACCES`、`EPERM`、`ENOTDIR`、`EISDIR`、`EINVAL`、`ABORT_ERR` 映射为稳定错误码，例如 `not_found`、`permission_denied`、`not_directory`、`is_directory`、`invalid`、`aborted`。

## 运行流程

文件操作的基本流程是：先用 `resolvePath(cwd, path)` 得到真实操作路径，再检查 `AbortSignal` 是否已取消，然后调用 Node 原生 API，最后把成功值包装为 `ok(...)`，把异常包装为 `err(new FileError(...))`。`readTextLines` 使用 `createReadStream` 和 `readline.createInterface` 逐行读取，支持 `maxLines` 提前停止，并在循环中反复检查 abort。

目录枚举的流程是：`readdir(..., { withFileTypes: true })` 获取条目，再对每个 entry 调用 `lstat` 生成 `FileInfo`。`FileInfo` 包含 `name`、`path`、`kind`、`size`、`mtimeMs`。不支持的文件类型会返回 `invalid`。

命令执行的流程是：`exec` 先选择 shell。自定义 `shellPath` 存在时使用它；Windows 下优先找 Git Bash 常见路径，再找 PATH 中的 `bash.exe`；非 Windows 下优先 `/bin/bash`，再找 PATH 中的 `bash`，最后退回 `sh`。随后用 `spawn(shell, ["-c", command])` 启动子进程，合并 `process.env`、构造时的 `shellEnv` 和本次调用的 `env`。如果设置了 timeout，则到期后杀掉进程树；如果 abort，则同样杀进程树。进程关闭后按优先级返回 callback 错误、timeout、aborted 或正常结果。

## 上下游依赖

上游依赖主要是 Node.js 标准库：`node:child_process` 负责启动 shell 和杀进程，`node:fs/promises` 与 `node:fs` 负责文件系统，`node:path` 负责路径拼接和解析，`node:os` 提供临时目录，`node:crypto` 提供临时文件名中的 `randomUUID`，`node:readline` 支持逐行读取。

类型上游是 `packages/agent/src/harness/types.ts`。`NodeExecutionEnv` 不向外抛出原生异常作为常规控制流，而是遵循 `ExecutionEnv` 的 `Result` 协议，这让上层能够统一处理预期失败。

下游使用者包括 harness 工具执行链、shell 输出捕获工具、会话或资源逻辑中需要读写文件的部分。根据当前片段推断，`AgentHarness` 通过 `ExecutionEnv` 把具体运行环境注入给工具和内部辅助流程，从而让同一套 harness 逻辑可以在测试、内存环境或未来其他平台环境中复用。

测试下游是 `packages/agent/test/harness/nodejs-env.test.ts`。它不仅验证 API 功能，也固定了若干语义：非零退出码不是错误、symlink 不被 `fileInfo` 跟随、`exists` 对缺失路径返回 `false`、stream callback 抛错会终止命令并返回 `callback_error`。

## 修改时最容易踩的坑

第一，不能把命令非零退出码改成 `ExecutionError`。测试明确要求 `exit 7` 返回成功结果并携带 `exitCode: 7`，因为 shell 命令失败属于命令语义，不等同于环境无法执行。

第二，路径解析要保持 `cwd` 语义。所有相对路径都应基于 `NodeExecutionEnv.cwd`，否则工具在工作区中的行为会漂移。绝对路径则不应再拼接 `cwd`。

第三，`lstat` 和 `realpath` 的职责不同。`fileInfo`、`listDir` 当前使用 `lstat`，目的是把 symlink 本身报告为 `symlink`；只有 `canonicalPath` 才解析到真实目标。把 `lstat` 改成 `stat` 会破坏符号链接行为。

第四，abort 和 timeout 都要清理子进程树。非 Windows 平台通过 detached process group 和 `process.kill(-pid)`；Windows 通过 `taskkill /F /T /PID`。如果只杀父进程，shell 启动的子命令可能残留。

第五，stream 回调的异常必须被转成 `callback_error`。`onStdout`、`onStderr` 是上层消费实时输出的入口，回调抛错时需要终止进程并返回可识别错误，而不是让异常逃逸到事件循环。

第六，文件错误码要稳定。上层和测试依赖 `not_found`、`permission_denied`、`not_directory` 等抽象码，不应泄漏平台相关的 `ENOENT`、`EPERM` 作为主要判断依据。

## 推荐阅读顺序

1. 先读 `packages/agent/src/harness/types.ts` 中的 `Result`、`FileError`、`ExecutionError`、`ExecutionEnv`，理解这个目录要实现的契约。
2. 再读 `packages/agent/src/harness/env/nodejs.ts` 的辅助函数：`resolvePath`、`toFileError`、`getShellConfig`、`killProcessTree`，这些决定了跨平台行为和错误边界。
3. 接着读 `NodeExecutionEnv` 的文件 API，再读 `exec`。文件 API 较直接，`exec` 涉及 shell 选择、环境变量、进程树、timeout、abort 和流式回调，是复杂度最高的部分。
4. 然后读 `packages/agent/src/harness/utils/shell-output.ts`，看执行环境如何被更高层工具用于捕获和落盘大输出。
5. 最后读 `packages/agent/test/harness/nodejs-env.test.ts`，把测试当作行为合同，尤其关注非零退出码、symlink、abort、timeout、callback_error 和大输出捕获这些边界案例。
