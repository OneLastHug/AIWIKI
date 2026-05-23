# 目录：src/server/services/queue

## 它负责什么

`src/server/services/queue` 是服务端 Agent Runtime 的“步骤调度抽象层”。它不直接实现 Agent 的推理、工具调用、状态管理或消息持久化，而是把“下一步什么时候执行、通过什么机制触发执行”封装成统一接口，供 `src/server/services/agentRuntime/AgentRuntimeService.ts` 调用。

这个目录的核心职责可以概括为三点：

1. 提供统一的 `QueueService` 门面，屏蔽本地开发模式和生产队列模式的差异。
2. 定义队列消息结构 `QueueMessage`，承载 `operationId`、`stepIndex`、`context`、`endpoint`、`priority`、`delay`、重试参数等调度信息。
3. 根据运行环境选择具体实现：默认本地模式使用 `setTimeout` 延迟执行回调；队列模式使用 `@upstash/qstash` 向指定 endpoint 投递 HTTP 任务。

从代码关系看，这里是 Agent Runtime 异步执行链路中的“调度器适配层”，不是通用任务队列平台。它主要服务于 Agent step 的启动、续跑、人类干预后的恢复执行，以及本地/生产两种运行方式的行为对齐。

## 直接子目录地图

`src/server/services/queue` 当前结构很小，只有一个实现目录和一个测试目录：

`src/server/services/queue/impls` 是队列实现层。它定义 `QueueServiceImpl` 接口，并提供两个实现：`LocalQueueServiceImpl` 和 `QStashQueueServiceImpl`。同时，`impls/index.ts` 负责根据环境配置创建具体实现。

`src/server/services/queue/__tests__` 是单元测试目录。测试重点不是复杂业务流程，而是确认运行模式选择、缺少 `QSTASH_TOKEN` 时的错误、local 模式返回 task id、批量调度、健康检查，以及 `QueueService.calculateDelay` 的优先级和退避规则。

目录根部的文件承担公开 API 和类型边界：`QueueService.ts` 是门面服务；`types.ts` 是消息、统计和健康检查的类型定义；`index.ts` 是对外导出入口。

## 关键入口

最重要的入口是 `src/server/services/queue/index.ts`。外部通常通过它导入 `QueueService`、`QueueServiceImpl`、`QueueMessage`、`QueueStats`、`HealthCheckResult`。这让调用方不需要关心内部实现文件布局。

业务使用层的入口是 `QueueService` 类，位于 `src/server/services/queue/QueueService.ts`。它在构造函数中调用 `createQueueServiceModule()` 得到具体实现，然后把 `scheduleMessage`、`scheduleBatchMessages`、`cancelScheduledTask`、`getQueueStats`、`healthCheck` 等方法直接委托给实现对象。

实现选择入口是 `src/server/services/queue/impls/index.ts`。其中 `isQueueAgentRuntimeEnabled()` 读取 `appEnv.enableQueueAgentRuntime`，注释说明其来源对应 `AGENT_RUNTIME_MODE=queue`。如果开启队列模式，则要求存在 `QSTASH_TOKEN`，并创建 `QStashQueueServiceImpl`；否则创建 `LocalQueueServiceImpl`。

本地执行的特殊入口是 `LocalQueueServiceImpl.setExecutionCallback()`。它由 `AgentRuntimeService` 注入回调，用来避免 `queue` 目录反向依赖 `agentRuntime`。也就是说，本地模式不是发送 HTTP 请求，而是在 `setTimeout` 到期后调用注入的 `executeStep` 回调。

生产队列入口是 `QStashQueueServiceImpl.scheduleMessage()`。它动态导入 `@upstash/qstash`，调用 `publishJSON`，把 `operationId`、`stepIndex`、`context`、`payload`、`priority` 等写入 body，并把任务投递到 `endpoint`。源码里的 endpoint 主要由 Agent Runtime 拼成 `/api/agent/run` 这一类内部运行端点；这里不展开真实部署地址。

## 主流程位置

主流程不在 `queue` 目录内部，而在 `src/server/services/agentRuntime/AgentRuntimeService.ts`。`queue` 目录只是被它调用的调度基础设施。

创建操作时，`AgentRuntimeService.createOperation()` 会初始化 Agent operation 状态、保存 metadata、注册 hooks，然后在 `autoStart` 为 true 且 `queueService` 可用时调用 `queueService.scheduleMessage()` 调度第一步。这个消息会携带 `initialContext`、`operationId`、`initialStepCount`、高优先级和短延迟，目标 endpoint 是 Agent 执行入口。

