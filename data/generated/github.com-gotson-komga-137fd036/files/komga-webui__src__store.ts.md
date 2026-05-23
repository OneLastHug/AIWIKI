# 文件：komga-webui/src/store.ts

## 它负责什么

`komga-webui/src/store.ts` 是 Komga Web UI 的 Vuex 根 store。它不是业务 API 层，也不直接请求后端；它主要承担两类职责：

1. 管理全局 UI 状态，尤其是“可复用弹窗”的打开/关闭状态和弹窗所需的数据。
2. 保存少量跨页面共享的信息，例如公告、版本发布信息、Actuator 构建信息、待检查书籍数量，以及一个持久化的用户偏好模块 `persistedState`。

这个文件导出的是一个已经创建好的 `Vuex.Store` 实例：

```ts
export default new Vuex.Store(...)
```

在 `komga-webui/src/main.ts` 中，它被导入为 `store`，然后传给根 Vue 实例：

```ts
new Vue({
  router,
  store,
  ...
})
```

因此，整个前端组件树都可以通过 `this.$store` 访问这里定义的 state、getters、mutations 和 actions。

## 关键组成

### 1. import 依赖

文件顶部引入了 Vue/Vuex、业务 DTO 类型、持久化插件和工具函数：

- `Vue`、`Vuex`：Vue 2 + Vuex 的状态管理基础。
- `BookDto`：书籍对象类型，来自 `@/types/komga-books`。
- `Oneshot`、`SeriesDto`：单本系列/系列对象类型，来自 `@/types/komga-series`。
- `LibraryDto`：媒体库对象类型，来自 `@/types/komga-libraries`。
- `ReadListDto`：阅读列表对象类型，来自 `@/types/komga-readlists`。
- `ItemDto`、`JsonFeedDto`：公告 feed 类型，来自 `@/types/json-feed`。
- `createPersistedState`：来自 `vuex-persistedstate`，用于把指定 Vuex state 写入本地持久化存储。
- `persistedModule`：本项目自己的持久化模块，来自 `./plugins/persisted-state`。
- `isEmpty`：来自 `lodash`，用于判断 `actuatorInfo` 是否为空。

值得注意的是，`CollectionDto`、`ActuatorInfo`、`ReleaseDto` 在本文件中直接使用但没有显式 import。根据当前片段推断，这些类型可能来自全局类型声明或生成的类型声明文件；依据是 TypeScript 文件中可以直接引用这些类型且仓库中存在大量 `types` 相关定义。

### 2. Vuex 插件注册

文件执行：

```ts
Vue.use(Vuex)
```

这一步让 Vue 2 应用可以使用 Vuex。

随后创建持久化插件：

```ts
const persistedState = createPersistedState({
  paths: ['persistedState'],
})
```

这里非常关键：持久化插件只持久化 Vuex 中的 `persistedState` 模块，而不是整个 store。也就是说，弹窗开关、正在编辑的书籍、待删除的系列等临时 UI 状态不会被保存到浏览器持久化存储里。

### 3. state：全局状态

`state` 可以分成几组。

第一组是 collection 相关弹窗状态：

- `addToCollectionSeriesIds`：准备加入 collection 的 series id 列表。
- `addToCollectionDialog`：加入 collection 弹窗是否打开。
- `editCollection`：当前编辑的 collection。
- `editCollectionDialog`：编辑 collection 弹窗是否打开。
- `deleteCollections`：准备删除的 collection，可能是单个，也可能是数组。
- `deleteCollectionDialog`：删除 collection 确认弹窗是否打开。

第二组是 read list 相关弹窗状态：

- `addToReadListBookIds`：准备加入 read list 的 book id 列表。
- `addToReadListDialog`：加入 read list 弹窗是否打开。
- `editReadList`、`editReadListDialog`：编辑 read list 的对象和弹窗开关。
- `deleteReadLists`、`deleteReadListDialog`：删除 read list 的对象和弹窗开关。

第三组是 library 相关弹窗状态：

- `editLibrary`：当前编辑的 library；为 `undefined` 时可表示新增 library。
- `editLibraryDialog`：新增/编辑 library 弹窗是否打开。
- `deleteLibrary`：准备删除的 library。
- `deleteLibraryDialog`：删除 library 确认弹窗是否打开。

第四组是 book、oneshot、series 相关弹窗状态：

- `updateBooks`、`updateBooksDialog`：编辑单本或多本书籍。
- `deleteBooks`、`deleteBookDialog`：删除单本或多本书籍。
- `updateBulkBooks`、`updateBulkBooksDialog`：批量编辑书籍，固定为 `BookDto[]`。
- `updateOneshots`、`updateOneshotsDialog`：编辑 one-shot。
- `updateSeries`、`updateSeriesDialog`：编辑 series。
- `deleteSeries`、`deleteSeriesDialog`：删除 series。

