# 文件：src/spa/entry.web.tsx

## 它负责什么

`src/spa/entry.web.tsx` 是 LobeHub Web 端 SPA 的浏览器启动入口。它的职责不是实现页面业务，而是把“运行环境初始化、React 挂载、React Router 路由树、首屏启动错误兜底”串起来，让 `src/routes/` 下的桌面 Web 页面可以在浏览器中运行。

可以把它理解成 Web SPA 的 `main.tsx`：

1. 先执行全局初始化逻辑：`import '../initialize'`
2. 创建 Web 端使用的 React Router：`createAppRouter(desktopRoutes, { basename })`
3. 找到 HTML 里的 `#root` DOM 节点
4. 使用 React 19 的 `createRoot(...).render(...)` 挂载应用
5. 用 `BootErrorBoundary` 包住 `RouterProvider`，处理启动阶段异常，尤其是缓存/资源版本不一致导致的首屏崩溃

这个文件非常短，但它处在“HTML 页面进入 React 应用”的边界上，是 Web 端 SPA 的第一层入口。

## 关键组成

### `import '../initialize'`

这是副作用导入，不绑定变量。它的作用是执行 `src/initialize.ts` 中的全局初始化代码。

根据当前片段，`initialize.ts` 主要做了几类事情：

- 启用 `immer` 的 `enablePatches()` 和 `enableMapSet()`，让状态更新支持 patch 和 `Map/Set`
- 注册 `dayjs` 插件：`relativeTime`、`utc`、`isToday`、`isYesterday`
- 监听 Vite chunk 预加载失败：
  - `vite:preloadError`
  - `unhandledrejection`
- 如果识别为 chunk 加载错误，就调用 `notifyChunkError()`
- 开发环境下启用 `react-scan`

所以 `entry.web.tsx` 并不直接配置日期、状态库或 chunk 错误处理，而是通过这行副作用导入确保这些初始化在 React 挂载前完成。

### `createRoot`

```ts
createRoot(document.getElementById('root')!).render(...)
```

这里使用 `react-dom/client` 的 `createRoot` 创建 React 根节点。`document.getElementById('root')!` 中的非空断言表示代码假设 HTML 模板中一定存在 `id="root"` 的节点。

这个节点通常来自 SPA HTML 模板或 Vite/Next 提供的页面容器。入口文件只负责拿到它并挂载 React 应用，不负责创建这个 DOM 节点。

### `RouterProvider`

```tsx
<RouterProvider router={router} />
```

`RouterProvider` 来自 `react-router-dom`，负责把 `createBrowserRouter` 创建出来的数据路由实例注入 React 应用。

也就是说，真正的页面渲染并不是从 `entry.web.tsx` 中直接 import 某个页面组件开始，而是由 `router` 根据当前 URL 匹配 `desktopRoutes` 后决定渲染哪个 route element。

### `BootErrorBoundary`

```tsx
<BootErrorBoundary>
  <RouterProvider router={router} />
</BootErrorBoundary>
```

`BootErrorBoundary` 是启动阶段的错误边界。它是一个 class component，使用 `getDerivedStateFromError` 和 `componentDidCatch` 捕获错误。

它的特殊点在于：如果错误发生在首次成功挂载之前，它会尝试进行一次 hard reload，并在 URL 上追加 `__lobe_force_reload` 作为 cache-busting 参数。这样可以恢复某些“浏览器缓存了旧 chunk，但页面需要新 chunk”的情况。

根据组件实现，它默认最多 reload 一次，次数记录在 `sessionStorage` 的 `lobe:boot:hard-reload-attempts` 中。成功启动后会清理 reload 计数和 URL 上的强制刷新参数。

这里和 `src/utils/router.tsx` 里的 `ErrorBoundary` 不同：

- `BootErrorBoundary` 保护的是 SPA 启动阶段
- router 里的 `ErrorBoundary` 保护的是路由渲染阶段
- `initialize.ts` 里的 chunk error listener 保护的是异步 chunk 加载失败等更全局的异常场景

### `desktopRoutes`

```ts
import { desktopRoutes } from './router/desktopRouter.config';
```

Web 入口使用的是 `desktopRoutes`，也就是桌面 Web 端路由树。虽然文件名是 `entry.web.tsx`，但它不是移动端入口，也不是 Electron 桌面入口；它加载的是 Web 浏览器中的桌面 SPA 路由。

`desktopRoutes` 是一个 `RouteObject[]`，内部声明了大量路径结构，例如：

