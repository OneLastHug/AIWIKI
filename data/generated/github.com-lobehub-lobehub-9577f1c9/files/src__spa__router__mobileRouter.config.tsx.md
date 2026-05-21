# 文件：src/spa/router/mobileRouter.config.tsx

## 它负责什么

`src/spa/router/mobileRouter.config.tsx` 是 LobeHub SPA 移动端入口的路由表。它导出：

```ts
export const mobileRoutes: RouteObject[] = [...]
```

这个数组会被 `src/spa/entry.mobile.tsx` 引入，并传给 `createAppRouter(mobileRoutes)`，最终由 `react-router-dom` 的 `<RouterProvider />` 渲染移动端 SPA。

它的核心职责可以概括为三点：

1. 定义移动端 URL 到页面组件的映射关系，例如 `/agent/:aid`、`/settings`、`/community`、`/me`、`/share/t/:id`。
2. 给不同路由挂载不同布局，例如移动端全局布局、聊天布局、设置布局、发现页列表/详情布局、任务工作区布局。
3. 通过 `dynamicElement` / `dynamicLayout` 做懒加载，把页面和布局拆成按需加载的 chunk，降低移动端首屏负担。

这个文件只做“路由声明”，不直接实现页面 UI。真正的页面组件主要放在 `src/routes/` 下，复杂业务 UI 会继续下沉到 `src/features/`。这符合仓库的 SPA 约定：`src/spa/router/` 负责路由配置，`src/routes/` 负责页面段，`src/features/` 负责业务实现。

## 关键组成

### 顶部 imports

```ts
import type { RouteObject } from 'react-router-dom';
```

`RouteObject` 是 React Router 的路由配置类型，说明 `mobileRoutes` 是一棵数据化路由树。

```ts
import {
  BusinessMobileRoutesWithMainLayout,
  BusinessMobileRoutesWithoutMainLayout,
} from '@/business/client/BusinessMobileRoutes';
```

这两个是业务版扩展插槽。当前源码片段中它们都是空数组：

```ts
export const BusinessMobileRoutesWithMainLayout: RouteObject[] = [];
export const BusinessMobileRoutesWithoutMainLayout: RouteObject[] = [];
```

但它们的存在说明这个路由表预留了“业务定制路由”的扩展位置：

- `BusinessMobileRoutesWithMainLayout` 会被插入到移动端主布局之内。
- `BusinessMobileRoutesWithoutMainLayout` 会被插入到主布局之外。

```ts
import {
  mobileAgentSettingsRouteMeta,
  shareTopicRouteMeta,
} from '@/features/RouteMeta/mobileRouteMeta';
import { agentRouteMeta } from '@/routes/(main)/agent/features/routeMeta';
```

这些是路由元信息，挂在 `handle.meta` 上。它们不会直接渲染页面，而是给导航、标题、标签页、动态标题等上层能力提供信息。例如：

- `agentRouteMeta` 可以根据 `aid`、`topicId` 生成会话标题、头像、背景色，并支持新建话题标签页。
- `mobileAgentSettingsRouteMeta` 用于移动端 Agent 设置页标题。
- `shareTopicRouteMeta` 会根据分享 ID 请求共享话题标题。

```ts
import { dynamicElement, dynamicLayout, ErrorBoundary, redirectElement } from '@/utils/router';
```

这些是路由配置中的核心工具：

- `dynamicElement(importFn, debugId)`：懒加载页面组件，并包一层 `Suspense` 加载态。
- `dynamicLayout(importFn, debugId)`：懒加载布局组件，语义上用于承载子路由。
- `ErrorBoundary`：路由级错误边界，支持 chunk 加载失败时提示错误。
- `redirectElement(to)`：返回 `<Navigate replace to={to} />`，用于声明式重定向。

### 根路由 `/`

`mobileRoutes` 的第一项是移动端主应用路由：

```ts
{
  children: [...],
  element: dynamicLayout(() => import('@/routes/(mobile)/_layout'), 'Mobile > Main > Layout'),
  errorElement: <ErrorBoundary />,
  path: '/',
}
```

它表示：大多数移动端页面都包在 `@/routes/(mobile)/_layout` 这个主布局下面。这个主布局外层还会被 `createAppRouter` 自动包上全局的 `RouterRoot`，也就是：

```tsx
<SPAGlobalProvider>
  <BusinessGlobalProvider>
    <NavigatorRegistrar />
    <Outlet />
  </BusinessGlobalProvider>
</SPAGlobalProvider>
```

