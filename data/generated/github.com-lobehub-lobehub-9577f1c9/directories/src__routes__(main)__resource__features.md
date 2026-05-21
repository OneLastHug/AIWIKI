# 目录：src/routes/(main)/resource/features

## 它负责什么

`src/routes/(main)/resource/features` 是 `/resource` 这一组 SPA 路由的“页面级功能胶水层”。它不直接等同于全局的 `src/features/ResourceManager`，而是围绕资源页运行时需要的本地状态、URL 参数、文件详情弹层、拖拽上下文和知识库路径解析做适配。

从当前片段看，它主要承担四类职责：

1. 管理资源页局部 UI 状态  
   通过 `features/store` 维护当前视图模式、选中文件、全选状态、排序方式、当前知识库、当前查看项、搜索词、待重命名项等。

2. 同步 URL 与页面状态  
   通过 `hooks/useFileQueryParam.ts`、`modal/useFilesQueryParam.ts`、`hooks/useResourceManagerUrlSync.ts` 读取或写入 `?file=`、兼容旧的 `?files=`，以及 `sorter`、`sortType` 等查询参数。

3. 支撑资源管理器的交互能力  
   `DndContextWrapper.tsx` 提供自定义 HTML5 drag-and-drop 上下文，负责文件/文件夹拖拽、拖拽浮层、移动到目标文件夹、拖拽期间的全局 cursor 状态等。

4. 打开文件详情、预览或全屏查看  
   `FileDetail.tsx` 与 `modal/` 下的文件负责根据当前文件 ID 展示详情、预览、全屏 modal 页面等。由于当前只读取到部分文件片段，modal 内部具体 UI 细节根据文件命名和调用关系推断为文件详情/预览视图的路由级包装。

这个目录偏“route-local feature”，它和真正复用型业务组件之间的关系是：这里负责路由、URL、状态、拖拽和弹层控制；底层资源列表、文件数据、知识库数据、文件操作则更多来自 `@/features/ResourceManager`、`@/store/file`、`@/store/library`、`@/store/tree`、`@/services/resource` 等外部模块。

## 关键组成

### `DndContextWrapper.tsx`

这是资源页拖拽能力的核心包装器。

它导出：

- `DndContextWrapper`
- `useDragActive`
- `useCurrentDrag`
- `useSetCurrentDrag`
- `getTransparentDragImage`

内部定义了几个 React context：

- `DragActiveContext`：标记当前是否正在拖拽，用于让 drop zone 在拖拽时才激活，减少大列表下的性能消耗。
- `CurrentDragContext`：保存当前拖拽对象。
- `SetCurrentDragContext`：暴露更新当前拖拽对象的方法。

拖拽对象结构大致是：

```ts
interface DragState {
  data: any;
  id: string;
  parentKey: string;
  type: 'file' | 'folder';
}
```

核心逻辑是监听 document 级别事件：

- `dragstart`：初始化拖拽浮层位置。
- `drag`：直接操作 DOM 更新浮层位置，避免 React 高频重渲染。
- `drop`：从事件目标向上查找 `data-drop-target-id`、`data-is-folder`、`data-root-drop`，判断是否是合法投放目标。
- `dragover`：阻止默认行为，使 drop 生效。
- `dragend`：清空拖拽状态。

移动逻辑依赖 `useTreeStore.getState()`：

- 如果拖拽的是当前选中集合中的一个文件，则批量调用 `moveItems(itemsToMove, fromParent, toParent)`。
- 否则调用 `moveItem(drag.id, fromParent, toParent)`。
- 移动失败时通过 `antd` 的 `message.error` 提示 `FileManager.actions.moveError`。
- 移动成功后提示 `FileManager.actions.moveSuccess`。
- 如果是批量拖拽，移动后清空 `selectedFileIds`。

