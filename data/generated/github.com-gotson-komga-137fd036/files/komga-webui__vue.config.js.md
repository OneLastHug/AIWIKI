# 文件：komga-webui/vue.config.js

## 它负责什么

`komga-webui/vue.config.js` 是 `komga-webui` 前端项目的 Vue CLI 全局配置文件。它不会直接参与业务运行逻辑，而是在执行 `vue-cli-service serve`、`vue-cli-service build`、`vue-cli-service test:unit`、`vue-cli-service lint` 等命令时被 Vue CLI 读取，用来影响开发服务器、生产构建产物、国际化插件配置，以及 webpack 对特殊资源文件的处理方式。

这个项目是 Vue 2 + TypeScript + Vuetify 的前端应用，入口在 `komga-webui/src/main.ts`。`vue.config.js` 站在更上游的位置：它决定构建工具如何把 `src` 下的 Vue、TypeScript、CSS、图片、字体、阅读器样式资源等内容打包成可部署的静态前端资源。

文件核心职责可以概括为四类：

1. 控制前端资源的基础路径 `publicPath`。
2. 给 `vue-cli-plugin-i18n` 提供默认国际化配置。
3. 配置本地开发服务器 `devServer`，尤其是 WebSocket 地址。
4. 通过 `configureWebpack` 添加一条自定义 webpack rule，专门处理 Readium / R2D2BC 阅读器所需的 `.css.resource` 文件。

## 关键组成

### `module.exports`

文件使用 CommonJS 形式导出配置：

```js
module.exports = {
  ...
}
```

这是 Vue CLI 期望的配置格式。Vue CLI 启动时会自动读取项目根目录下的 `vue.config.js`，并把这里的选项合并到内部 webpack 和 dev server 配置中。

这里没有 `import` 或 `require`，说明它本身不依赖其他本地模块；它只是声明式地输出配置对象。

### `publicPath`

```js
publicPath: process.env.NODE_ENV === 'production' ? './' : '/',
```

这是整个文件里最容易影响部署行为的一项。

`publicPath` 决定构建后资源引用的基础路径。开发环境使用 `/`，生产环境使用 `./`。

从注释可以看出作者做过权衡：

```js
// with './' the dev server cannot load any arbitrary path
// with '/' the prod build generates some url(/fonts…) calls in the css chunks, which doesn't work with a servlet context path
```

意思是：

开发环境如果使用 `./`，dev server 不能正确加载任意路由路径。比如 SPA 应用里访问 `/library/xxx` 这类前端路由时，资源路径可能会被错误地按相对路径解析。

生产环境如果使用 `/`，构建出的 CSS chunk 里会出现类似 `url(/fonts...)` 的绝对路径。Komga 作为后端应用部署时可能带有 servlet context path，也就是不一定部署在站点根路径 `/`，而可能部署在 `/komga` 之类路径下。此时 `/fonts...` 会指向服务器根目录，导致字体等资源加载失败。

所以这里的策略是：

- 开发：`publicPath = '/'`，方便 Vue dev server 支持任意前端路由。
- 生产：`publicPath = './'`，让静态资源使用相对路径，适配非根路径部署。

这和 `komga-webui/src/main.ts` 中的 `import './public-path'` 也有关。根据当前片段推断，项目还通过 `public-path` 动态调整运行时资源基础路径，以适配 Komga 后端部署环境。

### `pluginOptions.i18n`

```js
pluginOptions: {
  i18n: {
    locale: 'en',
    fallbackLocale: 'en',
    localeDir: 'locales',
    enableInSFC: false,
  },
},
```

这段配置是给 `vue-cli-plugin-i18n` 使用的。`package.json` 中可以看到相关依赖：

- `vue-i18n`
- `vue-cli-plugin-i18n`

配置含义：

- `locale: 'en'`：默认语言是英文。
- `fallbackLocale: 'en'`：找不到目标语言翻译时回退到英文。
- `localeDir: 'locales'`：语言文件目录名是 `locales`。
- `enableInSFC: false`：不启用 Vue 单文件组件内的 `<i18n>` 块。

实际运行时的 i18n 实例定义在 `komga-webui/src/i18n.ts`：

