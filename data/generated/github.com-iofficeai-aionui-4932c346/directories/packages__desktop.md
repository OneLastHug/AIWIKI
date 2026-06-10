# 目录：packages/desktop

## 它负责什么

`packages/desktop` 是 AionUi 的桌面端应用包，按项目约定属于 Electron 形态的前端客户端。它承载桌面应用的三类核心代码：主进程能力、预加载桥接能力、渲染进程界面。根据当前片段推断，这个目录不是普通 Web 单页应用目录，而是把 Electron 的 `main`、`preload`、`renderer` 三段职责放在同一个 package 下管理。

它的边界很明确：`packages/desktop/src/process/` 面向 Electron 主进程，负责窗口、应用生命周期、系统能力、文件或进程级逻辑，不能使用 DOM API；`packages/desktop/src/renderer/` 面向界面渲染，负责 React UI、页面状态、组件和样式，不能直接使用 Node.js API；`packages/desktop/src/preload/` 是两者之间的 IPC 暴露层，把主进程能力以受控接口开放给渲染进程。公共配置、类型、国际化配置等共享内容位于 `packages/desktop/src/common/` 一类位置。

这个目录的学习重点不是逐个组件看 UI，而是先理解“桌面壳、桥接层、渲染界面”三段如何分工，再回到具体功能模块。

## 直接子目录地图

根据当前片段和项目约定，`packages/desktop` 下最重要的目录是 `src`。它是桌面端源码主体，内部再按进程边界分层。

`src/process` 是主进程代码区。这里应放 Electron app 启动、BrowserWindow 创建、系统菜单、托盘、原生能力、文件系统或后台任务等逻辑。凡是需要 Node.js 或 Electron 主进程 API 的能力，都应优先在这里落点。

`src/preload` 是预加载脚本与 IPC bridge 区。它连接 `process` 和 `renderer`，通常通过 `contextBridge` 或项目封装的桥接 API，把安全、有限、类型化的能力挂到渲染端可访问对象上。跨进程通信不应绕过这里。

`src/renderer` 是桌面端 UI 区。这里承载 React、Arco Design 组件、UnoCSS 工具类、CSS Modules、页面路由、视图状态和用户交互。它只能依赖浏览器环境与桥接出来的 API，不应直接读写本地文件或调用 Node 模块。

`src/common` 是共享约定区。根据项目指南，`packages/desktop/src/common/config/i18n-config.json` 定义国际化语言和模块，因此公共配置、跨进程类型、常量、协议名等也应在这一层附近寻找。

除 `src` 外，`packages/desktop` 通常还会有 package 级配置，例如 `package.json`、构建配置、TypeScript 配置或 Electron/Vite 配置。由于当前可见片段未展开这些文件，具体名称需要以仓库实际文件为准。

## 关键入口

桌面端入口应分三条线阅读。

第一条是主进程入口，位置根据当前片段推断在 `packages/desktop/src/process/` 下，常见文件名可能是 `main.ts`、`index.ts` 或由 Electron/Vite 配置指定的入口文件。它负责启动 Electron 应用、创建窗口、注册 IPC handler，并在应用生命周期事件中安排初始化和清理。

第二条是 preload 入口，位置在 `packages/desktop/src/preload/`。它是渲染进程能接触本地能力的唯一正规通道。学习时要重点看它暴露了哪些命名空间、每个 API 对应哪个 IPC channel、参数和返回值是否有类型约束。

第三条是渲染入口，位置在 `packages/desktop/src/renderer/`。React 应用通常从入口文件挂载根组件，再进入路由、布局、页面和功能组件。这个目录还会关联 `packages/desktop/src/renderer/styles/`，其中全局样式和 Arco 覆盖样式有固定位置要求，例如 `packages/desktop/src/renderer/styles/arco-override.css`。

国际化配置入口是 `packages/desktop/src/common/config/i18n-config.json`。凡是 UI 文案、菜单文案、提示文本，都不应硬编码，而应通过 i18n key 进入语言资源体系。

## 主流程位置

应用启动主流程从 `src/process` 开始：Electron app 初始化后创建主窗口，加载渲染进程资源，并注册主进程侧的 IPC 服务。这里决定桌面应用的外壳行为，例如窗口打开、关闭、最小化、权限、菜单和底层服务生命周期。

跨进程调用主流程经过 `src/preload`：渲染进程触发某个动作后，不直接访问 Node.js，而是调用 preload 暴露的 API；preload 通过 IPC 把请求发送到主进程；主进程完成实际工作后返回结果。读代码时可以按“renderer 调用名 -> preload 暴露方法 -> IPC channel -> process handler”这条链路追踪。

界面交互主流程在 `src/renderer`：用户操作 Arco 组件或业务组件，组件更新本地状态或调用桥接 API，再根据返回结果刷新 UI。样式优先使用 UnoCSS 工具类，复杂样式放 CSS Modules；组件库使用 `@arco-design/web-react`，图标使用 `@icon-park/react`。

配置和公共契约主流程在 `src/common`：跨进程共享的类型、常量、配置、i18n 模块定义适合从这里找。它的价值是减少 `process`、`preload`、`renderer` 之间互相偷偷依赖实现细节。

## 推荐阅读顺序

1. 先看 `packages/desktop/package.json` 和构建配置，确认这个 package 的脚本、入口、依赖和 Electron/Vite 绑定方式。
2. 再看 `packages/desktop/src/process/` 的入口文件，理解应用如何启动、窗口如何创建、IPC handler 如何注册。
3. 接着看 `packages/desktop/src/preload/`，列出渲染进程实际能调用的桌面能力边界。
4. 然后进入 `packages/desktop/src/renderer/`，先看根入口、布局和路由，再看具体页面或组件。
5. 最后回到 `packages/desktop/src/common/`，补齐共享类型、常量、i18n 配置和跨进程契约。

如果只想建立地图，不建议一开始钻进单个 UI 组件。更高效的方式是先画出三层调用链，再选择一个真实功能从界面按钮一路追到主进程 handler。

## 常见误区

第一个误区是混淆进程边界。`src/renderer` 不能直接使用 Node.js API，`src/process` 也不能依赖 DOM。看到某个功能需要系统能力时，应先找 preload 和 IPC，而不是在 React 组件里直接实现。

第二个误区是把 preload 当成业务层。`src/preload` 应该薄而稳定，主要负责暴露安全接口和转发 IPC；复杂业务应放在主进程服务或渲染进程状态逻辑中。

第三个误区是硬编码用户可见文案。项目要求所有用户可见文本走 i18n，相关配置从 `packages/desktop/src/common/config/i18n-config.json` 及语言资源体系展开。

第四个误区是绕开 UI 规范。桌面端交互组件应使用 `@arco-design/web-react`，图标使用 `@icon-park/react`，不要随手写原生 `<button>`、`<input>`、`<select>` 这类交互元素。

第五个误区是把样式散落到全局。全局样式只应在 `packages/desktop/src/renderer/styles/`，复杂组件样式用 CSS Modules，颜色应使用语义 token 或 CSS variables，而不是硬编码颜色值。

第六个误区是只看 `renderer` 就判断功能全貌。桌面功能往往跨越 `renderer`、`preload`、`process` 三层；只看界面层容易漏掉权限、IPC 协议、错误处理和主进程生命周期。
