# 目录：packages/coding-agent/examples/extensions

## 它负责什么

`packages/coding-agent/examples/extensions` 是 `pi-coding-agent` 的扩展示例集合，用来展示 Extension API 可以接入哪些能力，以及不同扩展点应该怎样组合。它不是运行时核心实现目录，而是面向扩展作者的“样例地图”：每个 `.ts` 文件或子目录通常代表一种独立扩展模式，可以通过 `pi --extension examples/extensions/<name>.ts` 显式加载，也可以复制到用户或项目的 `.pi/agent/extensions/` 一类扩展目录中被发现。

从 README 和示例代码看，这个目录覆盖的能力面很宽：生命周期事件拦截、安全确认、工具注册、命令注册、TUI 自定义、系统提示词追加、上下文压缩、Git 集成、会话元数据、资源发现、自定义模型 provider、子代理、远程/沙箱执行等。理解它时不要把它当成一个统一应用，而应把它看成扩展机制的 cookbook：目录中的示例共同说明 `ExtensionAPI` 如何通过 `pi.on(...)`、`pi.registerTool(...)`、`pi.registerCommand(...)`、`pi.registerFlag(...)`、`pi.setActiveTools(...)`、`ctx.ui.*` 等入口影响 agent 行为。

## 直接子目录地图

`custom-provider-anthropic/` 展示自定义 Anthropic provider，包括独立 `package.json`、`package-lock.json` 和 `index.ts`，重点是 OAuth 与自定义 streaming provider 的组织方式。

`custom-provider-gitlab-duo/` 展示 GitLab Duo provider。根据当前片段推断，它更偏向通过代理复用 `pi-ai` 已有 Anthropic/OpenAI streaming 能力，目录内还带有 `test.ts`。

`doom-overlay/` 是复杂 TUI overlay 示例，包含 `index.ts`、渲染组件、按键映射、游戏引擎桥接、WAD 查找，以及 `doom/` 下的 C 侧适配与构建脚本。它主要用来展示高频刷新、实时交互和 overlay 组合能力。

`dynamic-resources/` 展示 `resources_discover` 资源发现，目录中有 `index.ts`、`SKILL.md`、`dynamic.md`、`dynamic.json`，对应动态技能、提示词或主题等资源加载。

`gondolin/` 展示把内置工具和 `!` 命令路由到 Gondolin micro-VM。它带独立依赖配置，属于系统隔离/执行后端类示例。

`plan-mode/` 是 Claude Code 风格的计划模式示例，`index.ts` 是入口，`utils.ts` 放安全命令判断和计划项解析等辅助逻辑，`README.md` 说明用法。它演示只读探索、命令拦截、状态持久化、快捷键和进度 UI。

`sandbox/` 展示基于 `@anthropic-ai/sandbox-runtime` 的 OS 级 sandbox，带独立包配置和入口文件。

`subagent/` 展示子代理委派。`index.ts` 是工具入口，`agents.ts` 负责发现 agent 配置，`agents/` 存放角色定义，`prompts/` 存放复合工作流提示词。它代表目录里较完整的“扩展内调度器”示例。

`with-deps/` 展示扩展自带依赖的组织方式，重点是独立 `package.json` 与 jiti/module resolution，而不是某个具体 agent 工作流。

## 关键入口

最小入口是 `hello.ts`。它用 `defineTool(...)` 定义 `helloTool`，再在默认导出函数 `export default function (pi: ExtensionAPI)` 中调用 `pi.registerTool(helloTool)`。这是理解扩展加载模型的第一块：扩展文件默认导出函数接收 `ExtensionAPI`，所有注册动作都在这里发生。

命令与 TUI 入口可看 `tools.ts`。它注册 `/tools` 命令，用 `pi.getAllTools()`、`pi.getActiveTools()`、`pi.setActiveTools()` 管理工具开关，并通过 `ctx.ui.custom(...)` 渲染交互列表；同时用 `pi.appendEntry(...)` 和 `ctx.sessionManager.getBranch()` 做状态持久化与分支恢复。

事件拦截入口散布在多个单文件示例中。README 明确列出 `permission-gate.ts`、`protected-paths.ts`、`confirm-destructive.ts`、`dirty-repo-guard.ts` 等安全类示例，它们核心都围绕 `pi.on("tool_call", ...)` 或会话相关事件返回 block/确认结果。

