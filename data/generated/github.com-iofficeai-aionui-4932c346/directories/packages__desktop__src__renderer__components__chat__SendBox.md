# 目录：packages/desktop/src/renderer/components/chat/SendBox

## 它负责什么

`packages/desktop/src/renderer/components/chat/SendBox` 是桌面端 renderer 进程里聊天输入区的共享组件目录。按它所处的位置和邻近上下文看，它不属于某个具体会话平台页面，而是位于 `components/chat` 下面，角色更接近“聊天发送框的通用 UI 基座”：承载输入框样式、发送区域布局、附件/草稿/提交交互的组件化入口，并被 conversation 页面下的平台实现复用或包裹。

根据当前片段推断，这个目录本身偏向表现层：已确认存在 `packages/desktop/src/renderer/components/chat/SendBox/sendbox.css`，说明 SendBox 的局部样式集中在这里；而发送框的状态逻辑被拆到了 renderer hooks：`packages/desktop/src/renderer/hooks/chat/useSendBoxDraft.ts` 和 `packages/desktop/src/renderer/hooks/chat/useSendBoxFiles.ts`。也就是说，SendBox 目录更可能负责“怎么显示和组织输入区”，草稿保存、文件选择/附件管理等可复用状态则由 hooks 层提供。

它位于 `renderer` 下，因此只能使用浏览器/React/UI 侧能力，不能直接调用 Node.js 或主进程 API。若发送动作需要访问会话、文件、平台后端或本地能力，正常路径应通过页面层、hooks、store、IPC bridge 或平台 adapter 间接完成。

## 直接子目录地图

当前可确认的目标目录下没有发现需要展开说明的直接子目录。已确认的核心资产是：

`packages/desktop/src/renderer/components/chat/SendBox/sendbox.css`：SendBox 的样式文件，用于定义输入区布局、边距、聚焦态、按钮区域或附件展示相关的视觉规则。由于它是 CSS 文件而不是 CSS Module，从命名看可能服务于该组件目录内的全局类名或局部约定类名，需要结合组件 JSX 中的 className 使用方式阅读。

根据当前片段推断，如果该目录内还存在 `index.tsx`、`SendBox.tsx`、`types.ts` 等文件，它们应是实际组件入口、导出聚合和类型定义；但在当前可见证据里，只有 `sendbox.css` 被明确定位到目标目录。因此本概览不逐文件展开，也不对未确认文件名做确定性描述。

## 关键入口

关键入口要从两个层次理解。

第一层是共享组件入口：`packages/desktop/src/renderer/components/chat/SendBox`。页面或平台发送框通常不会直接把所有输入逻辑写在业务页面里，而会引用这一目录下的通用 SendBox 组件或样式，保持聊天输入区在不同平台中的一致性。真正的组件导出文件需要继续在该目录内确认；当前片段只能确定样式入口 `sendbox.css` 存在。

第二层是业务接入入口：`packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpSendBox.tsx` 和 `packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsSendBox.tsx`。这两个文件名显示，conversation 页面按平台拆分了发送框适配层。它们很可能负责把平台相关的发送参数、消息格式、附件规则、会话状态传给通用 SendBox，或在通用 SendBox 的基础上增加平台差异行为。

第三层是状态逻辑入口：`packages/desktop/src/renderer/hooks/chat/useSendBoxDraft.ts`、`packages/desktop/src/renderer/hooks/chat/useSendBoxFiles.ts`。前者从命名看负责输入草稿的读取、保存和切换会话时的恢复；后者从命名看负责发送框附件、文件列表、选择/移除文件等状态。阅读 SendBox 时，应把这两个 hook 视为输入区行为的关键支撑，而不是把目录内 CSS 当成完整实现。

## 主流程位置

聊天发送主流程大致分为五段，SendBox 目录处在中间偏前的位置。

第一段是页面选择具体聊天平台。conversation 页面下存在 `packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpChat.tsx`、`packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsChat.tsx`，说明会话主界面按平台分流。平台 Chat 组件通常负责组合消息列表、标题栏、发送框和平台状态。

