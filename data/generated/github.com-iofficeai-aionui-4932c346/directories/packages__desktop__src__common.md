# 目录：packages/desktop/src/common

## 它负责什么

`packages/desktop/src/common` 是桌面端代码里跨进程共享的“公共契约层”。它不属于单纯的 Electron main process，也不属于 renderer UI 层，而是把两边都需要理解的类型、配置、协议、桥接 API、主题规则、聊天数据结构、平台抽象和少量通用工具集中在一起。

从当前片段看，`common` 的核心价值有三类：第一，定义 renderer 与 process 之间共享的数据形状，例如 `TMessage`、`TChatConversation`、`Theme`、`AcpInitializeResult`、`RemoteAgentConfig`、`TeamAgent` 等；第二，提供跨进程访问后端或 Electron 能力的桥接封装，例如 `ipcBridge`、`httpRequest`、`application`、`mcpService`、`webui` 等；第三，沉淀桌面端全局配置和领域规则，例如配置存储、i18n 配置、模型能力判断、主题解析、更新类型、平台服务抽象。

可以把它理解为桌面端的“共享语言层”：`process` 负责真实系统能力和后台服务，`renderer` 负责界面与交互，而 `common` 负责让两边使用同一套 API 名称、类型定义和配置约定。

## 直接子目录地图

`packages/desktop/src/common/adapter` 是桥接适配层。这里包含 `ipcBridge.ts`、`httpBridge.ts`、`browser.ts`、`main.ts`、`registry.ts` 以及多个 mapper。`ipcBridge.ts` 体量较大，是前后端/主渲染进程共享的主要调用面；`httpBridge.ts` 负责 HTTP 请求封装；`browser.ts` 从 renderer 侧接入浏览器环境桥；`main.ts` 则更靠近主进程注册或通知类能力。mapper 文件用于在不同 API、数据库或前端模型之间转换字段。

`packages/desktop/src/common/api` 是大模型 API 客户端与协议转换区域。这里有 `OpenAIRotatingClient`、`AnthropicRotatingClient`、`GeminiRotatingClient`、`ClientFactory`、`ApiKeyManager`、`ProtocolConverter` 以及 OpenAI 到 Anthropic/Gemini 的转换器。根据当前片段推断，图像生成、聊天或内置 MCP 能力会通过这里统一适配不同供应商协议。

`packages/desktop/src/common/chat` 存放聊天领域的共享逻辑。顶层有 `chatLib.ts`、`atCommandParser.ts`、`normalizeToolCall.ts`、`imageGenCore.ts`、`sideQuestion.ts`；子目录包括 `approval`、`document`、`navigation`、`slash`。它覆盖消息结构、工具调用归一化、审批状态、文档转换、预览导航拦截、斜杠命令映射等聊天链路的公共部分。

`packages/desktop/src/common/config` 是配置中心。它包含 `configService.ts`、`storage.ts`、`configKeys.ts`、`configMigration.ts`、`storageKeys.ts`、`constants.ts`、`i18n.ts`、`i18n-config.json`、`fontSizes.ts`、`appEnv.ts`、`imageGenerationMcpEnv.ts`。这里既定义配置键和值类型，也处理配置迁移、环境感知名称、国际化语言配置和字体大小配置。

`packages/desktop/src/common/platform` 是平台服务抽象层。`IPlatformServices.ts` 定义公共接口，`ElectronPlatformServices.ts` 和 `NodePlatformServices.ts` 分别提供不同运行环境实现，`register-electron.ts` 用于在 Electron 主进程启动时注册平台服务。它的存在是为了让 common 内部代码不要直接依赖 Electron 或 Node 的具体 API。

`packages/desktop/src/common/theme` 管理主题共享规则。它包含 `types.ts`、`constants.ts`、`resolveTheme.ts`、`migrateThemeConfig.ts`，用于描述主题类型、内置浅色/深色主题标识、主题解析和旧配置迁移。

`packages/desktop/src/common/types` 是领域类型集合，按 `agent`、`channel`、`codex`、`office`、`platform`、`provider`、`team` 分组，并包含少量第三方声明文件。这里是阅读业务数据结构的主要入口，尤其是远程 Agent、ACP、Codex 模式、Office 预览、团队协作和 provider API。

`packages/desktop/src/common/update` 存放更新相关类型，包含 `updateTypes.ts` 和 `models/VersionInfo.ts`。它被 `process/bridge/updateBridge.ts` 等位置引用。

`packages/desktop/src/common/utils` 是轻量工具区，包括 `uuid` 所在的工具导出、模型能力判断、协议识别、URL 校验、平台鉴权类型、预设 Assistant 资源、构造 Agent 会话参数等。`utils/shims` 里有面向特定依赖的兼容层，例如 `xterm-headless.ts`。

## 关键入口

最重要的入口是 `packages/desktop/src/common/index.ts`。从引用看，很多位置直接 `import { ipcBridge } from '@/common'`，说明它对外暴露了最常用的桥接对象，是 renderer、process 工具函数和桥注册代码都依赖的公共入口。