所以移动端页面实际处在三层上下文里：

1. `createAppRouter` 的全局 SPA Provider。
2. `mobileRouter.config.tsx` 里的移动端主布局。
3. 各业务页面自己的局部布局。

### Chat routes

聊天相关路由挂在 `/agent` 下：

```ts
path: 'agent'
```

内部关键路径包括：

- `/agent`：重定向到 `/`。
- `/agent/:aid`：进入某个 Agent 的默认聊天页。
- `/agent/:aid/:topicId`：进入某个 Agent 下的指定话题。
- `/agent/:aid/settings`：进入移动端 Agent 设置页。

其中 `:aid` 这一层挂了聊天布局：

```ts
element: dynamicLayout(
  () => import('@/routes/(mobile)/chat/_layout'),
  'Mobile > Chat > Layout',
)
```

聊天页和话题页都使用：

```ts
handle: { meta: agentRouteMeta }
```

设置页使用：

```ts
handle: { meta: mobileAgentSettingsRouteMeta }
```

也就是说，路由路径不仅决定页面，还会给上层导航系统提供“这个页面代表哪个 Agent / Topic / Settings”的动态元数据。

### Community / Discover routes

发现页挂在 `/community` 下。它分成两组：

1. 列表页 routes。
2. 详情页 routes。

列表页使用移动端列表布局：

```ts
element: dynamicElement(
  () => import('@/routes/(mobile)/community/(list)/_layout'),
  'Mobile > Discover > List > Layout',
)
```

列表页中复用了主站社区页面：

- `/community` -> `@/routes/(main)/community/(list)/(home)`
- `/community/agent` -> `@/routes/(main)/community/(list)/agent`
- `/community/model` -> `@/routes/(main)/community/(list)/model`
- `/community/provider` -> `@/routes/(main)/community/(list)/provider`
- `/community/mcp` -> `@/routes/(main)/community/(list)/mcp`

详情页也挂在 `/community` 下，但使用移动端详情布局：

```ts
element: dynamicElement(
  () => import('@/routes/(mobile)/community/(detail)/_layout'),
  'Mobile > Discover > Detail > Layout',
)
```

详情页路径包括：

- `/community/agent/:slug`
- `/community/model/:slug`
- `/community/provider/:slug`
- `/community/mcp/:slug`
- `/community/user/:slug`

这里有一个重要细节：详情页很多模块不是直接使用 default export，而是从主站页面模块里取移动端专用导出：

```ts
import('@/routes/(main)/community/(detail)/agent').then(
  (m) => m.MobileDiscoverAssistantDetailPage,
)
```

这说明同一个 route module 可能同时服务桌面端和移动端，移动端通过命名导出拿到适配版本。

### Settings routes

设置页挂在 `/settings` 下：

- `/settings`：移动端设置首页。
- `/settings/provider`：重定向到 `/settings/provider/all`。
- `/settings/provider/:providerId`：Provider 详情页。
- `/settings/:tab`：通用设置 tab，例如 common、agent、memory、tts、about 等。

设置页有两层布局：

```ts
element: dynamicLayout(
  () => import('@/routes/(mobile)/settings/_layout'),
  'Mobile > Settings > Layout',
)
```

Provider 子路由再套一层：

```ts
element: dynamicLayout(
  () => import('@/routes/(mobile)/settings/provider/_layout'),
  'Mobile > Settings > Provider > Layout',
)
```

Provider 详情页复用主站设置模块里的命名导出：

```ts
import('@/routes/(main)/settings/provider').then((m) => m.ProviderDetailPage)
```

根据当前片段推断，移动端设置页不是完全独立实现，而是在移动端布局下复用部分主站设置页面能力。

### Task workspace routes

任务工作区路由包括：

- `/tasks`
- `/task/:taskId`
- `/agent/:aid/task/:taskId`

它们统一挂在共享任务工作区布局下：

```ts
element: dynamicLayout(
  () => import('@/routes/(main)/(task-workspace)/_layout'),
  'Mobile > Task Workspace > Layout',
)
```

对应页面包括：

```ts
@/routes/(main)/tasks
@/routes/(main)/task/[taskId]
@/routes/(main)/agent/task/[taskId]
```

这个设计被 `src/spa/router/mobileRouter.test.tsx` 明确保护。测试会检查这些 import 和 path 是否存在，并确保没有错误地使用 `@/routes/(main)/tasks/_layout`。也就是说，移动端任务路由被要求共享 `(task-workspace)` 这个上层布局，而不是单独挂任务列表布局。

