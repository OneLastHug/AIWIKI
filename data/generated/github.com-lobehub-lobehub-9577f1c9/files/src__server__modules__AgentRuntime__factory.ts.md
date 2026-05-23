# 文件：src/server/modules/AgentRuntime/factory.ts

## 一句话定位

`factory.ts` 是 Agent Runtime 后端运行时的“基础设施选择器”：它根据环境配置和 Redis 可用性，决定状态存储与事件流使用 Redis 实现、内存实现，或在队列模式缺少 Redis 时直接失败。

## 它暴露/定义了什么

这个文件主要暴露三个函数：

`isRedisAvailable()`：判断 Agent Runtime 专用 Redis client 是否可用。它通过 `getAgentRuntimeRedisClient()` 获取全局 Redis 实例，只要结果不是 `null` 就认为 Redis 可用。

`createAgentStateManager()`：创建 `IAgentStateManager`。它负责选择 Agent operation、Agent state、step result、执行历史、step lock 等状态管理的底层实现。

`createStreamEventManager()`：创建 `IStreamEventManager`。它负责选择 Agent Runtime 事件流发布、订阅、历史读取、清理等能力的底层实现，并可按配置包一层 `GatewayStreamNotifier`。

文件内部还有一个私有函数 `isQueueModeEnabled()`，只读取 `appEnv.enableQueueAgentRuntime`，用于判断是否进入 queue-based agent runtime 模式。

## 谁调用它

直接调用者集中在 Agent Runtime 的协调层、服务层和事件入口：

`src/server/modules/AgentRuntime/AgentRuntimeCoordinator.ts` 在构造函数里调用 `createAgentStateManager()` 和 `createStreamEventManager()`，为 coordinator 注入默认状态管理器和事件管理器。

`src/server/services/agentRuntime/AgentRuntimeService.ts` 在构造时调用 `createStreamEventManager()`，并把同一个 stream manager 传给 `AgentRuntimeCoordinator`，保证服务层发布事件和协调器终止事件使用同一套事件通道。

`src/app/(backend)/api/agent/stream/route.ts` 调用 `createStreamEventManager()`，用于 SSE 接口订阅指定 `operationId` 的事件流，并读取历史事件。

`src/server/services/aiAgent/index.ts`、`src/server/services/heterogeneousAgent/index.ts`、`src/server/routers/lambda/agentNotify.ts` 也会创建 stream manager，用于 AI agent、异构 agent 或通知路由里的事件发布/订阅场景。

此外，`src/server/modules/AgentRuntime/index.ts` 重新导出了这三个函数，因此部分调用通过模块入口 `@/server/modules/AgentRuntime` 完成。

## 它调用谁

`factory.ts` 主要依赖同目录下的几个实现类和单例：

`getAgentRuntimeRedisClient()` 来自 `src/server/modules/AgentRuntime/redis.ts`，负责创建或复用 Agent Runtime 的全局 Redis client；如果环境禁用 Redis 或没有 `REDIS_URL`，会返回 `null`。

`AgentStateManager` 是 Redis/分布式模式下的状态管理实现。

`inMemoryAgentStateManager` 是本地或简单部署下的内存状态管理单例。

`StreamEventManager` 是 Redis 事件流实现，用于跨进程、跨 worker 的事件发布与订阅。

`inMemoryStreamEventManager` 是本地内存事件流单例。

`GatewayStreamNotifier` 是包装器：当 `appEnv.AGENT_GATEWAY_URL` 和 `appEnv.AGENT_GATEWAY_SERVICE_TOKEN` 同时存在时，它会包住选定的 stream manager，把事件额外通知到 Agent Gateway。

它还读取 `appEnv.enableQueueAgentRuntime`、`appEnv.AGENT_GATEWAY_URL`、`appEnv.AGENT_GATEWAY_SERVICE_TOKEN`，并使用 `debug` 命名空间 `lobe-server:agent-runtime:factory` 输出选择过程。

