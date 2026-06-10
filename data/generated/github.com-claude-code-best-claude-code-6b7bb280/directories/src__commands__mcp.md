# 目录：src/commands/mcp

## 它负责什么

`src/commands/mcp` 是 MCP 管理功能的“命令入口层”，主要承担两类入口的薄封装：

一类是交互式 REPL 里的 `/mcp` slash command。它通过 `src/commands/mcp/index.ts` 注册为 `local-jsx` 命令，再由 `src/commands/mcp/mcp.tsx` 根据参数渲染 MCP 设置界面、重连界面，或执行启用/禁用操作。

另一类是 shell CLI 里的 `claude mcp ...` 子命令中一部分被拆出的注册逻辑。`src/commands/mcp/addCommand.ts` 专门注册 `claude mcp add`，负责把命令行参数转换成 MCP server 配置并写入对应 scope；`src/commands/mcp/xaaIdpCommand.ts` 专门注册 `claude mcp xaa ...`，负责 XAA/SEP-990 IdP 连接的 setup、login、show、clear。

这个目录不实现 MCP 协议连接、工具发现、资源拉取、server health check 或运行期 client 管理。那些能力主要在 `src/services/mcp/*`、`src/components/mcp/*`、`src/main.tsx` 和 CLI handler 层完成。可以把本目录理解为“用户命令到 MCP 管理能力之间的路由和参数整理层”。

## 直接子目录地图

当前 `src/commands/mcp` 没有直接子目录，只有四个顶层文件：

`src/commands/mcp/index.ts` 是 slash command 元数据入口，声明命令名 `mcp`、描述、参数提示、是否 immediate，以及动态加载 `./mcp.js`。

`src/commands/mcp/mcp.tsx` 是 `/mcp` 的 JSX 命令实现，面向交互式终端 UI。

`src/commands/mcp/addCommand.ts` 是 `claude mcp add` 的 Commander 注册模块，面向非交互式 shell CLI。

`src/commands/mcp/xaaIdpCommand.ts` 是 `claude mcp xaa` 的 Commander 注册模块，只有在 `isXaaEnabled()` 为真时才会被 `src/main.tsx` 注册。

## 关键入口

交互式入口是 `src/commands/mcp/index.ts`。它导出默认的 `mcp` command 对象，`type` 为 `local-jsx`，`name` 为 `mcp`，`load` 使用动态 import 加载 `src/commands/mcp/mcp.tsx`。这说明 `/mcp` 不是普通文本命令，而是会返回 React/Ink 节点的本地 UI 命令。

`src/commands/mcp/mcp.tsx` 暴露 `call(onDone, _context, args)`。这是 `/mcp` 被触发后的主要分发函数。它识别几种参数形态：`/mcp no-redirect` 直接打开旧的 `MCPSettings`；`/mcp reconnect <server>` 渲染 `MCPReconnect`；`/mcp enable [server-name]` 和 `/mcp disable [server-name]` 走 `MCPToggle`。没有参数时，如果 `process.env.USER_TYPE === 'ant'`，会跳到 `PluginSettings` 的 manage 视图，并传入 `showMcpRedirectMessage`；否则打开 `MCPSettings`。

CLI 入口在 `src/main.tsx` 的 `claude mcp` 注册段。这里创建 Commander 子命令 `mcp`，注册 `serve`，调用 `registerMcpAddCommand(mcp)`，在 XAA 开启时调用 `registerMcpXaaIdpCommand(mcp)`，并继续注册 `remove`、`list`、`get`、`add-json`、`add-from-claude-desktop`、`reset-project-choices` 等子命令。其中 `add` 和 `xaa` 的细节就在本目录，其余子命令根据当前片段推断主要委托给 `./cli/handlers/mcp.js`，依据是 `src/main.tsx` 中多处动态 import handler 并调用 `mcpRemoveHandler`、`mcpListHandler`、`mcpGetHandler` 等函数。

## 主流程位置

`/mcp` 的主流程从 command registry 进入 `src/commands/mcp/index.ts`，再加载 `src/commands/mcp/mcp.tsx` 的 `call()`。如果是 UI 管理流程，核心界面不在本目录，而在 `src/components/mcp/index.js` 导出的 `MCPSettings`；如果是重连，进入 `src/components/mcp/MCPReconnect.js`；如果是启用/禁用，`MCPToggle` 会读取 `useAppState(s => s.mcp.clients)`，过滤掉名为 `ide` 的 client，然后调用 `useMcpToggleEnabled()` 返回的 `toggleMcpServer`。因此 `/mcp enable/disable` 的实际状态切换逻辑位于 `src/services/mcp/MCPConnectionManager.js` 一侧，本目录只负责找到目标 server 并触发切换。