### Business mobile routes

```ts
...BusinessMobileRoutesWithMainLayout
```

这一段位于移动端主布局内部。业务定制路由插在这里，就会自动享受 `@/routes/(mobile)/_layout` 主布局。

```ts
...BusinessMobileRoutesWithoutMainLayout
```

这一段位于主布局之外。适合登录、活动页、特殊落地页等不需要移动端主框架的业务路由。

当前开源片段里这两个数组为空，但结构说明企业版或业务构建可以在这里注入额外移动端页面。

### Me routes

个人中心挂在 `/me` 下：

- `/me`
- `/me/profile`
- `/me/settings`

每一组都使用自己的移动端布局：

```ts
@/routes/(mobile)/me/(home)/layout
@/routes/(mobile)/me/profile/layout
@/routes/(mobile)/me/settings/layout
```

页面组件分别是：

```ts
@/routes/(mobile)/me/(home)
@/routes/(mobile)/me/profile
@/routes/(mobile)/me/settings
```

这说明个人中心不是一个单一页面，而是一个带多个子页面和局部布局的移动端区域。

### Home route

默认首页是根路径 `/` 下的 index route：

```ts
{
  children: [
    {
      element: dynamicElement(() => import('@/routes/(mobile)/(home)/'), 'Mobile > Home'),
      index: true,
    },
  ],
  element: dynamicLayout(
    () => import('@/routes/(mobile)/(home)/_layout'),
    'Mobile > Home > Layout',
  ),
}
```

当用户访问 `/`，会进入移动端主布局，然后进入首页布局，最后渲染首页页面。

### Catch-all route

```ts
{
  element: redirectElement('/'),
  path: '*',
}
```

主布局内部没有匹配到的路径会被重定向回 `/`。这避免移动端出现空白页或默认 404 页面。

### Onboarding routes

Onboarding 路由位于主布局之外：

- `/onboarding`
- `/onboarding/agent`
- `/onboarding/classic`

它们直接放在 `mobileRoutes` 顶层，而不是 `/` 主路由的 children 中。这意味着它们不会套用移动端主布局。

这是合理的：引导流程通常需要独立页面结构，不一定需要主导航或常规应用框架。

### Share topic route

分享话题路径是：

```ts
/share/t/:id
```

它也在主布局之外，使用自己的 layout：

```ts
@/routes/share/t/[id]/_layout
```

页面为：

```ts
@/routes/share/t/[id]
```

并挂载：

```ts
handle: { meta: shareTopicRouteMeta }
```

`shareTopicRouteMeta` 会根据 `params.id` 调用：

```ts
lambdaClient.share.getSharedTopic.query({ shareId })
```

拿到分享话题标题，用于动态页面标题或导航展示。

## 上下游关系

### 上游：移动端入口

直接调用方是：

```ts
src/spa/entry.mobile.tsx
```

调用链如下：

```ts
import { mobileRoutes } from './router/mobileRouter.config';

const router = createAppRouter(mobileRoutes);

createRoot(document.getElementById('root')!).render(<RouterProvider router={router} />);
```

也就是说，这个文件不是被页面组件调用，而是被移动端 SPA 启动入口消费。只要移动端入口启动，整个 `mobileRoutes` 路由树就会成为 React Router 的匹配依据。

### 上游：createAppRouter

`createAppRouter` 定义在：

```ts
src/utils/router.tsx
```

它会把传入的 routes 包在一个根路由下面：

```ts
createBrowserRouter([
  {
    children: routes,
    element: <RouterRoot />,
    errorElement: <ErrorBoundary />,
    path: '/',
  },
])
```

因此 `mobileRoutes` 不是浏览器路由的最外层唯一根；它会成为 `RouterRoot` 的 children。

`RouterRoot` 提供：

- `SPAGlobalProvider`
- `BusinessGlobalProvider`
- `NavigatorRegistrar`
- `<Outlet />`

这意味着 `mobileRouter.config.tsx` 下所有页面都默认具备 SPA 全局上下文、业务全局上下文，以及全局导航引用注册能力。

### 下游：页面和布局模块

`mobileRouter.config.tsx` 的下游主要是 `src/routes/` 下的页面段，例如：

