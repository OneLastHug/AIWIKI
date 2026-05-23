# 目录：src

## 它负责什么

根据当前片段推断，`src` 是整个应用的源码主根，承担了前端展示、路由编排、业务逻辑、状态管理、服务调用和服务端能力的统一放置。它不是单纯的 UI 目录，而是把 Next.js App Router、SPA 路由、共享组件、业务模块和后端辅助逻辑放在一起，形成一个前后端同仓的主工程入口。

从目录结构看，`src` 里同时存在两条主线：一条是 `src/app` 下的 Next.js 壳和后端路由，另一条是 `src/spa` + `src/routes` 组成的单页应用主界面。再往下，`src/features`、`src/services`、`src/store`、`src/server`、`src/business` 分别承接页面能力、接口封装、状态层、服务端配置与业务规则。

## 直接子目录地图

- `src/app`：Next.js App Router 层，负责根布局、站点元信息、`trpc` 等后端入口，以及认证相关页面壳。
- `src/spa`：SPA 启动与路由配置层，包含 `entry.web.tsx`、`entry.desktop.tsx`、`entry.mobile.tsx`、`entry.popup.tsx` 和各端路由树。
- `src/routes`：页面段目录，主要放路由壳、布局壳和页面组件，按 `main`、`mobile`、`desktop`、`popup`、`onboarding`、`share` 等场景分组。
- `src/features`：业务功能模块的主要落点，像聊天、页面编辑、插件、技能、引导、导航、设置等都按域拆开。
- `src/components`：更偏通用的可复用 UI 组件、提示、加载态、图标和小型交互部件。
- `src/services`：面向前端的数据服务层，通常封装 API 请求、资源操作、用户动作和各类业务接口。
- `src/store`：状态管理层，按业务域拆分 Zustand store。
- `src/server`：服务端专用逻辑，包含 metadata、manifest、translation、runtime config、workflow、utility 等。
- `src/business`：根据当前片段推断，这里放跨端复用的业务规则与 provider，且按 `client` / `server` 划分。
- `src/hooks`、`src/helpers`、`src/utils`：通用函数和复用 hooks，给页面、features、services 提供底层能力。
- `src/libs`：第三方或平台封装层，比如 `trpc`、`swr`、`next`、`mcp`、`redis`、`qstash` 等适配。
- `src/config`、`src/envs`、`src/const`、`src/types`、`src/locales`、`src/styles`、`src/layout`：配置、环境变量、常量、类型、国际化、样式和全局布局相关基础层。

## 关键入口

- `src/app/layout.tsx`：Next.js 根布局，定义 HTML/body 壳，并挂载 analytics 等全局副作用。
- `src/app/(backend)/trpc/*`：后端 RPC 入口，说明这个仓库不只是纯前端。
- `src/spa/entry.web.tsx`、`src/spa/entry.desktop.tsx`、`src/spa/entry.mobile.tsx`、`src/spa/entry.popup.tsx`：不同宿主的 SPA 启动点。
- `src/spa/router/desktopRouter.config.tsx`、`src/spa/router/mobileRouter.config.tsx`、`src/spa/router/popupRouter.config.tsx`：各端路由树，其中桌面路由是最复杂的一条主线。
- `src/routes/(main)/_layout/index.tsx`：桌面主壳，负责 Hotkeys、导航、标题栏、主容器、`Outlet` 和全局面板。
- `src/routes/onboarding/index.tsx`：新手引导入口，属于独立业务流。
- `src/initialize.ts`：从 `src/spa/entry.web.tsx` 可见它会在应用启动前先执行，用于初始化环境。
- `src/proxy.ts`、`src/auth.ts`：分别对应本地代理和认证相关的全局入口。

## 主流程位置

主流程可以分成前台 SPA 和后台能力两条。

前台部分，浏览器先进入 `src/spa/entry.*.tsx`，然后由对应路由配置创建 `react-router-dom` 路由树，再落到 `src/routes/...` 下的页面段。桌面端尤其明显：`src/spa/router/desktopRouter.config.tsx` 把 `/agent`、`/group`、`/community`、`/settings` 等大路由接到 `src/routes/(main)` 与 `src/features` 上，而 `src/routes/(main)/_layout/index.tsx` 则提供真正的桌面工作台外壳。

业务实现通常不写在路由文件里，而是下沉到 `src/features`、`src/services` 和 `src/store`。也就是说，`routes` 更像“装配层”，`features` 才是“功能层”，`services` 负责取数和副作用，`store` 负责页面状态。

后台部分，`src/app/(backend)`、`src/server` 和 `src/business/server` 共同承担服务端配置、元数据、翻译、workflow 和鉴权相关逻辑。`src/business/client` 则放客户端侧的业务 provider 和错误处理，和 server 侧形成明显分工。

## 推荐阅读顺序

1. 先看 `src/app/layout.tsx`，理解 Next.js 全局壳。
2. 再看 `src/spa/entry.web.tsx` 和 `src/spa/router/desktopRouter.config.tsx`，把 SPA 启动和路由总图串起来。
3. 接着看 `src/routes/(main)/_layout/index.tsx`，理解桌面主工作区如何拼装。
4. 然后浏览 `src/features`、`src/services`、`src/store` 的目录命名，建立功能域映射。
5. 最后补 `src/server`、`src/business/server`、`src/business/client`，确认哪些逻辑是服务端，哪些是客户端。

## 常见误区

- 把 `src/routes` 当成业务实现层。实际上这里应尽量保持“薄”，主要做路由段和装配。
- 只改了 `src/spa/router/desktopRouter.config.tsx`，忘了同步 `src/spa/router/desktopRouter.config.desktop.tsx`。从目录里能看到它们并存，说明桌面路由有双配置源，容易出不一致问题。
- 把 `src/app` 和 `src/routes` 混为一谈。前者是 Next.js 壳和后端入口，后者是 SPA 页面树，职责不同。
- 在 `src/features` 里继续堆全局状态或接口细节。更合适的边界通常是：页面装配放 `routes`，业务 UI 放 `features`，请求放 `services`，状态放 `store`。
- 忽略 `src/business/client` 与 `src/business/server` 的分层。这个目录名已经提示它是跨端业务规则，不应随意交叉引用。
