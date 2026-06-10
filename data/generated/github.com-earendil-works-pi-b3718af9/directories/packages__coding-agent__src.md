# 目录：packages/coding-agent/src

## 它负责什么

`packages/coding-agent/src` 是 `coding-agent` 包的 TypeScript 源码主体，承担命令行编码代理的启动、配置解析、会话管理、交互模式、非交互执行、RPC 模式、工具执行、扩展加载、导出、剪贴板与图片处理等运行时能力。它不是底层模型 SDK 本身，也不是终端 UI 组件库本身；从导入关系看，它会调用 `@earendil-works/pi-ai`、`@earendil-works/pi-agent-core`、`@earendil-works/pi-tui` 等包，把模型、会话、工具、终端界面和用户配置组装成一个可运行的 CLI 应用。

根据当前片段推断，这个目录的核心职责可以概括为三层：最外层是 CLI 启动与模式选择，中间层是 agent session/runtime/services，内层是工具、扩展、配置、文件、shell、图片、剪贴板等支撑能力。

## 直接子目录地图

`bun/` 放 Bun 运行时相关入口和环境修复逻辑，例如 `bun/cli.ts`、`bun/register-bedrock.ts`、`bun/restore-sandbox-env.ts`。它更像平台适配层，不是主业务逻辑中心。

`cli/` 负责命令行参数、初始消息、文件参数、模型列表、项目信任、会话选择和启动 UI。重要文件包括 `cli/args.ts`、`cli/initial-message.ts`、`cli/file-processor.ts`、`cli/list-models.ts`、`cli/project-trust.ts`、`cli/session-picker.ts`、`cli/startup-ui.ts`。如果想理解用户输入如何变成运行参数，应先看这里。

`core/` 是运行时核心。它包含 `agent-session.ts`、`agent-session-runtime.ts`、`agent-session-services.ts`、`session-manager.ts`、`settings-manager.ts`、`model-registry.ts`、`model-resolver.ts`、`system-prompt.ts`、`slash-commands.ts`、`bash-executor.ts`、`exec.ts`、`event-bus.ts`、`sdk.ts` 等。这里承载会话生命周期、模型解析、系统提示词、工具执行、事件传递、认证存储、配置管理、项目信任和 SDK 暴露。

`core/compaction/` 根据名称和位置推断负责上下文压缩或会话压缩相关逻辑；它属于 `core` 内部能力，不应先于会话主线阅读。

`core/export-html/` 负责把会话导出为 HTML，入口看起来是 `core/export-html/index.ts`，并配有工具渲染逻辑，如 `tool-renderer.ts`。

`core/extensions/` 负责扩展系统。`main.ts` 中导入了 `ExtensionFactory`，`export-html` 也引用了 `ToolDefinition`、`ToolRenderContext`，说明扩展既可能提供工具，也可能影响渲染或运行时能力。

`core/tools/` 是工具定义和工具执行相关区域。由于本次只做概览，不逐文件展开；从 `bash-executor.ts`、`exec.ts`、`extensions/types.ts` 的相邻关系看，工具系统应与 shell 执行、扩展工具和会话 runtime 紧密相关。

`modes/` 放应用运行模式。顶层有 `modes/index.ts`、`modes/print-mode.ts`，并分出 `modes/interactive/` 和 `modes/rpc/`。它对应 CLI 解析后真正进入的交互、打印、RPC 三类执行路径。

`modes/interactive/` 是终端交互模式主体。`main.ts` 导入了 `InteractiveMode` 和 `modes/interactive/theme/theme.ts`，说明这里包含 TUI 会话界面、输入输出、主题和交互行为。

`modes/rpc/` 是 RPC 模式主体，用于把 coding agent 作为可被外部进程调用的服务或协议端运行。具体协议细节需要继续进入该目录阅读。

`utils/` 是跨模块工具集合，覆盖 ANSI 处理、子进程、剪贴板、图片转换与缩放、Git URL 解析、路径、shell、语法高亮、工具下载、浏览器打开、版本检查、Windows 自更新等。这里支撑面很宽，但多数文件不是主流程入口。

## 关键入口

`main.ts` 是最关键的应用入口。它导出 `main(args, options?)`，并导入了参数解析、文件处理、初始消息、模型列表、项目信任、会话选择、启动 UI、runtime 创建、认证、HTML 导出、模型解析、输出保护、会话管理、设置管理、迁移、运行模式等大量模块。理解启动链路时应以 `main.ts` 为中心。

`cli.ts` 很可能是 Node CLI 的薄入口，用来调用 `main.ts`。与之对应，`bun/cli.ts` 是 Bun 分发或 Bun 运行时入口。

