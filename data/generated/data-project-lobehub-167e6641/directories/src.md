# `src` 目录说明

## 这个目录在项目中的位置

- 仓库位置：`/data/project/lobehub/src`
- 它属于主工程源码目录，是整个仓库里最应该优先读的一层

## 它负责什么

如果把整个仓库看成一家公司，`src` 基本就是总部大楼。

这里同时放着：

- Next.js 入口与后端路由：`src/app`
- SPA 入口与前端路由注册：`src/spa`
- 页面段与布局：`src/routes`
- 真正业务 UI：`src/features`
- 前端状态：`src/store`
- 前端请求层：`src/services`
- 后端业务层：`src/server`
- 一些基础设施：`src/config`、`src/libs`、`src/utils`、`src/hooks`

所以 `src` 不是单纯的“前端页面目录”，而是主应用的综合源码层。

## 初学者应该先看哪些文件和子目录

推荐顺序：

1. `src/app`
   先知道 Next.js 在这里负责什么。
2. `src/spa`
   这是浏览器端真正跑起来的入口。
3. `src/routes`
   先看 URL 到页面壳的映射。
4. `src/features`
   再看页面主体实现。
5. `src/store`
   再理解数据和动作放哪里。
6. `src/server`
   最后进入服务端。

如果你只想先抓顶层地图，可以先记住这些目录：

| 目录 | 最朴素的理解 |
| --- | --- |
| `src/app` | Next.js 壳与后端入口 |
| `src/spa` | SPA 启动与 Router 注册 |
| `src/routes` | 页面段、布局、URL 结构 |
| `src/features` | 业务功能实现 |
| `src/store` | Zustand 状态层 |
| `src/services` | 前端请求与能力调用 |
| `src/server` | 后端 router / service / module |
| `src/business` | 扩展位或业务增强层 |
| `src/components` | 更通用、更基础的 UI 组件 |
| `src/libs` | 封装过的基础库接入层 |

## 它和其他目录如何交互

`src` 内部最重要的一条协作主线是：

```text
src/app
-> src/spa
-> src/routes
-> src/features
-> src/store / src/services
-> src/server
-> packages/*
```

更具体一点：

- `src/app/spa/.../route.ts` 把 HTML 和首屏配置送到浏览器
- `src/spa/entry.*` 启动 React Router
- `src/routes/*` 决定当前 URL 用哪个页面壳
- `src/features/*` 负责真正的 UI 与交互
- `src/store/*` 保存状态
- `src/services/*` 发请求或调桌面桥接
- `src/server/*` 在后端处理真实业务

## 常见概念解释

### `app`

这里的 `app` 指 Next.js App Router 层，不等于“所有应用代码”。

### `spa`

这里的 `spa` 指浏览器单页应用入口。当前仓库是“Next.js 托管壳 + React Router 管页面”的混合结构。

### `routes`

主要回答“当前 URL 对应哪个页面段和布局”。

### `features`

主要回答“这个页面真正做什么、显示什么、怎么交互”。

### `store`

主要回答“前端状态放哪里、谁能读、谁能改”。

### `server`

主要回答“请求到了后端后，谁来处理业务”。

## 需要暂时跳过的内容

刚入门时，建议先不要在这些地方花太多时间：

- `src/styles`
  除非你当前就要改样式体系。
- `src/locales`
  语言包很重要，但不适合作为第一站。
- `src/envs`
  环境变量定义较碎，等你已经知道配置链再回来看。
- `src/business`
  当前公开代码里有不少扩展位，初学者先知道它存在即可。
- `src/utils` 和 `src/libs` 的深层细节
  先按需看，不要地毯式扫读。

## 一句话阅读建议

先把 `src` 看成“多层协作系统”，不要看成“一个平铺的 React 页面目录”。
