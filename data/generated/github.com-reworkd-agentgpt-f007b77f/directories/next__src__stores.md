# 目录：next/src/stores

## 它负责什么

`next/src/stores` 是前端全局状态层，基于 `zustand` 组织 AgentGPT 页面运行时需要共享的状态。它不直接负责 UI 渲染、API 请求或 agent 推理逻辑，而是把这些流程中的关键状态集中起来，让页面、组件、hooks 和 service 可以通过统一的 store 读写。

从职责上看，这个目录覆盖五类状态：agent 运行状态、任务队列、消息列表、输入框草稿、用户配置与模型设置。agent 运行状态包括当前 `AutonomousAgent` 实例、`lifecycle`、thinking 状态、摘要状态和启用的 tools；任务队列保存 agent 生成或用户手动添加的 task；消息列表保存聊天窗口展示的 message；输入 store 保存首页的 name/goal 输入值；配置 store 保存侧栏布局和组织身份；模型设置 store 保存语言、模型名、token 等设置。

这个目录的一个重要特点是：多数 store 都通过 `createSelectors` 包装，形成 `useXxxStore.use.someField()` 的选择器调用方式。这样组件可以只订阅自己需要的字段，降低不必要的重新渲染。部分 store 使用 `persist` 写入 `localStorage`，但持久化范围经过限制，例如 `agentStore` 只持久化 tools，`modelSettingsStore` 会对模型名和 token 上限做归一化。

## 直接子目录地图

`next/src/stores` 当前没有直接子目录，所有状态模块都平铺在该目录下。按角色可以分成几组：

状态工具层：`next/src/stores/helpers.ts` 提供 `createSelectors`，是所有 store 的选择器增强工具。

聚合出口层：`next/src/stores/index.ts` 统一导出部分 store，目前导出 `messageStore`、`agentStore`、`modelSettingsStore`。注意它不是完整导出入口，`taskStore`、`agentInputStore`、`configStore` 在代码中经常通过具体路径导入。

agent 运行状态层：`agentStore.ts` 维护当前 agent 实例、生命周期、thinking 标记、摘要标记和 tools。

会话内容状态层：`messageStore.ts` 维护聊天消息，`taskStore.ts` 维护任务列表。它们共同构成 agent 运行过程中可见的主要内容。

页面输入和配置层：`agentInputStore.ts` 保存首页输入框状态，`configStore.ts` 保存布局与组织信息，`modelSettingsStore.ts` 保存模型设置。

## 关键入口

最常见的导入入口是 `next/src/stores/index.ts`。页面和服务层通过它拿到 `useAgentStore`、`useMessageStore`、`useModelSettingsStore`，例如 `next/src/pages/index.tsx`、`next/src/services/agent/agent-api.ts`、`next/src/services/agent/autonomous-agent.ts` 都会从这里读取或更新 agent/message/model 相关状态。

第二类入口是具体 store 文件。`useTaskStore` 通常从 `next/src/stores/taskStore.ts` 直接导入，因为它没有从 `index.ts` 聚合导出；`useAgentInputStore` 也通过 `next/src/stores/agentInputStore.ts` 直接使用；`useConfigStore` 在布局和侧栏组件中通过 `next/src/stores/configStore.ts` 使用。

`helpers.ts` 是内部入口，不面向业务流程，但它决定了调用风格。代码里大量出现的 `useAgentStore.use.lifecycle()`、`useTaskStore.use.tasks()`、`useMessageStore.use.addMessage()` 都来自这个 helper 自动生成的 selector。

## 主流程位置

Agent 启动主流程在 `next/src/pages/index.tsx`。首页读取 `useAgentInputStore` 的目标输入，读取 `useModelSettingsStore` 经 `useSettings` 包装后的模型设置，使用 `useMessageStore` 的 `addMessage`，并通过 `useAgentStore` 设置新的 `AutonomousAgent` 实例。点击启动后，页面构造 `DefaultAgentRunModel`、`MessageService`、`AgentApi`、`AutonomousAgent`，再调用 `setAgent(newAgent)` 和 `newAgent.run()`。

