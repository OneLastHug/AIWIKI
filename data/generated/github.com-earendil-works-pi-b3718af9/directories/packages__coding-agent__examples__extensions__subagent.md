# 目录：packages/coding-agent/examples/extensions/subagent

## 它负责什么

`packages/coding-agent/examples/extensions/subagent` 是一个示例扩展目录，用来展示 `pi` coding agent 如何通过扩展机制增加一个 `subagent` 工具，把任务委派给独立上下文中的专用子代理。它不是核心运行时本身，而是一个“可安装示例”：把扩展入口、agent 定义和 workflow prompt 通过符号链接放到用户配置目录后，主 agent 就可以在对话中调用 `subagent` 工具。

这个目录表达的核心思想是：主 agent 不直接把所有搜索、计划、实现、复审过程都塞进同一个上下文，而是按角色启动独立的 `pi` 子进程。每个子进程有自己的 system prompt、工具权限、模型配置和上下文窗口，结束后把结构化结果回传给主进程。这样可以支持三类委派模式：单个子代理执行一个任务、多个子代理并行执行多个任务、多个子代理按链式流程顺序执行并通过 `{previous}` 传递上一步输出。

从实现上看，这个目录主要覆盖两层：`index.ts` 负责注册和运行工具，`agents.ts` 负责发现和解析 agent 配置；`agents/` 与 `prompts/` 则是示例数据，分别提供可被发现的角色定义和可通过斜杠命令触发的工作流模板。

## 直接子目录地图

`agents/` 存放示例子代理定义。每个文件是一个带 YAML frontmatter 的 Markdown 文件，frontmatter 中声明 `name`、`description`、可选的 `tools` 和 `model`，正文则是该子代理的 system prompt。当前示例包括 `scout`、`planner`、`reviewer`、`worker` 四种角色：`scout` 偏代码侦察和压缩上下文，`planner` 只读并产出实施计划，`reviewer` 做代码审查，`worker` 是拥有完整能力的通用执行者。

`prompts/` 存放 workflow preset，也就是可复用的 prompt 模板。它们不是 agent 定义，而是告诉主 agent 如何调用 `subagent` 工具的“编排说明”。例如 `implement.md` 描述 `scout -> planner -> worker`，`scout-and-plan.md` 描述只侦察和计划不实现，`implement-and-review.md` 描述 `worker -> reviewer -> worker` 的实现、复审、修正流程。

该目录本身还有 `README.md`、`index.ts`、`agents.ts` 三个顶层文件。`README.md` 是安装和使用说明；`index.ts` 是扩展入口；`agents.ts` 是 agent 发现和配置解析模块。

## 关键入口

最重要的入口是 `packages/coding-agent/examples/extensions/subagent/index.ts`。它默认导出一个函数，接收 `ExtensionAPI`，并通过 `pi.registerTool` 注册 `subagent` 工具。工具的参数结构支持三种形态：`agent + task` 的单任务模式、`tasks` 数组的并行模式、`chain` 数组的链式模式。文件顶部注释已经把这三种模式写得很清楚，后续执行逻辑也围绕这三种输入分支展开。

第二个入口是 `packages/coding-agent/examples/extensions/subagent/agents.ts`。这个文件不注册工具，而是为 `index.ts` 提供 `discoverAgents`。它会从用户级 agent 目录和项目级 `.pi/agents` 目录读取 Markdown agent 定义，解析 frontmatter，并返回 `AgentConfig` 列表。`AgentScope` 支持 `user`、`project`、`both`，其中项目级 agent 需要显式允许，这也是示例强调安全模型的地方。

使用层面的入口还包括 `prompts/` 下的三个模板。它们一般通过斜杠命令触发，例如 `/implement <query>`，再由主 agent 按模板内容调用 `subagent` 的 `chain` 参数。也就是说，`prompts/` 不直接执行代码，但它们是用户进入多 agent 工作流的常用路径。

## 主流程位置

主执行流程集中在 `index.ts` 的 `execute` 回调中。根据当前片段可见，执行时会先根据 `ctx.cwd` 和 `agentScope` 调用 `discoverAgents`，构建可用 agent 列表；然后判断传入参数属于 single、parallel 还是 chain；再校验请求的 agent 是否存在、项目级 agent 是否需要确认；最后进入对应分支运行子代理。

