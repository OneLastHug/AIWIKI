# 目录：src/routes/(main)/eval

## 它负责什么

`src/routes/(main)/eval` 从路径命名上看，属于 LobeHub SPA 主应用路由树里的一个页面段：`(main)` 表示主界面路由分组，`eval` 通常对应评测、评估或调试类页面入口。按照仓库约定，`src/routes/` 下的目录应当只承载“路由壳”：也就是 `_layout/index.tsx`、`index.tsx`、动态段页面等薄层入口，不应该把复杂业务逻辑、状态管理、请求流程或重型 UI 直接放在这里。

不过，根据当前片段推断，本次环境中未能读取到目标目录本身；目标路径 `src/routes/(main)/eval` 以及相邻的 `src/routes`、`src/spa/router/desktopRouter.config.tsx`、`src/spa/router/desktopRouter.config.desktop.tsx` 在当前可见文件树下没有命中。因此下面的说明是基于仓库给出的路由规范、目标路径命名和 LobeHub 的 SPA 组织方式进行的地图式概览，而不是对真实文件内容的逐项展开。

这个目录如果存在，核心职责应当是把 `/eval` 这一路由挂到主应用页面中，并把实际页面内容转交给 `src/features/` 下的某个评测相关 feature，例如 `Eval`、`Evaluation`、`AgentEval` 或类似命名的领域模块。它更像“导航入口”和“页面装配点”，不是评测逻辑本体。

## 直接子目录地图

由于目标目录当前不可见，无法确认真实子目录列表。根据 LobeHub 的 SPA 路由约定，`src/routes/(main)/eval` 这类页面段通常可能包含以下几类结构：

`src/routes/(main)/eval/index.tsx`：最常见的页面入口。它通常只导入 feature 层组件并返回页面组件，例如从 `@/features/...` 引入主页面容器。

`src/routes/(main)/eval/_layout/index.tsx`：如果 `eval` 页面需要自己的局部布局，例如左侧评测列表、顶部工具栏、二级导航或上下文 Provider，可能会有这个 layout。它应当仍然保持薄层，只负责拼装布局和 `Outlet`，不承载核心业务。

`src/routes/(main)/eval/[id]/index.tsx`：如果评测页面存在详情页、任务页、报告页或会话级页面，可能会通过动态段表达某个评测对象的详情入口。动态参数解析可以在路由层拿到，但具体加载与展示应继续下沉到 feature、store 或 service。

`src/routes/(main)/eval/*` 的更深层子目录：如果存在，通常表示二级页面，例如结果、配置、运行记录等。但按照仓库说明，路由目录不应变成业务目录；复杂 UI 和逻辑应搬到 `src/features/`，路由层只保留页面段。

## 关键入口

关键入口首先应看 `src/routes/(main)/eval/index.tsx`。这是理解这个目录的第一站，因为它决定 `/eval` 根页面展示什么，以及实际依赖哪个 feature 模块。如果它只导入并渲染一个组件，例如 `EvalPage`、`Evaluation` 或 `EvalContainer`，那么真正的阅读重点不在路由目录，而在对应的 `src/features/...` 模块。

第二个入口是可能存在的 `src/routes/(main)/eval/_layout/index.tsx`。如果目录下有多个子页面，layout 会说明这些页面共享哪些外壳：例如导航、权限边界、数据上下文、响应式布局、错误边界等。对于 overview 深度，重点不是每个组件细节，而是识别“共享外壳在哪里、页面内容在哪里插入”。

第三个入口是 SPA router 注册位置。根据仓库约定，桌面主路由需要同时关注 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx`，两者必须保持路径和嵌套一致。当前环境未能读取到这两个文件，但如果目录存在，正常排查时应确认 `eval` 是否被挂进主路由树，以及它是一级入口、懒加载页面，还是某个父路由下的子页面。

## 主流程位置

`src/routes/(main)/eval` 的主流程通常不是“评测执行流程”，而是“路由进入页面的流程”。用户访问对应路径后，React Router 命中 `eval` 页面段；如果存在 `_layout`，先进入 layout；再由 `index.tsx` 或动态子路由渲染实际页面；页面组件随后调用 feature 层 hook、store action 或 service 方法完成数据加载、状态更新和 UI 展示。

根据当前片段推断，真正的评测主流程更可能分布在这些位置：`src/features/` 下的评测页面和组件负责用户交互；`src/store/` 下的 zustand slice 负责页面状态、任务状态或缓存；`src/services/` 下的 service 负责调用客户端 API；`src/server/routers/` 或 `src/app/(backend)/` 下的后端入口负责服务端过程；如果涉及模型调用或评测运行，还可能关联 `packages/agent-runtime`、`packages/` 下的共享包。

因此阅读这个目录时要把它当成“指路牌”。它告诉你从哪个 URL 进入、页面壳如何组合、业务模块从哪里导入；但它通常不会解释评测规则、执行队列、结果计算或报告生成。这些应继续顺着 import 跳到 feature、service、server 和 package 层。

## 推荐阅读顺序

1. 先确认 `src/routes/(main)/eval` 是否真实存在，以及目录下有哪些一级文件和子目录。overview 阶段只需要看三类文件：`index.tsx`、`_layout/index.tsx`、动态段入口。

2. 再看 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 中是否注册了 `eval`。重点确认路径、父级、懒加载方式、是否与 desktop 专用配置同步。

3. 接着从路由文件的 import 追到 `src/features/`。这一步才是理解页面能力的关键：页面标题、列表、详情、表单、运行按钮、结果视图等一般都在 feature 层。

4. 如果页面涉及数据加载，再继续看 `src/services/` 和 `src/store/`。服务层说明 API 边界，store 说明页面状态和动作组织方式。

5. 最后才看后端路由、数据库或运行时包。只有当 feature/service 明确指向这些模块时，才需要继续深入，避免从路由目录直接扩散到全仓库。

## 常见误区

第一个误区是把 `src/routes/(main)/eval` 当成完整业务模块来读。按照仓库规范，`src/routes/` 是 roots，不是 features。这里应该很薄；如果大量业务代码出现在这里，反而说明它可能偏离了项目约定。

第二个误区是只看 web 路由配置，不看 desktop 路由配置。LobeHub 的桌面路由要求 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 同步。新增或调整 `eval` 页面时，只改一个配置可能导致某个构建入口出现空白页。

第三个误区是从目录名直接推断评测能力。`eval` 只能说明页面意图，不能证明它实现了哪些评测类型、指标、模型调用或报告功能。没有读到 feature、service 和后端入口前，只能说“根据当前片段推断”。

第四个误区是逐个叶子文件展开。对于 overview 文档，更重要的是确认层级角色：路由入口在哪里，layout 是否存在，页面委托给哪个 feature，主流程从哪里继续，而不是解释每个按钮、每个 hook 或每个样式文件。

第五个误区是忽略缺失证据。当前环境没有读取到目标目录本体，所以不能把任何具体文件名、组件名或函数名写成已确认事实。后续如果重新提供可见源码，应优先补充真实子目录地图和 import 流向，再把本文中的推断部分替换为源码证据。
