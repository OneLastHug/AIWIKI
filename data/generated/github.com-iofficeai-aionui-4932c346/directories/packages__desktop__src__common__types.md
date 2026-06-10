# 子系统：packages/desktop/src/common/types

## 解决什么问题

`packages/desktop/src/common/types` 是桌面端跨进程、跨模块共享的“契约层”。AionUi 桌面端同时存在 renderer、preload、process/main 侧代码，还会和 Rust 后端、ACP agent、远程 agent、扩展中心、SQLite 存储、HTTP API、IPC 事件交互。这个目录把这些边界上的数据形状集中定义出来，避免 renderer 直接引用 `@process/*`，也避免每个业务模块各自声明一套相似但不完全一致的类型。

它不是单纯的 TypeScript 工具类型目录，而是把“外部协议”和“内部持久化模型”整理成稳定接口：例如 ACP 初始化响应、provider API 请求响应、team IPC 事件、assistant 导入导出、文档预览与转换、远程 agent 配置、Electron bridge 全局对象等。根据当前片段推断，这里的类型大多服务于编译期约束和边界文档，只有少量文件包含运行时代码，例如 `agent/agentModes.ts` 的 `getFullAutoMode`、`codex/codexModes.ts` 的 `normalizeCodexMode`、`agent/detectedAgent.ts` 的 `isAgentKind`。

## 相关目录和文件

`agent/` 负责 agent 发现、assistant 配置、远程 agent、扩展 hub 和自动执行模式。关键文件包括 `agent/detectedAgent.ts`、`agent/assistantTypes.ts`、`agent/remoteAgentTypes.ts`、`agent/hub.ts`、`agent/agentModes.ts`。

`platform/` 负责平台边界类型：`platform/acpTypes.ts` 描述 ACP 协议初始化、能力、权限请求、session 配置项和模型信息；`platform/electron.ts` 描述 `window.electronAPI`、WebUI 状态和后端启动失败原因；`platform/fileSnapshot.ts` 描述文件快照/变更比较结果。

`provider/` 负责模型服务供应商和语音转文字契约。`provider/providerApi.ts` 明确标注为 `/api/providers/*` 的 wire-contract，并要求与 Rust 侧 `provider.rs` 同步；`provider/speech.ts` 定义 OpenAI、Deepgram 语音配置和识别请求结果。

`team/` 负责团队协作域模型。`team/teamTypes.ts` 定义 `TTeam`、`TeamAgent` 和一组 team IPC/WS 事件；`team/database.ts` 定义消息搜索响应，它依赖 `common/chat/chatLib` 和 `common/config/storage` 中的聊天会话类型。

`office/` 负责文档转换与预览。`office/conversion.ts` 定义 Word、Excel、PPT、PDF 转换服务 API 与统一转换请求/响应；`office/preview.ts` 定义预览内容类型、历史目标、快照信息和远程图片获取请求。

`codex/` 负责 Codex 模型与模式。`codex/codexModels.ts` 保存默认模型候选，`codex/codexModes.ts` 兼容旧配置值并规范化到原生 Codex mode。根部的 `pptx2json.d.ts`、`turndown-plugin-gfm.d.ts` 是第三方库声明补丁，用来补齐缺失类型。

## 核心对象

`DetectedAgent` 是执行引擎抽象，使用 `kind` 区分 `acp`、`remote`、`aionrs`、`openclaw-gateway`、`nanobot`，并通过泛型把不同 kind 的字段收窄。它表达的是“系统检测到的执行引擎”，而不是用户配置的 assistant。

`Assistant` 是用户、内置或扩展提供的助手预设，包含名称、多语言字段、头像、启用状态、技能、提示词、模型和上下文。源码注释说明它镜像 `aionui-api-types/src/assistant.rs`，因此字段变更需要和后端同 PR 同步。

`RemoteAgentConfig` 表示远程 agent 的持久化配置，对应 `remote_agents` 表，包含协议、认证、URL、TLS 选项、OpenClaw 设备密钥和连接状态。`RemoteAgentProtocol`、`RemoteAgentAuthType` 的 canonical definition 放在 `agent/detectedAgent.ts`，`remoteAgentTypes.ts` 只是复用并转导，避免协议枚举分叉。

