# 目录：src/server/services/agentSignal/procedure

## 它负责什么

`src/server/services/agentSignal/procedure` 从命名和 `agent-signal` 技能说明来看，属于 Agent Signal 服务里的“用例流程层”。它不是 `source`、`signal`、`action` 之外的第四种运行时节点，而更像把一次端到端业务过程组织起来的目录：从某个入口事件进入，经过 source handler 解释，生成 signal，再由 policy 匹配出 action，最后交给 action handler 执行副作用，并产出内置结果信号或观测事件。

根据当前片段推断，这个目录的主要价值不是定义底层队列、调度器或共享模型，而是沉淀“某类 Agent Signal 任务该如何跑”的流程组合。也就是说，读这里时应把它理解成业务流程地图，而不是运行时内核。底层抽象应继续看 `packages/agent-signal`，服务端运行时应看 `src/server/services/agentSignal/runtime`，策略和处理器应看 `src/server/services/agentSignal/policies`。

这个目录和 `source`、`policies`、`runtime` 的关系大致是：`procedure` 负责描述或封装某个场景的主路径；`sourceTypes.ts` 负责规范“外部事实”；`policies` 负责把事实解释成语义和动作；`runtime` 负责调度、作用域、队列执行、幂等和中间件；`observability` 负责把过程投影成可追踪事件。

## 直接子目录地图

由于当前可用片段未能完整枚举 `src/server/services/agentSignal/procedure` 的真实文件树，下面是基于 Agent Signal 架构约定的地图式阅读方式，而不是逐叶子文件解释。

如果目录下按业务场景拆分子目录，通常每个子目录应代表一条 procedure：例如某类用户输入、运行时事件、后台分析、记忆写入、反馈理解或跨系统入口。每个子目录的职责应是承接一个“源事件到动作结果”的业务闭环，而不是重新实现公共 runtime。

如果目录下存在共享文件，如 `index.ts`、`types.ts`、`utils.ts`、`context.ts` 之类，则它们大概率承担 procedure 层的统一导出、流程参数类型、上下文拼装或小型辅助函数。判断标准是：只要代码开始处理队列、scope 串行化、handler 注册、middleware 执行，就应回到 `runtime` 或 `policies` 查找真正来源，不要把它们误认为 procedure 自己的核心机制。

如果目录下没有很多子目录，而是少量入口文件，则说明这里可能只是把现有 policy 组合成更高层的业务 API。此时重点看导出的函数名，以及它们调用的是 `emitAgentSignalSourceEvent(...)`、`executeAgentSignalSourceEvent(...)` 还是 `enqueueAgentSignalSourceEvent(...)`。

## 关键入口

理解这个目录前，建议先明确 Agent Signal 的几个真正入口。`src/server/services/agentSignal/index.ts` 是服务端调用方最可能接触到的门面入口，通常会暴露同步触发、受控执行、异步入队等函数。`src/server/workflows/agentSignal/index.ts` 和 `src/server/workflows/agentSignal/run.ts` 则是后台工作流入口，用于把事件交给 Upstash Workflow 一类的异步执行环境。

在 procedure 目录内部，关键入口一般有两类。第一类是目录级 `index.ts`，它负责把具体流程导出给上层服务或 workflow。第二类是以业务流程命名的函数，例如 `runXxxProcedure`、`executeXxxProcedure`、`enqueueXxxProcedure` 或类似命名。阅读时不必从所有处理器开始，而应先找这些导出函数，看它们把什么 source event 交给 runtime。

入口函数里最关键的分歧是执行时机：`emitAgentSignalSourceEvent(...)` 表示调用方希望立即执行 Agent Signal 管线；`executeAgentSignalSourceEvent(...)` 表示当前路径已经拥有执行控制权，可能会注入 runtime guard；`enqueueAgentSignalSourceEvent(...)` 表示调用方快速返回，把后续工作交给后台 workflow；`emitAgentSignalSourceEventWithStore(...)` 更偏测试、评测或隔离运行，避免依赖环境中的共享 Redis 状态。

## 主流程位置

主流程应按“事件进入、语义解释、动作执行、结果观测”来定位。

