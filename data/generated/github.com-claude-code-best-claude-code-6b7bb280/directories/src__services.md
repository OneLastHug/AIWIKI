# 目录：src/services

## 它负责什么

`src/services` 是整个 CLI 的“服务层中枢”，负责把高层交互逻辑拆成可复用的能力模块。这里不是单一业务目录，而是一组面向运行期的服务集合：API 调用与重试、MCP 与 ACP 连接、会话压缩、提示建议、插件管理、LSP 管理、远程配置同步、分析埋点、OAuth 认证、技能学习与检索、团队记忆同步、工具执行统计等。

根据当前片段推断，这个目录的职责可以理解为三类：

1. 运行时基础设施：例如 `src/services/api/*`、`src/services/mcp/*`、`src/services/lsp/*`、`src/services/oauth/*`，它们直接支撑主循环和外部连接。
2. 会话智能化能力：例如 `src/services/compact/*`、`src/services/PromptSuggestion/*`、`src/services/extractMemories/*`、`src/services/skillLearning/*`。
3. 辅助治理与可观测性：例如 `src/services/analytics/*`、`src/services/policyLimits/*`、`src/services/remoteManagedSettings/*`、`src/services/langfuse/*`、`src/services/providerUsage/*`。

整体上，它是 `src/query.ts`、`src/main.tsx`、`src/screens/REPL.tsx`、`src/entrypoints/init.ts` 的服务底座。

## 直接子目录地图

这里的子目录很多，但可以按功能簇看，不必逐叶子文件展开。

- `api/`：Claude/OpenAI/Gemini/Grok 等模型访问层，以及 bootstrap、usage、retry、error、prompt dump、quota 等周边逻辑。
- `mcp/`：MCP 客户端、连接管理、权限、认证、资源与工具拉取、IDE/RPC 交互。
- `acp/`：ACP agent 的入口、桥接、权限与流封装，面向 agent 协议运行。
- `compact/` 与 `contextCollapse/`：上下文压缩、micro compact、snip、会话恢复与折叠策略。
- `analytics/` 与 `langfuse/`：事件上报、埋点、GrowthBook、Datadog、Langfuse tracing。
- `oauth/` 与 `auth/`：账户授权、token 交换、workspace key 保存、host guard。
- `lsp/`：LSP server manager、client、diagnostics、配置与被动反馈。
- `plugins/`：插件安装、启用、禁用、升级、CLI 命令集。
- `remoteManagedSettings/`、`settingsSync/`、`policyLimits/`：远程配置同步、策略限制、设置缓存与加载。
- `skillLearning/`、`skillSearch/`：技能发现、学习、提炼、推广与本地/远程检索。
- `teamMemorySync/`、`SessionMemory/`、`extractMemories/`、`AgentSummary/`、`PromptSuggestion/`、`MagicDocs/`：记忆、摘要、提示建议和文档生成相关的服务簇。
- `providerRegistry/`、`providerUsage/`：模型提供方注册、兼容矩阵、用量与余额轮询。
- 其他散列目录如 `searchExtraTools/`、`toolUseSummary/`、`tips/`、`tools/`、`localVault/`、`sessionTranscript/`，多半承担单点能力封装。

目录下还夹着若干顶层服务文件，例如 `awaySummary.ts`、`voice.ts`、`diagnosticTracking.ts`、`notifier.ts`、`preventSleep.ts`、`tokenEstimation.ts`，说明 `src/services` 也承载一部分跨模块通用功能。

## 关键入口

真正需要优先看的入口不在每个子目录里，而是少数几个被主流程频繁调用的文件。