第五组是首页/状态提示类数据：

- `booksToCheck`：需要检查的书籍数量，首页 badge 会使用。
- `announcements`：公告 feed。
- `actuatorInfo`：后端 Actuator info，包含当前构建版本等信息。
- `releases`：发布版本列表。

这些状态大多是“轻量协调状态”：页面或菜单组件发起动作，把对象放入 store；全局弹窗组件读取对象并展示。

### 4. getters：派生状态

本文件定义了两个 getter。

`getUnreadAnnouncementsCount` 用来计算未读公告数量：

```ts
getUnreadAnnouncementsCount: (state) => (): number => {
  return state.announcements?.items
    ?.filter((value: ItemDto) => false == value._komga?.read)
    ?.length || 0
}
```

它读取 `state.announcements.items`，筛选 `_komga.read` 不为 true 的公告。返回形式是“getter 返回函数”，所以调用方使用：

```ts
this.$store.getters.getUnreadAnnouncementsCount()
```

`isLatestVersion` 用来判断当前版本是否最新：

```ts
isLatestVersion: (state) => (): number => {
  if(isEmpty(state.actuatorInfo)) return -1
  if(state.releases.length == 0) return -1
  if(state.actuatorInfo.build.version == state.releases.find((x: ReleaseDto) => x.latest)?.version) return 1
  else return 0
}
```

返回值不是 boolean，而是三态 number：

- `-1`：信息不足，无法判断。
- `1`：当前版本是最新版本。
- `0`：当前版本不是最新版本。

调用方例如 `HomeView.vue`、`UpdatesView.vue` 会用 `isLatestVersion() == 0` 判断是否显示更新提示。

### 5. mutations：实际修改 state 的入口

mutations 基本都是简单 setter，例如：

```ts
setUpdateBooks(state, books) {
  state.updateBooks = books
}

setUpdateBooksDialog(state, dialog) {
  state.updateBooksDialog = dialog
}
```

每组弹窗通常都有两类 mutation：

1. 设置弹窗要操作的数据，例如 `setUpdateBooks`、`setDeleteSeries`。
2. 设置弹窗显示状态，例如 `setUpdateBooksDialog`、`setDeleteSeriesDialog`。

还有一些非弹窗 mutation：

- `setBooksToCheck`
- `setAnnouncements`
- `setActuatorInfo`
- `setReleases`

这些由页面在加载时通过服务请求后端，再 `commit` 到 store。

### 6. actions：更语义化的操作入口

actions 是本文件最像“业务动作”的部分，但它们仍然不直接请求后端。它们主要负责把多个 mutation 组合成一个用户动作。

例如打开“添加 series 到 collection”的弹窗：

```ts
dialogAddSeriesToCollection({commit}, seriesIds: string[]) {
  commit('setAddToCollectionSeriesIds', seriesIds)
  commit('setAddToCollectionDialog', true)
}
```

这个 action 做了两件事：

1. 记录本次要加入 collection 的 `seriesIds`。
2. 打开 `addToCollectionDialog`。

再如打开编辑书籍弹窗：

```ts
dialogUpdateBooks({commit}, books) {
  commit('setUpdateBooks', books)
  commit('setUpdateBooksDialog', true)
}
```

关闭弹窗的 action 通常只设置 dialog boolean，例如：

```ts
dialogUpdateBooksDisplay({commit}, value) {
  commit('setUpdateBooksDialog', value)
}
```

这种命名模式在文件中非常统一：

- `dialogXxx(...)`：准备数据并打开弹窗。
- `dialogXxxDisplay(...)`：只控制弹窗显示/隐藏。

### 7. modules 和 plugins

store 注册了一个模块：

```ts
modules: {
  persistedState: persistedModule,
}
```

`persistedModule` 来自 `komga-webui/src/plugins/persisted-state.ts`。它保存的是用户偏好和跨会话状态，例如：

- `locale`
- `theme`
- `webreader` 阅读器设置
- `epubreader` 设置
- `browsingPageSize`
- `thumbnailsPageSize`
- collection/read list/library 的筛选条件
- `importPath`
- `duplicatesNewPageSize`
- `rememberMe`

同时 store 注册插件：

```ts
plugins: [persistedState]
```

结合前面的 `paths: ['persistedState']`，只有这个模块会被 `vuex-persistedstate` 持久化。

## 上下游关系

### 上游：谁写入这个 store

主要有三类上游。

第一类是页面和菜单组件，通过 `dispatch` 发起全局弹窗。例如：

