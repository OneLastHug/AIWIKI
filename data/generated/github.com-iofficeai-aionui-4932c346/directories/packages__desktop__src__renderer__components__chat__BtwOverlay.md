# 目录：packages/desktop/src/renderer/components/chat/BtwOverlay

## 它负责什么

`packages/desktop/src/renderer/components/chat/BtwOverlay` 是聊天输入框里 `/btw` 旁路提问能力的前端承载目录。它不负责普通消息发送，也不负责完整会话渲染，而是把用户在输入框中输入的 `/btw ...` 命令转成一次“基于当前对话上下文的临时提问”，并用一个浮层展示问题、加载态和回答。

从当前片段看，这个目录承担两类职责：一类是 UI 层的 `BtwOverlay` 组件，负责浮层定位、遮罩、关闭行为、问题气泡、答案气泡和 Markdown 渲染；另一类是命令状态层的 `useBtwCommand` Hook，负责发起 IPC 请求、维护 `isOpen`、`isLoading`、`question`、`answer`，以及处理不同后端响应状态。它依赖 `ipcBridge.conversation.askSideQuestion.invoke` 与主进程或服务侧通信，因此真正的问答生成逻辑不在这个目录内。

## 直接子目录地图

这个目录当前没有直接子目录，只有三个核心文件：

`packages/desktop/src/renderer/components/chat/BtwOverlay/index.tsx`：浮层组件入口，默认导出 `BtwOverlay`。它接收 `answer`、`question`、`isOpen`、`isLoading`、`anchorEl`、`onDismiss`、`parentTaskRunning` 等 props，并通过 `ReactDOM.createPortal` 渲染到 `document.body`。

`packages/desktop/src/renderer/components/chat/BtwOverlay/useBtwCommand.ts`：命令状态与请求 Hook，导出 `useBtwCommand(conversation_id?: string, enabled = true)`。它是 `/btw` 功能和 IPC 调用之间的桥。

`packages/desktop/src/renderer/components/chat/BtwOverlay/BtwOverlay.module.css`：浮层样式模块，定义遮罩、面板、问题气泡、答案气泡和滚动区域。复杂定位逻辑在组件内完成，视觉样式集中在这里。

## 关键入口

组件入口是 `index.tsx` 里的默认导出 `BtwOverlay`。调用方不直接处理门户渲染细节，只需要传入当前 `/btw` 状态和关闭回调。组件内部会在 `isOpen` 为 `false` 时返回 `null`；打开后创建全屏 `portalRoot`，其中一层 `backdrop` 捕获点击关闭，另一层 `overlay` 按计算位置显示内容。

状态入口是 `useBtwCommand.ts` 里的 `useBtwCommand`。它返回 `ask`、`dismiss` 和展开后的状态字段。`ask(question)` 会先显示开始提示，并把浮层切到加载态；如果没有 `conversation_id`，会直接显示 unsupported；否则通过 `ipcBridge.conversation.askSideQuestion.invoke({ conversation_id, question })` 发起请求。响应回来后，根据 `status` 分流：`ok` 使用返回的 `answer`，`noAnswer`、`unsupported`、`toolsRequired`、`invalid` 映射到对应 i18n 文案，异常或空响应则落到错误提示。

外部接入点位于 `packages/desktop/src/renderer/components/chat/SendBox/index.tsx`。从引用片段可见，这里导入了 `BtwOverlay` 和 `useBtwCommand`，定义了 `BTW_COMMAND_RE = /^\/btw(?:\s+([\s\S]*))?$/i`，在组件中创建 `const btwCommand = useBtwCommand(conversationContext?.conversation_id, enableBtw)`，并在渲染尾部挂载 `<BtwOverlay ... />`。因此 `SendBox` 是用户输入命令进入该目录能力的直接上游。

## 主流程位置

主流程可以按“输入识别、前置校验、请求、浮层展示、关闭重置”理解。

