# 文件：src/utils/router.tsx

## 它负责什么

`src/utils/router.tsx` 是 LobeHub SPA 路由层的公共工具文件，主要负责把 `react-router-dom` 的基础能力包装成项目统一使用的路由工具。

它解决了几类问题：

1. **统一创建 SPA Router**
   通过 `createAppRouter(routes, options)` 把桌面端、移动端、弹窗端等不同路由配置包装成一个完整的 `createBrowserRouter` 实例，并在最外层挂载全局 Provider、全局错误边界和根布局。

2. **统一处理路由级懒加载**
   `dynamicElement` 和 `dynamicLayout` 用 `React.lazy` + `Suspense` 包装动态导入的页面或布局组件，让路由配置可以直接写：

   ```tsx
   element: dynamicElement(() => import('@/routes/(main)/agent'), 'Desktop > Chat')
   ```

   而不需要每个页面都单独声明一个 `const XxxPage = lazy(...)`。

3. **统一处理路由错误**
   `ErrorBoundary` 使用 `useRouteError()` 获取 React Router 捕获到的错误，然后交给项目通用的 `ErrorCapture` 展示。如果错误是 chunk 加载失败，还会调用 `notifyChunkError()` 做专门提示。

4. **把 React Router 的 `navigate` 同步到全局 store**
   `NavigatorRegistrar` 在 Router 内部调用 `useNavigate()`，再把得到的 `navigate` 写入 `useGlobalStore` 的 `navigationRef`。这样一些非 React Hook 环境也能通过 `getStableNavigate()` 拿到稳定导航函数。

5. **提供路由跳转元素和预加载工具**
   `redirectElement(to)` 用 `<Navigate replace />` 实现声明式重定向。
   `prefetchRoute(path)` 在用户 hover 导航项时提前加载对应路由 layout chunk，减少真正点击时的等待。

整体来看，这个文件不是某个页面的业务代码，而是 SPA 路由系统的“基础设施层”。

## 关键组成

### 顶部依赖

这个文件声明了 `'use client'`，说明它只在客户端环境使用。它依赖的核心模块包括：

- `react`
  使用 `lazy`、`Suspense`、`memo`、`useLayoutEffect` 等客户端渲染能力。

- `react-router-dom`
  使用 `createBrowserRouter`、`Navigate`、`Outlet`、`useNavigate`、`useRouteError` 和 `RouteObject`。

- `@lobehub/ui`
  在错误边界里使用 `ThemeProvider`，保证错误页也能拿到 CSS 变量主题。

- `@/layout/SPAGlobalProvider`
  SPA 根级 Provider。

- `@/business/client/BusinessGlobalProvider`
  业务侧全局 Provider。

- `@/store/global`
  用于写入 `navigationRef`。

- `@/store/global/initialState`
  提供 `createNavigationRef()`，用于卸载时重置导航引用。

- `@/utils/chunkError`
  用于识别和处理 chunk 加载失败。

- `@/components/Error`
  路由错误展示组件。

- `@/components/Loading/BrandTextLoading`
  懒加载 fallback 组件。

这些 import 表明：`router.tsx` 处在“React Router + 全局 Provider + 全局状态 + 错误处理”的交叉点上。

### `importModule`

```ts
async function importModule<T>(importFn: () => Promise<T>): Promise<T> {
  return importFn();
}
```

这是一个很薄的包装函数，目前只是直接执行传入的动态 import 函数。

它的作用更多是结构上的：让 `dynamicElement` 和 `dynamicLayout` 内部都通过统一入口执行动态导入。以后如果要在动态导入前后加监控、日志、异常包装，也可以集中放到这里。

### `resolveLazyModule`

```ts
function resolveLazyModule<P>(module: { default: ComponentType<P> } | ComponentType<P>) {
  ...
}
```

这个函数负责把动态导入结果标准化成 React.lazy 需要的格式：

```ts
{ default: Component }
```

它处理了几种情况：

1. `module == null`
   直接抛错：

   ```ts
   Dynamic import resolved to undefined. This usually means a chunk failed to load.
   ```

   这说明项目明确把“动态 import 得到 undefined”视作 chunk 加载失败或构建产物异常。

2. `typeof module === 'function'`
   如果导入结果本身就是组件函数，则包装成：

   ```ts
   { default: module }
   ```

3. `'default' in module`
   如果是标准 ES module 默认导出，则直接返回。