它还创建一个透明 `1x1` 图片作为 `setDragImage` 的候选，用于隐藏浏览器默认拖拽图标。拖拽浮层通过 `createPortal` 渲染到 `useAppElement()` 返回的应用容器里。

### `store/action.ts`

这是本目录局部 Zustand store 的主要 action 实现。

它定义了：

- `MultiSelectActionType`
- `FolderCrumb`
- `Store = Action & State`
- `ResourceManagerStoreActionImpl`
- `createResourceManagerStoreSlice`
- `store`

`MultiSelectActionType` 支持的批量操作包括：

```ts
'addToKnowledgeBase'
'moveToOtherKnowledgeBase'
'batchChunking'
'delete'
'deleteLibrary'
'removeFromKnowledgeBase'
```

`ResourceManagerStoreActionImpl` 采用 class action 模式，内部持有私有的 `#get` 和 `#set`，再通过 `flattenActions` 展平为 Zustand action。这个写法和 LobeHub 近期 store 迁移风格一致，避免把大量 action 直接堆在对象字面量里。

关键 action：

- `clearSelectAllState()`  
  清空全选状态和已选文件 ID。

- `handleBackToList()`  
  把当前模式恢复为 `explorer`，并清空 `currentViewItemId`。

- `onActionClick(type)`  
  批量操作入口。它按需动态 import：
  - `@/store/file`
  - `@/store/library`
  - `@/utils/isChunkingUnsupported`
  - `@/services/resource`

- `resolveSelectedResourceIds()`  
  当 `selectAllState === 'all'` 时，不只返回当前页面已加载 ID，而是通过 `resourceService.resolveSelectionIds(queryParams)` 根据当前查询条件解析服务端完整选区。

- `selectAllLoadedResources(selectedFileIds)`  
  只选择当前已加载资源，状态设为 `loaded`。

- `selectAllResources()`  
  进入“全量选择”状态，`selectedFileIds` 清空。这里的语义是：选中的不是一个本地 ID 数组，而是“当前查询条件下的全部资源”。

- `setCategory()`、`setSorter()`、`setSortType()`、`setViewMode()`、`setMode()` 等  
  普通局部状态 setter。

值得注意的是 `delete` 的分支：

- 如果 `selectAllState === 'all'` 且本地没有显式选中 ID，并且 `fileStore.queryParams` 存在，则直接调用 `resourceService.deleteResourcesByQuery(fileStore.queryParams)`。
- 否则先解析 `resourceIds`，再调用 `fileStore.deleteResources(resourceIds)`。
- 删除完成后都会清空选择状态。

这说明该 store 不只是 UI 状态，还承接了“资源页批量操作”的编排职责。

### `store/initialState.ts`

当前片段没有完整展开，但从 `action.ts` 的使用可以确认它至少定义：

- `State`
- `SelectAllState`
- `ViewMode`
- `initialState`

根据 action 字段推断，`initialState` 至少包含：

- `mode`
- `category`
- `libraryId`
- `currentViewItemId`
- `pendingRenameItemId`
- `searchQuery`
- `selectAllState`
- `selectedFileIds`
- `sorter`
- `sortType`
- `viewMode`

其中 `mode` 使用的是 `ResourceManagerMode`，来自 `@/features/ResourceManager`；`category` 使用 `FilesTabs`；`sortType` 使用 `SortType`。

### `store/index.ts`

当前只读到开头片段：

```ts
'use client';

import type { SWRResponse } from 'swr';
import { subscribeWithSelector } from 'zustand/middleware';
import { shallow } from 'zustand/shallow';
import { createWithEqualityFn } from 'zustand/traditional';

import { useFileStore } from '@/store/file';

import type { FolderCrumb, Store } from './action';
import { store } from './action';

export type { State } from './initialState';
```

根据当前片段推断，它负责创建并导出 `useResourceManagerStore`，并可能包装了文件夹 breadcrumb 的 SWR hook，因为 `hooks/useCurrentFolderId.ts` 从这里导入了：

