# 目录：src/routes/(main)/resource

## 它负责什么

`src/routes/(main)/resource` 是桌面主应用里的资源管理路由入口，覆盖两类页面：

- `/resource`：全局资源首页，按文件类型分类浏览全部资源。
- `/resource/library/:id`：某个知识库的资源列表。
- `/resource/library/:id/:slug`：知识库内某个文件夹路径下的资源列表。

这个目录本质上是“资源管理页面的路由壳 + 一部分尚未迁移出去的业务状态和辅助逻辑”。按照当前仓库的 `spa-routes` 约定，`src/routes/` 理想上只放薄路由文件，复杂 UI 和业务逻辑应放到 `src/features/`。但该目录仍然保留了 `features/`、`features/store/`、`features/hooks/`、`features/modal/` 等实现，属于渐进迁移中的旧结构和新结构混合状态。

从功能上看，它不直接完成所有资源展示细节，而是把主展示交给 `@/features/ResourceManager`，自身负责：

- 注册 `/resource` 路由布局。
- 根据 URL 参数同步资源管理状态。
- 区分“全局资源列表”和“知识库资源列表”。
- 管理 `libraryId`、文件分类、当前打开文件、视图模式、批量选择等本页状态。
- 提供资源侧边栏、知识库侧边栏、热键注册、拖拽上下文、文件详情弹窗等页面级辅助能力。

## 关键组成

### 路由入口

`_layout/index.tsx` 是 `/resource` 的根布局。它渲染 `<Outlet />`，同时挂载 `RegisterHotkeys`：

```tsx
<Outlet />
<RegisterHotkeys />
```

这意味着 `/resource` 下的所有子路由都会处在这个根布局之下，文件相关快捷键也会在该路由分支注册。

`(home)/index.tsx` 是 `/resource` 首页。它读取 URL query 中的 `category`，同步到 `useResourceManagerStore` 的 `category`，并在确认当前是首页路由时清空 `libraryId`。最后渲染 `ResourceManager`。

`library/index.tsx` 是 `/resource/library/:id` 的知识库页面。它从 `useParams` 读取知识库 ID，调用 `useKnowledgeBaseItem` 加载知识库数据，如果加载完成后没有数据则显示 `NotFound`，否则渲染 `ResourceManager`。

`library/[slug]/index.tsx` 直接：

```ts
export { default } from '../index';
```

也就是说文件夹 slug 页面复用知识库首页同一个页面组件。`slug` 的差异不是由页面组件本身处理，而是由下游 hooks，例如 `useFolderPath` 和 `useCurrentFolderId`，从 URL params 里解析。

### 首页布局

`(home)/_layout/index.tsx` 组合首页侧边栏和主内容区域：

- `Sidebar`：放在 `NavPanelPortal navKey="resource"` 内。
- `Outlet`：放在 `Flexbox` 主容器里。

首页侧边栏由 `Header`、`CategoryMenu` 和 `Body` 构成。

`CategoryMenu` 提供文件类型筛选入口：

- `FilesTabs.All`
- `FilesTabs.Documents`
- `FilesTabs.Images`
- `FilesTabs.Audios`
- `FilesTabs.Videos`

点击分类时不会让浏览器默认跳转，而是：

1. `preventDefault()`。
2. 调用 `setMode('explorer')`。
3. `navigate(item.url, { replace: true })`。

所以分类切换会强制回到资源浏览模式，并用 URL query 表达当前分类。

`Body/index.tsx` 中使用 `useCreateNewModal` 创建知识库。创建成功后跳转到：

```ts
/resource/library/${id}
```

### 知识库布局

`library/_layout/index.tsx` 组合知识库侧边栏、主内容和热键注册：

- `Sidebar`：放在 `NavPanelPortal navKey="resourceLibrary"` 内。
- 主区域：包裹子路由 `<Outlet />`。
- `RegisterHotkeys`：再次注册文件热键。

知识库侧边栏使用 `LibraryHierarchy`，这是来自 `@/features/ResourceManager/components/LibraryHierarchy` 的知识库层级树。Header 使用 `SideBarHeaderLayout`，支持 `backTo="/resource"`，并通过 `LibraryHead` 展示当前知识库标题/状态。

