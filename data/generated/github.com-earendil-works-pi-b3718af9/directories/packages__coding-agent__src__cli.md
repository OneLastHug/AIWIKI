# 子系统：packages/coding-agent/src/cli

## 解决什么问题

`packages/coding-agent/src/cli` 是 coding agent 的命令行适配层。它不直接实现大模型会话、工具执行或交互主界面，而是把用户从终端传入的参数、文件引用、启动期选择、项目信任确认、模型列表查询等“CLI 边界输入”整理成上层 `packages/coding-agent/src/main.ts` 可以消费的结构。

这个目录的核心职责可以概括为三类：第一，解析命令行参数，例如 `--model`、`--session`、`--resume`、`--print`、`--list-models`、`@file`、扩展自定义 flag；第二，处理启动前的辅助输入，例如把 `@file` 转成 prompt 文本和图片附件，把 stdin、文件内容、首条消息拼成初始 prompt；第三，提供启动期 TUI 小组件，例如恢复会话选择、配置选择、扩展信任流程里的选择和输入弹窗。

真正的程序入口是 `packages/coding-agent/src/cli.ts`，它设置 `process.title`、`PI_CODING_AGENT`、HTTP dispatcher，然后调用 `main(process.argv.slice(2))`。因此 `src/cli` 目录更像“CLI 辅助模块集合”，由 `main.ts` 统一编排。

## 相关目录和文件

`packages/coding-agent/src/cli/args.ts` 定义 `Args`、`Mode`、`parseArgs()` 和 `printHelp()`，是命令行语义的集中入口。它识别内置 flag，也会把未知的 `--xxx` 收集到 `unknownFlags`，供扩展系统使用。

`packages/coding-agent/src/cli/file-processor.ts` 处理 `@file` 参数。文本文件会被包装成 `<file name="...">...</file>`；图片文件会通过 MIME 检测和可选 resize 转成 `ImageContent`，同时在文本 prompt 中留下文件标记或尺寸说明。

`packages/coding-agent/src/cli/initial-message.ts` 负责把 stdin、`@file` 文本、第一条 CLI message 合并成 `initialMessage`，并携带 `initialImages`。它会从 `parsed.messages` 中移除首条消息，剩余消息继续作为后续 prompt。

`packages/coding-agent/src/cli/list-models.ts` 负责 `--list-models` 输出。它依赖 `ModelRegistry`，支持 fuzzy search，并按 provider、model 排序，输出 context、max-out、thinking、images 等列。

`packages/coding-agent/src/cli/session-picker.ts`、`config-selector.ts`、`startup-ui.ts` 是启动期 TUI 包装层，分别连接会话选择、配置选择、通用选择/输入组件。

`packages/coding-agent/src/cli/project-trust.ts` 把 CLI/TUI 能力包装成 `ProjectTrustContext`，供项目本地扩展、技能、主题、prompt template 等资源加载前的信任判断使用。

邻近的关键文件是 `packages/coding-agent/src/main.ts`。它导入上述模块，并进一步连接 `core/session-manager.ts`、`core/settings-manager.ts`、`core/agent-session-runtime.ts`、`core/model-resolver.ts`、`modes/interactive`、`modes/print-mode.ts`、`modes/rpc` 等真正运行层。

## 核心对象

`Args` 是该目录最重要的数据结构。它把 CLI 输入规范化为 provider、model、apiKey、session、fork、mode、tools、extensions、skills、themes、messages、fileArgs、unknownFlags、diagnostics 等字段。后续 `main.ts` 基本围绕这个对象做模式判断、会话选择、资源加载和 runtime 参数构造。

`Mode` 表示用户可指定的输出模式：`text`、`json`、`rpc`。`main.ts` 会再结合 `--print`、stdin/stdout 是否为 TTY，映射为应用层 `AppMode`：`interactive`、`print`、`json`、`rpc`。

`ProcessedFiles` 包含 `text` 和 `images`。它是 `@file` 到模型输入之间的桥梁，既支持文本上下文，也支持图片输入模型。

`InitialMessageResult` 包含 `initialMessage` 和 `initialImages`，是进入 `InteractiveMode` 或 `runPrintMode()` 前的初始用户消息。

`ProjectTrustContext` 不是在该目录定义，但 `createProjectTrustContext()` 在这里组装它。它把 `select`、`confirm`、`input`、`notify` 这些启动期 UI 能力暴露给项目信任解析流程。

## 运行流程

启动从 `packages/coding-agent/src/cli.ts` 进入，随后 `main.ts` 先处理 `--offline`、Windows 自更新隔离清理、扩展包管理命令和 `config` 命令。普通 agent 启动路径会调用 `parseArgs()` 得到 `Args`，如果有参数诊断错误则直接退出。

