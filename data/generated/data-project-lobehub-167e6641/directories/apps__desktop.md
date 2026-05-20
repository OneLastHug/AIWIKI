# `apps/desktop` 目录说明

## 这个目录在项目中的位置

- 仓库位置：`/data/project/lobehub/apps/desktop`
- 它是 Electron 桌面端宿主工程

## 它负责什么

`apps/desktop` 负责把 LobeHub 这套共享前端能力变成真正的桌面应用。

它主要提供：

- Electron 主进程
- preload 安全桥
- IPC controller
- 本地系统能力
- 托盘、菜单、快捷键、更新
- 截图覆盖层

重要的是：

- 它不是把整个前端重写一遍
- 它主要是在共享页面之上，加了一层桌面宿主和本地能力

## 初学者应该先看哪些文件

推荐顺序：

1. `apps/desktop/package.json`
   先看开发、构建、打包命令。
2. `apps/desktop/src/main/index.ts`
   看桌面应用如何真正启动。
3. `apps/desktop/src/main/core/App.ts`
   这是桌面主进程的总控类。
4. `apps/desktop/src/main/controllers/registry.ts`
   看有哪些 IPC controller 被注册。
5. `apps/desktop/src/preload/index.ts`
   看 preload 做了什么。
6. `apps/desktop/src/preload/electronApi.ts`
   看渲染进程能调用哪些桥接 API。
7. `apps/desktop/src/common/routes.ts`
   看哪些前端路由会被桌面端拦截成独立窗口。
8. `apps/desktop/src/overlay/entry.tsx`
   看截图覆盖层是如何启动的。

## 它和其他目录如何交互

最关键的关系是：

```text
apps/desktop/src/main
-> 管理 Electron 主进程与系统能力

apps/desktop/src/preload
-> 暴露安全桥给 renderer

renderer 页面
-> 大量复用主工程 src/* 的 React UI

桌面通信
-> 依赖 packages/electron-client-ipc
-> 依赖 packages/electron-server-ipc
-> 依赖 packages/desktop-bridge
```

所以阅读顺序通常是：

- 先知道桌面端“多了哪些能力”
- 再知道这些能力怎样通过桥接送到共享 React 页面

## 目录里的主要分层

### `src/main`

Electron 主进程。

这是桌面端最重要的一层，负责：

- App 生命周期
- 窗口管理
- 菜单 / 托盘 / 快捷键
- 本地文件与系统命令
- Git / MCP / 本地工具检测
- 更新机制

其中 `App.ts` 很像“桌面宿主总装配器”：

- 初始化 StoreManager
- 初始化 BrowserManager
- 动态加载 controllers 和 services
- 注册协议
- 注册工具检测器
- 启动 IPC server

### `src/preload`

预加载脚本层。

这里的作用是：

- 不把 Electron 能力直接裸暴露给页面
- 而是通过 `contextBridge` 提供受控 API

比如 `electronApi.ts` 里暴露了：

- `invoke`
- `onScreenCaptureSession`
- `onStreamInvoke`
- `lobeEnv`

### `src/overlay`

截图覆盖层 UI。

这是桌面端很有辨识度的一块：

- 显示屏幕选区
- 生成窗口预览
- 把截图提交给聊天面板

它是独立于主页面的另一套渲染入口。

### `src/common`

放桌面端共享的小型约定，例如路由拦截配置。

从 `src/common/routes.ts` 可以直接看出：

- 某些 URL 可以被桌面端拦成独立窗口
- 当前代码里开发工具页就是一个例子

## 常见概念解释

### 主进程、渲染进程、preload 分别是什么

这是 Electron 入门必须先懂的三件事：

- 主进程
  像桌面应用的后台总控，能碰系统 API
- 渲染进程
  主要就是网页 UI，很多是 React 代码
- preload
  主进程和网页之间的安全桥

### controller 是什么

在这个项目里，controller 主要是 IPC 方法集合。

例如从文件名就能看出职责范围：

- `AuthCtr`
- `GitCtr`
- `LocalFileCtr`
- `ScreenCaptureCtr`
- `ShellCommandCtr`
- `UpdaterCtr`

它们会被统一注册进 IPC 服务系统里。

### 为什么 `apps/desktop` 还要有自己的 `package.json`

因为桌面端有独立的构建、打包和 Electron 依赖。

此外，主仓库顶层 `package.json` 还把 `apps/desktop/src/main` 单独纳入 workspace，用来暴露一个仅提供 typings 的小包 `@lobehub/desktop-ipc-typings`。

### overlay 为什么不直接写进普通页面

因为它不是普通页面的一部分，而是桌面截图能力的一块专用 UI。

它有自己的入口、自己的交互模型、自己的 session 数据来源。

## 需要暂时跳过的内容

初学阶段可以先跳过：

- `build/` 下的图标和安装资源
- `resources/locales/*`
- `scripts/update-test/*`
- 打包平台细节，例如 dmg、nsis、notarize

先把主进程、preload、overlay、IPC 主线看懂，再回来补这些工程细节。

## 一句话阅读建议

把 `apps/desktop` 看成“给共享 Web UI 加本地系统能力的宿主层”，不要把它看成另一套完全独立前端。
