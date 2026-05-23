# 文件：komga-webui/public/index.html

## 它负责什么

`komga-webui/public/index.html` 是 Komga Web 前端的 HTML 壳文件，也就是 Vue 单页应用的浏览器入口模板。

它本身不实现业务页面，也不直接渲染书库、漫画、用户、阅读器等功能；它负责在浏览器里提供一个最小的页面骨架：

- 声明 HTML 文档基础信息，例如字符集、视口、兼容模式。
- 设置 Komga 的页面标题和各类图标。
- 挂载 PWA 相关资源，例如 `manifest.json`、移动端图标、Windows tile 信息。
- 定义全局变量 `window.resourceBaseUrl`，让前端代码知道 Komga 当前部署在哪个 URL 前缀下。
- 提供 Vue 应用挂载点 `<div id="app"></div>`。
- 在用户禁用 JavaScript 时显示 `<noscript>` 提示。
- 作为 Vue CLI 构建模板，最终由构建流程自动注入打包后的 JS/CSS 文件。

可以把它理解成：Komga Web UI 的“空舞台”。真正的应用逻辑从 `komga-webui/src/main.ts` 开始挂载到这个舞台上。

## 关键组成

文件开头是标准 HTML5 声明：

```html
<!DOCTYPE html>
<html lang="en">
```

`lang="en"` 表示默认文档语言为英文。注意这不代表 Komga 只支持英文界面；实际国际化由前端的 `vue-i18n` 体系处理，入口在 `komga-webui/src/main.ts` 引入的 `./i18n`。

`<head>` 里主要有几类内容。

第一类是基础浏览器元信息：

```html
<meta charset="utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
```

这些配置保证页面使用 UTF-8 编码，在旧版 IE 中尽量使用最新渲染模式，并让移动端按设备宽度渲染。

第二类是移动 Web App 能力声明：

```html
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
```

它们用于告诉移动浏览器：这个站点可以像 Web App 一样被添加到主屏幕并以更接近 App 的方式打开。

第三类是标题和图标：

```html
<title>Komga</title>
<link rel="icon" href="/favicon.ico">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
```

这些资源都位于 `komga-webui/public` 目录下。同目录可以看到：

- `komga-webui/public/favicon.ico`
- `komga-webui/public/favicon-32x32.png`
- `komga-webui/public/favicon-16x16.png`
- `komga-webui/public/apple-touch-icon.png`
- `komga-webui/public/android-chrome-192x192.png`
- `komga-webui/public/android-chrome-512x512.png`
- `komga-webui/public/mstile-144x144.png`
- `komga-webui/public/manifest.json`

第四类是 PWA / Windows tile 配置：

```html
<meta name="msapplication-TileColor" content="#08397f">
<meta name="msapplication-TileImage" content="/mstile-144x144.png">
<link rel="manifest" href="/manifest.json">
```

`manifest.json` 描述 Web App 的名称、图标、启动方式等信息。`mstile-144x144.png` 和 `msapplication-*` 主要服务于 Windows / Microsoft 生态里的磁贴显示。

最特殊的一段是这个内联脚本：

```html
<script th:inline="javascript">
    /*<![CDATA[*/
    window.resourceBaseUrl = /*[(<%="$"%>{"'" + baseUrl + "'"})]*/ '/'
    /*]]>*/
</script>
```

这里有几个层次需要拆开看。

`th:inline="javascript"` 说明这个 HTML 会被 Thymeleaf 当作 JavaScript 内联模板处理。Komga 后端是 Kotlin/Spring 应用，相关入口可以从 `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt` 的搜索结果看出：它会准备一个 `baseUrl`，值来自 `servletContext.contextPath` 加 `/`，然后放入 model。

`window.resourceBaseUrl` 是暴露给浏览器端 JavaScript 的全局变量。它的含义是：当前 Komga Web 应用的资源基础路径。

默认值是 `'/'`。如果没有经过后端模板处理，例如前端开发服务器直接使用这个 HTML，表达式后面的 fallback 会让它退回根路径：

```js
window.resourceBaseUrl = '/'
```

如果经过后端 Thymeleaf 渲染，`baseUrl` 会被注入进去。这样 Komga 部署在非根路径时，例如某个 servlet context path 下，前端仍然能计算正确的静态资源和 API 基础路径。

`<body>` 里只有两个关键部分：

```html
<noscript>
    <strong>We're sorry but Komga doesn't work properly without JavaScript enabled. Please enable it to
        continue.</strong>
</noscript>
<div id="app"></div>
```

`<noscript>` 是兜底提示。Komga Web UI 是 Vue 单页应用，没有 JavaScript 时无法正常运行。

`<div id="app"></div>` 是 Vue 的挂载点。`komga-webui/src/main.ts` 末尾有：

```ts
new Vue({
  router,
  store,
  vuetify,
  i18n,
  render: h => h(App),
}).$mount('#app')
```

这说明真正的根组件 `App.vue` 会被渲染并挂载到 `#app` 这个 DOM 节点里。

