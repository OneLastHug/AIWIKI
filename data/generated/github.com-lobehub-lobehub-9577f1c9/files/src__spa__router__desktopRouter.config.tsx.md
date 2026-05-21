# 文件：src/spa/router/desktopRouter.config.tsx

## 它负责什么

`src/spa/router/desktopRouter.config.tsx` 是 LobeHub SPA 桌面端的 **React Router 路由树配置文件**。它不实现具体页面 UI，而是把 `src/routes/` 下的页面段、布局段、错误边界、重定向、导航元信息组合成一个 `RouteObject[]`，并导出为：

```ts
export const desktopRoutes: RouteObject[] = [...]
```

这个 `desktopRoutes` 会被桌面/网页 SPA 入口消费：

- `src/spa/entry.web.tsx`：导入 `desktopRoutes`，传给 `createAppRouter(desktopRoutes, { basename })`
- `src/spa/entry.desktop.tsx`：导入 `desktopRoutes`，传给 `createAppRouter(desktopRoutes)`

也就是说，这个文件是桌面 SPA 的“路由总表”：访问 `/agent/:aid`、`/settings/provider/:providerId`、`/page/:id`、`/share/t/:id` 等路径时，React Router 会根据这里的树形结构决定加载哪个 layout、哪个 page、哪个 error boundary，以及导航标签该显示什么图标和标题。

它的定位可以概括为：

- 定义桌面端主布局内的业务路由
- 定义主布局外的特殊路由，如 share、onboarding、devtools
- 使用 `dynamicElement` / `dynamicLayout` 做懒加载和代码分割
- 给部分路由挂载 `handle.meta`，供导航、标签页或标题系统读取
- 接入 `BusinessDesktopRoutesWithMainLayout` / `BusinessDesktopRoutesWithoutMainLayout`，允许业务层扩展桌面路由
- 通过 `ErrorBoundary` 处理路由级错误，尤其是 chunk 加载失败等情况

## 关键组成

第一类 import 是路由图标和类型：

```ts
import {
  BrainCircuit,
  FilePenIcon,
  Home,
  Image,
  LibraryBigIcon,
  Settings,
  ShapesIcon,
} from 'lucide-react';
import { type RouteObject } from 'react-router-dom';
```

这些图标不会直接渲染在本文件里，而是作为 `routeMeta({ icon, titleKey })` 的一部分挂到路由 `handle.meta` 上，后续由导航或标签系统读取。`RouteObject` 是 React Router 的路由对象类型。

第二类 import 是业务扩展路由：

```ts
import {
  BusinessDesktopRoutesWithMainLayout,
  BusinessDesktopRoutesWithoutMainLayout,
} from '@/business/client/BusinessDesktopRoutes';
```

这两个数组分别插入到不同层级：

- `BusinessDesktopRoutesWithMainLayout` 插入主布局 `/` 的 children 中，表示这些业务路由会共享 `@/routes/(main)/_layout`
- `BusinessDesktopRoutesWithoutMainLayout` 插入顶层，表示这些业务路由不包在主布局里

这体现了 LobeHub 的开源核心和业务/云端扩展分层：核心路由固定在这里，业务侧可通过 `@/business/client/BusinessDesktopRoutes` 扩展。

第三类 import 是路由元信息：

```ts
import { taskRouteMeta, tasksRouteMeta } from '@/features/AgentTasks/routeMeta';
import { pageRouteMeta } from '@/features/Pages/routeMeta';
import { agentRouteMeta } from '@/routes/(main)/agent/features/routeMeta';
import { agentTopicPageRouteMeta } from '@/routes/(main)/agent/features/topicPageRouteMeta';
import { groupRouteMeta } from '@/routes/(main)/group/features/routeMeta';
import { settingsRouteMeta } from '@/routes/(main)/settings/features/routeMeta';
import { routeMeta } from '@/spa/router/routeMeta';
```

其中 `routeMeta` 是一个轻量包装函数，返回 `RouteMeta`。`RouteMeta` 支持：

- `icon`
- `titleKey`
- `createNewTab`
- `useDynamicMeta`

因此 `handle: { meta: ... }` 不只是给菜单显示文字，也可能支持动态标题、头像、创建新标签页等行为。

第四类 import 是路由工具：

```ts
import { dynamicElement, dynamicLayout, ErrorBoundary, redirectElement } from '@/utils/router';
```

它们是理解本文件的核心：