Agent 生命周期和任务推进的主流程在 `next/src/services/agent/agent-run-model.tsx` 与 `next/src/services/agent/autonomous-agent.ts`。`DefaultAgentRunModel` 不自己保存任务，而是通过 `useTaskStore.getState()` 读取、添加、更新任务；生命周期也通过 `useAgentStore.getState()` 读写。`AutonomousAgent` 执行 work log 时根据生命周期判断是否运行、暂停或停止，并在重试等待、结束时更新 `isAgentThinking`。

消息流主流程在 `next/src/services/agent/message-service.ts` 和聊天组件附近。`MessageService` 接收 `addMessage` 回调，把 agent 产生的输出写入 `messageStore`；`next/src/components/index/chat.tsx` 从页面传入 messages，并把它们渲染为 `ChatMessage`。已有消息的更新则通过 `useMessageStore.getState().updateMessage()` 发生在服务层。

任务 UI 主流程在 `next/src/components/drawer/TaskSidebar.tsx`、`next/src/components/index/chat.tsx`、`next/src/components/console/SummarizeButton.tsx`。这些组件读取 `useTaskStore.use.tasks()` 展示任务、判断摘要按钮状态，或手动追加任务。

配置和设置主流程分散在 hooks 与布局中。`next/src/hooks/useSettings.ts` 包装 `useModelSettingsStore`，并处理 Next.js 语言路由与 Zustand/localStorage 的 hydration 问题；`next/src/hooks/useTools.ts` 请求工具列表后把 active tools 写入 `agentStore`；`next/src/layout/dashboard.tsx` 和 `TaskSidebar.tsx` 使用 `configStore` 控制左右侧栏显示。

## 推荐阅读顺序

建议先读 `next/src/stores/helpers.ts`，理解为什么 store 可以用 `.use.xxx()` 的形式调用。然后读 `next/src/stores/agentStore.ts`，因为 agent 生命周期是整个应用状态变化的中心。接着读 `next/src/stores/taskStore.ts` 和 `next/src/stores/messageStore.ts`，把任务队列与聊天消息两条内容流理清。

之后读 `next/src/pages/index.tsx`，从启动按钮到创建 `AutonomousAgent` 的路径会把多个 store 串起来。再读 `next/src/services/agent/agent-run-model.tsx` 和 `next/src/services/agent/autonomous-agent.ts`，理解 service 层为什么直接用 `useXxxStore.getState()` 操作全局状态。最后补读 `next/src/hooks/useSettings.ts`、`next/src/hooks/useTools.ts`、`next/src/layout/dashboard.tsx`，掌握设置、tools 和布局状态的外围使用方式。

## 常见误区

不要把 `next/src/stores` 理解成后端状态或数据库层。这里的状态主要是浏览器端运行时状态，持久化也只是 `localStorage` 级别，不能替代服务端数据源。

不要以为 `index.ts` 是完整统一出口。当前它只导出部分 store，很多调用点仍然直接导入 `taskStore`、`agentInputStore`、`configStore`。如果新增 store，需要根据现有风格判断是否加入聚合出口，不能只看 `index.ts`。

不要把 `agentStore.agent` 当成可持久化业务数据。它保存的是 `AutonomousAgent` 实例，真正通过 `persist` 保留下来的只有 tools 子集。页面刷新后 agent 实例不会作为可恢复对象保存。

不要忽略 reset 逻辑。`agentStore`、`messageStore`、`taskStore`、`modelSettingsStore` 内部都有 resetter 模式；首页的 restart 会调用 `resetAllMessageSlices()`、`resetAllTaskSlices()`、`resetAllAgentSlices()` 清空一次运行上下文。阅读状态变化时，需要把这些重置入口一起纳入流程。

不要把任务和消息混为一条数据源。虽然 task 类型可能也是 message 的一种表现形式，但当前代码中任务队列主要由 `taskStore` 管理，聊天窗口消息由 `messageStore` 管理，二者在 UI 上相关，在状态层是分开的。
