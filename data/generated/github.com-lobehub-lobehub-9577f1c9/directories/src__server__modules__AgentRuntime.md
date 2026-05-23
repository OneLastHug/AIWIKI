# 目录：src/server/modules/AgentRuntime

## 它负责什么

这个目录是服务端里“Agent 运行时编排层”的实现位置。它不直接承载数据库模型或路由层逻辑，而是把一次 Agent operation 的状态保存、步骤结果持久化、流式事件发布、分布式执行锁，以及本地内存回退这些能力拼在一起。

从现有文件结构看，它更像一个运行时中枢：上层调用它来创建 operation、推进 state、记录 step result、清理资源；下层则由不同实现负责真正存储和事件分发。根据当前片段推断，这里同时支持 Redis 模式和纯内存模式，适合本地开发、单机部署和队列式部署几种场景。

## 直接子目录地图

这个目录下真正的子目录只有 `__tests__`，没有再拆出更深的业务分层。也就是说，核心实现文件都平铺在 `src/server/modules/AgentRuntime/` 根部，测试集中放在 `__tests__/`。

`__tests__/` 里主要是两类内容：

- 单元测试：围绕 `AgentStateManager`、`StreamEventManager`、`GatewayStreamNotifier`、`ToolResultWaiter`、`resolveToolTimeout`、`llmErrorClassification`、`dispatchClientTool` 等模块验证行为。
- 场景规范：`AgentRuntimeCoordinator.feature` 和对应的 `AgentRuntimeCoordinator.test.ts`，更像是这个目录的主流程行为说明书。

## 关键入口

这个目录最重要的入口是 `index.ts`。它把对外可用的核心类型和工厂函数统一导出，包括 `AgentRuntimeCoordinator`、`createAgentStateManager`、`createStreamEventManager`、`createRuntimeExecutors` 以及 `IAgentStateManager`、`IStreamEventManager` 等类型。对外使用方通常不应该直接遍历内部文件，而是从这里拿到稳定 API。

第二个关键入口是 `factory.ts`。这里决定运行时到底用哪套实现：

- Redis 可用时，优先走 Redis 相关实现。
- Redis 不可用且未开启队列模式时，回退到 `InMemory` 实现。
- 如果开启了队列模式但没有 Redis，则直接抛错。

这也是这个目录和环境变量强绑定的地方。根据当前片段推断，`appEnv.enableQueueAgentRuntime`、`REDIS_URL`、`AGENT_GATEWAY_URL`、`AGENT_GATEWAY_SERVICE_TOKEN` 都会影响最终行为。

第三个关键入口是 `AgentRuntimeCoordinator.ts`。它是编排层本体，负责把状态管理和事件管理串起来。

## 主流程位置

主流程基本都收敛在 `AgentRuntimeCoordinator.ts` 里，核心路径是：

1. `createAgentOperation()`  
   创建 operation metadata，并立刻发布初始化事件。

2. `saveAgentState()`  
   先读旧状态，再写新状态，如果状态首次进入终态，就发布 `agent_runtime_end` 一类的结束事件。

3. `saveStepResult()`  
   先读旧状态，再写 step result，保证 step 事件先于终态事件到达；这是这个目录里很关键的顺序控制点。

4. `deleteAgentOperation()`  
   同时清理 state 和 stream 侧资源。

5. `tryClaimStep()` / `releaseStepLock()`  
   这两处说明这里不只是“保存状态”，还承担分布式执行协调，避免同一步骤被重复抢占。

6. `disconnect()`  
   收尾关闭 state manager 和 stream manager。

配套实现上，`AgentStateManager.ts`、`StreamEventManager.ts`、`InMemoryAgentStateManager.ts`、`InMemoryStreamEventManager.ts`、`GatewayStreamNotifier.ts`、`redis.ts` 这些文件共同构成它的运行底座。前者偏持久化和锁，后者偏事件通道和外部网关转发。`RuntimeExecutors.ts`、`ToolResultWaiter.ts`、`dispatchClientTool.ts`、`resolveToolTimeout.ts` 则更像是运行步骤里的工具调用和等待控制辅助件。

## 推荐阅读顺序

1. `index.ts`：先看这个目录暴露了什么能力。
2. `factory.ts`：再看运行时是怎么选实现的。
3. `AgentRuntimeCoordinator.ts`：最后看主流程编排和事件时序。
4. `types.ts`：补齐接口契约。
5. `__tests__/AgentRuntimeCoordinator.feature` 和相关测试：用例能最快说明设计意图。

## 常见误区

- 把这里当成纯业务逻辑目录。实际上它更偏“运行时编排”，重点是协调 state、event、lock，而不是承载上层 Agent 能力本身。
- 忽略 `factory.ts` 的环境分支。这个目录的行为会随着 Redis、队列模式、网关配置变化，不能默认只有一种实现。
- 只看 `saveAgentState()` 不看 `saveStepResult()`。这两条路径都可能触发终态事件，但时序要求不同，后者尤其强调“先发 step，再发 end”。
- 把 `InMemory` 实现当作测试专用。根据文件结构和工厂逻辑推断，它也是本地或简单部署下的正式回退方案。
- 只关注 coordinator，不看 `__tests__/`。这个目录的边界和行为约束，很多其实是测试文件在定义。
