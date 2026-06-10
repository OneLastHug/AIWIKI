# 目录：packages/desktop/src/renderer/hooks/mcp

## 它负责什么

`packages/desktop/src/renderer/hooks/mcp` 是 renderer 层 MCP 功能的 Hook 与轻量工具集合，主要服务于“工具 / MCP 服务器设置页”和“会话创建时的 MCP 选择”。它不直接实现 MCP 协议，也不负责启动本地进程、建立真实 stdio/http/sse 连接；这些能力通过 `packages/desktop/src/common/adapter/ipcBridge.ts` 暴露的 `mcpService` 访问后端接口，例如 `/api/mcp/servers`、`/api/mcp/test-connection`、`/api/mcp/oauth/*`。

从当前片段看，这个目录承担三类职责：第一，管理 MCP server 列表、增删改、批量导入、启停等前端状态；第二，封装连接测试与 OAuth 登录状态等异步操作；第三，为会话发送链路提供 MCP catalog / session server 形态转换。它更像 renderer 的 MCP “应用层适配器”，把页面组件从 IPC/API 细节、加载状态、错误提示和局部 UI 状态中解耦出来。

## 直接子目录地图

该目录当前没有直接子目录，只有一组平铺文件：

`packages/desktop/src/renderer/hooks/mcp/index.ts` 是聚合出口，通常用于统一导出本目录 Hook 和工具。

`packages/desktop/src/renderer/hooks/mcp/catalog.ts` 处理 MCP catalog 或内置 MCP server 的前端形态转换。已知 `packages/desktop/src/renderer/pages/guid/hooks/useGuidSend.ts` 会从这里导入 `toSessionMcpServer`，用于把被选中的 MCP server 快照写入发送参数。

`packages/desktop/src/renderer/hooks/mcp/useMcpServers.ts` 根据命名推断是 MCP server 列表读取与刷新入口，面向设置页或选择器提供服务器集合状态。

`packages/desktop/src/renderer/hooks/mcp/useMcpServerCRUD.ts` 根据命名推断封装服务器创建、更新、删除、导入、启停等变更操作。底层对应 `ipcBridge.mcpService` 中的 `createServer`、`updateServer`、`deleteServer`、`toggleServer`、`batchImportServers` 等接口。

`packages/desktop/src/renderer/hooks/mcp/useMcpConnection.ts` 根据命名推断封装“测试 MCP 连接 / 可用性检查”相关状态。后端入口在 `ipcBridge.mcpService.testConnection`，设置页里 `McpServerHeader.tsx` 会展示测试中、手动检查通过、检查失败、需要登录等状态。

`packages/desktop/src/renderer/hooks/mcp/useMcpOAuth.ts` 负责 OAuth MCP server 的认证状态检查、登录、登出等前端动作。`packages/desktop/src/renderer/pages/settings/ToolsSettings/McpServerHeader.tsx` 已导入其类型 `McpOAuthStatus`，说明它直接影响 MCP server 卡片或标题区域的登录按钮与状态显示。

`packages/desktop/src/renderer/hooks/mcp/useMcpModal.ts` 根据命名推断维护 MCP 设置相关弹窗状态，例如新增、编辑、导入 JSON、一键导入等 UI 交互。

`packages/desktop/src/renderer/hooks/mcp/messageQueue.ts` 根据命名推断是消息提示队列或通知节流工具，用来避免多个异步操作同时触发重复 toast/message。证据不足，具体行为需阅读该文件确认。

## 关键入口

最值得先看的入口是 `index.ts`。它决定外部页面通过哪些稳定 API 使用 MCP hooks，也能快速看出哪些文件是公共接口、哪些只是内部辅助。

业务入口主要在设置页：`packages/desktop/src/renderer/pages/settings/CapabilitiesSettings.tsx` 把 tools tab 展示为 MCP & Voice；MCP server 的具体 UI 位于 `packages/desktop/src/renderer/pages/settings/ToolsSettings/`。其中 `McpServerHeader.tsx` 与本目录的 OAuth / connection 状态有明确关联，`mcpJsonImport.ts` 则负责解析用户粘贴的 MCP JSON，解析后的导入动作大概率会交给本目录 CRUD hook 或相关页面状态处理。

