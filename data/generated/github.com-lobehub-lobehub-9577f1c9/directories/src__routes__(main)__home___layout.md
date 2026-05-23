# 目录：src/routes/(main)/home/_layout

## 它负责什么

`src/routes/(main)/home/_layout` 从命名和仓库约定看，应当是 SPA 主区 `home` 路由的布局段目录。它位于 `src/routes/` 下，而不是 `src/features/` 下，因此它的职责通常不是承载复杂业务逻辑，而是作为路由树中的“页面骨架入口”：接收 React Router 命中的 `home` 分支，挂载该分支需要的外层布局，再把实际内容交给子路由或 `src/features/*` 中的业务组件。

根据当前片段推断，这个目录更接近“路由层 layout”而不是“功能模块 layout”。依据是仓库的 SPA 约定明确要求 `src/routes/` 只放页面段文件，如 `_layout/index.tsx`、`index.tsx`、动态段等；重 UI、hooks、状态和领域逻辑应下沉到 `src/features/`。因此阅读这个目录时，重点不应放在寻找业务规则，而应关注它怎样把 `home` 路由接入主框架、是否提供嵌套路由出口、是否包裹桌面/移动差异布局、以及它与 router config 的路径关系。

需要说明的是，在当前可读环境片段中，目标路径 `src/routes/(main)/home/_layout` 未能直接解析到实际文件清单，`src/routes` 和 `src/spa/router` 也未在当前工作目录下命中。因此以下内容是基于仓库给出的结构规范和路径语义做的 overview 级说明；涉及具体文件名时，以“常见入口位置”和“应检查位置”的方式描述，而不假定源码中一定存在某个实现细节。

## 直接子目录地图

当前片段没有取得 `src/routes/(main)/home/_layout` 的真实子目录清单。按 LobeHub SPA 路由约定，这类 `_layout` 目录通常应保持很薄，理想结构可能只有一个入口文件，例如 `src/routes/(main)/home/_layout/index.tsx`，也可能按平台或局部布局拆出少量邻近组件。

如果该目录下存在子目录，建议按角色理解，而不是逐个叶子文件展开：

`components/`：通常放仅服务于这个 layout 的轻量局部组件，例如顶部容器、局部占位、简单分区。若组件开始包含业务状态、数据请求或复用价值，应优先移动到 `src/features/Home` 或相关 feature 目录。

`hooks/`：如果存在，应只放 layout 层需要的薄 hook，例如读取路由参数、布局可见性或简单响应式判断。涉及会话、助手、知识库、文件、模型等领域行为的 hook 不应沉在这里。

`style`、`styles` 或 `style.ts`：如果存在，通常承载 layout 外壳样式。结合仓库规范，样式应优先使用 `antd-style` 的 `createStaticStyles` 与 `cssVar.*`，只有确实需要运行时 token 计算时再使用 `createStyles`。

`desktop/`、`mobile/` 或平台后缀文件：如果出现，说明 home layout 可能对不同入口做了平台适配。此时应同时关注 `src/spa/router/desktopRouter.config.tsx`、`src/spa/router/desktopRouter.config.desktop.tsx`、`src/spa/router/mobileRouter.config.tsx` 中对应路由是否一致。

## 关键入口

最关键的入口通常是 `src/routes/(main)/home/_layout/index.tsx`。在 LobeHub 的路由约定里，`_layout/index.tsx` 负责定义某个路由分支的外层组件。它一般会导入 feature 层导出的布局组件，例如从 `@/features/Home` 或相邻领域模块导入真正的页面框架，然后返回布局结构。

