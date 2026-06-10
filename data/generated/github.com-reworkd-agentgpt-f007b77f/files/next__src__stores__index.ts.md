# 文件：next/src/stores/index.ts

## 一句话定位

`next/src/stores/index.ts` 是前端状态层的 barrel export 文件，用来把几个核心 Zustand store 统一转出口，方便页面、hooks 和 agent 服务通过 `../stores` 获取共享状态能力，而不必分别感知每个 store 的具体文件位置。

## 它暴露/定义了什么

这个文件自身不定义状态、类型或函数，只做三行重新导出：

```ts
export * from "./messageStore";
export * from "./agentStore";
export * from "./modelSettingsStore";
```

因此它实际向外暴露的是 `messageStore`、`agentStore`、`modelSettingsStore` 中导出的对象和函数，主要包括：

`useMessageStore`、`resetAllMessageSlices`，负责聊天/系统/任务消息列表的读写与重置。

`useAgentStore`、`resetAllAgentSlices`，负责当前 `AutonomousAgent` 实例、agent 生命周期、总结状态、思考状态以及可用 tools 的管理，其中 tools 会持久化到 `localStorage`。

`useModelSettingsStore`、`resetSettings`，负责模型设置的读取、更新与持久化，默认值来自 `getDefaultModelSettings()`。

需要注意的是，同目录下还有 `taskStore.ts`、`configStore.ts`、`agentInputStore.ts`，但它们没有从 `index.ts` 导出。调用方若需要这些 store，当前代码中是直接按具体文件路径导入。

## 谁调用它

根据当前片段，`index.ts` 的主要调用方分为三类。

第一类是页面入口，例如 `next/src/pages/index.tsx` 从 `../stores` 导入 `useAgentStore`、`useMessageStore`、`resetAllAgentSlices`、`resetAllMessageSlices`。这里是最核心的使用点：页面通过 store 控制 agent 启停、渲染聊天消息、重置会话状态。

第二类是 UI 组件，例如 `next/src/components/index/chat.tsx`、`next/src/components/index/landing.tsx`、`next/src/components/console/ChatWindow.tsx`、`next/src/components/console/SummarizeButton.tsx`、`next/src/components/drawer/TaskSidebar.tsx` 等。这些组件通过 `useAgentStore.use.xxx()` 订阅某个状态字段，驱动界面展示与按钮可用性。

第三类是业务服务和 hooks，例如 `next/src/services/agent/agent-run-model.tsx`、`next/src/services/agent/autonomous-agent.ts`、`next/src/services/agent/agent-api.ts`、`next/src/services/agent/message-service.ts`、`next/src/hooks/useSettings.ts`、`next/src/hooks/useTools.ts`。这些非组件代码通常通过 `useXStore.getState()` 直接读写状态，避免 React hook 调用限制。

## 它调用谁

`index.ts` 只调用 TypeScript/ES module 的重新导出机制，本身没有运行时业务逻辑。它依赖的三个目标文件才是实际调用链的起点。

`messageStore.ts` 调用 `zustand` 的 `create` 创建消息 store，并调用本地 `createSelectors` 生成 `store.use.xxx()` 形式的 selector。

`agentStore.ts` 调用 `zustand`、`zustand/middleware` 的 `persist` 和 `createJSONStorage`，并依赖 `AutonomousAgent`、`AgentLifecycle`、`ActiveTool` 等类型或实体。它只把 `tools` 持久化到 `localStorage`，不持久化运行中的 agent 实例。

`modelSettingsStore.ts` 同样使用 `persist` 和 `createJSONStorage`，并调用 `getDefaultModelSettings()` 构造默认模型配置。持久化时会通过 `partialize` 修正 `customModelName` 和限制 `maxTokens`。

## 核心流程

整体流程可以理解为“统一入口导出 store，业务代码按需消费”。

页面启动时，`next/src/pages/index.tsx` 从 `../stores` 取得 agent 和 message 相关 store。用户输入目标并启动 agent 后，页面创建 `DefaultAgentRunModel`、`MessageService`、`AgentApi` 和 `AutonomousAgent`，随后通过 `useAgentStore.use.setAgent()` 写入当前 agent，并调用 `newAgent.run()`。

agent 运行期间，服务层会更新状态。`AgentApi`、`AutonomousAgent` 会通过 `useAgentStore.getState()` 设置 `isAgentThinking`；`agent-run-model.tsx` 会读取或设置生命周期；`MessageService` 会通过 `useMessageStore.getState().updateMessage()` 更新已存在消息。组件层则通过 selector 订阅这些变化并重新渲染。

重启或刷新会话时，页面调用 `resetAllMessageSlices()`、`resetAllTaskSlices()`、`resetAllAgentSlices()`。其中 message 和 agent 的 reset 函数来自 `index.ts`，task 的 reset 因未被 barrel 导出，仍从 `taskStore.ts` 直接导入。

## 关键函数的高层作用

`index.ts` 没有自己的关键函数，它的关键作用是模块边界管理：决定哪些 store 属于公共状态入口，哪些 store 需要显式从具体文件导入。

`useAgentStore` 是最重要的导出之一，承载 agent 生命周期和运行中状态。它既被 React 组件订阅，也被服务层直接读写，因此是 UI 与 agent 执行逻辑之间的桥。

`useMessageStore` 负责消息列表，是聊天窗口、系统提示、任务进度消息的集中来源。它的 `addMessage` 追加消息，`updateMessage` 按 `id` 替换已有消息。

`useModelSettingsStore` 负责模型设置。`useSettings.ts` 通过它把用户配置转成运行 agent 所需的模型参数。

`createSelectors` 虽然不在本文件导出，但它影响所有这些 store 的使用方式：store 会拥有 `use` 属性，例如 `useAgentStore.use.lifecycle()`，让组件只订阅单个字段，减少无关状态变化带来的重渲染。

## 修改风险

最大风险是导出面变化。因为很多文件通过 `../stores` 导入 `useAgentStore`、`useMessageStore`、`useModelSettingsStore` 或 reset 函数，删除、重命名或移动这些导出会造成大范围编译失败。尤其 `next/src/pages/index.tsx` 是主页入口，受影响后会直接破坏核心交互。

第二个风险是误以为 `index.ts` 导出了所有 store。同目录的 `taskStore.ts`、`configStore.ts`、`agentInputStore.ts` 没有被包含。如果贸然把它们加入 barrel，短期看可能只是导入更方便，但也可能改变模块依赖图，引入循环依赖或让原本清晰的边界变模糊。根据当前片段推断，作者有意只把 agent、message、model settings 作为公共入口，而把 task、config、input 维持为显式导入；依据是多个调用点仍直接从具体 store 文件导入它们。

第三个风险是 barrel 文件会掩盖运行时副作用。虽然 `index.ts` 没有逻辑，但导入它会加载三个 store 模块，而 `agentStore` 和 `modelSettingsStore` 都配置了 `localStorage` 持久化。若在服务端渲染路径或测试环境中使用不当，可能遇到浏览器 API 不存在的问题。当前项目使用 Next.js，相关 store 主要在客户端组件、hooks 和服务运行流中消费，修改时应继续留意 SSR 边界。

第四个风险是 reset 行为分散。`resetAllAgentSlices`、`resetAllMessageSlices` 从这里导出，但 `resetAllTaskSlices` 不在这里。若新增统一 reset API，需要同时理解 agent、message、task 三套 resetter 的作用范围，避免重置不完整或意外清掉持久化配置。