- `BrowseSeries.vue` 中会调用 `dialogUpdateBooks`、`dialogAddBooksToReadList`、`dialogDeleteBook`。
- `DashboardView.vue` 会调用 `dialogAddSeriesToCollection`、`dialogDeleteSeries`、`dialogDeleteBook`。
- `SearchView.vue` 会调用 `dialogUpdateBooks`、`dialogAddBooksToReadList`、`dialogDeleteSeries`。
- `BookActionsMenu.vue`、`SeriesActionsMenu.vue`、`LibraryActionsMenu.vue` 等菜单组件也会 dispatch 对应 action。

这类调用的共同点是：调用方通常不关心弹窗组件在哪里，只负责告诉全局 store“我要对这些对象执行某个动作”。

第二类是页面直接 `commit` 状态数据。例如：

- `HomeView.vue` 在 `created` 时请求 Actuator info、待检查书籍数量、公告、发布版本，然后提交 `setActuatorInfo`、`setBooksToCheck`、`setAnnouncements`、`setReleases`。
- `UpdatesView.vue` 会加载 Actuator info 和 releases，用于版本更新页面。
- `AnnouncementsView.vue` 会加载公告并提交 `setAnnouncements`。
- `MediaAnalysis.vue` 会提交 `setBooksToCheck`。

第三类是持久化模块自身的使用者。很多视图会读写 `state.persistedState`，例如：

- `App.vue` 监听 `persistedState.locale` 和 `persistedState.theme`。
- `DivinaReader.vue` 读取 `persistedState.webreader`。
- `EpubReader.vue` 读取 `persistedState.epubreader`。
- `BrowseSeries.vue`、`BrowseBooks.vue`、`BrowseLibraries.vue` 等读取分页大小、筛选状态。

### 下游：谁读取这个 store

最核心的下游是 `komga-webui/src/components/ReusableDialogs.vue`。

这个组件集中渲染多个全局弹窗：

- `CollectionAddToDialog`
- `CollectionEditDialog`
- `ReadListAddToDialog`
- `ReadListEditDialog`
- `LibraryEditDialog`
- `EditBooksDialog`
- `BulkEditBooksDialog`
- `EditOneshotDialog`
- `EditSeriesDialog`
- `ConfirmationDialog`

`ReusableDialogs.vue` 通过 computed getter 读取 store state，例如：

```ts
updateBooks(): BookDto | BookDto[] {
  return this.$store.state.updateBooks
}
```

又通过 computed setter 反向 dispatch 关闭弹窗，例如：

```ts
updateBooksDialog: {
  get(): boolean {
    return this.$store.state.updateBooksDialog
  },
  set(val) {
    this.$store.dispatch('dialogUpdateBooksDisplay', val)
  },
}
```

也就是说，store 和 `ReusableDialogs.vue` 之间形成了一个典型的双向 UI 协调关系：

- store 决定弹窗是否打开、弹窗拿什么数据。
- 弹窗通过 `v-model` 关闭时，再通知 store 修改对应 dialog 状态。

另外，`HomeView.vue`、`UpdatesView.vue`、`AnnouncementsView.vue` 等会读取 getter 或 state 来显示 badge、更新提示、公告未读数量。

## 运行/调用流程

以“在书籍列表里选择多本书，然后打开编辑书籍弹窗”为例，流程大致如下：

1. 用户在某个页面选择书籍，例如 `BrowseBooks.vue`、`BrowseSeries.vue` 或 `SearchView.vue`。
2. 页面调用：

   ```ts
   this.$store.dispatch('dialogUpdateBooks', this.selectedBooks)
   ```

3. `store.ts` 中的 action `dialogUpdateBooks` 执行：

   ```ts
   commit('setUpdateBooks', books)
   commit('setUpdateBooksDialog', true)
   ```

4. `state.updateBooks` 被设置为选中的书籍数组。
5. `state.updateBooksDialog` 被设置为 `true`。
6. `ReusableDialogs.vue` 的 computed `updateBooksDialog` 读取到 `true`。
7. 模板中的 `<edit-books-dialog v-model="updateBooksDialog" :books="updateBooks" />` 打开。
8. `EditBooksDialog` 接收 `books` prop，展示编辑界面。
9. 用户关闭弹窗时，`v-model` 触发 computed setter。
10. setter dispatch `dialogUpdateBooksDisplay`，最终把 `updateBooksDialog` 设回 `false`。

删除书籍、删除系列、添加到阅读列表、添加到 collection 等流程都类似：页面只发起 action，具体弹窗由 `ReusableDialogs.vue` 集中承载。

再看“首页版本提示”的流程：

1. `HomeView.vue` 创建时，如果用户是管理员，会调用 `$actuator.getInfo()` 和 `$komgaReleases.getReleases()`。
2. 请求成功后分别 commit：

   ```ts
   this.$store.commit('setActuatorInfo', x)
   this.$store.commit('setReleases', x)
   ```

3. `store.ts` 中 `isLatestVersion` getter 比较 `actuatorInfo.build.version` 和 releases 中 `latest` 版本。
4. `HomeView.vue` 或 `UpdatesView.vue` 根据 `isLatestVersion()` 的返回值决定是否显示更新提示。

