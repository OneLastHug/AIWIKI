# 目录：src/routes/(main)/resource/features/store

## 它负责什么

`src/routes/(main)/resource/features/store` 是 Resource 页面局部使用的资源管理状态层。它不是全局的文件数据仓库，而是围绕“资源管理器页面 UI 状态”和“批量操作状态”建立的 zustand store。

从代码看，它主要负责这些事情：

- 记录当前资源页的浏览模式，例如 `explorer`、`editor` 等 `ResourceManagerMode`。
- 记录当前选中的分类 tab：`category: FilesTabs`。
- 记录当前所在知识库：`libraryId?: string`。
- 记录当前正在查看的资源项：`currentViewItemId?: string`。
- 记录搜索、排序和视图模式：
  - `searchQuery`
  - `sorter`
  - `sortType`
  - `viewMode`
- 管理文件列表的多选状态：
  - `selectedFileIds`
  - `selectAllState`
- 为批量删除、批量分块、从知识库移除、删除知识库等操作提供统一 action。
- 暴露少量 selector，供 UI 判断当前是否处于预览模式、文件是否被选中、全选控件该显示什么状态等。

这个目录可以理解为 Resource 页面自己的“控制面板状态”。真正的文件数据、知识库数据、资源查询参数、文件删除和分块等能力来自其他 store 或 service，例如 `@/store/file`、`@/store/library`、`@/services/resource`。

## 关键组成

这个目录下的核心文件很少：

```text
src/routes/(main)/resource/features/store
├── action.ts
├── action.test.ts
├── index.ts
├── initialState.ts
├── selectors.ts
└── selectors.test.ts
```

`index.ts` 是入口文件。

它使用：

- `createWithEqualityFn` 创建 zustand store。
- `subscribeWithSelector` 支持按 selector 订阅。
- `shallow` 作为默认 equality function，减少组件订阅数组或对象时的无意义渲染。
- `store()` 从 `action.ts` 生成完整 store 定义。
- `useFileStore` 暴露 `useResourceManagerFetchFolderBreadcrumb`，把文件 store 中的 `useFetchFolderBreadcrumb` 包装成资源管理器语义下的 hook。

核心导出包括：

```ts
export const createStore = () =>
  createWithEqualityFn<Store>()(subscribeWithSelector(store()), shallow);

export const useResourceManagerStore = createStore();

export { selectors } from './selectors';

export const useResourceManagerFetchFolderBreadcrumb = (
  slug?: string | null,
): SWRResponse<FolderCrumb[]> => {
  return useFileStore((s) => s.useFetchFolderBreadcrumb)(slug);
};
```

`initialState.ts` 定义状态结构和默认值。

关键类型包括：

- `ViewMode = 'list' | 'masonry'`
- `SelectAllState = 'all' | 'loaded' | 'none'`
- `State`

默认状态是：

```ts
{
  category: FilesTabs.All,
  currentViewItemId: undefined,
  libraryId: undefined,
  mode: 'explorer',
  pendingRenameItemId: null,
  searchQuery: null,
  selectAllState: 'none',
  selectedFileIds: [],
  sortType: SortType.Desc,
  sorter: 'createdAt',
  viewMode: 'list',
}
```

这里最需要注意的是 `selectAllState` 和 `selectedFileIds` 的组合语义：

- `selectAllState === 'none'`：没有全选，`selectedFileIds` 表示普通选中的文件 id。
- `selectAllState === 'loaded'`：选择当前已加载的数据，`selectedFileIds` 仍然表示已选中的文件 id。
- `selectAllState === 'all'`：选择查询结果中的全部资源，此时 `selectedFileIds` 不再表示“选中项”，而是表示“被排除的 id”。

这个设计是为了支持分页或无限加载场景下的“选择全部查询结果”，而不只是选择当前页面已经加载的资源。

`action.ts` 定义 store action。它采用 class-based action 写法：

```ts
export class ResourceManagerStoreActionImpl {
  readonly #get: () => Store;
  readonly #set: Setter;
}
```

然后通过：

```ts
flattenActions<Action>([createResourceManagerStoreSlice(...params)])
```