最后一行注释：

```html
<!-- built files will be auto injected -->
```

这是 Vue CLI 项目的典型模板说明。构建时，`vue-cli-service build` 会基于这个 `public/index.html` 生成最终 HTML，并自动注入打包后的 JS、CSS 资源引用。开发时，`vue-cli-service serve` 也会用它作为页面模板。

## 上下游关系

上游主要有三类。

第一类是 Vue CLI 构建系统。

`komga-webui/package.json` 中定义了：

```json
"serve": "vue-cli-service serve --port 8081",
"build": "vue-cli-service build"
```

这说明 `komga-webui/public/index.html` 会被 Vue CLI 当成 HTML 模板使用。构建时，前端源代码、依赖、样式会被打包，并把生成的资源插入这个模板，形成浏览器最终加载的页面。

第二类是 `komga-webui/vue.config.js`。

这个配置里有一段很关键：

```js
publicPath: process.env.NODE_ENV === 'production' ? './' : '/',
```

它说明开发环境使用 `/`，生产构建使用 `./`。注释里解释了原因：开发服务器需要能加载任意路径；生产构建如果直接用 `/`，在 servlet context path 下可能导致 CSS 中的字体等资源路径错误。

这和 `index.html` 里的 `window.resourceBaseUrl` 是配套关系：HTML 模板负责把后端 context path 暴露给浏览器，前端运行时代码再利用它修正资源路径。

第三类是 Spring MVC / Thymeleaf 后端入口。

搜索结果显示 `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt` 中有：

```kotlin
private val baseUrl: String = "${servletContext.contextPath}/"
model.addAttribute("baseUrl", baseUrl)
```

根据当前片段推断，后端在返回 Web UI 首页时，会把 `baseUrl` 注入到这个 HTML 模板中，使 `window.resourceBaseUrl` 成为实际部署路径。

下游主要有四类。

第一类是 Vue 应用入口 `komga-webui/src/main.ts`。

它导入了大量插件和核心模块：

- `App`：根组件。
- `router`：前端路由。
- `store`：Vuex 状态管理。
- `i18n`：国际化。
- `vuetify`：UI 框架。
- 多个 Komga API 插件，例如 `komgaBooks`、`komgaSeries`、`komgaLibraries`、`komgaUsers` 等。

最后通过 `$mount('#app')` 接管 `index.html` 中的 `<div id="app"></div>`。

第二类是 `komga-webui/src/public-path.js`。

搜索结果显示它使用了 `window.resourceBaseUrl`：

```js
__webpack_public_path__ = process.env.NODE_ENV === 'production' ? window.location.origin + window.resourceBaseUrl : '/'
```

这说明生产环境下，Webpack 动态加载资源时会使用：

```text
window.location.origin + window.resourceBaseUrl
```

例如应用部署在：

```text
[URL已移除]
```

那么资源基础路径就应该接近：

```text
[URL已移除]
```

这能避免 JS chunk、CSS、字体等资源在非根路径部署时加载失败。

第三类是 `komga-webui/src/functions/urls.ts`。

搜索结果显示它也使用了 `window.resourceBaseUrl`，并派生出类似 `base`、`baseNoSlash` 这样的 URL 形式。根据当前片段推断，这个文件负责统一生成前端请求或资源访问所需的基础 URL，避免各处手写路径。

第四类是浏览器和 PWA 环境。

`manifest.json`、favicon、apple touch icon、Windows tile 图标都由浏览器或操作系统读取。它们不是 Vue 运行时直接调用的业务代码，但会影响标签页图标、添加到主屏幕后的图标、PWA 外观等。

## 运行/调用流程

从开发环境看，流程大致是：

1. 开发者在 `komga-webui` 下执行 `npm run serve` 或等价命令。
2. `vue-cli-service serve --port 8081` 启动开发服务器。
3. Vue CLI 使用 `komga-webui/public/index.html` 作为页面模板。
4. 浏览器打开开发服务器地址。
5. `window.resourceBaseUrl` 没有经过后端 Thymeleaf 注入，因此使用默认值 `'/'`。
6. 构建工具注入开发环境 JS。
7. `komga-webui/src/main.ts` 执行。
8. Vue 创建根实例，并挂载到 `#app`。
9. 用户看到完整 Komga Web UI。

从生产环境看，流程更接近这样：

1. 前端执行 `komga-webui/package.json` 中的 `build` 脚本。
2. Vue CLI 基于 `public/index.html` 生成生产 HTML，并注入打包后的 JS/CSS。
3. 生产构建产物被集成进 Komga 后端应用。
4. 用户访问 Komga Web 页面。
5. Spring MVC 的 `IndexController` 返回首页模板。
6. 后端把 `baseUrl` 放入 Thymeleaf model。
7. Thymeleaf 处理 `th:inline="javascript"`，把 `baseUrl` 写入 `window.resourceBaseUrl`。
8. 浏览器加载 HTML、图标、manifest、JS/CSS。
9. 前端代码执行 `komga-webui/src/public-path.js`，设置 `__webpack_public_path__`。
10. `komga-webui/src/main.ts` 初始化 Vue、路由、状态、插件、Vuetify、i18n。
11. Vue 根实例挂载到 `#app`。
12. 后续页面切换由 Vue Router 接管，数据请求由各个 Komga 插件和 HTTP 插件完成。

