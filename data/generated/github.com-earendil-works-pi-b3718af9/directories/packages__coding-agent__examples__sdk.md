# 目录：packages/coding-agent/examples/sdk

## 它负责什么

`packages/coding-agent/examples/sdk` 是 `packages/coding-agent` 包下的 SDK 示例目录，用来展示如何在 TypeScript 代码中直接调用 coding agent 的 SDK 能力，而不是只通过 CLI 或 TUI 使用它。这个目录更像一组“从最小可运行到完整控制”的学习脚本：每个示例文件按编号递进，围绕模型选择、提示词、skills、tools、extensions、上下文文件、模板、认证、设置、会话和运行时控制逐步展开。

根据当前片段推断，这里不是核心实现目录，而是面向使用者和维护者的示例入口。核心 SDK 能力大概率仍在 `packages/coding-agent/src` 中实现；本目录负责把这些能力组织成可读、可运行、便于对照的调用样例。阅读它的价值在于快速理解 coding agent 暴露给外部代码的主要使用面，以及不同配置项如何组合成一次 agent 执行。

该目录目前没有下级子目录，全部内容集中在若干编号 `.ts` 示例和一个 `README.md` 中。编号从 `01` 到 `13`，说明作者希望读者按顺序阅读，而不是把它当成随机示例集合。

## 直接子目录地图

当前片段显示 `packages/coding-agent/examples/sdk` 下没有直接子目录，只有文件。目录结构可以按主题分成几组：

`README.md` 是目录说明和导航入口，通常应先读，用来了解运行方式、示例目标和依赖前提。

`01-minimal.ts`、`02-custom-model.ts`、`03-custom-prompt.ts` 属于基础调用组，覆盖最小 SDK 调用、指定模型、定制提示词这些最常见入口。

`04-skills.ts`、`05-tools.ts`、`06-extensions.ts` 属于能力扩展组，展示 agent 如何加载或接入额外能力。这里的重点不是业务逻辑，而是 SDK 如何表达“可用能力”的边界。

`07-context-files.ts`、`08-prompt-templates.ts` 属于上下文与提示词组织组，关注如何把文件、模板和输入拼成更稳定的任务上下文。

`09-api-keys-and-oauth.ts`、`10-settings.ts` 属于运行配置组，展示认证信息、OAuth、设置项等环境相关配置如何传给 SDK。

`11-sessions.ts`、`12-full-control.ts`、`13-session-runtime.ts` 属于会话与高级控制组，重点是 agent 多轮状态、会话生命周期，以及更底层的运行时控制方式。

## 关键入口

第一入口是 `packages/coding-agent/examples/sdk/README.md`。在没有展开源码内容的情况下，应把它视为示例目录的索引：它通常会说明如何运行这些 `.ts` 文件、需要哪些环境变量、示例之间的阅读顺序，以及 SDK 示例与包内源码的关系。

最小代码入口是 `packages/coding-agent/examples/sdk/01-minimal.ts`。它大概率展示 SDK 的最短调用路径：创建或调用 agent、传入一个 prompt、等待返回结果。学习时应先确认这里使用的导入符号、初始化方式和返回结果结构，因为后续示例通常都在这个基础上增加配置。

配置入口包括 `02-custom-model.ts`、`03-custom-prompt.ts`、`10-settings.ts`。它们分别对应模型选择、提示词定制和更通用的设置注入。理解这些文件有助于分清哪些参数属于“单次请求级别”，哪些属于“agent 或 session 级别”。

扩展能力入口包括 `04-skills.ts`、`05-tools.ts`、`06-extensions.ts`。这三个文件是理解 SDK 可扩展性的关键。根据文件名推断，`skills` 更偏向预定义能力包或工作流说明，`tools` 更偏向可被模型调用的函数能力，`extensions` 更偏向插件式或宿主侧扩展机制。

高级入口是 `12-full-control.ts` 和 `13-session-runtime.ts`。如果要理解 SDK 的完整生命周期、事件处理、流式输出、会话运行时或手动控制边界，应重点看这两个文件。`11-sessions.ts` 则是进入这部分之前的过渡示例。

## 主流程位置

本目录的主流程不是一个单一应用入口，而是分散在编号示例中的多条 SDK 调用流程。整体主线可以理解为：

先从 `01-minimal.ts` 进入，观察一次最小 agent 执行需要哪些输入，以及 SDK 返回什么结果。这里是“主流程骨架”。

