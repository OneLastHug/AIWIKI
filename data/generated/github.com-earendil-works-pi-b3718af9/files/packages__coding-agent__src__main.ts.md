# 文件：packages/coding-agent/src/main.ts

## 一句话定位

`packages/coding-agent/src/main.ts` 是 `@earendil-works/pi-coding-agent` 的 CLI 主编排入口：它不直接实现模型推理、TUI 渲染或工具执行，而是把命令行参数、会话、配置、扩展、项目信任、输入内容和运行模式组装成一个 `AgentSessionRuntime`，再分发到 interactive、print/json 或 rpc 模式。

## 它暴露/定义了什么

该文件主要暴露 `main(args: string[], options?: MainOptions)`，并定义 `MainOptions`，目前可传入 `extensionFactories?: ExtensionFactory[]`，用于嵌入式集成或自定义入口注入内联扩展工厂。

文件内部还定义了一批入口级辅助函数：`readPipedStdin` 读取管道输入，`resolveAppMode` 判断最终运行模式，`prepareInitialMessage` 合并 CLI 文本、`@file` 文件内容和 stdin，`createSessionManager` 解析新建、继续、恢复、指定、fork 会话，`buildSessionOptions` 将 CLI 模型、thinking、工具开关等转换成 `CreateAgentSessionOptions`。这些函数服务于入口编排，不是底层业务核心。

## 谁调用它

直接 CLI 入口是 `packages/coding-agent/src/cli.ts`：它设置 `process.title`、`PI_CODING_AGENT`、HTTP dispatcher 和 warning 行为后调用 `main(process.argv.slice(2))`。包级 API 也在 `packages/coding-agent/src/index.ts` 重新导出 `main` 和 `MainOptions`，因此外部程序可以把它当成可嵌入入口调用。测试中也直接 import `main`，尤其用于包管理命令路径、配置命令等 CLI 行为验证。

根据 `package.json`，发布后的 bin 名称是 `pi`，指向 `dist/cli.js`；源码层面对应 `src/cli.ts` 再进入本文件。

## 它调用谁

向下游看，`main.ts` 依赖几类模块：

CLI 解析和输入处理来自 `./cli/args.ts`、`./cli/file-processor.ts`、`./cli/initial-message.ts`、`./cli/list-models.ts`、`./cli/session-picker.ts`、`./cli/startup-ui.ts`。会话与运行时来自 `./core/session-manager.ts`、`./core/agent-session-runtime.ts`、`./core/agent-session-services.ts`、`./core/sdk.ts`。配置、鉴权、模型解析和信任逻辑来自 `SettingsManager`、`AuthStorage`、`resolveCliModel`、`resolveModelScope`、`ProjectTrustStore`、`resolveProjectTrusted`。最终执行模式来自 `./modes/index.ts` 的 `InteractiveMode`、`runPrintMode`、`runRpcMode`。此外还会调用迁移、导出 HTML、HTTP dispatcher、主题初始化、Windows 自更新清理、包管理和配置命令处理等入口级功能。

## 核心流程

`main` 开始会重置启动计时，处理 `--offline`/`PI_OFFLINE`，Windows 下清理自更新隔离文件。随后优先尝试 `handlePackageCommand` 和 `handleConfigCommand`，这意味着 `pi install/list/update`、配置类命令会在普通 agent 启动前短路返回。

接着调用 `parseArgs`，输出参数诊断；`--version` 和 `--export` 也是早退出路径。然后通过 `resolveAppMode` 判断 `rpc`、`json`、`print` 或 `interactive`：显式 `--mode rpc/json` 优先，其次 `--print`、非 TTY stdin/stdout 会进入 print，否则进入 interactive。非交互模式会用 `takeOverStdout` 管控 stdout，避免模型流式输出和普通日志混杂。

