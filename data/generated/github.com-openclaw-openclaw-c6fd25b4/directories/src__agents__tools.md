# 子系统：src/agents/tools

## 解决什么问题

`src/agents/tools` 是 OpenClaw agent 的“工具工厂层”。它把模型可调用的能力包装成统一的 `AgentTool` 形态，让 agent 在一次运行中可以发送消息、查询/管理会话、调用 gateway、搜索/抓取网页、生成或处理媒体、更新计划、查看状态、启动子会话等。这个目录本身不负责主循环，也不直接决定模型如何思考；它负责把外部系统和内部运行时能力变成安全、可描述、可门控的工具接口。

从 `src/agents/openclaw-tools.ts` 看，上层通过 `createOpenClawTools()` 组合这些工具。该函数根据当前会话、配置、sandbox、模型能力、插件 allow/deny、embedded 模式、web 工具运行时元数据等条件，决定哪些工具进入最终工具列表，并在返回前可统一包一层 `before_tool_call` hook，用于循环检测、上下文注入和调用前策略。

## 相关目录和文件

核心入口在 `src/agents/openclaw-tools.ts`，它导入并组合 `src/agents/tools/*-tool.ts` 中的工具工厂。`src/agents/tools/common.ts` 提供参数读取、返回值封装、图片结果封装、action gate 等共享基础设施。`src/agents/tools/gateway.ts` 和 `src/agents/tools/gateway-tool.ts` 负责把工具调用转为 gateway RPC，并处理 `gatewayUrl`、token、operator scope、approval runtime token 等安全边界。

会话相关文件包括 `sessions-list-tool.ts`、`sessions-history-tool.ts`、`sessions-send-tool.ts`、`sessions-spawn-tool.ts`、`sessions-yield-tool.ts`、`sessions-access.ts`、`sessions-resolution.ts`、`sessions-helpers.ts`。这些文件共同处理会话可见性、current/main alias 解析、sandbox 上下文、A2A 发送、子会话启动和会话列表格式化。

消息和渠道相关能力集中在 `message-tool.ts`、`nodes-tool.ts`、`nodes-tool-commands.ts`、`nodes-utils.ts`。网页能力通过 `web-tools.ts` 重新导出 `web-search.ts` 和 `web-fetch.ts`，并配套 `web-tool-runtime-context.ts`、`web-search-provider-*`、`web-fetch-*` 处理 provider 配置、凭据、缓存、SSRF/guarded fetch、可见性等。媒体能力包括 `image-tool.ts`、`image-generate-tool.ts`、`video-generate-tool.ts`、`music-generate-tool.ts`、`tts-tool.ts`、`pdf-tool.ts` 以及一组 `media-*shared*` 文件。

## 核心对象

最核心的抽象是 `AnyAgentTool` / `AgentToolResult` 一类工具对象和返回对象，定义在 `common.ts` 及其导入类型周边。每个 `createXxxTool()` 通常返回一个带 `name`、描述、参数 schema 和执行函数的工具；执行函数会把模型输入先通过 `readStringParam`、`readNumberParam`、`asToolParamsRecord` 等工具归一化，再调用对应运行时。

`createOpenClawTools()` 是工具装配器。它接收 `agentSessionKey`、`runSessionKey`、`agentChannel`、`agentTo`、`agentThreadId`、`workspaceDir`、`sandboxRoot`、`fsPolicy`、`authProfileStore`、`modelProvider`、`modelId`、`pluginToolAllowlist` 等上下文，把这些上下文分发给各个工具工厂。

`callGatewayTool()` 是 gateway 类工具的关键边界对象。它不只是简单转发 RPC，还会验证 override URL 只能指向允许的 loopback gateway 或配置好的 remote gateway，并为方法解析最小 operator scopes。根据当前片段推断，这是防止模型通过工具任意连接 gateway 或越权调用 operator API 的主要保护层之一。

## 运行流程

一次典型流程是：agent 运行层调用 `createOpenClawTools()`；该函数先解析配置、运行时 secrets snapshot、session agent id、workspace、delivery context、runtime web tools metadata；然后按能力创建核心工具，例如 `message`、`nodes`、`cron`、`gateway`、`agents_list`、`sessions_*`、`session_status`、`web_search`、`web_fetch`、媒体工具等。