第二段是平台发送框适配。`AcpSendBox.tsx` 与 `AionrsSendBox.tsx` 很可能是平台差异的承接点：同样是输入并发送消息，但不同平台可能有不同模型、上下文、文件支持、命令格式或消息提交 API。这里应是把通用 SendBox 接入具体平台的主要位置。

第三段是共享 SendBox UI。`packages/desktop/src/renderer/components/chat/SendBox` 负责用户可见的输入区域：文本输入、附件展示、发送按钮、快捷键提交、禁用/加载状态、样式布局等。`sendbox.css` 是这一段的可见证据。

第四段是发送框状态 hooks。草稿流在 `useSendBoxDraft.ts`，附件流在 `useSendBoxFiles.ts`。根据当前片段推断，用户输入、切换会话、选择文件、删除附件等操作会先落到这些 hook 管理的本地状态，再由平台发送框在提交时汇总。

第五段是消息提交和会话更新。实际发送动作应继续进入 conversation 平台层、renderer 的聊天工具层或 IPC/adapter 层。邻近可见的 `packages/desktop/src/common/chat/chatLib.ts` 和 `packages/desktop/src/renderer/utils/chat` 表明仓库把聊天通用能力拆到了 common 与 renderer utils 中。SendBox 不应直接承担完整消息协议处理，它更像用户输入到业务发送之间的 UI/状态交汇点。

## 推荐阅读顺序

1. 先读 `packages/desktop/src/renderer/pages/conversation/components/ChatConversation.tsx`，理解会话页面如何组织整体聊天界面，以及平台聊天组件从哪里进入。

2. 再读 `packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpChat.tsx` 和 `packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsChat.tsx`，确认不同平台的页面结构是否一致，发送框在页面中的挂载位置在哪里。

3. 接着读 `packages/desktop/src/renderer/pages/conversation/platforms/acp/AcpSendBox.tsx`、`packages/desktop/src/renderer/pages/conversation/platforms/aionrs/AionrsSendBox.tsx`。这里最适合看“通用 SendBox 如何被业务使用”，包括 props、回调、禁用条件、提交函数和附件能力。

4. 然后回到 `packages/desktop/src/renderer/components/chat/SendBox`，重点看组件入口和 `sendbox.css`。此时再看 UI 结构会更容易，因为你已经知道它被哪些平台传入了哪些行为。

5. 最后读 `packages/desktop/src/renderer/hooks/chat/useSendBoxDraft.ts` 和 `packages/desktop/src/renderer/hooks/chat/useSendBoxFiles.ts`，把草稿保存、附件状态、会话切换后的恢复逻辑补齐。

## 常见误区

不要把 SendBox 理解成“发送消息的全部实现”。它位于 `components/chat`，从层级看首先是 renderer 组件；真正的平台发送、协议转换、会话更新通常在 `pages/conversation/platforms`、hooks、utils 或跨进程桥接之后完成。

不要忽略平台发送框。`AcpSendBox.tsx` 和 `AionrsSendBox.tsx` 这类文件往往比共享组件更能说明业务差异：同一个输入框外观相似，但提交目标、上下文、附件限制和错误处理可能完全不同。

不要只看 `sendbox.css` 判断行为。样式文件只能解释布局和视觉状态，不能证明草稿、文件、快捷键、提交时机如何工作。行为要结合组件入口、平台 SendBox 和 `useSendBoxDraft.ts`、`useSendBoxFiles.ts` 一起读。

不要在 renderer 组件里寻找主进程能力。该目录属于 `packages/desktop/src/renderer`，如果看到文件上传、路径解析、本地资源访问等需求，应继续查 IPC bridge 或平台适配层，而不是假设 SendBox 直接访问 Node.js API。

不要把通用组件和平台组件的职责混在一起。通用 SendBox 应尽量保持输入区交互一致，平台 SendBox 负责接入具体业务。阅读或修改时如果把平台分支塞进共享组件，容易让后续新增平台变得困难。
