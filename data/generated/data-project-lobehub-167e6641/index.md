# LobeHub 中文学习文档

这套文档不是按“文件清单”写的，而是按“人怎么把这个项目看懂”来写的。

如果你第一次打开 `lobehub` 仓库，最大的困难通常不是代码不会写，而是看不出：

- 这是一个什么产品
- 为什么同一个仓库里同时有 Next.js、React Router、tRPC、Electron
- `src/routes`、`src/features`、`src/store`、`src/server` 到底怎么分工
- 哪些目录现在就该看，哪些先跳过反而更容易入门

下面给你几条不同目标的推荐阅读顺序。

## 完全小白路线

适合对 React、Next.js、Electron 都不熟，只想先把项目“看成一张图”的读者。

1. [00-overview.md](./00-overview.md)
   先用产品语言理解 LobeHub 到底是什么，不要一上来钻进代码。
2. [01-tech-stack.md](./01-tech-stack.md)
   把 Next.js、React、TypeScript、Zustand、tRPC、Drizzle、Electron 这些名词先翻译成人话。
3. [02-architecture.md](./02-architecture.md)
   建立总分层：`apps`、`packages`、`src` 分别扮演什么角色。
4. [03-runtime-flow.md](./03-runtime-flow.md)
   看“页面是怎么跑起来的”“请求是怎么走到后端的”。
5. [directories/src.md](./directories/src.md)
   知道主工程 `src` 顶层目录的地图。
6. [directories/src__spa.md](./directories/src__spa.md)
   先看 SPA 入口和路由注册，知道浏览器到底先执行什么。
7. [directories/src__routes.md](./directories/src__routes.md)
   再看页面路由树，理解 URL 和页面文件的关系。
8. [directories/src__features.md](./directories/src__features.md)
   认识真正承载业务 UI 的地方。
9. [directories/src__store.md](./directories/src__store.md)
   理解状态管理，不然会一直找不到数据从哪来。
10. [directories/src__server.md](./directories/src__server.md)
    理解服务端路由、服务、模块三层分工。
11. [directories/packages.md](./directories/packages.md)
    最后再看共享包，否则容易一开始就被工作区包数量吓到。
12. [directories/apps__desktop.md](./directories/apps__desktop.md)
    如果你还关心桌面端，再进入 Electron 部分。

## 前端路线

适合想改页面、改交互、改状态，但暂时不想碰后端的人。

1. [02-architecture.md](./02-architecture.md)
2. [directories/src.md](./directories/src.md)
3. [directories/src__spa.md](./directories/src__spa.md)
4. [directories/src__routes.md](./directories/src__routes.md)
5. [directories/src__features.md](./directories/src__features.md)
6. [directories/src__store.md](./directories/src__store.md)
7. [files/src__store__serverConfig__index.ts.md](./files/src__store__serverConfig__index.ts.md)
   这是前端“全局服务器配置入口”的好例子。
8. [files/package.json.md](./files/package.json.md)
   需要跑起来或找脚本时再回来看。

## 后端路线

适合想理解接口、配置、任务执行、服务端模块的人。

1. [00-overview.md](./00-overview.md)
2. [02-architecture.md](./02-architecture.md)
3. [03-runtime-flow.md](./03-runtime-flow.md)
4. [directories/src__server.md](./directories/src__server.md)
5. [files/src__server__runtimeConfig__index.ts.md](./files/src__server__runtimeConfig__index.ts.md)
6. [files/src__store__serverConfig__index.ts.md](./files/src__store__serverConfig__index.ts.md)
   读完这个，你就知道服务端配置怎样一路送到前端。
7. [directories/packages.md](./directories/packages.md)
   尤其关注 `@lobechat/database`、`@lobechat/model-runtime`、`@lobechat/agent-runtime`。

## 桌面端路线

适合想看 Electron 主进程、preload、IPC、桌面增强能力的人。

1. [00-overview.md](./00-overview.md)
2. [02-architecture.md](./02-architecture.md)
3. [directories/apps__desktop.md](./directories/apps__desktop.md)
4. [directories/src__spa.md](./directories/src__spa.md)
   因为桌面端复用了主工程的 SPA 页面。
5. [directories/src__routes.md](./directories/src__routes.md)
   重点看 `(desktop)`、`(popup)`、以及普通 `(main)` 页面如何被 Electron 复用。
6. [directories/packages.md](./directories/packages.md)
   重点看 `desktop-bridge`、`electron-client-ipc`、`electron-server-ipc`。

## 想改代码路线

适合已经准备动手改功能，不只是阅读的人。

1. [files/package.json.md](./files/package.json.md)
   先知道怎么启动、怎么构建、怎么跑桌面端。
2. [directories/src__spa.md](./directories/src__spa.md)
   改路由前必须先懂入口和 router 注册方式。
3. [directories/src__routes.md](./directories/src__routes.md)
   判断你该改“路由壳”还是“业务实现”。
4. [directories/src__features.md](./directories/src__features.md)
   大多数 UI 改动应该落在这里。
5. [directories/src__store.md](./directories/src__store.md)
   需要数据联动时，找到对应 store。
6. [directories/src__server.md](./directories/src__server.md)
   需要接口或执行链路时，再进服务端。
7. [files/src__store__serverConfig__index.ts.md](./files/src__store__serverConfig__index.ts.md)
8. [files/src__server__runtimeConfig__index.ts.md](./files/src__server__runtimeConfig__index.ts.md)

## 读这套文档时的建议

- 先抓“层”和“边界”，不要一开始逐行读组件。
- 先看入口文件和 `index.ts`，再看深层实现。
- 看见 `routes`、`features`、`store` 三个词时，先问自己它们分别回答什么问题：
  - `routes`：当前 URL 对应哪个页面壳。
  - `features`：这个页面真正的业务 UI 和交互。
  - `store`：这些 UI 共用的数据和动作放在哪里。
- 看到我写“推测”时，表示这个结论主要来自目录命名、空壳扩展位或局部上下文，不是直接由单一源码文件明说。