`AcpInitializeResult`、`AcpAgentCapabilities`、`AcpPermissionRequest` 是 ACP agent 的主要协议对象，覆盖初始化能力、认证方法、session 更新、配置项、mode/model 信息和权限请求。

`TTeam` 与 `TeamAgent` 是团队协作持久化核心。`TeamAgent` 记录 slot、conversation、角色、agent 类型、状态、模型和待确认数；相关 `ITeam*Event` 类型则约束后端或主进程推送给 renderer 的实时事件。

`CreateProviderRequest`、`UpdateProviderRequest`、`FetchModelsResponse`、`ProviderHealthCheckResponse` 是 provider 管理 API 的边界对象，依赖 `common/config/storage` 里的 `IProvider`、`ModelCapability`。

## 运行流程

典型流程是：process 或后端探测可用执行引擎，生成 `DetectedAgent`；renderer 用这些信息展示 agent 选择或 assistant 配置；用户创建 assistant、remote agent、team 或 provider 时，请求体遵循本目录的 request 类型；process/preload/HTTP 层再把响应、IPC 事件或 WebSocket 事件转换为这里的 response/event 类型交给 UI。

在会话启动时，agent 模式会经过 `getFullAutoMode` 选出不同 backend 的全自动模式；Codex 相关配置会经 `normalizeCodexMode` 把旧值如 `autoEdit`、`yolo` 映射成当前 Codex 原生值。ACP agent 初始化后，`AcpInitializeResult` 被缓存或展示，session 配置项、可选模式、权限请求再通过对应类型流入聊天、团队和设置界面。

文档能力的流程相对独立：UI 或服务层提交 `DocumentConversionRequest`，转换服务返回带 `to` 判别字段的 `DocumentConversionResponse`；预览侧使用 `PreviewHistoryTarget` 和 `PreviewSnapshotInfo` 保存最近预览对象与快照元数据。

## 上下游依赖

上游主要包括 Rust 后端类型、ACP 协议、远程 agent 协议、Electron preload 注入、SQLite 表结构、第三方文档转换库和 provider HTTP API。源码中多处注释直接要求与 Rust 类型同步，例如 `agent/assistantTypes.ts`、`provider/providerApi.ts`。

下游主要是 `packages/desktop/src/common/config`、`packages/desktop/src/common/utils`、renderer 页面/组件、process 服务、preload bridge、测试用例和 E2E 场景。`common/config/storage.ts` 会引用 ACP、speech 类型；team E2E 通过 `team.add-agent` 等 bridge 通道验证 `TeamAgent` 相关行为；provider、assistant、remote、preview 等页面根据这些类型组织表单和状态。

## 修改时最容易踩的坑

第一，不要把 renderer 私有类型或 process 私有实现类型放进这里。这里是 common 契约层，任何放入的类型都可能被两侧共同依赖。

第二，涉及后端镜像类型时不能只改 TypeScript。`Assistant`、provider API 类型、远程 agent 数据库字段都可能有 Rust 结构体、SQLite 表或迁移逻辑对应，字段名尤其要保持 snake_case wire format。

第三，已有持久化配置需要兼容。`normalizeCodexMode` 明确保留旧值映射，新增 mode 或 backend 时要考虑历史配置、默认值和 unknown fallback。

第四，判别联合类型要同步消费方。比如 `PreviewContentType`、`TeamMcpPhase`、`ProviderHealthCheckErrorKind` 新增枚举值后，UI 显示、i18n、错误处理和测试都可能需要补齐。

第五，不要随意引入运行时依赖。多数文件是纯类型；如果加入函数或常量，会影响打包边界和跨进程引用关系。

## 推荐阅读顺序

1. 先读 `agent/detectedAgent.ts`，理解 AionUi 如何区分“执行引擎”和“assistant 预设”。
2. 再读 `platform/acpTypes.ts`，掌握 ACP agent 能力、session 配置、权限请求这些核心协议。
3. 继续读 `team/teamTypes.ts`，把 agent 如何进入团队协作、如何通过事件推送状态串起来。
4. 阅读 `provider/providerApi.ts` 和 `provider/speech.ts`，理解模型供应商、模型拉取、健康检查和语音输入契约。
5. 阅读 `office/conversion.ts`、`office/preview.ts`，了解文件转换和预览子系统的数据边界。
6. 最后看 `codex/codexModes.ts`、`agent/agentModes.ts`，理解各 backend 的执行模式兼容逻辑。