- `dynamicElement(importFn, debugId)`：懒加载页面组件，返回包在 `Suspense` 里的 React element
- `dynamicLayout(importFn, debugId)`：懒加载布局组件，布局组件内部通常会渲染 `<Outlet />`
- `redirectElement(to)`：返回 `<Navigate replace to={to} />`
- `ErrorBoundary`：路由级错误边界，内部会处理 `useRouteError()`，并对 chunk load error 做通知

本文件还提前定义了一个复用元素：

```ts
const agentChatElement = dynamicElement(() => import('@/routes/(main)/agent'), 'Desktop > Chat');
```

它被多处 agent chat index route 复用，避免在同一聊天页入口重复写动态 import。

核心 export 是 `desktopRoutes`。它整体是一个数组，第一项是主应用路由：

```ts
{
  path: '/',
  element: dynamicLayout(() => import('@/routes/(main)/_layout'), 'Desktop > Main > Layout'),
  errorElement: <ErrorBoundary />,
  children: [...]
}
```

这意味着绝大多数桌面页面都在 `@/routes/(main)/_layout` 这个主布局下运行。

主布局 children 中主要包含：

- `agent`：单 Agent 聊天、topic、page doc、profile、channel、agent task detail
- `group`：群组聊天和 profile
- `community`：发现页，分 list 和 detail 两套嵌套路由
- `resource`：资源首页、知识库列表和知识库详情
- `settings`：设置页、provider 嵌套路由、普通 tab、二级 tab
- `memory`：记忆模块首页和 identities、contexts、preferences、experiences、activities
- `video`：视频创建页
- `image`：图片创建页
- `eval`：评测模块 overview、benchmark、run、case、dataset
- `tasks` / `task/:taskId`：跨 Agent 的任务工作区
- `page`：Pages 模块首页和详情页
- index route：默认首页
- catch-all route：未知路径重定向到 `/`

主布局之外还有：

- `BusinessDesktopRoutesWithoutMainLayout`
- `/share/t/:id`
- dev-only `/devtools`
- `/onboarding`
- `/onboarding/agent`
- `/onboarding/classic`

文件末尾用 `desktopRoutes.push(...)` 追加 onboarding 相关路由。这和前面的数组字面量不同，但最终效果仍然是扩展同一个 `desktopRoutes` 数组。

## 上下游关系

上游入口是 SPA 启动文件。

`src/spa/entry.web.tsx` 中：

```ts
import { desktopRoutes } from './router/desktopRouter.config';

const router = createAppRouter(desktopRoutes, { basename });
```

Web 入口会根据 debug proxy 情况设置 `basename`。如果当前页面运行在 `/_dangerous_local_dev_proxy` 下，`createBrowserRouter` 会带上这个 basename，保证本地 Vite SPA 可以嵌到线上代理路径下运行。

`src/spa/entry.desktop.tsx` 中：

```ts
import { desktopRoutes } from './router/desktopRouter.config';

const router = createAppRouter(desktopRoutes);
```

Electron 桌面入口同样使用这个异步路由配置文件。根据当前片段推断，`desktopRouter.config.desktop.tsx` 是一份同步 import 版本，主要用于同步性、Electron 或构建侧校验/兼容场景；但实际 `entry.desktop.tsx` 当前导入的是 `desktopRouter.config.tsx`。

下游由 `src/utils/router.tsx` 接管。`createAppRouter(routes)` 会把传入的 `desktopRoutes` 包到一个根路由下面：

```ts
createBrowserRouter([
  {
    path: '/',
    element: <RouterRoot />,
    errorElement: <ErrorBoundary />,
    children: routes,
  },
])
```

`RouterRoot` 又包了：

- `SPAGlobalProvider`
- `BusinessGlobalProvider`
- `NavigatorRegistrar`
- `<Outlet />`

所以本文件中的任何页面真正渲染前，都会先进入全局 Provider 环境。`NavigatorRegistrar` 会把 React Router 的 `navigate` 写入全局 store 的 `navigationRef`，支持应用内的命令式导航。

本文件依赖的页面和布局主要来自 `src/routes/`，例如：

- `@/routes/(main)/_layout`
- `@/routes/(main)/agent/_layout`
- `@/routes/(main)/agent`
- `@/routes/(main)/settings/_layout`
- `@/routes/(main)/settings/provider`
- `@/routes/(main)/page/_layout`
- `@/routes/share/t/[id]`