然后看 `02-custom-model.ts` 和 `03-custom-prompt.ts`，理解同一条执行流程如何通过模型和 prompt 改变行为。它们通常不会改变主流程形态，只是在初始化参数或请求参数上增加字段。

再进入 `04-skills.ts`、`05-tools.ts`、`06-extensions.ts`，主流程会从“单纯发送 prompt”扩展为“带能力上下文的 agent 执行”。这里应重点找能力注册、能力传入、模型调用能力、宿主处理能力调用结果这些位置。根据当前片段推断，真正的工具调用协议和扩展执行实现不在本目录，而在 `packages/coding-agent/src` 中；示例只展示接线方式。

随后看 `07-context-files.ts` 和 `08-prompt-templates.ts`，主流程关注点转向输入构造：如何把文件内容或模板变量加入任务。这部分通常决定 agent 看到的上下文质量，也是 SDK 实际落地时最容易出错的地方。

最后看 `11-sessions.ts`、`12-full-control.ts`、`13-session-runtime.ts`，主流程从“一次性调用”转为“会话化运行”。这里应关注 session 的创建、恢复、消息追加、运行、终止，以及 runtime 是否暴露事件、状态或中断控制。`12-full-control.ts` 很可能是最完整的流程示例，适合用来反查前面各示例的能力如何组合。

## 推荐阅读顺序

建议先读 `README.md`，确认示例运行方式和前置条件。不要直接从高级文件开始，否则容易把 SDK 的核心调用和示例里的演示配置混在一起。

接着按编号读 `01-minimal.ts`、`02-custom-model.ts`、`03-custom-prompt.ts`。这一段只关注最基本的 SDK 调用形态：导入什么、构造什么、传入什么、返回什么。

然后读 `04-skills.ts`、`05-tools.ts`、`06-extensions.ts`。这一步的目标是建立“agent 能力从哪里来”的地图，而不是记住每个示例的细节。读的时候可以把三者对比：`skills` 是能力说明或能力包，`tools` 是可调用函数，`extensions` 是更宽的扩展接口。具体边界应以源码内容为准；这里根据文件名和目录语义推断。

之后读 `07-context-files.ts` 和 `08-prompt-templates.ts`。它们适合放在能力扩展之后，因为真实任务往往不是单句 prompt，而是由文件、模板、参数和用户输入共同组成上下文。

再读 `09-api-keys-and-oauth.ts`、`10-settings.ts`。认证和设置通常受运行环境影响，适合在理解 SDK 主体后再看，避免一开始被环境变量、OAuth 或配置细节分散注意力。

最后读 `11-sessions.ts`、`12-full-control.ts`、`13-session-runtime.ts`。这部分用于理解长期会话和更细粒度控制。若只想快速调用 SDK，可以暂时停在 `03-custom-prompt.ts` 或 `05-tools.ts`；若要把 SDK 嵌入自己的产品或服务，则必须继续读到 `13-session-runtime.ts`。

## 常见误区

第一个误区是把这个目录当成 SDK 实现。`packages/coding-agent/examples/sdk` 从路径和文件命名看是示例层，不是核心库层。真正的类型定义、执行器、会话管理、工具协议和模型适配实现，应继续去 `packages/coding-agent/src` 查找。

第二个误区是跳过 `01-minimal.ts` 直接看 `12-full-control.ts`。高级示例会把多个概念叠在一起：模型、prompt、tools、settings、session、runtime 都可能同时出现。没有最小示例作参照，很难判断某段代码是必需流程还是演示性配置。

第三个误区是把 `skills`、`tools`、`extensions` 混为一谈。根据当前片段推断，它们代表三类不同扩展面：`04-skills.ts` 更偏能力包或行为指导，`05-tools.ts` 更偏模型可请求执行的宿主函数，`06-extensions.ts` 更偏系统级扩展机制。实际边界要以对应示例和 `src` 中类型为准。

第四个误区是忽略认证和设置示例。`09-api-keys-and-oauth.ts`、`10-settings.ts` 看起来不像主业务流程，但它们决定 SDK 在真实环境中如何拿到模型凭据、如何应用用户配置、如何避免把示例中的默认值误用到生产环境。

第五个误区是认为 session 只是“多轮聊天记录”。`11-sessions.ts`、`13-session-runtime.ts` 的存在说明会话很可能还涉及运行状态、上下文复用、事件流或恢复机制。把它只理解成消息数组，会低估 SDK 在长任务、交互式任务和可中断任务里的设计复杂度。