- `agent`
- `group`
- `community`
- `settings`
- `page`
- `resource`
- 以及业务侧注入的 desktop routes

这些路由中的页面和布局大多通过 `dynamicElement()`、`dynamicLayout()` 懒加载，例如：

```ts
dynamicElement(() => import('@/routes/(main)/agent'), 'Desktop > Chat')
```

因此，入口文件只加载路由配置，具体页面组件会在路由匹配时按需加载。

### `createAppRouter`

```ts
const router = createAppRouter(desktopRoutes, { basename });
```

`createAppRouter` 定义在 `src/utils/router.tsx`。它内部调用 `createBrowserRouter`，并统一包了一层根路由：

```tsx
{
  path: '/',
  element: <RouterRoot />,
  errorElement: <ErrorBoundary />,
  children: routes,
}
```

`RouterRoot` 里又挂了几个全局层：

- `SPAGlobalProvider`
- `BusinessGlobalProvider`
- `NavigatorRegistrar`
- `Outlet`

这意味着 `entry.web.tsx` 传入的 `desktopRoutes` 并不是直接成为应用根节点，而是被包在统一的 SPA 全局 Provider 和 root route 下面。

`NavigatorRegistrar` 会把 React Router 的 `navigate` 同步到全局 store 的 `navigationRef`，让应用其他地方可以通过稳定引用进行命令式导航。

### `debugProxyBase` 和 `basename`

```ts
const debugProxyBase = '/_dangerous_local_dev_proxy';
const basename =
  window.__DEBUG_PROXY__ || window.location.pathname.startsWith(debugProxyBase)
    ? debugProxyBase
    : undefined;
```

这是 `entry.web.tsx` 相比 `entry.desktop.tsx`、`entry.mobile.tsx`、`entry.popup.tsx` 最特别的地方。

它会判断当前是否运行在本地开发 Debug Proxy 场景下：

- 如果 `window.__DEBUG_PROXY__` 为真
- 或当前路径以 `/_dangerous_local_dev_proxy` 开头

就把 React Router 的 `basename` 设置为 `/_dangerous_local_dev_proxy`。

这样 React Router 在解析 URL 时，会把这个代理前缀当作基础路径，而不是业务路由的一部分。例如：

```txt
/_dangerous_local_dev_proxy/agent/xxx
```

在 router 内部应当被理解为：

```txt
/agent/xxx
```

如果没有这个 `basename`，开发代理路径可能会被误识别为应用路由，导致路由不匹配或白屏。

## 上下游关系

### 上游：谁加载它

根据当前片段推断，`src/spa/entry.web.tsx` 是 Web SPA 构建入口之一，通常会被 Vite/Next 的 SPA HTML 模板或构建配置引用。仓库中同目录还有：

- `src/spa/entry.desktop.tsx`
- `src/spa/entry.mobile.tsx`
- `src/spa/entry.popup.tsx`

这些文件结构相似，都是各平台 SPA 的入口文件。差异主要在于使用的 route config 不同：

- `entry.web.tsx` 使用 `desktopRoutes`
- `entry.desktop.tsx` 使用 `desktopRoutes`
- `entry.mobile.tsx` 使用 `mobileRoutes`
- `entry.popup.tsx` 使用 `popupRoutes`

其中 `entry.web.tsx` 额外处理 Debug Proxy 的 `basename`。

### 下游：它依赖什么

`entry.web.tsx` 的下游依赖可以分成四层。

第一层是全局初始化：

- `src/initialize.ts`

它初始化 `immer`、`dayjs`、chunk 错误监听和开发工具。

第二层是 React 挂载：

- `react-dom/client`
- HTML 中的 `#root`

这层负责把 React 应用真正挂到页面上。

第三层是路由系统：

- `react-router-dom`
- `src/utils/router.tsx`
- `src/spa/router/desktopRouter.config.tsx`

其中 `createAppRouter` 创建 browser router，`desktopRoutes` 提供具体 route tree。

第四层是全局 Provider 和页面模块：

- `src/layout/SPAGlobalProvider`
- `@/business/client/BusinessGlobalProvider`
- `src/routes/(main)/**`
- `src/features/**`
- `src/store/**`
- `src/services/**`

这些不是 `entry.web.tsx` 直接全部 import 的，但会通过 router 和 Provider 间接进入应用运行链路。

### 与 `desktopRouter.config.tsx` 的关系

`entry.web.tsx` 不关心具体有哪些页面，它只把 `desktopRoutes` 交给 `createAppRouter`。

