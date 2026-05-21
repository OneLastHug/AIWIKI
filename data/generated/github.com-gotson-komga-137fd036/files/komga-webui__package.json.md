# 文件：komga-webui/package.json

## 它负责什么

`komga-webui/package.json` 是 Komga 前端子项目 `komga-webui` 的 npm 包清单。它不包含业务逻辑本身，而是定义这个 Vue 前端应用如何被安装、启动、构建、测试和静态检查，以及运行这些流程所需要的依赖集合。

从文件内容看，`komga-webui` 是一个私有包：

```json
{
  "name": "komga-webui",
  "version": "0.1.0",
  "private": true
}
```

`private: true` 表示它不是准备发布到 npm registry 的通用库，而是仓库内部的前端应用模块。它更像是 Komga 服务端配套的 Web UI 工程入口：开发者通过这里安装依赖、启动 Vue CLI dev server、构建生产静态资源，再由后端或部署流程集成这些前端产物。

结合邻近文件可以确认它使用的是 Vue 2 技术栈：`vue` 版本为 `^2.6.14`，路由是 `vue-router` 3.x，状态管理是 `vuex` 3.x，UI 框架是 `vuetify` 2.x，构建和测试由 `@vue/cli-service` 5.x 驱动。

## 关键组成

第一部分是 `scripts`，它定义开发者最常接触的命令：

```json
"scripts": {
  "serve": "vue-cli-service serve --port 8081",
  "build": "vue-cli-service build",
  "test:unit": "vue-cli-service test:unit",
  "lint": "vue-cli-service lint --mode production"
}
```

`serve` 用于本地开发，启动 Vue CLI dev server，并固定端口为 `8081`。这和 `komga-webui/vue.config.js` 中的 `devServer.client.webSocketURL` 对应，后者配置了开发服务器的 WebSocket 地址 `ws://0.0.0.0:8081/ws`。

`build` 调用 `vue-cli-service build`，负责生产构建。`vue.config.js` 中的 `publicPath` 对这个流程很关键：生产环境使用 `./`，开发环境使用 `/`。配置注释说明这样做是为了兼顾开发服务器任意路径加载，以及生产环境在 servlet context path 下部署时 CSS 字体资源路径可用。

`test:unit` 运行 Vue CLI 的单元测试插件。`komga-webui/jest.config.js` 指定了 `@vue/cli-plugin-unit-jest/presets/typescript-and-babel`，说明测试环境同时处理 TypeScript、Babel 和 Vue 组件。

`lint` 运行 Vue CLI 的 ESLint 检查，并指定 `--mode production`。这意味着 lint 时会以生产模式加载环境配置，可能影响 `process.env` 相关判断。

第二部分是 `dependencies`，即运行时依赖。可以按功能分组理解：

`vue`、`vue-router`、`vuex`、`vuex-router-sync`、`vuex-persistedstate` 是应用框架骨架。`src/main.ts` 中通过 `new Vue({ router, store, vuetify, i18n, render })` 挂载应用，并用 `sync(store, router)` 同步路由状态到 Vuex。

`vuetify`、`@mdi/font`、`typeface-roboto` 支撑 Material Design 风格 UI。虽然 `@mdi/font` 和 `typeface-roboto` 放在 `devDependencies`，但它们通常参与构建时打包，最终为 Vuetify 图标和字体服务。`src/plugins/vuetify.ts` 是 Vuetify 的接入点。

`vue-i18n` 和 `vue-cli-plugin-i18n` 支撑国际化。`src/i18n.ts` 使用 `require.context('./locales', true, /...\.json$/i)` 加载 `src/locales` 下的 JSON 语言包，并设置默认语言和 fallback 语言。`vue.config.js` 的 `pluginOptions.i18n` 也声明了 `localeDir: 'locales'`。

