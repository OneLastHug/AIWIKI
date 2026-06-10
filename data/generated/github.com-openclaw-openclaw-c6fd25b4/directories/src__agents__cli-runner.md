# 子系统：src/agents/cli-runner

## 解决什么问题

`src/agents/cli-runner` 负责把 OpenClaw 的一次 agent 请求，转换成对外部 CLI agent 后端的可执行调用。这里的“CLI 后端”不是内置模型循环，而是 Codex、Claude Code、Gemini CLI 等命令行运行时。它要解决的核心问题包括：组装 system prompt 与用户 prompt、选择和规范化模型、复用或重建 CLI 会话、注入 MCP 工具配置、准备图片与技能环境、启动受监管的子进程、解析 stdout/jsonl 输出，并把结果重新包装成 OpenClaw 的 `EmbeddedPiRunResult`。

这个目录不是 agent 总调度入口的全部。真正对外暴露的编排入口在邻近文件 `src/agents/cli-runner.ts`，而目录内文件承担 prepare、execute、MCP 适配、会话历史、可靠性策略等分层职责。

## 相关目录和文件

`src/agents/cli-runner/types.ts` 定义贯穿整个子系统的参数和准备态对象，尤其是 `RunCliAgentParams`、`PreparedCliRunContext`、`CliPreparedBackend`。

`src/agents/cli-runner/prepare.ts` 负责“运行前准备”：解析工作目录、CLI backend 配置、auth profile、context window、bootstrap 文件、MCP loopback、系统提示词、会话复用条件、context engine 等。

`src/agents/cli-runner/execute.ts` 负责“真正执行”：构造命令行参数和环境变量，写临时 system prompt 或图片文件，进入串行队列，通过 process supervisor 启动子进程，处理超时、取消、流式输出和错误分类。

`src/agents/cli-runner/helpers.ts` 是执行层的工具箱，包含 CLI 参数拼装、prompt 输入方式选择、模型规范化、队列 key、图片 payload、system prompt 文件写入等。

`src/agents/cli-runner/bundle-mcp.ts` 及 `bundle-mcp-codex.ts`、`bundle-mcp-claude.ts`、`bundle-mcp-gemini.ts` 负责把 OpenClaw 的 bundled/user MCP 配置投影到不同 CLI 的配置形态。Claude 走 `--mcp-config` 文件，Codex 走 `-c mcp_servers=...` 或 thread config patch，Gemini 走临时 system settings 文件。

`src/agents/cli-runner/session-history.ts` 负责读取会话历史、构造 reseed/history prompt，并控制历史文件和历史消息数量上限。`src/agents/cli-runner/reliability.ts` 放置无输出 watchdog 与 supervisor scope key 等可靠性策略。`claude-live-session.ts` 和 `claude-skills-plugin.ts` 是 Claude CLI 的长会话与 skills 插件特殊路径。

## 核心对象

`RunCliAgentParams` 是上游传入 CLI runner 的完整请求。它包含会话标识、工作目录、配置、prompt、provider/model、超时、触发来源、图片、技能快照、channel 信息、auth profile、工具策略、取消信号和回调。

`PreparedCliRunContext` 是 prepare 阶段产物。它把原始参数扩展为可执行上下文，包括解析后的 backend、准备好的 backend 参数、可复用 CLI session、system prompt、bootstrap 警告、context engine、模型名、auth epoch、MCP hash 等。execute 阶段主要消费这个对象，避免重复查配置。

`CliBackendConfig` 来自 `src/agents/cli-backends.ts` 及插件 backend 合同。它描述 CLI 命令、基础参数、resume 参数、输出格式、session 参数、模型参数、环境变量清理、序列化策略等。cli-runner 不硬编码单个 CLI 的完整语义，而是通过 backend 配置和少量适配器完成差异化。

`CliOutput` 来自 `src/agents/cli-output.ts`，是 stdout/jsonl 解析后的统一输出，包含文本、原始文本、sessionId、usage 等信息。

## 运行流程

上游通常经 `src/agents/command/attempt-execution.ts` 调用 `runCliAgent`。`runCliAgent` 先处理 cron 场景下的 `before_agent_reply` hook；如果 hook 已经生成回复，就直接返回，不进入 CLI 准备阶段。否则 lazy import `prepare.runtime.ts`，调用 `prepareCliRunContext`。

prepare 阶段先解析运行工作目录和 CLI backend。如果配置要求 `toolsAllow` 或禁用 native tools 但后端无法保证，会直接失败。随后解析 agent 目录、auth profile、模型、context window，读取 bootstrap/context 文件并计算截断警告。若后端启用 bundled MCP，会启动或复用 MCP loopback server，生成 `OPENCLAW_MCP_*` 环境变量，并调用 `prepareCliBundleMcpConfig` 合并外部 MCP、用户 MCP、插件 MCP 和 loopback MCP 配置。之后 prepare 还会计算 auth epoch、system prompt hash、MCP hash，并判断旧 CLI session 是否可复用。

