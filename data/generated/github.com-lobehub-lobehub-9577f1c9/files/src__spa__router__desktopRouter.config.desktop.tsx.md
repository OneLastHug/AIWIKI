# 文件：`src/spa/router/desktopRouter.config.desktop.tsx`

## 一句话定位
这是 Electron 桌面端的同步路由总表，直接用静态 `import` 把整套桌面路由、布局、重定向和桌面专属页面组装成 `desktopRoutes: RouteObject[]`，供桌面运行时快速创建路由树。

## 它暴露/定义了什么
它对外只暴露一个核心产物：`desktopRoutes`。这个数组不是零散页面的集合，而是完整的桌面端路由结构，包含主布局 `/`、会话相关路由、社区发现、资源、设置、记忆、视频、图片、任务工作区、页面管理、分享页，以及 `__DEV__` 下的 `devtools`。文件末尾还通过 `desktopRoutes.push(...)` 追加了桌面专属的 onboarding 路由和几个 Web 到桌面 onboarding 的重定向别名。

## 谁调用它
根据当前片段推断，直接消费者主要是桌面入口和路由相关基础设施：`src/spa/entry.desktop.tsx` 会把 `desktopRoutes` 交给 `createAppRouter`，`src/spa/entry.web.tsx` 也会读取同名路由配置用于 Web 端壳层；另外 `src/features/Electron/navigation/useNavigationHistory.ts`、`src/features/Electron/titlebar/TabBar/*` 这些 Electron 能力会基于 `desktopRoutes` 做路由解析、标题和标签页回溯。`src/spa/router/desktopRouter.sync.test.tsx` 还会读这个文件，校验它和异步版配置保持一致。

## 它调用谁
它本身不承载业务逻辑，主要是把一批页面、布局和工具函数拼装进路由对象里。它调用/引用的对象包括：各个 `src/routes/...` 下的页面组件和布局组件，`BusinessDesktopRoutesWithMainLayout`、`BusinessDesktopRoutesWithoutMainLayout`，`routeMeta`、`taskRouteMeta`、`tasksRouteMeta`、`pageRouteMeta`、`settingsRouteMeta`、`groupRouteMeta`、`agentRouteMeta`、`agentTopicPageRouteMeta`，以及 `redirectElement`、`ErrorBoundary`。这些依赖决定了路由进入后展示什么页面、是否重定向、以及导航元数据怎么生成。

## 核心流程
核心流程可以概括成“静态拼树 + 桌面补丁”：
1. 先定义根路由 `/` 及其所有子树，主布局由 `DesktopMainLayout` 承载。
2. 通过嵌套路由把不同业务域拆开，例如 `agent`、`group`、`community`、`resource`、`settings`、`memory`、`eval`、`page` 等。
3. 每个叶子节点挂上具体页面组件，并用 `handle.meta` 提供导航标题和图标。
4. 对需要异常兜底的分支挂 `ErrorBoundary`，对默认入口和非法路径挂 `redirectElement('/')`。
5. 把 `BusinessDesktopRoutesWithMainLayout` 和 `BusinessDesktopRoutesWithoutMainLayout` 拼入同一棵树，保证业务扩展不必改主结构。
6. 最后追加桌面专属 onboarding 与桌面别名重定向，使 Electron 版和 Web 版在入口体验上保持一致但又能分流。

## 关键函数的高层作用
`redirectElement()` 负责把某些路径快速导向目标页，是这个文件里最关键的控制流工具。`routeMeta()` 负责把图标和标题键包装成统一的路由元数据，供导航、面包屑和标题栏读取。`ErrorBoundary` 提供路由级错误兜底，避免单个页面崩溃拖垮整条路由树。`desktopRoutes.push()` 这里不是普通数组追加，而是在主路由树定义完成后再补桌面专属入口，体现了“共用主结构 + 桌面增强”的设计。

## 修改风险
这个文件的风险很高，因为它是桌面端路由的中心枢纽。改动路径、嵌套层级或 `index/path` 组合，容易造成空白页、404、重定向循环，或者让 Electron 的标题栏、历史导航、最近访问页解析失真。尤其要注意三类风险：一是 `desktopRouter.config.tsx` 与这里不同步，会触发同步测试失败或运行时行为分叉；二是 `handle.meta` 丢失或变形，会影响导航与窗口标题；三是 onboarding、`/share/t`、`/devtools` 这类桌面/环境专属路由一旦误改，问题通常只在特定构建模式下暴露，排查成本很高。
