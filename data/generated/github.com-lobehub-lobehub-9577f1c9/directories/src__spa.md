# 目录：src/spa

## 它负责什么

`src/spa` 是这个仓库里 SPA 前端的“装配层”。它不放业务页面本体，而是负责把不同平台的入口、路由树、路由元数据和错误边界串起来，让应用在 web、desktop、mobile、popup 这些运行形态下都能用同一套 React Router 机制启动。

根据当前片段推断，这里的职责可以概括为三件事：第一，提供各平台的 SPA 入口文件；第二，按平台组装路由配置；第三，维护路由相关的轻量公共能力，比如 `routeMeta` 和桌面路由同步测试。

## 直接子目录地图

`src/spa` 的直接子目录只有一个：`router/`。这说明目录层级很收敛，顶层几乎全是入口文件，真正的路由编排集中在子目录里。

`src/spa/router/` 下面主要是这几类文件：

- `desktopRouter.config.tsx`：桌面端主路由树，使用动态导入和懒加载。
- `desktopRouter.config.desktop.tsx`：桌面端同步版路由树，给 Electron 或本地打包路径做一致性保障。
- `mobileRouter.config.tsx`：移动端路由树。
- `popupRouter.config.tsx`：弹窗窗口的独立路由树。
- `routeMeta.ts`：路由 `handle.meta` 的结构定义与读取工具。
- `desktopRouter.sync.test.tsx`、`mobileRouter.test.tsx`：用于校验路由树同步和结构约束。

## 关键入口

这里最重要的入口文件是四个平台入口：

- `src/spa/entry.web.tsx`
- `src/spa/entry.desktop.tsx`
- `src/spa/entry.mobile.tsx`
- `src/spa/entry.popup.tsx`

它们的共同模式是：先 `import '../initialize'`，再通过 `createAppRouter(...)` 创建路由实例，最后用 `RouterProvider` 挂载到 `#root`。

其中 `entry.web.tsx` 还额外处理了 `window.__DEBUG_PROXY__` 和 `/_dangerous_local_dev_proxy` 这类本地调试代理前缀，说明 web 入口兼顾了本地开发代理场景。

## 主流程位置

主流程实际上集中在 `src/spa/router/`。

桌面端主流程是 `desktopRouter.config.tsx`。它把 `agent`、`group`、`community`、`settings` 等大路由组拼成一棵树，并通过 `dynamicElement`、`dynamicLayout` 把真正的页面模块延迟加载进来。这里还能看到大量 `handle: { meta: ... }`，说明页面图标、标题等导航信息不是散落在页面组件里，而是挂在路由元数据上统一读取。

移动端主流程在 `mobileRouter.config.tsx`。它和桌面端共享不少页面来源，但结构更偏向移动 UI：例如社区页会拆成 list 和 detail 两层布局，设置页也有专门的移动嵌套结构。

弹窗流程在 `popupRouter.config.tsx`，路径前缀固定为 `/popup`，只承载单会话窗口。它不走复杂的主站布局，而是直接挂载 `PopupLayout` 和几个主题页面，属于最轻量的一条路由链。

`routeMeta.ts` 是路由元数据的公共协议层，定义了 `StaticRouteMeta`、`DynamicRouteMeta`、`RouteHandle` 等类型，并提供 `getRouteMetaFromHandle`。它本身不做渲染，但会影响菜单、标签、动态标题等上层表现。

## 推荐阅读顺序

1. 先看 `src/spa/entry.web.tsx`，理解 SPA 从哪里起步。
2. 再看 `src/spa/router/desktopRouter.config.tsx`，把桌面主路由树的结构摸清。
3. 然后看 `src/spa/router/mobileRouter.config.tsx`，对比移动端如何复用和裁剪同一套页面。
4. 接着看 `src/spa/router/popupRouter.config.tsx`，理解独立窗口怎么单独成树。
5. 最后看 `src/spa/router/routeMeta.ts` 和 `desktopRouter.sync.test.tsx`，补齐元数据与一致性约束。

## 常见误区

- 把 `src/spa` 当成页面业务层。实际上这里主要是入口和路由编排，真正业务通常在 `src/routes/` 和 `src/features/`。
- 只改 `desktopRouter.config.tsx`，忘了同步 `desktopRouter.config.desktop.tsx`。这里有明确的同步测试，漏改很容易造成桌面构建行为不一致。
- 误以为 `entry.*.tsx` 会承载页面逻辑。它们通常只负责初始化、选路由树、挂载 `RouterProvider`。
- 忽略 `handle.meta`。很多导航标题、图标、动态信息不是写死在组件里，而是通过路由元数据传递。
- 把 popup、mobile、desktop 看成同一条简单路由线。它们在入口、布局和路由树形态上是分开的，适用场景也不同。
