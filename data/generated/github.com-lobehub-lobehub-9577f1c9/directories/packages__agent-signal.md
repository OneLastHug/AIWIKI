# 目录：packages/agent-signal

## 它负责什么

`packages/agent-signal` 按命名和项目内 `agent-signal` skill 的说明来看，是 LobeHub Agent Signal 体系的共享语义核心包，主要负责定义“后台 agent 信号流水线”的通用模型、类型与构建工具。这个体系的抽象链路是 `source event -> signal interpretation -> action execution -> built-in result signals`：外部或运行时先产生一个 `source`，运行时把它解释成一个或多个语义化 `signal`，再由策略或处理器规划并执行具体 `action`，最后形成内置的结果信号、执行状态和可观测事件。

需要说明的是：在当前可读片段中，目标路径 `packages/agent-signal` 没有被 `find` 读取到，`packages`、`src`、根 `package.json` 也没有在当前 shell 视图中出现。因此以下文档是“根据当前片段推断”，依据主要来自仓库提供的 `agent-signal` skill，其中明确把 `packages/agent-signal/src/index.ts`、`packages/agent-signal/src/base/builders.ts`、`packages/agent-signal/src/base/types.ts`列为共享语义核心阅读入口。也就是说，本目录更像底层 SDK/协议层，而不是完整业务运行时。

## 直接子目录地图

根据当前片段推断，`packages/agent-signal` 的目录规模应该较小，核心集中在 `src` 下。

`packages/agent-signal/src` 是包的源码根目录，承担对外导出与内部基础模型组织。它应该暴露给服务端运行时、策略实现、测试或评估代码使用。

`packages/agent-signal/src/base` 是最关键的基础层，skill 明确提到其中的 `builders.ts` 和 `types.ts`。`types.ts` 应该定义 `source`、`signal`、`action`、处理结果、节点标识、上下文载荷等类型契约；`builders.ts` 则提供标准化构造函数，避免调用方手写结构体时出现字段缺失、命名不一致或结果格式漂移。

如果目录中还存在测试、构建配置或包元数据，它们的角色应服务于这个共享包的发布与类型校验，而不是承载具体业务策略。具体业务策略在 skill 中指向 `src/server/services/agentSignal/policies/**`，不属于该 package 的主要职责。

## 关键入口

最重要的入口是 `packages/agent-signal/src/index.ts`。它应当是 `@lobechat/agent-signal` 的公开导出面，服务端运行时和策略代码通常从这里导入共享类型、builder 或常量。阅读这个文件可以快速判断该包对外承诺了哪些 API，以及哪些内部实现没有暴露出去。

第二个入口是 `packages/agent-signal/src/base/types.ts`。Agent Signal 的边界非常依赖类型：什么时候应该新增 `source`，什么时候应该新增 `signal`，什么时候应该新增 `action`，都需要由类型系统把概念固定下来。这个文件通常能帮助读者理解“信号节点长什么样”“执行结果如何表达”“handler 之间传递什么结构”。

第三个入口是 `packages/agent-signal/src/base/builders.ts`。这个文件的意义不只是减少重复代码，更重要的是统一节点构造规范。Agent Signal 这类后台流水线很容易跨越多个服务、worker、策略和观测模块，如果每个调用方自行拼装对象，后续做去重、追踪、scope 串行化、结果投影都会变得脆弱。

## 主流程位置

主流程本身不在 `packages/agent-signal` 内完整闭环。根据当前片段推断，这个 package 只提供“语言”和“工具”，真正运行流水线的位置在服务端目录。

同步或受控执行入口在 `src/server/services/agentSignal/index.ts`，其中会出现类似 `emitAgentSignalSourceEvent(...)`、`executeAgentSignalSourceEvent(...)`、`emitAgentSignalSourceEventWithStore(...)` 的接口。它们决定 source event 是立即执行、由已有 worker 控制执行，还是在隔离 store 中测试执行。

