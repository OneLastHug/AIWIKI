# 目录：src/agents

## 它负责什么

`src/agents` 是 OpenClaw 中“代理运行时”的核心目录，负责把一次 agent 请求从配置解析、模型与运行时选择、系统提示词构造、工具清单装配、上下文与权限处理，一直推进到具体 harness 或 CLI 后端执行，并把执行结果、工具调用、会话状态、子代理协作等能力接回 OpenClaw 的上层通道与网关。

从当前目录结构看，它不是单一“模型调用层”，而是一个横跨多种 agent runtime 的编排层。这里同时包含原生/嵌入式 PI runner、外部 CLI runner、ACP spawn、auth profile、bash/tool 执行、context compaction、system prompt、tool policy、workspace、session/subagent 工具等模块。也就是说，`src/agents` 解决的是“OpenClaw 如何稳定地启动、约束、驱动和观察一个 agent 回合”。

根部 `src/agents/AGENTS.md` 特别强调性能边界：agent 测试和热路径容易被插件、通道、provider runtime 的冷加载拖慢；如果只需要 schema、capability、routing、静态发现信息，应优先使用轻量 artifact 或纯 helper，而不是加载完整 bundled plugin/channel/provider runtime。这说明该目录在架构上很重视“运行时编排”和“轻量决策路径”的分离。

## 直接子目录地图

`src/agents/auth-profiles` 负责 agent auth profile 的持久化、排序、OAuth、外部 CLI 认证同步、credential state、doctor/repair 等能力。根部还有 `auth-profiles.ts`、`auth-profiles.runtime.ts` 等聚合或运行时入口。

`src/agents/cli-runner` 负责把 agent 请求转成外部 CLI 后端执行，例如 Claude/Codex/Gemini 相关 bundle MCP、系统提示词文件写入、图片输入准备、session history、CLI 参数构造、执行监督与可靠性控制。根部 `src/agents/cli-runner.ts` 是更高层的运行入口。

`src/agents/command` 根据命名和 `agent-command.ts` 的引用推断，承载 agent command 回合中的 attempt lifecycle、回调和命令级执行支持。

`src/agents/harness` 是 agent harness 抽象层，包含 harness registry、selection、policy、builtin PI 适配、v2 lifecycle、hook helpers、native hook relay、context engine lifecycle、tool result middleware 等。它是“选择哪个 agent 执行器并跑一次 attempt”的核心位置。

`src/agents/pi-embedded-helpers` 和 `src/agents/pi-embedded-runner` 面向内置 PI runtime。后者还有 scoped `AGENTS.md`，其中 `run` 子目录应是嵌入式运行实现的更深层区域。

`src/agents/pi-hooks` 负责 PI 相关 hooks，其中 `context-pruning` 指向上下文裁剪能力。

`src/agents/runtime-plan` 负责把一次 agent 运行拆成可执行计划。可见入口包括 `buildAgentRuntimePlan`、`buildAgentRuntimeDeliveryPlan`、`buildAgentRuntimeAuthPlan`、`normalizeAgentRuntimeTools`，说明这里把 auth、delivery、outcome、tool policy、runtime model/config 等统一成 plan。

`src/agents/sandbox` 根据名称推断负责 agent 运行沙箱、文件系统或执行权限上下文。

`src/agents/schema` 放通用 schema helper，例如 `stringEnum`、`optionalStringEnum`、`channelTargetSchema`、Gemini schema 清理等，服务工具定义和 provider 兼容。

`src/agents/skills` 根据目录名推断负责 agent skill 的发现、过滤或注入，和 `agent-scope.ts` 中 `resolveAgentSkillsFilter` 等配置解析相关。

`src/agents/test-helpers` 放测试夹具和快速 stub，例如 agent message fixture、fast bash/coding/openclaw tools、sandbox context、subagent gateway、usage fixtures 等。

`src/agents/tools` 是 OpenClaw agent 可用工具的集中实现区，包含 session/subagent、message、gateway、cron、web search/fetch、image/video/music/pdf/tts、nodes、update plan、heartbeat、agents list 等工具。它有自己的 `AGENTS.md`，说明工具层有独立约束。

## 关键入口

`src/agents/agent-command.ts` 是命令级主入口之一。它导出 `agentCommand` 和 `agentCommandFromIngress`，内部可见 `resolveAgentRunContext`、`runWithModelFallback`、`attemptExecutionRuntime.runAgentAttempt`、attempt lifecycle callback 等关键节点。阅读它可以理解一次外部请求如何进入 agent 执行、如何处理模型 fallback、如何收尾生命周期事件。

`src/agents/harness/selection.ts` 是 harness 选择和执行入口。它导出 `selectAgentHarness`、`runAgentHarnessAttempt`、`maybeCompactAgentHarnessSession`，并连接 builtin PI、v2 harness、policy、registry。它回答“这次请求到底由哪个 runtime 跑”。

`src/agents/cli-runner.ts` 是 CLI 后端执行入口，导出 `runCliAgent`、`runPreparedCliAgent`、`runClaudeCliAgent`。它串起 prepare、before-agent hooks、prompt 输入、CLI 执行、LLM input/output hook、agent end hook 等流程。

`src/agents/cli-runner/prepare.ts` 和 `src/agents/cli-runner/execute.ts` 是 CLI runner 的两段式核心：前者生成 `PreparedCliRunContext`，后者执行 `executePreparedCliRun`。

`src/agents/openclaw-tools.ts` 是工具装配入口，导出 `createOpenClawTools`，内部会组合 `src/agents/tools/*` 下的具体工具。

