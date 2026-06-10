# 文件：next/src/stores/agentInputStore.ts

## 一句话定位

`next/src/stores/agentInputStore.ts` 是首页 Agent 启动表单的轻量级 Zustand 状态仓库，负责保存用户当前输入的 `nameInput` 和 `goalInput`，并向页面、模板卡片等组件提供读取与更新入口。

## 它暴露/定义了什么

该文件定义了一个 `AgentInputSlice` 状态切片，包含两类内容：

状态字段包括 `nameInput` 和 `goalInput`。从当前使用方式看，`goalInput` 是真正驱动 Agent 启动的目标文本；`nameInput` 更多用于模板或聊天界面展示、传递 Agent 名称，但在首页启动逻辑里并不是创建 Agent 的核心参数。

动作函数包括 `setNameInput`、`setGoalInput` 和 `resetInputs`。前两个用于单独更新输入框内容，`resetInputs` 用于把两项输入恢复为空字符串。

文件最终导出 `useAgentInputStore`。它不是裸的 Zustand store，而是经过 `createSelectors` 包装后的 store，因此调用侧常见写法是 `useAgentInputStore.use.goalInput()`、`useAgentInputStore.use.setGoalInput()`，每个状态字段和动作都会被自动生成一个 selector hook。

## 谁调用它

直接调用者主要有两个：

`next/src/pages/index.tsx` 是核心调用方。首页读取 `nameInput`、`goalInput`，把它们传给 `Chat` 或 `Landing` 组件，同时把 `setGoalInput`、`setNameInput` 传入表单相关子组件。首页还在用户登录恢复流程中从 `localStorage` 读取暂存的 Agent 数据，并写回该 store。

`next/src/components/templates/TemplateCard.tsx` 是模板入口调用方。用户点击某个模板卡片时，它会调用 `setNameInput(model.name)` 和 `setGoalInput(model.promptTemplate)`，然后跳转到首页，让首页表单预填模板名称与目标提示词。

根据当前片段推断，`Chat`、`Landing` 本身并不直接 import 这个 store，而是通过 `index.tsx` 接收相关 props；依据是搜索结果中直接 import `useAgentInputStore` 的文件只有上述两个。

## 它调用谁

该文件依赖 `zustand` 的 `create` 和 `StateCreator` 来创建 store，依赖本地 `next/src/stores/helpers.ts` 中的 `createSelectors` 生成按字段访问的 `use.xxx()` 选择器。

它没有调用业务服务、后端 API、Agent 执行逻辑或持久化中间件。与 `agentStore`、`configStore`、`modelSettingsStore` 不同，它没有使用 `persist`，所以输入状态默认只存在于前端内存中，刷新页面通常会丢失。登录前后的短暂保存逻辑不在本文件，而是在 `next/src/pages/index.tsx` 中通过 `localStorage` 手动完成。

## 核心流程

用户在首页输入目标时，`Landing` 通过 props 调用 `setGoalInput`，更新 `goalInput`。首页组件通过 `useAgentInputStore.use.goalInput()` 订阅该值，并用它计算 `disableStartAgent`：如果目标为空，启动按钮会被禁用。

用户点击启动或按下 Enter 时，`index.tsx` 的 `handlePlay(goalInput)` 被触发。实际创建 Agent 的逻辑并不在本 store，而是在首页里根据 `goalInput` 创建 `DefaultAgentRunModel`、`AgentApi` 和 `AutonomousAgent`。

用户点击模板卡片时，`TemplateCard` 将模板的名称和 prompt 写入 store，然后路由跳转到 `/`。首页读取到新的 `nameInput` 和 `goalInput` 后，表单或聊天区就能展示这些预填内容。

未登录用户启动时，首页会把 `{ name, goal }` 暂存到 `localStorage` 并弹出登录框；登录状态恢复后，首页再把暂存数据写回 `agentInputStore`。这说明该 store 负责 UI 当前态，而跨登录流程的临时持久化由页面层兜底。

## 关键函数的高层作用

`createAgentInputSlice` 是本文件的核心工厂函数。它接收 Zustand 的 `set`，返回初始状态和三个更新动作。它把输入状态的定义集中在一个 slice 中，便于未来和其他 store slice 合并，虽然当前文件只创建了这一种 slice。

`setNameInput` 和 `setGoalInput` 是最重要的写入口。它们分别更新名称和目标文本，不做 trim、校验或副作用处理。目标为空、目标 trim、Agent 生命周期判断等规则都放在 `index.tsx`，这让 store 保持为简单状态容器。

`resetInputs` 用于恢复 `initialInputState`。当前搜索片段中没有看到直接调用，因此根据当前片段推断它是预留给重置表单或未来全局 reset 流程的接口。

`resetters` 数组在本文件内会收集一个重置函数，但当前片段没有看到导出或消费。根据当前片段推断，这可能是沿用了其他 store 的全局 reset 模式但尚未接入；依据是 `index.tsx` 中存在 `resetAllAgentSlices`、`resetAllMessageSlices`、`resetAllTaskSlices`，而本文件没有对应导出。

## 修改风险

第一类风险是破坏 selector 调用约定。调用方使用的是 `useAgentInputStore.use.xxx()`，如果移除 `createSelectors`、改名字段或改变导出形态，会直接影响 `index.tsx` 和 `TemplateCard.tsx`。

第二类风险是把业务逻辑塞进 store。当前 store 只保存原始输入，不负责 trim、鉴权、启动 Agent、localStorage 恢复。如果在 `setGoalInput` 中加入自动清洗或副作用，可能改变 Enter 启动、模板预填、未登录暂存等流程的行为。

第三类风险是持久化语义变化。如果给这个 store 加 `persist`，用户刷新后可能保留旧目标，影响首页初始状态；如果产品期望每次打开都是空表单，这会是行为回归。相反，如果要支持刷新恢复，需要同时梳理 `index.tsx` 里已有的 `localStorage` 登录恢复逻辑，避免两套持久化互相覆盖。

第四类风险是 reset 行为不完整。当前 `handleRestart` 会重置 message、task、agent，但没有显式重置输入。若把 `resetInputs` 接入全局重置，聊天结束或重新加载时表单内容可能被清空；这可能是期望行为，也可能破坏用户修改目标后再次启动的体验，修改前需要确认产品意图。