`desktopRouter.config.tsx` 才是桌面 Web 路由结构的核心声明文件。它定义路径、嵌套路由、动态加载页面、错误边界和 route meta。

例如 `agent` 路由下会继续嵌套：

- agent 首页
- topic 页面
- doc 页面
- profile
- channel
- task detail

这些页面最终由 `RouterProvider` 根据 URL 匹配后渲染。

### 与 `src/routes/` 和 `src/features/` 的关系

按照仓库约定，`src/routes/` 是 SPA 页面段，应该保持“薄”，主要负责 route segment 和页面组合；业务 UI 和逻辑应放到 `src/features/`。

所以从入口看，下游链路大致是：

```txt
entry.web.tsx
→ createAppRouter(desktopRoutes)
→ desktopRouter.config.tsx
→ src/routes/(main)/** 页面段
→ src/features/** 业务组件
→ src/store / src/services / src/server API
```

入口文件本身不应该塞业务逻辑，也不应该直接 import 某个 feature 组件来显示页面。

## 运行/调用流程

完整启动流程可以按时间顺序理解。

1. 浏览器加载 Web SPA 的 HTML

页面中存在一个 `#root` 容器，并加载打包后的 `entry.web.tsx` 入口脚本。

2. 执行 `../initialize`

在 React 渲染前，先注册全局能力：

```txt
immer patches/map-set
dayjs plugins
chunk load error listeners
react-scan in dev
```

这一步是全局副作用，后续组件和 store 可以默认依赖这些能力已经存在。

3. 计算 Debug Proxy 的 `basename`

入口读取浏览器环境：

```ts
window.__DEBUG_PROXY__
window.location.pathname
```

如果当前运行在 `/_dangerous_local_dev_proxy` 下，就设置：

```ts
basename = '/_dangerous_local_dev_proxy'
```

否则 `basename` 是 `undefined`。

这个值会传给 React Router，影响它如何从浏览器 URL 中剥离基础路径。

4. 创建 router

```ts
const router = createAppRouter(desktopRoutes, { basename });
```

`createAppRouter` 内部会创建 browser router，并增加统一根路由：

```txt
/
├─ SPAGlobalProvider
├─ BusinessGlobalProvider
├─ NavigatorRegistrar
└─ Outlet
   └─ desktopRoutes 匹配到的页面
```

这里的 `Outlet` 是子路由真正渲染的位置。

5. 挂载 React 根节点

```tsx
createRoot(document.getElementById('root')!).render(...)
```

React 开始接管 HTML 中的 `#root` 节点。

6. `BootErrorBoundary` 包住 `RouterProvider`

渲染结构是：

```tsx
<BootErrorBoundary>
  <RouterProvider router={router} />
</BootErrorBoundary>
```

如果首次启动阶段发生错误，`BootErrorBoundary` 可能触发一次带 cache-busting 参数的 hard reload。

7. `RouterProvider` 根据当前 URL 匹配路由

例如访问：

```txt
/agent/abc
```

在非 Debug Proxy 场景下，React Router 直接用 `/agent/abc` 匹配 `desktopRoutes`。

如果访问：

```txt
/_dangerous_local_dev_proxy/agent/abc
```

并且 `basename` 是 `/_dangerous_local_dev_proxy`，React Router 会把基础路径去掉，再用 `/agent/abc` 匹配业务路由。

8. 懒加载页面和布局

`desktopRoutes` 中的 route element 通常由 `dynamicElement()` 或 `dynamicLayout()` 创建。匹配到具体路由后，才会动态 import 对应页面模块。

加载过程中显示：

```tsx
<Loading debugId="..." />
```

加载完成后渲染对应的 `src/routes/` 页面段，再继续组合 `src/features/` 下的业务 UI。

## 小白阅读顺序

建议不要一开始就钻进所有路由。这个入口文件短，但它背后连接的系统很多，可以按下面顺序读。

1. 先读 `src/spa/entry.web.tsx`

重点看它只做四件事：

```txt
initialize
create router
create root
render RouterProvider
```

不要把它误解成页面文件。

2. 再读 `src/initialize.ts`

理解为什么入口文件第一行是副作用导入。这里能看到应用在 React 启动前需要准备哪些全局能力，尤其是 `immer`、`dayjs` 和 chunk error 处理。

3. 再读 `src/utils/router.tsx`

重点看这些函数和组件：

- `createAppRouter`
- `RouterRoot`
- `NavigatorRegistrar`
- `dynamicElement`
- `dynamicLayout`
- `ErrorBoundary`
- `redirectElement`

