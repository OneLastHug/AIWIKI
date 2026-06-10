# 子系统：src/services/mcp

## 解决什么问题

`src/services/mcp` 是 Claude Code 内部的 MCP（Model Context Protocol）接入层，负责把外部 MCP Server 变成 CLI 可用的工具、命令、资源和交互能力。它解决的核心问题不是“实现某个工具”，而是统一管理多来源 MCP 配置、建立不同传输协议的连接、处理认证和权限、发现远端能力，并把这些能力注入到主对话循环和 Ink UI 状态中。

从代码结构看，这个目录承担四类职责：配置聚合与校验、连接生命周期管理、MCP 能力发现与调用适配、扩展交互协议支持。这里的扩展交互包括 OAuth 登录、IDE/VSCode SDK MCP、Claude.ai connector 代理、channel 消息注入、channel 权限回传、elicitation 表单/URL 请求等。根据当前片段推断，它是“工具系统”和“外部上下文系统”的桥梁：MCP Server 对外暴露协议能力，Claude Code 则把这些能力包装成 `Tool`、`Command`、`ServerResource`，再交给模型和界面使用。

## 相关目录和文件

`src/services/mcp/types.ts` 定义配置 schema、传输类型、连接状态和资源类型，是阅读本目录的入口。它用 `zod` 描述 `stdio`、`sse`、`http`、`ws`、`sdk`、`claudeai-proxy` 等服务器配置，并定义 `MCPServerConnection` 联合类型，包括 `connected`、`failed`、`needs-auth`、`pending`、`disabled`。

`src/services/mcp/config.ts` 负责读取和合并 MCP 配置。它处理 `user`、`project`、`local`、`enterprise`、`dynamic`、`claudeai`、`managed` 等 scope，支持 `.mcp.json`、全局配置、项目配置、企业托管配置、插件 MCP、Claude.ai connectors，并执行去重、策略过滤、启停状态判断。

`src/services/mcp/client.ts` 是协议客户端核心。它创建 MCP SDK `Client`，按配置选择 `StdioClientTransport`、`SSEClientTransport`、`StreamableHTTPClientTransport`、WebSocket、SDK 控制传输或 Claude.ai proxy transport；连接后拉取 tools、prompts、resources，并把远端 tool 包装成内置 `MCPTool`。

`src/services/mcp/MCPConnectionManager.tsx` 和 `src/services/mcp/useManageMCPConnections.ts` 是 React/Ink 侧的连接管理层。它们把连接、重连、启停、通知监听和 AppState 更新封装成 context hook，供 `/mcp` UI、插件 UI、REPL 等组件调用。

`src/services/mcp/auth.ts` 管理远端 MCP OAuth，包括 `ClaudeAuthProvider`、`performMCPOAuthFlow`、token 存储、刷新、撤销、step-up scope 检测，以及 XAA 相关登录流程。`headersHelper.ts` 负责动态 header 构建，`envExpansion.ts` 负责配置中的环境变量展开。

`channelNotification.ts`、`channelPermissions.ts`、`channelAllowlist.ts` 处理“频道型 MCP Server”：服务器可以把外部消息注入对话，也可以把工具权限请求转发到外部 channel 并接收结构化审批结果。`elicitationHandler.ts` 则处理 MCP Server 主动向用户索取信息的 `elicitation` 请求。

`normalization.ts`、`mcpStringUtils.ts`、`utils.ts` 提供名称规范化、工具名前缀解析、按 server 过滤工具/命令/资源、scope 文案、配置 hash、日志安全 URL 等公共能力。`vscodeSdkMcp.ts` 处理 VSCode SDK MCP 的事件通知和文件变更同步。

## 核心对象

最重要的类型是 `ScopedMcpServerConfig`。它在原始 `McpServerConfig` 之外增加 `scope` 和可选 `pluginSource`，让后续连接、权限和 UI 能知道配置来源。配置来源会影响优先级、是否允许连接、是否需要用户批准，以及是否被企业策略拦截。

`MCPServerConnection` 是运行期状态模型。`connected` 持有 SDK `Client`、server capabilities、server info、instructions、cleanup 函数；`needs-auth` 表示远端认证未完成；`disabled` 表示配置存在但不会连接；`failed` 记录连接失败；`pending` 用于连接或重连过程中的临时状态。UI 和主流程都围绕这个联合类型做状态分支。

`connectToServer` 是连接入口。它按 transport 类型构造底层传输，连接 SDK client，读取 capabilities、server version、instructions，并注册错误、关闭、清理逻辑。为了避免重复连接，它使用基于 server name 和 config 的缓存 key。

`getMcpToolsCommandsAndResources` 是能力发现入口。它聚合配置，跳过 disabled server，把本地 server 和远端 server 分组并发连接，连接成功后并行调用 `fetchToolsForClient`、`fetchCommandsForClient`、`fetchResourcesForClient`。如果 server 支持 resources，它还会注入通用的 `ListMcpResourcesTool` 和 `ReadMcpResourceTool`。

`MCPConnectionManager` 和 `useManageMCPConnections` 是 UI 状态入口。它们暴露 `reconnectMcpServer` 和 `toggleMcpServer`，同时监听 MCP 的 tool/resource/prompt list changed 通知、channel 通知和 elicitation 请求，将变化批量写入 `AppState.mcp`。

## 运行流程

启动或进入 REPL 时，上层会通过 `getAllMcpConfigs` 或 `getClaudeCodeMcpConfigs` 获取 MCP 配置。配置合并的大致优先级是插件低于用户配置，用户低于项目，项目低于 local；enterprise 配置存在时具有排他控制权。Claude.ai connectors 会以较低优先级并入，并通过签名去重避免和手写配置重复。