4. 其他情况
   兜底把 module 强转成组件：

   ```ts
   return { default: module as unknown as ComponentType<P> };
   ```

这个函数让项目的动态路由导入更宽容：既支持 `export default Component`，也兼容直接返回组件的形式。

### `dynamicElement`

```ts
export function dynamicElement<P = NonNullable<unknown>>(
  importFn: () => Promise<{ default: ComponentType<P> } | ComponentType<P>>,
  debugId?: string,
): ReactElement
```

`dynamicElement` 用于创建懒加载页面元素。

核心逻辑：

1. 用 `lazy(async () => { ... })` 创建 `LazyComponent`。
2. 调用 `importModule(importFn)` 执行动态导入。
3. 调用 `resolveLazyModule(mod)` 标准化模块格式。
4. 返回：

   ```tsx
   <Suspense fallback={<Loading debugId={debugId || 'dynamicElement'} />}>
     <LazyComponent {...({} as P)} />
   </Suspense>
   ```

它的主要调用场景是路由配置里的普通页面：

```tsx
element: dynamicElement(() => import('@/routes/(main)/agent'), 'Desktop > Chat')
```

`debugId` 会传给 `Loading`，用于标识当前正在加载哪个动态页面。比如路由配置中常见 `"Desktop > Chat"`、`"Mobile > Settings"` 这类字符串。

需要注意的是，函数内部有两个 `// @ts-ignore`。这说明这里为了让“泛型组件 + 空 props + React.lazy”组合顺利通过，牺牲了一部分类型严格性。根据当前片段推断，项目更看重路由配置书写简洁，而不是在这里严格校验每个懒加载页面的 props。

### `dynamicLayout`

```ts
export function dynamicLayout<P = NonNullable<unknown>>(
  importFn: () => Promise<{ default: ComponentType<P> } | ComponentType<P>>,
  debugId?: string,
): ReactElement
```

`dynamicLayout` 和 `dynamicElement` 几乎一样，只是语义上用于 layout。

注释里写到：

> Unlike dynamicElement (for pages), layouts use Outlet so children are rendered inside.

也就是说，`dynamicLayout` 加载的组件一般是路由布局组件，布局组件内部会通过 `<Outlet />` 渲染子路由。

但从当前实现看，`dynamicLayout` 本身并没有自动注入 `<Outlet />`，它只是加载 layout 组件。真正的 `<Outlet />` 需要 layout 文件自己处理。

所以这里要区分：

- `dynamicLayout`：声明“这是一个懒加载布局组件”的工具。
- 具体 layout 组件：负责实际渲染自己的结构和 `<Outlet />`。

### `ErrorBoundary`

```tsx
export const ErrorBoundary = ({ resetPath }: ErrorBoundaryProps) => {
  const error = useRouteError() as Error;

  if (typeof window !== 'undefined' && isChunkLoadError(error)) {
    notifyChunkError();
  }

  return (
    <ThemeProvider theme={{ cssVar: { key: 'lobe-vars' } }}>
      <ErrorCapture error={error} resetPath={resetPath} />
    </ThemeProvider>
  );
};
```

这是 React Router 的路由级错误边界组件。

它接收一个可选参数：

```ts
export interface ErrorBoundaryProps {
  resetPath?: string;
}
```

`resetPath` 表示错误页中“返回首页”或“重置路径”的目标路径，默认由 `ErrorCapture` 自己处理。路由配置里有些地方会指定：

```tsx
errorElement: <ErrorBoundary resetPath="/tasks" />
```

它的核心行为是：

1. 通过 `useRouteError()` 读取路由错误。
2. 如果当前是浏览器环境，并且错误符合 `isChunkLoadError(error)`，则调用 `notifyChunkError()`。
3. 用 `ThemeProvider` 包住 `ErrorCapture`，避免错误页脱离主题变量。
4. 把 `error` 和 `resetPath` 传给 `ErrorCapture`。

这说明项目对“chunk 加载失败”做了特殊处理。常见场景是用户打开旧版本页面，但服务器已经部署了新 chunk，旧 chunk 文件不存在。这类错误和普通运行时错误不同，通常需要提示用户刷新或重新加载。

### `NavigatorRegistrar`