```ts
useResourceManagerFetchFolderBreadcrumb
```

结合导入的 `SWRResponse`、`useFileStore`、`FolderCrumb` 可以推断，这个入口文件一方面创建局部 store hook，另一方面桥接 `fileStore` 中的文件夹路径/面包屑获取能力。

### `hooks/useFolderPath.ts`

这个 hook 解析当前资源页路由路径。

它使用：

- `useParams<{ id: string; slug?: string }>()`
- `useLocation()`

返回：

```ts
{
  currentFolderSlug,
  isInKnowledgeBase,
  knowledgeBaseId,
}
```

判断规则：

- `knowledgeBaseId = params.id || null`
- `isInKnowledgeBase = location.pathname.includes('/resource/library/')`
- `currentFolderSlug = params.slug || null`

注释中给出的示例：

- `/resource/library/kb_123`  
  表示进入某个知识库根目录。
- `/resource/library/kb_123/folder-slug-1`  
  表示进入该知识库下某个文件夹。
- `/knowledge`  
  表示不在知识库上下文中。

这里要注意注释里提到 `/knowledge`，但目标路径实际是 `/resource` 组；这可能是历史命名或迁移过程中留下的描述。

### `hooks/useCurrentFolderId.ts`

这个 hook 把 URL 中的 folder slug 转换成真实 folder id。

流程是：

1. 调用 `useFolderPath()` 得到 `currentFolderSlug`。
2. 调用 `useResourceManagerFetchFolderBreadcrumb(currentFolderSlug)` 获取面包屑。
3. 返回最后一个 crumb 的 `id`，没有则返回 `null`。

也就是说，URL 里保存的是 slug，但业务操作移动、查询等更可能需要真实 ID。

### `hooks/useFileQueryParam.ts`

这个文件处理文件详情 modal 的 URL 参数。

核心常量：

```ts
export const FILE_MODAL_QUERY_KEY = 'file';
```

导出：

- `useFileModalId()`
- `useSetFileModalId()`
- `createSetFileModalId(setSearchParams)`

兼容规则：

- 新参数：`?file=[id]`
- 旧参数：`?files=[id]`

读取时优先 `file`，再 fallback 到 `files`：

```ts
searchParams.get('file') ?? searchParams.get('files') ?? undefined
```

写入时会同时删除 `file` 和 `files`，再按新格式写入 `file`。这是一种向后兼容但向新 URL 语义收敛的做法。

### `hooks/useInitFileCheck.ts`

这个 hook 处理初始打开文件的场景，例如：

```txt
/resource?file=xxxxxx
```

流程：

1. 从 URL 读取 `file`。
2. 调用 `useFileStore((s) => s.useFetchKnowledgeItem)` 拉取文件数据。
3. 通过 `documentSelectors.getDocumentById(fileId)` 从本地文档 map 取数据。
4. 如果存在 `fileId`，设置：
   - `currentViewItemId = fileId`
   - 根据文件类型决定 `mode`
5. 如果没有 `fileId`，恢复：
   - `mode = 'explorer'`
   - `currentViewItemId = undefined`

文件类型判断逻辑：

- PDF：
  - `fileType` 是 `pdf`
  - `fileType` 是 `application/pdf`
  - 文件名或 source 以 `.pdf` 结尾
- Page/document：
  - 不是 PDF
  - `sourceType === 'document'`
  - `fileType === 'custom/document'`
  - 或本地存在 `documentData`

模式选择：

- PDF：`editor`
- Page/document：`page`
- 其他：`editor`

这说明资源页支持至少三种核心模式：

- `explorer`：资源列表/文件管理器
- `editor`：文件编辑或预览编辑模式
- `page`：文档页面模式

### `hooks/useKnowledgeItem.ts`

这个文件只有一个轻量包装：

