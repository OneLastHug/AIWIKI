# 文件：komga-webui/src/router.ts

## 它负责什么

`komga-webui/src/router.ts` 是 Komga Web UI 的前端路由总入口。它负责把浏览器 URL 映射到具体 Vue 页面组件，定义页面之间的重定向规则，并在进入页面前做统一的访问控制。

从职责上看，它主要做四件事：

1. 初始化 `vue-router`，使用 HTML5 history 模式。
2. 注册 Komga Web UI 的主要页面路由，例如首页、登录、设置、媒体管理、library 浏览、collection/readlist/series/book 详情、阅读器页面等。
3. 定义路由守卫，例如未登录跳转、管理员权限校验、无 library 时跳转欢迎页、无 pinned library 时跳转提示页。
4. 处理少量全局路由副作用，例如页面滚动位置、`document.title` 重置、OAuth2 登录弹窗回调。

这个文件最终 `export default router`，供 `komga-webui/src/main.ts` 导入，并注入根 Vue 实例。

## 关键组成

### 1. import 依赖

文件开头导入了几个核心依赖：

- `@/functions/urls`：提供前端基础路径和后端 origin 等 URL 配置。这里主要用到 `urls.base` 和 `urls.origin`。
- `vue`、`vue-router`：Vue 2 项目的路由基础设施。
- `./store`：Vuex store，路由守卫依赖它判断登录态、管理员权限、library 状态等。
- `@/types/library`：导入 `LIBRARIES_ALL` 和 `LIBRARY_ROUTE`，用于决定 `/libraries/:libraryId?` 应该重定向到哪个 library 子页面。
- `qs`：用于自定义 query string 的解析和序列化。

这里有一个细节：

```ts
const lStore = store as any
```

这说明当前 store 类型没有完整覆盖动态注册模块和 getter，因此作者用 `any` 绕过 TypeScript 类型约束。路由守卫中访问的 `lStore.getters.meAdmin`、`lStore.getters.authenticated`、`lStore.state.komgaLibraries.libraries`、`lStore.getters.getLibrariesPinned` 等都来自全局 store 或插件注册的 Vuex 模块。

### 2. 路由守卫函数

文件中定义了三个局部 `beforeEnter` 守卫。

`adminGuard` 用于管理员页面：

```ts
if (!lStore.getters.meAdmin) next({name: 'home'})
else next()
```

如果当前用户不是管理员，就跳回 `home`。它被用于用户管理、服务器设置、UI 设置、指标、公告、更新、媒体管理、历史、导入等管理类页面。

`noLibraryGuard` 用于需要至少有一个 library 的页面：

```ts
if (lStore.state.komgaLibraries.libraries.length === 0) {
  next({name: 'welcome'})
} else next()
```

如果服务器没有配置任何 library，就跳到 `welcome`。它被用于 library 推荐页、书籍浏览、系列浏览、collections、readlists 等页面。

`noLibraryNorPinGuard` 用于 dashboard：

```ts
if (libraries.length === 0) {
  next({name: 'welcome'})
} else if (pinned libraries.length === 0) {
  next({name: 'no-pins'})
} else next()
```

它比 `noLibraryGuard` 多检查 pinned library。如果没有 library，进入 `welcome`；如果有 library 但没有 pinned library，进入 `no-pins`；否则进入 dashboard。

根据 `komga-webui/src/plugins/komga-libraries.plugin.ts`，`getLibrariesPinned` 是从 `getLibraries` 过滤出没有 `unpinned` 标记的 library。也就是说 dashboard 默认依赖“被固定的 library”。

### 3. `getLibraryRoute`

`getLibraryRoute(libraryId: string)` 决定访问 `/libraries/:libraryId?` 时应该落到哪个具体页面。

它读取：

```ts
lStore.getters.getLibraryRoute(libraryId)
```

并根据 `LIBRARY_ROUTE` 枚举转换成路由名：

- `LIBRARY_ROUTE.COLLECTIONS` -> `browse-collections`
- `LIBRARY_ROUTE.READLISTS` -> `browse-readlists`
- `LIBRARY_ROUTE.BROWSE` -> `browse-libraries`
- `LIBRARY_ROUTE.BOOKS` -> `browse-books`
- `LIBRARY_ROUTE.RECOMMENDED` 或默认 -> `recommended-libraries`

