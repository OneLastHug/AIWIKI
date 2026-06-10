# 文件：next/src/stores/agentStore.ts

## 一句话定位

`next/src/stores/agentStore.ts` 是前端 Agent 运行状态的 Zustand 中心 store，负责保存当前 `AutonomousAgent` 实例、运行生命周期、思考中状态、摘要标记，以及用户启用的工具列表；它把“页面 UI 是否显示聊天/落地页”“Agent 是否运行/暂停/停止”“后端分析任务时带哪些工具”这些跨组件状态集中到一个可订阅入口。

## 它暴露/定义了什么

文件主要定义两个 slice：

`AgentSlice` 保存 Agent 运行态数据：`agent`、`lifecycle`、`summarized`、`isAgentThinking`，并暴露 `setAgent`、`setLifecycle`、`setSummarized`、`setIsAgentThinking` 等 setter。`lifecycle` 类型来自 `services/agent/agent-run-model.tsx`，取值包括 `offline`、`running`、`pausing`、`paused`、`stopped`。

`ToolsSlice` 保存 `tools` 和 `setTools`。这里的 `tools` 类型是 `Omit<ActiveTool, "active">[]`，表示只持久化/暴露已启用工具本身，而不是完整的工具开关列表。

最终导出 `useAgentStore`，它是经过 `createSelectors` 包装的 Zustand hook，因此调用方可以写 `useAgentStore.use.agent()`、`useAgentStore.use.lifecycle()` 这种选择器式访问。文件还导出 `resetAllAgentSlices`，用于批量执行本文件注册的 resetter。

## 谁调用它

页面入口 `next/src/pages/index.tsx` 是最核心调用者：它读取 `agent` 和 `lifecycle` 决定显示 `Landing` 还是 `Chat`，并在新建 `AutonomousAgent` 后调用 `setAgent(newAgent)`。重启时它会调用 `resetAllAgentSlices()`，同时清空消息和任务 store。

Agent 执行层也直接使用它。`services/agent/agent-run-model.tsx` 的 `DefaultAgentRunModel` 通过 `useAgentStore.getState()` 读取和写入 `lifecycle`。`services/agent/autonomous-agent.ts` 在重试、工作执行结束时设置 `isAgentThinking`。`services/agent/agent-api.ts` 在请求前后设置 `isAgentThinking`，并在 `analyzeTask` 中读取 `tools`，把启用工具名传给分析接口。

UI 组件侧，`components/index/landing.tsx`、`components/index/chat.tsx`、`components/console/ChatWindow.tsx`、`components/console/SummarizeButton.tsx`、`components/drawer/TaskSidebar.tsx` 等读取 agent、生命周期或思考状态来控制可见性、按钮状态和交互行为。`hooks/useTools.ts` 负责加载和切换工具，并通过 `setTools` 同步已启用工具。

## 它调用谁

本文件直接依赖 `zustand` 和 `zustand/middleware` 创建 store，并使用 `persist`、`createJSONStorage` 把部分状态写入 `localStorage`。它调用本地 `./helpers` 中的 `createSelectors`，为 store 增加按字段选择的访问方式。

类型层面，它依赖 `hooks/useTools` 的 `ActiveTool`、`services/agent/agent-run-model` 的 `AgentLifecycle`、`services/agent/autonomous-agent` 的 `AutonomousAgent`。运行时真正持久化的是 `tools` 字段，`agent` 实例和生命周期等运行态不进入持久化结果。

## 核心流程

初始化时，`createAgentSlice` 返回默认运行态：`agent: null`、`lifecycle: "offline"`、`summarized: false`、`isAgentThinking: false`。同时它把一个 resetter 注册进模块级数组 `resetters`，后续 `resetAllAgentSlices` 会遍历这些函数恢复初始 Agent 状态。

