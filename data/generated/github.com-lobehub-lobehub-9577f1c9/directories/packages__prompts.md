# 目录：packages/prompts

## 它负责什么

`packages/prompts` 是 monorepo 内部包 `@lobechat/prompts`，定位是“提示词与上下文文本渲染层”。它把 LobeHub 各业务模块需要喂给模型的 system prompt、chain prompt、上下文片段、工具结果格式化文本、Agent 管理相关提示词等集中维护，并通过 `src/index.ts` 统一导出。

从 `package.json` 看，这个包是 `private: true`，入口是 `./src/index.ts`，说明它不是独立发布给外部使用的 SDK，而是工作区内部共享依赖。外部调用通常通过 `import { ... } from '@lobechat/prompts'` 完成。调用方分布很广，包括 `packages/context-engine`、多个 `packages/builtin-tool-*`、`src/store/chat`、`src/server/services/*`、`src/features/*` 等。

它不负责真正调用模型、不负责状态管理、不负责数据库读写，也不负责工具执行。它主要做两件事：第一，提供稳定的 prompt 模板、格式化函数和类型；第二，把不同业务域的模型输入文本收敛到一个可复用边界里，避免在 store、server service、tool runtime、context-engine 中散落大量模型面向文本。

## 直接子目录地图

`packages/prompts` 根部主要是包配置与测试配置：`package.json` 定义包名、入口和测试脚本；`vitest.config.mts` 是本包测试配置；`README.md` 提供包说明；`.gitignore` 管理本目录忽略项。

核心代码在 `packages/prompts/src`。根据当前片段，`src` 下有四个一级业务子目录：

`packages/prompts/src/agents` 放 Agent 相关的提示词组装与上下文格式化。已看到的文件包括 `agentSkillManager.ts`、`pageContentContext.ts`、`pageSelectionContext.ts` 和 `index.ts`。它更靠近“Agent/页面上下文输入如何表达”的层面，例如页面内容、页面选区、技能管理上下文等。

`packages/prompts/src/chains` 放面向链式任务的 prompt 构造函数。典型文件包括 `summaryTitle.ts`、`summaryHistory.ts`、`compressContext.ts`、`translate.ts`、`langDetect.ts`、`answerWithContext.ts`、`inputCompletion.ts`、`rewriteGenerationPrompt.ts`、`taskTopicHandoff.ts` 等。这里的“chain”更像模型子任务模板：总结标题、压缩上下文、翻译、语言检测、基于上下文回答、输入补全等。

`packages/prompts/src/contexts` 放上下文块的生成与格式化。根据索引导出可见，它覆盖 `supervisor`、`agentBuilder`、`agentGroup`、`botPlatformContext`、`chatMessages`、`discordContext`、`files`、`fileSystem`、`groupChat`、`knowledgeBaseQA`、`messagesToText`、`planTodo`、`plugin`、`remoteDevice`、`search`、`skills`、`speaker`、`systemRole`、`task`、`toolDiscovery`、`userMemory` 等主题。这个目录是上下文工程的主要文本组件库。

`packages/prompts/src/prompts` 放更底层、可组合的 prompt 模板集合。它被 `src/chains/*` 和 `src/contexts/*` 引用，例如 `summaryHistory.ts` 会引用 `chatHistoryPrompts`，`compressContext.ts` 会引用压缩相关模板，`contexts/supervisor/makeDecision.ts` 会引用 `groupChatPrompts`、`groupSupervisorPrompts`。根据当前片段推断，`src/prompts` 是“原始模板/模板集合”，而 `src/chains`、`src/contexts` 是“面向具体任务的组合与格式化”。

## 关键入口

第一入口是 `packages/prompts/package.json`。它声明包名为 `@lobechat/prompts`，主入口为 `./src/index.ts`，所以工作区其他包会通过这个别名消费本包能力。

第二入口是 `packages/prompts/src/index.ts`。它统一导出 `./agents`、`./chains`、`./contexts`、`./prompts`。这意味着外部模块通常不需要知道内部目录结构，直接从 `@lobechat/prompts` 取 `chainSummaryTitle`、`chainCompressContext`、`pluginPrompts`、`filesPrompts`、`formatPageContentContext` 等能力。

第三组入口是各子域的 `index.ts`：`packages/prompts/src/agents/index.ts`、`packages/prompts/src/chains/index.ts`、`packages/prompts/src/contexts/index.ts`、`packages/prompts/src/prompts/index.ts`。它们分别维护本域对外 API。读代码时要特别关注这些索引文件，因为它们能告诉你哪些 prompt 已经被视为公共接口，哪些只是目录内部实现。

测试入口主要是 `packages/prompts/src/index.test.ts` 和局部测试，例如 `packages/prompts/src/agents/pageContentContext.test.ts`。本包测试脚本在 `package.json` 中是 `vitest`、`vitest --coverage --silent='passed-only'`、`vitest -u`。

## 主流程位置

主流程可以理解为三段：模板定义、任务组合、外部消费。

