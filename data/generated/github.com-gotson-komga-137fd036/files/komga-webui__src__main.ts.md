# 文件：komga-webui/src/main.ts

## 它负责什么

`komga-webui/src/main.ts` 是 Komga Web UI 的前端启动入口。它的职责不是实现某个页面功能，而是把整个 Vue 2 应用“组装起来”：导入全局依赖、注册 Vue 插件、挂载全局服务、连接 `router` 与 `store`，最后创建根 Vue 实例并渲染 `App.vue`。

可以把它理解成前端应用的“启动总线”。浏览器加载 Web UI 后，真正进入业务页面之前，会先经过这里完成以下准备：

1. 给 Vue 原型挂载全局工具，例如 `$_`、`$eventHub`。
2. 配置第三方插件，例如 `Vuelidate`、`vue-line-clamp`、`vue-chartkick`。
3. 注册 Komga 自己封装的一批业务插件，例如 books、series、libraries、users、settings、SSE 等。
4. 注入核心基础设施：`router`、`store`、`vuetify`、`i18n`。
5. 把根组件 `App.vue` 挂载到页面中的 `#app` 节点。

这个文件本身没有导出业务函数，也不直接处理具体页面逻辑。它的核心价值在于确定“应用启动时有哪些能力是全局可用的”。

## 关键组成

第一组 import 是第三方基础库：

- `lodash`：作为 `_` 引入，并挂到 `Vue.prototype.$_`，让组件可以通过 `this.$_` 使用 lodash。
- `Vue`：Vue 2 主库。
- `vue-line-clamp`：文本截断插件，用于多行文本省略。
- `vuelidate`：表单校验插件。
- `vue-chartkick` 和 `chart.js`：图表展示相关插件。
- `vuex-router-sync` 的 `sync`：用于把路由状态同步进 Vuex。

第二组 import 是应用内部核心模块：

- `App`：根组件 `./App.vue`。
- `router`：来自 `./router`，定义路由表、路由守卫和懒加载页面。
- `store`：来自 `./store`，是全局 Vuex Store。
- `i18n`：国际化实例。
- `vuetify`：UI 框架实例。
- `./public-path`：Webpack public path 配置，影响生产环境资源加载路径。

第三组 import 是 Komga 业务插件：

- `httpPlugin`：创建 Axios 实例并挂到 `Vue.prototype.$http`。
- `logger`：日志插件。
- `komgaSettings`、`komgaUsers`、`komgaLibraries` 等：把对应领域的 service 和 Vuex module 注册进应用。
- `komgaSse`：服务端事件推送相关插件，通过 `$eventHub` 和 `store` 协作。
- `actuator`、`komgaMetrics`、`komgaAnnouncements`、`komgaReleases` 等：偏系统状态、监控、公告和更新检查的插件。

文件中还配置了 `Chartkick.options.colors`，为图表定义统一颜色数组。这是全局图表主题的一部分，所有通过 Chartkick 渲染的图表都会受到影响。

`Vue.prototype.$eventHub = new Vue()` 是一个重要点。这里创建了一个独立 Vue 实例作为事件总线，后续组件可以通过 `this.$eventHub.$on(...)`、`this.$eventHub.$emit(...)` 进行跨组件事件通信。比如 `App.vue` 中会监听 `LIBRARY_ADDED`、`LIBRARY_DELETED`、`LIBRARY_CHANGED`、`SESSION_EXPIRED` 等事件。

文件末尾有两个 TypeScript 声明扩展：

```ts
declare module 'vue/types/vue' {
  interface Vue {
    $_: LoDashStatic;
    $eventHub: Vue;
  }
}

declare global {
  interface Window {
    resourceBaseUrl: string
  }
}
```

前者告诉 TypeScript：所有 Vue 组件实例上都有 `this.$_` 和 `this.$eventHub`。后者告诉 TypeScript：浏览器全局 `window` 上存在 `resourceBaseUrl`。这个字段与 `public-path.js` 相关，生产环境中会用它拼接 Webpack 静态资源基础路径。

## 上下游关系

上游来看，`main.ts` 依赖构建系统和 HTML 容器。它最终执行：

```ts
new Vue({
  router,
  store,
  vuetify,
  i18n,
  render: h => h(App),
}).$mount('#app')
```

这说明页面 HTML 中必须存在 `id="app"` 的 DOM 节点。Webpack/Vue CLI 会把这个入口打包，并在浏览器中执行。`./public-path` 会在入口早期执行，用于设置 `__webpack_public_path__`。根据当前片段可知，生产环境下它会使用 `window.location.origin + window.resourceBaseUrl`，开发环境下使用 `/`。

中游来看，`main.ts` 连接了多个核心模块：

- `router.ts` 负责页面路径、路由守卫、懒加载视图组件。
- `store.ts` 负责全局 Vuex 状态、mutations、actions、getters。
- `i18n.ts` 负责语言环境。
- `plugins/vuetify` 负责 UI 框架配置。
- `plugins/*.plugin.ts` 负责把业务 service、Vuex module 或全局方法注入 Vue。

下游来看，所有 Vue 组件都会间接受到 `main.ts` 的影响。比如组件中如果使用 `this.$http`、`this.$komgaLibraries`、`this.$komgaUsers`、`this.$eventHub`、`this.$_`，这些能力基本都来自这里注册的插件或原型挂载。

以 `komga-libraries.plugin.ts` 为例，它在 install 阶段创建 `KomgaLibrariesService`，挂到 `Vue.prototype.$komgaLibraries`，并执行：

```ts
store.registerModule('komgaLibraries', vuexModule)
```