执行一步时，`AgentRuntimeService.executeStep()` 会先通过 coordinator 尝试 claim step，防止 QStash 重试或多实例下重复执行。一步完成后，如果 `shouldContinue` 且存在 `nextContext`，它会计算下一步的 delay 和 priority，再次调用 `queueService.scheduleMessage()` 调度 `stepIndex + 1`。因此 Agent 的多步执行不是在一个长同步调用里跑到底，而是在“执行一步、保存状态、调度下一步”的循环中推进。

本地模式下，`AgentRuntimeService` 构造时会调用 `setupLocalExecutionCallback()`。如果底层实现是 `LocalQueueServiceImpl`，就注入一个回调：收到 `operationId`、`stepIndex`、`context` 后调用 `this.executeStep(...)`。这解释了为什么 local 模式同样走 `scheduleMessage()`，但实际不会发 HTTP 请求。

人类干预恢复执行也会经过队列。`AgentRuntimeService.processHumanIntervention()` 在收到 approve、reject、input、select 等动作后，会用高优先级和短延迟重新调度指定 step，并把人工输入或工具审批结果放入 `payload`。

此外，`src/server/services/agentRuntime/hooks/HookDispatcher.ts` 和 `src/server/services/bot/AgentBridgeService.ts` 会读取 `isQueueAgentRuntimeEnabled()`。它们不是队列调度主流程，但会根据是否为 queue mode 调整 hook 分发或 bot 交互策略。根据当前片段推断，queue mode 代表跨进程/生产异步执行，local mode 代表同进程内存回调执行；依据是 `HookDispatcher` 对 local hooks 使用内存 handler，而生产模式转为 webhook 配置投递。

## 推荐阅读顺序

建议先读 `src/server/services/queue/types.ts`，理解 `QueueMessage` 是这个目录的核心数据契约。重点看 `operationId`、`stepIndex`、`context`、`endpoint`、`payload`、`priority`、`delay`、`retries`、`retryDelay` 这些字段如何描述一次 Agent step 调度。

第二步读 `src/server/services/queue/impls/type.ts` 和 `src/server/services/queue/QueueService.ts`。前者定义所有实现必须提供的能力，后者展示门面层只是做委托和少量辅助判断。

第三步读 `src/server/services/queue/impls/index.ts`。这里能看清 local mode 与 queue mode 的切换条件，以及 `QSTASH_TOKEN` 为什么是生产队列模式的必要条件。

第四步对比 `src/server/services/queue/impls/local.ts` 和 `src/server/services/queue/impls/qstash.ts`。前者关注 `setExecutionCallback`、`setTimeout`、`pendingExecutions`；后者关注 `publishJSON`、headers、delay 秒级转换、重试参数。

最后再跳到 `src/server/services/agentRuntime/AgentRuntimeService.ts`，只看 `setupLocalExecutionCallback()`、`createOperation()`、`executeStep()` 中调度下一步的位置，以及 `processHumanIntervention()`。这样能把“队列服务如何被真实业务驱动”串起来。

## 常见误区

第一个误区是把 `queue` 理解为完整后台任务系统。当前目录没有持久化任务表、消费 worker、任务状态机或通用调度 DSL。它只是 Agent Runtime 的队列适配层，真正的 operation 状态由 Agent Runtime coordinator 管，执行逻辑也在 `AgentRuntimeService`。

第二个误区是认为 local mode 和 queue mode 的调用路径完全不同。实际上上层都调用 `scheduleMessage()`。差异只在底层实现：local mode 用 `setTimeout` 调用注入回调，queue mode 用 QStash 投递 HTTP 请求。

第三个误区是认为 `cancelScheduledTask()` 已经具备强取消能力。当前 local 实现只是记录日志，不支持取消已安排的 `setTimeout`；QStash 实现中也只是留下 TODO，注释提到未来可通过 Redis cancellation marker 实现。因此不要把它当作可靠取消语义。

第四个误区是只看 `QueueService.calculateDelay()` 就以为所有 delay 都在这里计算。它提供了基于 priority、tool calls、errors、stepIndex 的静态规则，但真实下一步调度还会经过 `AgentRuntimeService` 内部的 `calculateStepDelay()`、`calculatePriority()` 等逻辑。要理解完整节奏，需要回到 Agent Runtime 主流程。

第五个误区是忽略 `endpoint` 字段。`QueueService` 本身不知道任务最终执行什么，它只是把消息送到调用方指定的 endpoint。本地模式甚至不使用 endpoint，而是靠注入回调执行；生产模式才会把 endpoint 作为 QStash 投递目标。
