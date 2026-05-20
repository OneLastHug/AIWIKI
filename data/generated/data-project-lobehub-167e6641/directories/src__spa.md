# `src/spa` 目录说明

## 这个目录在项目中的位置

- 仓库位置：`/data/project/lobehub/src/spa`
- 它位于主工程 `src` 下面，是浏览器端 SPA 的直接入口层

## 它负责什么

`src/spa` 主要做两件事：

1. 提供不同运行形态的入口文件
   - `entry.web.tsx`
   - `entry.mobile.tsx`
   - `entry.desktop.tsx`
   - `entry.popup.tsx`
2. 注册 React Router 路由树
   - `router/desktopRouter.config.tsx`
   - `router/desktopRouter.config.desktop.tsx`
   - `router/mobileRouter.config.tsx`
   - `router/popupRouter.config.tsx`

你可以把它理解成：

- 这里决定“应用怎么启动”
- 这里决定“启动后先用哪套路由表”

## 初学者应该先看哪些文件

推荐顺序：

1. `src/spa/entry.web.tsx`
   最简单地看到 Web 版如何 `createRoot`、如何挂 `RouterProvider`。
2. `src/utils/router.tsx`
   这是 router 创建的公共封装，`dynamicElement`、`dynamicLayout` 很关键。
3. `src/spa/router/desktopRouter.config.tsx`
   认识主桌面/网页路由骨架。
4. `src/spa/router/mobileRouter.config.tsx`
   看移动端是如何裁剪路由的。
5. `src/spa/router/popupRouter.config.tsx`
   看弹窗模式为什么是另一套更小的路由树。
6. `src/spa/router/desktopRouter.config.desktop.tsx`
   理解桌面同步导入版路由树的存在原因。

## 它和其他目录如何交互

最重要的交互链是：

```text
src/app/spa/.../route.ts
-> 返回 HTML + window.__SERVER_CONFIG__
-> src/spa/entry.*
-> src/utils/router.tsx
-> src/spa/router/*.config.tsx
-> src/routes/*
-> src/features/*
```

具体来说：

- `src/app/spa/.../route.ts` 决定返回哪种 HTML 模板，并把首屏配置注入到浏览器
- `src/spa/entry.*` 决定当前运行环境使用哪套路由
- `router/*.config.tsx` 通过 `dynamicElement` / `dynamicLayout` 指向 `src/routes/*`
- `src/routes/*` 再去组合 `src/features/*`

## 常见概念解释

### `entry.web.tsx` 和 `entry.desktop.tsx` 的区别

两者都启动 React Router，但面对的运行环境不同：

- `entry.web.tsx`
  会处理 `/_dangerous_local_dev_proxy` 的 `basename`，方便本地开发代理
- `entry.desktop.tsx`
  面向 Electron 桌面端渲染

### `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 为什么有两份

这是这个目录里最容易让人困惑的点。

当前代码能直接看出：

- `desktopRouter.config.tsx`
  使用 `dynamicElement` / `dynamicLayout`，偏动态导入、代码分割
- `desktopRouter.config.desktop.tsx`
  直接同步 import，偏 Electron 本地构建与同步装配

而且仓库里还有 `desktopRouter.sync.test.tsx`，专门校验这两份路由树不要漂移。

所以它们不是重复劳动，而是“同一套路由树的两种装配方式”。

### `dynamicElement` 和 `dynamicLayout`

这两个助手函数都来自 `src/utils/router.tsx`：

- `dynamicElement`
  给普通页面组件做懒加载
- `dynamicLayout`
  给 layout 组件做懒加载

它们的作用是把真正的 `import(...)` 细节藏起来，让 router 配置更清楚。

### `popup` 是什么

`popup` 是桌面端的一种特殊窗口模式。

从 `popupRouter.config.tsx` 可以直接看出，它只关注：

- `agent/:aid/:tid`
- `agent/:aid`
- `group/:gid/:tid`

也就是一个“更轻量、围绕单个会话窗口”的路由树。

## 这个目录里最值得先记住的现实事实

### 1. 这里注册的是“路线图”，不是页面实现

`src/spa/router` 里写的是路由树，不是 UI 主体。

如果你开始看到一堆 path 就头大，不妨先把它看成“导航菜单的数据结构”。

### 2. `src/routes` 和 `src/spa/router` 不同

- `src/spa/router`
  负责注册路由关系
- `src/routes`
  负责提供这些路由指向的页面段

两者经常一起出现，但职责不同。

## 需要暂时跳过的内容

刚入门时可以先跳过：

- `desktopRouter.sync.test.tsx`
  它很重要，但先理解双路由树的存在原因更关键。
- 路由配置里的每一个嵌套细节
  先抓住大的分组：`agent`、`group`、`community`、`settings`、`memory`、`image`、`video`、`tasks`、`page`。
- `BusinessDesktopRoutes*`、`BusinessMobileRoutes*`
  当前公开代码里它们是扩展位，先知道有这个插槽就够了。

## 一句话阅读建议

先把 `src/spa` 看成“启动器 + 路由装配层”，不要把它误读成“页面实现目录”。