这意味着 `main.ts` 中 `Vue.use(komgaLibraries, {store, http})` 执行后，路由守卫和组件才能访问 `store.state.komgaLibraries`、`getLibrariesPinned` 等状态或 getter。`router.ts` 中的 `noLibraryGuard`、`noLibraryNorPinGuard` 就依赖这些数据。

## 运行/调用流程

启动流程可以按时间顺序这样理解：

1. 浏览器加载前端 bundle，执行 `main.ts`。
2. `main.ts` 先导入 `./public-path`，设置静态资源加载基础路径。虽然 import 位置在代码中间，但 ES module 的导入会在模块执行前处理；实际语义上这是入口初始化的一部分。
3. 导入 `router`、`store`、`i18n`、`vuetify` 和根组件 `App.vue`。
4. 把 lodash 挂到 `Vue.prototype.$_`，把事件总线挂到 `Vue.prototype.$eventHub`。
5. 配置 Chartkick 的颜色，并通过 `Vue.use(Chartkick.use(Chart))` 启用图表插件。
6. 注册通用插件：`Vuelidate`、`lineClamp`。
7. 注册 `httpPlugin`，创建 Axios 客户端并注入 `this.$http`。这个顺序很关键，因为后面的 Komga 业务插件普遍需要 `Vue.prototype.$http`。
8. 注册 `logger` 和各类 Komga 插件。多数插件会创建 service，并挂到 Vue 原型上；部分插件还会向 Vuex 动态注册 module。
9. 设置 `Vue.config.productionTip = false`，关闭 Vue 生产提示。
10. 调用 `sync(store, router)`，把当前路由状态同步到 Vuex 中。这样 store 里可以访问路由信息，调试时也更容易看到路由状态。
11. 创建根 Vue 实例，把 `router`、`store`、`vuetify`、`i18n` 注入进去。
12. 渲染 `App.vue`，并挂载到 `#app`。

`App.vue` 是启动后的第一个组件。它的模板非常薄，只是：

```vue
<v-app>
  <router-view/>
</v-app>
```

也就是说，实际页面由 `router-view` 根据当前路由选择对应 view 组件来渲染。`App.vue` 同时会监听全局事件：媒体库变化时重新 dispatch `getLibraries`，会话过期时调用 `this.$komgaUsers.logout()` 并跳转到 `login` 路由。这些能力都依赖 `main.ts` 已经提前注册 `$eventHub`、`$komgaUsers`、`store` 和 `router`。

## 小白阅读顺序

建议不要一开始就逐个钻进所有插件。这个文件里的插件数量很多，但它们的模式大体相似。更适合按“主干到分支”的顺序读：

1. 先读 `komga-webui/src/main.ts`，只抓住三件事：注册插件、同步路由、创建 Vue 根实例。
2. 再读 `komga-webui/src/App.vue`，理解根组件只提供 `v-app` 和 `router-view`，同时监听全局事件。
3. 接着读 `komga-webui/src/router.ts`，看 URL 如何映射到页面，以及哪些路由守卫依赖 Vuex 状态。
4. 再读 `komga-webui/src/store.ts`，理解全局 Store 的基础状态和 actions。
5. 然后读 `komga-webui/src/plugins/http.plugin.ts`，因为它提供 `$http`，后面大部分业务插件都依赖它。
6. 最后抽样读一个业务插件，例如 `komga-webui/src/plugins/komga-libraries.plugin.ts`。看懂它如何创建 service、挂载 `this.$komgaLibraries`、注册 Vuex module 后，再看其他插件会容易很多。

读 `main.ts` 时可以特别关注 `Vue.use(...)` 的顺序。`httpPlugin` 必须早于依赖 HTTP 的业务插件；`komgaSettings`、`komgaUsers`、`komgaLibraries` 这类传入 `store` 的插件，通常会改变全局状态结构；`komgaSse` 传入的是 `eventHub` 和 `store`，说明它更偏事件推送和状态联动。

## 常见误区

第一个误区是把 `main.ts` 当成业务逻辑文件。它不是业务页面，也不是 API service。它主要负责装配应用。如果想找“获取书籍列表怎么实现”，应该顺着 `komgaBooks` 插件进入对应 service，而不是在 `main.ts` 里找请求细节。

第二个误区是忽略插件注册顺序。比如很多插件安装时需要 `{http: Vue.prototype.$http}`，因此 `Vue.use(httpPlugin)` 必须先执行。否则这些插件拿不到 Axios 实例。当前文件中先注册 `httpPlugin`，再注册业务插件，正是为了满足这个依赖。

第三个误区是以为 `store.ts` 中定义了所有 Vuex 状态。实际上，部分状态模块是插件运行时通过 `store.registerModule(...)` 动态注册的。例如 `komga-libraries.plugin.ts` 注册了 `komgaLibraries` 模块。`router.ts` 里访问 `store.state.komgaLibraries.libraries`，依赖的就是这个动态模块。

第四个误区是忽略 `$eventHub`。它不是 Vue 官方默认属性，而是这里手动挂到 `Vue.prototype` 的事件总线。`App.vue` 中监听 SSE 或全局事件，就是通过它完成。根据当前片段推断，`komgaSse` 插件会接收 `{eventHub, store}`，并在收到服务端事件后通过事件总线通知应用其他部分。

第五个误区是认为 `sync(store, router)` 会替代路由。它只是把 Vue Router 的状态同步到 Vuex，真正控制页面跳转和组件匹配的仍然是 `router.ts` 里的 `new Router(...)` 配置。

第六个误区是忽略 TypeScript 的 `declare module`。`Vue.prototype.$_ = _` 只是在运行时挂载属性；如果没有 `declare module 'vue/types/vue'`，TypeScript 在组件里看到 `this.$_`、`this.$eventHub` 时可能会报类型错误。因此文件末尾的声明是运行时注入的类型补充，不是多余代码。
