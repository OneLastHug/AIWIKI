# 文件：src/server/services/queue/QueueService.ts

## 一句话定位

`QueueService` 是 Agent Runtime 异步执行队列的统一门面：上层只面向它调度“下一步执行”，底层根据环境切换为本地 `setTimeout` 执行或生产队列 `QStash` 投递。

## 它暴露/定义了什么

该文件定义并导出 `QueueService` class。它内部持有一个私有 `impl: QueueServiceImpl`，构造时通过 `createQueueServiceModule()` 创建真实实现。对外暴露的方法分两类：

一类是队列操作代理：`scheduleMessage`、`scheduleBatchMessages`、`cancelScheduledTask`、`getQueueStats`、`healthCheck`，这些方法本身不实现业务逻辑，只把调用转发给当前 `impl`。

另一类是运行模式和调度策略辅助：`getImpl()` 用于取到底层实现，`isLocalExecution()` 判断是否为 `LocalQueueServiceImpl`，`static calculateDelay()` 根据优先级、工具调用、错误状态和 step 序号计算下一步延迟。

## 谁调用它

主要调用方是 `src/server/services/agentRuntime/AgentRuntimeService.ts`。`AgentRuntimeService` 默认在构造函数里创建 `new QueueService()`，除非外部通过 options 显式传入 `queueService: null` 关闭队列，测试或同步执行路径会这样做。

在 `AgentRuntimeService.createOperation()` 中，创建 operation 后会用 `queueService.scheduleMessage()` 调度首个 step，endpoint 指向 agent runtime 的 `/run` 执行入口。`executeStep()` 完成一个 step 后，如果 `shouldContinueExecution()` 判断仍需继续，也会再次 `scheduleMessage()` 调度下一个 step。人工干预恢复、显式启动执行等路径同样通过它重新入队。

测试文件 `src/server/services/queue/__tests__/QueueService.test.ts` 直接验证本地模式、队列模式、健康检查和 `calculateDelay()` 行为。根据当前片段推断，生产业务代码中除 `AgentRuntimeService` 外没有发现其他直接依赖 `QueueService` 的核心调用方，依据是仓库搜索结果中相关生产 import 集中在该服务。

## 它调用谁

`QueueService` 直接调用 `src/server/services/queue/impls/index.ts` 中的 `createQueueServiceModule()`，并依赖 `LocalQueueServiceImpl` 做实例判断。真实队列能力来自 `QueueServiceImpl` 接口的两个实现：

`LocalQueueServiceImpl` 位于 `src/server/services/queue/impls/local.ts`，使用 `setTimeout` 和注入的 execution callback 在当前进程异步执行 step。

`QStashQueueServiceImpl` 位于 `src/server/services/queue/impls/qstash.ts`，运行时动态 import `@upstash/qstash`，调用 `publishJSON()` 把消息投递到远端 HTTP endpoint。

实现选择由 `appEnv.enableQueueAgentRuntime` 控制；开启队列模式时还要求 `process.env.QSTASH_TOKEN` 存在，否则创建实现时直接抛错。

## 核心流程

典型流程是：`AgentRuntimeService` 创建 operation 并保存初始状态；如果允许自动开始，就调用 `QueueService.scheduleMessage()` 传入 `operationId`、`stepIndex`、`context`、`endpoint`、`priority`、重试配置和延迟。`QueueService` 不关心 agent 业务，只把 `QueueMessage` 交给底层实现。

本地模式下，消息被转为一个 `local-${operationId}-${stepIndex}-${Date.now()}` task id，并通过 `setTimeout` 触发 `AgentRuntimeService` 注入的 callback，最终回到 `executeStep()`。这种设计避免 `queue` 包反向 import `AgentRuntimeService`，用 callback injection 打断循环依赖。

队列模式下，消息被封装为 QStash JSON 请求，请求 body 包含 `operationId`、`stepIndex`、`context`、`payload`、`priority` 和 timestamp，headers 里也写入 operation、priority、stepIndex 信息。QStash 之后会请求传入的 endpoint，由 API 入口恢复执行。

## 关键函数的高层作用

`constructor()`：确定运行时使用哪种队列实现，是本文件最关键的分发点。它自身没有参数，环境差异完全下沉到 `createQueueServiceModule()`。

`getImpl()`：主要服务于 `AgentRuntimeService.setupLocalExecutionCallback()`。上层拿到底层实现后判断是否为 `LocalQueueServiceImpl`，如果是，就注入 `executeStep()` callback。

`isLocalExecution()`：提供一个轻量运行模式判断，测试中覆盖较多，业务上可用于区分本地开发和远端队列行为。

`scheduleMessage()`：统一的单消息调度入口，是 `AgentRuntimeService` 首步启动、下一步继续、人工干预恢复等流程的关键连接点。

`scheduleBatchMessages()`、`cancelScheduledTask()`、`getQueueStats()`、`healthCheck()`：都是薄代理。当前实现中统计和取消能力较弱，尤其 QStash 取消仍是 TODO，本地取消也是 no-op。

`calculateDelay()`：纯函数式调度策略。高优先级基础延迟 200ms，普通 1000ms，低优先级 5000ms；存在工具调用额外加 1000ms；存在错误时按 `stepIndex * 1000` 增加退避，最多增加 10000ms。

## 修改风险

最大风险是破坏 `QueueServiceImpl` 门面契约。`AgentRuntimeService` 假设 `scheduleMessage()` 一定返回 message/task id，且本地和 QStash 模式都接受同一份 `QueueMessage`。字段语义改动会同时影响本地开发、生产异步执行和测试。

第二个风险是本地模式 callback 注入。`getImpl()` 和 `LocalQueueServiceImpl` 的 `instanceof` 判断看似暴露实现细节，但它支撑了本地执行闭环。若改成包装、代理或多份模块实例，可能导致 `instanceof` 失效，进而本地消息被调度后无人执行。

第三个风险是延迟策略。`calculateDelay()` 会影响 agent 多步执行节奏；延迟过短可能放大工具调用尚未完成、重复失败或远端重试压力，延迟过长会让交互显著变慢。修改时应同步更新 `QueueService.test.ts` 中的期望。

第四个风险是生产环境配置。`createQueueServiceModule()` 在队列模式缺少 `QSTASH_TOKEN` 时直接抛错，因此任何默认开启 `enableQueueAgentRuntime` 的部署都必须保证环境变量完整，否则 `new QueueService()` 会在服务初始化路径失败。

第五个风险是取消和统计能力容易被误解。当前 `cancelScheduledTask()` 在本地不真正取消，在 QStash 也只是日志和 TODO；`getQueueStats()` 返回的多为占位值。如果新功能依赖“可取消”或“准确队列统计”，不能只调用现有方法，需要补齐底层实现和幂等检查。