`src/agents/system-prompt.ts` 是系统提示词入口，导出 `buildAgentSystemPrompt`、`buildAgentBootstrapSystemContext`、`appendAgentBootstrapSystemPromptSupplement`、`buildRuntimeLine` 等。它决定 agent 看到的运行规则、runtime 信息、工具说明和 bootstrap 上下文。

`src/agents/agent-scope.ts` 是 agent/session/model scope 的配置解析入口，包含 session agent id、模型 primary/fallback、subagent model config、workspace 到 agent id 映射等逻辑。

`src/agents/agent-runtime-config.ts` 和 `src/agents/runtime-plan/*` 是运行时配置与计划层入口，适合理解 provider runtime handle、auth plan、delivery plan、tool policy 如何进入执行。

## 主流程位置

主流程可以按“入口到执行器”理解：上层 ingress 调用 `src/agents/agent-command.ts` 的 `agentCommand` 或 `agentCommandFromIngress`；命令层解析 run context、agent scope、模型配置、fallback 策略和 lifecycle callback；随后通过 attempt execution runtime 进入具体执行路径。

执行路径再分两类。第一类是 harness 路径：`src/agents/harness/selection.ts` 根据 runtime policy、provider runtime config、注册表和 builtin PI 支持，选择合适的 `AgentHarness`，再调用 `runAgentHarnessAttempt`。harness 过程中会经过 hook context、LLM input/output hook、agent end hook、tool result middleware、context engine lifecycle 等辅助模块。

第二类是 CLI 路径：`src/agents/cli-runner.ts` 调用 `prepareCliRunContext` 准备工作区、提示词、认证、图片输入、MCP bundle、session history，然后用 `executePreparedCliRun` 启动对应 CLI，并处理无输出超时、supervisor、复用 session、hook 回调和最终结果。

工具主流程位于 `src/agents/openclaw-tools.ts` 与 `src/agents/tools`。前者创建工具清单，后者实现具体工具行为；工具 schema 辅助在 `src/agents/schema`，工具权限、展示、错误摘要、mutation 检测、loop detection、filesystem policy 等横切能力则分布在根部 `tool-*.ts`、`bash-tools*.ts`、`channel-tools.ts` 等文件中。

上下文和提示词主流程位于 `src/agents/system-prompt.ts`、`src/agents/context*.ts`、`src/agents/compaction.ts`、`src/agents/bootstrap-*.ts` 以及 `src/agents/harness/context-engine-lifecycle.ts`。这些文件决定 agent 每轮能看到什么、何时压缩、如何补充 bootstrap 文件与运行环境信息。

## 推荐阅读顺序

1. 先读 `src/agents/AGENTS.md`，理解这个目录最重要的性能和架构约束：不要在热路径随意加载完整插件、通道或 provider runtime。

2. 再读 `src/agents/agent-command.ts`，抓住 agent 请求的总入口、attempt 生命周期、模型 fallback 和 ingress 形状。

3. 接着读 `src/agents/harness/types.ts`、`src/agents/harness/registry.ts`、`src/agents/harness/selection.ts`，建立 `AgentHarness` 抽象和 runtime 选择模型。

4. 如果关注外部 CLI agent，再读 `src/agents/cli-runner.ts`、`src/agents/cli-runner/prepare.ts`、`src/agents/cli-runner/execute.ts`、`src/agents/cli-runner/helpers.ts`。

5. 如果关注工具能力，再读 `src/agents/openclaw-tools.ts`，然后只挑 `src/agents/tools` 中与目标功能相关的工具，例如 session、web、media、gateway、message，不需要逐个叶子展开。

6. 最后补读 `src/agents/system-prompt.ts`、`src/agents/agent-scope.ts`、`src/agents/runtime-plan/build.ts`、`src/agents/runtime-plan/auth.ts`、`src/agents/runtime-plan/tools.ts`，理解配置、提示词、运行计划如何在执行前合并。

## 常见误区

不要把 `src/agents` 理解成单纯的“调用大模型 API”目录。模型请求只是其中一环；这里更大的职责是 agent 回合编排、运行时选择、工具注入、认证、上下文、会话和生命周期管理。

不要把 `src/agents/tools` 当作全部工具系统。具体工具实现集中在那里，但工具策略、展示、权限、bash process、filesystem policy、工具调用 ID、tool catalog 等支撑逻辑大量位于 `src/agents` 根部。

不要在阅读时逐文件扫根目录。该目录文件数量很大，overview 阶段应围绕 `agent-command.ts`、`harness/selection.ts`、`cli-runner.ts`、`openclaw-tools.ts`、`system-prompt.ts`、`agent-scope.ts` 建图，再按问题深入。

不要忽略 harness 与 CLI runner 的区别。`harness` 是 OpenClaw 内部抽象的 agent 执行器选择层；`cli-runner` 更偏向外部命令行后端的准备和进程执行。两者会在生命周期 hook、prompt、工具和结果处理上交汇，但关注点不同。

不要在热路径为了判断通道、插件或 provider 能力而直接加载完整 runtime。`src/agents/AGENTS.md` 明确把这类冷加载视为性能和架构信号；如果只需要静态路由、schema 或 capability，应找轻量 helper 或 typed artifact。

不要把 `auth-profiles` 看成普通配置文件读写。它涉及 OAuth、外部 CLI 同步、profile 顺序、cooldown、credential state、doctor/repair 和运行时契约，修改时会影响升级和已有用户状态。