```tsx
export const NavigatorRegistrar = memo(() => {
  const navigate = useNavigate();

  useLayoutEffect(() => {
    useGlobalStore.setState({ navigationRef: { current: navigate } });
    return () => {
      useGlobalStore.setState({ navigationRef: createNavigationRef() });
    };
  }, [navigate]);

  return null;
});
```

`NavigatorRegistrar` 是一个不渲染 UI 的注册组件。

它必须挂在 Router 内部，因为 `useNavigate()` 只能在 Router 上下文中使用。

它的作用是：

1. 读取 React Router 的 `navigate` 函数。
2. 在 layout effect 中写入全局 Zustand store：

   ```ts
   useGlobalStore.setState({ navigationRef: { current: navigate } });
   ```

3. 组件卸载时重置：

   ```ts
   useGlobalStore.setState({ navigationRef: createNavigationRef() });
   ```

相邻文件 `src/utils/stableNavigate.ts` 中有：

```ts
export function getStableNavigate(): NavigateFunction | null {
  return useGlobalStore.getState().navigationRef.current;
}
```

这说明 `NavigatorRegistrar` 和 `getStableNavigate()` 是一组配套机制：

- `NavigatorRegistrar`：在 React Router 内部注册 navigate。
- `getStableNavigate()`：在非 Hook 场景读取 navigate。

适用场景包括 service、store action、事件回调等不方便直接调用 `useNavigate()` 的地方。

`src/store/global/initialState.ts` 中也有注释说明：

```ts
/** Imperative router navigate; see `NavigatorRegistrar` in `src/utils/router.tsx`. */
navigationRef: GlobalNavigationRef;
```

这进一步确认 `navigationRef` 是为命令式导航准备的全局引用。

### `RouterRoot`

```tsx
const RouterRoot = memo(() => (
  <SPAGlobalProvider>
    <BusinessGlobalProvider>
      <NavigatorRegistrar />
      <Outlet />
    </BusinessGlobalProvider>
  </SPAGlobalProvider>
));
```

`RouterRoot` 是所有 SPA 路由的根元素。

它做了三件事：

1. 挂载 `SPAGlobalProvider`。
2. 挂载 `BusinessGlobalProvider`。
3. 挂载 `NavigatorRegistrar`。
4. 渲染 `<Outlet />`，让子路由显示出来。

它被 `createAppRouter` 放在最外层根路由上：

```tsx
{
  children: routes,
  element: <RouterRoot />,
  errorElement: <ErrorBoundary />,
  path: '/',
}
```

这意味着无论桌面端、移动端还是弹窗端，只要通过 `createAppRouter` 创建 router，都会自动获得这套全局 Provider 和导航注册逻辑。

### `createAppRouter`

```ts
export function createAppRouter(routes: RouteObject[], options?: CreateAppRouterOptions) {
  return createBrowserRouter(
    [
      {
        children: routes,
        element: <RouterRoot />,
        errorElement: <ErrorBoundary />,
        path: '/',
      },
    ],
    { basename: options?.basename },
  );
}
```

这是创建 SPA router 的统一入口。

调用方包括：

- `src/spa/entry.web.tsx`
- `src/spa/entry.desktop.tsx`
- `src/spa/entry.mobile.tsx`
- `src/spa/entry.popup.tsx`

例如 `entry.web.tsx` 会传入桌面路由，并可能传入 `basename`：

```ts
const router = createAppRouter(desktopRoutes, { basename });
```

它的设计意义是：各端入口只需要关心“使用哪套路由配置”，不需要重复写根 Provider、根错误边界和 `createBrowserRouter` 结构。

`CreateAppRouterOptions` 目前只有一个字段：

```ts
export interface CreateAppRouterOptions {
  basename?: string;
}
```

`basename` 是 React Router 的基础路径，适合部署在非根路径或特殊代理路径下。

### `redirectElement`

```tsx
export function redirectElement(to: string): ReactElement {
  return <Navigate replace to={to} />;
}
```

这是声明式重定向工具。

注释中写到：

```ts
Replaces loader: () => redirect('/path') in declarative mode
```

也就是说，在当前路由配置风格里，项目不使用 loader 里的 `redirect()` 来跳转，而是直接把某个 route 的 `element` 写成：

```tsx
element: redirectElement('/settings/provider/all')
```

它内部使用 `<Navigate replace />`，意味着重定向会替换当前 history 记录，而不是新增一条记录。用户点击浏览器返回时，不会回到这个中转路由。

### `prefetchRoute`