第二类关键入口是上层路由注册文件。对于主桌面 SPA，重点应检查 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx`。仓库说明中特别强调这两个 desktop router config 必须保持路径和嵌套同步，否则不同构建路径可能出现空白页。也就是说，`_layout` 本身即便写对了，如果 router config 没有把它挂到正确的 `home` 分支，页面仍然不会进入该布局。

第三类入口是它包裹的下级页面段。一般会在 `src/routes/(main)/home/index.tsx` 或 `src/routes/(main)/home/*/index.tsx` 一类位置继续承载页面入口。`_layout` 的职责是给这些子页面提供共同外壳，而不是替代子页面实现内容。

第四类入口是 feature 暴露点。如果 layout 文件只是薄封装，那么真正值得继续读的往往是 `src/features/Home/index.ts`、`src/features/Home/index.tsx` 或相关领域 feature 的导出文件。这里通常能看到布局被拆成哪些业务区域，例如侧边栏、内容区、导航区、空状态或快捷入口。

## 主流程位置

主流程可以按“路由配置命中 → layout 挂载 → feature 组件渲染 → 子路由出口渲染”理解。

第一步发生在 `src/spa/router/*`。React Router 的配置把 `home` 路径绑定到 `src/routes/(main)/home/_layout` 这一层。对于桌面主路由，需要尤其注意 `desktopRouter.config.tsx` 与 `desktopRouter.config.desktop.tsx` 的一致性；对于移动端，则要看 `mobileRouter.config.tsx` 是否另有分支。

第二步进入 `src/routes/(main)/home/_layout`。这里通常完成主页面外壳选择：是否套用主应用布局、是否渲染侧边栏或导航栏、是否放置 `<Outlet />`，以及是否接入少量 layout 级上下文。它应该尽量不直接写数据拉取、业务判断或复杂交互。

第三步进入 feature 层。根据仓库规范，`src/routes/` 只作为 roots，业务 UI 应在 `src/features/`。因此 home 页面的真实功能区大概率在 `src/features/Home` 或名称相近的 feature 下。如果阅读时发现 `_layout` 文件中大量出现 store action、service 调用、复杂条件渲染或长列表 UI，就要警惕它可能违反了“route thin、feature heavy”的分层原则。

第四步是子页面出口。若 layout 使用 React Router 的 `<Outlet />`，则后续内容来自 `home` 下的子路由；若没有 `<Outlet />`，则它可能直接挂载一个 feature 页面组件。overview 阶段只需要确认主流程在哪里断开和交接，不需要展开每个子页面。

## 推荐阅读顺序

1. 先读 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 中 `home` 相关配置，确认 `_layout` 在路由树中的父子关系、路径段和嵌套层级。

2. 再读 `src/routes/(main)/home/_layout/index.tsx`。重点看它导入了哪些 feature、是否使用 `<Outlet />`、是否区分平台、是否只是组合布局。

3. 接着读 `src/routes/(main)/home/index.tsx` 以及同级子路由入口，理解 layout 包住的是哪个默认页面或哪些子页面。

4. 然后进入 `src/features/Home` 或 layout 实际导入的 feature 目录。这里才是阅读业务组件、状态流、数据加载和交互细节的主要位置。

5. 最后回到样式和测试。如果 layout 有局部样式，查看是否遵循 `createStaticStyles` 与 `cssVar.*`；如果改动过路由结构，还应关注类似 `desktopRouter.sync.test.tsx` 的同步测试。

## 常见误区

第一个误区是把 `_layout` 当作业务模块阅读。`src/routes/(main)/home/_layout` 的核心价值是定位 home 路由分支的外壳和交接点，不是解释 Home 功能本身。真正的业务应去 `src/features/*` 找。

第二个误区是只看一个 desktop router config。这个仓库明确要求 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 保持同步。只改或只读其中一个，容易误判页面为什么能在某个入口显示、却在另一个入口空白。

第三个误区是把 `src/routes/` 下的目录当成可以随意放组件的地方。按照项目约定，route tree 应该薄，新增复杂组件、hooks、数据请求逻辑时，应优先放在 `src/features/<Domain>/`，再由 route 入口导入组合。

第四个误区是看到 `_layout` 就默认它一定负责全局应用框架。这里的 `_layout` 更可能只是 `home` 分支布局；全局级别的壳可能在更上层的 `(main)` layout、SPA entry 或主 router 中。阅读时要顺着父路由向上确认，不要只凭目录名判断作用域。

第五个误区是忽略平台差异。`(main)`、`(mobile)`、`(desktop)`、`.desktop.tsx` 等命名在这个仓库里有明确意义。若 home layout 通过条件导入或路由配置参与多端渲染，需要同时理解 web、desktop、mobile 的入口差异。
