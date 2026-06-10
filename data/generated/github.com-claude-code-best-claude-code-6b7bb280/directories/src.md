# 目录：src

## 它负责什么

`src` 是这个 CLI 的主应用层，承载从命令行启动、配置初始化、交互式 REPL、模型请求、工具调用、权限控制、状态管理到各种子命令的核心流程。根据当前片段推断，这个仓库把底层工具实现的一部分下沉到了 workspace 包，例如 `packages/builtin-tools`，而 `src` 更像“编排层”：决定什么时候加载哪些功能、如何把用户输入变成消息、如何调用 API、如何渲染终端 UI、如何执行工具并把结果接回对话。

这个目录同时包含两类代码：一类是常驻主链路，例如 `src/entrypoints/cli.tsx`、`src/main.tsx`、`src/query.ts`、`src/QueryEngine.ts`、`src/screens/REPL.tsx`、`src/services/api/claude.ts`、`src/tools.ts`；另一类是大量功能模块，例如 slash commands、MCP、Bridge、Daemon、ACP、插件、技能、记忆、压缩、认证、遥测、后台任务等。阅读时不要把它当成普通“小型 CLI 项目”，它更接近一个终端应用框架加 AI agent 运行时。

## 直接子目录地图

`src/entrypoints` 放真正的进程入口与特殊模式入口，`cli.tsx` 是最重要的启动文件，`init.ts` 负责一次性初始化。

`src/commands` 是 slash command 与 CLI 内部命令的大目录，包含 `mcp`、`login`、`model`、`memory`、`plugin`、`doctor`、`resume`、`compact`、`poor`、`voice`、`daemon`、`bridge` 等命令。这个目录很大，overview 阶段只需要知道它是命令注册与命令行为的来源，不必逐个读叶子目录。

`src/components`、`src/screens` 是终端 UI 层。项目使用 React/Ink，`src/screens/REPL.tsx` 承接交互式会话界面，`src/components` 下则是消息渲染、输入框、权限弹窗、设置、MCP、diff、skills、tasks 等组件。

`src/services` 是服务层，包含 API、认证、MCP、analytics、compact、SessionMemory、MagicDocs、plugins、policyLimits、providerRegistry、lsp、langfuse、skillSearch 等。外部系统、模型提供商、后台服务和可观测性相关逻辑大多从这里进入。

`src/utils` 是最大的一组通用能力，覆盖模型选择、消息转换、配置、认证辅助、git、shell、sandbox、settings、permissions、plugins、skills、tokens、sessionStorage、processUserInput 等。这里不是纯工具函数仓库，很多运行时关键逻辑也在其中。

`src/state` 是全局应用状态，核心是 `AppState`、store 和 selectors。`src/bootstrap` 保存进程级状态单例，例如 session、cwd、模型覆盖、权限模式等。

`src/query` 与根部的 `src/query.ts`、`src/QueryEngine.ts` 是对话主循环相关区域。`src/query.ts` 负责单轮/多轮消息发送、流式响应、工具调用、压缩、预算与错误处理；`QueryEngine` 则面向 REPL 或 SDK 管理更高层会话状态。

`src/bridge`、`src/daemon`、`src/cli`、`src/remote` 处理远程控制、后台会话、守护进程和命令行辅助通道。`src/services/acp` 和 `src/cli/handlers` 则涉及 Agent Client Protocol、template jobs、autonomy 等特殊入口。

`src/tasks`、`src/jobs`、`src/assistant`、`src/buddy`、`src/proactive` 是 agent、后台任务或实验性能力区域。`src/types`、`src/constants`、`src/schemas` 提供类型、常量和结构定义。`src/hooks`、`src/keybindings`、`src/vim` 支撑交互输入、快捷键和编辑模式。`src/context`、根部 `src/context.ts` 与 `src/memdir` 负责系统上下文、用户上下文、记忆文件和 CLAUDE.md 相关加载。

## 关键入口

最外层入口是 `src/entrypoints/cli.tsx`。它先做极轻量启动，例如 performance shim、`MACRO` fallback、环境变量修正，然后检查快速路径。`--version` 不加载完整 CLI；`--dump-system-prompt`、`--claude-in-chrome-mcp`、`--computer-use-mcp`、`--acp`、`daemon`、`remote-control`、`job`、`environment-runner`、`self-hosted-runner`、`--bg` 等都会在这里被提前分流。没有命中特殊路径时，它才动态 import `src/main.jsx` 并执行 `main()`。