这里最重要的链路是：

```text
IndexController 注入 baseUrl
-> index.html 写入 window.resourceBaseUrl
-> public-path.js 设置 Webpack public path
-> main.ts 挂载 Vue 到 #app
```

如果只看 `index.html`，容易以为它只是普通静态页面；但结合上下文可以看到，它其实承担了“后端部署路径”和“前端运行时资源路径”之间的桥接职责。

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就陷入 Vue 组件细节。

第一步，先读 `komga-webui/public/index.html`。

重点看三件事：

- `<div id="app"></div>`：Vue 要挂载的位置。
- `window.resourceBaseUrl`：后端传给前端的部署路径。
- `manifest.json` 和图标：PWA / 浏览器外观相关资源。

第二步，读 `komga-webui/package.json`。

重点看 `scripts`：

```json
"serve": "vue-cli-service serve --port 8081",
"build": "vue-cli-service build"
```

它告诉你这个 Web UI 是 Vue CLI 项目，`public/index.html` 是构建模板，不是手写完整页面。

第三步，读 `komga-webui/vue.config.js`。

重点看 `publicPath`：

```js
publicPath: process.env.NODE_ENV === 'production' ? './' : '/',
```

这里能理解为什么 Komga 对资源路径特别谨慎：它可能部署在 servlet context path 下，而不是永远部署在域名根路径。

第四步，读 `komga-webui/src/public-path.js`。

这个文件和 `index.html` 中的 `window.resourceBaseUrl` 是直接配套的。它解释了为什么 HTML 里要提前写一个全局变量。

第五步，读 `komga-webui/src/main.ts`。

这是前端真正启动的位置。重点看：

- `import './public-path'`
- `import App from './App.vue'`
- `import router from './router'`
- `import store from './store'`
- `new Vue(...).$mount('#app')`

读到这里，就能把 HTML 壳、运行时 public path、Vue 根实例串起来。

第六步，再看后端的 `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt`。

重点理解 `baseUrl` 从哪里来，以及为什么要放到 model 里。这样就能明白 `th:inline="javascript"` 不是多余写法，而是生产部署路径适配的一部分。

## 常见误区

第一个误区：把 `index.html` 当成普通静态 HTML 页面。

它不是完整页面，只是 Vue 单页应用的模板。页面主体不是写在这个文件里，而是由 `komga-webui/src/main.ts` 启动后渲染 `App.vue` 以及后续路由组件。

第二个误区：以为 `<div id="app"></div>` 里面应该有内容。

在源码模板里它本来就是空的。Vue 运行后才会把根组件渲染进去。如果浏览器中看到它一直为空，通常说明 JS 没有加载、执行报错，或者前端构建产物没有正确注入。

第三个误区：忽略 `window.resourceBaseUrl`。

这行看起来像小配置，但对生产环境很关键。Komga 可能部署在 `/`，也可能部署在类似 `/komga/` 的 context path 下。资源路径、动态 chunk、API URL 如果没有正确处理，很容易在非根路径部署时失败。

第四个误区：以为 `href="/manifest.json"`、`href="/favicon.ico"` 一定在所有部署路径下都没问题。

这些是浏览器读取的静态资源路径。仓库里同时还有后端 Web MVC 配置和前端 public path 逻辑来处理资源访问。根据当前片段推断，Komga 的后端会对这些公共资源做映射或放行；但只看 `index.html` 不能完整判断所有部署场景下的 URL 重写规则，需要结合 `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebMvcConfiguration.kt` 阅读。

第五个误区：把 `th:inline="javascript"` 当成前端框架语法。

它不是 Vue 语法，也不是浏览器原生语法，而是 Thymeleaf 模板语法。浏览器最终拿到的 HTML 应该已经被后端处理过，或者在开发环境下使用注释后的默认值。

第六个误区：认为 `<!-- built files will be auto injected -->` 是运行时代码。

这只是模板注释。真正的 JS/CSS 注入发生在 Vue CLI 构建或开发服务器处理阶段。源文件里看不到 `<script src="...">` 不代表应用没有入口脚本。

第七个误区：看到 `lang="en"` 就认为应用没有国际化。

`index.html` 的语言声明只是 HTML 壳的默认语言。实际界面语言由 `komga-webui/src/main.ts` 引入的 `i18n` 和相关 locale 文件控制。

第八个误区：只读 `index.html` 就试图理解业务功能。

这个文件只解释“应用如何被浏览器启动”。如果要理解书库、系列、图书、用户、任务、阅读器等功能，应继续从 `komga-webui/src/main.ts` 里的插件注册、`komga-webui/src/router`、`komga-webui/src/store` 和各业务组件继续读。
