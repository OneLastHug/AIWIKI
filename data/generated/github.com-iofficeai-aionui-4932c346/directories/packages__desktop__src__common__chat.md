# 子系统：packages/desktop/src/common/chat

## 解决什么问题
`packages/desktop/src/common/chat` 是桌面端聊天子系统的“公共协议层”和“消息整形层”。它不直接负责界面渲染，而是把后端、ACP/CLI Agent、工具调用、权限请求、计划更新、思考态、可用命令等不同来源的消息统一成前端可消费的结构，再提供一组轻量转换函数，让 renderer、process、preload 以及数据库层共享同一套聊天语义。

从目录结构看，这里同时覆盖了消息类型定义、消息归一化、slash command 映射、审批与导航辅助、文档/图片相关转换等能力。根据当前片段推断，这一层的目标是把“聊天流里的异构事件”收敛成“可存储、可传输、可展示”的标准对象。

## 相关目录和文件
核心入口是 `chatLib.ts`，它定义了 `TMessage`、`IMessageText`、`IMessageToolCall`、`IMessageAcpToolCall`、`IMessageAgentStatus`、`IConfirmation` 等聊天主数据结构，并提供 `transformMessage`、`mergeTextMessageContent`、`normalizeAgentStreamError`、`joinPath` 这类基础工具。

`normalizeToolCall.ts` 负责把 `tool_group`、`tool_call`、`acp_tool_call` 统一压平成 `NormalizedToolCall`，供 UI 侧的工具卡片和工具摘要使用；`normalizeToolCall.test.ts` 是这部分逻辑的对应测试。

`slash/types.ts`、`slash/availability.ts`、`slash/acpMapping.ts` 则专门处理 slash command：定义命令类型、判断是否该展示命令列表、以及把 ACP 的 `available_commands` 或 HTTP 返回结果映射为 `SlashCommandItem`。

子目录里还有 `approval/ApprovalStore.ts`、`document/DocumentConverter.ts`、`navigation/NavigationInterceptor.ts`、`imageGenCore.ts`、`atCommandParser.ts`、`sideQuestion.ts`。根据文件名和引用关系推断，它们分别覆盖审批状态管理、文档内容转换、导航拦截、图像生成核心逻辑、`@` 指令解析和侧边提问辅助。

## 核心对象
最重要的对象是 `TMessage`。它把文本、提示、工具调用、工具组、Agent 状态、权限、ACP 权限、ACP 工具调用、计划、思考态、可用命令统一成一个联合类型，后续消息链路几乎都围绕它展开。

第二层核心是 `IMessage` 家族。`IMessageText` 处理文本增量和替换；`IMessageTips` 处理错误/信息提示；`IMessageToolGroup` 处理带确认细节的工具批次；`IMessageAcpToolCall` 处理 ACP 的流式工具调用；`IMessagePermission`、`IMessageAcpPermission` 处理用户确认；`IMessagePlan`、`IMessageThinking`、`IMessageAvailableCommands` 则服务于计划、思考和命令提示。

第三层是转换结果对象，例如 `NormalizedToolCall` 和 `SlashCommandItem`。前者是工具调用展示的标准形态，后者是输入框 autocomplete 菜单的标准形态。

## 运行流程
典型流程是：后端或 adapter 产出 `IResponseMessage`，`chatLib.ts` 里的 `transformMessage` 先把它转换成统一的 `TMessage`；再由 renderer 的 conversation 页面按 `type` 分发到 `MessageText`、`MessageToolCall`、`MessageToolGroup`、`MessageTips` 等组件。

工具流会再走一层 `normalizeToolCall.ts`，把不同协议的工具事件压成一致的摘要数据，方便列表、折叠面板和运行中状态判断。

slash command 流程则是先由 `isSlashCommandListEnabled` 判断当前会话是否允许查询命令，再由 `mapAcpCommandsToSlashCommands` 把 ACP 命令映射到统一菜单项，最后在 `SendBox` 和相关 hook 中用于自动补全。

`joinPath`、`DocumentConverter`、`NavigationInterceptor` 这类辅助模块则分散在预览、Markdown 渲染、文档解析和导航处理路径上，用来支撑聊天场景中的文件与内容联动。

## 上下游依赖
上游依赖主要来自 `@/common/types/platform/acpTypes`、`@/common/adapter/ipcBridge`、`../utils`，以及 ACP/agent 协议返回的数据结构。`chatLib.ts` 还会消费 `PlanUpdate`、`ToolCallUpdate` 之类平台层类型。

下游消费面很广：renderer 里的 `packages/desktop/src/renderer/pages/conversation/**`、`SendBox`、`useSlashCommands`、`MessageToolCall`、`MessageToolGroupSummary`、`MessageTips` 都直接依赖这里的类型和转换函数；process 侧的 `packages/desktop/src/process/services/database/IConversationRepository.ts`、`packages/desktop/src/process/utils/initStorage.ts`、`packages/desktop/src/process/pet/petConfirmManager.ts` 也会读取 `TMessage`；`packages/desktop/src/process/resources/builtinMcp/imageGenServer.ts` 使用 `imageGenCore` 作为图片生成能力的公共实现。

## 修改时最容易踩的坑
第一，`TMessage` 是跨进程共享协议，改字段名、枚举值或可选性时，renderer、process、数据库和 IPC bridge 往往都要一起改。

第二，`transformMessage` 和 `normalizeToolCall` 都在做“兼容旧协议 + 新协议”的归一化，贸然删掉兼容分支很容易让历史会话、回放数据或外部 agent 断掉。

第三，slash command 的可见性受会话类型和状态影响，尤其 `codex` 需要 `session_active` 才允许拉取命令；这里改错会造成空列表、404 或错误的输入行为。

第四，`joinPath` 看起来只是字符串拼接，但它被文件预览、Markdown 图片等路径敏感场景复用，改坏会直接影响本地文件展示。

## 推荐阅读顺序
先读 `chatLib.ts`，建立消息协议和 `TMessage` 的整体认识；再读 `normalizeToolCall.ts`，理解工具调用如何被统一展示；然后看 `slash/types.ts`、`slash/availability.ts`、`slash/acpMapping.ts`，把输入框命令链路补齐。最后再看 `approval/ApprovalStore.ts`、`document/DocumentConverter.ts`、`navigation/NavigationInterceptor.ts`、`imageGenCore.ts`、`atCommandParser.ts`，把聊天子系统和文件、审批、导航、生成能力的连接补完整。