```ts
export const useKnowledgeBaseItem = (id: string) => {
  const useFetchKnowledgeBaseItem = useKnowledgeBaseStore((s) => s.useFetchKnowledgeBaseItem);

  return useFetchKnowledgeBaseItem(id);
};
```

它把 `@/store/library` 的 `useFetchKnowledgeBaseItem` 包装成资源页本地 hook，便于页面内使用。命名上文件叫 `useKnowledgeItem.ts`，导出叫 `useKnowledgeBaseItem`，阅读时不要混淆。

### `hooks/useResourceManagerUrlSync.ts`

这个 hook 把资源管理器排序状态和 URL 查询参数互相同步。

它从本地 store 读取：

- `sorter`
- `sortType`
- `setSorter`
- `setSortType`

初始化时执行 URL 到 store：

- `sorter` 默认 `createdAt`
- `sortType` 默认 `SortType.Desc`

后续执行 store 到 URL：

- 如果 `sorter === 'createdAt'`，从 URL 删除 `sorter`。
- 否则写入 `sorter`。
- 如果 `sortType === SortType.Desc`，从 URL 删除 `sortType`。
- 否则写入 `sortType`。

这种设计让默认状态的 URL 更干净，同时非默认排序可以被收藏和分享。

### `modal/`

`modal` 子目录包含：

- `FileDetail.tsx`
- `FilePreview.tsx`
- `FullscreenModal.tsx`
- `ModalPageClient.tsx`
- `useFilesQueryParam.ts`

当前片段只确认了 `useFileQueryParam.ts` 中新旧参数兼容逻辑，`modal/useFilesQueryParam.ts` 很可能是 modal 内部同类逻辑或旧入口。根据文件命名推断：

- `FileDetail.tsx`：文件详情弹窗内容。
- `FilePreview.tsx`：文件预览内容。
- `FullscreenModal.tsx`：全屏弹层容器。
- `ModalPageClient.tsx`：客户端 modal 页面包装，可能用于 route modal 或 parallel/modal page 场景。

证据不足处：modal 组件内部具体 UI 结构、依赖组件和条件分支没有完整读取到，因此这里只能根据文件名、URL 参数 hook 和资源页职责推断它们的定位。

## 上下游关系

### 上游：路由页面与布局

邻近目录中存在：

- `src/routes/(main)/resource/(home)/index.tsx`
- `src/routes/(main)/resource/library/index.tsx`
- `src/routes/(main)/resource/_layout/index.tsx`
- `src/routes/(main)/resource/_layout/RegisterHotkeys.tsx`

这些文件属于 `/resource` 路由树的页面和布局。根据目录结构推断，它们会引入本目录的 store、hooks、`DndContextWrapper` 或文件详情组件，把 route 参数、URL 参数和资源管理器 UI 串起来。

### 中游：本目录的 route-local feature

本目录处在“页面路由”和“全局业务模块”之间，主要做适配：

- 路由参数转业务 ID：`useFolderPath`、`useCurrentFolderId`
- URL query 转 UI 状态：`useFileQueryParam`、`useInitFileCheck`、`useResourceManagerUrlSync`
- 局部交互状态：`features/store`
- 拖拽交互：`DndContextWrapper`
- 文件详情/预览 modal：`FileDetail.tsx`、`modal/*`

### 下游：全局 store、service 和 feature

它依赖多个仓库级模块：

- `@/features/ResourceManager`  
  提供资源管理器相关类型，例如 `ResourceManagerMode`。根据路径名推断也提供主要 UI 组件。

- `@/store/file`  
  负责文件资源数据、查询参数、删除资源、解析文件 chunk、获取 knowledge item 等。

- `@/store/library`  
  负责知识库数据和操作，如 `removeFilesFromKnowledgeBase`、`removeKnowledgeBase`、`useFetchKnowledgeBaseItem`。

- `@/store/tree`  
  负责树结构移动操作，如 `moveItem`、`moveItems`。

- `@/services/resource`  
  提供服务端资源操作：
  - `deleteResourcesByQuery`
  - `resolveSelectionIds`