公告未读数流程也类似：

1. 页面调用 `$komgaAnnouncements.getAnnouncements()`。
2. 结果 commit 到 `setAnnouncements`。
3. `getUnreadAnnouncementsCount()` 统计未读公告。
4. `HomeView.vue` 用这个数量显示 badge。

## 小白阅读顺序

1. 先看 `komga-webui/src/main.ts`  
   重点看 `import store from './store'`、`sync(store, router)` 和 `new Vue({ store })`。这样可以确认 `store.ts` 是整个前端应用的根状态容器。

2. 再看 `komga-webui/src/store.ts` 的 `state`  
   不要一开始就纠结每个 DTO 的字段。先按注释分组理解：collections、read lists、libraries、books、oneshots、series、announcements、releases。

3. 接着看 `actions`  
   这里最能看出设计意图。比如 `dialogAddSeriesToCollection` 不是简单 setter，而是“记录数据 + 打开弹窗”的组合动作。

4. 然后看 `mutations`  
   mutations 基本都是 state setter。理解 actions 后再看 mutations，会发现它们只是 Vuex 规定下的实际改值入口。

5. 再看 `komga-webui/src/components/ReusableDialogs.vue`  
   这是理解本文件的关键下游。你会看到 store 中的 `xxxDialog` 和 `xxx` 数据如何被实际绑定到弹窗组件上。

6. 最后看 `komga-webui/src/plugins/persisted-state.ts`  
   这个文件解释了 `persistedState` 模块到底保存什么，以及为什么 `store.ts` 里只持久化 `persistedState` 这一条路径。

7. 有余力再抽样看调用方  
   可以选 `BrowseBooks.vue`、`BrowseSeries.vue`、`SearchView.vue`、`HomeView.vue`。这些文件能展示页面如何通过 `$store.dispatch` 或 `$store.commit` 与全局 store 交互。

## 常见误区

1. 误以为 `store.ts` 会直接调用后端 API  
   实际上，这个文件几乎不做网络请求。真正请求后端的是服务插件和页面组件，例如 `$komgaBooks`、`$komgaAnnouncements`、`$actuator`、`$komgaReleases`。`store.ts` 只保存请求结果或 UI 状态。

2. 误以为所有 state 都会持久化  
   `vuex-persistedstate` 只配置了 `paths: ['persistedState']`。因此 `updateBooksDialog`、`deleteBookDialog`、`announcements`、`actuatorInfo` 等根 state 不会被持久化。真正跨刷新保留的是 `persistedModule` 中的用户偏好和浏览设置。

3. 误把 `dialogXxxDisplay` 当成打开弹窗的主入口  
   `dialogXxxDisplay` 只控制显示状态，通常用于 `v-model` 的 setter 或关闭弹窗。真正打开弹窗并传入数据的是 `dialogXxx`，例如 `dialogUpdateBooks`、`dialogDeleteSeries`、`dialogAddBooksToReadList`。

4. 误以为 `isLatestVersion` 返回 boolean  
   它返回的是 `-1`、`0`、`1` 三态值。`-1` 表示信息不足，`0` 表示不是最新，`1` 表示是最新。调用方通常会写 `isLatestVersion() == 0` 来判断需要显示更新提示。

5. 误以为 `updateBooks` 和 `updateBulkBooks` 是同一套逻辑  
   两者都和书籍编辑有关，但类型和用途不同。`updateBooks` 可以是单个 `BookDto` 或 `BookDto[]`，用于普通编辑弹窗；`updateBulkBooks` 是 `BookDto[]`，对应 `BulkEditBooksDialog`，语义上是批量编辑。

6. 误以为单个删除和批量删除有不同状态字段  
   多数删除状态字段同时支持单个对象和数组，例如 `deleteBooks: BookDto | BookDto[]`、`deleteSeries: SeriesDto | SeriesDto[]`。下游 `ReusableDialogs.vue` 通过 `Array.isArray(...)` 判断当前是单个还是多个，再显示不同文案。

7. 误以为关闭弹窗会清空对应对象  
   多数 `dialogXxxDisplay` 只把 dialog boolean 改成 `false`，并不会清空 `updateBooks`、`deleteSeries` 等数据。根据当前片段推断，这些对象会在下一次打开弹窗时被新的 action 覆盖；依据是 actions 打开弹窗前都会先 commit 对应数据。

8. 误忽略 `ReusableDialogs.vue` 的中心地位  
   很多页面并没有直接引入具体弹窗，而是 dispatch 全局 action。真正渲染弹窗的是 `ReusableDialogs.vue`。如果只看发起页面，会觉得弹窗“凭空出现”；必须把页面 dispatch、`store.ts`、`ReusableDialogs.vue` 连起来看。
