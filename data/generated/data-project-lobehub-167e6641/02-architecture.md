# 02. 架构总览

## 先给结论

LobeHub 当前这套仓库，可以先粗分成三大块：

- `src`
  主工程。这里放 Web 应用、SPA 页面、前端状态、服务端代码。
- `packages`
  共享工作区包。把数据库、模型运行时、常量、类型、Electron IPC、工具生态等抽出来复用。
- `apps`
  独立应用宿主。当前最重要的是 `apps/desktop`。

如果你一上来就把整个仓库当“一个普通 React 页面项目”看，几乎一定会迷路。

## 一张图看懂关系

```text
用户打开 Web / Desktop
        |
        v
src/app (Next.js 壳、API、认证、SPA 模板服务)
        |
        v
src/spa (React SPA 入口与 Router 注册)
        |
        v
src/routes (页面段与布局壳)
        |
        v
src/features (真正的业务 UI 与交互)
        |
        +------> src/store (前端状态)
        |
        +------> src/services (前端请求与能力调用)
        |
        v
src/server (后端 router / service / module)
        |
        v
packages/* (数据库、类型、模型运行时、工具、桥接层等共享能力)
        |
        v
apps/desktop (Electron 主进程、preload、IPC、本地系统能力)
```

## `src`、`packages`、`apps` 各自回答什么问题

### `src`

`src` 回答的是：

- 页面长什么样
- 路由怎么切
- 前端状态怎么管
- 前端如何调后端
- 后端接口和服务怎么组织

它是主战场。

### `packages`

`packages` 回答的是：

- 哪些能力应该独立成共享包
- 哪些类型、常量、运行时逻辑要同时给前端和后端用
- Electron、Agent Runtime、工具生态怎样抽成可复用模块

它不是“第三方依赖目录”，而是仓库自己的内部基础设施层。

### `apps`

`apps` 回答的是：

- 这套能力最终要以什么宿主形态运行

当前最值得关心的是：

- `apps/desktop`
  Electron 桌面端宿主

另外还能看到：

- `apps/cli`
- `apps/device-gateway`

但它们不在本批文档的重点范围里。

## `src` 内部再拆一层

即使只看 `src`，也不是平铺的。

### `src/app`

这是 Next.js App Router 层。

从当前目录能看出它主要承担三类事情：

- `src/app/(backend)`
  API、tRPC、webhook、OIDC、认证相关后端路由
- `src/app/spa`
  把 SPA HTML 模板按不同变体吐给浏览器
- `src/app/[variants]/(auth)`
  一些需要 SSR/认证流程的页面

换句话说，`src/app` 在这里更像平台入口层，不是主要业务页面层。

### `src/spa`

这里是浏览器端 SPA 的真实入口。

它决定：

- 用哪个 entry 文件启动
- 用哪套路由树
- desktop / mobile / popup 之间怎么分流

### `src/routes`

这里是“页面壳”。

它的核心作用是：

- 对应 URL 结构
- 放 `_layout`
- 放动态段比如 `[id]`
- 连接 `src/features`

根据仓库约定，理想目标是“routes 薄，features 厚”。当前代码快照里，这个方向已经存在，但尚未完全统一。

### `src/features`

这里是业务主体。

例如：

- `Conversation`
- `ChatInput`
- `AgentSetting`
- `Pages`
- `PageExplorer`
- `AgentTasks`

这些目录里才是“页面真正能用起来”的实现。

### `src/store`

这里是 Zustand 状态层。

大多数业务域都会有自己的一套：

- `store.ts`
- `initialState.ts`
- `selectors.ts`
- `slices/*`

### `src/server`

这里是服务端业务层。

常见结构有：

- `routers`
  对外接口定义
- `services`
  业务用例层
- `modules`
  可复用的服务端基础模块
- `runtimeConfig`
  运行时配置抽象
- `agent-hono`
  Agent 执行与 webhook 路径

## `packages` 为什么这么多

因为这个项目本身就是平台型项目。

你可以把 `packages` 再理解成几个簇：

### 1. 基础共享层

- `@lobechat/types`
- `@lobechat/utils`
- `@lobechat/const`
- `@lobechat/config`

这些包提供“全项目都可能用到”的底层定义。

### 2. 数据与模型层

- `@lobechat/database`
- `@lobechat/model-runtime`
- `@lobechat/agent-runtime`
- `@lobechat/context-engine`

这些包支撑 AI 应用的核心能力，不只服务一个页面。

### 3. 工具与 Agent 生态层

- `@lobechat/builtin-tools`
- `@lobechat/builtin-tool-*`
- `@lobechat/builtin-agents`
- `@lobechat/builtin-skills`

这一层让 Agent 不只是“会聊天”，而是能带工具、技能和行为规则。

### 4. 桌面桥接层

- `@lobechat/desktop-bridge`
- `@lobechat/electron-client-ipc`
- `@lobechat/electron-server-ipc`

这一层把 Web UI 和 Electron 主进程对接起来。

## `apps/desktop` 和 `src` 的关系

这是一个很关键的点：

- `apps/desktop` 负责 Electron 主进程、preload、系统能力
- `src/*` 负责大量共享页面 UI

也就是说，桌面端不是“重写一个新前端”，而是“给现有前端加桌面宿主与本地能力”。

## `business` 这一层怎么看

仓库里同时有：

- `src/business/*`
- `packages/business/*`

从当前代码能直接看到两件事：

- `packages/business/const` 里有 `ENABLE_BUSINESS_FEATURES = false`
- `src/business/client/BusinessDesktopRoutes.tsx`、`BusinessMobileRoutes.tsx` 目前都是空数组

因此可以比较稳地说：

- 当前公开代码里，这层更像“扩展位”或“业务增强位”

至于它是不是完全对应商业版/私有能力，单靠本批文件不能百分百下结论；如果这样理解，需要明确标记为“推测”。

## 新手最该先建立的边界感

读这个仓库时，请优先记住下面几组边界：

- `app` 不是主要页面实现层
- `routes` 不等于全部业务代码
- `features` 才是页面主体
- `store` 不是后端接口层
- `services` 不是 React 组件
- `packages` 不是外部依赖缓存
- `apps/desktop` 不是重复造轮子的第二套前端

一旦这些边界清楚了，后面的目录阅读速度会快很多。
