# 文件：next/src/stores/messageStore.ts

## 一句话定位

`next/src/stores/messageStore.ts` 是前端消息列表的 Zustand 状态中心，负责保存当前 Agent 运行过程中展示给用户的 `Message[]`，并提供追加消息、按 `id` 更新消息、整体重置消息状态这三个核心能力。

## 它暴露/定义了什么

这个文件主要定义并导出：

`MessageSlice`：消息状态切片接口，包含 `messages: Message[]`、`addMessage(newMessage)`、`updateMessage(newMessage)`。

`initialMessageState`：初始状态，目前只有空数组 `messages: []`。这个 store 没有持久化配置，因此刷新页面后消息不会从本地恢复。

`createMessageSlice`：Zustand slice 工厂，接收 `set`，返回初始状态和两个 action。

`useMessageStore`：最终给 React 组件和普通服务代码使用的 Zustand store。它经过 `createSelectors` 包装，因此支持 `useMessageStore.use.messages()`、`useMessageStore.use.addMessage()` 这类自动 selector 写法，也保留 `useMessageStore.getState()` 这类命令式访问方式。

`resetAllMessageSlices`：遍历内部 `resetters` 数组，把 store 重置回 `initialMessageState`。当前文件只有一个 slice，但结构上和其他 store 保持一致，方便未来组合多个 slice。

## 谁调用它

直接调用者主要有三个层次。

第一层是 `next/src/stores/index.ts`，它重新导出 `messageStore`，让业务代码可以从 `../stores` 统一导入。

第二层是页面入口 `next/src/pages/index.tsx`。首页通过 `useMessageStore.use.addMessage()` 取得追加消息函数，通过 `useMessageStore.use.messages()` 订阅消息数组，并把 `messages` 传给 `Chat` 或 `Landing`。当用户重新加载或重启 Agent 时，首页调用 `resetAllMessageSlices()` 清空消息。

第三层是 `next/src/services/agent/message-service.ts`。`MessageService` 构造时接收首页传入的 `addMessage`，`sendMessage()` 会调用这个函数把新消息渲染进 store；`updateMessage()` 则直接使用 `useMessageStore.getState().updateMessage(message)` 更新已有消息。`execute-task-work.ts`、`chat-work.ts`、`summarize-work.ts` 等 Agent work 不直接操作 store，而是通过 `parent.messageService.updateMessage(...)` 间接更新消息内容。

根据当前片段推断，`Chat`、`Landing`、`ChatWindow`、`ChatMessage` 等组件主要消费从首页传入的 `messages` props，用于 UI 展示，而不是直接读写该 store；依据是搜索结果中这些组件没有出现 `useMessageStore` 直接引用。

## 它调用谁

这个文件依赖 `zustand` 的 `create` 和 `StateCreator` 来创建 store；依赖本地 `next/src/stores/helpers.ts` 的 `createSelectors` 给每个 state/action 自动生成 selector；依赖 `next/src/types/message.ts` 的 `Message` 类型约束消息结构。

它不调用后端 API、不访问 localStorage、不做消息格式转换，也不负责生成消息 `id`。消息内容、类型、状态、`id` 的生成都在上游业务层完成，例如 `MessageService` 和各个 Agent work 中使用 `uuid` 创建任务消息 `id`。

## 核心流程

典型流程是：用户在首页启动 Agent，`index.tsx` 创建 `MessageService(addMessage)`，再把它传入 `AutonomousAgent`。Agent 运行过程中，`MessageService.sendMessage()` 会把 goal、system、task、error 等消息追加到 `messages` 数组。首页因为订阅了 `messages`，会重新渲染，并把最新数组传给 `Chat` 或 `Landing` 展示。

对于流式输出类消息，流程略有不同。以 `execute-task-work.ts` 为例，它先创建一个带 `id` 的 `executionMessage`，调用 `sendMessage()` 把占位消息加入列表；随后 `streamText()` 每收到一段文本，就修改同一个 `executionMessage.info`，并调用 `messageService.updateMessage(executionMessage)`。最终落到 `messageStore.updateMessage()`，按 `id` 找到旧消息，用新消息替换数组中的对应项，从而驱动界面显示逐步增长的结果。

重启流程中，首页的 `handleRestart()` 调用 `resetAllMessageSlices()`，该函数执行注册在 `resetters` 中的 reset 回调，把 `messages` 恢复为空数组。

## 关键函数的高层作用

`addMessage(newMessage)` 的作用是追加一条消息。实现上它使用 `set((state) => ...)` 基于当前状态创建新数组：`messages: [...state.messages, { ...newMessage }]`。这里会浅拷贝消息对象，避免直接把调用方传入的对象引用原样塞进数组，但只是一层浅拷贝，嵌套字段如果存在仍然共享引用。

`updateMessage(newMessage)` 的作用是按 `newMessage.id` 替换已有消息。它先在 `state.messages` 中查找 `id` 相同的旧消息，找到后用 `map` 生成新数组，把目标项替换为 `newMessage`；找不到则返回原状态，不追加、不报错。这个设计说明 `updateMessage` 只适合“已有占位消息的后续更新”，不能当成 upsert 使用。

`resetAllMessageSlices()` 是全局清空入口。当前实现通过模块级 `resetters` 数组保存 reset 函数，再逐个执行。辅助价值大于业务逻辑复杂度，主要是和其他 Zustand slice 的 reset 模式保持一致。

`createSelectors(...)` 不是本文件实现的核心业务，但它影响调用方式：组件不需要手写 selector，可以直接调用 `useMessageStore.use.messages()` 订阅单个字段，减少无关状态变化带来的渲染。

## 修改风险

最大的风险是 `id` 语义。`updateMessage()` 完全依赖 `Message.id` 匹配，但 `Message` 类型里 `id` 是 optional。如果上游发送没有 `id` 的消息再尝试更新，`newMessage.id` 为 `undefined` 时可能匹配到第一条同样没有 `id` 的消息，或者找不到目标，行为不够显式。修改流式消息或任务消息时，应保证可更新消息一定有稳定 `id`。

第二个风险是不要把 `updateMessage()` 改成隐式追加，除非同时审查所有调用点。当前 Agent work 的语义是“先 `sendMessage` 创建，再 `updateMessage` 替换”，如果改成 upsert，可能掩盖上游顺序错误，也可能在流式回调中重复插入消息。

第三个风险是对象引用和浅拷贝。`addMessage()` 会浅拷贝，`updateMessage()` 则直接把 `newMessage` 放入数组。现有流式流程会持续修改同一个 `executionMessage` 对象再提交更新，UI 依赖数组替换触发响应。如果未来引入更复杂的嵌套字段或不可变数据约束，需要统一消息对象的复制策略。

第四个风险是重置机制。`resetters` 是模块级数组，`createMessageSlice` 创建时会 push reset 函数。当前 store 只创建一次，问题不大；如果未来在测试或热更新场景中多次初始化 store，可能出现重复 resetter。修改时应参考其他 store 的同类实现，避免这个文件和全局 reset 行为不一致。

第五个风险是持久化预期。与 `agentStore`、`configStore`、`modelSettingsStore` 不同，该 store 没有使用 `persist`。如果想保存历史消息，不能只在这里加持久化，还要考虑消息体大小、敏感信息、登录态切换、PDF 导出和 Agent 重启时清空逻辑。