会话阶段先校验 `--fork`、`--session-id` 冲突，再运行迁移，读取启动 cwd 的设置，解析 sessionDir，然后由 `createSessionManager` 创建、打开、继续、恢复或 fork 会话。若恢复的会话 cwd 缺失，交互模式会提示选择 fallback cwd，非交互模式直接报错退出。之后处理 `--name` 写入会话信息。

运行时阶段创建 `ProjectTrustStore`、解析 CLI 传入的扩展/技能/提示模板/主题路径，并构造 `createRuntime` 工厂。这个工厂会按目标 cwd 创建 `SettingsManager` 和 `createAgentSessionServices`，处理项目信任、加载资源、扩展错误、模型 scope、CLI 模型和 thinking、工具过滤、临时 API key，最后通过 `createAgentSessionFromServices` 得到 session。外层再用 `createAgentSessionRuntime` 包一层，支持后续 runtime reload 或 session start event。

运行时创建后，文件处理 `--help` 和 `--list-models` 这类依赖扩展/模型注册表的元数据命令。随后读取 stdin，必要时把 interactive 降级为 print；再构建初始消息和图片，初始化主题，报告诊断，检查非交互模式必须有模型。最后按模式分发：`rpc` 调 `runRpcMode(runtime)`，`interactive` 创建 `InteractiveMode` 并 `run()`，print/json 调 `runPrintMode(runtime, ...)`，并负责 `stopThemeWatcher`、`restoreStdout` 和 exit code 设置。

## 关键函数的高层作用

`main` 是唯一对外入口，职责是“启动编排”：参数、会话、配置、信任、资源、模型、输入和模式分发都在这里串起来。

`createSessionManager` 是会话路由器，集中处理 `--no-session`、`--fork`、`--session`、`--resume`、`--continue`、`--session-id` 的优先级和错误退出。它会区分本地 session、全局 session、直接路径和未找到，并在跨项目恢复时让用户确认是否 fork。

`buildSessionOptions` 是 CLI 到 SDK option 的转换层：解析 `--model`/`--provider`、`--models` scope、thinking level、工具启用/排除策略，并产生诊断。它避免把复杂 CLI 语义泄漏到 `createAgentSessionFromServices`。

`resolveAppMode` 决定进程行为边界，尤其影响 stdin 是否作为 prompt、stdout 是否被接管、是否启动 TUI。这个函数虽短，但修改会影响脚本管道、CI、JSON 输出和交互终端体验。

`prepareInitialMessage` 负责把普通消息、文件参数和管道输入合成首条用户输入，并携带图片内容；具体文件读取和消息拼接委托给 `processFileArguments`、`buildInitialMessage`。

## 修改风险

最大风险是入口顺序。`handlePackageCommand`、`handleConfigCommand`、`--version`、`--export`、`--help`、`--list-models` 各自依赖不同初始化深度；随意移动可能导致本应快速退出的命令加载扩展、触发信任提示、读取 stdin 或创建会话。

第二类风险是模式判断和 stdout 管控。`resolveAppMode`、`takeOverStdout`、`restoreStdout`、`readPipedStdin` 共同决定 CLI 在管道、JSON、RPC 和 TTY 下的可脚本化行为。这里的回归通常不会表现为类型错误，而是表现为输出污染、命令挂起或 RPC stdin 被错误消费。

第三类风险是会话 cwd 和项目信任。`--session`、`--resume` 可能切到另一个项目 cwd，因此 runtime 服务必须在最终 session cwd 确定后创建。若提前加载项目配置、扩展或模型，可能读错项目资源，甚至绕过或重复触发信任判断。

第四类风险是扩展和模型解析。`MainOptions.extensionFactories`、CLI extension paths、settings enabled models、`--api-key`、`--model` shorthand thinking 都在这里汇合；修改时要同时覆盖普通 CLI、嵌入式调用、非交互和已有会话恢复场景。

最后，错误处理大量使用 `process.exit` 或 `process.exitCode`。把这些路径改成 throw/return 会影响 CLI 行为和测试预期；反过来，在可嵌入 `main()` 场景中过早退出进程也可能伤害宿主程序。