接着 `main.ts` 处理快速命令：`--version` 直接输出版本，`--export` 导出 session HTML。之后根据 `--mode`、`--print`、stdin/stdout TTY 状态确定运行模式，并验证 `--fork`、`--session-id` 等互斥关系。

会话阶段由 `createSessionManager()` 负责：`--no-session`、`--help`、`--list-models` 使用内存 session；`--fork` 从指定 session 复制；`--session` 按路径或 ID 查找；`--resume` 调用 `selectSession()` 弹出 TUI；`--continue` 使用最近 session；否则创建新 session。

runtime 创建阶段会读取 settings、auth、资源加载器、扩展 flag、模型 registry，并通过 `buildSessionOptions()` 把 CLI 模型、thinking、tools allowlist/denylist 等转成 `CreateAgentSessionOptions`。如果需要项目信任判断，会通过 `createProjectTrustContext()` 提供启动期 UI。

runtime 创建完成后，`--help` 会调用 `printHelp()`，并把扩展注册的 CLI flags 一起显示；`--list-models` 调用 `listModels()`。普通运行会读取 stdin，再用 `prepareInitialMessage()` 处理 `@file` 和初始 prompt。最后按模式分发：`rpc` 进入 `runRpcMode()`，交互终端进入 `InteractiveMode`，非交互或 `-p` 进入 `runPrintMode()`。

## 上下游依赖

上游是 Node 进程参数、stdin/stdout、当前工作目录、环境变量、用户本地配置和 session 文件。`args.ts` 还允许扩展系统把未知 flag 延迟解释，这使 CLI 层和扩展层保持松耦合。

下游主要是 `core` 和 `modes`。`core/session-manager.ts` 负责 session 创建、打开、查找、fork；`core/settings-manager.ts` 提供配置；`core/model-registry.ts` 和 `core/model-resolver.ts` 决定可用模型和 CLI 模型匹配；`core/agent-session-runtime.ts`、`core/agent-session-services.ts` 创建真正的 agent runtime；`modes/interactive`、`modes/print-mode.ts`、`modes/rpc` 承接最终运行。

外部包方面，`@earendil-works/pi-tui` 提供 TUI、终端、fuzzy filter、keybindings 接入；`@earendil-works/pi-ai` 提供模型和图片内容类型；`@earendil-works/pi-agent-core` 提供 `ThinkingLevel`；`chalk` 负责终端颜色输出。

## 修改时最容易踩的坑

最容易踩的是把 CLI 解析和 runtime 行为混在一起。`src/cli` 只应收集和标准化输入，真正影响 session、模型、工具、资源加载的逻辑大多在 `main.ts` 和 `core` 中。

第二个坑是新增 flag 时忘记互斥关系和 help 文案。`parseArgs()`、`printHelp()`、`main.ts` 中的验证逻辑通常要一起更新；如果 flag 会影响资源加载，还要考虑 `resourceLoaderOptions` 或 `extensionFlagValues`。

第三个坑是 `parsed.messages` 会被 `buildInitialMessage()` 原地 `shift()`。如果后续逻辑假设 messages 仍包含首条 prompt，会出现重复发送或漏发。

第四个坑是 RPC 模式不能使用 `@file`，因为 stdin 要留给 JSON-RPC；相关错误在 `main.ts` 中显式检查。修改文件输入逻辑时要保持这个边界。

第五个坑是启动期 TUI 与主题/keybindings 生命周期。`session-picker.ts`、`config-selector.ts`、`startup-ui.ts` 都会创建临时 `TUI`，需要正确 stop、clear 或停止 theme watcher，否则可能污染后续交互界面。

## 推荐阅读顺序

先读 `packages/coding-agent/src/cli.ts`，理解程序入口只做进程级初始化。然后读 `packages/coding-agent/src/main.ts`，重点看它如何调用 `parseArgs()`、`createSessionManager()`、`prepareInitialMessage()`、`createAgentSessionRuntime()` 和最终模式分发。

接着读 `packages/coding-agent/src/cli/args.ts`，掌握所有 CLI flag 的语义和 `Args` 结构。再读 `file-processor.ts`、`initial-message.ts`，理解文本、图片、stdin、首条消息如何合并。随后读 `session-picker.ts`、`startup-ui.ts`、`project-trust.ts`，看启动期 TUI 如何服务 session 恢复和项目信任。最后读 `list-models.ts`，它相对独立，适合作为模型 registry 输出路径的补充。