读完这个文件后，就能明白入口文件中的 `createAppRouter(desktopRoutes, { basename })` 实际创建了什么。

4. 再读 `src/spa/router/desktopRouter.config.tsx`

不要试图一次记住所有路由。先看结构：

```txt
RouteObject[]
children
path
index
element
handle.meta
errorElement
```

再观察页面大多是动态 import 的：

```ts
dynamicElement(() => import('@/routes/...'))
dynamicLayout(() => import('@/routes/.../_layout'))
```

这说明页面代码是按路由拆包加载的。

5. 抽一个具体 route 往下追

比如从 `agent` 路由追到：

```txt
src/routes/(main)/agent
src/routes/(main)/agent/_layout
src/routes/(main)/agent/(chat)/_layout
```

再看这些 route 文件如何引入 `src/features/` 的业务组件。

6. 最后对比其他入口

可以简单对比：

- `src/spa/entry.desktop.tsx`
- `src/spa/entry.mobile.tsx`
- `src/spa/entry.popup.tsx`

你会发现它们模式一致，只是 route config 不同。`entry.web.tsx` 的特殊点是 Debug Proxy `basename` 和 `BootErrorBoundary`。

## 常见误区

### 误区一：以为 `entry.web.tsx` 是首页

它不是首页，也不是 `/` 路由页面。它是 SPA 启动入口。真正的首页由 `desktopRoutes` 中的 `/` 或 index route 决定，并最终落到 `src/routes/` 下的页面模块。

### 误区二：以为 `desktopRoutes` 只给 Electron desktop 用

`entry.web.tsx` 和 `entry.desktop.tsx` 都使用 `desktopRoutes`。这里的 `desktop` 更偏向“桌面布局/桌面路由树”，不等同于 Electron。

Web 浏览器中的桌面版 SPA 也使用这套路由配置。

### 误区三：忽略 `basename`

`basename` 是本文件最容易被忽略但很关键的逻辑。

在普通访问中：

```txt
basename = undefined
```

在 Debug Proxy 中：

```txt
basename = '/_dangerous_local_dev_proxy'
```

如果删除或误改这段逻辑，本地 `dev:spa` 的 Debug Proxy URL 可能无法正确匹配业务路由，表现为白屏、跳转异常或路由 404。

### 误区四：把 `window.__DEBUG_PROXY__` 当成通用业务状态

`window.__DEBUG_PROXY__` 只用于判断是否处在本地调试代理环境。它不是业务 feature flag，也不应该被页面逻辑依赖。

这个判断只应该影响 router 的基础路径解析。

### 误区五：以为 `BootErrorBoundary` 等同于路由错误页

`BootErrorBoundary` 保护的是启动阶段，尤其是首次渲染前的异常。它可能触发 hard reload 来恢复缓存错配。

路由页面内部的错误边界主要来自 `createAppRouter` 中的 `errorElement: <ErrorBoundary />`，以及某些 route 自己配置的 `errorElement`。

两者职责不同：

```txt
BootErrorBoundary：应用启动兜底
Router ErrorBoundary：路由渲染兜底
initialize chunk listener：异步资源加载兜底
```

### 误区六：在入口文件里加业务逻辑

`entry.web.tsx` 应该保持极薄。它处在应用最外层，任何放在这里的逻辑都会影响整个 Web SPA 启动。

如果要加页面、布局或业务功能，通常应该放在：

```txt
src/routes/
src/features/
src/store/
src/services/
```

如果要加路由，应该改 `src/spa/router/desktopRouter.config.tsx`，并注意桌面路由配置同步规则。按照仓库约定，`desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 在路径和嵌套上需要保持同步，否则不同构建路径可能出现空白页面。

### 误区七：认为 `document.getElementById('root')!` 很随意

这里的 `!` 是非空断言，表示入口假设宿主 HTML 一定提供 `#root`。如果 HTML 模板缺失这个节点，React 挂载会直接失败。

所以这行不是“可以为空也没关系”，而是“运行环境必须满足这个约定”。

### 误区八：看不到 Provider 就以为没有全局上下文

`entry.web.tsx` 表面上只渲染了 `RouterProvider`，但 `createAppRouter` 内部把所有 routes 包进了 `RouterRoot`。`RouterRoot` 里有：

```txt
SPAGlobalProvider
BusinessGlobalProvider
NavigatorRegistrar
Outlet
```

所以全局 Provider 并不是在入口 JSX 中直接出现，而是在 router root element 中统一挂载。
