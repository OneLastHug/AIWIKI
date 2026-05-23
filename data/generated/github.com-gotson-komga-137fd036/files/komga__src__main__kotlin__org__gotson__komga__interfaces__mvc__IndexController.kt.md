# 文件：`komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt`

## 它负责什么
这个文件是 Komga 的 MVC 入口控制器，职责很单一：接住根路径 `/` 的请求，向模板视图注入一个 `baseUrl`，然后返回 `index` 视图。根据当前片段推断，它的主要用途不是提供业务数据，而是把后端部署路径传给前端单页应用，避免前端在有上下文路径时拼错静态资源和 API 地址。

它属于 Spring MVC 层，而不是 REST API 层。也就是说，它返回的是页面视图名 `index`，最终会被模板引擎渲染成 HTML。

## 关键组成
- `@Controller`：声明这是一个 MVC 控制器，返回视图而不是 JSON。
- 构造参数 `ServletContext`：用来读取当前 Web 容器的 `contextPath`。
- `private val baseUrl: String = "${servletContext.contextPath}/"`：提前计算应用基础路径。若应用部署在子路径下，这个值会包含该前缀。
- `@GetMapping("/")`：处理站点根路径。
- `fun index(model: Model): String`：把 `baseUrl` 放进视图模型，然后返回 `"index"`。

这里没有复杂分支，也没有服务层依赖，核心逻辑就是“取上下文路径，塞进模板，再交给前端入口页”。

## 上下游关系
上游主要有两类：

1. HTTP 请求入口  
   访问 `/` 时命中这个控制器。`ResourceNotFoundController` 里还有一个补充逻辑：当请求不是 `/api`、`/opds`、`/sse` 这些后端接口路径时，404 会被转发到 `/`，从而回到这个 `IndexController`。这说明它是 SPA 的总入口。

2. 容器环境  
   `ServletContext.contextPath` 决定 `baseUrl`，所以它对部署前缀敏感。应用挂在根路径还是子路径下，前端拿到的资源基址会不同。

下游主要有两层：

1. `komga-webui/public/index.html`  
   这个模板里会把后端传入的 `baseUrl` 写进 `window.resourceBaseUrl`。前端入口页就是靠这个全局变量知道自己应该从哪个路径加载资源。

2. `komga-webui/src/public-path.js`、`komga-webui/src/functions/urls.ts`  
   前端在生产环境下直接读取 `window.resourceBaseUrl`，拼出静态资源前缀和 API 前缀。也就是说，`IndexController` 的输出会直接影响前端所有 URL 的生成结果。

## 运行/调用流程
1. 浏览器请求站点根路径 `/`。
2. Spring MVC 命中 `IndexController.index()`。
3. 控制器从 `ServletContext` 读出 `contextPath`，拼成 `baseUrl`，例如 `/komga/`。
4. `model.addAttribute("baseUrl", baseUrl)` 把这个值交给视图层。
5. 返回视图名 `"index"`。
6. `komga-webui/public/index.html` 被渲染，模板脚本把 `baseUrl` 写入 `window.resourceBaseUrl`。
7. 前端启动后，`src/public-path.js` 和 `src/functions/urls.ts` 读取这个变量，决定静态资源和接口请求应该走哪个前缀。
8. 如果用户访问了不存在的前端路由，`ResourceNotFoundController` 会把非 API 请求 forward 到 `/`，再次回到这条流程。

## 小白阅读顺序
1. 先看 `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/IndexController.kt`，抓住它只做了“返回首页视图 + 注入 `baseUrl`”。
2. 再看 `komga/src/main/kotlin/org/gotson/komga/interfaces/mvc/ResourceNotFoundController.kt`，理解为什么很多 404 会回到首页。
3. 接着看 `komga/src/main/kotlin/org/gotson/komga/infrastructure/web/WebMvcConfiguration.kt`，弄清静态资源是怎么映射到 `public/` 的。
4. 然后看 `komga-webui/public/index.html`，确认 `baseUrl` 如何被写入 `window.resourceBaseUrl`。
5. 最后看 `komga-webui/src/public-path.js` 和 `komga-webui/src/functions/urls.ts`，把后端传参和前端请求地址串起来。

## 常见误区
- 把它当成 REST 接口控制器。实际上它返回的是视图名 `index`，不是 JSON。
- 以为 `baseUrl` 是“网站根路径”固定等于 `/`。实际上它来自 `ServletContext.contextPath`，部署在子路径时会变化。
- 误解 `index` 视图的作用。它不是传统服务端渲染页面，而是前端单页应用的壳页面。
- 忽略 `ResourceNotFoundController` 的 forward 逻辑。很多前端路由并不对应后端真实文件，最终是靠它兜底回到首页。
- 只看后端不看前端。这个控制器本身很短，但它的真实价值在于给 `komga-webui` 提供运行时路径信息。
