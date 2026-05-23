# 目录：packages/builtin-agents/src/agents/page-agent

## 它负责什么

`packages/builtin-agents/src/agents/page-agent` 是 `packages/builtin-agents` 包内的一个内置 Agent 定义目录，目标对象是“页面编辑/页面协作”场景。它不像 `packages/builtin-tool-page-agent` 那样实现具体工具执行、Inspector、Render 或 Streaming UI，而更像是给运行时注册一个可被选择、可被调用的“Page Agent”人格与能力边界。

从当前可见结构看，这个目录非常小，只包含 `index.ts`、`systemRole.ts`、`README.md` 三个入口性文件。根据当前片段推断，它的核心职责是：声明 Page Agent 的元信息、导出系统提示词，并把这些内容交给 `builtin-agents` 的统一注册体系使用。真正负责页面内容读取、标题修改、节点修改、文本替换、初始化页面等工具能力的位置，不在本目录，而在相邻包 `packages/builtin-tool-page-agent`。

因此，学习这个目录时要把它理解为“Agent 定义层”，而不是“工具实现层”或“页面编辑器实现层”。它告诉系统这个 Agent 是什么、应该如何思考和行动；但它通常不直接处理页面 AST、编辑命令、UI 渲染或工具调用结果。

## 直接子目录地图

当前目标目录下没有直接子目录，只有少量文件：

`packages/builtin-agents/src/agents/page-agent/index.ts`：Page Agent 的主要导出入口。根据目录命名和仓库同类结构推断，这里应负责组装并导出 Agent 配置，例如标识、名称、描述、系统角色、可能的默认能力声明等。上层注册表通常会从各个 `agents/*/index.ts` 聚合这些内置 Agent。

`packages/builtin-agents/src/agents/page-agent/systemRole.ts`：Page Agent 的系统角色提示词位置。这里通常承载 Agent 的行为约束、任务目标、工作方式和边界说明。对于源码学习来说，它是理解“这个 Agent 为什么这样调用工具、为什么这样组织输出”的第一手材料。

`packages/builtin-agents/src/agents/page-agent/README.md`：面向开发者或维护者的说明文档。根据当前片段推断，它可能描述 Page Agent 的用途、能力范围、设计意图或调试方式。由于本任务要求只做地图式概览，README 更适合作为阅读导引，而不是逐段拆解对象。

邻近但不属于本目录的关键实现是 `packages/builtin-tool-page-agent`。该包下可见 `src/manifest.ts`、`src/types.ts`、`src/systemRole.ts`、`src/executor/index.ts`，以及 `src/client/Inspector`、`src/client/Render`、`src/client/Placeholder`、`src/client/Streaming` 等目录。它们说明 Page Agent 相关能力被拆成了 Agent 定义和工具实现两个层次：本目录定义“谁在工作”，工具包定义“能做什么”和“结果如何展示”。

## 关键入口

本目录的关键入口优先看 `index.ts`。它大概率是整个 `page-agent` 目录对外唯一稳定入口，也是上层 `builtin-agents` 聚合时最可能引用的文件。阅读时重点关注它导出了什么对象、使用了哪些标识、是否引入 `systemRole`，以及是否绑定了与 Page Agent 相关的工具或能力集合。

第二个入口是 `systemRole.ts`。在 Agent 架构中，系统提示词往往比普通配置更能解释主流程：它会规定 Agent 的职责边界，例如是否专注页面内容生成、是否允许修改页面结构、是否需要先读取页面上下文、遇到不确定信息时如何处理等。即使不看工具实现，也能从这里把握 Page Agent 的行为预期。

第三个入口是 `README.md`。它不是运行时入口，但对学习者很重要。README 一般承接设计解释，适合帮助你确认 `index.ts` 和 `systemRole.ts` 中的配置为什么这样组织。

如果要继续追踪运行时接入点，可以转到 `packages/builtin-agents/src` 的上层聚合文件，根据当前片段推断那里会统一收集 `agents/*`。如果要追踪工具接入点，则看 `packages/builtin-tool-page-agent/src/index.ts` 和 `packages/builtin-tool-page-agent/src/manifest.ts`；如果要看应用侧执行器注册，可关注 `src/store/tool/slices/builtin/executors/lobe-page-agent.ts`。

## 主流程位置

从职责分层看，Page Agent 的主流程可以分成三段。