这些 `src/routes/` 文件按项目约定应该保持轻量，只做页面段和布局段的组合，具体业务 UI 和逻辑通常下沉到 `src/features/`。

同目录还有一个重要测试文件：

```txt
src/spa/router/desktopRouter.sync.test.tsx
```

它会读取：

- `src/spa/router/desktopRouter.config.tsx`
- `src/spa/router/desktopRouter.config.desktop.tsx`

并校验两者的 route path、`index: true` 数量、`handle.meta` 声明基本同步。测试里明确记录了一个允许差异：

```ts
'/desktop-onboarding': '/onboarding'
```

这说明维护桌面路由时，不能只改当前文件，还要同步静态桌面配置文件，否则可能导致 web/desktop 路由树漂移。

## 运行/调用流程

以访问 `/settings/provider/openai` 为例，流程大致是：

1. 浏览器或桌面壳启动 SPA，执行 `src/spa/entry.web.tsx` 或 `src/spa/entry.desktop.tsx`
2. 入口导入 `desktopRoutes`
3. 入口调用 `createAppRouter(desktopRoutes)`
4. `createAppRouter` 创建 React Router data router，并挂载根级 `RouterRoot`
5. React Router 开始匹配路径 `/settings/provider/openai`
6. 先匹配根路由 `/`
7. 进入本文件中主应用路由 `/`
8. 加载 `@/routes/(main)/_layout`
9. 在 children 中匹配 `settings`
10. 加载 `@/routes/(main)/settings/_layout`
11. 在 settings children 中匹配 `provider`
12. 加载 provider layout：

```ts
import('@/routes/(main)/settings/provider').then((m) => m.ProviderLayout)
```

13. 再匹配 `:providerId`
14. 加载 provider detail page：

```ts
import('@/routes/(main)/settings/provider').then((m) => m.ProviderDetailPage)
```

15. 页面渲染时，相关 route 的 `handle.meta` 可被导航、标签页或标题系统读取

再以 `/agent/:aid/:topicId/page/:docId` 为例：

1. 匹配 `/`
2. 匹配 `agent`
3. 匹配 `:aid`
4. 加载 `@/routes/(main)/agent/_layout`
5. 进入 chat layout：

```ts
@/routes/(main)/agent/(chat)/_layout
```

6. 匹配 `:topicId`
7. 匹配 `page`
8. 匹配 `:docId`
9. 加载：

```ts
@/routes/(main)/agent/[topicId]/page/[docId]
```

这里的 `:aid`、`:topicId`、`:docId` 是 React Router 的动态参数；具体页面可以通过 `useParams()` 等方式读取。

本文件中 `dynamicElement` 和 `dynamicLayout` 都会返回带 `Suspense` 的 element。用户首次进入某个路由时，对应 chunk 才会被加载；加载期间显示 `BrandTextLoading`，并带有类似 `'Desktop > Settings > Layout'` 的 `debugId`，便于定位慢加载或加载失败的路由节点。

如果某个路由加载或渲染失败，该层级的 `errorElement: <ErrorBoundary />` 会接管。部分任务路由传了 `resetPath`：

```ts
<ErrorBoundary resetPath="/" />
<ErrorBoundary resetPath="/tasks" />
```

这表示错误页的恢复路径会因上下文不同而不同。

## 小白阅读顺序

建议先不要从第一行硬读到最后一行，而是按“路由树层级”理解。

第一步，看文件顶部的工具函数 import：

```ts
dynamicElement
dynamicLayout
redirectElement
ErrorBoundary
```

只要理解这四个工具，本文件 80% 的结构就清楚了：

- `dynamicLayout` 是外壳，通常包 children
- `dynamicElement` 是具体页面
- `redirectElement` 是重定向
- `ErrorBoundary` 是错误兜底

第二步，看 `desktopRoutes` 的最外层结构：

```ts
[
  {
    path: '/',
    element: dynamicLayout(() => import('@/routes/(main)/_layout'), ...),
    children: [...]
  },
  ...BusinessDesktopRoutesWithoutMainLayout,
  {
    path: '/share/t',
    ...
  },
  devtools...
]
```

先分清哪些路由在主布局内，哪些在主布局外。主布局内通常是应用主体；主布局外通常是分享页、引导页、调试页等特殊流程。

第三步，只挑一个模块跟到底。例如 `settings`：

```ts
path: 'settings'
  index -> redirect '/settings/profile'
  path: 'provider'
    index -> redirect '/settings/provider/all'
    path: ':providerId'
  path: ':tab'
  path: ':tab/:sub'
```