`axios`、`qs`、`js-file-downloader` 是网络和下载相关工具。`src/main.ts` 注册了 `httpPlugin`，之后大量 Komga 业务插件都通过 `{http: Vue.prototype.$http}` 注入 HTTP 能力，例如 `komgaBooks`、`komgaLibraries`、`komgaUsers` 等。

`chart.js`、`vue-chartkick` 用于图表。`src/main.ts` 中设置了 `Chartkick.options.colors`，并执行 `Vue.use(Chartkick.use(Chart))`，说明统计、指标或管理页面会复用这套图表能力。

`vuelidate` 负责表单校验，`vue-line-clamp` 和 `vue-read-more-smooth` 负责文本展示效果，`vuedraggable` 支持拖拽排序或列表交互，`screenfull` 支持全屏能力，`marked` 支持 Markdown 渲染，`date-fns`、`filesize`、`lodash`、`language-tags`、`@w0s/isbn-verify` 是常见数据处理工具。

`@d-i-t-a/reader` 是一个特殊依赖，来源是 GitHub：`github:gotson/R2D2BC#fork`。这不是 npm 普通版本号，而是直接引用 gotson 维护的 R2D2BC fork。结合 `vue.config.js` 中专门处理 `readium` 和 `r2d2bc` 的 `.css.resource` 规则，可以推断它与电子书阅读器能力有关，且需要特殊的 CSS 资源打包方式。

第三部分是 `devDependencies`，即构建、类型检查、测试、转译和样式处理所需工具。

`@vue/cli-plugin-babel`、`@vue/cli-plugin-typescript`、`@vue/cli-plugin-router`、`@vue/cli-plugin-vuex`、`@vue/cli-plugin-unit-jest`、`@vue/cli-plugin-eslint` 和 `@vue/cli-service` 共同组成 Vue CLI 工程能力。

`typescript`、`ts-jest`、`@typescript-eslint/*`、`@types/*` 提供 TypeScript 编译、测试类型支持和 lint 支持。`komga-webui/tsconfig.json` 开启了 `strict: true`，并配置路径别名：

```json
"paths": {
  "@/*": ["src/*"]
}
```

所以源码中大量 `@/types/...`、`@/functions/...` 导入都来自 `komga-webui/src`。

`jest`、`babel-jest`、`@vue/test-utils`、`@vue/vue2-jest`、`jest-canvas-mock` 组成单元测试环境。`jest-canvas-mock` 的存在通常说明某些组件或图表库依赖 Canvas API。

`sass`、`sass-loader`、`postcss.config.js` 共同参与样式构建。`vuetify-loader` 则服务于 Vuetify 组件按需或构建优化。

## 上下游关系

从上游看，`package.json` 被 npm 或兼容包管理器读取。开发者进入 `komga-webui` 后执行 `npm install` 时，会根据 `dependencies`、`devDependencies` 和 `package-lock.json` 安装依赖；执行 `npm run serve`、`npm run build`、`npm run test:unit`、`npm run lint` 时，会通过 `scripts` 找到对应的 Vue CLI 命令。

从下游看，`package.json` 影响整个 `komga-webui/src` 的运行方式。

`src/main.ts` 是主要消费者之一。它直接使用了 `lodash`、`vue`、`vue-line-clamp`、`vuelidate`、`vue-chartkick`、`chart.js`、`vuex-router-sync` 等依赖，并注册大量本地插件。可以把 `package.json` 看作“依赖声明层”，`src/main.ts` 看作“运行装配层”。

`src/router.ts` 使用 `vue-router` 和 `qs`。其中 `qs.parse`、`qs.stringify` 被配置为路由 query 的解析和序列化逻辑，说明 query 参数可能需要支持复杂对象，而不是只用浏览器默认的简单字符串解析。

`src/store.ts` 使用 `vuex`、`vuex-persistedstate` 和 `lodash/isEmpty`。它创建全局 Vuex Store，存放对话框状态、编辑对象、公告、版本发布信息等全局状态。`vuex-persistedstate` 被配置为只持久化 `persistedState` 路径，具体模块来自 `src/plugins/persisted-state`。

