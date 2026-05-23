# 目录：src/routes

## 它负责什么

`src/routes` 是这个项目的 SPA 路由根目录，职责不是放业务实现，而是承载“页面段”本身。根据当前片段推断，它遵循的是一种 `roots vs features` 分层：这里主要放 `_layout/index.tsx`、`index.tsx`、`[param]/index.tsx` 这类路由入口文件，真正的业务 UI 和逻辑则尽量下沉到 `src/features`。

这个目录的意义在于把“路由结构”单独固定下来，让 `src/spa/router/*` 可以稳定地把不同入口页挂到桌面端、移动端、弹窗和 onboarding 流程里。也就是说，`src/routes` 更像是应用的页面骨架，而不是功能实现仓库。

## 直接子目录地图

从目录结构看，`src/routes` 下的一级路由分组主要有：

- `(main)`：主应用区，是最大的一组页面树，覆盖 `agent`、`community`、`home`、`settings`、`page`、`memory`、`resource`、`eval`、`group`、`task`、`tasks`、`devtools`、`hooks` 以及 `(create)`、`(task-workspace)` 等。
- `(mobile)`：移动端页面树，包含 `chat`、`community`、`me`、`settings`、`(home)`。
- `(popup)`：弹窗/浮层场景，包含 `agent`、`group`。
- `(desktop)`：桌面端专用页面，当前能看到 `desktop-onboarding`。
- `onboarding`：首次引导流程，包含 `agent`、`classic`、`components`、`features`。
- `share`：分享页，当前有 `t/[id]` 这条分享主题路由。

从深度上看，`(main)` 是最核心的树，`(mobile)` 和 `(popup)` 是面向特定入口的裁剪版本，`onboarding` 和 `share` 则属于独立流程，不完全依附主壳。

## 关键入口

这个目录本身不是唯一入口，但它是多个入口的共同落点。最关键的组合是：

- `src/routes/(main)/_layout/index.tsx`：主应用壳层，决定主站的整体布局。
- `src/routes/(main)/home/index.tsx`、`src/routes/(main)/agent/index.tsx`、`src/routes/(main)/settings/index.tsx`、`src/routes/(main)/page/index.tsx`：主流程里最常见的页面入口。
- `src/routes/(mobile)/_layout/index.tsx`、`src/routes/(mobile)/chat/index.tsx`、`src/routes/(mobile)/settings/index.tsx`：移动端主入口。
- `src/routes/(popup)/_layout/index.tsx`：弹窗场景的统一外壳。
- `src/routes/onboarding/_layout/index.tsx` 与 `src/routes/onboarding/index.tsx`：引导流程入口。
- `src/routes/share/t/[id]`：分享链接页入口。

从文件形态上看，很多路由目录里只保留薄薄的 `index.tsx` 或 `_layout/index.tsx`，符合“只做组装、不做重逻辑”的路由薄层思路。

## 主流程位置

主流程主要不是在 `src/routes` 内部串起来，而是在 `src/spa/router` 里被装配起来，再映射到这些页面段。最关键的是：

- `src/spa/router/desktopRouter.config.tsx`
- `src/spa/router/desktopRouter.config.desktop.tsx`
- `src/spa/router/mobileRouter.config.tsx`
- `src/spa/router/popupRouter.config.tsx`

其中桌面端有一条很重要的双文件约束：`desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 必须保持同构，同一条路径、同一层级、同一 index 关系都要一致。`src/spa/router/desktopRouter.sync.test.tsx` 就是在守这个一致性。

从路由挂载方式看，主站入口大致集中在 `(main)` 树里，桌面端与移动端会分别挑选其中一部分页面复用；例如 `agent`、`settings`、`tasks`、`community`、`resource`、`eval` 等都能看到跨端复用痕迹。根据当前片段推断，`src/routes/(main)` 是全局业务导航的中心，`(mobile)` 只是针对移动场景裁剪后的表现层。

## 推荐阅读顺序

1. 先看 `src/spa/router/desktopRouter.config.tsx`，理解桌面端如何把 `src/routes` 挂成完整路由树。
2. 再看 `src/spa/router/desktopRouter.config.desktop.tsx`，确认桌面端静态路由树与动态配置的对应关系。
3. 接着看 `src/spa/router/mobileRouter.config.tsx` 和 `src/spa/router/popupRouter.config.tsx`，理解同一套页面段如何被不同入口复用。
4. 然后回到 `src/routes/(main)/_layout/index.tsx` 以及几个高频页面入口，如 `home`、`agent`、`settings`、`page`。
5. 最后再看 `src/routes/(main)/*/features`、`src/routes/onboarding/features` 这类目录，判断哪些逻辑已经被下沉到 feature 层，哪些还保留在路由附近。

## 常见误区

- 把 `src/routes` 当成业务实现目录。这里更应该被理解为路由段和页面壳，复杂逻辑通常不该堆在这里。
- 只改 `src/spa/router/desktopRouter.config.tsx`，忘记同步 `desktopRouter.config.desktop.tsx`。这在这个仓库里是高风险操作，容易导致桌面构建和本地预览不一致。
- 误以为所有路由都已经完全“薄化”。从当前目录树看，部分子目录下面仍保留 `components`、`features`，说明这里还处于迁移中的混合状态，不能机械套用“只有 index 和 layout”的理想模型。
- 忽略跨端复用关系。`(main)` 下的很多页面会被 `mobileRouter`、`popupRouter` 直接复用，改动时不能只按单端视角理解。
- 看到 `page`、`agent`、`settings` 这些目录就以为它们只是单页。实际上它们往往是一个小型路由子树，包含布局、详情页、重定向页或嵌套段。
