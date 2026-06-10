# 子系统：packages/builtin-tools/src/tools

## 解决什么问题

这个目录负责“Claude Code 的内置工具实现层”。它把文件读写、Shell 执行、Web 检索、任务管理、规划模式、子 agent、工作区切换、MCP 资源访问等能力拆成一个个独立工具目录，再由上层统一拼装成可用的工具池。根据当前片段推断，它的目标不是提供单一业务功能，而是提供一整套可被模型调用的标准工具面板，并且支持按环境变量、feature flag、权限规则动态增减。

## 相关目录和文件

最核心的入口是 `packages/builtin-tools/src/index.ts`，它把 `AgentTool`、`FileReadTool`、`WebFetchTool`、`WorkflowTool` 等主工具统一 re-export，供宿主侧深度导入。`packages/builtin-tools/package.json` 说明这个包的主入口也是 `src/index.ts`，同时暴露 `./tools/*` 深层路径，便于按工具单独引用。

真正决定“哪些工具可见、如何组合”的逻辑在仓库上层的 `src/tools.ts`，它从这个目录逐个导入实现，再做 feature gate、权限过滤、REPL 简化模式和 MCP 工具合并。目录内还有两个很重要的公共辅助文件：`packages/builtin-tools/src/tools/utils.ts` 负责消息标记类通用函数；`packages/builtin-tools/src/tools/shared/` 放跨工具复用的小工具，比如 Git 操作跟踪和多 agent 生成逻辑。

## 核心对象

这里的核心对象不是单个类，而是一套“工具约定”。每个子目录通常导出一个工具实现，例如 `FileEditTool`、`PowerShellTool`、`AgentTool`、`WorkflowTool`，并配套自己的 `prompt.ts`、`UI.tsx`、`constants.ts`、`__tests__/`。

上层会把它们当作 `Tool` 对象数组来处理，关键集合函数是 `getAllBaseTools()`、`getTools()`、`assembleToolPool()`、`getMergedTools()`。其中 `getAllBaseTools()` 定义了内置工具的完整候选集，`getTools()` 会做环境过滤和权限裁剪，`assembleToolPool()` 再和 MCP 工具合并去重。`SYNTHETIC_OUTPUT_TOOL_NAME`、`initBundledWorkflows()`、`getWorkflowCommands()` 这类导出说明这个目录里还承担了少量“非传统工具对象”的支撑角色。

## 运行流程

典型流程是：宿主层先从 `src/tools.ts` 读取当前运行环境，再从这个目录加载对应工具实现。随后 `getAllBaseTools()` 先拼出基础工具，再按 `process.env.USER_TYPE`、`feature('...')`、`isTodoV2Enabled()`、`isWorktreeModeEnabled()` 等条件附加可选工具。接着 `getTools()` 会依据权限上下文过滤掉被 deny 的工具，在 REPL 或 simple mode 下进一步缩减工具集。

如果还要接入 MCP 工具，`assembleToolPool()` 会把内置工具和 MCP 工具合并、按名字排序并去重，保证 built-in 工具优先。`utils.ts` 里的 `tagMessagesWithToolUseID()` 和 `getToolUseIDFromParentMessage()` 则服务于消息流转：前者给用户消息打上临时来源标记，后者从父 assistant 消息中反查 tool use id，避免 UI 中“运行中”状态重复展示。

## 上下游依赖

上游主要来自宿主应用 `src/tools.ts`、`src/query.ts`、`src/services/api/claude.ts`、`src/screens/REPL.tsx` 这类调用方，它们需要从这里拿到稳定的工具列表。下游则是各个具体工具目录依赖的支撑模块，比如 `src/types/message.ts`、权限相关代码、MCP 资源处理、以及 `packages/agent-tools` 这类工作流/子 agent 辅助包。

需要注意的是，这个目录并不孤立。像 `AgentTool` 会反向依赖 `Tool` 体系和其他工具的常量名，`WorkflowTool` 还会调用 `bundled/index.ts` 初始化内置工作流，`PowerShellTool` 会依赖额外的安全与命令语义校验文件。换句话说，它既是工具实现层，也是整个工具生态的装配中心。

## 修改时最容易踩的坑

第一，别只改单个工具目录而忘了 `src/index.ts` 或上层 `src/tools.ts` 的注册逻辑，否则工具文件存在但永远不会出现在运行时。第二，feature gate 和环境分支很多，新增工具时要同时考虑 `process.env.USER_TYPE`、`bun:bundle` 的 `feature()`、以及权限过滤，不然会出现本地可用、构建后消失的问题。

第三，`AgentTool`、`TeamCreateTool`、`SendMessageTool` 这类工具之间存在循环引用风险，仓库已经用 `require()` 延迟加载规避，改动时不要轻易把它们改回静态 import。第四，`getAllBaseTools()` 的顺序和 cache/prompt 稳定性有关，不能随意重排。第五，测试文件分布很散，改公共工具时要同步检查 `shared/__tests__/`、各工具自己的 `__tests__/`，否则很容易只改实现没改约束。

## 推荐阅读顺序

先看 `packages/builtin-tools/src/index.ts`，建立这个包对外暴露了什么。再看 `src/tools.ts`，理解工具是怎么被组合、过滤和合并的。然后读 `packages/builtin-tools/src/tools/utils.ts`，掌握跨工具通用的数据流辅助。

最后按使用频率挑几个代表性目录深入：`AgentTool/` 看子 agent 体系，`FileEditTool/` 看文件编辑链路，`PowerShellTool/` 看 shell 安全约束，`WorkflowTool/` 看可扩展工作流，`WebFetchTool/` 和 `Task*Tool/` 看模型常用的外部交互与任务状态管理。这样能最快建立这个子系统的整体心智模型。
