# 目录：src/store/agent

## 它负责什么

`src/store/agent` 是这一仓库里“Agent 配置与能力状态”的 Zustand 状态域。根据当前片段推断，它主要负责把一个 agent 在编辑、选择、保存、重置、能力挂载时需要的状态和动作集中管理起来，并向外提供统一的 `useAgentStore` 读取入口。这个目录不是页面层代码，而是偏底层的状态中枢：上层功能通常通过 selector 读数据，通过 action 改数据，再由 store 统一合并和暴露。

从结构上看，它把状态拆成多个 slice 再组合：`agent`、`bot`、`builtin`、`knowledge`、`plugin`。其中 `agent` 和 `builtin` 同时提供 state 与 action，`bot`、`knowledge`、`plugin` 更像能力域动作层。`selectors/` 则是读取层，专门把 store 内部结构整理成更稳定的查询接口。

## 直接子目录地图

`src/store/agent` 下的直接子目录只有三类，职责分得比较清楚。

`src/store/agent/slices/`：状态与动作的拼装区。这里按领域拆成 `agent`、`bot`、`builtin`、`knowledge`、`plugin` 五个子域。每个子域通常有 `action.ts`、`index.ts`，部分还带 `initialState.ts` 和测试文件。整体作用是把单个领域的状态逻辑独立出来，再交给总 store 聚合。

`src/store/agent/selectors/`：只读查询层。这里按查询主题拆出 `agentByIdSelectors.ts`、`builtinAgentSelectors.ts`、`chatConfigSelectors.ts`、`chatConfigByIdSelectors.ts`、`selectors.ts`，并通过 `index.ts` 统一导出。根据文件名推断，这里主要处理“按 ID 查 agent / builtin agent”“按 chat config 查配置”“组合型派生数据”等读操作。

`src/store/agent/utils/`：通用辅助工具。目前可见的核心文件是 `localAgentWorkingDirectoryStorage.ts`，从名字看像是给 agent 相关工作目录做本地持久化或读取辅助的工具层。

## 关键入口

最重要的入口是 `src/store/agent/index.ts`。它只做两件事：导出 `AgentStore` 类型，以及导出 `useAgentStore`、`getAgentStoreState`。这意味着对外使用方基本都从这里进入，而不是直接碰内部 slice。

真正的 store 组装发生在 `src/store/agent/store.ts`。这里完成了几个关键动作：

1. 用 `initialState` 初始化基础状态。
2. 通过 `flattenActions(...)` 把各个 slice 的 action 合并成一个 store。
3. 用 `createWithEqualityFn` 创建 hook，并配合 `shallow` 降低订阅抖动。
4. 用 `createDevtools('agent')` 接入调试工具。
5. 通过 `expose('agent', useAgentStore)` 把 store 暴露给外部调试或运行时接入。

`src/store/agent/initialState.ts` 是基础状态入口。当前可见它只合并了 `initialAgentSliceState` 和 `initialBuiltinAgentSliceState`，说明 store 的“静态初始值”主要来自这两个 slice，其他域更多像行为扩展。

## 主流程位置

如果把这个目录的主流程画成一条线，核心路径大致是：

`src/store/agent/store.ts` 负责创建 store  
`src/store/agent/initialState.ts` 负责拼接初始状态  
`src/store/agent/slices/*/action.ts` 负责定义各领域 action  
`src/store/agent/selectors/*` 负责把内部状态整理成外部可消费的查询接口  
`src/store/agent/index.ts` 负责对外导出统一入口

其中最值得关注的“总装配点”是 `store.ts`。它把 `createAgentSlice`、`createBotSlice`、`createBuiltinAgentSlice`、`createKnowledgeSlice`、`createPluginSlice` 和 `ResetableStoreAction` 一次性合并，说明这个目录的设计目标不是单一业务，而是把 agent 相关能力拼成一个统一状态容器。`ResetableStoreAction` 还暗示这里支持整体重置，适合编辑器式或表单式流程。

selector 的主路径则在 `src/store/agent/selectors/selectors.ts` 及其同级文件。根据命名推断，这里是上层页面、配置面板、预览逻辑最常调用的读层，避免业务代码直接依赖 store 内部字段布局。

## 推荐阅读顺序

1. 先看 `src/store/agent/index.ts`，确认对外出口。
2. 再看 `src/store/agent/store.ts`，理解 store 是怎么组出来的。
3. 接着看 `src/store/agent/initialState.ts`，把状态骨架先建立起来。
4. 然后按 `src/store/agent/slices/agent/index.ts`、`src/store/agent/slices/builtin/index.ts`、`src/store/agent/slices/bot/index.ts`、`src/store/agent/slices/knowledge/index.ts`、`src/store/agent/slices/plugin/index.ts` 的顺序，理解每个领域的职责。
5. 最后看 `src/store/agent/selectors/index.ts` 和各 selector 文件，补齐读取路径。

## 常见误区

不要把 `src/store/agent` 当成页面组件目录，它是状态层，不是 UI 层。

不要直接从页面代码读取内部 slice 字段，而绕过 selector；这个目录已经提供了更稳定的查询入口，直接读内部结构会让上层耦合变重。

不要只改某个 slice 的 action，却忘了 `store.ts` 里的合并顺序和 `initialState.ts` 的初始值；这两处才是全局是否真正生效的关键位置。

不要忽略 `useAgentStore` 和 `getAgentStoreState` 的区别：前者适合响应式订阅，后者适合一次性取值或调试式访问。若使用场景选错，容易造成不必要的重渲染或状态读取时机问题。

最后，`selectors/` 和 `slices/` 的职责要分清：前者偏“怎么读”，后者偏“怎么改”。把两者混在一起，后续维护成本会明显上升。