这里需要注意：根 `_layout` 已经注册了一次 `useRegisterFilesHotkeys()`，`library/_layout` 里又注册了一次。根据当前片段推断，`useRegisterFilesHotkeys` 需要是幂等的，或者内部能处理重复注册；否则在知识库页可能存在重复绑定风险。证据是两个 `RegisterHotkeys.tsx` 文件内容基本相同，且路由树上 library layout 位于 resource root layout 内。

### 页面级 store

主状态在 `features/store` 下：

- `initialState.ts`
- `action.ts`
- `selectors.ts`
- `index.ts`

`initialState` 定义资源管理页状态：

- `category`：当前文件分类。
- `libraryId`：当前知识库 ID。
- `mode`：`ResourceManagerMode`，可为 `'explorer' | 'editor' | 'page'`。
- `currentViewItemId`：当前打开的文件或文档 ID。
- `viewMode`：`'list' | 'masonry'`。
- `searchQuery`：搜索关键字。
- `sorter` / `sortType`：排序字段和方向。
- `selectedFileIds` / `selectAllState`：批量选择状态。
- `pendingRenameItemId`：当前正在重命名的资源 ID。

`action.ts` 使用 class action 写法，核心动作包括：

- `setCategory`
- `setLibraryId`
- `setMode`
- `setCurrentViewItemId`
- `setViewMode`
- `setSearchQuery`
- `setSelectedFileIds`
- `selectAllResources`
- `selectAllLoadedResources`
- `clearSelectAllState`
- `handleBackToList`
- `onActionClick`
- `resolveSelectedResourceIds`

其中 `onActionClick` 处理批量操作：

- `delete`：删除选中资源；如果是“全选全部查询结果”，会通过 `resourceService.deleteResourcesByQuery` 按查询条件批量删除。
- `removeFromKnowledgeBase`：从当前知识库移除资源。
- `batchChunking`：对支持切片的文件调用 `parseFilesToChunks`。
- `deleteLibrary`：删除当前知识库，然后跳转到 `/knowledge`。
- `addToKnowledgeBase` 和 `moveToOtherKnowledgeBase` 当前分支直接 `return`，具体逻辑应该在其他 UI 流程里处理，或还未接入到这个 action。

`selectors.ts` 提供排序和选择相关纯函数，例如：

- `sortFileList`
- `isExplorerItemSelected`
- `getExplorerSelectAllUiState`
- `getExplorerSelectedCount`

这些函数被 `ResourceManager` 的 Explorer、ListView、MasonryView 等组件复用。

目录下还有一组 `src/routes/(main)/resource/store`，包含更简单的 `action.ts` 和 `initialState.ts`。从当前 `rg` 结果看，主业务大量引用的是 `src/routes/(main)/resource/features/store`，因此外层 `store` 更像遗留代码或旧实现残留。阅读时应优先看 `features/store`。

### hooks 和页面辅助逻辑

`useInitFileCheck` 根据 URL query 的 `file` 参数决定打开哪个文件，并切换模式：

- 没有 `file`：回到 `explorer`，清空 `currentViewItemId`。
- 有 `file`：设置 `currentViewItemId`。
- 如果判断为 PDF：进入 `editor`。
- 如果判断为页面文档：进入 `page`。
- 其他文件默认进入 `editor`。

`useResourceManagerUrlSync` 同步排序参数：

- 首次挂载时从 URL 初始化 `sorter` 和 `sortType`。
- 后续 store 变化时写回 URL。
- 默认值会从 URL 中删除，避免 query 冗余。

`useFolderPath` 从 `react-router-dom` 读取 `id` 和 `slug`，判断是否处在 `/resource/library/` 下，并返回：

```ts
{
  knowledgeBaseId,
  currentFolderSlug,
  isInKnowledgeBase,
}
```

`useCurrentFolderId` 再基于 `currentFolderSlug` 获取文件夹 breadcrumb，取最后一级的 `id` 作为当前文件夹 ID。上传文件、查询资源时会用到这个 ID。

`DndContextWrapper` 提供资源拖拽上下文。它没有使用 `dnd-kit`，而是直接监听原生 `dragstart`、`drag`、`drop`、`dragover`、`dragend`，维护当前拖拽项、显示拖拽浮层，并在 drop 时调用 `useTreeStore` 的 `moveItem` 或 `moveItems`。根据当前片段，它主要服务知识库内文件/文件夹移动，并会结合 `selectedFileIds` 支持批量移动。

