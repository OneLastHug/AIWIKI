# 目录：komga-webui/src

## 它负责什么

`komga-webui/src` 是 Komga 的前端应用源码根目录，负责浏览器端的完整交互界面：登录后主框架、书库浏览、书籍/系列/合集/阅读列表管理、账号设置、管理员设置、媒体维护、统计指标、公告与更新提示等。技术栈是 Vue 2 + TypeScript + Vue Router + Vuex + Vuetify，构建入口来自 `komga-webui/package.json` 中的 `vue-cli-service serve --port 8081` 和 `vue-cli-service build`。

从结构看，这个目录不是单纯的页面集合，而是一个“前端壳 + 路由 + 全局状态 + API 服务插件 + 类型定义 + 组件库”的组合。`main.ts` 把 Vue、Vuetify、router、store、i18n 和大量 `$komgaXxx` 服务插件装配起来；`App.vue` 只保留最外层 `<v-app>` 与 `<router-view/>`，并处理全局主题、语言和 SSE 事件；实际业务页面主要落在 `views` 与 `components` 中。

## 关键组成

`main.ts` 是应用启动入口。它注册 `Vuelidate`、`vue-line-clamp`、`vue-chartkick`、`Chart.js`，创建全局 `$_` lodash、`$eventHub` 事件总线，然后依次安装 `http.plugin`、`logger.plugin`、`komga-books.plugin`、`komga-libraries.plugin`、`komga-users.plugin`、`komga-sse.plugin` 等插件。最后通过 `sync(store, router)` 将路由状态同步到 Vuex，并挂载 `App` 到 `#app`。

`router.ts` 是页面地图。它使用 history 模式，`base` 来自 `@/functions/urls`，查询字符串由 `qs` 解析和序列化。路由以 `HomeView.vue` 为登录后主布局，下面挂载 `dashboard`、`libraries`、`browse-books`、`browse-libraries`、`browse-collections`、`browse-readlists`、`browse-series`、`browse-book`、`search`、`settings-*`、`media-management/*` 等页面。它还定义了 `adminGuard`、`noLibraryGuard`、`noLibraryNorPinGuard`，分别处理管理员权限、无书库跳转欢迎页、无固定书库跳转提示页。

`store.ts` 是全局 Vuex store 的基础部分。它保存大量跨页面弹窗状态，例如新增到合集、编辑阅读列表、编辑书库、更新书籍、删除系列等，也保存 `booksToCheck`、`announcements`、`actuatorInfo`、`releases` 这类全局提示数据。需要注意，`store.ts` 只展示基础 store；根据 `main.ts` 的安装方式，部分插件会继续向 store 注册模块或动作，例如书库、用户、设置相关能力。

`plugins` 是前端和后端 API 的桥接层。`http.plugin.ts` 创建 axios client，`baseURL` 来自 `urls.origin`，开启 `withCredentials` 并加上 `X-Requested-With` 请求头；响应拦截器会递归把 ISO 日期字符串转换为 `Date`。类似 `komga-books.plugin.ts` 的插件会把 `KomgaBooksService` 注入到 `Vue.prototype.$komgaBooks`，让组件可以通过 `this.$komgaBooks` 调用后端。

`services` 根据当前片段推断是具体 API service 的实现目录，依据是 `komga-books.plugin.ts` 从 `@/services/komga-books.service` 创建服务实例。`types` 保存 DTO、枚举和事件类型，例如 `komga-books`、`komga-series`、`komga-libraries`、`events`、`themes`。`locales` 配合 `i18n.ts` 提供多语言 JSON。`styles` 放全局样式，`assets` 放 logo 等静态资源，`functions` 放 URL 等工具函数。

## 上下游关系

上游输入主要来自浏览器环境、后端 API 和服务端运行上下文。`public-path.js`、`functions/urls`、`vue.config.js` 共同影响资源路径和 API 基础地址；`http.plugin.ts` 负责把浏览器请求发往 Komga 后端；`komga-sse.plugin` 根据当前片段推断负责接收服务器推送事件，因为 `App.vue` 监听了 `LIBRARY_ADDED`、`LIBRARY_DELETED`、`LIBRARY_CHANGED`、`SESSION_EXPIRED` 等事件。

下游输出是用户可见的 Vue 页面。`router.ts` 把 URL 分发到 `views` 中的页面组件；页面组件再组合 `components` 中的通用控件、菜单、对话框。`HomeView.vue` 是主工作台布局，包含顶部搜索框、左侧导航抽屉、书库列表、导入、媒体管理、历史、设置等入口。它依赖 Vuex 中的书库、任务数、公告未读数等状态来显示徽标和菜单。

