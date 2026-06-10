# 目录：packages

## 它负责什么

`packages` 是当前仓库的应用包聚合层，用来承载实际可运行、可构建的产品代码。根据当前片段能确认，仓库的核心桌面端应用位于 `packages/desktop`，并且项目约束里多次把 `packages/desktop/src/process/`、`packages/desktop/src/preload/`、`packages/desktop/src/renderer/` 作为主架构边界来描述。因此可以把 `packages` 理解为 monorepo 中“产品包”的入口目录，而不是通用脚本、文档或基础设施目录。

从架构上看，`packages` 下面的重点不是单个工具函数，而是 Electron 桌面应用的分层组织：主进程负责系统能力和后端式调度，预加载层负责安全暴露 IPC 能力，渲染进程负责用户界面。项目规则明确要求 Main 与 Renderer 不混用 API：`packages/desktop/src/process/` 不能使用 DOM API，`packages/desktop/src/renderer/` 不能使用 Node.js API，跨进程交互必须经过 `packages/desktop/src/preload/`。这说明 `packages` 是理解整个应用运行方式的第一层入口。

## 直接子目录地图

根据当前片段确认到的直接子目录主要是：

`packages/desktop`：桌面端应用包。它是当前 `packages` 下最关键的业务承载目录，包含 Electron 桌面应用的主进程、预加载层、渲染进程、公共配置和样式体系。项目文档中的测试、i18n、Arco 主题覆盖、进程边界说明，几乎都围绕这个包展开。

在 `packages/desktop` 内部，关键结构根据当前片段可概括为：

`packages/desktop/src/process`：Electron Main 进程代码所在位置。它适合放窗口生命周期、系统资源访问、文件或进程能力、主进程服务编排等逻辑。这里不能直接依赖浏览器 DOM。

`packages/desktop/src/preload`：预加载桥接层。它位于 Main 与 Renderer 之间，负责把经过约束的 IPC 能力暴露给前端界面。项目规则强调跨进程通信必须经过这里，因此它是安全边界和接口契约的核心位置。

`packages/desktop/src/renderer`：渲染进程代码所在位置，也就是用户界面和前端交互的主要区域。这里使用 `@arco-design/web-react` 作为组件库，图标使用 `@icon-park/react`，样式优先采用 UnoCSS 工具类，复杂样式使用 CSS Modules。这里不能直接使用 Node.js API。

`packages/desktop/src/common`：根据当前片段推断，这是跨层共享配置和公共定义的区域，证据是 i18n 模块配置位于 `packages/desktop/src/common/config/i18n-config.json`。它更适合放不绑定具体进程能力的配置、类型、常量或协议定义。

`packages/desktop/src/renderer/styles`：渲染端全局样式入口。项目规则指定全局样式只能放在这里，Arco 主题覆盖集中在 `packages/desktop/src/renderer/styles/arco-override.css`。

## 关键入口

`packages/desktop` 是阅读 `packages` 的首要入口。它应当包含该桌面应用的包配置、构建配置和源代码根目录。根据当前片段推断，常见入口会包括 `packages/desktop/package.json`、构建配置文件以及 `packages/desktop/src` 下的进程分层入口；具体文件名需要结合仓库实际文件确认。

主进程入口应在 `packages/desktop/src/process/` 下寻找。阅读时重点看应用启动、窗口创建、IPC 注册、系统能力封装、应用生命周期处理等位置。这些代码通常决定桌面应用如何启动，以及前端界面能调用哪些本地能力。

预加载入口应在 `packages/desktop/src/preload/` 下寻找。这里的关键不是页面渲染，而是接口暴露方式：哪些 API 被挂载给 Renderer、参数如何传递、返回值如何约束、是否经过 IPC 通道。理解这里之后，才能判断 Renderer 中调用的本地能力实际来自哪里。

渲染入口应在 `packages/desktop/src/renderer/` 下寻找。这里通常包含 React 应用入口、路由或页面组合、状态管理、组件树、样式入口和 i18n 初始化。由于项目要求所有用户可见文本都使用 i18n key，阅读 UI 时需要同步关注 locale 配置和翻译资源，而不能只看组件文本。

公共配置入口中，`packages/desktop/src/common/config/i18n-config.json` 是理解多语言模块划分的重要文件。凡是修改渲染端文案、locale 或 i18n 配置，都需要配合运行 `bun run i18n:types` 和 `node scripts/check-i18n.js` 进行校验。

## 主流程位置