但默认分支还有一个特殊规则：

```ts
return libraryId === LIBRARIES_ALL ? 'browse-libraries' : 'recommended-libraries'
```

`LIBRARIES_ALL` 的值是 `'all'`。因此访问所有 library 的聚合页时，默认会进入 series 浏览页 `browse-libraries`；访问某个具体 library 时，默认更倾向进入推荐页 `recommended-libraries`。

根据当前片段推断，`getLibraryRoute` getter 很可能来自客户端设置相关 Vuex 模块，因为它表示“某个 library 默认打开哪个页面”的用户偏好；依据是 `komga-webui/src/router.ts` 只导入了 `LIBRARY_ROUTE` 类型，而实际 getter 不在目标文件内定义。

### 4. Router 实例配置

核心代码是：

```ts
const router = new Router({
  mode: 'history',
  base: urls.base,
  parseQuery(query: string) {
    return qs.parse(query)
  },
  stringifyQuery(query: Object) {
    const res = qs.stringify(query)
    return res ? `?${res}` : ''
  },
  routes: [...],
  scrollBehavior(...)
})
```

几个配置点需要注意：

- `mode: 'history'`：使用干净 URL，不使用 `#/path`。
- `base: urls.base`：路由基础路径来自 `komga-webui/src/functions/urls.ts`。生产环境通常使用 `window.resourceBaseUrl`，开发环境通常是 `/`。
- `parseQuery` / `stringifyQuery`：用 `qs` 替代 vue-router 默认 query 处理，通常是为了更好地支持复杂 query 对象，例如数组、嵌套对象等。
- `scrollBehavior`：浏览器前进/后退时恢复 `savedPosition`；切换到不同路由名时滚动到页面顶部；同名路由变化时不强制滚动。

### 5. 路由表结构

路由表可以分成几组。

第一组是主应用壳：

```ts
{
  path: '/',
  name: 'home',
  redirect: {name: 'dashboard'},
  component: () => import('./views/HomeView.vue'),
  children: [...]
}
```

`HomeView.vue` 是大部分业务页面的父级容器。它下面挂载 dashboard、设置页、账户页、library 浏览页、详情页、搜索、导入等子路由。虽然子路由的 `path` 多数以 `/` 开头，但它们仍作为 `HomeView` 的 children 存在，意味着这些页面会渲染在 `HomeView.vue` 内部的 `<router-view>` 中。

主应用壳下的重要页面包括：

- `/welcome` -> `WelcomeView.vue`
- `/no-pins` -> `NoPinnedLibraries.vue`
- `/dashboard` -> `DashboardView.vue`
- `/settings/users` -> `SettingsUsers.vue`
- `/settings/server` -> `SettingsServer.vue`
- `/settings/ui` -> `UISettings.vue`
- `/settings/metrics` -> `MetricsView.vue`
- `/settings/announcements` -> `AnnouncementsView.vue`
- `/settings/updates` -> `UpdatesView.vue`
- `/media-management/...` -> 多个媒体管理页面
- `/history` -> `HistoryView.vue`
- `/account/...` -> 账户相关页面
- `/libraries/:libraryId?` -> 动态重定向
- `/libraries/:libraryId/recommended` -> `DashboardView.vue`
- `/libraries/:libraryId/books` -> `BrowseBooks.vue`
- `/libraries/:libraryId/series` -> `BrowseLibraries.vue`
- `/libraries/:libraryId/collections` -> `BrowseCollections.vue`
- `/libraries/:libraryId/readlists` -> `BrowseReadLists.vue`
- `/collections/:collectionId` -> `BrowseCollection.vue`
- `/readlists/:readListId` -> `BrowseReadList.vue`
- `/series/:seriesId` -> `BrowseSeries.vue`
- `/book/:bookId` -> `BrowseBook.vue`
- `/oneshot/:seriesId` -> `BrowseOneshot.vue`
- `/search` -> `SearchView.vue`
- `/import/books` -> `ImportBooks.vue`
- `/import/readlist` -> `ImportReadList.vue`