服务调用关系大致是：组件调用 `this.$komgaBooks`、`this.$komgaLibraries`、`this.$komgaUsers` 等注入服务；服务通过 `this.$http` 发 axios 请求；响应进入组件或 Vuex；Vuex 状态变化再驱动页面刷新。事件关系则是：`komga-sse.plugin` 收到后端事件后通过 `$eventHub` 广播；`App.vue` 监听事件后触发 `getLibraries` 或执行登出跳转。

## 运行/调用流程

应用启动时，Vue CLI 加载 `main.ts`。第一步注册第三方库和全局插件，特别是 axios、日志、各类 Komga API service、SSE、Vuetify、i18n。第二步创建 router 和 store 的同步关系，使路由状态进入 Vuex。第三步渲染 `App.vue`。

进入 `App.vue` 后，最外层 `<v-app>` 提供 Vuetify 应用容器，真正页面由 `<router-view/>` 决定。`App.vue` 在 `created` 中监听系统深色模式变化、书库变更事件、会话过期事件；同时 watch `persistedState.locale` 和 `persistedState.theme`，即时切换语言方向和明暗主题。

当用户访问 `/` 时，`router.ts` 重定向到 `dashboard`。`dashboard` 在进入前会经过 `noLibraryNorPinGuard`：如果没有任何书库，跳到 `welcome`；如果没有固定书库，跳到 `no-pins`；否则加载 `DashboardView.vue`。访问 `/libraries/:libraryId` 时，路由不会直接显示页面，而是根据 `getLibraryRoute(libraryId)` 决定跳到推荐页、系列浏览、书籍浏览、合集或阅读列表。管理员页面如 `/settings/users`、`/settings/server`、媒体管理页面等会先经过 `adminGuard`。

一次典型业务操作是：用户在 `HomeView.vue` 或某个浏览页面点击按钮；组件 dispatch Vuex action 或调用 `$komgaXxx` 服务；服务通过 axios 请求后端；成功后更新本地状态、弹窗状态或触发事件；页面根据 Vuex、props、route 参数重新渲染。

## 小白阅读顺序

建议先读 `komga-webui/package.json`，确认这是 Vue CLI 项目、运行端口是 8081、核心依赖是 Vue 2、Vuetify、Vuex、Vue Router、axios。

第二步读 `src/main.ts`，重点看插件安装顺序。这里能建立“所有页面为什么能用 `this.$http`、`this.$komgaBooks`、`this.$komgaUsers`、`this.$eventHub`”的基本认知。

第三步读 `src/App.vue`，理解最外层应用只负责主题、语言、全局事件和路由出口，不承载具体业务页面。

第四步读 `src/router.ts`，把 URL、页面和权限守卫对应起来。阅读时不必一次记住所有 route，先抓住 `HomeView.vue` 作为主布局、`views/*` 作为页面、`beforeEnter` 作为权限/前置状态检查即可。

第五步读 `src/store.ts`，理解全局弹窗和提示状态。再结合插件目录继续看各个 store module 或 service。

第六步挑一个业务链路深入，例如书籍：从 `plugins/komga-books.plugin.ts` 到 `services/komga-books.service`，再到 `types/komga-books`，最后看 `views/BrowseBooks.vue` 或 `views/BrowseBook.vue`。

## 常见误区

不要把 `store.ts` 理解为全部状态来源。它是基础 Vuex store，但 `main.ts` 中很多插件拿到了 `store`，根据当前片段推断它们可能注册额外模块、actions 或 getters，所以看到 `router.ts` 使用 `meAdmin`、`getLibrariesPinned`、`getLibraryRoute` 这类 getter 时，不一定能在 `store.ts` 里直接找到定义。

不要把 `views` 和 `components` 混为一谈。`views` 是路由级页面，通常由 `router.ts` 懒加载；`components` 是页面内部复用的菜单、对话框、卡片、搜索框等。比如 `HomeView.vue` 是主布局 view，但它里面使用了 `search-box`、`reorder-libraries`、`libraries-actions-menu`、`library-actions-menu` 等组件。

不要忽略 `App.vue` 的全局事件。书库新增、删除、修改后并不是只靠当前页面刷新，`App.vue` 会监听事件并 dispatch `getLibraries`。会话过期也不是普通接口错误展示，而是通过 `SESSION_EXPIRED` 事件触发 `$komgaUsers.logout()` 并跳转 `login`。

不要以为 `publicPath` 固定是 `/`。`vue.config.js` 在生产环境使用 `./`，开发环境使用 `/`，这是为了兼容 servlet context path 和开发服务器任意路径加载。资源路径问题应同时看 `vue.config.js`、`public-path.js`、`functions/urls`。

不要手动按字符串解析接口日期。`http.plugin.ts` 的响应拦截器已经会递归处理 ISO 日期字符串，把它们转成 `Date`。如果页面里再假设日期仍是字符串，可能会产生类型和显示问题。