第一步是 ingress，也就是谁创建了 source event。相关类型通常在 `src/server/services/agentSignal/sourceTypes.ts`，调用位置可能在聊天服务、Agent runtime hooks、bot ingress、用户消息处理或后台任务中。procedure 目录如果存在流程封装，它很可能就是这些 ingress 代码和通用 Agent Signal runtime 之间的薄层。

第二步是 handler 匹配。source 被送进 runtime 后，`policies` 中注册的 source handler 会把它解释为 signal。现有示例可参考 `src/server/services/agentSignal/policies/analyzeIntent/index.ts`，以及同目录下的 `feedbackSatisfaction.ts`、`feedbackDomain.ts`、`feedbackAction.ts`、`actions/userMemory.ts`。这些文件体现了一个典型链路：分析意图，识别反馈满意度或领域，再规划具体 action，比如写入用户记忆。

第三步是 action handler 执行副作用。这里才真正发生外部写入、模型调用、记忆更新、任务创建或其他服务调用。procedure 不应承担过多副作用细节；它更适合表达“这一流程会触发哪些 action”，具体执行应在 action handler 中完成，并负责幂等、错误结果和 executor 风格返回。

第四步是 observability。执行过程中的节点、结果、错误和工作流快照，通常会流向 `src/server/services/agentSignal/observability` 以及 `packages/observability-otel/src/modules/agent-signal`。排查 procedure 行为时，除了看业务代码，也要看 trace event 是否能还原一次 source 到 action 的路径。

## 推荐阅读顺序

1. 先读 `src/server/services/agentSignal/index.ts`，确认服务端对外暴露了哪些 Agent Signal 调用方式。
2. 再读 `src/server/services/agentSignal/sourceTypes.ts`，建立 source event 的类型地图，弄清楚有哪些外部事实会进入系统。
3. 然后读 `src/server/services/agentSignal/procedure` 的目录级入口，优先找 `index.ts` 或导出的 `execute*`、`emit*`、`enqueue*` 函数，判断每条流程的触发方式。
4. 接着读 `src/server/services/agentSignal/policies/index.ts`，确认 procedure 依赖哪些 policy，以及这些 policy 注册了哪些 source、signal、action handler。
5. 选择一个现成 policy 样例继续追踪，例如 `src/server/services/agentSignal/policies/analyzeIntent/index.ts`，再顺着相关 signal handler 和 action handler 看完整闭环。
6. 最后读 `src/server/services/agentSignal/runtime/AgentSignalRuntime.ts`、`src/server/services/agentSignal/runtime/AgentSignalScheduler.ts`、`src/server/services/agentSignal/runtime/middleware.ts`，理解 scope、调度、去重和中间件如何保证流程可控。
7. 如果关注后台异步执行，再补读 `src/server/workflows/agentSignal/index.ts` 和 `src/server/workflows/agentSignal/run.ts`。

## 常见误区

第一个误区是把 `procedure` 当成 Agent Signal 的核心运行时。根据当前片段推断，Agent Signal 的核心模型仍然是 `source -> signal -> action`，`procedure` 只是某个用例的端到端组织方式。真正的运行时能力在 `runtime`，共享抽象在 `packages/agent-signal`。

第二个误区是把 source handler 写成重副作用入口。source handler 更适合做解释和 fan-out，把原始事件变成语义信号；具体写数据库、调用模型、更新记忆等工作应放进 action handler，这样才便于幂等、重试和结果追踪。

第三个误区是新增 procedure 时绕过现有 `source`、`signal`、`action` 类型。正确做法是优先复用 `sourceTypes.ts` 和 `policies/types.ts` 里的既有类型，只有当外部事实、语义概念或副作用确实新增时才扩展。

第四个误区是忽略执行方式差异。同步 `emit`、受控 `execute`、异步 `enqueue` 的语义不同：前者适合立即跑完，中者适合由 worker 或后端路径接管执行时机，后者适合安静的后台任务。procedure 的入口设计应明确选择其中一种，而不是随意混用。

第五个误区是只看业务结果，不看 scope 和 observability。Agent Signal 面向后台或安静执行场景，重复事件、并发事件、工作流恢复都可能出现。阅读或改动 procedure 时，应同时确认 `scopeKey`、idempotency key、trace event 和结果信号是否能支撑排障。