- `src/routes/(mobile)/_layout`
- `src/routes/(mobile)/chat`
- `src/routes/(mobile)/chat/_layout`
- `src/routes/(mobile)/settings`
- `src/routes/(mobile)/settings/_layout`
- `src/routes/(mobile)/community/_layout`
- `src/routes/(main)/community/(list)/(home)`
- `src/routes/(main)/community/(detail)/agent`
- `src/routes/(main)/tasks`
- `src/routes/share/t/[id]`

根据 SPA 路由规范，`src/routes/` 中的文件应该尽量保持薄，只做页面段和布局组合；真正复杂的业务逻辑和 UI 应继续放入 `src/features/`。

### 下游：路由元信息消费方

本文件通过 `handle: { meta: ... }` 给部分路由挂载元信息。元信息结构由 `src/spa/router/routeMeta.ts` 定义：

```ts
export interface RouteMeta {
  createNewTab?: (params: Record<string, string | undefined>) => NewTabAction | null;
  useDynamicMeta?: (params: Record<string, string | undefined>) => DynamicRouteMeta;
  icon?: LucideIcon;
  titleKey?: string;
}
```

`getRouteMetaFromHandle(handle)` 可以从 React Router 的 `handle` 中取出这些 meta。根据当前片段推断，应用内的导航栏、标签页标题、页面标题或移动端 header 可能会读取这些 meta，因为 meta 包含 `titleKey`、`icon`、动态标题、头像、背景色、新建标签页动作等信息。

### 测试约束

相关测试文件是：

```ts
src/spa/router/mobileRouter.test.tsx
```

当前测试重点保护任务路由：

- 必须注册 `@/routes/(main)/(task-workspace)/_layout`
- 必须注册 `@/routes/(main)/tasks`
- 必须注册 `@/routes/(main)/task/[taskId]`
- 必须注册 `@/routes/(main)/agent/task/[taskId]`
- 必须包含 `tasks`、`task`、`:taskId`、`:aid/task/:taskId` 等 path
- 不能错误引用 `@/routes/(main)/tasks/_layout`

这说明任务工作区路由是一个曾经容易改错的区域，阅读或修改时需要特别注意。

## 运行/调用流程

以访问 `/agent/abc/topic123` 为例，流程大致如下：

1. 浏览器加载移动端 SPA 入口 `src/spa/entry.mobile.tsx`。
2. `entry.mobile.tsx` 引入 `mobileRoutes`。
3. `createAppRouter(mobileRoutes)` 创建 React Router data router。
4. `<RouterProvider router={router} />` 开始根据当前 URL 匹配路由。
5. 最外层先命中 `createAppRouter` 创建的根路由 `/`，渲染 `RouterRoot`。
6. `RouterRoot` 渲染全局 Provider 和 `<Outlet />`。
7. 进入 `mobileRoutes` 的主路由 `/`，渲染 `@/routes/(mobile)/_layout`。
8. 匹配 `agent` 子路由。
9. 匹配 `:aid`，这里 `aid = "abc"`，渲染 `@/routes/(mobile)/chat/_layout`。
10. 继续匹配 `:topicId`，这里 `topicId = "topic123"`，渲染 `@/routes/(mobile)/chat`。
11. 页面 route 上的 `handle.meta = agentRouteMeta` 可被上层读取，用 `aid` 和 `topicId` 生成动态标题、头像等信息。

以访问 `/share/t/share001` 为例：

1. 路由不会进入移动端主布局 `/` 的 children。
2. 顶层直接匹配 `/share/t`。
3. 渲染 `@/routes/share/t/[id]/_layout`。
4. 子路由匹配 `:id`，这里 `id = "share001"`。
5. 渲染 `@/routes/share/t/[id]`。
6. `shareTopicRouteMeta` 通过 `id` 请求共享话题数据，动态生成标题。

以访问未知路径 `/unknown/path` 为例：

1. 如果这个路径落在主布局匹配范围内但没有更具体的子路由命中，会匹配：

```ts
{
  element: redirectElement('/'),
  path: '*',
}
```

2. `redirectElement('/')` 返回 `<Navigate replace to="/" />`。
3. 用户被重定向到移动端首页。

## 小白阅读顺序

1. 先看 `src/spa/entry.mobile.tsx`  
   理解 `mobileRoutes` 是怎么被启动入口使用的。重点看这三行：导入 `mobileRoutes`、调用 `createAppRouter`、渲染 `RouterProvider`。

2. 再看 `src/utils/router.tsx`  
   理解 `dynamicElement`、`dynamicLayout`、`redirectElement`、`ErrorBoundary` 分别是什么。尤其要知道：`dynamicElement` 和 `dynamicLayout` 都是懒加载组件，不是普通函数调用页面。