`FileDetail.tsx` 是文件详情展示组件，展示文件名、大小、类型、创建/更新时间、chunk 数量、embedding 状态，并提供下载按钮。

## 上下游关系

上游路由注册在两个桌面路由配置中保持一致：

- `src/spa/router/desktopRouter.config.tsx`
- `src/spa/router/desktopRouter.config.desktop.tsx`

动态配置里使用 `dynamicElement` 指向这些 route module；desktop 同步配置里直接静态 import：

- `ResourceLayout`
- `ResourceHomePage`
- `ResourceHomeLayout`
- `ResourceLibraryPage`
- `ResourceLibraryLayout`
- `ResourceLibrarySlugPage`

路由结构是：

```txt
resource
├── index: (home)
└── library/:id
    ├── index: library
    └── :slug: library/[slug]
```

下游核心依赖是 `@/features/ResourceManager`。资源路由本身只决定当前是全局资源还是知识库资源，并把状态写入 `useResourceManagerStore`。真正的资源列表、上传、编辑器、页面编辑器、文件列表视图、瀑布流视图、搜索结果浮层、批量操作工具栏，大多在 `src/features/ResourceManager` 下实现。

`ResourceManager` 反过来又依赖本目录的 store 和 hooks：

- `useCurrentFolderId`
- `useResourceManagerStore`
- `useResourceManagerUrlSync`
- `sortFileList`
- `useFolderPath`
- `DndContextWrapper`

这说明当前结构并不是单向的“routes 调 features”，而是 `features/ResourceManager` 也回调了 route 目录里的业务状态。根据 `spa-routes` 约定，这属于未来可以继续迁移的耦合点。

数据层依赖包括：

- `useFileStore`：资源列表、文件上传、资源删除、文档缓存、任务状态等。
- `useKnowledgeBaseStore`：知识库详情、删除知识库、从知识库移除文件等。
- `resourceService`：按 query 删除资源、解析全选资源 ID、搜索资源等。
- `documentService`：进入 page 模式时按 ID 加载文档。
- `useTreeStore`：知识库树结构中的拖拽移动。

UI 基础设施依赖包括：

- `@lobehub/ui`
- `antd`
- `antd-style`
- `react-router-dom`
- `react-i18next`
- `lucide-react`
- `@/features/NavPanel`
- `@/features/LibraryModal`

## 运行/调用流程

访问 `/resource` 时：

1. 桌面 router 匹配 `path: 'resource'`。
2. 渲染 `ResourceLayout`，挂载根 `<Outlet />` 和文件热键。
3. 命中 index 子路由，渲染 `(home)/_layout`。
4. 首页 layout 渲染资源侧边栏和主内容 Outlet。
5. `(home)/index.tsx` 读取 `category` query。
6. `useLayoutEffect` 清空 `libraryId`，并同步 `category` 到 `useResourceManagerStore`。
7. `useInitFileCheck` 检查 `file` query，决定是否进入文件编辑/页面编辑。
8. 渲染 `ResourceManager`。
9. `ResourceManager` 内部始终渲染 `Explorer`，并根据 `mode` 叠加 `FileEditor` 或 `PageEditor`。
10. `Explorer` 根据 `libraryId`、`category`、`currentFolderSlug`、排序等构造 query，调用 `useFetchResources` 获取资源列表。

访问 `/resource/library/:id` 时：

1. 仍然先经过 `ResourceLayout`。
2. 匹配 `library/:id`，渲染 `LibraryLayout`。
3. `LibraryLayout` 渲染知识库侧边栏 `LibraryHierarchy`、主内容 Outlet 和 library 级热键。
4. `library/index.tsx` 从 params 中读取 `id`。
5. `useKnowledgeBaseItem(id)` 加载知识库信息。
6. `useLayoutEffect` 将 `libraryId` 写入 `useResourceManagerStore`。
7. `useInitFileCheck` 继续处理 `file` query。
8. 渲染 `ResourceManager`。
9. `Explorer` 构造 query 时，如果存在 `libraryId`，会忽略 `category`，即知识库内展示所有类型资源；同时用 `currentFolderSlug` 作为 `parentId`。

访问 `/resource/library/:id/:slug` 时：

1. 路由命中 `library/[slug]/index.tsx`。
2. 该文件复用 `library/index.tsx`。
3. `useFolderPath` 读取 `slug`。
4. `useCurrentFolderId` 根据 slug 获取 breadcrumb，推导当前文件夹 ID。
5. `Explorer` 使用 `currentFolderSlug` / `parentId` 限定资源列表。
6. 上传文件时，`ResourceManager` 会把 `libraryId` 和当前文件夹 ID 传给 `pushDockFileList`。