- `@/utils/isChunkingUnsupported`  
  判断文件类型是否不支持 chunking。

- `@/types/files`  
  提供 `FilesTabs`、`SortType` 等资源列表类型。

## 运行/调用流程

### 打开资源页

1. 路由进入 `/resource` 或 `/resource/library/:id/:slug?`。
2. 页面或布局初始化 `useResourceManagerStore`。
3. `useFolderPath()` 从 `react-router-dom` 中读取 `id`、`slug` 和当前 pathname。
4. 如果需要真实文件夹 ID，`useCurrentFolderId()` 通过 folder slug 获取 breadcrumb，并取最后一个 crumb 的 `id`。
5. `useResourceManagerUrlSync()` 在首次 mount 时把 `sorter`、`sortType` 从 URL 写入 store。
6. 之后排序状态变化时，再把非默认排序写回 URL。

### 通过 URL 打开某个文件

1. 用户访问类似 `/resource?file=xxx`。
2. `useInitFileCheck()` 读取 `file`。
3. 设置 `currentViewItemId = xxx`。
4. 从 `useFileStore` 获取文件信息或本地 document 数据。
5. 判断文件类型：
   - PDF 进入 `editor`
   - document/page 进入 `page`
   - 其他进入 `editor`
6. 如果 URL 中没有 `file`，恢复为 `explorer` 列表模式。

### 打开/关闭文件 modal

1. 组件调用 `useFileModalId()` 读取当前 modal 文件 ID。
2. 需要打开时调用 `useSetFileModalId()(id)`。
3. URL 写成 `?file=id`。
4. 关闭时调用 `useSetFileModalId()(undefined)`，删除 `file` 和旧的 `files` 参数。
5. 旧链接 `?files=id` 仍能被识别，但下一次写入会迁移成 `?file=id`。

### 拖拽移动文件或文件夹

1. 页面外层包裹 `DndContextWrapper`。
2. 可拖拽项在 drag start 时通过 `useSetCurrentDrag()` 写入当前拖拽对象。
3. `DndContextWrapper` 显示跟随鼠标的拖拽浮层。
4. 用户 drop 时，wrapper 向上查找目标 DOM 上的 dataset：
   - `data-drop-target-id`
   - `data-is-folder`
   - `data-root-drop`
5. 如果目标不是文件夹或根投放区，则取消。
6. 如果把项目拖到自己内部或原父级，也取消。
7. 判断是否是“拖拽当前选中集合”：
   - 是：调用 `moveItems`
   - 否：调用 `moveItem`
8. 成功后提示移动成功；失败后提示移动失败。
9. 批量移动后清空选中状态。

### 批量操作

1. 用户在资源管理器中选择文件。
2. `selectedFileIds` 和 `selectAllState` 写入本地 store。
3. 点击批量操作按钮后调用 `onActionClick(type)`。
4. 如果是普通选中，直接使用 `selectedFileIds`。
5. 如果是全量选择，调用 `resolveSelectedResourceIds()`，由服务端按当前 `queryParams` 解析完整 ID 集合。
6. 根据操作类型执行：
   - `delete`：删除资源或按 query 删除资源。
   - `removeFromKnowledgeBase`：从当前知识库移除资源。
   - `batchChunking`：过滤不支持 chunking 的文件，再调用 `parseFilesToChunks`。
   - `deleteLibrary`：删除知识库，并跳转到 `/knowledge`。
   - `addToKnowledgeBase`、`moveToOtherKnowledgeBase`：当前片段中是空实现，可能由其他 UI 流程处理或尚未完成。

## 小白阅读顺序

1. 先看 `hooks/useFolderPath.ts`  
   这是理解 `/resource/library/:id/:slug?` 路由语义的入口。先弄清楚 `knowledgeBaseId`、`currentFolderSlug`、`isInKnowledgeBase` 从哪里来。

