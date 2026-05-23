# 目录：komga-webui/public

## 它负责什么

`komga-webui/public` 是 Komga 前端 WebUI 的“静态入口资源目录”。它不承载业务逻辑，也不包含 Vue 组件、路由、状态管理或 API 调用代码，而是负责提供浏览器启动前端应用时最先接触到的基础文件：

- HTML 入口页：`komga-webui/public/index.html`
- PWA 安装清单：`komga-webui/public/manifest.json`
- 各平台使用的 favicon、Apple touch icon、Android Chrome icon、Windows tile icon

从 `komga-webui/package.json` 看，前端是 Vue CLI 项目，主要脚本包括 `vue-cli-service serve --port 8081` 和 `vue-cli-service build`。在 Vue CLI 体系中，`public` 目录里的文件会作为构建入口模板或原样静态资源参与输出；其中 `index.html` 会被 Vue CLI 当作页面模板，构建后的 JS/CSS 资源会自动注入到 HTML 中。

这个目录的核心职责可以概括为：为 Vue 单页应用提供宿主 HTML、浏览器/PWA 元信息和应用图标资源。

## 关键组成

`komga-webui/public/index.html` 是最重要的文件。它定义了标准 HTML 页面结构，包含：

- `<meta charset="utf-8">`：字符编码。
- `<meta name="viewport" content="width=device-width,initial-scale=1.0">`：移动端视口适配。
- `apple-mobile-web-app-capable` 和 `mobile-web-app-capable`：允许移动端以类 App 模式打开。
- `<title>Komga</title>`：浏览器标签页标题。
- 一组图标引用：`favicon.ico`、`apple-touch-icon.png`、`favicon-32x32.png`、`favicon-16x16.png`、`mstile-144x144.png`。
- `<link rel="manifest" href="/manifest.json">`：关联 PWA manifest。
- `<div id="app"></div>`：Vue 应用挂载点。
- `<noscript>`：当浏览器禁用 JavaScript 时显示提示。

其中最值得注意的是这一段：

```html
<script th:inline="javascript">
    /*<![CDATA[*/
    window.resourceBaseUrl = /*[(<%="$"%>{"'" + baseUrl + "'"})]*/ '/'
    /*]]>*/
</script>
```

它不像普通 Vue CLI 模板里的纯前端代码，而是带有 `th:inline="javascript"`，说明该 HTML 在生产环境中很可能会经过后端模板引擎处理。根据当前片段推断，Komga 后端会向模板注入 `baseUrl`，并赋值给浏览器全局变量 `window.resourceBaseUrl`。如果模板变量没有被后端替换，默认值是 `'/'`。

`komga-webui/public/manifest.json` 定义了 PWA 元数据：

- `name` 和 `short_name` 都是 `Komga`。
- `start_url` 是 `.`，表示从当前路径启动。
- `display` 是 `standalone`，表示安装后可以像独立应用一样显示。
- `background_color` 是 `#08397f`。
- `theme_color` 是 `black`。
- `description` 是 `Free and open source comics/mangas media server`。
- `icons` 列出不同尺寸的图标，覆盖 32、144、180、192、512 等常见场景。

图标文件包括：

- `favicon.ico`
- `favicon-16x16.png`
- `favicon-32x32.png`
- `apple-touch-icon.png`
- `apple-touch-icon-180x180.png`
- `android-chrome-192x192.png`
- `android-chrome-512x512.png`
- `mstile-144x144.png`

这些文件主要服务于浏览器标签页、移动端添加到主屏幕、Android PWA、Windows 磁贴等外壳体验。

## 上下游关系

上游主要是构建系统和服务端部署环境。

从 `komga-webui/package.json` 可知，WebUI 使用 Vue 2、Vue Router、Vuex、Vuetify、TypeScript、Vue CLI 等技术栈。`public/index.html` 是 Vue CLI 构建链路的入口模板，构建时会被 `vue-cli-service build` 处理，最终生成带有前端 bundle 引用的 HTML。

`komga-webui/vue.config.js` 对这个目录的行为有直接影响。配置里设置了：

```js
publicPath: process.env.NODE_ENV === 'production' ? './' : '/'
```

注释说明了这里的取舍：

- 开发环境使用 `/`，否则 dev server 无法加载任意路径。
- 生产环境使用 `./`，避免 CSS chunk 中生成 `url(/fonts...)` 这类绝对路径，因为 Komga 可能运行在 servlet context path 下。

这说明 Komga WebUI 不是永远部署在站点根路径 `/`，而可能被后端挂在某个上下文路径下。因此，`index.html` 里的静态引用和运行时 `resourceBaseUrl` 都与“前端资源如何在后端路径下正确加载”有关。

下游主要是浏览器和 Vue 应用运行时。

浏览器请求 WebUI 页面后，会先拿到 `index.html`，再加载构建注入的 JS/CSS。Vue 应用启动后会挂载到 `<div id="app"></div>`。同时，浏览器还会读取 `manifest.json` 和各种 icon，用于 PWA、标签页图标、桌面安装入口等。