```ts
export default new VueI18n({
  locale: process.env.VUE_APP_I18N_LOCALE || 'en',
  fallbackLocale: process.env.VUE_APP_I18N_FALLBACK_LOCALE || 'en',
  messages: loadLocaleMessages(),
  ...
})
```

这里有一个细节：`vue.config.js` 给插件声明默认配置，而 `src/i18n.ts` 才是应用运行时真正创建 `VueI18n` 实例的地方。`src/i18n.ts` 会从 `./locales` 目录加载 JSON 语言包，并挂到 Vue 根实例上。

`src/main.ts` 中：

```ts
import i18n from './i18n'

new Vue({
  router,
  store,
  vuetify,
  i18n,
  render: h => h(App),
}).$mount('#app')
```

说明所有组件中的 `$i18n`、`$t`、`$tc` 等能力最终来自 `src/i18n.ts` 创建的实例，而不是直接来自 `vue.config.js`。

### `devServer`

```js
devServer: {
  allowedHosts: 'all',
  client: {
    webSocketURL: 'ws://0.0.0.0:8081/ws',
  },
},
```

这段只影响开发服务器，也就是 `npm run serve` 时的行为。`package.json` 中对应脚本是：

```json
"serve": "vue-cli-service serve --port 8081"
```

关键点有两个。

`allowedHosts: 'all'` 表示开发服务器允许所有 Host 访问。这通常用于容器、远程开发环境、局域网调试、反向代理等场景。否则 webpack dev server 可能因为 Host 校验拒绝请求。

`client.webSocketURL: 'ws://0.0.0.0:8081/ws'` 指定浏览器端用于热更新 / dev server 通信的 WebSocket 地址。Vue CLI 5 底层使用 webpack-dev-server，新版 dev server 的客户端热更新连接会受这个配置影响。

结合 `serve --port 8081` 看，这里强制 WebSocket 连接到 `8081` 端口，与开发服务器端口保持一致。

需要注意：`0.0.0.0` 在服务端表示监听所有网卡地址，但作为浏览器要连接的目标地址时，在某些环境下可能不如 `localhost` 或实际 IP 直观。根据当前片段推断，这个配置是为了配合容器化或远程环境，而不是普通本机浏览器访问的最小配置。

### `configureWebpack.module.rules`

```js
configureWebpack: {
  module: {
    rules: [
      {
        test: [
          /readium\/.*\.css.resource$/,
          /r2d2bc\/.*\.css.resource$/,
        ],
        type: 'asset/resource',
        generator: {
          filename: 'css/[hash].css[query]',
        },
      },
    ],
  },
},
```

这是文件中最项目定制化的一段。它给 webpack 增加了一条资源处理规则，专门匹配：

- `readium/...*.css.resource`
- `r2d2bc/...*.css.resource`

匹配到的文件不会按普通 CSS 方式解析、压缩、注入页面，而是作为 `asset/resource` 输出成独立资源文件。

输出路径格式是：

```js
css/[hash].css[query]
```

也就是说，最终构建产物中这类文件会被放到 `css/` 目录下，文件名使用 hash，并保留 query。

注释写得很清楚：

```js
// custom rule for readium and r2d2bc css that needs to be made available, but untouched
```

这些 CSS 需要“可被访问”，但不能被 webpack 当作普通 CSS 加工。

调用方在 `komga-webui/src/views/EpubReader.vue` 中可以看到，例如：

```ts
new URL('../styles/readium/ReadiumCSS-before.css.resource', import.meta.url).toString()
new URL('../styles/readium/ReadiumCSS-default.css.resource', import.meta.url).toString()
new URL('../styles/readium/ReadiumCSS-after.css.resource', import.meta.url).toString()
new URL('../styles/r2d2bc/popup.css.resource', import.meta.url).toString()
new URL('../styles/r2d2bc/popover.css.resource', import.meta.url).toString()
new URL('../styles/r2d2bc/style.css.resource', import.meta.url).toString()
```

这说明 EPUB 阅读器运行时需要拿到这些 CSS 文件的 URL，再交给阅读器加载。它们不是普通页面样式，而是阅读器 iframe / publication 内容环境中需要引用的外部样式资源。

`package.json` 中还有：

```json
"@d-i-t-a/reader": "github:gotson/R2D2BC#fork"
```

而 `komga-webui/src/views/EpubReader.vue` 引入了：

```ts
import D2Reader, {Locator} from '@d-i-t-a/reader'
```

