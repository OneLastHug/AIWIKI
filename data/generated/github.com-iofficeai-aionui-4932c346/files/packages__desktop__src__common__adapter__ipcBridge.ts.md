# 文件：packages/desktop/src/common/adapter/ipcBridge.ts

## 一句话定位

`packages/desktop/src/common/adapter/ipcBridge.ts` 是桌面端统一的“前端调用后端能力”适配层：它保留上层仍按 `ipcBridge.xxx.yyy.invoke()` / `.on()` 使用的接口形状，但把大量原本 Electron IPC 风格的调用改路由到 aioncore 的 HTTP REST 和 WebSocket，同时让窗口控制、原生对话框、自动更新、DevTools、缩放、CDP、deep link 等 Electron 原生能力继续走 IPC。

## 它暴露/定义了什么

这个文件按业务域导出一组 bridge 对象，核心是面向上层消费的 `ipcBridge` 聚合接口。根据当前片段可见，它至少定义了：

`こ shell`：打开文件、在文件夹中显示、打开外部链接、检测工具、用 VSCode/terminal/explorer 打开目录等。

`assistants`：助手列表、创建、更新、删除、启停、导入。

`conversation`：会话创建、克隆、获取、更新、删除、重置、warmup、停止生成、发送消息、slash commands、side question、确认权限、artifact 列表与更新，以及多类 WebSocket 事件流。

此外，从 imports 和调用点推断，它还会继续聚合 `database`、`fs`、`application`、`provider`、`team`、`workspace`、`pptPreview`、`wordPreview`、`excelPreview`、`deepLink`、`autoUpdate` 等领域接口。这个判断依据是仓库其他文件直接调用 `ipcBridge.database.getUserConversations`、`ipcBridge.fs.getImageBase64`、`ipcBridge.application.writeRendererLog`、`ipcBridge.pptPreview` 等成员。

## 谁调用它

主要调用者有两类。

第一类是 renderer UI。对话页面、历史列表、消息组件、预览面板、Markdown/Image/PDF/Office 预览器等通过 `@/common` 导入 `ipcBridge`，执行会话增删改查、发送消息、确认工具调用、读取图片、打开本地文件，并订阅 `conversation.responseStream`、`turnCompleted`、`listChanged` 等事件。

第二类是 main/process 侧工具逻辑。比如 `packages/desktop/src/process/utils/tray.ts` 使用它读取最近会话和活跃任务数，`deepLink.ts` 使用事件 emit 通知前端，`migrateAssistants.ts` 使用助手接口迁移或修正助手状态。`packages/desktop/src/common/utils/presetAssistantResources.ts` 也把预设助手资源读取包装成对 `ipcBridge.fs` 和 `ipcBridge.assistants` 的透传。

## 它调用谁

HTTP/WS 方向主要调用 `packages/desktop/src/common/adapter/httpBridge.ts` 中的 `httpGet`、`httpPost`、`httpPut`、`httpPatch`、`httpDelete`、`httpRequest`、`withResponseMap`、`wsEmitter`、`wsMappedEmitter`。这些 helper 负责把接口声明变成统一的 `invoke` 或事件订阅能力。

数据转换方向调用多个 mapper：`apiModelMapper` 负责会话模型字段转换，`searchMapper` 负责搜索结果转换，`teamMapper` 负责 team/agent 前后端结构转换，`fileSnapshotMapper` 负责文件快照对比结果转换，`workspaceMapper` 负责 workspace 文件列表和路径格式转换。

Electron 原生或平台桥接方向调用 `@office-ai/platform` 的 `bridge`。根据文件头注释和调用点推断，这部分用于保留真正必须留在 Electron IPC 层的能力，例如窗口、原生对话框、更新、DevTools、CDP、deep link 等。

## 核心流程

上层代码并不直接关心某个能力走 HTTP、WS 还是 Electron IPC，而是统一调用 `ipcBridge`。例如发送消息时，renderer 调用 `ipcBridge.conversation.sendMessage.invoke(params)`；该文件把它映射为 `POST /api/conversations/{conversation_id}/messages`，同时把前端字段 `input`、`files`、`loading_id`、`inject_skills` 转成后端需要的 body 字段。后端返回后，必要时通过 mapper 转回前端领域模型。

事件流则走 WebSocket。比如 `conversation.responseStream` 由 `wsEmitter('message.stream')` 暴露，调用方通过 `.on()` 订阅消息流；`turnCompleted` 使用 `wsMappedEmitter` 对后端事件做兼容性整理，例如兼容 `last_message` 与 `lastMessage` 字段，再交给 UI 更新状态。

这个文件的核心价值在于“接口稳定、传输替换”：上层仍像使用 IPC 一样使用 bridge，下层可以逐步迁移到 aioncore REST/WS。

## 关键函数的高层作用

`httpGet`、`httpPost`、`httpPut`、`httpPatch`、`httpDelete` 在本文件中不是普通函数调用，而是接口工厂。它们把 URL、参数映射函数、静默状态码等配置组合成具有 `.invoke()` 语义的 API。

`withResponseMap` 用于处理后端响应和前端类型不完全一致的场景，例如会话接口返回后通过 `fromApiConversation` 转成 `TChatConversation`。

`wsEmitter` 暴露无需转换的 WebSocket 事件。`wsMappedEmitter` 暴露需要字段兼容或结构规整的事件，典型例子是 `conversation.turnCompleted`。

`conversation.create` 和 `conversation.createWithConversation` 是比较关键的业务适配点：它们会根据会话类型判断是否把 `model` 放在顶层。代码注释说明顶层 `model` 是 `aionrs` 后端专用，其他 agent 类型通过 `extra` 携带模型信息。这里体现了前端领域模型与后端 API 契约之间的边界处理。

`conversation.update` 负责把前端局部更新对象转成后端 patch body，并对 `model` 做可选转换，同时透传 `merge_extra` 控制后端如何合并扩展字段。

## 修改风险

最大风险是破坏上层稳定契约。大量 UI 和 process 工具都依赖 `ipcBridge.xxx.yyy.invoke()`、`.on()`、`.emit()` 的形状；如果改名、移动字段、改变返回类型，即使 HTTP 请求本身成功，也可能让调用侧状态更新失败。

第二个风险是前后端字段映射。这里存在多处命名和结构转换，例如 `input` 到 `content`、`conversation_id` 到 URL path、`model` 的条件上浮、`lastMessage`/`last_message` 兼容。修改时必须同时确认 aioncore API 契约和前端类型，否则容易出现静默数据丢失。

第三个风险是错误处理和状态码语义。像 `conversation.get` 对 404 配置了 `silentStatuses`，说明调用方可能把“查不到”当成可恢复状态。随意移除会改变 UI 错误表现。

第四个风险是混淆 HTTP/WS 与 Electron IPC 边界。文件头明确说明并非所有能力都迁移到 HTTP；窗口控制、原生对话框、自动更新、DevTools、缩放、CDP、deep link 等仍应走 IPC。把这类能力改成普通 HTTP 调用，可能破坏桌面端权限、生命周期或安全模型。

第五个风险是类型表面很宽。这个文件聚合了助手、会话、文件、团队、预览、更新、工作区等多个领域，改动一个 helper 或共享 mapper 可能影响多个页面。较安全的修改方式是先定位具体业务域，只改对应对象和 mapper，并补充调用侧验证。
