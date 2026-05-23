# 目录：src/server/services/agentSignal

## 它负责什么

`src/server/services/agentSignal` 是 LobeHub 服务端的 Agent Signal 管线实现目录，负责把“某个事件发生了”转换成可执行的后台智能行为。它的核心模型可以概括为：

`source event` -> `signal interpretation` -> `action execution` -> `result signals / receipts / observability`

这里的 `source` 是外部或运行时产生的事实，例如用户消息、bot 消息合并、agent runtime step、执行完成/失败、夜间 review 触发等；`signal` 是对 source 的语义解释，例如意图、领域、满意度、可处理的过程状态；`action` 是真正产生副作用的执行单元，例如写入用户记忆、维护 skill、生成 self review proposal 等。

这个目录不是单纯的“分类器”或“任务队列”。它更像一套服务端背景智能工作流框架：入口层负责接收并归一化事件，运行时层负责注册 handler、调度 source/signal/action，策略层负责声明某类业务流程如何被处理，存储层负责去重、锁、窗口、过程状态和 receipt，观测层负责把一次运行投影成 trace/telemetry。

从当前片段看，Agent Signal 还承担“自我迭代 / self iteration”相关能力，包括基于反馈分析意图、记忆写入、skill 管理、夜间 review、自反思、工具执行结果回传等。这部分业务主要分布在 `policies/analyzeIntent`、`policies/reviewNightly`、`services/selfIteration` 和 `procedure` 下。

## 直接子目录地图

`__tests__` 放置顶层集成与边界测试，例如 feature gate、orchestrator、prompt boundary、scope key 等，用来验证入口和主流程行为。

`observability` 负责 Agent Signal 的可观测性投影与持久化。关键角色包括 `projector.ts`、`store.ts`、`traceEvents.ts`、`types.ts`，它把 runtime trace、handler run、node edge 等信息整理成可记录、可查询的结构。

`policies` 是业务策略目录。策略把多个 source handler、signal handler、action handler 组合成可安装的 middleware。当前能看到 `analyzeIntent` 和 `reviewNightly` 两类主要策略；其中 `analyzeIntent` 下面还包含 `actions`、`context` 等子目录，承接反馈意图分析、领域判断、skill 管理、用户记忆等流程。

`procedure` 是过程状态和过程产物层。它不等同于 runtime 节点，而是围绕一次端到端业务流程记录 marker、record、receipt、tool outcome、accumulator、batch scorer 等，用于去重、抑制、累积、评分和向消息上下文回填过程结果。

`processors` 放置可复用的处理器函数，连接策略 handler 与业务判断逻辑，例如 action planning、classifier 调用、procedure 转移、runtime result 处理等。它更像策略内部的公共处理算法层。

`runtime` 是 Agent Signal 的运行时核心，包括 `AgentSignalRuntime`、`AgentSignalScheduler`、`middleware`、`context`、`scope`、`guards` 和 `backend`。这里定义 handler 注册机制、调度循环、运行上下文、scope key 解析、debounce/throttle/timeout 等保护逻辑，以及 Redis guard backend。

`services` 是业务服务适配层，封装分类器、action 服务、receipt 服务、procedure state service、自反思、自反馈意图、self iteration 执行、review brief、工具集等。策略通常不直接散落访问底层资源，而是通过这里的 service 或 adapter 完成具体业务。

`sources` 是 source event 归一化和入口去重层。`buildSource.ts`、`index.ts`、`types.ts` 负责把输入转为标准 source，并处理 dedupe、scope lock、window 计数；`renderers` 则为不同 source 类型提供展示或调试用渲染信息。

`store` 是 Agent Signal 的存储抽象和实现。`types.ts` 定义 store contract，`adapters/redis` 提供 Redis-backed 的 source event、policy state、runtime guard 等实现。这个目录支撑去重、锁、窗口、过程状态和跨任务 guard。

## 关键入口

最外层导出入口是 `src/server/services/agentSignal/index.ts`，目前主要 re-export `emitter`。业务方通常从这里引入 Agent Signal 的 emit/enqueue API，而不是直接实例化 runtime。

`src/server/services/agentSignal/emitter.ts` 是 producer 面向的主入口，提供几类关键函数：

`emitAgentSignalSourceEvent(...)` 用于服务端生产者在当前进程内立即触发管线。它会先通过 `isAgentSignalEnabledForUser` 做 feature gate 判断，再调用 orchestrator 执行。

`enqueueAgentSignalSourceEvent(...)` 用于异步交给 Upstash Workflow。它会创建 normalized source event，计算 `scopeKey`，然后调用 `AgentSignalWorkflow.triggerRun(...)`。适合调用方需要快速返回、后台慢慢处理的场景。

`resolveSourceScopeKey` 暴露 scope key 推导能力，便于上游在入队或记录前获得稳定 scope。

`src/server/services/agentSignal/orchestrator.ts` 是真正组装服务端执行环境的入口。它连接 source 生成、默认策略创建、procedure policy options、runtime 创建、receipt 投影、observability 投影与持久化。这里还提供 `executeAgentSignalSourceEvent(...)` 和 `emitAgentSignalSourceEventWithStore(...)`，后者偏测试和 eval，用注入 store 避免依赖环境 Redis。

