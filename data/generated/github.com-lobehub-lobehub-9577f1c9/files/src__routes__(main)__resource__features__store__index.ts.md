# 文件：src/routes/(main)/resource/features/store/index.ts

## 它负责什么

这个文件是 ResourceManager 这套资源管理界面的“路由层 store 入口”。它本身不存业务 UI，而是把 `action.ts` 里的状态动作、`initialState.ts` 的默认状态、`selectors.ts` 的派生读取方式组装成一个可直接给 React 组件使用的 Zustand store。

从职责上看，它主要做三件事：

1. 创建 `useResourceManagerStore`，作为资源管理页共享状态的单例入口。
2. 重新导出 `selectors`，让调用方能拿到一些派生逻辑。
3. 提供 `useResourceManagerFetchFolderBreadcrumb`，把文件 store 里的 folder breadcrumb 能力包一层，供资源管理页使用。

这说明它不是通用全局 store，而是 `src/routes/(main)/resource/**` 这条资源管理路由专用的状态汇合点。

## 关键组成

- [`use client`](./src/routes/(main)/resource/features/store/index.ts)  
  说明它只在客户端运行。这里会用到 React hook 和 Zustand hook。

- `createWithEqualityFn` + `subscribeWithSelector` + `shallow`  
  这是 store 的核心创建方式。`subscribeWithSelector` 允许按 selector 订阅局部状态，`shallow` 用于减少不必要的重渲染。整体上适合这种“很多组件同时读同一个 store，但只关心局部字段”的场景。

- `store()`  
  来自 [`action.ts`](./src/routes/(main)/resource/features/store/action.ts) 的工厂函数，里面把：
  - `initialState`
  - 所有 action 方法
  组合成最终 store slice。

- `export type { State } from './initialState'`  
  把状态结构类型暴露给调用方，便于测试和类型约束。

- `export { selectors } from './selectors'`  
  直接透出一组派生选择器，比如当前文件预览态、当前文件、排序后的文件列表等。

- `useResourceManagerFetchFolderBreadcrumb`  
  这是一个薄包装：内部直接调用 `useFileStore((s) => s.useFetchFolderBreadcrumb)(slug)`。它把文件系统里的 breadcrumb 查询能力转交给资源管理页面使用。

## 上下游关系

上游是这个目录下的三个核心文件：

- [`action.ts`](./src/routes/(main)/resource/features/store/action.ts)：定义状态操作、选择文件、切换模式、批量操作等。
- [`initialState.ts`](./src/routes/(main)/resource/features/store/initialState.ts)：定义默认状态和字段类型。
- [`selectors.ts`](./src/routes/(main)/resource/features/store/selectors.ts)：定义派生读法和一些纯函数工具。

下游主要是资源管理相关页面和组件，典型调用点包括：

- [`src/routes/(main)/resource/(home)/index.tsx`](./src/routes/(main)/resource/(home)/index.tsx)：首页路由挂载后，会先同步 `category` 和 `libraryId`。
- [`src/features/ResourceManager/index.tsx`](./src/features/ResourceManager/index.tsx)：主容器读取 `mode`、`currentViewItemId`、`libraryId`，并驱动 Explorer / Editor / PageEditor 的切换。
- [`src/routes/(main)/resource/features/hooks/useCurrentFolderId.ts`](./src/routes/(main)/resource/features/hooks/useCurrentFolderId.ts)：通过 breadcrumb 推导当前 folder id。
- [`src/routes/(main)/resource/features/hooks/useResourceManagerUrlSync.ts`](./src/routes/(main)/resource/features/hooks/useResourceManagerUrlSync.ts)：把排序状态和 URL 查询参数互相同步。
- `Explorer`、`Header`、`Toolbar`、`LibraryHierarchy`、`Editor` 等组件：大量使用 `useResourceManagerStore` 读写局部字段。

根据当前片段推断，这个 store 也是资源管理页“单页应用状态总线”，负责把 URL、文件 store、知识库 store 和页面视图状态连起来。

## 运行/调用流程

1. 资源管理首页路由 [`src/routes/(main)/resource/(home)/index.tsx`](./src/routes/(main)/resource/(home)/index.tsx) 挂载。
2. 页面通过 `useResourceManagerStore` 把 URL 中的 `category`、`libraryId` 同步到 store。
3. `ResourceManager` 主组件读取 store 的 `mode`、`currentViewItemId`、`libraryId`，决定显示 Explorer、文件编辑器还是 PageEditor。
4. 各子组件按需订阅 store 的局部字段：
   - 选择状态
   - 排序字段
   - 搜索词
   - 当前文件
   - 视图模式
5. 用户操作触发 action：
   - `setMode`、`setCurrentViewItemId` 控制页面内视图切换
   - `setSelectedFileIds`、`selectAllResources`、`clearSelectAllState` 管理批量选择
   - `onActionClick` 处理删除、从知识库移除、批量切分、删除知识库等操作
6. `selectors.ts` 提供派生结果：
   - `getCurrentFile`
   - `getSortedFileList`
   - `isFilePreviewMode`
   - `getExplorerSelectAllUiState`
7. `useResourceManagerFetchFolderBreadcrumb` 再通过 `useFileStore` 取 folder breadcrumb，辅助推导当前目录 ID。

一个很关键的点是：这个 store 不只是“界面状态”，它还承担了跨 store 协调。比如批量删除和批量切分会临时去读 `useFileStore`、`useKnowledgeBaseStore`、`resourceService`，说明它是资源管理页的操作编排层。

## 小白阅读顺序

1. 先看 [`initialState.ts`](./src/routes/(main)/resource/features/store/initialState.ts)，弄清楚有哪些状态字段。
2. 再看 [`action.ts`](./src/routes/(main)/resource/features/store/action.ts)，理解这些字段如何被修改，以及批量操作如何落到文件库和知识库。
3. 然后看 [`selectors.ts`](./src/routes/(main)/resource/features/store/selectors.ts)，理解“怎么算当前文件、怎么算选中数量、怎么算排序”。
4. 最后回到这个 [`index.ts`](./src/routes/(main)/resource/features/store/index.ts)，把三部分拼起来，理解它是怎么暴露给页面用的。
5. 结合 [`src/features/ResourceManager/index.tsx`](./src/features/ResourceManager/index.tsx) 和 [`src/routes/(main)/resource/(home)/index.tsx`](./src/routes/(main)/resource/(home)/index.tsx) 看实际调用，理解它在页面生命周期中的位置。

## 常见误区

- 它不是“全局通用 store”，而是资源管理路由专属 store。不要把它和 `src/store/file`、`src/store/library` 混为一谈。
- `useResourceManagerStore` 是单例 hook，不是每个页面实例各自创建一份。`createStore()` 只是构造方式，真正导出的是已经创建好的实例。
- `selectors.getSortedFileList` 看起来像主路径，但注释里已经标了 `@deprecated`，而且它直接读 `useFileStore.getState().fileList`，不是当前最推荐的数据流。
- `selectAllState === 'all'` 时，`selectedFileIds` 的语义会反转成“排除项”，不是普通的“已选项列表”。这一点在批量删除和计数逻辑里很容易看错。
- `useResourceManagerFetchFolderBreadcrumb` 只是薄封装，不是独立数据源。真实能力仍然来自 `useFileStore`。
- `onActionClick('deleteLibrary')` 会在删除后直接跳转到 `/knowledge`，这说明某些操作已经超出当前页面本身，属于跨页面导航行为。