打开文件时：

1. 列表项点击或 URL 带 `?file=xxx` 会设置 `currentViewItemId`。
2. `useInitFileCheck` 根据文件类型选择 `editor` 或 `page`。
3. `ResourceManager` 保持 `Explorer` 常驻，同时用绝对定位 overlay 展示 `FileEditor` 或 `PageEditor`。
4. 点击返回时，`handleBack` 设置 `mode='explorer'`，清空 `currentViewItemId`，并从 URL 删除 `file` query。

## 小白阅读顺序

1. 先看路由配置  
   从 `src/spa/router/desktopRouter.config.tsx` 的 `Resource routes` 开始，理解实际 URL 是 `/resource`、`/resource/library/:id`、`/resource/library/:id/:slug`。

2. 再看根布局  
   阅读 `src/routes/(main)/resource/_layout/index.tsx`，确认它只是 `<Outlet />` 加热键注册。

3. 看两个页面入口  
   阅读 `(home)/index.tsx` 和 `library/index.tsx`。重点看它们如何设置 `category`、`libraryId`、`currentViewItemId`，以及为什么都渲染同一个 `ResourceManager`。

4. 看两个 layout 的侧边栏差异  
   首页侧边栏在 `(home)/_layout`，负责分类和知识库列表；知识库侧边栏在 `library/_layout`，负责知识库层级树。

5. 看 `features/store/initialState.ts`  
   先理解状态字段，再看 `action.ts`。不要一开始就陷入批量删除、全选、chunking 的细节。

6. 看 `useInitFileCheck` 和 `useFolderPath`  
   这两个 hook 是理解 URL 如何驱动页面状态的关键。

7. 最后看 `src/features/ResourceManager/index.tsx`  
   它是主业务组件，负责在 explorer、file editor、page editor 三种模式之间切换。

8. 如果继续深入列表渲染  
   再进入 `src/features/ResourceManager/components/Explorer/index.tsx`，看资源查询参数如何生成，以及 list/masonry 如何切换。

## 常见误区

1. 误以为 `/resource/library/:id/:slug` 有独立页面逻辑  
   实际上 `[slug]/index.tsx` 只是 re-export `../index`。文件夹差异由 URL params 和 hooks 处理。

2. 误以为 `category` 在知识库内仍然生效  
   `Explorer` 构造 query 时写了注释：在具体知识库内会忽略分类筛选，展示所有类型资源。`category` 主要用于 `/resource` 全局资源首页。

3. 误以为 `ResourceManager` 只在当前模式下渲染一个视图  
   它始终渲染 `Explorer`，再根据 `mode` 用 overlay 叠加 `FileEditor` 或 `PageEditor`。这样可以保留列表状态。

4. 误把 `src/routes/(main)/resource/store` 当成主 store  
   当前主要业务引用的是 `src/routes/(main)/resource/features/store`。外层 `store` 看起来更像旧代码残留或未完全删除的早期实现。

5. 误以为 routes 目录完全符合“薄路由”规范  
   这个目录仍有本地 `features`、`store`、`modal`、DnD 等业务实现。按照项目约定，理想方向是迁移到 `src/features/`，但当前代码仍处于混合状态。

6. 忽略 `useLayoutEffect` 的用途  
   首页和知识库页用 `useLayoutEffect` 同步 `libraryId` 和 `category`，是为了在子组件 effect 运行前更新 store，避免 `Explorer` 用旧状态计算查询参数。

7. 忽略全选状态的特殊语义  
   当 `selectAllState === 'all'` 时，`selectedFileIds` 不是“选中的 ID”，而是“排除的 ID”。批量删除、批量切片等操作需要通过 `resolveSelectedResourceIds` 转成真实资源 ID。

8. 误以为拖拽只移动单个文件  
   `DndContextWrapper` 会判断当前拖拽项是否在 `selectedFileIds` 中。如果是，它会移动整个选择集合；否则只移动当前拖拽项。

9. 忘记桌面路由有两份配置  
   `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 必须保持同样的 route tree。新增、删除或调整 `/resource` 路由时，只改一份会导致不同构建入口行为不一致，严重时可能出现空白页。