完整 CLI 入口是 `src/main.tsx`。这里用 Commander 注册主命令和大量 subcommands，并在主 action 中完成配置、权限、MCP、模型、会话恢复、headless/REPL 分发等工作。它也是连接 `commands`、`tools`、`services`、`components` 的大枢纽。

交互式入口继续落到 `src/replLauncher.tsx` 和 `src/screens/REPL.tsx`。前者更像启动包装，后者是终端对话 UI 的主体。

## 主流程位置

主流程可以按“启动、初始化、输入、查询、工具、渲染”理解。

启动阶段在 `src/entrypoints/cli.tsx`：先识别 fast path，能不加载主应用就不加载。普通交互进入 `src/main.tsx`。

初始化阶段在 `src/main.tsx` 与 `src/entrypoints/init.ts`：读取配置、应用 managed settings、初始化 telemetry/growthbook/policy limits、处理 trust dialog、认证和启动前检查。

输入阶段在 `src/screens/REPL.tsx`、`src/components/PromptInput`、`src/utils/processUserInput/processUserInput.ts` 一带。用户输入会被识别为普通 prompt、slash command、本地命令、附件或特殊控制指令。

会话编排在 `src/QueryEngine.ts`。它维护会话级状态、文件历史、归因、消息规范化、SDK 兼容输出、插件缓存、memory prompt，并调用底层 `query()`。

模型主循环在 `src/query.ts`。这里处理系统提示、上下文追加、消息压缩、token budget、API 错误、流事件、工具调用、tool result 回填、stop hooks、Langfuse trace 等。

API 请求在 `src/services/api/claude.ts` 及 `src/services/api/*`。模型提供商选择由 `src/utils/model/providers.ts` 等模块参与。工具列表由 `src/tools.ts` 汇总，具体工具执行编排在 `src/services/tools`，工具接口定义在 `src/Tool.ts`。

UI 回显回到 `src/screens/REPL.tsx` 和 `src/components/messages`、`src/components/permissions` 等组件，形成下一轮输入。

## 推荐阅读顺序

第一步读 `src/entrypoints/cli.tsx`，先掌握进程如何分流，尤其是哪些功能不会进入完整 `main.tsx`。

第二步读 `src/main.tsx` 的 imports、Commander 注册和主 action，不需要逐行吃完，但要标出配置初始化、MCP、工具加载、REPL/headless 分发的位置。

第三步读 `src/replLauncher.tsx`、`src/screens/REPL.tsx`、`src/state/AppState.tsx`，理解交互 UI、状态和权限提示怎么衔接。

第四步读 `src/QueryEngine.ts`，这是从 UI/SDK 进入对话主循环前的会话编排层。

第五步读 `src/query.ts`，重点看消息如何进入 API、工具调用如何被执行、结果如何追加回 messages、何时 compact 或中断。

第六步按兴趣分支阅读：命令读 `src/commands` 和 `src/commands.ts`；工具读 `src/tools.ts`、`src/Tool.ts`、`src/services/tools`；模型提供商读 `src/services/api`、`src/utils/model`；远程控制读 `src/bridge`、`src/daemon`、`src/services/acp`。

## 常见误区

不要以为 `src/main.tsx` 是唯一入口。很多模式在 `src/entrypoints/cli.tsx` 已经提前 return，例如 daemon、bridge、ACP、MCP server、runner 和版本输出。

不要把 `src/tools.ts` 理解为所有工具实现的位置。它主要是注册和装配，许多内置工具来自 `@claude-code-best/builtin-tools`，实际代码在 workspace package 中。

不要把 `src/utils` 当作低风险杂物目录。这个目录里有模型选择、消息处理、配置、安全权限、session、tokens 等关键路径，修改影响面可能很大。

不要逐个展开 `src/commands` 或 `src/components` 的叶子目录来理解主流程。overview 阶段应先抓住入口、状态、query loop、API、tool orchestration 这条主线。

不要忽略 feature flag。代码中大量使用 `feature('FLAG')`，而且仓库说明要求它只能直接出现在 `if` 或三元条件位置。阅读某段逻辑时要同时判断它是否可能在当前 build/dev 配置下启用。

不要把 React Compiler 产生的 `_c()` memoization 当成人手写业务逻辑。组件里这类结构是反编译/编译产物特征，阅读时应优先看 props、状态、事件处理和渲染分支。