`index.ts` 和 `core/index.ts` 是包级导出入口。前者通常面向包外部使用者，后者面向核心能力聚合。若要看这个包暴露了哪些 API，应看这两个文件。

`package-manager-cli.ts` 是另一个命令路径，`main.ts` 中导入了 `handleConfigCommand`、`handlePackageCommand`，说明配置和包管理命令可能在进入 agent 会话前被提前处理。

`config.ts` 和 `migrations.ts` 虽然不在子目录内，但属于根层关键支撑文件。`config.ts` 提供目录、版本、环境变量等基础配置；`migrations.ts` 负责启动时迁移和弃用提示。

## 主流程位置

主启动流程位于 `main.ts`。根据当前片段推断，它大致按以下顺序组织：解析 `Args`，处理帮助、版本、模型列表、配置命令或包命令；读取管道输入和文件参数；解析工作目录、路径、项目信任、会话恢复或 fork；加载设置、认证和模型 registry；解析 CLI 指定模型或恢复会话模型；创建 `SessionManager` 和 `AgentSessionRuntime`；最后根据 `resolveAppMode` 进入 `InteractiveMode`、`runPrintMode` 或 `runRpcMode`。

交互主流程在 `modes/interactive/`。它是用户看到的 TUI 层，负责持续输入、渲染输出、主题和会话交互。它不应被误认为模型逻辑本体；真正的 session 和工具调度在 `core/`。

非交互主流程在 `modes/print-mode.ts`。当 stdin/stdout 或参数决定进入一次性执行时，`main.ts` 会把初始消息和会话选项交给 print mode，输出结果后退出。

RPC 主流程在 `modes/rpc/`。它服务于机器间调用或外部集成，入口由 `runRpcMode` 暴露到 `modes/index.ts` 再被 `main.ts` 调用。

会话核心流程在 `core/agent-session.ts`、`core/agent-session-runtime.ts`、`core/agent-session-services.ts`、`core/session-manager.ts`。其中 `session-manager` 更偏持久化和会话文件管理，`agent-session-runtime` 更偏运行时装配，`agent-session` 更偏一次会话中的消息、模型、工具和状态流转。这个判断基于文件命名和 `main.ts` 的导入关系。

工具执行流程应从 `core/bash-executor.ts`、`core/exec.ts`、`core/tools/` 和 `core/extensions/` 一起看。内置 shell 执行、扩展工具定义、工具渲染和输出保护分布在不同文件中，不是单文件完成。

## 推荐阅读顺序

1. 先看 `main.ts`，建立“启动参数到运行模式”的总路线图。
2. 再看 `cli/args.ts`、`cli/initial-message.ts`、`cli/file-processor.ts`，理解用户命令如何被标准化。
3. 接着看 `core/session-manager.ts`、`core/agent-session-runtime.ts`、`core/agent-session.ts`，理解会话如何创建、恢复、运行和保存。
4. 然后按关心的使用方式选择阅读：终端交互看 `modes/interactive/`，一次性命令看 `modes/print-mode.ts`，外部协议看 `modes/rpc/`。
5. 模型相关看 `core/model-registry.ts`、`core/model-resolver.ts`、`core/defaults.ts`、`core/provider-display-names.ts`。
6. 工具与扩展看 `core/tools/`、`core/extensions/`、`core/bash-executor.ts`、`core/slash-commands.ts`。
7. 最后补充阅读 `utils/` 中与具体问题相关的文件，例如图片问题看 `image-*`，shell 问题看 `shell.ts` 和 `child-process.ts`，路径问题看 `paths.ts`。

## 常见误区

不要把 `packages/coding-agent/src` 当成模型提供方实现。模型列表、模型解析和认证在这里编排，但具体 AI provider 能力来自相邻包和外部依赖。

不要从 `utils/` 开始读主流程。`utils/` 文件多且杂，适合按问题索引，不适合作为理解应用架构的入口。

不要把 `modes/interactive/` 理解成全部业务逻辑。它主要承担交互界面和交互状态，真正的会话、工具和模型调度在 `core/`。

不要忽略根层文件。`main.ts`、`config.ts`、`index.ts`、`cli.ts`、`package-manager-cli.ts` 虽然不在子目录里，但它们是理解整个 `src` 的关键骨架。

不要逐个叶子文件平均阅读。这个目录是大目录，正确方法是先抓 `main.ts`、`cli/`、`core/session*`、`modes/` 的主干，再按功能深入 `tools`、`extensions`、`export-html` 或 `utils`。