当首页启动新 Agent 时，`pages/index.tsx` 构造 `DefaultAgentRunModel`、`MessageService`、`AgentApi`、`AutonomousAgent`，然后调用 `setAgent(newAgent)`。页面因为 `agent !== null` 切换到聊天界面，随后 `newAgent.run()` 开始执行。执行期间 `DefaultAgentRunModel` 更新 `lifecycle`，`AgentApi` 和 `AutonomousAgent` 更新 `isAgentThinking`，组件通过选择器自动刷新。

工具流程相对独立：`useTools` 从 `/api/agent/tools` 加载全部工具，再结合 `localStorage` 中的开关状态算出 active 列表。每次工具开关变化时，它调用 `setTools(data.filter((tool) => tool.active))`。之后 `AgentApi.analyzeTask` 会读取 `useAgentStore.getState().tools.map((tool) => tool.name)`，把启用工具名放进请求体。

持久化流程只保留 `tools`：`persist` 的 `partialize` 返回 `{ tools: state.tools }`，存储名为 `agent-storage-v2`。这意味着刷新页面后工具选择可恢复，但当前 Agent 实例、生命周期、摘要状态、思考状态不会恢复。

## 关键函数的高层作用

`createAgentSlice` 是运行态 slice 的工厂。它定义 Agent 相关字段和 setter，并注册重置逻辑。最需要注意的是 `setAgent`：先把 `agent` 设为传入值，然后如果当前 `get().agent === null`，会执行所有 resetter。按现有代码语义，传入 `null` 时会触发重置；传入新 Agent 时不会清空状态。根据当前片段推断，这用于停止/重启后恢复初始状态，依据是首页 `handleRestart` 会显式调用 `resetAllAgentSlices()`。

`createToolsSlice` 是工具 slice 的工厂，只保存已启用工具列表。它不负责拉取工具、不负责维护 active 开关状态；这些在 `hooks/useTools.ts` 中处理。

`useAgentStore` 是对外主入口。它把两个 slice 合并成一个 Zustand store，并通过 `persist` 限定只持久化 `tools`。调用方既可以在 React 组件中订阅字段，也可以在服务类中用 `useAgentStore.getState()` 做命令式读写。

`resetAllAgentSlices` 是模块级批量重置函数。目前本文件只注册了 Agent slice 的 resetter，Tools slice 没有注册 resetter，所以重置 Agent 不会清空已启用工具。

## 修改风险

最大风险是生命周期语义被破坏。`DefaultAgentRunModel`、`AutonomousAgent`、首页按钮状态和多个组件都依赖 `lifecycle` 的具体字符串值；新增、改名或改变状态转换条件，可能导致 Agent 无法恢复、暂停后无法继续，或 UI 错误禁用启动按钮。

第二个风险是持久化边界。当前只持久化 `tools` 是有意设计，因为 `AutonomousAgent` 是包含方法和运行中依赖的类实例，不适合进 `localStorage`。如果把 `agent`、`lifecycle`、`isAgentThinking` 等运行态加入 `partialize`，刷新后很容易出现“UI 以为还在运行，但真实 Agent 实例不存在”的状态撕裂。

第三个风险是 `setAgent` 的重置副作用。它通过 `get().agent === null` 判断是否执行 resetter，实际等价于“设置为 null 后重置”。如果未来把 `setAgent(null)` 用在只想清空实例、不想重置 `summarized` 或生命周期的场景，会产生额外副作用。修改这里时要同步检查 `pages/index.tsx` 的 `handleRestart` 和所有停止/重载逻辑。

第四个风险是工具类型和持久化来源不完全一致。`useTools` 自己用 key `tools` 存完整 active 列表，而 `agentStore` 的 persist 用 `agent-storage-v2` 存已启用工具列表。两份 localStorage 数据承担不同职责：前者恢复开关 UI，后者供 Agent 请求读取启用工具。合并或改名时要同时检查 `hooks/useTools.ts` 和 `AgentApi.analyzeTask`，否则可能出现 UI 显示启用但请求没有带工具，或请求带了过期工具的情况。

第五个风险是 selector 包装依赖 `createSelectors`。组件大量使用 `useAgentStore.use.xxx()` 形式，如果移除或替换该 helper，需要迁移所有调用点，而不只是修改本文件导出。