应用启动主流程主要在 `packages/desktop/src/process/`。这里负责 Electron 主进程生命周期，通常包括应用初始化、窗口创建、菜单或托盘、IPC handler 注册、系统资源访问等。要理解“应用如何被拉起”，应从这里开始。

前后端能力调用流程横跨 `packages/desktop/src/renderer/`、`packages/desktop/src/preload/`、`packages/desktop/src/process/`。典型链路是：Renderer 中的界面或业务逻辑发起调用，Preload 暴露受控 API 并转发到 IPC，Process 接收请求后执行主进程能力，再把结果返回给 Renderer。项目明确禁止 Renderer 直接访问 Node.js API，这条链路是理解功能实现的关键。

界面渲染主流程在 `packages/desktop/src/renderer/`。这里关注页面组织、组件组合、状态流转、表单和交互。由于 UI 组件必须使用 `@arco-design/web-react`，不能直接写原生交互元素如 `<button>`、`<input>`、`<select>`，所以阅读时要注意 Arco 组件与项目封装组件之间的关系。

样式主流程在 UnoCSS、CSS Modules 和渲染端全局样式之间展开。简单布局和视觉状态优先看组件里的 UnoCSS class；复杂局部样式看同目录 CSS Module；全局样式和 Arco 覆盖看 `packages/desktop/src/renderer/styles/`，特别是 `arco-override.css`。

多语言主流程围绕 `packages/desktop/src/common/config/i18n-config.json` 和 locale 资源。任何用户可见文本都不应直接写死在组件中，而应通过 i18n key 引用。阅读某个界面文案时，需要沿着组件中的 key 回到 locale 文件和 i18n 配置查看模块归属。

## 推荐阅读顺序

第一步，先读 `packages/desktop` 的包级配置和构建配置，确认它如何被根目录脚本调用、如何启动开发环境、如何参与测试和类型检查。这里能建立“这个包在仓库中怎么运行”的基本认识。

第二步，阅读 `packages/desktop/src/process/`，先抓住应用启动、窗口管理和 IPC 注册。不要一开始陷入每个服务细节，先画出主进程能提供哪些能力。

第三步，阅读 `packages/desktop/src/preload/`，把主进程能力与渲染端可见 API 对齐。这里是理解跨进程边界的关键，应重点看 API 命名、参数类型和通道设计。

第四步，阅读 `packages/desktop/src/renderer/` 的入口、路由或页面组织，再进入具体业务页面和组件。读 UI 时同步关注 Arco 组件使用、UnoCSS class、CSS Modules 和 i18n key。

第五步，补读 `packages/desktop/src/common/`，尤其是 `packages/desktop/src/common/config/i18n-config.json`。这一层可以帮助你理解跨进程共享的配置、类型和文案模块划分。

第六步，需要修改或验证时再看根目录质量命令：`bun run lint:fix`、`bun run format`、`bunx tsc --noEmit`、`bun run test`。如果变更涉及 Renderer、locales 或 i18n 配置，还要关注 `bun run i18n:types` 和 `node scripts/check-i18n.js`。

## 常见误区

不要把 `packages` 当成普通源码杂物目录。它承载的是产品包边界，尤其是 `packages/desktop` 这个 Electron 应用包；脚本、文档、CI 配置和应用源码职责不同，阅读时要分清层级。

不要绕过 `packages/desktop/src/preload/` 做跨进程调用。项目明确要求 Main 与 Renderer 通过 IPC bridge 交互，Renderer 不能直接使用 Node.js API，Main 也不能写 DOM 逻辑。把这些边界打破，会让功能短期可用但长期难以维护和测试。

不要在 Renderer 里随手写原生交互 HTML。项目约定交互组件使用 `@arco-design/web-react`，图标使用 `@icon-park/react`。如果看到按钮、输入框、选择器等交互控件，应优先寻找 Arco 组件或项目已有封装。

不要硬编码用户可见文本。`packages/desktop/src/renderer/` 中出现的界面文案应通过 i18n key 管理，模块定义则要对齐 `packages/desktop/src/common/config/i18n-config.json`。修改文案后如果不更新类型和检查，很容易产生缺失翻译或 key 不一致问题。

不要把样式随意放到全局文件。全局样式只应在 `packages/desktop/src/renderer/styles/`，组件复杂样式应使用 CSS Modules，颜色也应使用 UnoCSS 语义 token 或 CSS 变量，而不是硬编码颜色值。

不要逐叶子文件理解大目录。`packages` 的学习重点是先把桌面应用的进程边界、入口链路、UI 层、i18n 和样式体系连起来；等主流程清楚后，再进入具体功能目录，阅读效率会高很多。