```ts
const prefetchedRoutes = new Set<string>();

const routePrefetchMap: Record<string, () => Promise<unknown>> = {
  '/agent': () => import('@/routes/(main)/agent/_layout'),
  '/community': () => import('@/routes/(main)/community/_layout'),
  '/group': () => import('@/routes/(main)/group/_layout'),
  '/page': () => import('@/routes/(main)/page/_layout'),
  '/resource': () => import('@/routes/(main)/resource/_layout'),
  '/settings': () => import('@/routes/(main)/settings/_layout'),
};
```

`prefetchRoute(path)` 用来提前加载某些主路由的 layout chunk。

核心逻辑：

```ts
export function prefetchRoute(path: string): void {
  const key = '/' + path.replace(/^\//, '').split('/')[0];
  if (prefetchedRoutes.has(key)) return;
  const loader = routePrefetchMap[key];
  if (loader) {
    prefetchedRoutes.add(key);
    loader();
  }
}
```

它会把传入路径归一化成第一级路径：

- `/settings/provider` -> `/settings`
- `settings/provider` -> `/settings`
- `/agent/abc` -> `/agent`

然后：

1. 如果这个 key 已经预加载过，直接返回。
2. 如果 `routePrefetchMap` 有对应 loader，就记录到 `prefetchedRoutes`。
3. 调用动态 import，触发 chunk 预加载。

调用方主要在首页导航相关组件中，例如：

- `src/routes/(main)/home/_layout/Header/components/Nav.tsx`
- `src/routes/(main)/home/_layout/Body/index.tsx`
- `src/routes/(main)/home/_layout/Footer/index.tsx`
- `src/routes/(main)/home/_layout/Body/Agent/List/AgentItem/index.tsx`
- `src/routes/(main)/home/_layout/Body/Agent/List/InboxItem.tsx`

这些组件一般在 `onMouseEnter` 中调用：

```tsx
onMouseEnter={() => prefetchRoute(item.url!)}
```

这说明预加载策略是“用户鼠标移到导航项上时，提前加载目标路由布局”。

## 上下游关系

### 上游：谁给它输入

`router.tsx` 的直接输入主要有三类。

第一类是 SPA 入口传入的路由配置：

- `desktopRoutes`
- `mobileRoutes`
- `popupRoutes`

这些路由配置来自 `src/spa/router/*.config.tsx`。入口文件调用 `createAppRouter(routes)` 后，再交给 `<RouterProvider router={router} />` 渲染。

第二类是路由配置中的动态 import：

```tsx
dynamicElement(() => import('@/routes/(main)/agent'), 'Desktop > Chat')
dynamicLayout(() => import('@/routes/(main)/_layout'), 'Desktop > Main > Layout')
```

这些 import 指向 `src/routes/` 下的页面段和 layout 文件。

第三类是用户交互传入的路径：

```tsx
prefetchRoute('/settings')
prefetchRoute(agentUrl)
prefetchRoute(inboxUrl)
```

这些路径通常来自导航配置、agent URL 或 inbox URL。

### 下游：它影响谁

`router.tsx` 的下游影响范围比较大。

1. **所有 SPA 页面渲染**
   `createAppRouter` 包住所有 routes，因此桌面、移动、弹窗入口都会经过这里。

2. **路由配置写法**
   `dynamicElement`、`dynamicLayout`、`redirectElement` 让路由配置保持统一风格，避免每个 config 文件重复写 `lazy`、`Suspense`、`Navigate`。

3. **错误页展示**
   所有挂了 `ErrorBoundary` 的路由，在出错时都会进入这里，再由 `ErrorCapture` 负责展示。

4. **全局命令式导航**
   `NavigatorRegistrar` 把 `navigate` 写入 `useGlobalStore`，影响 `src/utils/stableNavigate.ts` 以及所有通过 `getStableNavigate()` 做跳转的非组件代码。

5. **首页导航性能**
   `prefetchRoute` 影响首页导航 hover 后的 chunk 加载时机，目标是缩短点击后的白屏或 loading 时间。

## 运行/调用流程

### SPA 启动流程

以 web 端为例，整体流程是：

1. `src/spa/entry.web.tsx` 导入 `desktopRoutes`。
2. 调用：

   ```ts
   createAppRouter(desktopRoutes, { basename })
   ```