- `src/services/api/claude.ts`：模型请求主入口，包含 `queryModelWithStreaming`、`queryModelWithoutStreaming`、usage 累积、system prompt 组装等关键函数。
- `src/services/api/client.ts`：创建 Anthropic client 的基础入口，主请求链路通常先从这里拿到客户端。
- `src/services/mcp/client.ts`：MCP 连接与工具/资源拉取的核心入口，包含 `connectToServer`、`ensureConnectedClient`、`getMcpToolsCommandsAndResources`。
- `src/services/mcp/MCPConnectionManager.tsx`：UI 和状态层的 MCP 连接管理入口，主界面会用到。
- `src/services/acp/entry.ts`：`runAcpAgent()` 是 ACP 模式的直接启动点。
- `src/services/compact/compact.ts`：`compactConversation()`、`partialCompactConversation()` 是上下文压缩的主入口。
- `src/services/remoteManagedSettings/index.ts`：远程托管设置的加载、刷新、轮询入口。
- `src/services/analytics/index.ts`：埋点与 sink 挂载入口。
- `src/services/oauth/client.ts`：OAuth 流程入口，负责授权 URL、token 交换、刷新与 profile 拉取。
- `src/services/lsp/manager.ts`：LSP server manager 的初始化与生命周期入口。

## 主流程位置

`src/services` 的主流程不是单点，而是被几条“上层主线”串起来。

第一条主线是查询与工具执行：`src/query.ts` 会调用 `src/services/api/withRetry.ts`、`src/services/api/errors.ts`、`src/services/compact/autoCompact.ts`、`src/services/compact/compact.ts`、`src/services/tools/StreamingToolExecutor.ts`、`src/services/tools/toolOrchestration.ts`，再结合 `src/services/langfuse/index.ts`、`src/services/analytics/index.ts` 做观测与统计。这里决定了对话轮次如何进入模型、如何触发工具、何时压缩上下文。

第二条主线是启动与装配：`src/main.tsx` 和 `src/entrypoints/init.ts` 会提前加载 `src/services/analytics/*`、`src/services/mcp/client.ts`、`src/services/policyLimits/index.ts`、`src/services/remoteManagedSettings/index.ts`、`src/services/lsp/manager.ts`、`src/services/oauth/client.ts`。这说明服务层很多模块并不是“被动工具”，而是启动时就要建立状态。

第三条主线是交互界面运行期：`src/screens/REPL.tsx` 直接消费 `src/services/mcp/MCPConnectionManager.tsx`、`src/services/compact/compact.ts`、`src/services/PromptSuggestion/speculation.ts`、`src/services/tips/tipScheduler.ts`、`src/services/preventSleep.ts` 等服务。也就是说，服务层同时服务于命令行主循环和 REPL 交互层。

## 推荐阅读顺序

1. 先看 `src/services/api/claude.ts` 和 `src/services/api/client.ts`，建立“请求如何发出”的整体感。
2. 再看 `src/services/compact/compact.ts`、`src/services/compact/autoCompact.ts`，理解上下文如何被控制。
3. 接着看 `src/services/mcp/client.ts` 与 `src/services/mcp/MCPConnectionManager.tsx`，把工具协议和连接管理串起来。
4. 然后看 `src/services/oauth/client.ts`、`src/services/lsp/manager.ts`、`src/services/remoteManagedSettings/index.ts`，补齐启动期基础设施。
5. 最后再扫 `src/services/analytics/index.ts`、`src/services/langfuse/index.ts`、`src/services/providerUsage/*`，理解可观测性与用量侧逻辑。

## 常见误区

1. 容易把 `src/services` 当成“纯辅助目录”。实际上它参与了主请求链路、启动装配和交互状态管理。
2. 容易只盯着 `api/`。但在这个仓库里，`mcp/`、`compact/`、`oauth/`、`lsp/`、`remoteManagedSettings/` 的重要性同样高。
3. 容易把 `index.ts` 当成唯一入口。这里很多目录确实有聚合层，但真正的主流程常落在更具体的实现文件里，比如 `src/services/api/claude.ts`、`src/services/mcp/client.ts`、`src/services/compact/compact.ts`。
4. 容易忽略顶层散文件。像 `awaySummary.ts`、`voice.ts`、`notifier.ts`、`preventSleep.ts` 这类文件虽然不在子目录中，但仍属于服务层能力的一部分。
5. 只按文件名理解语义会不稳。当前片段能确认的大方向是“协议、上下文、观测、同步、认证、工具执行”几条线，细粒度行为仍要回到具体实现验证。