第二组是不在 `HomeView` 壳里的独立页面：

- `/startup` -> `StartupView.vue`
- `/login` -> `LoginView.vue`
- `/book/:bookId/read` -> `DivinaReader.vue`
- `/book/:bookId/read-epub` -> `EpubReader.vue`
- `*` -> `PageNotFound.vue`

这说明启动页、登录页、阅读器页和 404 页不复用主应用布局。阅读器通常需要全屏或特殊布局，所以单独放在顶层路由是合理的。

### 6. props 映射

很多动态路由使用 `props` 把 URL 参数转成组件 prop，例如：

```ts
props: (route) => ({bookId: route.params.bookId})
```

这样 `BrowseBook.vue`、`BrowseSeries.vue`、`BrowseCollection.vue` 等组件可以通过 prop 接收 ID，而不是直接依赖 `$route.params`。这会让组件更容易测试，也让路由参数和组件输入关系更清晰。

典型映射包括：

- `libraryId` 传给 library 相关页面。
- `collectionId` 传给 `BrowseCollection.vue`。
- `readListId` 传给 `BrowseReadList.vue`。
- `seriesId` 传给 `BrowseSeries.vue`、`BrowseOneshot.vue`。
- `bookId` 传给 `BrowseBook.vue`、`DivinaReader.vue`、`EpubReader.vue`。

### 7. 全局 `beforeEach`

文件底部定义了全局前置守卫：

```ts
router.beforeEach((to, from, next) => {
  ...
})
```

它有三段逻辑。

第一段重置页面标题：

```ts
if (!['read-book', 'read-epub', ...].includes(<string>to.name)) {
  document.title = 'Komga'
}
```

某些详情页或阅读页可能会自己设置更具体的标题，例如书名、系列名。为了避免切换路由时标题闪烁，这里对这些页面做了排除；其他页面进入时统一把标题设为 `Komga`。

第二段处理 OAuth2 弹窗登录回调：

```ts
if (
  window.opener !== null &&
  window.name === 'oauth2Login' &&
  to.query.server_redirect === 'Y'
) {
  ...
  window.close()
}
```

如果当前窗口是名为 `oauth2Login` 的弹窗，并且 query 中有 `server_redirect=Y`，则说明这是 OAuth2 服务端回跳页面。

成功时：

```ts
window.opener.location.href = urls.origin
```

父窗口跳回 Komga origin，让它通过 cookie 完成登录状态刷新。

失败时：

```ts
window.opener.location.href = window.location
```

把错误 URL 传给父窗口，让父窗口处理错误信息。

最后弹窗调用 `window.close()` 关闭自己。

第三段处理未认证用户：

```ts
if (to.name !== 'startup' && to.name !== 'login' && !lStore.getters.authenticated) {
  const query = Object.assign({}, to.query, {redirect: to.fullPath})
  next({name: 'startup', query: query})
} else next()
```

除了 `startup` 和 `login`，其他页面都要求已认证。如果未认证，会跳到 `startup`，并把原目标地址放进 `redirect` query。这样登录完成后可以回到原本想访问的页面。

## 上下游关系

上游入口是 `komga-webui/src/main.ts`。它导入：

```ts
import router from './router'
```

然后在根 Vue 实例中注册：

```ts
new Vue({
  router,
  store,
  vuetify,
  i18n,
  render: h => h(App),
}).$mount('#app')
```

同时 `main.ts` 调用了：

```ts
sync(store, router)
```

这来自 `vuex-router-sync`，作用是把当前路由状态同步进 Vuex store。也就是说，路由不仅驱动页面切换，也能被 store 相关逻辑观察到。

`router.ts` 的关键下游是所有 `views` 页面组件。它通过动态 import 懒加载页面组件，例如：

```ts
component: () => import('./views/BrowseBook.vue')
```

这种写法会让 webpack 按路由拆包，用户访问某个页面时才加载对应 chunk。注释里的 `webpackChunkName` 用于控制打包后的 chunk 名称，便于缓存和调试。

它还依赖以下 store/getter：

