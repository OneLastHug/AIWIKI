# 目录：packages/desktop/src/renderer

## 它负责什么

`packages/desktop/src/renderer` 是桌面端 Electron 应用的渲染进程代码区域，职责是承载用户界面、页面路由、交互状态、组件组合、样式覆盖以及通过预加载层暴露出来的 IPC 能力调用。按照项目约束，`renderer` 内只能使用浏览器 / DOM / React 相关能力，不应直接使用 Node.js API，也不应绕过 `packages/desktop/src/preload` 去访问主进程能力。

根据当前片段推断，这个目录是 `packages/desktop` 中最接近“产品界面”的一层：它不负责系统托盘、窗口生命周期、文件系统、进程管理等主进程逻辑；它负责把主进程提供的能力组织成可见、可操作的桌面 UI。项目要求 UI 组件使用 `@arco-design/web-react`，图标使用 `@icon-park/react`，用户可见文案必须走 i18n key，因此这里也是国际化落地、主题样式、交互细节最密集的位置。

## 直接子目录地图

当前可见的项目说明明确提到 `packages/desktop/src/renderer/styles/`，这是全局样式与 Arco 主题覆盖的归属地。全局样式只能放在这里；Arco 的全局覆盖应集中在 `packages/desktop/src/renderer/styles/arco-override.css`；组件级覆盖则应使用 CSS Module 和 `:global()` 控制作用域。

根据当前片段推断，`renderer` 下还通常会按职责拆出以下类型目录：组件目录用于沉淀可复用 UI；页面或路由目录用于组织主要视图；hooks 目录放置 React 组合逻辑；状态目录管理 UI 状态或业务状态；服务 / API 封装目录负责调用 preload 暴露的桥接能力；工具目录保存纯前端辅助函数；资源目录存放渲染侧静态资产。具体名称需要以实际仓库为准，因为本次可见片段没有提供完整目录树。

阅读时不要把 `renderer` 当成独立 Web 项目理解，它是 Electron 渲染进程的一部分，很多“后端能力”并不在这里实现，而是通过 preload 和 main 间接接入。

## 关键入口

关键入口通常包括渲染进程的启动文件、根组件、路由挂载点、全局 provider 与样式入口。根据当前片段推断，入口文件大概率位于 `packages/desktop/src/renderer` 根部或其上层构建配置所指向的位置，例如 `main.tsx`、`App.tsx`、`router` 相关模块、全局样式 import 位置等。

判断入口时可以优先查找三类线索：第一，哪里调用了 React 渲染 API，例如 `createRoot`；第二，哪里引入了 `styles/` 下的全局 CSS 或 UnoCSS 入口；第三，哪里包裹了 Arco、i18n、状态管理、路由等全局 provider。找到这些位置后，基本就能串起“应用启动后最先执行什么、全局能力从哪里注入、页面如何被选择”的主线。

与主进程交互的入口不应在 `renderer` 中直接落到 Node API，而应表现为调用某个桥接对象、IPC client、preload 暴露的 API 或封装后的 service。看到这类调用时，需要继续追到 `packages/desktop/src/preload/` 和 `packages/desktop/src/process/`，而不是在 `renderer` 内寻找底层实现。

## 主流程位置

`renderer` 的主流程可以按“启动、装配、呈现、交互、跨进程调用”来理解。

启动阶段由渲染入口创建 React 应用，并加载全局样式、主题覆盖和基础 provider。装配阶段通常会挂载路由、国际化、全局状态、Arco 配置、错误边界等横切能力。呈现阶段由页面级模块组合业务组件，形成最终界面。交互阶段由组件事件、hooks、store 更新驱动 UI 变化。跨进程调用阶段则通过 preload 暴露的接口向主进程请求能力，例如文件、窗口、系统集成或本地资源访问。

样式主流程集中在 `packages/desktop/src/renderer/styles/` 以及组件局部样式中。项目偏好 UnoCSS utility class，复杂样式才使用 CSS Modules。颜色应使用 `uno.config.ts` 中的语义 token 或 CSS 变量，不应在组件里随手硬编码颜色。

文案主流程不在 JSX 里直接写中文或英文，而是通过 i18n key 获取。凡是 `renderer` 新增按钮、菜单、提示、表单标签、空状态、错误信息，都应同步考虑 `locales/` 和 i18n 类型生成流程。

## 推荐阅读顺序

1. 先看 `packages/desktop/src/renderer` 的根入口，定位 React 应用从哪里创建、全局样式从哪里引入、根组件是谁。
2. 再看根组件或路由配置，建立页面结构地图，知道主要视图之间如何切换。
3. 接着看全局 provider、状态管理和 hooks，理解界面状态如何流动。
4. 然后看 `packages/desktop/src/renderer/styles/`，掌握 Arco 覆盖、全局样式和主题 token 的边界。
5. 遇到跨进程调用时，再跳到 `packages/desktop/src/preload/` 看桥接定义，最后追到 `packages/desktop/src/process/` 看主进程实现。
6. 最后阅读具体组件和页面，不要一开始逐文件展开，否则容易被 UI 细节淹没。

## 常见误区

第一个误区是把 `renderer` 当成可以随意访问系统能力的地方。它属于渲染进程，不能直接混入 Node.js、文件系统或主进程 API；跨进程能力必须通过 IPC bridge。

第二个误区是在组件里硬编码用户可见文案。项目要求所有用户可见文本使用 i18n key，修改 `renderer` 文案时通常还要关注 `locales/`、`packages/desktop/src/common/config/i18n`、`bun run i18n:types` 和 `node scripts/check-i18n.js`。

第三个误区是绕开设计系统写原生交互控件。项目约束要求使用 `@arco-design/web-react`，不要在业务 UI 中随意写原生 `<button>`、`<input>`、`<select>` 等交互元素。

第四个误区是把样式分散到任意位置。全局样式应留在 `packages/desktop/src/renderer/styles/`，组件复杂样式使用 CSS Module，颜色走语义 token 或 CSS 变量。

第五个误区是从叶子组件开始读源码。`renderer` 是一个大目录时，正确方式是先建立入口、路由、状态、IPC、样式的地图，再进入具体页面；否则很难判断某个组件在主流程中的真实位置。
