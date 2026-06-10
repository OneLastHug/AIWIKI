# 目录：packages/desktop/src/renderer/pages/guid

## 它负责什么

`guid` 是桌面端 renderer 里的一个页面目录，按当前代码片段推断，它承担的是“引导式发起对话/任务”的页面职责：让用户先选模型、选助手/Agent、配置技能与 MCP 服务器，再输入内容并发送。它不是一个纯展示页，而是一个把“选择、编辑、发送”串起来的工作台入口。

从 `GuidPage.tsx` 的依赖关系看，这里同时处理了几类状态：模型选择、Agent 选择、输入框与附件、@ mention 选择、技能开关、MCP 服务器选择，以及发送前的最终整合。也就是说，这个目录更像是一个页面级编排层，具体交互拆成多个小组件和 hooks 来承接。

## 直接子目录地图

这个目录下只有三类子目录，层次不深，适合按职责理解：

- `components/`：页面拆分出来的视觉与交互组件。根据文件名看，主要覆盖 Agent 展示条、助手选择区、动作栏、输入卡片、模型选择器、骨架屏、脚注、mention 下拉框、预设 Agent 标签、快捷按钮、技能市场横幅等。
- `hooks/`：页面状态与流程逻辑的拆分层。这里集中放了 Agent 可用性、Custom Agent 加载、Agent 选择、输入管理、mention 管理、模型选择、发送逻辑、预设助手解析、占位符打字效果等 hooks。
- `utils/`：少量页面内部工具函数，负责光标位置、模型相关的辅助计算。

目录内还包含若干平级文件：`GuidPage.tsx`、`index.tsx`、`constants.ts`、`types.ts`、`index.module.css`。它们通常分别对应页面主组件、对外入口、静态常量、类型定义和样式。

## 关键入口

这个目录的直接入口是 `index.tsx`，它只做了一件事：把默认导出转发到 `./GuidPage`。因此，真正的页面入口和主控制器是 `GuidPage.tsx`。

从页面结构看，`GuidPage.tsx` 又是整个目录的编排中心。它直接引入并组合了 `AgentPillBar`、`AssistantSelectionArea`、`GuidActionRow`、`GuidInputCard`、`GuidModelSelector`、`MentionDropdown`、`QuickActionButtons` 等组件，也接入了 `useGuidAgentSelection`、`useGuidInput`、`useGuidMention`、`useGuidModelSelection`、`useGuidSend`、`useTypewriterPlaceholder` 等 hooks。换句话说，入口链路是：

`index.tsx` -> `GuidPage.tsx` -> 页面组件群 + 状态 hooks

## 主流程位置

主流程基本都收敛在 `GuidPage.tsx` 里。按当前片段推断，它的顺序大致是：

1. 初始化页面级状态，读取语言环境、路由状态和输入焦点样式。
2. 通过 `ipcBridge` 拉取 builtin skills 与可用 skills，合并成技能目录。
3. 通过 `ensureBackendMcpCatalog()` 拉取可用 MCP servers。
4. 使用 `useGuidModelSelection('aionrs')` 建立模型选择上下文。
5. 基于路由状态调用 `useGuidAgentSelection(...)`，完成 Agent 预选、重置和上下文计算。
6. 通过 `useGuidInput(...)` 管理文本、文件、目录、加载态。
7. 通过 `useGuidMention(...)` 处理 mention 搜索、下拉选择与输入框联动。
8. 通过 `useGuidSend(...)` 汇总所有前置状态，形成最终发送流程。
9. 在输入变更、键盘事件、技能开关、MCP 选择等交互中，把多个 hooks 的状态协调起来。

如果要找“业务主线”，就看 `GuidPage.tsx`；如果要找“输入如何变成发送动作”，优先看 `hooks/useGuidSend.ts`；如果要找“Agent 怎么被选中并映射到页面状态”，优先看 `hooks/useGuidAgentSelection.ts`。

## 推荐阅读顺序

1. `index.tsx`，先确认页面对外入口很薄。
2. `GuidPage.tsx`，看页面级编排和状态流转。
3. `hooks/useGuidModelSelection.ts`、`hooks/useGuidAgentSelection.ts`、`hooks/useGuidInput.ts`、`hooks/useGuidMention.ts`、`hooks/useGuidSend.ts`，按“模型 -> Agent -> 输入 -> mention -> 发送”的顺序理解主流程。
4. `components/GuidInputCard.tsx`、`components/GuidActionRow.tsx`、`components/GuidModelSelector.tsx`、`components/MentionDropdown.tsx`，再回头看 UI 如何承接状态。
5. `constants.ts`、`types.ts`、`utils/modelUtils.ts`、`utils/caretUtils.ts`，最后补齐常量、类型和局部工具。

## 常见误区

- 容易把 `index.tsx` 当成主逻辑文件，但它其实只是 re-export，真正入口是 `GuidPage.tsx`。
- 容易把这个目录理解成“纯 UI 目录”，但它实际上同时包含页面级编排、异步加载、发送整合和多状态协调。
- 容易只看 `components/`，忽略 `hooks/`，结果看不懂为什么页面会同时管理模型、Agent、mention、skills、MCP 和发送。
- 容易把 `guid` 里的 mention 逻辑误认为全局聊天输入的通用逻辑；从现有代码看，这里有自己的页面约束，比如首页不会因为输入 `@` 自动弹出 mention 列表，相关行为在 `handleInputChange` 里被特别处理。
- 容易忽视 `ipcBridge` 和 `ensureBackendMcpCatalog()` 这类外部依赖。这个页面不是静态组合，而是明显依赖运行时能力与后端目录数据。