3. 回到 `src/spa/router/mobileRouter.config.tsx` 看顶层结构  
   先不要逐行看所有页面，先识别大分区：
   - `/` 主布局内的移动端应用页面
   - `/onboarding` 引导页
   - 业务扩展路由
   - `/share/t/:id` 分享页

4. 再按业务块阅读主布局 children  
   推荐顺序：
   - Home：理解默认首页怎么匹配。
   - Chat：理解 `/agent/:aid/:topicId?`。
   - Settings：理解设置页和 Provider 子路由。
   - Community：理解列表页和详情页两套路由。
   - Tasks：理解共享任务工作区布局。
   - Me：理解个人中心分组。
   - Catch-all：理解兜底重定向。

5. 最后看 route meta  
   阅读：
   - `src/features/RouteMeta/mobileRouteMeta.ts`
   - `src/routes/(main)/agent/features/routeMeta.ts`
   - `src/spa/router/routeMeta.ts`

   重点理解 `handle: { meta }` 不是页面渲染本身，而是给导航、标题、标签页等系统提供附加信息。

6. 如果要继续深挖页面实现，再跳到具体 route 文件  
   例如你关心聊天页，就从：

```ts
src/routes/(mobile)/chat
src/routes/(mobile)/chat/_layout
```

继续往下看。按照仓库约定，如果 route 文件里只是导入和组合，那真正实现还要去 `src/features/` 下找。

## 常见误区

1. 误以为这个文件会渲染页面 UI  
   实际上它只声明路由树。页面 UI 在 `src/routes/` 和 `src/features/` 中。这里的 `element` 是“懒加载后的组件元素”，不是业务逻辑实现。

2. 误把 `dynamicElement` 和 `dynamicLayout` 当成有本质区别的 React Router API  
   它们是项目自定义工具，底层都是 `React.lazy + Suspense`。区别主要是语义：前者用于页面，后者用于布局。布局组件通常需要在内部渲染 `<Outlet />`，否则子路由页面不会显示。

3. 误以为所有移动端页面都在 `src/routes/(mobile)`  
   不完全是。移动端路由大量复用了 `src/routes/(main)` 下的页面或命名导出，例如社区列表、社区详情、设置 Provider、任务页等。移动端不一定有独立文件，可能只是复用主站模块里的移动端导出。

4. 误以为 `/onboarding` 和 `/share/t/:id` 会套移动端主布局  
   它们是 `mobileRoutes` 顶层路由，位于主布局 `/` 的外面。它们只会被 `createAppRouter` 的全局 `RouterRoot` 包住，不会自动使用 `@/routes/(mobile)/_layout`。

5. 误改任务路由布局  
   `mobileRouter.test.tsx` 明确要求任务列表和详情使用：

```ts
@/routes/(main)/(task-workspace)/_layout
```

不能改成：

```ts
@/routes/(main)/tasks/_layout
```

这是测试保护的行为，说明这里对布局层级有明确要求。

6. 误以为 `BusinessMobileRoutesWithMainLayout` 和 `BusinessMobileRoutesWithoutMainLayout` 是无用代码  
   当前片段中它们为空，但它们是业务扩展插槽。一个插在移动端主布局内，一个插在主布局外。删除或移动它们可能影响商业版、私有部署或构建时扩展能力。

7. 误把 `handle.meta` 当成 React props  
   `handle` 是 React Router 路由对象上的自定义字段。页面组件不会自动收到这些 meta。需要通过路由匹配结果或项目里的 `getRouteMetaFromHandle` 等工具读取。

8. 误认为 `path: '/'` 下面的子路径都要写绝对路径  
   在 React Router 的嵌套路由中，children 里的 `path: 'agent'`、`path: 'settings'` 都是相对父路由的路径。只有顶层独立路由如 `/onboarding`、`/share/t` 使用了绝对路径。

9. 误认为 index route 和空 path 一样  
   `index: true` 表示“父路径完全匹配时渲染这个默认子页面”。例如 `/settings` 命中设置布局后，会渲染设置首页；`/settings/:tab` 则是另一个子路由。

10. 误忽略错误边界  
   多个业务块都配置了：

```tsx
errorElement: <ErrorBoundary />
```

任务详情还配置了不同的 `resetPath`。这会影响错误页里的返回路径和 chunk 加载失败处理，不只是装饰性代码。