- `lStore.getters.authenticated`：判断是否已登录。
- `lStore.getters.meAdmin`：判断是否管理员。
- `lStore.state.komgaLibraries.libraries`：判断是否存在 library。
- `lStore.getters.getLibrariesPinned`：判断是否存在 pinned library。
- `lStore.getters.getLibraryRoute(libraryId)`：判断 library 默认入口页面。

其中 `komgaLibraries` 模块是在 `komga-webui/src/plugins/komga-libraries.plugin.ts` 里通过 `store.registerModule('komgaLibraries', vuexModule)` 动态注册的。该模块提供 `libraries` state，以及 `getLibraries`、`getLibraryById`、`getLibrariesPinned`、`getLibrariesUnpinned` 等 getter。

URL 基础路径来自 `komga-webui/src/functions/urls.ts`。该文件根据 `VUE_APP_KOMGA_API_URL`、`window.location.origin`、`window.resourceBaseUrl` 和 `NODE_ENV` 计算 `origin`、`base` 等值。`router.ts` 使用 `urls.base` 作为前端路由 base，OAuth2 回调时使用 `urls.origin` 重定向父窗口。

## 运行/调用流程

一个典型启动流程如下：

1. 浏览器加载 Komga Web UI。
2. `komga-webui/src/main.ts` 初始化 Vue、插件、store、router。
3. `Vue.use(Router)` 在 `router.ts` 中安装 vue-router 插件。
4. `new Router(...)` 创建路由实例，注册所有路径和守卫。
5. 根 Vue 实例挂载到 `#app`。
6. vue-router 根据当前浏览器路径匹配路由。
7. 先执行全局 `router.beforeEach`。
8. 如果用户未登录，并且目标不是 `startup` 或 `login`，跳转到 `startup`，同时保留 `redirect`。
9. 如果通过全局认证检查，再执行目标路由自己的 `beforeEnter`，例如 `adminGuard`、`noLibraryGuard`。
10. 守卫全部通过后，懒加载目标 `views/*.vue` 组件并渲染。

以访问 `/dashboard` 为例：

1. `/dashboard` 匹配到 `home` 的 child route。
2. 全局 `beforeEach` 检查登录态。
3. 如果未登录，跳到 `/startup?redirect=/dashboard`。
4. 如果已登录，进入 `noLibraryNorPinGuard`。
5. 如果没有 library，跳到 `welcome`。
6. 如果有 library 但没有 pinned library，跳到 `no-pins`。
7. 如果检查通过，加载并显示 `DashboardView.vue`。

以访问 `/settings/users` 为例：

1. 全局守卫先检查是否已认证。
2. `adminGuard` 再检查 `meAdmin`。
3. 非管理员会被重定向到 `home`，而 `home` 又重定向到 `dashboard`。
4. 管理员才会加载 `SettingsUsers.vue`。
5. 如果访问 `/settings/users/add`，它会作为 `SettingsUsers.vue` 的子路由加载 `UserAddDialog.vue`，通常用于在用户管理页上打开添加用户对话框。

以访问 `/libraries/abc` 为例：

1. 匹配到 `/libraries/:libraryId?`。
2. 该路由没有直接页面组件，而是执行 `redirect` 函数。
3. `getLibraryRoute('abc')` 根据用户设置决定目标路由名。
4. 假设返回 `browse-books`，则跳到 `/libraries/abc/books`。
5. 目标页面执行 `noLibraryGuard`，确认至少存在一个 library。
6. 加载 `BrowseBooks.vue`，并传入 `{ libraryId: 'abc' }`。

以 OAuth2 弹窗回调为例：

1. 用户在名为 `oauth2Login` 的弹窗里完成 OAuth2 流程。
2. 服务端重定向回前端，并带上 `server_redirect=Y`。
3. 全局 `beforeEach` 检测到 `window.opener !== null`、`window.name === 'oauth2Login'`。
4. 如果没有 `error` query，父窗口跳到 `urls.origin`。
5. 如果有 `error` query，父窗口跳到当前错误 URL。
6. 弹窗关闭。

## 小白阅读顺序

建议按下面顺序读这个文件和相关上下文：

1. 先看 `komga-webui/src/main.ts`  
   明白 `router` 是在哪里被导入、如何注入 Vue 根实例、如何和 `store` 同步的。