模板定义集中在 `packages/prompts/src/prompts`。这里保存可复用的 prompt 文本、模板片段或模板函数。它是更靠近“模型该看到什么原始话术”的层。

任务组合集中在 `packages/prompts/src/chains` 和 `packages/prompts/src/contexts`。`chains` 面向明确的模型子任务，例如标题总结、历史压缩、翻译、语言检测、RAG 回答等；`contexts` 面向上下文注入和工具/环境/用户信息表达，例如文件、知识库、插件、技能、任务、群聊、设备、用户记忆等。根据当前片段推断，`chains` 更常产出一组可直接交给模型的消息或 prompt，`contexts` 更常产出被拼入 system role、上下文工程或工具结果中的文本块。

外部消费分布在几个关键位置。`packages/context-engine/src/providers/*` 大量导入 `@lobechat/prompts`，说明上下文工程会使用这里的格式化函数把文件、页面、知识库、工具、群聊、技能、用户记忆等注入对话上下文。`src/store/chat/*` 会使用 `chainCompressContext`、`chainSummaryHistory`、`chainSummaryTitle`、`chainLangDetect`、`chainTranslate` 等，说明聊天状态层会在会话生命周期、标题生成、翻译等操作中引用本包。`src/server/services/*` 会使用任务、Agent Signal、bot、tool execution 相关 prompt，说明服务端异步任务和自动化 Agent 流程也依赖这里。多个 `packages/builtin-tool-*` 会引用格式化函数，例如知识库、网页浏览、远程设备、任务、技能、本地系统工具等，把工具执行结果转成模型可读文本。

整体流程是：业务模块从 `@lobechat/prompts` 导入某个 chain/context/prompt 函数，传入业务数据，得到模型输入文本或消息结构，再交给 runtime、store action、server service 或 context-engine 继续执行。`packages/prompts` 本身停在“渲染模型输入”的边界，不跨进执行层。

## 推荐阅读顺序

第一步读 `packages/prompts/package.json` 和 `packages/prompts/src/index.ts`，先确认包入口、导出边界和公共 API 范围。

第二步读四个子目录的索引：`packages/prompts/src/prompts/index.ts`、`packages/prompts/src/chains/index.ts`、`packages/prompts/src/contexts/index.ts`、`packages/prompts/src/agents/index.ts`。这比从叶子文件开始读更高效，因为这里能看到本包按领域暴露了哪些能力。

第三步从高频 chain 开始：`packages/prompts/src/chains/compressContext.ts`、`packages/prompts/src/chains/summaryHistory.ts`、`packages/prompts/src/chains/summaryTitle.ts`、`packages/prompts/src/chains/translate.ts`、`packages/prompts/src/chains/langDetect.ts`。这些和聊天主流程、上下文压缩、标题生成、翻译等功能关系更直接。

第四步读上下文工程相关模块：`packages/prompts/src/contexts/files`、`packages/prompts/src/contexts/plugin`、`packages/prompts/src/contexts/skills`、`packages/prompts/src/contexts/task`、`packages/prompts/src/contexts/userMemory`、`packages/prompts/src/contexts/groupChat`。建议结合调用方 `packages/context-engine/src/providers/*` 一起看，才能理解这些文本片段什么时候被注入。

第五步再看 Agent 和自动化相关：`packages/prompts/src/agents/*` 以及 `packages/prompts/src/chains/agentSignal/*`。这些更偏高级 Agent 能力，适合在理解基础 prompt 与 context 之后阅读。

## 常见误区

不要把 `packages/prompts` 理解成模型运行时。它不发起 LLM 请求，也不决定 provider、模型、流式响应或 token 预算策略；这些通常在 runtime、store、server service、context-engine 等层处理。

不要把 `src/prompts`、`src/chains`、`src/contexts` 混为一谈。`src/prompts` 更像模板原料；`src/chains` 是面向模型子任务的 prompt 组合；`src/contexts` 是面向上下文注入和工具结果表达的格式化层。虽然它们都会产出文本，但职责边界不同。

不要在业务层重复拼接相同模型话术。已有公共能力应从 `@lobechat/prompts` 引用，例如工具结果、文件内容、知识库搜索结果、用户记忆、任务列表、标题总结等。否则容易造成不同入口的模型行为不一致。

不要忽视转义与结构化边界。调用方中可以看到 `escapeXml`、`escapeXmlAttr` 等函数来自本包，说明很多 prompt 采用 XML-like 标签组织上下文。新增模板时如果直接插入用户内容、文件名、工具结果或网页内容，必须考虑转义，否则可能破坏 prompt 结构。

不要把这里的文本当 UI 文案处理。它们主要面向模型，不是普通界面文案；是否走 `react-i18next`、是否进入 `src/locales`，要看它是否展示给用户，而不是只看它是不是自然语言。

不要只读本包内部而不看调用方。`packages/prompts` 的价值在“被谁消费、进入哪条模型链路”。理解某个 prompt 的真实作用时，应同时看 `packages/context-engine/src/providers/*`、`src/store/chat/*`、`src/server/services/*` 或对应 `packages/builtin-tool-*` 调用点。