所以这条 webpack rule 的直接业务背景是 EPUB / Readium 阅读体验。

## 上下游关系

上游主要是构建和开发工具链：

- `komga-webui/package.json` 中的 `vue-cli-service` 命令会读取 `vue.config.js`。
- `@vue/cli-service` 负责把这份配置转换为 webpack、webpack-dev-server、插件配置。
- `vue-cli-plugin-i18n` 读取 `pluginOptions.i18n`。
- webpack 读取 `configureWebpack` 并合并自定义资源规则。
- `NODE_ENV` 决定 `publicPath` 使用生产还是开发策略。

下游主要是前端构建产物和运行时资源加载：

- `komga-webui/src/main.ts` 是应用入口，最终挂载 Vue 根实例。
- `komga-webui/src/i18n.ts` 创建运行时 i18n 实例，并读取 `src/locales` 下的 JSON 翻译文件。
- `komga-webui/src/App.vue`、各 `views`、`components`、`types` 文件大量使用 `$i18n`、`$t`、`$tc`、`i18n.t()`。
- `komga-webui/src/views/EpubReader.vue` 使用 `new URL(...css.resource, import.meta.url)` 获取阅读器 CSS 资源 URL。
- `komga-webui/src/styles/readium/*.css.resource` 和 `komga-webui/src/styles/r2d2bc/*.css.resource` 依赖这里的 webpack rule 才能以“原样资源文件”的方式输出。
- 生产部署环境依赖 `publicPath: './'` 来避免 servlet context path 下资源路径错误。

可以把关系理解成：

`package.json scripts` → `vue-cli-service` → `vue.config.js` → webpack / dev server / i18n plugin → `src/main.ts`、`src/i18n.ts`、`src/views/EpubReader.vue` 等运行时代码。

## 运行/调用流程

### 开发环境流程

执行：

```bash
npm run serve
```

实际运行：

```bash
vue-cli-service serve --port 8081
```

流程如下：

1. Vue CLI 启动开发服务器。
2. 自动读取 `komga-webui/vue.config.js`。
3. 因为 `NODE_ENV` 不是 `production`，`publicPath` 取 `/`。
4. dev server 使用端口 `8081`。
5. `devServer.allowedHosts = 'all'` 放开 Host 校验。
6. 浏览器端 dev client 使用 `ws://0.0.0.0:8081/ws` 连接开发服务器 WebSocket。
7. webpack 按配置处理源码。
8. 如果遇到 `readium/...*.css.resource` 或 `r2d2bc/...*.css.resource`，按 `asset/resource` 输出为可访问的 CSS 文件资源。
9. 浏览器加载 Vue 应用，`src/main.ts` 创建 Vue 实例，挂载 router、store、vuetify、i18n。

### 生产构建流程

执行：

```bash
npm run build
```

实际运行：

```bash
vue-cli-service build
```

流程如下：

1. Vue CLI 启动生产构建。
2. 自动读取 `vue.config.js`。
3. 因为 `NODE_ENV === 'production'`，`publicPath` 取 `./`。
4. webpack 打包 Vue、TypeScript、CSS、字体、图片等资源。
5. 普通 CSS 由 Vue CLI 默认 CSS 规则处理。
6. `.css.resource` 文件命中自定义 rule，被当作静态资源输出到 `css/[hash].css[query]`。
7. 构建后的资源引用使用相对路径，适配 Komga 后端可能存在的 servlet context path。
8. 生产环境访问 EPUB 阅读器时，`EpubReader.vue` 中通过 `new URL(..., import.meta.url)` 生成的 CSS URL 指向构建产物中的独立 CSS 资源。

### i18n 初始化流程

i18n 相关流程可以拆成构建期和运行期。

构建期：

1. `vue.config.js` 的 `pluginOptions.i18n` 告诉 `vue-cli-plugin-i18n` 默认语言、回退语言、语言目录等信息。
2. 插件据此为 Vue CLI 项目提供国际化相关支持。

运行期：

1. `src/main.ts` 引入 `src/i18n.ts`。
2. `src/i18n.ts` 执行 `Vue.use(VueI18n)`。
3. `loadLocaleMessages()` 使用 `require.context('./locales', true, /[A-Za-z0-9-_,\s]+\.json$/i)` 扫描语言 JSON。
4. 创建 `new VueI18n(...)`。
5. 根 Vue 实例挂载 `i18n`。
6. 组件和普通 TS 文件通过 `$i18n` 或直接导入 `i18n` 获取翻译能力。

