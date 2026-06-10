# 文件：packages/coding-agent/examples/extensions/subagent/README.md

## 一句话定位

这是 `subagent` 示例扩展的使用说明书，负责把“如何安装、如何配置、如何调用子代理、如何理解输出”讲清楚。根据当前片段推断，它本身不参与运行时逻辑，主要服务于 `pi` 扩展使用者和维护者，让他们能把 `index.ts`、`agents.ts`、`agents/*.md`、`prompts/*.md` 组装成一个可用的子代理工作流。

## 它暴露/定义了什么

它定义的是一套面向示例扩展的约定，而不是代码 API。核心内容包括：安装方式、权限/安全模型、单代理与并行/链式任务的使用方式、工具模式参数、输出展示规则、Agent Frontmatter 规范、示例 Agent 列表、工作流 Prompt 列表、错误处理和限制说明。换句话说，它暴露的是“这个扩展怎么被使用”的全貌。

## 谁调用它

严格说，README 不被程序调用，而是被人和文档流程调用。典型读者是仓库贡献者、想本地试用扩展的 `pi` 用户，以及想了解 `subagent` 示例设计的人。按照文档里的安装步骤，使用者会把这里描述的文件链接到 `~/.pi/agent/extensions/subagent`、`~/.pi/agent/agents`、`~/.pi/agent/prompts`，然后在 `pi` 交互环境里通过自然语言或 `/implement`、`/scout-and-plan`、`/implement-and-review` 这类命令触发工作流。

## 它调用谁

README 不执行代码，但它明确指向了几个关键实现文件：`index.ts` 是扩展入口，`agents.ts` 负责 agent discovery，`agents/scout.md`、`agents/planner.md`、`agents/reviewer.md`、`agents/worker.md` 定义了不同角色，`prompts/implement.md`、`prompts/scout-and-plan.md`、`prompts/implement-and-review.md` 定义了预设链路。根据当前片段推断，真正的运行逻辑主要在这些文件里，README 只是把它们的协作关系串起来。

## 核心流程

这份文档描述的主流程很清楚：先完成符号链接安装，再由 `pi` 在运行时加载 agent 和 prompt；用户输入任务后，扩展按单代理、并行或链式模式分发任务；每个子代理在独立 `pi` 进程里运行，输出会被流式回传；必要时支持中断传播和 Markdown 渲染。文档还特别强调了并行模式的状态展示、输出截断、任务数量上限和失败诊断，这些都是用户实际感知最强的行为边界。

## 关键函数的高层作用

这里没有可执行函数可展开，但有几个“关键入口概念”值得看：`index.ts` 相当于扩展主入口，负责把 README 中承诺的能力接到 `pi` 的扩展体系里；`agents.ts` 的作用是发现和组织 Agent；`agents/*.md` 提供角色分工，决定子代理看到什么工具、用什么模型、承担什么职责；`prompts/*.md` 则把多个 agent 串成固定工作流。README 的价值在于把这些零散定义统一成可理解的操作模型。

## 修改风险

这类文件的风险主要是“文档和实现脱节”。如果 `index.ts`、`agents.ts` 或 agent/prompt 约定变了，但 README 没同步，用户会按过时步骤安装或误解安全边界。第二类风险是安全模型说明不准确，尤其是项目级 agent、`agentScope`、`confirmProjectAgents` 这些内容，一旦写错容易让用户低估执行外部命令的风险。第三类风险是限制描述过时，比如并行上限、输出截断、交互行为变化后，README 仍保留旧说法，会直接影响调试和排障效率。