3. `createAppRouter` 内部调用 `createBrowserRouter`。
4. 创建根路由：

   ```tsx
   path: '/'
   element: <RouterRoot />
   errorElement: <ErrorBoundary />
   children: desktopRoutes
   ```

5. 应用通过 `RouterProvider` 渲染 router。
6. `RouterRoot` 被挂载。
7. `SPAGlobalProvider` 和 `BusinessGlobalProvider` 生效。
8. `NavigatorRegistrar` 执行 `useNavigate()`，把 `navigate` 写入全局 store。
9. `<Outlet />` 根据当前 URL 渲染匹配到的子路由。

### 页面懒加载流程

当用户访问某个配置了 `dynamicElement` 的页面时：

1. React Router 匹配到对应 route。
2. route 的 `element` 是 `dynamicElement(...)` 返回的 ReactElement。
3. `Suspense` 先显示：

   ```tsx
   <Loading debugId="..." />
   ```

4. `React.lazy` 执行动态 import。
5. `importModule(importFn)` 调用真正的 `import(...)`。
6. `resolveLazyModule(mod)` 把导入结果转成 `{ default: Component }`。
7. chunk 加载完成后，`LazyComponent` 渲染真实页面组件。

如果动态 import 失败或返回异常，错误会沿 React Router 错误边界进入 `ErrorBoundary`。

### 路由错误处理流程

当某个 route 渲染或加载时出错：

1. React Router 捕获错误。
2. 渲染对应层级的 `errorElement`。
3. `ErrorBoundary` 调用 `useRouteError()` 得到错误对象。
4. 如果是 chunk 加载错误：
   调用 `notifyChunkError()`。
5. 渲染：

   ```tsx
   <ThemeProvider>
     <ErrorCapture error={error} resetPath={resetPath} />
   </ThemeProvider>
   ```

6. 用户看到项目统一错误页。

### 命令式导航注册流程

1. `RouterRoot` 挂载 `NavigatorRegistrar`。
2. `NavigatorRegistrar` 在 Router 上下文中调用 `useNavigate()`。
3. `useLayoutEffect` 写入：

   ```ts
   useGlobalStore.setState({ navigationRef: { current: navigate } });
   ```

4. 其他地方调用 `getStableNavigate()`。
5. `getStableNavigate()` 从 `useGlobalStore.getState().navigationRef.current` 读取 navigate。
6. 非组件代码也能执行页面跳转。

组件卸载时，`NavigatorRegistrar` 会把 `navigationRef` 重置成 `createNavigationRef()`，避免保留失效引用。

### 路由预加载流程

以首页导航 hover `/settings/provider` 为例：

1. 用户鼠标移到设置入口。
2. 组件调用：

   ```ts
   prefetchRoute('/settings/provider')
   ```

3. `prefetchRoute` 提取第一级 path：

   ```ts
   key = '/settings'
   ```

4. 检查 `prefetchedRoutes` 是否已有 `/settings`。
5. 如果没有，查找：

   ```ts
   routePrefetchMap['/settings']
   ```

6. 找到 loader：

   ```ts
   () => import('@/routes/(main)/settings/_layout')
   ```

7. 标记 `/settings` 已预加载。
8. 执行动态 import。
9. 用户真正点击时，layout chunk 可能已经在浏览器缓存中，进入页面更快。

## 小白阅读顺序

建议按下面顺序读，不要一上来就看完整路由配置，因为配置文件很长，容易迷路。

1. 先读 `createAppRouter`
   这是入口函数。理解它如何把外部传入的 `routes` 包成根路由。

2. 再读 `RouterRoot`
   看清楚所有页面外层都会包哪些 Provider，以及 `<Outlet />` 在哪里渲染子路由。

3. 再读 `dynamicElement`
   理解普通页面如何懒加载。

4. 再读 `dynamicLayout`
   对比它和 `dynamicElement`。实现几乎一样，但语义不同：一个用于页面，一个用于布局。

5. 再读 `ErrorBoundary`
   搞懂路由错误如何交给 `ErrorCapture`，以及为什么 chunk 加载错误要特殊处理。

6. 再读 `NavigatorRegistrar`
   理解为什么它必须在 Router 内部，以及它如何把 `navigate` 放进全局 store。

7. 再读 `redirectElement`
   这是最简单的工具，用来替代 loader redirect。

8. 最后读 `prefetchRoute`
   这部分和页面性能有关。重点看 `routePrefetchMap` 和第一级路径提取逻辑。

