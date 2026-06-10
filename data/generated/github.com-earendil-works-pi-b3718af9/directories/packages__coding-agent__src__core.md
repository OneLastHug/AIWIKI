# 目录：packages/coding-agent/src/core

## 它负责什么

`packages/coding-agent/src/core` 是 `coding-agent` 包的核心运行层，负责把“用户输入、模型调用、工具执行、会话持久化、配置、扩展、压缩、导出”等能力组织成一个可运行的 agent 会话。它不是单纯的工具集合，也不是 UI 层；更准确地说，它位于命令行/TUI 交互层和底层 `pi-ai`、`pi-agent-core`、文件系统、shell 执行之间，承担调度与状态管理职责。

从当前目录片段看，核心对象是 `AgentSession`，位于 `packages/coding-agent/src/core/agent-session.ts`。它聚合模型注册、系统提示词、工具定义、提示模板、会话记录、扩展绑定、bash 执行和 HTML 导出等能力。围绕它还有若干支撑模块：`session-manager.ts` 管会话文件与历史记录，`settings-manager.ts` 管全局/项目设置，`model-registry.ts` 管 provider/model 解析与鉴权配置，`system-prompt.ts` 管系统提示词拼装，`tools/` 提供 agent 可调用的本地工具，`extensions/` 提供外部扩展加载和运行环境。

这个目录的角色可以理解为“agent runtime 的业务内核”：上层负责展示和命令入口，下层负责具体模型 API、TUI 组件或系统调用，而 `core` 把这些能力按一次会话的生命周期串起来。

## 直接子目录地图

`packages/coding-agent/src/core/tools` 是内置工具层。这里能看到 `bash.ts`、`read.ts`、`write.ts`、`edit.ts`、`edit-diff.ts`、`ls.ts`、`grep.ts`、`find.ts`、`truncate.ts`、`path-utils.ts`、`file-mutation-queue.ts` 等文件。它们对应 agent 与本地环境交互的主要能力，包括 shell、读写文件、编辑 diff、搜索、列目录以及输出截断。`tools/index.ts` 很可能是工具注册汇总入口，`tool-definition-wrapper.ts` 用来把内部工具包装成模型/agent 可识别的工具定义。

`packages/coding-agent/src/core/extensions` 是扩展系统。`loader.ts` 负责发现、加载扩展，并创建扩展运行时；`runner.ts` 负责扩展事件或生命周期执行；`types.ts` 定义扩展、工具、命令等协议类型；`wrapper.ts` 和 `index.ts` 提供对外组织。根据 `loader.ts` 中的导入片段推断，这里会为扩展暴露受控 API，并处理虚拟模块、包路径、manifest、目录发现等问题。

`packages/coding-agent/src/core/compaction` 是上下文压缩与分支摘要相关逻辑。`compaction.ts`、`branch-summarization.ts`、`utils.ts`、`index.ts` 表明这里负责把长会话压缩成可继续传给模型的摘要内容，也可能与 `SessionManager` 中的 `CompactionEntry`、`BranchSummaryEntry` 记录联动。

`packages/coding-agent/src/core/export-html` 是会话导出为 HTML 的模块。`index.ts` 提供 `exportSessionToHtml`、`exportFromFile`，`tool-renderer.ts` 提供工具输出渲染，`ansi-to-html.ts` 处理终端 ANSI 样式，`template.html`、`template.css`、`template.js` 和 `vendor/` 下的前端库用于生成可阅读的静态导出页面。

## 关键入口

最重要的入口是 `packages/coding-agent/src/core/agent-session.ts`。它导出 `AgentSession`，并定义 `AgentSessionConfig`、`AgentSessionEvent`、`PromptOptions`、`SessionStats` 等会话级类型。从导入关系看，它会调用 `buildSystemPrompt`、`createAllToolDefinitions`、`executeBashWithOperations`、`exportSessionToHtml`、`expandPromptTemplate`，同时依赖 `ModelRegistry`、`SessionManager`、`SettingsManager`、`ResourceLoader` 等外部服务对象。

`packages/coding-agent/src/core/agent-session-runtime.ts` 和 `packages/coding-agent/src/core/agent-session-services.ts` 从命名上看是 `AgentSession` 的运行时服务组装层。根据当前片段只能推断：它们可能把配置、资源加载、模型注册、会话管理、扩展等依赖装配成可启动的 session runtime，适合从 CLI 或交互模式调用。