随后 `getMcpToolsCommandsAndResources` 遍历配置。对 disabled server，它只上报 `disabled` 状态，不发起网络或子进程连接。对需要认证且近期已确认缺少 token 的远端 server，它直接上报 `needs-auth` 并提供 `McpAuthTool`，避免启动时反复探测。

正常 server 进入 `connectToServer`。`stdio` 会启动本地命令，`sse`/`http` 会附加 header、OAuth provider、代理和超时包装，`ws` 使用 WebSocket transport，`sdk` 使用内部控制传输，`claudeai-proxy` 通过 Claude.ai OAuth token 访问代理地址。连接成功后读取 server capabilities，再发现 tools、prompts、resources。

远端 tool 会被包装成符合 Claude Code `Tool` 接口的对象，命名通常带 `mcp__<server>__<tool>` 前缀。模型调用该工具时，包装层再把输入转成 MCP `tools/call` 请求，处理超时、认证失败、session 过期、结果截断、二进制结果持久化、图片缩放等细节。

运行中如果 MCP Server 发送工具、资源或 prompt 列表变更通知，`useManageMCPConnections` 会重新拉取对应能力并更新 AppState。若连接断开或 SSE 等远端连接出错，相关逻辑会清理缓存并触发重连流程。用户在 `/mcp` 或插件界面中手动启停 server 时，也会走 `setMcpServerEnabled`、`clearServerCache` 和重连路径。

## 上下游依赖

上游主要来自 `src/main.tsx`、`src/cli/handlers/mcp.tsx`、`src/cli/print.ts`、`src/screens/REPL.tsx`、`src/state/AppStateStore.ts`。主入口负责启动时预取 MCP 资源和配置；CLI handler 提供 `mcp add/remove/list/get` 等命令；REPL 通过 `MCPConnectionManager` 挂载连接管理；headless/print 模式也会处理 MCP Server 变更和权限。

下游依赖包括 `@modelcontextprotocol/sdk`、`@claude-code-best/builtin-tools` 中的 `MCPTool`、`McpAuthTool`、`ListMcpResourcesTool`、`ReadMcpResourceTool`，以及 `src/utils/mcpValidation.ts`、`src/utils/mcpOutputStorage.ts`、`src/utils/toolResultStorage.ts` 等结果处理工具。认证侧依赖 `secureStorage`、OAuth 常量、浏览器打开和本地 callback server。配置侧依赖 `src/utils/config.ts`、settings、managed policy、plugin loader。

横向依赖也很多：IDE 相关代码通过 `callIdeRpc` 和 `vscodeSdkMcp.ts` 与 MCP 通信；插件系统通过 `getPluginMcpServers` 注入 server；channel 功能与权限 prompt handler、消息队列、通知系统连接；技能系统在 `MCP_SKILLS` feature 下会从 MCP resources 中发现 skill。

## 修改时最容易踩的坑

第一，`feature()` 有 Bun 编译限制，只能直接用于 `if` 或三元条件，不要赋值给变量、放进普通表达式或 `&&` 链。这个目录里有多处 feature-gated lazy require，改动时要保持现有写法。

第二，配置合并顺序和去重规则很敏感。插件 server、手写 server、Claude.ai connector 可能指向同一个底层服务，`getMcpServerSignature`、`dedupPluginMcpServers`、`dedupClaudeAiMcpServers` 用内容签名去重。随意改优先级会导致同一工具重复暴露，增加 prompt token，甚至让用户以为启停无效。

第三，`disabled` 和 `needs-auth` 不是失败状态。disabled server 必须显示在 UI 里但不能连接；needs-auth server 要提供 `McpAuthTool`，并避免启动时反复打远端请求。把它们当 `failed` 处理会破坏用户修复路径。

第四，MCP tool 名称依赖 `normalizeNameForMCP`、`buildMcpToolName` 和 `mcpInfoFromString`。权限规则、工具过滤、agent tool selector、settings validation 都会解析这个命名格式，不能只在一处改前缀。

第五，远端连接清理很重要。`connectToServer` 注册 cleanup，并对 stdio 子进程、transport close、缓存清理和 pending request 做处理。新增 transport 或错误分支时要保证 `clearServerCache`、`cleanup`、重连状态一致，否则容易出现幽灵连接或旧 client 被复用。

第六，channel 权限不是普通聊天文本。`channelPermissions.ts` 设计为结构化通知审批，不能退化成在普通 channel 文本里用正则拦截“yes id”，否则会扩大误批准和注入风险。

## 推荐阅读顺序

1. 先读 `src/services/mcp/types.ts`，建立配置类型、scope、transport、连接状态的整体模型。
2. 再读 `src/services/mcp/config.ts` 的 `getClaudeCodeMcpConfigs`、`getAllMcpConfigs`、`parseMcpConfig`、`isMcpServerDisabled`，理解配置从哪里来、谁覆盖谁、谁会被策略过滤。
3. 接着读 `src/services/mcp/client.ts` 的 `connectToServer`、`fetchToolsForClient`、`fetchCommandsForClient`、`fetchResourcesForClient`、`getMcpToolsCommandsAndResources`，理解从 server 到 Claude Code 工具池的转换。
4. 然后读 `src/services/mcp/useManageMCPConnections.ts` 和 `MCPConnectionManager.tsx`，看连接状态如何进入 AppState 和 UI。
5. 最后按需求阅读扩展模块：认证看 `auth.ts`，channel 看 `channelNotification.ts` 和 `channelPermissions.ts`，IDE 看 `vscodeSdkMcp.ts`，名称和过滤规则看 `mcpStringUtils.ts`、`normalization.ts`、`utils.ts`。
