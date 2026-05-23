# 目录：src/routes/(desktop)/desktop-onboarding

## 它负责什么

`src/routes/(desktop)/desktop-onboarding` 是桌面端专用的 SPA 路由段，用来承载 Electron / desktop 运行环境里的首次启动引导、初始化说明或桌面端特有的 onboarding 页面。它位于 `src/routes/(desktop)` 路由组下，说明它不是普通 Web 主站页面，也不是移动端页面，而是只面向桌面壳层或桌面构建入口暴露的页面段。

从项目约定看，`src/routes` 下的目录应当是“路由根”，职责偏薄：负责把某个 URL 段接入 React Router，并组合 layout/page；真正复杂的业务 UI、状态流转、按钮行为、初始化逻辑，通常应下沉到 `src/features`、`src/store`、`src/services`、`src/hooks` 等位置。也就是说，这个目录在架构上更像“桌面 onboarding 页面挂载点”，而不是完整业务模块本身。

根据当前片段推断，`desktop-onboarding` 关注的生命周期大概率是：桌面应用启动后判断用户是否完成过桌面端初始化；若未完成，则进入该路由；用户完成配置、跳过或确认后，再跳转到主应用页面。判断依据是它处在 `(desktop)` 路由组中，且命名直接指向桌面端 onboarding，而不是通用的 `onboarding` 路由。

## 直接子目录地图

本次可确认的稳定信息是：目标目录本身存在于 `src/routes/(desktop)/desktop-onboarding`，它属于 desktop 专用路由树。由于当前可读取片段没有成功展开完整叶子树，下面按 LobeHub 路由约定给出地图式理解，涉及具体子目录时以“根据当前片段推断”标注。

常见的直接结构会围绕以下几类角色展开：

- `index.tsx` 或同级页面入口：通常是该路由段的默认页面组件，负责导出给 React Router 使用的页面。
- `_layout`：如果存在，通常用于包裹该 onboarding 页面自己的布局，例如桌面端无侧边栏的全屏引导框架、背景层、窗口安全区或标题栏适配。
- `features` 或局部组件目录：如果存在，可能是历史结构或尚未迁移的 route-local UI。按当前仓库约定，新业务组件更推荐放在 `src/features/<Domain>/`，路由目录只做组合。
- `style`、`components`、`hooks` 等局部目录：如果存在，应理解为服务于这一页的局部实现；但在阅读时要警惕这些逻辑是否其实属于可复用 feature 层。

所以阅读这个目录时，不要把它当作完整“桌面引导系统”的唯一位置。它更像路由侧入口，真正的桌面端判断、状态写入、完成后跳转、偏好设置持久化，可能分散在 `src/features`、`src/store`、`src/services` 或 desktop 相关桥接代码中。

## 关键入口

第一入口是 `src/routes/(desktop)/desktop-onboarding` 下的页面导出文件，通常会是 `index.tsx`。它决定访问该路由时渲染什么组件，也是确认页面组成的起点。

第二入口是 React Router 配置。桌面路由通常需要关注 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx`。仓库约定要求这两个 desktop router 配置保持路径和嵌套同步，否则某些构建路径可能出现空白页。即使当前目标位于 `(desktop)` 组，也不能只看单个 router 文件。

第三入口是桌面运行时入口，例如 `src/spa/entry.desktop.tsx` 以及 Electron 相关的启动链路。它们不一定直接写 `desktop-onboarding`，但会决定桌面 SPA 采用哪套路由配置、哪些 provider 和运行环境能力会注入进页面。

第四入口是业务承载组件。根据当前片段推断，如果页面中导入了类似 `@/features/DesktopOnboarding`、`@/features/Onboarding` 或桌面初始化相关组件，那里才是页面内容、步骤控制和用户操作的主要阅读位置。

## 主流程位置

主流程可以按“进入条件、页面呈现、动作提交、离开路由”四段来理解。

进入条件通常不在这个目录内部完成，而是在桌面启动、路由守卫、应用初始化 store 或 desktop service 中完成。它会判断用户是否第一次启动、是否完成过 desktop onboarding、是否需要展示桌面端能力介绍或配置向导。这个判断结果最终会让应用进入 `desktop-onboarding` 路由。

页面呈现发生在 `src/routes/(desktop)/desktop-onboarding` 的页面入口处。这里一般只负责挂载真正的 onboarding 组件，并可能套一层 desktop 专属 layout。若看到大量表单、状态判断或副作用逻辑集中在路由文件中，要结合仓库“routes thin、features heavy”的约定来看，它可能是待迁移或历史实现。

动作提交通常会落到 store action、client service 或 desktop bridge。典型动作包括完成 onboarding、跳过引导、写入用户偏好、打开系统权限设置、进入主聊天页等。因为这是桌面端目录，涉及本地能力时还可能经过 Electron IPC、desktop preload 或 desktop service，而不是纯浏览器 API。

离开路由通常通过 React Router navigation 完成，目标可能是主聊天页、首页或桌面工作区默认页。这里要注意：路由页面只看到 `navigate` 并不代表业务结束；真正的“已完成 onboarding”标记往往还要看 store 持久化、用户配置或本地存储更新。

## 推荐阅读顺序

1. 先看 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx`，确认 `desktop-onboarding` 在桌面路由树里的路径、父级 layout、是否懒加载，以及两个配置是否同步。

2. 再看 `src/routes/(desktop)/desktop-onboarding` 的入口文件，判断它只是导入 feature，还是在路由层直接承载了页面逻辑。

3. 顺着入口里的 import 进入 `src/features` 下对应模块，阅读步骤组件、按钮动作、完成状态和跳转逻辑。这里通常比 route 文件更接近主流程。

4. 如果页面涉及“完成后不再展示”，继续查相关 store 或 service，例如 user setting、global preference、desktop setting、onboarding 状态等。重点看状态在哪里写入，在哪里读取。

5. 最后再回到 desktop 启动链路，例如 `src/spa/entry.desktop.tsx`、desktop router、Electron 相关目录，确认这个 onboarding 页面如何被桌面应用触达。

## 常见误区

第一个误区是把 `src/routes/(desktop)/desktop-onboarding` 当成完整业务模块。它的位置决定了它首先是路由段；如果要理解业务，必须顺着 import 去 feature、store、service 继续看。

第二个误区是只改或只读一个 desktop router 配置。这个仓库明确要求 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 保持同步；桌面端页面出现空白时，路由配置不一致是高风险排查点。

第三个误区是把它和通用 `src/routes/onboarding` 混为一谈。`desktop-onboarding` 位于 `(desktop)` 组，语义上偏 Electron / desktop 专属；通用 onboarding 更可能面向 Web 或跨端新用户流程。两者可能复用 feature，但入口语义不同。

第四个误区是只看 UI，不看状态持久化。onboarding 类页面最关键的不是展示几步，而是“什么时候出现”和“完成后如何不再出现”。这些判断通常藏在 store、setting、local storage、server preference 或 desktop 本地能力中。

第五个误区是忽视桌面环境能力。若流程里有文件系统、系统权限、窗口控制、自动更新、本地模型或 IPC 调用，它们不会是普通 Web API，需要顺着 desktop bridge 或 Electron 代码继续追踪。