复杂能力入口集中在目录型示例。`plan-mode/index.ts` 展示 `registerFlag`、`registerCommand`、`registerShortcut`、`tool_call`、`context`、`before_agent_start` 等多个扩展点组合；`subagent/index.ts` 展示注册一个委派工具后，通过子进程启动独立 `pi`，并用结构化结果回收输出；`doom-overlay/index.ts` 则是 overlay UI 能力的综合入口。

## 主流程位置

扩展的主流程可以按“加载、注册、运行时回调、状态恢复”来读。

加载阶段由 agent 运行时负责，示例侧体现为每个扩展默认导出函数，例如 `hello.ts`、`tools.ts`、`plan-mode/index.ts`、`subagent/index.ts`。这些函数同步或异步地把工具、命令、快捷键、事件监听器、provider 或资源发现逻辑注册到 `pi` 上。

注册阶段最常见的三条线是工具、命令和事件。工具线通过 `defineTool(...)` 或 `pi.registerTool(...)` 暴露给模型调用；命令线通过 `pi.registerCommand(...)` 暴露给用户输入；事件线通过 `pi.on(...)` 接入生命周期，例如 `session_start` 恢复状态、`tool_call` 审查工具调用、`context` 改写上下文、`before_agent_start` 注入提示词或约束。

运行时阶段由用户输入、模型工具调用或 UI 操作触发。比如 `tools.ts` 中用户执行 `/tools` 后打开 TUI 列表，切换状态后立即 `pi.setActiveTools(...)` 并 `pi.appendEntry(...)`；`plan-mode/index.ts` 中 `/plan` 或快捷键会切换只读工具集，随后 `tool_call` 事件检查 bash 命令是否安全；`subagent/index.ts` 中模型调用子代理工具后，扩展生成任务、启动外部 `pi` 进程、收集消息与用量，再把结果作为工具结果返回。

状态恢复主要依赖 session branch。README 的“State persistence via details”说明工具状态应写入 tool result `details`，而 `tools.ts` 还展示了用 custom entry 保存扩展状态，再在 `session_start`、`session_tree` 中从 `ctx.sessionManager.getBranch()` 重建当前分支状态。

## 推荐阅读顺序

1. 先读 `README.md`，建立分类视角：安全、工具、命令/UI、Git、系统提示词、资源、provider、依赖等。
2. 读 `hello.ts`，掌握最小扩展结构：默认导出函数、`ExtensionAPI`、`defineTool`、`registerTool`。
3. 读 `tools.ts`，理解命令注册、TUI 自定义、工具启停和 session 状态恢复。
4. 读几个安全类单文件，例如 `permission-gate.ts`、`protected-paths.ts`、`confirm-destructive.ts`，重点看 `tool_call` 阻断或确认模式。
5. 读 `plan-mode/index.ts` 和 `plan-mode/utils.ts`，学习多个扩展点如何组合成一个用户可感知的模式。
6. 读 `dynamic-resources/`、`subagent/`、`custom-provider-*`、`doom-overlay/` 这类目录型示例，分别对应资源发现、子代理调度、provider 扩展和复杂 UI/实时渲染。

## 常见误区

不要把这个目录当成生产默认扩展集合。这里的文件主要是示例，许多扩展展示的是某个 API 能力边界，未必适合作为默认策略直接启用。

不要逐个叶子文件背功能。overview 层面应先按扩展点分类：`registerTool` 是给模型新增工具，`registerCommand` 是给用户新增 slash command，`pi.on` 是接入生命周期，`ctx.ui.*` 是控制 TUI，provider 目录是模型后端扩展。

不要把状态只放在模块级变量里。示例中 `tools.ts` 和 README 都强调要把状态写回 session entry 或 tool result `details`，否则分支切换、会话恢复、fork 后状态会和历史不一致。

不要误以为 UI 示例只影响显示。像 `tools.ts`、`plan-mode/index.ts` 这类文件里的 UI 操作会进一步改变 active tools、上下文注入和工具调用权限，属于行为层扩展。

不要把目录型示例和单文件示例等价看待。`subagent/`、`doom-overlay/`、`custom-provider-*`、`sandbox/`、`with-deps/` 都有自己的依赖或辅助模块，阅读时应从各自 `index.ts` 进入，再看 README、配置文件和辅助模块。
