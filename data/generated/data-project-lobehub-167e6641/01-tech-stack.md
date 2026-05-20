# 01. 技术栈逐个解释

## 先看版本级印象

从当前仓库快照里的 `package.json` 和 `apps/desktop/package.json` 来看，核心栈大致是：

- Next.js `16.1.5`
- React `19.2.5`
- TypeScript `5.9.3`
- React Router DOM `7.13.0`
- Zustand `5.0.4`
- tRPC `11.8.1`
- Drizzle ORM `0.45.1`
- SWR `2.3.8`
- TanStack React Query `5.90.20`
- Electron `41.3.0`
- antd `6.3.5`
- antd-style `4.1.0`

版本不是这页最重要的重点，更重要的是“这些技术分别解决什么问题”。

## 核心技术一览

| 技术 | 它是什么 | 这个项目里怎么用 | 初学者抓什么 |
| --- | --- | --- | --- |
| Next.js | React 全栈框架 | 放在 `src/app`，负责后端路由、认证页、SPA HTML 模板服务 | 它在这里更像“外壳 + API 宿主” |
| React | 组件式 UI 库 | 所有页面、组件、布局都基于 React 写 | 看到 `.tsx` 基本就在看 React 组件 |
| TypeScript | 给 JS 加类型系统 | 前后端、桌面端、共享包都广泛使用 | 类型名往往就是这段代码的“说明书” |
| React Router | SPA 路由库 | `src/spa/router` 注册页面树，`src/routes` 放页面段 | 它管理前端页面切换，不是后端接口 |
| Zustand | 轻量状态管理 | `src/store` 下每个业务域一个 store | 看 `store.ts`、`initialState.ts`、`selectors.ts` |
| SWR | 数据获取和缓存库 | 很多 store 初始化和列表同步通过 SWR 做 | 它常和 Zustand 配合，而不是互相替代 |
| React Query | 请求缓存/状态库 | tRPC React Provider 接入时使用 | 在这里更像 tRPC 生态配套层 |
| tRPC | 类型安全的前后端调用方案 | 前端 `lambdaClient` 调后端 `/trpc/*`，服务端用 router/procedure 定义接口 | 它让前后端共享 TypeScript 类型感知 |
| Drizzle ORM | TypeScript 风格 ORM | 与 PostgreSQL 配合，数据库 schema 与查询能力在工作区包里 | 理解成“更类型安全的数据库访问层” |
| PostgreSQL | 关系型数据库 | 主要服务端数据存储 | 表结构与 repository/model 逻辑分离 |
| Redis | 内存型数据存储 | 用于运行时配置、缓存、Agent 事件流、部分临时状态 | 它不是主库，更像加速层和协调层 |
| Hono | 轻量 Web 框架 | `src/server/agent-hono` 处理 `/api/agent/*` 这类接口 | 主要用于 Agent 执行/webhook 入口 |
| Electron | 桌面应用壳 | `apps/desktop` 提供主进程、preload、IPC、本地系统能力 | 网页 UI 复用主工程，系统能力走 Electron |
| Vite | 前端构建工具 | 负责 SPA 构建与本地开发 | `dev:spa`、`build:spa` 都靠它 |
| pnpm / bun | 包管理与脚本执行工具 | `pnpm` 管 workspace，`bun run` 执行脚本 | 先别纠结“为什么不是 npm”，当作团队约定即可 |
| react-i18next | 国际化方案 | 文案、多语言翻译 | 看到 `useTranslation` 就是在取文案 |
| antd / @lobehub/ui / antd-style | UI 组件与样式体系 | 页面组件、主题、样式变量 | UI 不全是原生 HTML，很多是封装好的组件 |

## 这几个最容易混淆

## Next.js 和 React Router 为什么会同时出现

这是 LobeHub 最需要先想通的一点。

在很多项目里，Next.js 自己就把页面路由也包了。
但在这个仓库里：

- Next.js 主要负责：
  - `src/app/(backend)` 下的 API / tRPC / webhook / auth
  - `src/app/spa/[variants]/[[...path]]/route.ts` 这种 SPA HTML 模板服务
  - 一些必须 SSR 的认证相关页面
- React Router 主要负责：
  - 真正的 SPA 页面切换
  - `desktop`、`mobile`、`popup` 等多套路由树
  - 动态加载页面和布局组件

可以粗暴理解成：

- Next.js 管“这个应用怎么被托管、怎么提供后端入口”
- React Router 管“用户点来点去时前端页面怎么切”

## Zustand 和 SWR 为什么会同时出现

它们解决的问题也不完全一样。

- Zustand 更像“前端自己的长期状态仓库”
  - 当前打开哪个 Agent
  - 聊天消息映射
  - 页面侧边栏开关
  - 当前 serverConfig
- SWR 更像“向服务端拿数据时的拉取/缓存/重刷机制”
  - 初始化用户状态
  - 拉取 server config
  - 列表页数据同步

在这个仓库里，常见组合是：

`SWR 拿数据 -> store action 写入 Zustand -> 组件从 store 读`

## tRPC 和普通 REST API 的关系

这里并不是只有一种接口形式。

当前代码能看到几条路：

- `/trpc/lambda`
  主应用的大部分类型安全接口
- `/trpc/mobile`
  面向移动端的裁剪版接口
- `/trpc/async`
  偏异步、任务型接口
- `/trpc/tools`
  工具相关接口
- `/api/agent/*`
  通过 Hono 挂出的 Agent 执行 / webhook 路径

所以如果你问“这个项目到底是 tRPC 还是 REST”，更准确的回答是：

它以 tRPC 为主，但不是只有 tRPC。

## Drizzle、数据库包、服务端模型层怎么配合

这个仓库没有把数据库访问直接写死在页面里，而是分了几层：

1. `packages/database`
   放数据库适配、schema、repository、类型。
2. `src/server/services/*`
   放服务端业务逻辑。
3. `src/server/routers/*`
   对外暴露 procedure / router。

这样前端不会直接碰 SQL，后端也不会把所有逻辑都塞进 router 文件。

## Electron 在这里扮演什么

Electron 不是替换 Web，而是给 Web 加本地能力。

LobeHub 桌面端会额外获得：

- 本地文件访问
- Git / shell / 本地系统能力
- 窗口与托盘管理
- 屏幕截图覆盖层
- 本地 IPC 通信

但页面 UI 依然大幅复用 `src/*` 的 React 代码。

## 小白应该先掌握哪 5 个词

如果你只想先建立最小词汇表，优先掌握这五个：

1. `SPA`
   单页应用，页面切换不等于整站刷新。
2. `Route`
   URL 到页面组件的映射。
3. `Feature`
   业务功能模块，不只是“一个小组件”。
4. `Store`
   前端状态仓库。
5. `Service`
   把“调用后端 / 调系统能力”的脏活隔开。

掌握这五个词，再去看这个仓库的目录，会顺很多。
