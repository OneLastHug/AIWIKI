# 子系统：packages/desktop/src/renderer/components/layout

## 解决什么问题

`packages/desktop/src/renderer/components/layout` 按命名应属于桌面端 Renderer 进程的布局组件层，负责承载应用级页面骨架，例如导航区、侧栏、内容容器、标题栏、路由出口、全局状态入口和基础交互区域。它通常不是业务功能本身，而是把业务页面放入统一的视觉和交互框架中，保证不同页面在桌面端窗口内具有一致的结构、间距、滚动行为和主题表现。

需要特别说明：在当前可访问片段中，目标目录以及 `packages/desktop/src/renderer` 没有被实际命中，因此以下内容除“路径不存在/不可见”这一事实外，均为根据项目约束、目录命名和 Electron Renderer 分层规则进行的推断。依据包括项目约定中对 `packages/desktop/src/renderer/` 的职责说明、UI 库要求、i18n 要求以及组件命名规范。

## 相关目录和文件

该目录理论上位于 `packages/desktop/src/renderer/components/` 下，是 Renderer 组件体系的一部分。它与 `packages/desktop/src/renderer/` 中的页面、路由、状态管理、样式目录关系紧密：页面层会消费 layout 组件，layout 组件则会组合通用 UI 组件、读取 Renderer 状态，并提供页面容器。

邻近目录中，`packages/desktop/src/renderer/styles/` 负责全局样式和 Arco 覆盖；`packages/desktop/src/preload/` 负责向 Renderer 暴露 IPC 能力；`packages/desktop/src/process/` 属于 Main 进程，不能被 layout 直接依赖。若 layout 中出现用户可见文案，应联动 `locales/` 和 `packages/desktop/src/common/config/i18n`，而不是硬编码中文或英文字符串。

## 核心对象

根据当前片段推断，该子系统的核心对象应是若干 React 组件，而不是独立服务。常见形态包括应用外壳组件、侧边栏组件、顶部栏组件、内容区组件、窗口控制区域、导航菜单和布局状态 Hook。

这些对象的职责边界应清晰：布局组件负责“摆放”和“承载”，不应内嵌具体业务流程；导航组件可以关心当前路由和菜单高亮，但不应直接执行跨进程业务逻辑；窗口控制类组件如果需要调用系统能力，应通过 preload 暴露的 IPC API，而不是在 Renderer 中直接使用 Node.js 或 Electron Main API。

UI 实现上应优先使用 `@arco-design/web-react` 的组件，图标使用 `@icon-park/react`。交互控件不应直接写原生 `<button>`、`<input>`、`<select>` 等。

## 运行流程

典型运行流程是：应用启动后进入 Renderer 根组件，路由或入口组件挂载全局 layout；layout 初始化主题、导航和容器结构；当前页面作为 children 或 route outlet 被渲染到主内容区；用户点击导航、切换视图或触发窗口相关操作时，layout 将 UI 事件转化为路由跳转、状态更新或 IPC 调用。

如果目录中存在侧栏折叠、面板尺寸、当前 workspace、最近页面等状态，这些状态应尽量通过 Renderer 层状态管理或本地 Hook 管理。需要持久化或调用系统资源时，才通过 preload 桥接到后端能力。

## 上下游依赖

上游通常是 Renderer 应用入口、路由配置和页面模块。它们决定 layout 何时挂载、渲染哪一页、当前页面需要哪些全局区域。layout 的下游是基础组件库、图标库、样式系统、i18n、主题变量，以及可能的 IPC bridge。

架构上最重要的约束是进程隔离：`packages/desktop/src/renderer/` 不能直接依赖 `packages/desktop/src/process/` 的 Main 进程实现，也不能使用 Node.js API。跨进程通信必须经过 `packages/desktop/src/preload/`。样式方面应优先使用 UnoCSS 语义 token 或 CSS 变量，复杂布局可以使用 CSS Modules，但不应在组件内散落硬编码颜色。

## 修改时最容易踩的坑

第一，容易把 layout 写成业务聚合层。布局目录适合承载页面框架，不适合塞入具体业务请求、数据转换或模型逻辑，否则会导致每个页面都被迫加载无关依赖。

第二，容易违反 Renderer 进程边界。只要出现 `fs`、`path`、直接 Electron Main API 或 Node-only 包，就应警惕，这些能力应移动到 Main 或 preload 侧。

第三，容易遗漏 i18n。导航标题、按钮文案、空状态、tooltip 都是用户可见文本，必须使用 i18n key。

第四，容易破坏统一样式。该项目要求使用 Arco 组件、`@icon-park/react` 图标、UnoCSS 语义 token；硬编码颜色、原生交互控件和局部全局样式都会增加维护成本。

第五，目录规模需要受控。项目约定单个目录直接子项不超过 10 个，若 layout 继续膨胀，应按导航、外壳、侧栏、窗口区域等职责拆分。

## 推荐阅读顺序

建议先读 Renderer 应用入口和路由配置，确认 layout 是如何被挂载的；再读 `packages/desktop/src/renderer/components/layout` 中的顶层组件，理解页面骨架；随后查看导航、侧栏、顶部栏等子组件，区分结构职责和业务职责；接着阅读相关样式文件，确认主题 token、响应式规则和 Arco 覆盖方式；最后查看调用 preload 的位置，确认跨进程能力是否通过正确边界进入 Renderer。
