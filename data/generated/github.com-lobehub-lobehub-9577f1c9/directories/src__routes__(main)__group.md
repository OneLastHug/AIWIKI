# 目录：src/routes/(main)/group

## 它负责什么

`src/routes/(main)/group` 位于 LobeHub SPA 的主应用路由组 `(main)` 下，按仓库约定，它应负责桌面主界面中的 `group` 路由页面段。这里的“负责”主要是路由层职责：承接 React Router 中 `/group` 相关路径，组织该路径下的页面入口、布局入口和动态子页面入口，并把实际页面能力连接到更下层的业务组件、store、service 或 feature 模块。

根据当前片段推断，这个目录与“分组”类功能相关，可能用于展示、管理或进入某类 group 资源，例如 agent group、会话分组、资源分组或团队/群组式页面。推断依据是路径名 `group`、所在位置 `src/routes/(main)`，以及 LobeHub 的 SPA 目录规范：`src/routes/` 是页面段 roots，业务 UI 与逻辑通常应下沉到 `src/features/`、`src/store/`、`src/services/` 等目录。

需要注意的是，当前可读片段只确认了仓库的路由分层约定，没有足够证据逐项展开 `src/routes/(main)/group` 的真实文件树。因此下面是地图式概览，重点说明这个目录在系统中的角色、常见入口和应优先阅读的位置；涉及具体文件存在性时，以“如果存在”或“根据当前片段推断”表达。

## 直接子目录地图

按 LobeHub SPA route roots 的惯例，`src/routes/(main)/group` 下面通常会围绕“布局入口、列表页入口、详情页入口、局部组件”形成几类节点：

`_layout/` 是最值得优先关注的子目录。如果存在 `src/routes/(main)/group/_layout/index.tsx`，它通常是 `group` 路由段的父布局入口，负责放置 `<Outlet />`，并包裹该路由下共享的导航、侧栏、主体区域或数据同步组件。按照当前项目约定，新的实现应尽量保持这个文件很薄，只组合来自 `src/features/*` 的组件。

`[id]/` 或类似动态段目录代表详情页、单个 group 的页面、或某个 group 资源的内部页面。如果存在 `src/routes/(main)/group/[id]/index.tsx`，它通常承接 `/group/:id` 这种路径，主流程会从 URL 参数进入，再读取对应资源详情或渲染对应工作区。

`features/`、`components/`、`hooks/`、`style.ts` 等目录或文件如果出现在这里，通常说明这是一个尚未完全迁移到 roots/features 分层的新旧混合路由。LobeHub 当前规范更推荐把重业务 UI 放到 `src/features/<Domain>/`，让 `src/routes/(main)/group` 只保留页面段入口。但历史路由可能仍在 route 目录内部保留局部组件、样式和 hooks。

`index.tsx` 如果位于 `group` 根部，通常是 `/group` 的默认页面入口。它可能渲染 group 列表、默认空状态、引导页，或者在某些条件下跳转到默认 group。它是理解“进入 group 路由后先看到什么”的核心文件。

## 关键入口

第一个关键入口是路由注册位置。桌面主应用的路由树通常在 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 中维护。前者偏动态导入和代码拆分，后者偏同步导入，二者需要保持同一棵路由树。阅读 `group` 时，建议先在这两个文件中搜索 `group`，确认它的 `path`、父级布局、子路由结构，以及是否存在 index route 或动态 segment。

第二个关键入口是 `src/routes/(main)/group/_layout/index.tsx`。如果该文件存在，它定义了 group 路由段的外壳边界：哪些 UI 是所有 group 子页面共享的，哪些部分通过 `<Outlet />` 留给子页面渲染。布局入口还能帮助判断这个目录是独立工作区，还是嵌在主应用已有 layout 之下。

第三个关键入口是 `src/routes/(main)/group/index.tsx`。它通常对应 `/group` 默认页，是用户进入该路由后的第一屏逻辑。这里可以看到默认数据加载、默认选择、空态、跳转或入口组件。