## 小白阅读顺序

1. 先读 `komga-webui/package.json` 的 `scripts`，理解 `serve`、`build` 都是通过 `vue-cli-service` 启动的。这样才能明白为什么 `vue.config.js` 会被自动读取，而不是被业务代码手动 import。

2. 再读 `komga-webui/vue.config.js`，重点看四块：`publicPath`、`pluginOptions.i18n`、`devServer`、`configureWebpack`。这个文件短，但每一块都影响一个不同层面。

3. 接着读 `komga-webui/src/main.ts`，看 Vue 应用真正如何启动，以及 `i18n`、`router`、`store`、`vuetify` 如何挂到根实例上。

4. 然后读 `komga-webui/src/i18n.ts`，理解语言包是怎么从 `src/locales` 加载的。注意这里的 `locale` 和 `fallbackLocale` 可以从 `VUE_APP_I18N_LOCALE`、`VUE_APP_I18N_FALLBACK_LOCALE` 环境变量读取。

5. 如果想理解 `.css.resource` 的意义，再读 `komga-webui/src/views/EpubReader.vue` 中引用 `../styles/readium/*.css.resource` 和 `../styles/r2d2bc/*.css.resource` 的部分。这里能看到配置文件里的 webpack rule 为什么存在。

6. 最后抽样看 `komga-webui/src/styles/readium/ReadiumCSS-before.css.resource`、`komga-webui/src/styles/readium/ReadiumCSS-default.css.resource`、`komga-webui/src/styles/readium/ReadiumCSS-after.css.resource`、`komga-webui/src/styles/r2d2bc/style.css.resource`，理解这些文件是阅读器运行时资源，而不是普通页面样式。

## 常见误区

### 误区一：以为 `vue.config.js` 是业务入口

`vue.config.js` 不是前端应用入口。业务入口是 `komga-webui/src/main.ts`。`vue.config.js` 是构建工具入口，服务于 Vue CLI、webpack 和开发服务器。

### 误区二：以为 `pluginOptions.i18n` 就创建了 i18n 实例

真正的 `VueI18n` 实例在 `komga-webui/src/i18n.ts` 创建。`vue.config.js` 中的 `pluginOptions.i18n` 是插件配置，不是运行时实例。

换句话说，组件里使用的 `$i18n` 来自 `src/main.ts` 挂载的 `i18n`，而不是直接来自 `vue.config.js`。

### 误区三：随意把生产 `publicPath` 改成 `/`

这很可能破坏非根路径部署。注释已经说明，生产环境使用 `/` 会让 CSS chunk 里生成类似 `url(/fonts...)` 的绝对路径。如果 Komga 部署在 servlet context path 下，例如 `/komga`，这些资源可能会从错误位置加载。

这里生产环境使用 `./` 是有部署背景的，不是随手写法。

### 误区四：认为 `.css.resource` 是普通 CSS

`.css.resource` 文件被刻意避开普通 CSS 处理流程。它们需要“原样”输出为可访问资源，供 EPUB / Readium 阅读器在运行时加载。

如果把它们改成普通 `.css` 并让 webpack 默认处理，可能会被压缩、合并、注入主页面，导致阅读器无法通过 URL 独立引用这些样式。

### 误区五：忽略 `devServer.client.webSocketURL`

开发环境页面热更新、错误覆盖层等功能依赖 dev server client 和服务器之间的 WebSocket 通信。这里配置为 `ws://0.0.0.0:8081/ws`，明显是为了某种远程或容器化开发环境做适配。

如果本地访问热更新异常，排查时应该把这个配置和 `serve --port 8081`、浏览器实际访问地址一起看，而不是只看 Vue 业务代码。

### 误区六：把 `configureWebpack` 当成完整 webpack 配置替换

这里的 `configureWebpack` 是“合并配置”，不是完全替换 Vue CLI 内部 webpack 配置。项目仍然依赖 Vue CLI 默认规则来处理 `.vue`、`.ts`、普通 CSS、Sass、字体、图片等资源。当前文件只是额外补了一条 `.css.resource` 的特殊规则。