异步后台执行入口在 `src/server/workflows/agentSignal/index.ts` 和 `src/server/workflows/agentSignal/run.ts`。当调用方使用 `enqueueAgentSignalSourceEvent(...)` 时，请求路径可以快速返回，后续由 Upstash Workflow 或类似工作流机制在后台处理。

运行时核心在 `src/server/services/agentSignal/runtime/AgentSignalRuntime.ts`、`src/server/services/agentSignal/runtime/AgentSignalScheduler.ts`、`src/server/services/agentSignal/runtime/middleware.ts`、`src/server/services/agentSignal/runtime/context.ts`。这些位置负责调度 handler、维护上下文、执行中间件、处理 scope 串行化和 runtime guard。`packages/agent-signal` 中定义的类型和 builder 会被这些运行时代码消费。

策略样例在 `src/server/services/agentSignal/policies/analyzeIntent/index.ts` 及其相邻文件，例如 `feedbackSatisfaction.ts`、`feedbackDomain.ts`、`feedbackAction.ts`、`actions/userMemory.ts`。如果想看 `source -> signal -> action` 如何落地，这些策略文件比共享包更接近真实业务流程。

## 推荐阅读顺序

第一步读 `packages/agent-signal/src/index.ts`，先确认这个包公开了哪些能力。重点看导出的类型、builder、常量或 helper，而不是急着追内部细节。

第二步读 `packages/agent-signal/src/base/types.ts`，建立核心概念：`source` 是外部事实，`signal` 是语义解释，`action` 是具体副作用，`policy` 是把 source handler、signal handler、action handler 组织起来的中间件包。这里要特别注意 `procedure` 不是独立运行时节点，而是一个用例的端到端流程描述。

第三步读 `packages/agent-signal/src/base/builders.ts`，理解系统希望调用方怎样创建标准节点和结果。读 builder 时可以反向回到类型文件，看哪些字段是运行时强依赖，例如稳定 id、idempotency key、scopeKey、result contract 等。

第四步跳到 `src/server/services/agentSignal/runtime/AgentSignalRuntime.ts` 和 `AgentSignalScheduler.ts`，看共享模型如何被真正调度。这个阶段再理解 `scopeKey`、队列、middleware、runtime guard 会更自然。

第五步读 `src/server/services/agentSignal/policies/analyzeIntent/**`，用一个现成策略把抽象串起来。最后再看 `src/server/workflows/agentSignal/run.ts`，理解异步工作流如何接入。

## 常见误区

第一个误区是把 `packages/agent-signal` 当成完整业务实现目录。它更可能是共享包，负责定义协议、类型和构造方式；业务 handler、policy 注册、运行时调度在 `src/server/services/agentSignal/**`，异步工作流在 `src/server/workflows/agentSignal/**`。

第二个误区是混淆 `source`、`signal` 和 `action`。新增外部事件时应新增或复用 `source`；需要表达可复用语义时才新增 `signal`；需要执行副作用时才新增 `action`。如果把重副作用写进 source handler，后续会破坏流水线的可组合性和可观测性。

第三个误区是把 `procedure` 理解成一种新的节点类型。根据当前片段，`procedure` 只是端到端用例的说法，不是运行时图里的独立节点。真正被 runtime 调度的是 source、signal、action 以及它们对应的 handler。

第四个误区是绕过共享 builders 直接手写对象。Agent Signal 的后台执行涉及去重、追踪、workflow handoff、结果投影和测试隔离，结构不统一会让这些能力变得难以维护。应优先从 `@lobechat/agent-signal` 复用公开类型和构造函数。

第五个误区是忽视 scope 和幂等。后台 source 可能重复到达，同一会话或同一资源的信号也可能并发触发。实现 action handler 时应考虑 stable id、idempotency key 和 `scopeKey`，否则容易出现重复执行、顺序错乱或难以复盘的问题。
