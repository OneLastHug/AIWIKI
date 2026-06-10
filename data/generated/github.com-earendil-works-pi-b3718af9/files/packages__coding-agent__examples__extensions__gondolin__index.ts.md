# 文件：packages/coding-agent/examples/extensions/gondolin/index.ts

## 一句话定位
这是一个把 `pi` 的内置文件、搜索和 shell 工具重定向到 Gondolin micro-VM 中执行的扩展示例。它的核心价值不是新增业务能力，而是给 `pi-coding-agent` 提供一个“在 VM 里跑工具，但对用户看起来仍像本地工作区”的执行壳。

## 它暴露/定义了什么
文件默认导出一个扩展初始化函数，供 `pi -e ...` 加载。初始化后，它会注册一组能力：`gondolin` 命令、`read/write/edit/bash/ls/find/grep` 工具，以及 `user_bash`、`before_agent_start`、`session_start`、`session_shutdown` 等事件处理器。除此之外，它还定义了一批内部辅助函数，主要负责路径转换、文件遍历、grep 输出格式化和 VM shell 执行。

## 谁调用它
根据当前片段推断，调用方是 `pi` 的扩展加载器：用户通过 `pi -e /path/to/extensions/gondolin` 启动后，框架会执行这个默认导出函数，把 `ExtensionAPI` 注入进来。后续真正触发它内部逻辑的，是 `pi` 的会话生命周期和工具调用链，包括会话启动、用户执行 bash、agent 启动前注入提示词，以及具体工具的 `execute` 回调。

## 它调用谁
它主要调用两类外部依赖。第一类是 `@earendil-works/gondolin`，用 `VM.create` 创建微型虚拟机，用 `RealFSProvider` 把宿主工作区挂到 guest 的 `/workspace`，并通过 `vm.fs`、`vm.exec` 访问文件和运行命令。第二类是 `@earendil-works/pi-coding-agent` 提供的工具工厂：`createReadTool`、`createWriteTool`、`createEditTool`、`createBashTool`、`createFindTool`、`createGrepTool`、`createLsTool`，以及字符串截断和大小格式化辅助函数。

## 核心流程
整体流程是“先起 VM，再把工具接进去”。初始化时先记录本地 `cwd`，随后在 `session_start` 或首次工具调用时通过 `startVm` 懒启动 VM，并探测 guest 内可用的 shell，优先用 `bash`，否则退回 `/bin/sh`。VM 就绪后，各工具的执行都先把参数路径映射到 guest 路径，再交给 `pi-coding-agent` 的标准工具实现，但底层读写和命令执行改成走 Gondolin VM。`before_agent_start` 还会改写 system prompt，把“当前工作目录”明确成 VM 语义，避免 agent 误以为自己直接操作宿主机。`session_shutdown` 则负责关闭 VM，清理状态。

## 关键函数的高层作用
`toGuestPath`、`hostPathToGuest`、`isInsideHostPath` 负责把宿主路径、安全地转换成 guest `/workspace` 下的路径，这是整份文件最关键的边界层。`walkGuestFiles` 用于递归遍历 guest 文件树，供 `find` 和 `grep` 复用，并跳过 `.git`、`node_modules`。`executeGondolinGrep` 负责实现带上下文、glob、限制条数和截断提示的 grep 输出。`createGondolinBashOps` 则把命令执行包装进 `vm.exec`，同时处理超时、abort signal 和环境变量过滤。`startVm`、`ensureVm` 负责 VM 生命周期管理，`ensureVm` 还避免并发重复启动。

## 修改风险
这类文件最容易出问题的是路径语义和生命周期。只要 `toGuestPath` 出错，工具就可能把宿主路径误当 guest 路径，导致读写范围偏离预期。`grep`、`find` 的遍历逻辑也有性能和截断风险，尤其是大仓库里递归扫描时。`createGondolinBashOps` 对超时和中断做了包装，但如果底层 VM 行为变化，错误消息和退出码语义可能漂移。另一个风险是 `before_agent_start` 改写 prompt 的方式很脆弱，它依赖固定文本匹配，宿主提示词格式变化后，guest 目录说明可能注入失败。总体上，这是一个“基础设施型”文件，改动应优先保证路径映射、VM 关闭和工具输出格式稳定。