2. 再看 `komga-webui/src/router.ts` 顶部 import  
   搞清楚它依赖 `Vue`、`Router`、`store`、`urls`、`LIBRARY_ROUTE` 和 `qs`。

3. 接着看三个局部守卫  
   重点理解 `adminGuard`、`noLibraryGuard`、`noLibraryNorPinGuard` 的分工。它们决定了“哪些页面能不能进”。

4. 然后看 `getLibraryRoute`  
   这是 `/libraries/:libraryId?` 这种入口路由的核心。新手容易忽略它，因为它不是页面组件，但它决定用户打开 library 时看到推荐页、series、books、collections 还是 readlists。

5. 再整体扫 `routes` 数组  
   不要一上来逐行背所有路由。先按页面类型分组：主壳页面、设置页面、媒体管理页面、账户页面、library 浏览页面、详情页面、阅读器页面、登录/启动页面、404 页面。

6. 最后看全局 `beforeEach`  
   这是整个文件最容易影响用户访问体验的地方。认证跳转、OAuth2 弹窗处理、标题重置都在这里。

7. 补读 `komga-webui/src/plugins/komga-libraries.plugin.ts`  
   重点看 `komgaLibraries` 模块如何提供 `libraries` 和 `getLibrariesPinned`，这样才能理解 dashboard 为什么会跳到 `welcome` 或 `no-pins`。

8. 补读 `komga-webui/src/functions/urls.ts`  
   理解为什么 router 的 `base` 不直接写死成 `/`，以及 OAuth2 回调为什么使用 `urls.origin`。

## 常见误区

1. 误以为所有页面都在 `HomeView.vue` 里面渲染  
   不是。大部分业务页面是 `home` 的 children，会使用 `HomeView.vue` 作为壳；但 `/startup`、`/login`、阅读器页面和 404 是顶层路由，不走这个壳。

2. 误以为 `/libraries/:libraryId?` 是一个真实页面  
   它只是一个重定向入口。真正的页面是 `/libraries/:libraryId/recommended`、`/books`、`/series`、`/collections`、`/readlists` 等。

3. 误以为 `beforeEnter` 会负责登录校验  
   单个路由的 `beforeEnter` 主要负责管理员权限和 library 状态。登录校验是在全局 `router.beforeEach` 中统一做的。

4. 误以为 `adminGuard` 会跳到登录页  
   非管理员不是跳登录页，而是跳 `home`。由于 `home` 又重定向到 `dashboard`，实际效果通常是回到 dashboard。

5. 误以为 `noLibraryGuard` 检查的是当前 `libraryId` 是否存在  
   它只检查 `lStore.state.komgaLibraries.libraries.length === 0`，即系统是否一个 library 都没有。它没有在当前片段中验证 URL 里的 `libraryId` 是否有效。

6. 误以为 `noLibraryNorPinGuard` 和 `noLibraryGuard` 一样  
   `noLibraryNorPinGuard` 多了一层 pinned library 检查。它专门用于 dashboard，因为 dashboard 依赖 pinned library 展示内容。

7. 误以为 `qs` 是多余的  
   vue-router 默认也能处理 query，但 `qs` 对数组和复杂对象更友好。这里通过 `parseQuery` 和 `stringifyQuery` 替换默认 query 行为，可能是为了支持复杂筛选条件或页面状态。

8. 误以为 `document.title = 'Komga'` 会覆盖所有页面标题  
   它刻意排除了一批详情页和阅读页，例如 `read-book`、`read-epub`、`browse-book`、`browse-series` 等。这些页面可能自己设置标题，路由层避免造成标题闪烁。

9. 误以为 `window.opener` 逻辑和普通路由跳转有关  
   这段只针对 OAuth2 弹窗登录回调。触发条件很严格：必须有 opener，窗口名必须是 `oauth2Login`，并且 query 中 `server_redirect` 必须是 `Y`。

10. 误以为动态 import 只是普通导入写法  
   `component: () => import(...)` 是路由级懒加载。用户访问对应页面时才加载该页面 chunk，减少初始包体积。`webpackChunkName` 注释用于命名这些异步 chunk。