把 class 实例上的方法摊平成 zustand store action。

主要 action 包括：

- `setCategory`
- `setCurrentViewItemId`
- `setLibraryId`
- `setMode`
- `setPendingRenameItemId`
- `setSearchQuery`
- `setSelectedFileIds`
- `setSelectAllState`
- `setSorter`
- `setSortType`
- `setViewMode`
- `clearSelectAllState`
- `handleBackToList`
- `selectAllLoadedResources`
- `selectAllResources`
- `resolveSelectedResourceIds`
- `onActionClick`

其中 `onActionClick` 是最重要的业务入口，处理多选批量操作。

`MultiSelectActionType` 支持：

```ts
'addToKnowledgeBase'
'moveToOtherKnowledgeBase'
'batchChunking'
'delete'
'deleteLibrary'
'removeFromKnowledgeBase'
```

不过从当前实现看，`addToKnowledgeBase` 和 `moveToOtherKnowledgeBase` 暂时只是 `return`，具体弹窗或后续流程应该在调用侧处理，或者尚未实现到这个 action 内。根据当前片段推断，它们被保留为统一 action 类型的一部分。

`selectors.ts` 负责派生数据和 UI 判断。

它包含：

- `sortFileList`
- `getSortedFileList`
- `getCurrentFile`
- `isFilePreviewMode`
- `isExplorerItemSelected`
- `getExplorerSelectAllUiState`
- `getExplorerSelectedCount`
- `selectors`

其中 `sortFileList` 是纯函数，可以对任意 `FileListItem[]` 按名称、创建时间、大小排序。`getSortedFileList` 会直接读取 `useFileStore.getState().fileList`，但代码已标记：

```ts
@deprecated Use sortFileList with data from SWR hook instead
```

这说明新的使用方式倾向于：调用方通过 SWR 或其他数据 hook 拿到数据后，再用 `sortFileList` 做本地排序，而不是让 selector 主动读取全局 `FileStore`。

## 上下游关系

上游调用方主要集中在 Resource 路由和 Resource features 下。根据检索结果，典型调用点包括：

- `src/routes/(main)/resource/(home)/index.tsx`
- `src/routes/(main)/resource/(home)/_layout/Header/CategoryMenu.tsx`
- `src/routes/(main)/resource/library/index.tsx`
- `src/routes/(main)/resource/library/_layout/Header/LibraryHead.tsx`
- `src/routes/(main)/resource/features/hooks/useInitFileCheck.ts`
- `src/routes/(main)/resource/features/hooks/useResourceManagerUrlSync.ts`
- `src/routes/(main)/resource/features/DndContextWrapper.tsx`
- `src/routes/(main)/resource/(home)/_layout/Body/LibraryList/Item/index.tsx`

这些调用方大致分为几类：

- 页面入口初始化状态，例如进入资源首页时设置 `category`、`libraryId`。
- Header 或菜单切换模式，例如 `CategoryMenu` 使用 `category` 和 `setMode`。
- 知识库页面同步当前 `libraryId`。
- URL 同步 hook 使用 `sorter`、`sortType`、`setSorter`、`setSortType`。
- 文件检查 hook 根据文件 id 设置 `mode` 和 `currentViewItemId`。
- 拖拽或批量选择 UI 读取 `selectedFileIds`，并调用 `setSelectedFileIds`。

下游依赖则包括：

- `@/store/file`
- `@/store/library`
- `@/services/resource`
- `@/utils/isChunkingUnsupported`
- `@/types/files`
- `@/features/ResourceManager`

`@/store/file` 是最关键的下游。当前 store 会从它那里读取或调用：

- `useFetchFolderBreadcrumb`
- `fileList`
- `queryParams`
- `resourceMap`
- `deleteResources`
- `parseFilesToChunks`
- `clearCurrentQueryResources`

`@/store/library` 提供知识库操作：

- `removeFilesFromKnowledgeBase`
- `removeKnowledgeBase`

`@/services/resource` 负责服务端级别的资源批量处理：

- `deleteResourcesByQuery`
- `resolveSelectionIds`