真正启动子进程的位置在 `runSingleAgent` 附近。它会组合 `pi` 调用参数，把 agent 的 system prompt、模型、工具列表和任务写入子进程执行环境；`writePromptToTempFile` 用于把 prompt 写入临时文件；`getPiInvocation` 用于决定当前应该复用当前脚本、当前运行时，还是直接调用 `pi` 命令。子进程通过 JSON/事件流回传消息，父进程收集 `messages`、`stderr`、`usage`、`stopReason` 等信息，形成 `SingleResult`。

并行流程的位置在 `params.tasks` 分支。这里通过 `MAX_PARALLEL_TASKS` 限制最多 8 个任务，并通过 `mapWithConcurrencyLimit` 把实际并发限制在 4 个。每个并行任务本质上仍然调用 `runSingleAgent`，只是结果被汇总成 parallel 详情，并且模型可见的每个任务输出会被 `PER_TASK_OUTPUT_CAP` 限制到 50 KB。

链式流程的位置在 `params.chain` 分支。它按顺序执行每一步，把上一步输出写入 `previous`，再替换下一步 task 中的 `{previous}` 占位符。如果某一步失败，链路会停止，并报告失败步骤。这个分支对应 `prompts/implement.md` 等模板中反复强调的“passing output between steps via {previous}”。

显示流程也在 `index.ts` 中。`renderSummary` 和 `renderDetail` 相关代码会把 single、parallel、chain 的状态、工具调用、文本片段、usage stats 渲染到 TUI。`formatToolCall` 模拟内置工具的展示风格，例如把 bash 展示为 `$ command`，把 read、grep、find 展示成紧凑的可读文本；`formatUsageStats` 则汇总 turns、input/output token、cache、cost、context token 和模型名。

## 推荐阅读顺序

建议先读 `README.md`，理解这个目录的目标、安装方式、安全模型和三种调用模式。这里能先建立“这是一个示例扩展，而不是内置子代理框架全部实现”的边界感。

第二步读 `agents.ts`。它短小但关键，能说明 agent 定义从哪里来、frontmatter 需要哪些字段、用户级和项目级 agent 如何合并，以及为什么 `agentScope: "both"` 时项目级定义会覆盖同名用户级定义。

第三步读 `index.ts` 的顶部类型、常量和工具函数，重点看 `SingleResult`、`SubagentDetails`、`runSingleAgent`、`mapWithConcurrencyLimit`、`getPiInvocation`。这些结构决定了子进程怎么启动、结果怎么表达、并发怎么限制。

第四步读 `index.ts` 中 `pi.registerTool` 的 `execute` 分支。这里是最适合串起主流程的位置：先发现 agent，再判断模式，再单个、并行或链式执行，最后返回给模型和 TUI。

最后再回头看 `agents/` 和 `prompts/`。这两个目录更像示例配置库，适合在理解执行器后阅读：`agents/` 展示一个 agent prompt 应该怎样写，`prompts/` 展示如何把多个 agent 组合成面向用户的工作流。

## 常见误区

一个常见误区是把 `agents/` 下的 Markdown 当成 TypeScript 插件入口。实际上它们只是被 `agents.ts` 发现和解析的配置文件，真正注册工具的是 `index.ts`。

另一个误区是认为项目里的 `.pi/agents` 会默认参与发现。根据当前片段，默认行为偏向用户级 agent；项目级 agent 只有在 `agentScope` 为 `project` 或 `both` 时才会加载，而且交互模式下还会有确认逻辑。这是安全边界，不是普通路径问题。

不要把 `prompts/` 理解成子代理本身。`prompts/implement.md` 这类文件只是指导主 agent 使用 `subagent` 工具的模板，它们通过 `chain` 参数组织 `scout`、`planner`、`worker` 等角色，但不会自己启动进程。

还要注意并行不等于无限并发。示例中参数允许最多 8 个 parallel task，但实际并发由 `MAX_CONCURRENCY` 控制为 4；过大的任务集会被拒绝或排队执行。

最后，`worker` 拥有更完整的默认能力，而 `scout`、`planner`、`reviewer` 都通过 frontmatter 限定了工具。阅读这个示例时应把“角色 prompt”和“工具权限”一起看，否则容易误判某个子代理能做什么。
