# 子系统：packages/desktop/src/renderer/pages/settings

## 解决什么问题

`packages/desktop/src/renderer/pages/settings` 是桌面端“设置中心”的路由页面层。它把原先可能散落在弹窗、侧栏入口、首页快捷操作中的配置能力，整理成 `/settings/*` 下的独立页面：模型供应商与模型、助手、Agent、能力中心、外观主题、WebUI、桌面宠物、系统设置和扩展设置。这个目录本身不是底层配置存储，也不是 Electron 主进程能力实现；它主要负责把设置页 UI、路由参数、表单状态、用户操作和跨进程/后端 API 调用串起来。

从路由看，`/settings` 会重定向到 `/settings/model`；`/settings/skills-hub` 和 `/settings/tools` 是旧入口，会重定向到 `/settings/capabilities?tab=skills|tools`；`/settings/display` 会重定向到 `/settings/appearance`。因此该目录还承担了一部分设置入口兼容和页面聚合职责。

## 相关目录和文件

核心页面集中在 `packages/desktop/src/renderer/pages/settings`。其中 `ModeSettings.tsx` 负责模型/平台设置；`AssistantSettings/` 负责助手列表、编辑抽屉、删除确认和技能确认；`AgentSettings/` 负责本地 Agent、远程 Agent、Agent Hub 和预设管理；`CapabilitiesSettings.tsx` 将 Skills Hub 与 MCP/工具能力合并到一个 tab 页面；`AppearanceSettings/` 包装外观设置，并包含主题预设、CSS 主题弹窗、背景工具和封面资源；`WebuiSettings.tsx`、`PetSettings.tsx`、`SystemSettings.tsx` 分别处理 WebUI、桌面宠物和系统级开关。

`ToolsSettings/` 是 MCP 设置的页面内拆分，包含 `McpManagement.tsx`、`McpServerItem.tsx`、`McpServerHeader.tsx`、`McpServerToolsList.tsx` 和 `mcpJsonImport.ts`。公共页面框架在 `components/`：`SettingsPageWrapper.tsx` 提供设置页通用外壳，`SettingsSider.tsx` 提供设置导航，多个 `*Modal.tsx` 承担新增模型、平台、MCP Server、JSON 导入、API Key 编辑等对话框。

相邻但重要的上下文包括 `packages/desktop/src/renderer/components/layout/Router.tsx` 的路由注册、`packages/desktop/src/renderer/components/layout/Sider/index.tsx` 的设置侧栏挂载、`packages/desktop/src/common/adapter/ipcBridge.ts` 的跨进程/HTTP 桥定义、`packages/desktop/src/common/config/configService.ts` 的客户端配置缓存与持久化，以及 `packages/desktop/src/process/bridge/systemSettingsBridge.ts` 的系统设置主进程实现。

## 核心对象

`SettingsPageWrapper` 是页面级布局基座。大多数设置页并不自己关心全局侧栏和滚动容器，而是把主体内容放进这个 wrapper，保持设置页在桌面端和移动端上的布局一致。

`SettingsSider` 是设置导航源。它根据内置 tab 和扩展 tab 生成侧栏项，内置项指向 `/settings/model`、`/settings/assistants`、`/settings/agent`、`/settings/capabilities`、`/settings/appearance`、`/settings/webui`、`/settings/pet`、`/settings/system` 等路径；扩展项则进入 `/settings/ext/:tabId`。

`ExtensionSettingsPage` 是扩展设置页容器。它通过 `useExtensionSettingsTabs` 查找扩展声明的设置 tab，并根据配置渲染内嵌 webview 或扩展资源页面。根据当前片段推断，扩展设置页使用独立的 webview partition，例如 `persist:ext-settings-${tab.id}`，目的是隔离扩展设置页面的会话状态。

`CapabilitiesSettings` 是能力设置聚合页。它维护 `skills` 和 `tools` 两个 tab，把 `SkillsHubSettings` 与 `ToolsModalContent` 放到同一页面，替代旧的 skills/tools 独立路由。

`AssistantSettings` 是助手管理编排层。它依赖 `useAssistantList`、`useAssistantEditor`、`useDetectedAgents`，负责列表展示、选中/高亮、编辑、复制、启停、删除和从路由或 session intent 打开指定助手。

`AgentSettings`、`RemoteAgentManagement` 和相关卡片组件负责 ACP/Agent 管理。远程 Agent 操作会走 `ipcBridge.remoteAgent`，包含 list、create、update、delete、testConnection、handshake 等流程。

