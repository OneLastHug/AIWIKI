# 文件：`src/spa/router/mobileRouter.config.tsx`

## 一句话定位
这是移动端 SPA 的路由蓝图，负责把 `react-router-dom` 的 `RouteObject[]` 组织成一棵完整的移动端路由树，再交给 `src/spa/entry.mobile.tsx` 创建真正的 router。它本身不渲染页面，只定义“访问什么路径时加载哪个路由模块、套哪层布局、怎么重定向”。

## 它暴露/定义了什么
它主要导出 `mobileRoutes: RouteObject[]`。这个数组包含移动端主站、`/onboarding`、分享页、以及从业务层注入的额外移动端路由片段。根据当前片段推断，这个文件就是移动端声明式路由配置的单一入口，供入口文件和测试直接消费。

路由树里能看到几个明确分组：`agent` 聊天、`community` 探索、`settings` 设置、`tasks` / `task` 任务工作区、`me` 个人中心、首页兜底，以及 `*` catch-all 重定向。很多子路由都通过 `handle.meta` 绑定路由元信息，用于导航、标题或页面标识。

## 谁调用它
直接调用方是 `src/spa/entry.mobile.tsx`，那里把 `mobileRoutes` 传给 `createAppRouter(mobileRoutes)`，再交给 `RouterProvider` 挂到 React 根节点上。另一个直接读取者是 `src/spa/router/mobileRouter.test.tsx`，从文件名和搜索结果看，它很可能用来校验路由结构或快照稳定性。

间接上，所有移动端页面访问最终都会经过这份配置，因为它决定了地址和页面模块的映射关系。

## 它调用谁
它不调用业务逻辑服务，主要调用的是路由构造辅助函数和懒加载页面模块：

- `dynamicElement`、`dynamicLayout`：把 `import()` 变成按需加载的页面或布局组件
- `redirectElement`：生成重定向节点
- `ErrorBoundary`：给路由层提供错误兜底
- `BusinessMobileRoutesWithMainLayout`、`BusinessMobileRoutesWithoutMainLayout`：注入业务扩展路由
- 各类 `@/routes/...` 路由模块：例如 `@/routes/(mobile)/chat`、`@/routes/(mobile)/settings/_layout`、`@/routes/share/t/[id]/_layout` 等
- 各种 `routeMeta`：如 `agentRouteMeta`、`mobileAgentSettingsRouteMeta`、`shareTopicRouteMeta`

## 核心流程
1. 最外层定义根路径 `/`，挂载 `@/routes/(mobile)/_layout` 作为移动端主壳。
2. 在主壳下按业务域拆分路由：聊天、探索、设置、任务、个人中心、首页。
3. 每个业务域继续分层：比如 `agent/:aid` 下再挂聊天页、topic 页、settings 页；`community` 下分 list/detail 两套布局。
4. 需要首屏跳转的位置用 `redirectElement('/')` 或其他目标路径做重定向。
5. 通过 `dynamicElement` / `dynamicLayout` 延迟加载页面，控制首屏体积。
6. 额外插入 onboarding 和 share 路由，它们不走主 layout，属于独立入口。
7. 最后把业务层拼接进来的路由片段合并进来，形成完整 mobile router。

## 关键函数的高层作用
`dynamicElement` 和 `dynamicLayout` 是这份文件的核心胶水。前者负责“某个 path 对应哪个页面组件”，后者负责“这组子页面共用哪层布局”。它们把静态配置和动态 `import()` 连接起来，既保持路由树声明式，又避免一次性打包所有页面。

`redirectElement` 用来处理默认入口和非法路径收口，保证移动端在缺省地址下能落到正确页面。`ErrorBoundary` 则是路由级容错，防止某个懒加载页面或子树崩掉后把整棵应用带死。

`BusinessMobileRoutesWithMainLayout`、`BusinessMobileRoutesWithoutMainLayout` 的作用更像“插槽”。它们让云端或业务层可以在不改主路由骨架的情况下，注入额外移动端页面。

## 修改风险
这类文件的风险不在业务计算，而在路由结构本身。改错一个 `path`、`index` 或嵌套层级，就可能导致页面 404、重定向循环，或者某个模块在移动端根本进不去。由于它和 `src/spa/entry.mobile.tsx`、`src/spa/router/mobileRouter.test.tsx` 以及桌面端路由约定共同构成入口契约，改动时要特别注意路径是否和 `src/routes/` 下实际文件一致，是否仍然挂在正确的 layout 下。

另一个高风险点是业务路由拼接。如果 `BusinessMobileRoutesWithMainLayout` / `WithoutMainLayout` 的注入顺序或挂载位置变了，可能影响首页、分享页或 onboarding 这类独立入口的可达性。对于共享的 `handle.meta`，误删会让导航或页面标识丢失，虽然页面还能打开，但产品层体验会退化。