之后，装配器根据 embedded 模式和策略裁剪工具。例如 embedded 模式下会跳过部分 gateway/cron/nodes 类能力；消息工具可能因 `sourceReplyDeliveryMode` 或显式 allowlist 被保留；媒体工具通过 `resolveOptionalMediaToolFactoryPlan()` 和具体 provider/auth 条件决定是否可用。核心工具列表创建完成后，如果没有 `disablePluginTools`，还会调用 `resolveOpenClawPluginToolsForOptions()` 加入插件工具，并避免与已有工具名冲突。最后默认用 `wrapToolWithBeforeToolCallHook()` 包装工具，加入 agent、session、channel 和 loop detection 上下文。

具体工具执行时，模型传入 JSON 参数，工具先做类型读取和归一化，再调用下游：消息工具走渠道/消息发送逻辑，会话工具走 gateway 或 session registry，网页工具走 provider/fetch runtime，媒体工具走 provider 生成任务或文件处理，gateway 工具走 `callGateway()`。

## 上下游依赖

上游主要是 agent 运行时、嵌入式 runner、自动回复流程和插件工具装配逻辑，代表文件包括 `src/agents/openclaw-tools.ts`、`src/agents/pi-tools.before-tool-call.ts`、`src/agents/openclaw-plugin-tools.ts`。这些上游只关心最终工具列表，不应知道每个工具的内部 provider 实现。

下游包括 `src/gateway/*`、`src/sessions/*`、`src/config/*`、`src/secrets/*`、`src/channels/*`、`src/plugins/*`、`src/plugin-sdk/*`、模型/媒体 provider 相关模块，以及 workspace/sandbox/fs policy。工具层是这些系统暴露给模型的边界，所以参数 schema、默认值、错误文本和权限门控都会直接影响模型行为与用户可见结果。

测试主要在同目录 `*.test.ts`，另有 `src/agents/openclaw-tools.sessions.test.ts`、`src/agents/openclaw-tools.image-generation.test.ts` 等组合层测试。目录内 `AGENTS.md` 强调工具测试不要为了静态描述加载完整 channel/plugin runtime，说明这里的性能和导入边界也是架构约束。

## 修改时最容易踩的坑

第一，不能把静态 schema 或 capability 判断写成加载完整插件/渠道运行时。`src/agents/tools/AGENTS.md` 明确要求 message-tool discovery 走轻量共享 artifact，测试也不应直接导入 bundled plugin 内部。

第二，工具参数是模型面对的协议。随意改字段名、默认值、enum 或错误行为，可能破坏 provider、channel、gateway、插件或 prompt snapshot。新增/删除参数时要同步 schema、测试和组合入口。

第三，会话工具有 sandbox、visibility、current/main alias、A2A policy 等多层语义。只改 `sessions-send-tool.ts` 或 `sessions-spawn-tool.ts` 的单点逻辑，容易绕过 `sessions-access.ts`、`sessions-resolution.ts` 中的可见性和身份解析。

第四，gateway 工具是安全边界。不要放宽 `gatewayUrl` 校验，不要跳过 operator scopes，也不要把 token、approval runtime token 暴露进日志或结果。

第五，媒体和 web 工具强依赖 provider 配置、auth profile、runtime metadata、sandbox/fs policy。根据当前片段推断，显式模型配置会影响 provider fallback，例如 `image-generate-tool.ts` 会区分 explicit model config 和自动 fallback；修改时必须覆盖 provider fallback、凭据和沙箱路径测试。

## 推荐阅读顺序

1. 先读 `src/agents/openclaw-tools.ts`，理解工具列表如何被创建、裁剪、插件扩展和 hook 包装。
2. 再读 `src/agents/tools/common.ts`，掌握参数读取、结果封装和共享工具约定。
3. 然后读 `src/agents/tools/message-tool.ts`、`src/agents/tools/gateway.ts`，这两个最能体现渠道发送和 gateway 安全边界。
4. 接着读 `src/agents/tools/sessions-helpers.ts`、`sessions-access.ts`、`sessions-resolution.ts`，再看具体 `sessions-*-tool.ts`。
5. 最后按目标能力阅读 `web-search.ts` / `web-fetch.ts`、`image-generate-tool.ts`、`pdf-tool.ts`、`nodes-tool.ts` 等具体工具，并配套看同名测试文件。