也就是说，`ResourceManagerStore` 自己不保存完整资源数据，也不直接实现 API 请求细节。它只根据当前 UI 状态决定“应该对哪些资源执行什么操作”，然后把实际操作委托给 file store、library store 或 resource service。

## 运行/调用流程

创建 store 的流程是：

1. `index.ts` 调用 `store()`。
2. `store()` 合并 `initialState`、可选 `publicState` 和 action。
3. `createWithEqualityFn` 创建 `useResourceManagerStore`。
4. 组件通过 `useResourceManagerStore((s) => ...)` 订阅状态或 action。

普通状态更新流程很直接。例如切换分类：

1. UI 调用 `setCategory(category)`。
2. action 内部执行 `this.#set({ category })`。
3. 订阅 `category` 的组件刷新。

进入详情或预览流程大致是：

1. 某个 hook 或 UI 判断当前需要查看文件。
2. 调用 `setCurrentViewItemId(id)`。
3. 调用 `setMode('editor')` 或其他 `ResourceManagerMode`。
4. selector `isFilePreviewMode` 根据 `mode === 'editor' && !!currentViewItemId` 判断是否处于文件预览/编辑视图。
5. `getCurrentFile` 会通过 `fileManagerSelectors.getFileById(currentViewItemId)(useFileStore.getState())` 从 FileStore 找到实际文件数据。

批量删除流程更复杂。

当用户点击批量删除时，调用：

```ts
onActionClick('delete')
```

内部逻辑分两种情况：

第一种是“选择全部查询结果”，且本地没有排除项：

```ts
selectAllState === 'all' &&
selectedFileIds.length === 0 &&
fileStore.queryParams
```

此时它不会逐个删除本地已加载 id，而是：

1. 动态 import `@/services/resource`。
2. 调用 `resourceService.deleteResourcesByQuery(fileStore.queryParams as any)`。
3. 调用 `fileStore.clearCurrentQueryResources()` 清掉当前查询资源。
4. 重置选择状态为 `none` 和 `[]`。

第二种情况是普通删除或带排除项的全选删除：

1. 如果 `selectAllState === 'all'`，调用 `resolveSelectedResourceIds()`。
2. 否则直接使用 `selectedFileIds`。
3. 调用 `fileStore.deleteResources(resourceIds)`。
4. 重置选择状态。

`resolveSelectedResourceIds` 的逻辑也值得单独理解：

1. 如果不是 `selectAllState === 'all'`，直接返回 `selectedFileIds`。
2. 如果是全选，则读取 `useFileStore.getState().queryParams`。
3. 调用 `resourceService.resolveSelectionIds(queryParams as any)` 获取查询命中的全部资源 id。
4. 过滤掉 `selectedFileIds` 中记录的排除项。
5. 返回真正要操作的 id 列表。

批量分块流程：

1. 调用 `onActionClick('batchChunking')`。
2. 通过 `resolveSelectedResourceIds()` 得到目标资源 id。
3. 根据 `fileStore.resourceMap` 和 `isChunkingUnsupported(resource.fileType)` 过滤不支持分块的文件。
4. 对于服务端解析出的但本地 `resourceMap` 没有的资源，如果当前是全选模式，会保留这些 id，让服务端再处理不支持类型过滤。
5. 调用 `fileStore.parseFilesToChunks(chunkableFileIds, { skipExist: true })`。
6. 清空选择状态。

从知识库移除流程：

1. 调用 `onActionClick('removeFromKnowledgeBase')`。
2. 调用 `resolveSelectedResourceIds()`。
3. 如果没有 `libraryId`，直接返回。
4. 调用 `kbStore.removeFilesFromKnowledgeBase(libraryId, resourceIds)`。
5. 清空选择状态。

删除知识库流程：

1. 调用 `onActionClick('deleteLibrary')`。
2. 如果没有 `libraryId`，直接返回。
3. 调用 `kbStore.removeKnowledgeBase(libraryId)`。
4. 在浏览器环境下跳转到 `/knowledge`。

这里使用了动态 import，例如：