第一段是 Agent 注册流程，主位置在 `packages/builtin-agents/src/agents/page-agent/index.ts`，再向上进入 `packages/builtin-agents/src` 的聚合导出。这里解决“系统里有没有这个 Agent、它叫什么、默认提示词是什么”的问题。本目录主要参与这一段。

第二段是系统角色注入流程，主位置在 `packages/builtin-agents/src/agents/page-agent/systemRole.ts`。当用户选择或触发 Page Agent 时，运行时会把该系统角色作为模型上下文的一部分，使模型按页面编辑助手的身份行动。根据当前片段推断，这里是影响 Agent 行为最直接的位置。

第三段是工具调用和前端呈现流程，主位置不在本目录，而在 `packages/builtin-tool-page-agent`。可见的工具包结构显示了几类核心能力：`executor/index.ts` 负责服务端或运行时执行逻辑；`manifest.ts` 负责工具清单；`types.ts` 负责参数和状态类型；`client/Inspector` 负责工具调用详情检查；`client/Render` 负责结果渲染；`client/Placeholder` 和 `client/Streaming` 负责调用过程中的占位和流式展示。具体页面动作可从 `client/Inspector/GetPageContent`、`EditTitle`、`ModifyNodes`、`InitPage`、`ReplaceText` 这些目录名看出，Page Agent 可能围绕读取页面内容、编辑标题、修改节点、初始化页面和替换文本展开。

所以，本目录的“主流程位置”不是执行链末端，而是启动链前端：它定义 Page Agent 的身份和提示词，后续执行能力由工具包和应用侧工具注册承接。

## 推荐阅读顺序

建议先读 `packages/builtin-agents/src/agents/page-agent/README.md`，先建立概念：这个 Agent 面向什么使用场景、与普通聊天 Agent 有什么区别。

然后读 `packages/builtin-agents/src/agents/page-agent/index.ts`，确认它对外暴露的配置形态。重点看导出对象的字段、标识命名、是否引用 `systemRole`，以及是否与某些工具标识产生绑定关系。

第三步读 `packages/builtin-agents/src/agents/page-agent/systemRole.ts`。这里适合细看，因为系统角色会直接影响模型行为。阅读时可以把提示词拆成“目标”“上下文获取”“编辑策略”“限制条件”“输出规范”几类来理解。

第四步跳到邻近工具包 `packages/builtin-tool-page-agent/src/manifest.ts` 和 `packages/builtin-tool-page-agent/src/types.ts`，建立 Agent 可用动作的能力表。再看 `packages/builtin-tool-page-agent/src/executor/index.ts`，理解工具请求如何落到实际执行逻辑。

最后再看 UI 侧目录 `packages/builtin-tool-page-agent/src/client/Inspector`、`packages/builtin-tool-page-agent/src/client/Render`、`packages/builtin-tool-page-agent/src/client/Streaming`。这一步用于理解用户在聊天界面中看到的工具调用过程和结果，而不是理解 Agent 定义本身。

## 常见误区

一个常见误区是把 `packages/builtin-agents/src/agents/page-agent` 当成页面编辑功能的完整实现。实际上，根据当前目录片段，它只有 Agent 定义文件；具体工具能力位于 `packages/builtin-tool-page-agent`，应用侧执行器还涉及 `src/store/tool/slices/builtin/executors/lobe-page-agent.ts`。

第二个误区是只看 `systemRole.ts` 就认为已经掌握全部流程。系统提示词能解释 Agent 行为倾向，但不能解释工具参数、执行状态、前端展示和错误处理。要理解完整链路，仍需要跨到工具包和注册位置。

第三个误区是把 `packages/builtin-agents` 和 `packages/builtin-tool-*` 混为一层。前者偏“角色/助手定义”，后者偏“能力/工具实现”。Page Agent 这个场景尤其容易混淆，因为目录名都带有 `page-agent`。

第四个误区是从 UI 组件倒推 Agent 设计。`client/Inspector`、`client/Render` 这些目录主要服务工具调用可视化，它们能展示工具结果，但不一定代表 Agent 的决策逻辑。真正的决策边界仍应回到本目录的 `systemRole.ts` 和上层 Agent 配置。

第五个误区是忽略上层聚合注册。单独看 `page-agent/index.ts` 只能知道它如何定义自己；要知道它什么时候可用、如何被列表发现、如何被运行时加载，还需要查看 `packages/builtin-agents/src` 中的统一导出或注册结构。根据当前片段推断，本目录通过这种聚合机制进入内置 Agent 列表。
