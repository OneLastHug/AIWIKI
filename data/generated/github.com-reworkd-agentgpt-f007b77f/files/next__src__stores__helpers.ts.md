# 文件：next/src/stores/helpers.ts

## 一句话定位

`next/src/stores/helpers.ts` 是前端 Zustand store 的选择器增强器：它把普通的 `useXStore` hook 包装成带 `.use.<stateKey>()` 形式的细粒度 selector API，供页面、组件和 hooks 按字段订阅 store，减少不必要的重新渲染。

## 它暴露/定义了什么

这个文件主要定义两部分：

`WithSelectors<S>` 是一个 TypeScript 辅助类型。它从传入的 Zustand bound store 中推断 `getState()` 返回的状态对象 `T`，然后给 store 扩展一个 `use` 对象；`use` 的每个 key 对应状态对象中的同名 key，值是一个无参 hook，返回该 key 对应的状态或 action。

`createSelectors` 是唯一导出的函数。它接收一个 `UseBoundStore<StoreApi<object>>`，直接在该 store 实例上挂载 `store.use = {}`，再遍历 `store.getState()` 的所有顶层 key，为每个 key 生成 `() => store((s) => s[key])` 这样的 selector hook，最后返回增强后的 store。

## 谁调用它

它在各个 Zustand store 定义文件中被调用，用来包装 `create(...)` 生成的原始 store。当前引用包括：

`next/src/stores/messageStore.ts`、`next/src/stores/agentInputStore.ts`、`next/src/stores/agentStore.ts`、`next/src/stores/configStore.ts`、`next/src/stores/taskStore.ts`、`next/src/stores/modelSettingsStore.ts`。

这些 store 暴露出去后，业务侧大量通过 `.use` 访问。例如 `next/src/pages/index.tsx` 使用 `useMessageStore.use.addMessage()`、`useMessageStore.use.messages()`、`useAgentStore.use.lifecycle()`、`useAgentInputStore.use.goalInput()`；`next/src/hooks/useTools.ts` 使用 `useAgentStore.use.setTools()`；`next/src/hooks/useSettings.ts` 使用 `useModelSettingsStore.use.modelSettings()`；`ChatWindow`、`TaskSidebar`、`SummarizeButton`、`TemplateCard` 等组件也依赖这种访问方式。

## 它调用谁

`helpers.ts` 自身只依赖 `zustand` 的类型 `StoreApi` 和 `UseBoundStore`。运行时核心调用来自传入 store 的两个能力：

`store.getState()`：读取当前 store 的状态对象，用于枚举所有顶层字段。

`store(selector)`：Zustand bound store 本身也是 hook，传入 selector 后可让 React 组件只订阅对应字段。

它不直接调用业务 store，也不关心 `persist`、`StateCreator`、slice resetter 等具体实现；这些都在各个 store 文件中完成。

## 核心流程

核心流程很短，但影响面很大。

第一步，业务 store 先通过 `create<SomeSlice>()(...)` 创建 Zustand store。部分 store 会叠加 middleware，例如 `agentStore.ts` 和 `configStore.ts` 使用 `persist`、`createJSONStorage` 等。

第二步，store 定义文件把原始 store 传入 `createSelectors`。例如 `useAgentStore = createSelectors(create<AgentSlice & ToolsSlice>()(...))`。

第三步，`createSelectors` 通过类型断言把原 store 视作 `WithSelectors<typeof _store>`，这一步是为了告诉 TypeScript：返回值除了原有 hook 能力，还会多一个 `.use` 字段。

第四步，它初始化 `store.use = {}`，随后用 `Object.keys(store.getState())` 拿到当前状态对象的所有顶层 key，包括普通状态字段和 action 函数字段。

第五步，对每个 key 生成一个 selector hook：`store.use[key] = () => store((s) => s[key])`。业务代码调用 `useAgentStore.use.lifecycle()` 时，本质上就是调用 Zustand hook 并订阅 `state.lifecycle`。

## 关键函数的高层作用

`createSelectors` 的作用是统一 store 的消费方式。没有它时，组件通常需要写 `useAgentStore((state) => state.lifecycle)`；有了它之后，可以写成 `useAgentStore.use.lifecycle()`。这既减少重复 selector 代码，也让调用方更明确地按字段订阅。

它的另一个作用是性能约束。组件只订阅单个字段或 action，而不是读取整个 store 对象。根据文件注释，这个设计来自 Zustand 官方推荐的 auto-generating selectors 思路。

`WithSelectors` 只是类型层封装，用来把运行时新增的 `.use` 结构表达给 TypeScript。它不产生运行时代码。

## 修改风险

最大风险是 `.use` API 已经成为跨页面、跨组件的公共约定。`next/src/pages/index.tsx`、`next/src/hooks/useTools.ts`、`next/src/hooks/useSettings.ts` 以及多个组件都直接调用 `useXStore.use.someKey()`。如果修改返回结构、字段命名、初始化时机或 selector 签名，会造成大面积编译错误或运行时 hook 调用失败。

第二个风险是它只枚举 `getState()` 在创建时已有的顶层 key。如果某个 store 后续动态添加状态字段，`createSelectors` 不会自动补齐对应 selector。根据当前片段推断，仓库内 store 都是在初始化时声明完整 slice，因此这个限制目前可接受；依据是各 store 文件均在 `create(...)` 回调中返回固定对象。

第三个风险是它会直接 mutate 原始 store：`store.use = {}`。这符合当前用法，但如果未来引入冻结对象、代理 store、或封装更严格的 Zustand helper，这种原地扩展可能不兼容。

第四个风险是 selector 只按顶层 key 生成，不能处理深层字段。例如 `modelSettings` 如果是对象，`useModelSettingsStore.use.modelSettings()` 订阅的是整个对象；对象内部任一属性变更都可能触发依赖它的组件更新。若要生成深层 selector，需要重新设计类型和运行时遍历，影响范围会明显扩大。

第五个风险是 action 也会被当作 key 生成 hook，例如 `setAgent`、`addMessage`、`updateSettings`。这在 Zustand 中通常可行，因为 action 函数引用一般稳定；但如果某个 store 更新时重新创建 action 函数，依赖这些 action selector 的组件可能出现额外渲染。当前 slice 写法主要在初始化时创建 action，风险较低。