第二个关键入口是 `packages/desktop/src/common/adapter/ipcBridge.ts`。它是公共调用协议的主文件，包含大量按业务域组织的 API 定义，例如 application、mcp、webui、remote agents、file snapshot、conversation、channel 等。renderer 页面、hooks、services 通过它发起动作；process 的 bridge 模块也通过同一份定义注册或调用相关能力。

第三个入口是 `packages/desktop/src/common/config/configService.ts` 与 `packages/desktop/src/common/config/storage.ts`。前者提供配置读写服务，后者定义配置数据形状、默认结构和持久化相关类型。renderer 的主题、引导页、i18n 服务以及 process 的初始化、迁移流程都会引用它们。

第四个入口是 `packages/desktop/src/common/platform/index.ts` 和 `packages/desktop/src/common/platform/register-electron.ts`。`packages/desktop/src/process/index.ts` 引入 `@/common/platform/register-electron`，说明主进程启动早期会注册 Electron 平台实现；其他 common 代码通过 `getPlatformServices()` 获取环境能力。

## 主流程位置

跨进程调用主流程大致是：renderer 侧入口 `packages/desktop/src/renderer/main.tsx` 先引入 `packages/desktop/src/common/adapter/browser.ts`，使浏览器环境具备桥接能力；业务页面、hooks 或 services 再从 `@/common` 或 `@/common/adapter/ipcBridge` 获取 API；请求经 `ipcBridge.ts`、`httpBridge.ts` 或 preload 暴露的通道传到 process；process 侧在 `packages/desktop/src/process/bridge` 下的各类 bridge 文件中处理真实逻辑，例如 `applicationBridge.ts`、`themeBridge.ts`、`webuiBridge.ts`、`updateBridge.ts`、`systemSettingsBridge.ts`。

配置主流程大致是：`storage.ts` 和 `configKeys.ts` 定义类型与键，`configService.ts` 提供读写入口，启动或升级时由 `configMigration.ts` 及 process 侧 `packages/desktop/src/process/utils/runBackendMigrations.ts` 参与迁移，renderer 侧如主题、引导页、模型选择、i18n 服务再读取这些配置。

聊天与 Agent 主流程中，`chat/chatLib.ts` 定义消息和工具调用相关结构，`chat/slash` 处理命令可用性与映射，`chat/approval` 处理权限审批状态，`types/platform/acpTypes.ts`、`types/agent/*`、`types/codex/*` 定义 Agent 协议和模式。发送会话参数时，`utils/buildAgentConversationParams.ts` 会组合 provider、model、workspace、assistant 等信息。

## 推荐阅读顺序

建议先读 `packages/desktop/src/common/index.ts`，确认公共导出面；再读 `packages/desktop/src/common/adapter/ipcBridge.ts`，把桌面端主要能力按 API 域建立地图。随后读 `packages/desktop/src/common/config/storage.ts`、`packages/desktop/src/common/config/configKeys.ts`、`packages/desktop/src/common/config/configService.ts`，理解配置系统如何被 renderer 和 process 共用。

接着阅读 `packages/desktop/src/common/types/platform/acpTypes.ts`、`packages/desktop/src/common/types/agent/*`、`packages/desktop/src/common/types/team/*`，建立主要业务实体概念。聊天相关可以从 `packages/desktop/src/common/chat/chatLib.ts` 开始，再看 `chat/slash`、`chat/approval`、`chat/navigation`。如果关注模型接入，再转到 `packages/desktop/src/common/api/ClientFactory.ts`、`RotatingApiClient.ts` 和各 provider client。最后看 `platform`、`theme`、`utils`，补齐运行环境抽象和工具规则。

## 常见误区

不要把 `common` 当成“随手放工具函数”的杂物目录。这里的代码会被 renderer 和 process 同时引用，任何引入 Electron、DOM、Node 专属 API 的改动都可能破坏另一侧运行环境。需要访问系统能力时，应优先走 `platform` 抽象或 IPC bridge。

不要绕过 `ipcBridge.ts` 私自定义一套 renderer 到 process 的调用协议。这个目录的关键职责就是集中维护共享 API 契约，分散协议会导致类型不同步、迁移困难和权限边界不清。

不要在 renderer 中直接假设配置存储结构等于 UI 状态。`config/storage.ts` 是持久化和跨进程共享结构，修改时要同时考虑迁移、默认值、i18n、主题应用和 process 启动路径。

不要把 `types` 目录看成无行为影响的声明集合。很多 mapper、bridge、数据库仓储、聊天流程都依赖这些类型表达业务边界，类型调整往往意味着 API 契约变化。

不要忽略 `platform/register-electron.ts`。根据当前片段推断，主进程启动时必须先注册 Electron 平台服务，否则依赖 `getPlatformServices()` 的 common 代码可能无法获得正确实现。