`src/i18n.ts` 使用 `vue-i18n`。它加载本地语言包，并额外配置了波兰语 `pl` 的复数规则。这说明国际化不是装饰性依赖，而是应用运行时的重要组成。

`komga-webui/vue.config.js` 是 `package.json` 的构建配置下游。`vue-cli-service serve/build/test/lint` 在运行时会读取这个配置。这里的 `publicPath`、`pluginOptions.i18n`、`devServer` 和 `configureWebpack` 会直接改变 dev server、国际化插件和 Webpack 资源打包行为。

从更大的仓库关系看，根据当前片段推断，`komga-webui` 是 Komga 后端项目中的前端子工程。依据是 `vue.config.js` 注释提到 servlet context path，而 Komga 本身通常是服务端应用托管 Web UI 的形态。生产构建后的静态资源很可能被后端打包或部署流程消费，但本次没有继续查看根目录构建脚本，所以这里应视为基于当前片段的推断。

## 运行/调用流程

开发模式下，典型流程是：

1. 包管理器读取 `komga-webui/package.json` 和 `komga-webui/package-lock.json`，安装 Vue、Vue CLI、Vuetify、Axios、测试工具等依赖。
2. 执行 `npm run serve`。
3. npm 找到 `scripts.serve`，实际运行 `vue-cli-service serve --port 8081`。
4. Vue CLI 读取 `vue.config.js`，设置 `publicPath: '/'`、dev server WebSocket 地址和自定义 Webpack 规则。
5. Webpack 以 `src/main.ts` 为前端入口，编译 TypeScript、Vue 单文件组件、样式和静态资源。
6. `src/main.ts` 注册全局插件：HTTP、日志、业务 API 插件、Vuetify、Vuelidate、Chartkick、line clamp 等。
7. `sync(store, router)` 把路由状态同步到 Vuex。
8. `new Vue({...}).$mount('#app')` 将 `App.vue` 挂载到页面上的 `#app` 节点。

生产构建下，流程类似，但执行的是 `npm run build`，实际命令是 `vue-cli-service build`。此时 `vue.config.js` 设置 `publicPath: './'`，并对 `readium`、`r2d2bc` 的 `.css.resource` 文件使用 `asset/resource` 输出到 `css/[hash].css[query]`。这点对阅读器相关资源尤其重要，因为这些 CSS 不能被普通 CSS loader 改写，而是需要作为独立资源保留。

测试流程是 `npm run test:unit`。Vue CLI 会读取 `jest.config.js`，使用 `typescript-and-babel` preset 来处理 `.ts`、`.vue` 等文件。因为项目依赖 Chart.js 或 Canvas 相关能力，所以 `jest-canvas-mock` 也被列入开发依赖，为测试环境补齐浏览器 Canvas API。

lint 流程是 `npm run lint`。它通过 Vue CLI 调用 ESLint，并结合 `.eslintrc.js`、`@vue/eslint-config-standard`、`@vue/eslint-config-typescript`、`eslint-plugin-vue` 等依赖检查代码风格和潜在问题。

## 小白阅读顺序

建议先读 `komga-webui/package.json`，不要急着看所有依赖源码。先把四个脚本记住：`serve` 是本地开发，`build` 是生产构建，`test:unit` 是单元测试，`lint` 是代码检查。

第二步读 `komga-webui/vue.config.js`。这个文件解释了为什么开发环境和生产环境的资源路径不同，也解释了阅读器相关 CSS 为什么要走特殊 Webpack 规则。理解它之后，再看 `package.json` 里的 `@d-i-t-a/reader` 会更容易。

第三步读 `komga-webui/src/main.ts`。这是把 `package.json` 中依赖真正接入应用的地方。看到 `Vue.use(...)` 时，可以回头在 `package.json` 找对应包：例如 `Vuelidate` 对应 `vuelidate`，`Chartkick` 对应 `vue-chartkick` 和 `chart.js`，`sync` 对应 `vuex-router-sync`。

