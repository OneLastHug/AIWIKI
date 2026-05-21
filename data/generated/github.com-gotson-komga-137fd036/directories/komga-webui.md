# 目录：komga-webui

## 它负责什么

`komga-webui` 是 Komga 的前端 Web UI 子项目，技术栈是 Vue 2 + TypeScript + Vue Router + Vuex + Vuetify。它的职责不是单纯展示页面，而是把后端能力包装成一个完整的读书/管理界面：登录态、主题、国际化、图书馆浏览、系列/书单/合集管理、后台设置、任务和统计、公告与更新提示等，都集中在这里完成。

从 `package.json` 看，这个目录本质上是一个独立的前端应用，使用 `vue-cli-service` 构建和开发，入口端口是 `8081`。从 `src/main.ts` 看，它会在启动时装配一组插件，把 HTTP、事件总线、i18n、路由、状态管理和 UI 主题串起来。

## 关键组成

直接看目录结构，核心内容分成几块：

`src/main.ts`、`src/App.vue`、`src/router.ts`、`src/store.ts` 是骨架层。  
`src/plugins` 是能力层，里面注册了大量领域插件，例如 `komga-books`、`komga-series`、`komga-libraries`、`komga-users`、`komga-sse`、`komga-settings` 等。根据当前片段推断，这些插件大多负责把后端 API 封装成 `Vue.prototype` 上的方法或模块化服务。  
`src/views` 是页面层，路由里的页面几乎都懒加载到这里。  
`src/components`、`src/functions`、`src/types`、`src/locales`、`src/styles` 分别承载通用组件、工具函数、类型定义、翻译文案和全局样式。  
`public/index.html`、`public/manifest.json` 和各类 icon 资源说明它是标准 SPA 入口。

其中最关键的三件事是：

1. `main.ts` 负责初始化所有插件与全局能力。  
2. `router.ts` 负责页面路由、守卫和库相关的跳转策略。  
3. `store.ts` 负责跨页面共享的 UI 状态，尤其是各种弹窗和通知数据。

## 上下游关系

上游主要是后端 Komga API 和 SSE 事件流。`main.ts` 把 `httpPlugin`、`komgaSse`、`komgaUsers`、`komgaLibraries` 等插件注册进去，说明前端几乎所有业务数据都来自后端接口，SSE 则用来推送库变更、会话过期等事件。`App.vue` 监听了 `LIBRARY_ADDED`、`LIBRARY_CHANGED`、`LIBRARY_DELETED`、`SESSION_EXPIRED`，也证明前端会根据后端推送刷新库列表或强制登出。

下游是页面路由和视图组件。`router.ts` 里的路由按业务域组织：欢迎页、仪表盘、库浏览、后台设置、媒体管理、历史、账户页等。很多页面通过 `beforeEnter` 守卫直接依赖 Vuex 状态，比如是否管理员、是否存在库、是否有 pinned libraries。也就是说，路由不是纯展示层，而是强依赖全局状态和登录态的导航层。

`store.ts` 的下游则是各类对话框和页面动作。它保存了“新增到合集/书单”“编辑/删除库”“更新书籍/系列”“公告”“版本发布”“待检查书籍数”等状态，页面和组件通过 `dispatch` / `commit` 触发这些弹窗，而不是自己各管各的本地状态。

## 运行/调用流程

启动时先走 `src/main.ts`。这里会先挂载 lodash、事件总线、Vuelidate、Chartkick、HTTP 插件、日志插件，再逐个 `Vue.use(...)` 注册领域插件。随后 `sync(store, router)` 把路由和 Vuex 同步，最后创建根实例并挂到 `#app`。

进入页面后，`src/App.vue` 作为最外层壳组件，只渲染 `<router-view/>`，但它承担了全局副作用：监听系统暗色模式变化、订阅 SSE 事件、根据 `persistedState.theme` 和 `persistedState.locale` 自动切换主题和语言。`SESSION_EXPIRED` 来时，它会调用 `this.$komgaUsers.logout()` 再跳转到 `login`。

路由层的核心逻辑在 `src/router.ts`。它用 `qs` 自定义 query parse/stringify，用 `urls.base` 作为 history base，并通过守卫判断权限。`getLibraryRoute()` 会根据某个库的路由偏好，把 `/libraries/:libraryId?` 重定向到 `books`、`series`、`collections`、`readlists` 或 `recommended` 视图。这个分流逻辑说明“同一个库”可以以不同浏览方式呈现，且选择权来自 store 里的库配置。

## 小白阅读顺序

1. 先看 `package.json`，确认这是 Vue 2 项目、有哪些核心依赖。  
2. 再看 `src/main.ts`，理解全局插件、HTTP、事件总线、路由和 store 是怎么装配的。  
3. 接着看 `src/App.vue`，把主题、语言、SSE 事件和登出流程串起来。  
4. 然后看 `src/router.ts`，重点理解路由分组、守卫、懒加载和库路由跳转。  
5. 再看 `src/store.ts`，重点关注 state 里那些弹窗和业务对象的生命周期。  
6. 最后按业务域去看 `src/plugins` 和 `src/views`，从“书籍/系列/库/用户/设置”这些主线切进去。

## 常见误区

最容易误判的是把它当成“纯展示前端”。实际上它更像一个前端业务中枢：既管页面，也管状态、权限、事件和后端 API 适配。

第二个误区是忽略 `src/plugins`。从 `main.ts` 的注册顺序看，真正的业务能力大多被封装进插件里，视图组件只是消费这些注入的方法和状态。

第三个误区是低估 `store.ts` 的作用。这里不只是缓存数据，还承载了大量 UI 工作流状态，比如“点了删除后先打开弹窗”“批量更新书籍”“公告未读数”“版本是否最新”。很多页面逻辑其实是围绕这些全局状态展开的。

第四个误区是以为路由只是页面列表。`router.ts` 里有权限守卫、库存在性判断、无 pin 引导页，以及按库配置重定向的逻辑。也就是说，导航本身就是业务规则的一部分。
