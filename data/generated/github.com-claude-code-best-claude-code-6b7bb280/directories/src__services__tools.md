# 子系统：src/services/tools

## 解决什么问题

`src/services/tools` 负责“模型发出 tool_use 之后，系统如何真正把这些工具跑起来”这一整段链路。它不是单个工具实现目录，而是工具执行编排层：把 Anthropic SDK 里的 `ToolUseBlock` 转成真实调用，处理权限判断、并发调度、进度消息、失败回收、后置 hooks、MCP 工具适配，以及把执行结果重新包装成对上层可消费的 `Message` 流。

根据当前片段推断，这里是 Claude Code 主循环里的工具执行中枢，因为 `src/query.ts` 和 `src/utils/queryHelpers.ts` 都直接调用了 `runTools`，而 `StreamingToolExecutor` 又服务于流式场景下的增量执行与 fallback 回收。

## 相关目录和文件

核心文件一共 4 个：

- `src/services/tools/toolExecution.ts`：单个工具调用的主执行入口，负责工具查找、权限检查、调用、错误分类、schema 提示、上下文修改和 telemetry。
- `src/services/tools/toolOrchestration.ts`：批量工具调度器，把一轮里的多个 `tool_use` 分成可并发与必须串行的批次。
- `src/services/tools/toolHooks.ts`：前置/后置 hooks 的包装层，负责把通用 hook 系统接到具体工具调用上。
- `src/services/tools/StreamingToolExecutor.ts`：流式执行器，适配“工具调用是边生成边执行”的场景，支持并发、安全排序、进度即时输出和丢弃回收。
- `src/services/tools/__tests__/StreamingToolExecutor.test.ts`：主要验证流式执行器的 `discard()` 语义和资源释放行为。

它们依赖的上层入口主要是 `src/query.ts`、`src/utils/queryHelpers.ts`；底层则会碰到 `src/Tool.js`、`src/tools.js`、`src/utils/messages.js`、`src/utils/hooks.js`、`src/services/mcp/*`、`src/services/langfuse/index.js` 等。

## 核心对象

这里最关键的对象是 `ToolUseContext`。它承载一次工具执行所需的全部上下文：当前工具列表、MCP 客户端、abort controller、消息数组、AppState 访问器、in-progress tool ID 集合、Langfuse trace/span 等。这个目录里的所有执行逻辑，基本都围绕它展开。

第二个核心对象是 `Tool`。它来自 `src/Tool.js`，包含输入 schema、执行能力、并发安全判断、中断行为、MCP 标记等。`toolExecution.ts` 会通过 `findToolByName()` 解析 tool 名称，再据此决定是否可以执行、是否是 MCP 工具、是否可以并发。

第三个核心对象是消息更新协议。`toolExecution.ts` 和 `StreamingToolExecutor.ts` 都使用 `MessageUpdate` / `MessageUpdateLazy` 一类结构，把“一个工具执行过程中的进度、结果、上下文修改”包装成迭代器输出，供上层逐条消费。

## 运行流程

一条完整路径通常是这样的：

1. `src/query.ts` 或 `src/utils/queryHelpers.ts` 收到模型返回的 `tool_use` blocks。
2. `runTools()` 接手整批调用，先用 `partitionToolCalls()` 判断哪些工具可并发，哪些必须串行。
3. 对每个 `tool_use`，`runToolUse()` 先做工具查找、别名回退、MCP 连接识别和取消检查。
4. 如果工具存在，就进入 `streamedCheckPermissionsAndCallTool()`，这里把权限判断与实际调用包成一个异步流，同时持续发出 progress 消息。
5. 具体调用过程中，`toolHooks.ts` 会把 pre/post hooks、失败 hooks、阻断消息、附加上下文、MCP 输出替换等统一接入。
6. 工具结果会被重新包装成 `user`/`attachment`/`progress` 等消息，回到主对话流里。
7. 对流式场景，`StreamingToolExecutor` 会把新来的 `tool_use` 先放队列，再根据并发条件决定执行顺序；如果流式回退发生，它还能 `discard()` 掉未完成结果，避免旧执行污染新一轮。

`toolExecution.ts` 里还有一个很实用的补充逻辑：`buildSchemaNotSentHint()`。当模型调用了一个“需要先被发送 schema 才能正常用”的 deferred tool，但当前消息里并没有包含它时，会补一个提示，帮助模型重新加载可用工具。

## 上下游依赖

上游主要是 `src/query.ts`、`src/utils/queryHelpers.ts` 和更外层的消息循环。它们只关心“拿到工具调用后怎么继续推进会话”，不关心单个工具怎么执行。

下游依赖更广，主要包括：

- `src/Tool.js`、`src/tools.js`：工具注册与查找。
- `src/hooks/useCanUseTool.js`、`src/utils/permissions/*`：权限决策与规则判定。
- `src/utils/hooks.js`：pre/post tool hooks 的实际执行器。
- `src/services/mcp/*`：MCP 工具的服务器识别、连接信息、安全日志。
- `src/utils/messages.js`：把执行状态转换成 Claude Code 的标准消息结构。
- `src/services/langfuse/index.js`、`src/services/analytics/*`：埋点和性能追踪。
- `src/utils/toolResultStorage.js`、`src/utils/searchExtraTools.js`：结果存储与特殊工具补充逻辑。

换句话说，这个目录是“执行层”，上面接对话引擎，下面接权限、hooks、MCP 和具体工具实现。

## 修改时最容易踩的坑

第一，别把并发和顺序搞乱。`toolOrchestration.ts` 只有在 `tool.isConcurrencySafe()` 返回真时才允许批量并发；否则必须串行，否则会破坏消息顺序和上下文修改顺序。

第二，`StreamingToolExecutor` 的 `discard()` 不是简单清空数组，它还要 abort sibling controller、释放 span、清理 progress resolver。否则旧流的结果可能继续冒出来，或者造成内存泄漏。

第三，hook 相关逻辑很容易重复显示错误消息。`toolHooks.ts` 里专门跳过了 `hook_blocking_error` 的重复输出，这类逻辑改动时必须谨慎，否则 UI 会出现两次相同阻断原因。

第四，MCP 输出和普通工具输出不是同一条路。`updatedMCPToolOutput` 只对 MCP 工具生效，不能把普通工具也当成可替换输出处理。

第五，`toolExecution.ts` 里很多分支都带 telemetry。改动错误分类、取消原因、权限来源时，往往要同步调整埋点字段，不然日志语义会漂。

第六，`feature('...')` 在这个仓库里有编译器限制，只能直接放在条件位置。这个目录虽然大多没直接写 feature 分支，但如果你往这里加新路径，仍要遵守这个约束。

## 推荐阅读顺序

1. `src/services/tools/toolExecution.ts`：先看单个工具如何被找出、鉴权、调用、包装结果。
2. `src/services/tools/toolOrchestration.ts`：再看一轮工具如何被分批并发/串行执行。
3. `src/services/tools/toolHooks.ts`：理解 pre/post hook 是怎么插入执行链的。
4. `src/services/tools/StreamingToolExecutor.ts`：最后看流式执行、回退清理和顺序保证。
5. `src/query.ts`、`src/utils/queryHelpers.ts`：回到调用方，看这个子系统在主对话循环里怎么被接上。