第四步读 `komga-webui/src/router.ts`。它会让你理解 `vue-router`、`qs` 的作用，以及 Komga Web UI 大概有哪些页面：dashboard、settings、libraries、collections、readlists、series 等。

第五步读 `komga-webui/src/store.ts`。它能帮助你理解 `vuex` 在这个项目中的定位：既保存全局 UI 状态，也配合业务插件保存用户、库、公告、版本等信息。

第六步读 `komga-webui/src/i18n.ts` 和 `src/locales`。这样可以理解 `vue-i18n` 和 `vue-cli-plugin-i18n` 为什么同时存在：前者是运行时国际化库，后者是 Vue CLI 的国际化工程插件配置。

最后再看 `komga-webui/tsconfig.json`、`jest.config.js`、`.eslintrc.js`。这些文件不是业务入口，但会解释为什么源码可以使用 `@/` 别名、为什么测试可以识别 Vue + TypeScript、为什么 lint 规则会约束写法。

## 常见误区

第一个误区是把 `package.json` 当成业务代码。它本身不实现页面、接口请求或阅读器逻辑，只声明“项目需要什么”和“命令怎么跑”。真正的装配逻辑在 `src/main.ts`，具体页面在 `src/views`、`src/components`，业务 API 能力多半在 `src/plugins` 和 `src/types` 周边。

第二个误区是认为 `dependencies` 一定只在浏览器运行时加载，`devDependencies` 一定不会进最终产物。实际前端项目中，某些放在 `devDependencies` 的资源型包或 loader 可能参与构建过程，例如 `@mdi/font`、`typeface-roboto`、`vuetify-loader`。是否进入最终 bundle 取决于源码 import 和构建配置，而不只取决于它在 `dependencies` 还是 `devDependencies`。

第三个误区是忽略 Vue 2 生态版本。这个项目使用 `vue@2.6`、`vue-router@3`、`vuex@3`、`vuetify@2`。阅读资料时不要直接套用 Vue 3、Vue Router 4、Pinia 或 Vuetify 3 的写法，否则很多 API 会对不上，例如 `new Vue({...}).$mount('#app')`、`Vue.use(...)`、`new Router(...)` 都是 Vue 2 时代的典型模式。

第四个误区是把 `@d-i-t-a/reader` 当作普通 npm 依赖。它来自 GitHub fork：`github:gotson/R2D2BC#fork`。这意味着安装稳定性、锁定版本和构建行为都更依赖 `package-lock.json`。同时 `vue.config.js` 对 `readium`、`r2d2bc` CSS 的特殊处理也说明它不是普通 UI 组件库，而是带有特殊静态资源要求的阅读器相关依赖。

第五个误区是忽略 `publicPath` 的生产差异。开发时是 `/`，生产时是 `./`。如果排查静态资源、字体、CSS、图片路径问题，必须先确认当前是 `serve` 还是 `build` 场景。尤其当 Komga 被部署在非根路径 servlet context path 下时，生产资源路径配置会影响页面能否正确加载。

第六个误区是以为 `vue-i18n` 配置只在 `package.json`。实际国际化链路分三层：`package.json` 声明 `vue-i18n` 和 `vue-cli-plugin-i18n`，`vue.config.js` 声明插件选项和语言目录，`src/i18n.ts` 在运行时加载 JSON 语言包并创建 `VueI18n` 实例。

第七个误区是只看 `scripts` 不看它们背后的 Vue CLI 配置。`serve`、`build`、`test:unit`、`lint` 都只是入口命令，真正影响行为的还有 `vue.config.js`、`tsconfig.json`、`jest.config.js`、`.eslintrc.js`、`babel.config.js` 等邻近文件。理解 `package.json` 时，应把它看成这些配置文件的总开关。