读完本文件后，可以继续看这些调用方：

- `src/spa/entry.web.tsx`
  看 web 入口如何创建 router。

- `src/spa/entry.desktop.tsx`
  看桌面入口如何复用同一个 `createAppRouter`。

- `src/spa/router/desktopRouter.config.tsx`
  看 `dynamicElement`、`dynamicLayout`、`redirectElement` 在大型路由配置中的真实使用方式。

- `src/spa/router/mobileRouter.config.tsx`
  对比移动端路由配置。

- `src/utils/stableNavigate.ts`
  看全局 `navigationRef` 如何被读取。

- `src/routes/(main)/home/_layout/Header/components/Nav.tsx`
  看 `prefetchRoute` 如何绑定到 hover 交互。

## 常见误区

### 误区一：以为 `dynamicLayout` 会自动渲染 `<Outlet />`

不会。

`dynamicLayout` 只是把 layout 组件懒加载出来。真正的 `<Outlet />` 必须由被导入的 layout 组件自己渲染。

文件中的注释说 layouts use Outlet，意思是“布局组件通常使用 Outlet”，不是 `dynamicLayout` 自动加 Outlet。

### 误区二：以为 `dynamicElement` 只能导入 default export

不完全是。

`resolveLazyModule` 兼容几种形式：

- 标准 `{ default: Component }`
- 直接返回组件函数
- 其他被强转成组件的模块

不过从项目规范角度看，路由页面最好还是使用清晰的 default export，这样最符合 `React.lazy` 的常规预期。

### 误区三：以为 `ErrorBoundary` 是普通 React Error Boundary

它不是 class component 形式的传统 React Error Boundary，而是 React Router 的 `errorElement` 组件。

它通过 `useRouteError()` 读取路由错误，主要服务于 React Router data router 的错误处理机制。

### 误区四：以为所有错误都会触发 `notifyChunkError`

不会。

只有满足：

```ts
typeof window !== 'undefined' && isChunkLoadError(error)
```

时才会调用 `notifyChunkError()`。

普通渲染错误、业务错误、路由异常会进入 `ErrorCapture`，但不一定触发 chunk 错误通知。

### 误区五：以为 `NavigatorRegistrar` 是可有可无的空组件

它虽然返回 `null`，但非常关键。

它负责把 Router 上下文中的 `navigate` 注册到全局 store。没有它，`getStableNavigate()` 这类非组件导航工具就拿不到当前 router 的导航函数。

### 误区六：以为 `getStableNavigate()` 可以在应用启动前稳定可用

不一定。

`navigationRef.current` 只有在 `NavigatorRegistrar` 挂载并执行 effect 后才会被写入。应用启动早期、Router 尚未挂载或组件已卸载时，读取结果可能是 `null`。

所以调用 `getStableNavigate()` 的地方需要考虑空值。

### 误区七：以为 `prefetchRoute` 会预加载所有页面

不会。

它只预加载 `routePrefetchMap` 中登记过的一级路径：

```ts
'/agent'
'/community'
'/group'
'/page'
'/resource'
'/settings'
```

比如传入 `/tasks`，如果 map 里没有 `/tasks`，函数不会做任何事情。

### 误区八：以为 `prefetchRoute('/settings/provider')` 会加载 provider 页面本身

根据当前代码，它只会加载：

```ts
@/routes/(main)/settings/_layout
```

也就是 settings 的 layout chunk，不一定会加载 provider 子页面 chunk。它的优化目标是提前加载主路由布局，而不是完整加载目标页面所有代码。

### 误区九：忽略 `replace` 的行为

`redirectElement(to)` 内部是：

```tsx
<Navigate replace to={to} />
```

这意味着跳转会替换历史记录。它适合默认页重定向，比如 `/settings` 自动去 `/settings/profile`。如果某个场景需要保留历史记录，就不能直接套用这个工具。

### 误区十：以为 `createAppRouter` 只是简单转发 `createBrowserRouter`

它确实调用了 `createBrowserRouter`，但不是简单转发。它额外统一注入了：

- 根路径 `/`
- `RouterRoot`
- `SPAGlobalProvider`
- `BusinessGlobalProvider`
- `NavigatorRegistrar`
- 根级 `ErrorBoundary`
- 可选 `basename`

所以各端入口复用它，可以保证 SPA 的全局运行环境一致。