```ts
const { useFileStore } = await import('@/store/file');
const { useKnowledgeBaseStore } = await import('@/store/library');
```

根据当前片段推断，这样做可以降低初始 bundle 依赖，也避免某些 store 之间的静态循环依赖风险。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先读 `initialState.ts`

   先理解这个 store 到底保存哪些状态。重点看 `State`、`ViewMode`、`SelectAllState` 和 `initialState`。

2. 再读 `index.ts`

   看这个目录对外暴露了什么。你会看到真正给组件使用的是 `useResourceManagerStore`，以及一个面包屑数据 hook `useResourceManagerFetchFolderBreadcrumb`。

3. 再读 `action.ts` 的简单 setter

   先不要急着看 `onActionClick`。先理解 `setCategory`、`setMode`、`setLibraryId`、`setSelectedFileIds` 这些方法如何更新状态。

4. 然后重点读 `selectAllState` 相关 action

   包括：

   - `clearSelectAllState`
   - `selectAllLoadedResources`
   - `selectAllResources`
   - `setSelectedFileIds`
   - `resolveSelectedResourceIds`

   这里是理解批量操作的关键。

5. 最后读 `onActionClick`

   按 action 类型逐个看：

   - `delete`
   - `removeFromKnowledgeBase`
   - `batchChunking`
   - `deleteLibrary`

   重点关注它如何从当前 store 状态，连接到 `useFileStore`、`useKnowledgeBaseStore` 和 `resourceService`。

6. 再读 `selectors.ts`

   `selectors.ts` 比较适合最后读，因为它是对状态和外部 FileStore 的派生。重点看：

   - `sortFileList`
   - `isExplorerItemSelected`
   - `getExplorerSelectAllUiState`
   - `getExplorerSelectedCount`

7. 有余力再看测试

   `action.test.ts` 和 `selectors.test.ts` 应该覆盖了批量操作和 selector 的边界行为。对于理解“全选时 `selectedFileIds` 是排除项”这种不直观逻辑，测试通常比 UI 代码更清楚。

## 常见误区

第一个误区：把这个 store 当成资源数据源。

它不是资源数据源。真实资源列表、文件详情、查询参数、分块、删除等能力主要在 `@/store/file` 和 `@/services/resource`。这个 store 只是 Resource 页面局部 UI 状态和操作编排层。

第二个误区：误解 `selectedFileIds`。

在普通选择模式下，`selectedFileIds` 表示“被选中的文件 id”。但在 `selectAllState === 'all'` 时，它表示“从全选中排除的文件 id”。这是最容易读错的地方。

第三个误区：以为 `selectAllState === 'all'` 只代表当前已加载列表全选。

不是。`all` 表示当前查询条件下的全部资源，可能包含尚未加载到前端的资源。因此需要 `resourceService.resolveSelectionIds(queryParams)` 去服务端解析完整 id 集合。

第四个误区：看到 `getSortedFileList` 就继续使用它。

这个 selector 已经标记 `@deprecated`。更推荐的模式是调用方自己拿到 SWR 数据，然后使用纯函数 `sortFileList(fileList, sorter, sortType)` 排序。

第五个误区：忽略 `queryParams` 对批量操作的影响。

批量删除和全选解析依赖 `useFileStore.getState().queryParams`。如果没有查询参数，`resolveSelectedResourceIds` 会退回 `selectedFileIds`。因此排查“全选批量操作不符合预期”时，需要同时检查 ResourceManagerStore 和 FileStore 的查询状态。

第六个误区：认为所有 `MultiSelectActionType` 都已经在这里完整实现。

当前 `addToKnowledgeBase` 和 `moveToOtherKnowledgeBase` 在 `onActionClick` 中直接 `return`。根据当前片段推断，这两个动作可能由其他 UI 流程处理，或者只是提前占位。阅读调用方时不要假设它们会在这个 action 内完成实际业务。

第七个误区：忽略动态 import。

`action.ts` 里多处使用 `await import(...)`，说明这些依赖不是在模块加载时就静态绑定的。读调用链时要把它们看作“执行到该 action 时才加载并调用”的下游依赖。
