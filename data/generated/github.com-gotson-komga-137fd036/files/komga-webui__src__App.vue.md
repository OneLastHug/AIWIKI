# 文件：komga-webui/src/App.vue

## 它负责什么

`App.vue` 是整个 `komga-webui` 的根组件，职责很轻，但位置很关键。它本身不渲染具体业务页面，只提供最外层的 `v-app` 容器和一个 `router-view`，让路由页面真正显示出来。换句话说，它是 Web UI 的全局壳。

更重要的是，它在这里集中处理两类全局状态联动：

1. 主题切换：根据持久化的 `theme` 和系统深色模式偏好，控制 Vuetify 的全局深浅色主题。
2. 语言与布局方向：根据持久化的 `locale`，同步 `vue-i18n` 语言和 Vuetify 的 RTL 状态。

此外，它还监听全局事件总线上的库变更和会话过期事件，做跨页面的统一响应。

## 关键组成

模板部分非常简洁：

- `<v-app>`：Vuetify 的根布局容器。
- `<router-view/>`：当前路由对应页面的挂载点。

脚本部分是核心逻辑：

- `Theme`：来自 `@/types/themes`，定义 `LIGHT`、`DARK`、`SYSTEM` 三种主题。
- `LIBRARY_ADDED`、`LIBRARY_CHANGED`、`LIBRARY_DELETED`、`SESSION_EXPIRED`：来自 `@/types/events`，用于全局消息分发。
- `created()`：
  - 监听 `window.matchMedia('(prefers-color-scheme: dark)')` 的变化。
  - 订阅事件总线上的库变更和会话过期事件。
- `beforeDestroy()`：
  - 反注册上述监听，避免重复绑定和内存泄漏。
- `watch`：
  - 监听 `$store.state.persistedState.locale`
  - 监听 `$store.state.persistedState.theme`
  - 两个 watcher 都使用 `immediate: true`，所以组件一创建就会立即同步一次。
- `methods`：
  - `systemThemeChange()`
  - `changeTheme(theme: Theme)`
  - `reloadLibraries()`
  - `logout()`

样式部分只有一句：

- `@import "styles/global.css";`

也就是说，它把全局样式也一并纳入根组件加载链。

## 上下游关系

上游最直接的是 `komga-webui/src/main.ts`。那里把 `App` 作为根组件挂载：

- `new Vue({ router, store, vuetify, i18n, render: h => h(App) }).$mount('#app')`

这说明 `App.vue` 是整套 Vue 应用的根入口视图，不是普通页面组件。

它依赖的下游也很明确：

- `router-view` 下面承载的是 `src/router.ts` 定义的各个页面。
- `this.$store.state.persistedState.locale/theme` 来自 `src/plugins/persisted-state.ts` 和 `src/store.ts` 的持久化模块。
- `this.$eventHub` 在 `main.ts` 里被挂到 `Vue.prototype`，全局都能用。
- `this.$komgaUsers.logout()` 说明它依赖用户插件封装的登出能力。
- `this.$vuetify`、`this.$i18n` 说明它是全局 UI 国际化和主题协调点。

从事件流看，`src/services/komga-sse.service.ts` 会把后端 SSE 转成事件总线事件，`App.vue` 订阅后做统一处理。根据当前片段推断，这种设计的目标是让任意页面无需自己处理“库已变更”或“会话失效”这种跨页状态。

## 运行/调用流程

可以把它理解成一条很短的启动链：

1. `main.ts` 创建 Vue 实例并挂载 `App.vue`。
2. `App.vue` 先渲染外层 `v-app`，再把当前路由页面交给 `router-view`。
3. 创建阶段：
   - 绑定系统深色模式监听。
   - 订阅库变更和会话过期事件。
4. `watch` 立即执行：
   - 如果持久化语言合法，就写入 `$i18n.locale`，同时更新 `$vuetify.rtl`。
   - 如果持久化主题合法，就调用 `changeTheme()`。
5. 用户切换系统主题时：
   - 只有当当前主题是 `Theme.SYSTEM`，才会重新根据系统偏好刷新 Vuetify 深浅色。
6. 后端推送库变化时：
   - 触发 `reloadLibraries()`，执行 `this.$store.dispatch('getLibraries')`。
7. 后端通知会话过期时：
   - 执行 `this.$komgaUsers.logout()`。
   - 跳转到路由名 `login`。

## 小白阅读顺序

1. 先看 `komga-webui/src/App.vue` 的模板，确认它只是根壳和路由出口。
2. 再看 `src/main.ts`，理解 `App` 是怎么被挂载进整个应用的。
3. 然后看 `src/plugins/persisted-state.ts`，理解 `locale`、`theme` 是怎么存、怎么读的。
4. 接着看 `src/types/themes.ts` 和 `src/types/events.ts`，把主题枚举和全局事件名对上。
5. 再回到 `src/router.ts`，看看 `router-view` 里具体会显示哪些页面。
6. 最后顺着 `reloadLibraries()` 和 `logout()` 去找 `getLibraries`、`$komgaUsers.logout()` 的实现，就能把全局刷新和登出流程串起来。

## 常见误区

1. 它不是业务页面。  
   很多人会把 `App.vue` 当成首页，但这里真正承载页面内容的是 `router-view`，业务都在路由页面里。

2. 它不是纯展示组件。  
   虽然模板很短，但它承担了全局主题、语言、事件订阅和会话退出处理，属于应用级协调器。

3. `Theme.SYSTEM` 不等于“永远跟着系统自动变”。  
   只有在 `persistedState.theme === Theme.SYSTEM` 时，`systemThemeChange()` 才会重新计算深色模式。

4. `locale` 不是只改界面文字。  
   这里还会同步 `this.$vuetify.rtl`，所以语言变化会影响布局方向。

5. `reloadLibraries()` 不是局部刷新当前页。  
   它触发的是全局 store 的 `getLibraries`，影响范围可能跨多个页面。

6. 事件总线监听必须清理。  
   `created()` 和 `beforeDestroy()` 是成对出现的，少了卸载就可能重复监听，造成多次触发。