第一步发生在 `packages/desktop/src/renderer/components/chat/SendBox/index.tsx`。输入框提交时会用 `BTW_COMMAND_RE` 识别 `/btw` 命令，并提取命令后的问题文本。根据搜索片段，该文件还处理空问题、父任务运行中、附件不允许等提示，例如 `conversation.sideQuestion.emptyQuestion`、`alreadyRunning`、`attachmentsNotAllowed`。这些前置规则不在 `BtwOverlay` 目录内。

第二步进入 `useBtwCommand.ask`。Hook 维护一个 `requestIdRef`，每次请求递增，用来避免旧请求在用户关闭、切换会话或禁用能力后回写状态。它还监听 `conversation_id` 和 `enabled`，当会话变化或能力从可用变为不可用时，如果浮层正在打开，就重置状态。

第三步是 IPC 请求。`ipcBridge.conversation.askSideQuestion.invoke` 是这个目录和后端能力的边界。根据当前片段推断，后端会返回至少包含 `status` 的结果，`ok` 时带 `answer`，其他状态用于说明无答案、不支持、需要工具或问题无效。依据是 `useBtwCommand.ts` 中的 `statusMap` 和 `response.status === 'ok' && 'answer' in response` 判断。

第四步是 `BtwOverlay` 展示。组件打开后根据 `.chat-layout-header`、`anchorEl`、视口宽高计算浮层位置，宽度约束在 `MIN_OVERLAY_WIDTH_PX` 到 `MAX_OVERLAY_WIDTH_PX` 之间，高度受输入框锚点和视口限制。答案区域用 `MarkdownView` 渲染，加载中使用 Arco `Spin`。关闭方式包括点击遮罩，以及延迟绑定后的 `Escape`、`Enter`、空格键；这里的延迟是为了避免提交 `/btw` 的回车立即把浮层关掉。

## 推荐阅读顺序

建议先读 `packages/desktop/src/renderer/components/chat/SendBox/index.tsx` 中与 `BTW_COMMAND_RE`、`useBtwCommand`、`BtwOverlay` 相关的片段，确认 `/btw` 是如何从输入框分流出来的。这里能建立“普通发送”和“旁路提问”的边界。

然后读 `packages/desktop/src/renderer/components/chat/BtwOverlay/useBtwCommand.ts`。这个文件最能说明业务状态机：什么时候打开浮层、什么时候 loading、哪些状态会显示 toast、如何防止过期请求污染 UI。

接着读 `packages/desktop/src/renderer/components/chat/BtwOverlay/index.tsx`。重点看 props、位置计算、portal、关闭事件和答案渲染。它解释了为什么浮层不是普通子节点，而是挂到 `document.body`。

最后看 `packages/desktop/src/renderer/components/chat/BtwOverlay/BtwOverlay.module.css` 和 `packages/desktop/src/renderer/services/i18n/locales/*/conversation.json` 里的 `sideQuestion`。前者理解视觉边界，后者理解所有用户可见文案来源。

## 常见误区

不要把 `BtwOverlay` 理解成聊天消息列表的一部分。它是临时浮层，不会把 `/btw` 问答作为普通消息气泡直接插入会话流。

不要在这个目录里寻找模型调用或检索逻辑。这里的边界止于 `ipcBridge.conversation.askSideQuestion.invoke`，真实回答如何生成需要继续查 `conversation.askSideQuestion` 的 IPC 注册和实现。

不要绕过 `useBtwCommand` 直接调用 `BtwOverlay`。组件只负责展示，不处理请求状态、过期请求防护、会话切换重置和错误分流。

不要忽略 `enabled` 和 `conversation_id`。没有会话 ID 时，Hook 会显示 unsupported；能力禁用或会话变化时，已打开的浮层会被重置。

不要把 `/btw` 当成具备搜索或工具能力的通用问答入口。i18n 文案中的 `toolsRequired` 明确说明它只能基于当前对话已有内容作答，不能搜索、浏览或获取新信息。