`packages/coding-agent/src/core/index.ts` 是目录级导出入口，通常用于让包内其他模块统一引用 core 能力。阅读时应把它当作“对外 API 面”，但真实流程仍要回到 `agent-session.ts`、`session-manager.ts`、`model-registry.ts` 等具体实现。

配置与环境相关入口包括 `settings-manager.ts`、`model-resolver.ts`、`model-registry.ts`、`auth-storage.ts`、`auth-guidance.ts`、`project-trust.ts`、`trust-manager.ts`、`session-cwd.ts`。其中 `model-registry.ts` 文件体量较大，导出 `ModelRegistry`，并包含 provider/model schema、兼容配置、OAuth 注册、API key 缓存等逻辑，是模型侧最核心的入口。

## 主流程位置

一次典型请求的主流程，根据当前片段推断，大致从上层创建 `AgentSession` 开始。创建时会注入或构造 `SettingsManager`、`SessionManager`、`ModelRegistry`、资源加载器、扩展绑定和工具列表。`AgentSession` 会根据当前配置解析模型、构建系统提示词、加载 prompt template 或 skill 信息，然后把用户消息和历史上下文送入模型循环。

模型循环中，工具调用会分发到 `tools/` 下的定义。比如读取文件会走 `read.ts`，写入和编辑会走 `write.ts`、`edit.ts` 或 `edit-diff.ts`，shell 命令会通过 `bash.ts`、`bash-executor.ts` 与 `exec.ts` 等模块执行。工具结果再回填给模型，直到模型产生最终 assistant 输出或需要继续执行下一轮工具调用。

会话状态与恢复流程主要在 `session-manager.ts` 和 `agent-session.ts` 之间。`SessionManager` 负责记录 header、消息、压缩条目、分支摘要等持久化数据；`AgentSession` 负责把这些数据转成当前运行状态。长上下文处理会进入 `compaction/`，导出会进入 `export-html/`。

扩展流程的主位置在 `extensions/loader.ts` 和 `extensions/runner.ts`。根据导入与函数名，扩展先被 discover/load，随后将 slash command、工具、事件处理器或资源能力注册进 session。`agent-session.ts` 中导入了 `emitSessionShutdownEvent`，说明 session 生命周期结束时也会通知扩展。

## 推荐阅读顺序

第一步读 `packages/coding-agent/src/core/index.ts`，了解 core 对外暴露了哪些能力。它适合建立边界感，但不要停留在导出列表。

第二步读 `packages/coding-agent/src/core/agent-session.ts`。重点看 `AgentSessionConfig`、`AgentSession` 构造、用户 prompt 处理、模型循环、工具调用、事件派发、导出和 shutdown 相关逻辑。这是理解整个目录的主干。

第三步读 `packages/coding-agent/src/core/tools/index.ts` 和几个代表性工具：`tools/bash.ts`、`tools/read.ts`、`tools/edit.ts`、`tools/write.ts`。这样可以理解模型工具调用如何落到本地系统操作。

第四步读 `packages/coding-agent/src/core/session-manager.ts`、`settings-manager.ts`、`model-registry.ts`。这三者分别解释“会话怎么存”、“配置怎么来”、“模型怎么选和鉴权怎么处理”。

第五步再读横向能力：`compaction/` 看长会话压缩，`extensions/` 看插件化边界，`export-html/` 看会话导出链路，`prompt-templates.ts`、`skills.ts`、`slash-commands.ts` 看用户输入被扩展和转换的方式。

## 常见误区

不要把 `core/tools` 理解成普通 CLI 命令集合。它们更像 agent tool definitions，设计目标是被模型调用，并且要和会话事件、权限、输出截断、文件变更队列等机制配合。

不要把 `AgentSession` 当作纯数据对象。它是运行时协调者，连接模型、工具、扩展、持久化和提示词构造。理解主流程时应从它入手，而不是从某个单独工具文件入手。

不要认为 `extensions/` 只是加载本地脚本。根据 `loader.ts` 中的函数和导入，它还处理虚拟模块、内置包映射、manifest、extension API、事件总线等运行时隔离与适配问题。

不要跳过 `model-registry.ts`。模型选择并不只是一个字符串配置；这里包含 provider schema、兼容模式、OAuth、API key、模型 override、请求鉴权解析等逻辑。很多“为什么这个模型这样请求”的答案会在这里。

不要把 `compaction/` 看成简单摘要工具。它和会话历史、分支摘要、上下文窗口管理相关，属于长会话可持续运行的关键路径。根据当前片段推断，它不一定每轮都参与，但一旦上下文接近限制，就会影响后续模型输入。