`claude mcp add` 的主流程位于 `src/commands/mcp/addCommand.ts` 的 `registerMcpAddCommand()`。它用 Commander 定义参数 `<name> <commandOrUrl> [args...]`，并支持 `--scope`、`--transport`、`--env`、`--header`、OAuth 相关参数和 `--xaa`。action 中先通过 `ensureConfigScope()`、`ensureTransport()` 规范化输入，再按 `stdio`、`sse`、`http` 三类 transport 构造 server config，最后调用 `addMcpConfig()` 写入配置。OAuth client secret 会通过 `readClientSecret()` 读取，并用 `saveMcpClientSecret()` 保存。这个文件还会记录 `tengu_mcp_add` analytics，并对“URL 被当作 stdio command”这类高频误用给出 warning。

`claude mcp xaa` 的主流程位于 `src/commands/mcp/xaaIdpCommand.ts` 的 `registerMcpXaaIdpCommand()`。它下面有 `setup`、`login`、`show`、`clear`。`setup` 校验 issuer URL、callback port 和可选 client secret，然后通过 `updateSettingsForSource('userSettings', { xaaIdp: ... })` 写入非密钥配置，并用 keychain 相关函数保存或清理 secret/token。`login` 要求已配置 IdP，可走浏览器 OIDC 登录，也可通过 `--id-token` 直接缓存 JWT。`show` 展示当前 IdP 配置和 secret/token 是否存在，`clear` 清理 settings 与 keychain 缓存。

运行期 MCP server 的加载、连接、工具注入并不从本目录开始。`src/main.tsx` 在主 CLI action 中会处理 `--mcp-config`、配置合并、enterprise/project/user/local scope、`getMcpToolsCommandsAndResources()`、`prefetchAllMcpResources()`、AppState 中 `mcp.clients/tools/commands/resources` 的填充等。阅读时应把“配置命令”与“运行期连接”分开看。

## 推荐阅读顺序

先读 `src/commands/mcp/index.ts`，确认 `/mcp` 是一个 immediate 的 `local-jsx` command，而不是普通字符串命令。

再读 `src/commands/mcp/mcp.tsx`，理解交互式 `/mcp` 的几个分支：旧设置页、插件管理页重定向、重连、启用、禁用。这里可以顺手记住 `MCPSettings`、`MCPReconnect`、`useMcpToggleEnabled` 三个外部依赖，它们才是 UI 和状态操作的主体。

然后读 `src/main.tsx` 中 `claude mcp` 的注册段，建立 shell CLI 子命令总览。这里能看到本目录只接管 `add` 和可选的 `xaa`，其他子命令委托 handler。

接着读 `src/commands/mcp/addCommand.ts`，重点看 transport 分支如何生成 `stdio`、`sse`、`http` 配置，以及 scope、env、headers、OAuth secret 的处理方式。

最后读 `src/commands/mcp/xaaIdpCommand.ts`。这个文件和普通 MCP add 相比更偏认证生命周期，建议带着 `src/services/mcp/xaaIdpLogin.js`、`src/services/mcp/auth.js`、`src/utils/settings/settings.js` 的职责去理解，但 overview 阶段不必深入协议细节。

## 常见误区

不要把 `/mcp` 和 `claude mcp` 当成同一个入口。`/mcp` 是 REPL 内的 JSX command，主要展示或操作当前会话中的 MCP 状态；`claude mcp ...` 是 shell CLI 子命令，主要管理配置、启动 MCP server 或做 health/detail 类操作。

不要以为 `src/commands/mcp` 负责 MCP 协议通信。真正连接 server、发现 tools/resources、维护 client 状态的逻辑在 `src/services/mcp/*` 和启动主流程里。本目录最多调用服务层函数或渲染组件。

不要忽略 `USER_TYPE === 'ant'` 的重定向逻辑。普通 `/mcp` 在 ant 用户环境下默认进入 `PluginSettings` 的 manage 视图，而不是旧的 `MCPSettings`。需要测试旧 UI 时，代码里保留了 `/mcp no-redirect`。

不要把 `claude mcp add` 的默认 transport 理解成自动识别 URL。代码中 `ensureTransport()` 后默认倾向 `stdio`；如果命令看起来像 URL 但没有显式 `--transport http` 或 `--transport sse`，只会 warning，不会自动改成远程 transport。

不要把 XAA 视为每个 MCP server 自己的普通 OAuth secret。`xaaIdpCommand.ts` 的注释和实现都表明，IdP 连接是 user-level 配置，保存在 `settings.xaaIdp` 与按 issuer 区分的 keychain slot 中；而单个 HTTP/SSE MCP server 的 client secret 走 `saveMcpClientSecret()`，是另一套信任域。
