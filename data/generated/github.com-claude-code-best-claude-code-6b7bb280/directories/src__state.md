# 目录：src/state

## 它负责什么

`src/state` 是这个仓库里最核心的“应用状态层”。它不负责渲染 UI，也不直接处理模型请求，而是统一承接整套 REPL/CLI 运行时的全局状态：会话配置、权限上下文、任务树、插件与 MCP 连接、远程会话、提示建议、队友视图、桥接状态、音频/语音相关上下文等。可以把它理解成整个终端界面的共享内存和状态中枢。

从当前代码片段看，这一层的设计目标非常明确：  
1. 用一个轻量 store 承载状态变化。  
2. 用 React context 暴露给 UI。  
3. 用 selector 型 hook 控制重渲染。  
4. 用副作用回调把状态变化同步到外部系统，比如 settings、权限模式、全局配置、认证缓存等。

它既服务于交互式 REPL，也服务于 headless、MCP、bridge、remote、工具面板等多条路径。根据当前片段推断，这个目录是“所有上层模块共享状态契约”的起点。

## 直接子目录地图

这个目录本身很小，只有一个直接子目录：

- `src/state/__tests__`：当前放的是 `store` 的单元测试，主要验证 `createStore` 的基础行为，比如 `getState`、`setState`、`subscribe`、取消订阅和 `onChange` 回调。

没有看到更深层的业务子目录，说明这里更偏“状态基础设施”，而不是按业务再拆分层级。

## 关键入口

这个目录里的关键入口主要是 4 个文件：

- `src/state/AppState.tsx`：对外入口。提供 `AppStateProvider`、`useAppState`、`useSetAppState`、`useAppStateStore`、`useAppStateMaybeOutsideOfProvider`，并向外重导出 `AppStateStore`、`AppState` 等类型。
- `src/state/AppStateStore.ts`：状态类型定义和默认初始状态工厂，`getDefaultAppState()` 在这里。
- `src/state/store.ts`：最底层的通用 store 实现，`createStore<T>()` 负责状态读写和订阅。
- `src/state/onChangeAppState.ts`：状态变更的副作用同步点，把 `AppState` 的变化推送到外部配置、会话元数据、缓存清理等流程。

辅助入口还有：

- `src/state/selectors.ts`：纯 selector 工具，负责从 `AppState` 派生出“当前查看的队友任务”“输入应该路由给谁”等计算结果。
- `src/state/teammateViewHelpers.ts`：队友视图切换的操作函数，直接修改 `viewingAgentTaskId`、`viewSelectionMode` 和任务释放逻辑。

## 主流程位置

主流程可以按“初始化 -> 订阅 -> 变更同步”理解。

1. `AppStateProvider` 在 `src/state/AppState.tsx` 内创建 store。它会把 `getDefaultAppState()` 或外部传入的 `initialState` 包装到 React context 中，并防止嵌套 provider。
2. 组件层通过 `useAppState(selector)` 订阅局部切片。这里使用 `useSyncExternalStore`，所以只有 selector 结果变化时才重渲染。
3. `useSetAppState()` 提供纯写入口，非 React 代码也能通过 `useAppStateStore()` 直接拿到 store 对象。
4. `onChangeAppState()` 负责把状态变化同步到系统外部。当前片段里最重要的几条同步链路是：
   - `toolPermissionContext.mode` 变化时，通知 CCR / SDK 的会话元数据。
   - `mainLoopModel` 变化时，更新进程内模型覆盖。
   - `expandedView`、`verbose`、`tungstenPanelVisible` 变化时，写回全局配置。
   - `settings` 变化时，清理认证缓存并重新应用环境变量。
5. `teammateViewHelpers.ts` 这条支路专门处理“查看队友任务”模式，确保进入/退出视图时任务状态、保留标记和回收时机一致。

换句话说，这里不是单纯的“状态容器”，而是“状态 + 约束 + 同步副作用”三者一起工作的地方。

## 推荐阅读顺序

1. 先看 `src/state/store.ts`，确认这个项目最底层 store 的语义：如何更新、如何通知、何时跳过重复写入。
2. 再看 `src/state/AppStateStore.ts`，理解 `AppState` 的整体形状，以及默认状态是怎么拼出来的。
3. 接着看 `src/state/AppState.tsx`，把“状态类型”和“React 访问方式”串起来。
4. 然后看 `src/state/onChangeAppState.ts`，理解状态变化为什么会影响配置、认证和会话元数据。
5. 最后看 `src/state/selectors.ts` 和 `src/state/teammateViewHelpers.ts`，补齐派生逻辑和 UI 切换流程。

如果只想先抓主干，优先顺序就是：`AppStateStore.ts` -> `AppState.tsx` -> `onChangeAppState.ts`。

## 常见误区

1. 把 `src/state` 当成“纯前端 UI 状态”。实际上它同时承载 CLI、MCP、remote、权限、插件和外部同步逻辑，范围远大于页面局部 state。
2. 只盯 `AppState.tsx`，忽略 `AppStateStore.ts`。真正的状态结构和默认值都在后者，前者更多是 React 适配层。
3. 把 `createStore` 当成完整状态管理框架。它其实很轻，只提供最小的 `getState/setState/subscribe` 能力。
4. 在 selector 里构造新对象。这里的订阅依赖 `Object.is`，返回新对象会导致不必要重渲染，这也是 `useAppState` 注释里特别强调的点。
5. 忽略 `onChangeAppState`。很多“看起来像设置没生效”的问题，其实是因为状态变化需要通过这里同步到全局配置、缓存或外部会话。
6. 误以为 `teammateViewHelpers.ts` 只是 UI 辅助函数。它实际上在维护任务生命周期和 transcript 视图切换，和任务回收策略直接相关。

总体上，`src/state` 是这套 CLI/REPL 系统的状态底座。读懂它，就能更快定位很多跨组件、跨命令、跨模式的联动问题。
