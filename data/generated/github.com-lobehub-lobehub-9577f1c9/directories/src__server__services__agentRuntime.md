# 目录：src/server/services/agentRuntime

## 它负责什么

这个目录是后端 agent 运行时的服务层封装，核心职责是把一次 agent 操作从“创建、调度、逐步执行、处理人工介入、完成收尾”串成一条完整链路。根据当前片段推断，它不是单一算法模块，而是一个运行时编排中心：上接消息、队列、工具执行和 agent signal，下接数据库持久化、trace 记录和 webhook 钩子。

它最重要的角色有三类：

1. 运行时编排。`AgentRuntimeService` 负责创建 operation、调度第一步、执行 step、查询状态、处理 human intervention、做同步执行。
2. 生命周期收尾。`CompletionLifecycle` 负责把 operation 走到终态时的数据库落库、signal 事件发射、hook 派发、错误回写。
3. 外部扩展。`hooks/HookDispatcher.ts` 负责本地 hook 和 webhook 两种模式的分发，保证运行时可以被外部系统观察或介入。

## 直接子目录地图

这个目录下真正的直接子目录很少，当前片段里能看到的只有两个：

- `hooks/`：外部生命周期 hook 的实现区。这里放着 hook 分发器、hook 类型和导出入口，是运行时的扩展接口层。
- `__tests__/`：围绕运行时主流程、hook、收尾、人工介入、同步执行等行为的测试集合。它更像行为说明书，不是主代码路径。

其余文件都位于目录根部，说明这个目录偏“服务聚合层”，不是再往下拆很多内部子模块。根据当前片段推断，`hooks/` 是唯一的功能性子目录，`__tests__/` 只是验证层。

## 关键入口

对外最直接的入口是 `index.ts`。它只做三件事：导出 `AbandonOperationService`、`AgentRuntimeService` 和 `types`，说明这个目录被设计成一个服务包，对外消费时不需要关心内部文件组织。

真正的主入口是 `AgentRuntimeService.ts`。从构造函数看，它会组装这些依赖：

- `AgentRuntimeCoordinator`
- `CompletionLifecycle`
- `HumanInterventionHandler`
- `OperationTraceRecorder`
- `ToolExecutionService`
- `QueueService`
- `hookDispatcher`

这说明 `AgentRuntimeService` 不是单点逻辑，而是把运行时需要的协调器、队列、工具执行和收尾器都接起来。

另一个关键入口是 `hooks/index.ts`。它通常会把 `hookDispatcher` 这种单例实例对外暴露，方便整个服务层共享同一个 hook 注册表。

## 主流程位置

主流程基本集中在 `AgentRuntimeService.ts` 的几个方法里，顺序很清晰：

- `createOperation()`：创建 operation。这里会先写入初始 `agent_operations` 记录，再创建初始 state，注册外部 hooks，最后决定是否自动启动首步。
- `executeStep()`：真正的 step 执行核心。这里会先抢分布式锁，再发 `step_start` 事件，读取 state，处理终态判断、step 重入、工具调用、LLM 调用，以及后续的状态推进。
- `startExecution()`：从方法名和测试覆盖看，它更像是启动或恢复一次执行的高层入口，通常会包住 step 调度和状态检查。
- `processHumanIntervention()`：处理人工审批、拒绝继续、恢复执行等交互分支。
- `executeSync()`：同步执行路径，常用于测试、禁用队列或需要立即跑完一步的场景。

收尾链路则分散在几个辅助文件里：

- `CompletionLifecycle.ts`：负责终态记录、完成原因映射、错误信息提取、signal 发射和 hook 派发。
- `OperationTraceRecorder.ts`：负责 trace snapshot 记录和最终归档。
- `HumanInterventionHandler.ts`：负责把人工介入写回消息和运行状态。
- `abort.ts`：负责中断判断和异常识别。
- `stepPresentation.ts`：负责把 step 结果整理成可展示的数据。

hook 分发主线在 `hooks/HookDispatcher.ts`。它区分本地模式和生产模式：本地模式直接调用 handler，生产模式把 hook 序列化成 webhook，通过 fetch 或 QStash 发出去。`hookDispatcher` 是单例，说明它是全局共享的事件总线式对象。

## 推荐阅读顺序

1. 先看 `index.ts`，确认这个目录对外导出了什么。
2. 再看 `AgentRuntimeService.ts` 的构造函数和 `createOperation()`、`executeStep()`，把主链路先串起来。
3. 接着看 `CompletionLifecycle.ts`，理解 operation 终态是怎么落库和收尾的。
4. 再看 `hooks/HookDispatcher.ts` 和 `hooks/types.ts`，理解扩展点和 webhook 机制。
5. 最后补 `OperationTraceRecorder.ts`、`HumanInterventionHandler.ts`、`stepPresentation.ts`、`abort.ts`，把辅助逻辑补齐。

## 常见误区

- 把 `createOperation()` 当成真正执行入口。它更像“创建并调度首步”，真正的运行逻辑在 `executeStep()`。
- 把 `CompletionLifecycle` 只理解成“保存完成状态”。它还负责 signal 事件和 hook 派发，属于终态收口器，不只是写库。
- 把 `hooks/` 当成测试辅助目录。它是正式功能路径，尤其是 `hookDispatcher`，会影响本地和生产两种模式。
- 忽略 `executeSync()`。这个方法通常是测试和非队列场景的关键入口，很多同步验证都要靠它。
- 只看根部文件忽略 `__tests__/`。这些测试名本身就暴露了目录的主流程边界：step 执行、completion webhook、human intervention、agent signal hooks、abandon 逻辑都在这里被覆盖。