根据当前片段推断，`window.resourceBaseUrl` 是前端运行时代码读取资源基础路径的全局配置。依据是：它被放在入口 HTML 的 `<head>` 中，在 Vue bundle 执行之前定义；变量名明确叫 `resourceBaseUrl`；并且值来自后端 `baseUrl` 模板变量。

## 运行/调用流程

开发环境大致流程是：

1. 开发者在 `komga-webui` 下运行 `npm run serve`。
2. `vue-cli-service serve --port 8081` 启动开发服务器。
3. Vue CLI 使用 `komga-webui/public/index.html` 作为 HTML 模板。
4. 浏览器访问开发服务器页面。
5. 页面中出现 `<div id="app"></div>`。
6. Vue CLI dev server 注入开发环境 JS/CSS。
7. Vue 应用启动并挂载到 `#app`。

生产构建流程大致是：

1. 执行 `npm run build`。
2. Vue CLI 根据 `vue.config.js` 使用生产 `publicPath: './'`。
3. `public/index.html` 作为模板被处理。
4. 构建产物中的 JS/CSS 被自动注入到 HTML。
5. `public` 目录下的图标、manifest 等静态资源进入最终发布资源。
6. 后端服务对外提供构建后的 WebUI。
7. 浏览器加载 HTML、manifest、icons 和前端 bundle。
8. Vue 单页应用接管页面交互。

生产运行时还有一层后端模板处理迹象：`index.html` 中的 `th:inline="javascript"` 表明页面可能先经由后端模板引擎渲染，把 `baseUrl` 写入 `window.resourceBaseUrl`。这对部署在非根路径、反向代理路径或 servlet context path 下的 Komga 很重要。

PWA/图标加载流程则比较独立：

1. 浏览器解析 `index.html`。
2. 通过 `<link rel="manifest" href="/manifest.json">` 获取 manifest。
3. manifest 中声明应用名称、显示模式、主题色和图标集合。
4. 不同平台按需要选择对应 icon，例如 Android 使用 `android-chrome-192x192.png` 或 `android-chrome-512x512.png`，iOS 使用 `apple-touch-icon.png`，Windows tile 使用 `mstile-144x144.png`。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先看 `komga-webui/public/index.html`，理解浏览器打开 Komga WebUI 时最先拿到的页面长什么样。重点关注 `<div id="app"></div>`，这是 Vue 应用真正挂载的位置。
2. 再看 `komga-webui/package.json` 的 `scripts`，明白 `serve` 和 `build` 分别对应开发运行和生产构建。
3. 接着看 `komga-webui/vue.config.js`，尤其是 `publicPath`。这里解释了为什么生产环境不能简单使用 `/` 作为资源路径。
4. 然后看 `komga-webui/public/manifest.json`，理解它只负责 PWA 元数据，不负责业务页面。
5. 最后浏览图标文件名即可，不需要深入研究每个图片内容。它们是同一个应用标识在不同平台和尺寸下的变体。

如果是第一次接触 Vue 项目，可以把 `public/index.html` 理解成“外壳”，真正的页面和交互在构建注入的 Vue JS 里；`public` 目录本身并不写书库、漫画、用户、阅读器等业务逻辑。

## 常见误区

第一个误区：以为 `public/index.html` 就是完整页面。实际上它只是 Vue 单页应用的宿主模板，页面主体只有一个 `#app` 挂载点。构建后的 JS 才会渲染真正的 Komga 界面。

第二个误区：以为 `manifest.json` 会控制前端路由。它不会。它只告诉浏览器这个 Web 应用的名称、图标、启动 URL、显示模式和主题信息。Vue Router 的路由不在这里定义。

第三个误区：随意把 `href="/manifest.json"`、`href="/favicon.ico"` 或资源路径全部改成相对路径/绝对路径。这个项目明显考虑了 servlet context path 和非根路径部署，`vue.config.js` 里的注释已经说明生产资源路径是敏感点。修改路径前必须同时理解后端部署方式、Vue CLI `publicPath` 和 `window.resourceBaseUrl` 的关系。

第四个误区：忽略 `th:inline="javascript"`。这不是普通无意义属性，而是后端模板处理的信号。根据当前片段推断，Komga 后端可能会把 `baseUrl` 注入给前端，用于解决资源基础路径问题。如果只按纯静态 Vue 项目理解，容易漏掉后端参与渲染入口 HTML 这一层。

第五个误区：认为 `public` 目录适合放业务代码。Vue CLI 项目中，`public` 更适合放不需要经过 webpack/Vue 编译处理、需要原样复制或作为 HTML 模板的资源。业务组件、页面、路由、状态管理通常应在 `src` 体系内，而不是放在 `public`。

第六个误区：删除看似重复的图标。`apple-touch-icon.png`、`android-chrome-192x192.png`、`mstile-144x144.png` 等分别服务不同平台和尺寸。即使它们视觉上相似，也可能被不同设备或浏览器读取。