2. 再看 `store/initialState.ts` 和 `store/action.ts`  
   重点看有哪些状态字段，以及 `onActionClick` 如何把批量操作转发给 `fileStore`、`libraryStore` 和 `resourceService`。

3. 接着看 `hooks/useResourceManagerUrlSync.ts`  
   理解排序状态为什么既存在 store 里，又会出现在 URL 上。

4. 然后看 `hooks/useFileQueryParam.ts` 和 `hooks/useInitFileCheck.ts`  
   这两者解释了 `?file=` 的作用：既可以控制 modal，也可以让资源页初始化时直接进入某个文件的查看/编辑模式。

5. 再看 `DndContextWrapper.tsx`  
   这部分代码较长，但主线很清楚：context 保存拖拽状态，document 事件处理拖拽生命周期，drop 时调用 `useTreeStore` 移动文件。

6. 最后看 `modal/` 下文件  
   在理解 URL 参数和当前文件 ID 后，再看文件详情、预览和全屏弹层会更容易。否则容易把 modal 的显示逻辑和资源页模式切换混在一起。

## 常见误区

1. 把这里的 `features` 当成全局 `src/features`  
   这个目录虽然叫 `features`，但它位于 `src/routes/(main)/resource/` 下，更像资源路由的本地功能层。通用资源管理器能力仍然在 `@/features/ResourceManager`、`@/store/file` 等模块中。

2. 以为 `selectedFileIds` 总是完整选区  
   当 `selectAllState === 'all'` 时，`selectedFileIds` 可能是空的。此时真正的完整选区需要通过 `resourceService.resolveSelectionIds(queryParams)` 按查询条件从服务端解析。

3. 忽略 `?file=` 和旧 `?files=` 的兼容  
   读取时两个参数都支持，写入时统一写 `file`。如果只搜 `files`，会误判新逻辑没有生效。

4. 把 folder slug 当成 folder id  
   `useFolderPath()` 拿到的是 `currentFolderSlug`。需要真实 ID 时，要通过 `useCurrentFolderId()` 获取 breadcrumb 后取最后一个 `id`。

5. 认为拖拽基于 `dnd-kit`  
   当前 `DndContextWrapper.tsx` 明确使用原生 HTML5 drag-and-drop，并且注释说明这是为了大规模虚拟列表下的性能。拖拽浮层位置也是直接改 DOM style，而不是放进 React state 高频更新。

6. 忽略 drop target 的 DOM dataset 约定  
   拖拽能否投放不是只看 React 组件层级，而是看 DOM 向上查找时能否找到 `data-drop-target-id`、`data-is-folder` 或 `data-root-drop`。新增文件夹节点或根投放区时，必须保证这些 dataset 正确。

7. 误以为 `deleteLibrary` 只是清空当前列表  
   `deleteLibrary` 会调用 `kbStore.removeKnowledgeBase(libraryId)`，然后在浏览器环境下跳转到 `/knowledge`。这是知识库级删除，不是普通文件删除。

8. 认为 `batchChunking` 会对所有选中文件执行  
   它会先用 `isChunkingUnsupported(resource.fileType)` 过滤本地已知且不支持切片的文件。对于服务端解析出来但本地 map 没有的资源，在全选模式下会保留，让服务端继续处理过滤。

9. 忽略默认排序不会写入 URL  
   `sorter === 'createdAt'` 和 `sortType === SortType.Desc` 是默认值，会从 URL 中删除。看到 URL 没有排序参数，不代表没有排序状态，而是处于默认排序。

10. 把 `explorer`、`editor`、`page` 混成 modal 状态  
   `mode` 是资源管理器主视图状态；`?file=`/modal 是 URL 和详情展示状态。它们有关联，但不是同一个概念。`useInitFileCheck()` 会根据 `file` 和文件类型切换 `mode`，而 modal 相关 hook 主要控制 URL 中当前文件 ID。