`src/server/services/agentSignal/runtime/AgentSignalRuntime.ts` 和 `runtime/AgentSignalScheduler.ts` 是运行时入口。`createAgentSignalRuntime(...)` 负责创建 runtime 并安装 policies；`AgentSignalScheduler.emit(...)` / `emitNormalized(...)` 负责把 source 放入调度过程，依次匹配 source、signal、action handler，并把 action result 转成内建 result signals。

`src/server/services/agentSignal/policies/index.ts` 是默认策略注册点。新增业务策略时，最终通常需要从这里进入默认 policy set，否则 runtime 创建后不会安装相关 handler。

## 主流程位置

同步主流程大致位于 `emitter.ts`、`orchestrator.ts`、`sources/index.ts`、`runtime/AgentSignalRuntime.ts`、`runtime/AgentSignalScheduler.ts`、`policies/index.ts` 之间。

第一步，业务方调用 `emitAgentSignalSourceEvent(...)`。入口检查当前用户是否启用 Agent Signal，并把 source input、`db`、`userId`、可选 `agentId` 组成执行上下文。

第二步，`orchestrator.ts` 的 `executeAgentSignalSourceEvent(...)` 进入核心执行。它会创建或接收 source event store，调用 `emitSourceEvent(...)` 做去重、scope lock、window 计数，并生成 normalized source。

第三步，orchestrator 创建默认策略和 runtime。策略来自 `createDefaultAgentSignalPolicies(...)`，procedure 相关依赖通过 `createProcedurePolicyOptions(...)` 注入，运行时由 `createAgentSignalRuntime(...)` 装配。

第四步，runtime scheduler 处理 source。`AgentSignalScheduler` 会按 node type 匹配已注册 handler：source handler 可能产出 signal，signal handler 可能继续产出 signal 或 action，action handler 执行副作用并返回 `ExecutorResult`。action 执行结果会被转换成 `actionApplied`、`actionSkipped`、`actionFailed` 这类内建 result signal，继续进入同一套语义链路。

第五步，流程结束后，orchestrator 把 trace 投影为 observability 记录和 receipt，并持久化。相关位置包括 `observability/projector.ts`、`observability/store.ts`、`services/receiptService.ts`。

异步主流程以 `enqueueAgentSignalSourceEvent(...)` 为起点，经 `src/server/workflows/agentSignal` 触发 worker 后，仍会回到 `executeAgentSignalSourceEvent(...)` 这条服务端执行路径。根据当前片段推断，workflow 只负责异步 handoff 和运行时机控制，核心语义处理仍集中在本目录。

## 推荐阅读顺序

1. 先读 `src/server/services/agentSignal/emitter.ts`，理解对外暴露的同步执行、异步入队和 scope key 入口。
2. 再读 `src/server/services/agentSignal/orchestrator.ts`，把 source store、policy、runtime、receipt、observability 如何串起来看清楚。
3. 接着读 `src/server/services/agentSignal/sources/index.ts` 和 `sources/buildSource.ts`，理解 source event 的去重、锁、窗口与标准化。
4. 然后读 `src/server/services/agentSignal/runtime/AgentSignalRuntime.ts`、`runtime/AgentSignalScheduler.ts`、`runtime/middleware.ts`，掌握 handler 注册和 source/signal/action 调度模型。
5. 再读 `src/server/services/agentSignal/policies/index.ts` 与 `policies/analyzeIntent/index.ts`，看默认业务策略如何安装到 runtime。
6. 最后按需要读 `procedure`、`services/selfIteration`、`observability`、`store/adapters/redis`，分别补足过程状态、具体业务副作用、观测和持久化细节。

## 常见误区

不要把 `procedure` 理解成 runtime 的第四种节点。根据目录和 skill 说明，runtime 节点主要是 source、signal、action；procedure 更像端到端业务过程的状态、记录、receipt 和抑制机制。

不要绕过 `emitter.ts` 或 `orchestrator.ts` 直接调用 policy handler。handler 依赖 runtime context、scope、store、observability 和 result signal 链路，单独调用容易漏掉去重、锁、receipt 或 trace。

不要把 source handler 写成重副作用执行器。这个目录的边界倾向是：source handler 做解释和 fan-out，signal handler 做语义转换或规划，action handler 才负责具体副作用和幂等处理。

不要只改一个策略文件就认为流程生效。新增 source、signal、action 或 policy 时，通常还要检查 `policies/types.ts`、`policies/index.ts`、`runtime/middleware.ts` 的注册方式，以及入口 source 是否真的从上游 emit/enqueue。

不要忽视 `scopeKey`。`sources` 和 `runtime/scope.ts` 都围绕 scope 做去重、锁和串行化；错误 scope 会导致重复执行、互相阻塞，或相同业务流程无法合并。

不要把 `services/selfIteration` 当成普通工具函数集合。它包含 self review、reflection、feedback、tools、execute 等更完整的业务执行层，和 `policies/analyzeIntent`、`policies/reviewNightly`、`procedure/emitToolOutcome.ts` 有明显流程关联。