## 核心流程

整体流程可以理解为两个独立但相关的选择链。

状态管理器选择链：如果 `enableQueueAgentRuntime` 没开启，直接返回 `inMemoryAgentStateManager`。这意味着默认本地/简单部署不强依赖 Redis。只有开启 queue mode 时才要求 Redis；如果此时 `isRedisAvailable()` 为 false，就抛出错误提示需要配置 `REDIS_URL`；否则创建新的 `AgentStateManager()`。

事件管理器选择链稍有不同：它优先使用 Redis。只要 Redis 可用，就创建 `StreamEventManager()`，即使 queue mode 未开启也一样。注释说明这是为了让 runtime worker 和 SSE route 在本地模式下也能通过同一条 stream bus 通信。Redis 不可用且 queue mode 未开启时，才退回 `inMemoryStreamEventManager`。Redis 不可用但 queue mode 开启时，抛出同样的 Redis 必需错误。

最后，`createStreamEventManager()` 会检查 Gateway 配置。如果 gateway URL 和 service token 都存在，返回 `new GatewayStreamNotifier(manager, url, token)`；否则返回原始 manager。

## 关键函数的高层作用

`isRedisAvailable()` 是全局判定入口，但它不是纯配置检查，而是会触发 `getAgentRuntimeRedisClient()` 的懒初始化逻辑。修改它可能影响 Redis client 创建时机、日志、连接错误暴露方式。

`createAgentStateManager()` 决定 Agent Runtime 状态是否可跨进程共享。queue mode 下它必须返回 Redis 版本，因为队列 worker、HTTP route、调度任务需要看到同一份 operation state 和 step lock。非 queue mode 返回内存单例，适合单进程本地执行。

`createStreamEventManager()` 决定 Agent Runtime 的事件通道。SSE 路由、运行时服务、异构 Agent 服务都依赖它发布和订阅 `agent_runtime_init`、step events、`agent_runtime_end` 等事件。它“Redis 优先”的策略很关键，因为事件流比状态管理更需要跨边界通信。

`isQueueModeEnabled()` 只是环境开关封装，辅助函数一句话即可理解：把 `appEnv.enableQueueAgentRuntime === true` 规范成布尔判断。

## 修改风险

第一类风险是 Redis 与内存实现的选择条件。`createAgentStateManager()` 和 `createStreamEventManager()` 的 fallback 策略并不完全相同：状态管理在非 queue mode 总是内存优先，而事件流 Redis 可用时优先 Redis。把两者改成一致看似简单，但可能破坏 worker、SSE route、agent service 之间的事件可见性。

第二类风险是 queue mode 的强约束。开启 `enableQueueAgentRuntime` 时缺少 Redis 必须快速失败，否则队列调度、step claim、operation state、事件订阅可能分别落到不同进程内存中，表现为任务丢失、重复执行、前端收不到结束事件。

第三类风险是单例与实例生命周期。内存实现是单例，Redis manager 多数是新实例但底层 Redis client 由 `redis.ts` 管理为全局单例。随意改成每次新建 Redis client，可能造成连接数膨胀；随意缓存 `GatewayStreamNotifier`，也可能影响测试注入和配置变更。

第四类风险是 Gateway 包装。`GatewayStreamNotifier` 是透明包装器的前提是它完整实现 `IStreamEventManager`。如果新增 stream manager 接口方法，必须同步检查 gateway wrapper、Redis 实现、内存实现和测试，否则某些调用路径会在运行期缺方法。

第五类风险是调用方共享同一个 stream manager 的假设。`AgentRuntimeService` 会先创建 `streamManager`，再传给 `AgentRuntimeCoordinator`。这能让服务层和 coordinator 对同一 operation 的事件发布保持一致。若在 coordinator 内部强行重新创建 manager，可能导致测试注入失效，也可能让同一次执行的事件分散到不同通道。