第四个关键入口是动态页面，例如 `src/routes/(main)/group/[id]/index.tsx`。它通常承载“选中某个 group 后”的主流程，关注点包括如何读取 route param、如何找到对应 store 数据、如何处理不存在的 id，以及是否与聊天、agent、资源或设置等模块联动。

## 主流程位置

从运行链路看，`group` 页面的主流程大致从 SPA entry 进入 React Router，再由桌面 router config 命中 `group` 路由段，随后渲染 `src/routes/(main)/group` 下的 layout 或 page 文件。也就是说，路由主流程位置首先不在该目录内部，而是在 `src/spa/router/desktopRouter.config.tsx`、`src/spa/router/desktopRouter.config.desktop.tsx` 中完成挂载。

进入目录内部后，主流程通常分两层：父布局层和页面内容层。父布局层负责稳定的壳，例如侧栏、顶部栏、容器尺寸、滚动区域、数据预加载边界；页面内容层负责具体 group 列表、详情、空状态或编辑交互。根据当前片段推断，如果 `group` 仍是旧式路由，业务逻辑可能直接散落在该目录下的组件和 hooks 中；如果已经迁移，则主流程会很快跳转到 `src/features/Group`、`src/features/Agent` 或其他领域目录。

数据主流程通常不会止步于 route 文件。route 入口会调用 feature 组件，feature 组件再使用 zustand store、client service 或 SWR/TRPC 数据层。对应的阅读线索包括 `src/store/` 下与 group、agent、session、chat 等相关的 slice，以及 `src/services/`、`src/server/routers/` 中的后端调用。对于 overview 深度，只需要知道 route 目录是“接线层”，真正的数据读写大多在这些下游模块。

## 推荐阅读顺序

1. 先读 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 中的 `group` 注册，确认 URL 结构、父子嵌套和入口组件。两个文件要一起看，因为桌面路由要求结构保持同步。

2. 再读 `src/routes/(main)/group/_layout/index.tsx`。如果存在这个文件，先理解它提供了哪些共享布局和上下文，再看它如何把子页面交给 `<Outlet />`。

3. 接着读 `src/routes/(main)/group/index.tsx`。这个文件通常回答“访问 `/group` 默认看到什么”，也是判断默认态、空态和跳转策略的入口。

4. 然后读动态段入口，例如 `src/routes/(main)/group/[id]/index.tsx`。这一步用于理解单个 group 的详情页、选中态和参数驱动流程。

5. 最后沿 import 追到 `src/features/`、`src/store/`、`src/services/`。只在需要理解具体业务时继续深入；如果只是建立目录地图，读到 route 如何委托给 feature 就可以停下。

## 常见误区

第一个误区是把 `src/routes/(main)/group` 当成完整业务模块。按照 LobeHub 当前规范，`src/routes/` 更像页面段根目录，理想状态下只负责 layout、page、dynamic segment 入口。真正复杂的 UI、hooks、状态和数据逻辑应放在 `src/features/`、`src/store/`、`src/services/` 等位置。若在 `group` 目录内看到较多组件，不代表这是推荐的新结构，更可能是历史实现或渐进迁移中的状态。

第二个误区是只看 `src/routes/(main)/group`，不看 router config。React Router 的真实路径、嵌套关系、index route 是否生效，都由 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 决定。仅凭目录名推断 URL 容易漏掉父级 layout、重定向或动态加载包装。

第三个误区是修改或理解桌面路由时只看一个 router config。这个仓库明确要求桌面路由树在两个配置文件中保持同步；一个用于动态导入路径，一个用于桌面侧同步导入路径。阅读时也应成对验证，否则可能误判某个路由“存在但运行时空白”的原因。

第四个误区是把 `group` 的数据来源直接等同于 route 文件。route 文件通常只是把页面挂上去；数据可能来自 zustand store、SWR、TRPC router、server service，甚至与 agent、chat、session 等领域交叉。overview 阶段应先画清楚入口和委托关系，再决定是否继续深入数据层。

第五个误区是逐个叶子文件解释这个目录。对于 `src/routes/(main)/group` 这种路由目录，更有价值的是识别入口层级：router 注册、layout、index page、dynamic page、feature/store/service 下游。只有当要改具体功能时，才需要继续展开每个组件文件。