进入 `runPreparedCliAgent` 后，系统会按需要读取历史消息，触发 `llm_input`、`before_agent_run`、`agent_end`、`llm_output` 等 harness hook。若 `before_agent_run` 阻止执行，会写入一条脱敏的阻止消息并返回错误 payload。

真正执行由 `executePreparedCliRun` 完成。它决定是否 resume、是否发送 system prompt、prompt 走 argv 还是 stdin、是否附带图片文件，然后构造最终 argv。执行会进入 `enqueueCliRun` 队列，避免同一 backend/session 并发踩踏。随后清理敏感宿主环境变量，叠加 backend/env、MCP env、skills env，通过 process supervisor spawn 子进程。stdout 会保留 tail 用于诊断，并保留最多 1MiB 用于解析；jsonl 输出还会边读边发 `assistant` stream 事件。进程退出后，代码按退出原因区分无输出超时、总体超时、格式错误、session 过期和普通失败。成功时解析输出、应用输出 text transform，返回统一结果。

如果 resume 因 `session_expired` 失败，外层会尝试不带旧 sessionId 再跑一次，以创建新 CLI session。成功结果会写入 `agentMeta.cliSessionBinding`，记录 sessionId、auth profile、auth epoch、system prompt hash、MCP hash，供后续复用判断。

## 上下游依赖

上游主要是 `src/agents/agent-command.ts`、`src/agents/command/attempt-execution.ts` 和 `src/agents/pi-embedded-runner` 相关路径，它们决定什么时候选择 CLI runner 而不是内置 harness。hook 上游来自 `src/plugins/hook-runner-global.ts` 和 `src/agents/harness/*`。

配置依赖集中在 `src/config/*`、`src/agents/cli-backends.ts`、`src/agents/auth-profiles/*`、`src/config/sessions.js`。会话和历史依赖 `@earendil-works/pi-coding-agent` 的 `SessionManager` 以及本仓库 session store。

执行依赖 `src/process/supervisor/*` 管理子进程生命周期；输出解析依赖 `src/agents/cli-output.ts`；失败分类依赖 `src/agents/failover-error.ts` 和 `src/agents/pi-embedded-helpers.ts`。MCP 依赖 `src/gateway/mcp-http*`、`src/plugins/bundle-mcp.js`、`src/agents/bundle-mcp-config.js` 和各 CLI 的适配文件。

## 修改时最容易踩的坑

第一，CLI session 复用条件不能只看 sessionId。auth profile、auth epoch、system prompt、prompt tool names、MCP 配置 hash、transcript 是否存在都会影响可复用性。忽略这些会导致旧 CLI 会话带着错误工具、旧身份或旧系统提示继续运行。

第二，MCP loopback 的端口会变化，所以 `bundle-mcp.ts` 专门把 openclaw loopback URL 规范化后计算 `mcpResumeHash`。如果直接用实际端口参与 resume 判断，会造成无意义的 session 失效；如果完全忽略 MCP 配置，又可能复用错误工具集。

第三，环境变量处理是安全边界。`execute.ts` 会清理 backend 指定的 auth env，并删除 `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`。新增后端或 auth profile 时，不要把宿主密钥默认透传给子进程。

第四，stdout 解析有大小限制。普通输出超过解析缓冲且没有 jsonl streaming parser 时会被拒绝，避免解析截断内容。新增输出模式必须同时考虑 tail 诊断、parse buffer、streaming delta 和 `parseCliOutput`。

第五，Claude live session 是特殊路径。它要求 JSONL streaming parser，并接管部分 cleanup；修改 `preparedBackend.cleanup`、skills plugin cleanup 或长期进程生命周期时，要同时检查普通 spawn 路径和 live session 路径。

第六，根据当前片段推断，`prepare.runtime.ts`、`execute.runtime.ts` 是 lazy import 边界，用于减少冷启动或避免循环依赖。调整导入时要小心不要把重依赖提前加载到主入口。

## 推荐阅读顺序

1. 先读 `src/agents/cli-runner/types.ts`，建立参数、准备态和返回信息的整体模型。
2. 再读邻近入口 `src/agents/cli-runner.ts`，理解 hook、context engine、失败重试和结果包装。
3. 读 `src/agents/cli-runner/prepare.ts`，重点看 backend 解析、auth profile、bootstrap、MCP、system prompt 和 session reuse。
4. 读 `src/agents/cli-runner/execute.ts`，重点看 argv/env 构造、队列、supervisor spawn、输出解析和错误分类。
5. 按需读 `src/agents/cli-runner/bundle-mcp.ts` 及三个 CLI 适配文件，理解 MCP 配置如何映射到不同 CLI。
6. 最后读 `src/agents/cli-runner/session-history.ts`、`reliability.ts`、`claude-live-session.ts`，补齐历史注入、watchdog 和 Claude 特殊会话行为。