## 运行流程

用户进入设置页时，`Router.tsx` 的 `HashRouter` 匹配 `/settings/*` 路由，进入对应 lazy 页面。应用外层 `Sider/index.tsx` 检测 `pathname.startsWith('/settings')` 后加载 `SettingsSider`，因此设置页左侧导航与主体路由是分开渲染的。标题栏也会识别 settings 路由，在移动端提供返回聊天等行为。

页面加载后，普通设置项通常从 `configService`、专用 hooks 或 `ipcBridge` 获取当前状态。`configService` 会从后端 `/api/settings/client` 初始化缓存，并在 `set` 时写回同一客户端设置存储。需要 Electron 主进程副作用的项，例如 close-to-tray、语言切换、keep awake、桌面宠物等，会通过 `ipcBridge.systemSettings` 到 `systemSettingsBridge.ts` 执行。MCP、Agent、助手、WebUI 等更偏业务的设置，则经 `ipcBridge` 映射到 `/api/mcp/*`、`/api/agents/*`、`/api/remote-agents/*`、`/api/assistants/*`、`/api/webui/*` 或对应主进程 provider。

## 上下游依赖

上游入口主要来自路由、首页快捷按钮和业务组件跳转。例如 `GuidModelSelector` 会跳到 `/settings/model`，`AgentPillBar` 会跳到 `/settings/agent?tab=local`，`QuickActionButtons` 会跳到 `/settings/webui`，助手选择区会跳到 `/settings/assistants`，文件附件或技能提示会跳到 `/settings/capabilities?tab=tools|skills`。

下游依赖分三类。第一类是 UI 与交互库：`@arco-design/web-react` 提供表单、按钮、Tabs、Modal 等组件，`@icon-park/react` 提供图标，`react-i18next` 提供 `settings.*` 文案。第二类是 renderer hooks 和工具：如 `useExtensionSettingsTabs`、`useTheme`、`useMcpConnection`、`useMcpServerCRUD`、`useAssistantEditor`。第三类是跨层通信：`ipcBridge`、`configService`、`httpRequest`、主进程 bridge 和后端 API 共同完成持久化与副作用。

## 修改时最容易踩的坑

第一，设置页里的用户可见文案必须走 i18n，不能直接写中文或英文常量。当前目录大量使用 `t('settings.xxx')`，新增页面、按钮、提示、错误信息时要同步补 `settings.json` 和类型。

第二，不要把 renderer 页面直接写成 Node/Electron 实现。renderer 只能通过 `ipcBridge`、hooks 或后端 API 间接调用主进程能力；涉及托盘、语言、唤醒、宠物窗口、WebUI 进程等副作用时，应检查 `packages/desktop/src/process/bridge` 和 `packages/desktop/src/common/adapter/ipcBridge.ts` 是否已有桥接。

第三，设置路由有兼容重定向。新增或迁移设置项时，不能只改页面文件，还要检查 `Router.tsx`、`SettingsSider.tsx`、标题栏/侧栏行为，以及是否有旧入口、deep link 或业务组件硬编码跳转。

第四，MCP 和 Agent 设置有本地缓存与后端状态同步问题。`mcp.config` 既可能来自 `configService`，也会通过 `/api/mcp/servers` 维护；远程 Agent 创建后还可能进入 handshake/pairing 状态。修改时要注意刷新 SWR、更新本地缓存和处理失败回滚。

第五，外观主题涉及 `theme.activeId`、`theme.userThemes`、内置 CSS preset、`ipcBridge.theme.setActive` 和运行时主题广播。只改 UI 选择器而不触发主题应用，会出现配置已保存但界面不变的情况。

## 推荐阅读顺序

先读 `packages/desktop/src/renderer/components/layout/Router.tsx`，确认 `/settings/*` 路由和旧路由重定向。然后读 `packages/desktop/src/renderer/pages/settings/components/SettingsSider.tsx` 与 `SettingsPageWrapper.tsx`，理解设置中心的导航和页面骨架。接着按业务读 `ModeSettings.tsx`、`AssistantSettings/index.tsx`、`AgentSettings/index.tsx`、`CapabilitiesSettings.tsx`、`AppearanceSettings/index.tsx`。最后再看下游桥接：`packages/desktop/src/common/adapter/ipcBridge.ts`、`packages/desktop/src/common/config/configService.ts`、`packages/desktop/src/process/bridge/systemSettingsBridge.ts`，这样能把“页面点击”如何变成“配置持久化或系统副作用”串起来。