这样可以快速理解 React Router 的嵌套路由写法。

第四步，再看复杂模块，比如 `agent`。`agent` 里同时有：

- `:aid`
- `:topicId`
- `page`
- `:docId`
- `profile`
- `channel`
- `task/:taskId`

这个模块体现了聊天页的多层嵌套结构：Agent layout 下面再套 chat layout，再根据 topic、page、doc 等参数渲染不同页面。

第五步，看 `handle.meta`。例如：

```ts
handle: {
  meta: routeMeta({ icon: Home, titleKey: 'navigation.home' }),
}
```

它不是 React Router 渲染页面必须的字段，而是项目自定义的路由元信息。读到这里要联想到 `src/spa/router/routeMeta.ts` 中的 `RouteMeta` 类型，以及导航、标签页、标题显示等上层 UI。

第六步，看同目录的 `desktopRouter.sync.test.tsx`。这个测试会帮助你理解为什么有两个桌面路由配置文件：

- `desktopRouter.config.tsx`：动态 import 版本
- `desktopRouter.config.desktop.tsx`：同步 import 版本

两者 route tree 必须保持一致，否则可能出现某端路径缺失、空白页、标签元信息不一致等问题。

## 常见误区

第一个误区：以为这个文件实现页面 UI。

它只注册路由，不负责页面业务逻辑。真正页面在 `src/routes/`，更深的业务组件通常在 `src/features/`。例如 `/page/:id` 在这里对应：

```ts
@/routes/(main)/page/[id]
```

但 Pages 模块的实际标题、布局、列表、编辑逻辑大概率在 `src/features/Pages/`、`src/features/PageExplorer/` 等目录中。

第二个误区：把 `dynamicElement` 和 `dynamicLayout` 当成普通函数调用组件。

它们返回的是 React element，并且内部使用 `React.lazy` 和 `Suspense`。因此这里写的是：

```ts
element: dynamicElement(...)
```

而不是：

```tsx
element: <SomePage />
```

这套写法的目的是让路由配置保持声明式，同时保留代码分割能力。

第三个误区：认为 `path: ':tab/:sub'` 是真实目录名。

这里的 `:tab`、`:sub` 是动态路由参数，不是文件夹名。对应页面仍然是：

```ts
@/routes/(main)/settings
```

注释也说明了：像 `/settings/messenger/discord` 这类二级设置页复用同一个 tab page，内部 feature 组件通过 `useParams()` 读取 `:sub`。

第四个误区：忽略 `index: true`。

`index: true` 表示父路径自身命中时使用的默认子路由。例如：

```ts
/settings -> redirectElement('/settings/profile')
/settings/provider -> redirectElement('/settings/provider/all')
/page -> 页面首页
```

它不是 `path: ''` 的简单替代，而是 React Router 的 index route 语义。

第五个误区：改当前文件时忘记同步 `desktopRouter.config.desktop.tsx`。

虽然本任务不修改文件，但阅读时必须知道这个约束。项目的 `desktopRouter.sync.test.tsx` 会校验两个桌面配置的路径、index route 数量和 `handle.meta`。新增、删除、改名任何桌面路由，都应该同时维护两个文件，否则可能造成 web 和 desktop 行为不一致。

第六个误区：以为 `handle.meta` 只是装饰信息。

`handle.meta` 会被应用的导航、标签页、标题或动态元信息系统读取。它可能包含静态图标和 i18n key，也可能通过 `useDynamicMeta`、`createNewTab` 等扩展行为影响标签创建和显示。删除或漏配 `handle.meta` 可能不会让页面立刻崩溃，但会影响导航体验。

第七个误区：把所有路由都放在主布局下。

本文件刻意区分主布局内外：

- 主布局内：聊天、设置、资源、记忆、评测、页面等主应用功能
- 主布局外：分享页、onboarding、devtools、业务扩展的无主布局路由

如果特殊流程错误地放到主布局下，可能会多出侧边栏、全局 shell 或不该出现的应用框架。

第八个误区：忽视 `BusinessDesktopRoutesWithMainLayout` 和 `BusinessDesktopRoutesWithoutMainLayout`。

这两个扩展点说明路由树不是完全由开源核心写死的。根据当前片段推断，业务侧或云端版本可以通过 `@/business/client/BusinessDesktopRoutes` 注入额外路由。阅读完整路由表时，不能只看这个文件里的字面 route，还要知道这里存在外部拼接。