另一个关键入口是会话发送链路：`packages/desktop/src/renderer/pages/guid/hooks/useGuidSend.ts` 使用 `catalog.ts` 的 `toSessionMcpServer`，并把 `selected_mcp_server_ids`、`selected_session_mcp_servers` 写进发送参数。对应类型和持久化快照可以在 `packages/desktop/src/common/adapter/ipcBridge.ts`、`packages/desktop/src/common/config/storage.ts` 中看到。

后端通信入口集中在 `packages/desktop/src/common/adapter/ipcBridge.ts` 的 `mcpService`。阅读本目录时，应把它视作所有 MCP 服务端数据的边界：renderer hook 负责组织调用和状态，真实数据源在 `/api/mcp/*` 后面。

## 主流程位置

设置页管理流程大致是：用户进入 `CapabilitiesSettings.tsx` 的 tools tab，页面加载 MCP server 列表；列表和卡片组件通过 `useMcpServers` 获取当前服务器，通过 `useMcpServerCRUD` 执行新增、编辑、删除、导入、启用/禁用；当用户点击测试连接时，`useMcpConnection` 调用 `mcpService.testConnection`，再把结果映射成 “testing / passed / failed / login required” 等 UI 状态；如果 server 需要 OAuth，则 `useMcpOAuth` 负责检查认证状态并触发登录或登出。

导入流程有两条线索：一条是 JSON 导入，`ToolsSettings/mcpJsonImport.ts` 解析用户粘贴的 `mcpServers` 配置，校验 stdio 必须有 `command`、http/sse 必须有 `url`，然后交给 MCP service 批量导入；另一条是 CLI 扫描/一键导入，对应 `ipcBridge.mcpService` 中的 import endpoint 和设置页文案。根据当前片段推断，本目录的 CRUD hook 是这两类导入结果进入全局 MCP server 仓库的前端动作层。

会话使用流程与设置页不同：`useGuidSend.ts` 在发送前读取用户选中的 MCP server，普通用户服务器以 `selected_mcp_server_ids` 传递；内置或 session-scoped MCP server 则通过 `toSessionMcpServer` 转成 `selected_session_mcp_servers`。这样会话创建时可以保存一份 MCP server 快照，后续在 `storage.ts` 中也能看到 `mcp_server_ids`、`mcp_servers`、`mcp_statuses`、`session_mcp_servers` 这些会话级字段。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/renderer/hooks/mcp/index.ts`，确认这个目录对外暴露的 API 名称。
2. 再读 `packages/desktop/src/common/adapter/ipcBridge.ts` 里的 `mcpService`，建立“前端 hook 调哪些后端接口”的边界感。
3. 接着读 `useMcpServers.ts` 和 `useMcpServerCRUD.ts`，理解列表状态与增删改导入动作如何组合。
4. 然后读 `useMcpConnection.ts`、`useMcpOAuth.ts`，把连接测试和认证状态补上。
5. 读 `useMcpModal.ts`、`messageQueue.ts`，理解 UI 弹窗状态和提示消息如何被集中管理。
6. 最后读 `catalog.ts`，并对照 `packages/desktop/src/renderer/pages/guid/hooks/useGuidSend.ts`，理解 MCP server 如何从设置仓库进入会话发送参数。

## 常见误区

不要把这个目录理解为 MCP 协议实现层。它在 `renderer/hooks` 下，职责是 React Hook、前端状态和 UI 操作封装；真实 MCP 连接、协议握手、stdio 进程、OAuth 后端处理都不应该在这里找。

不要只看设置页流程而忽略会话流程。MCP server 不只是“配置项”，还会在创建会话时被选中、快照化，并通过 `selected_mcp_server_ids` 或 `selected_session_mcp_servers` 传给后续运行链路。

不要把手动测试连接状态等同于会话运行时状态。设置页中展示的 “manual check passed / failed” 更像最近一次配置可用性检查；会话中的工具注入和调用状态还有独立链路，相关字段散落在 conversation storage、team MCP 注入状态和工具调用展示逻辑中。

不要在本目录硬编码用户可见文案。项目要求用户界面文本走 i18n；MCP 相关文案能在 `packages/desktop/src/renderer/services/i18n/locales/*/mcp.json`、`settings.json`、`tools.json` 中看到。新增页面提示或错误文案时，应同步走 i18n，而不是直接写在 hook 或组件里。
