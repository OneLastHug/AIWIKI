# 子系统：packages/desktop/src/renderer/utils

## 解决什么问题

`packages/desktop/src/renderer/utils` 按命名和项目约束看，应当是 Desktop Renderer 进程的通用工具层：它不直接承载页面、组件或业务状态，而是为 `packages/desktop/src/renderer` 下的视图、hooks、stores、services 等代码提供可复用的纯函数或轻量适配能力。根据当前片段推断，它的核心价值在于把“在浏览器上下文中可安全执行的横切逻辑”集中起来，例如格式化、数据转换、DOM/浏览器能力判断、UI 辅助计算、错误展示前的规范化、IPC 返回值的前端侧整理等。

需要注意的是，本次读取到的工作区片段中，目标目录以及其父级 `packages/desktop/src/renderer` 未能直接命中，因此以下说明以仓库级约束、AGENTS.md 中的架构规则和该路径命名为依据，而不是对具体叶子文件逐个归纳。若后续仓库检出恢复完整，应优先用实际源码修正本文中的推断部分。

## 相关目录和文件

与该目录关系最紧密的是 `packages/desktop/src/renderer`。这是 Electron Renderer 侧代码区域，按照项目规则可以使用 DOM、React、Arco Design 组件和浏览器 API，但不能直接使用 Node.js API。`utils` 若存在，应服务于这一边界内的代码。

`packages/desktop/src/preload` 是 Renderer 访问主进程能力的桥。`utils` 不应绕过 preload 直接调用 `fs`、`path`、`child_process` 等 Node 能力；如果工具函数需要文件、系统或窗口能力，应通过 preload 暴露的 IPC API 获取结果，再在 renderer 工具层做展示侧转换。

`packages/desktop/src/process` 是 Main 进程代码区域。它与 `utils` 的关系通常是“能力提供方”和“结果消费方”的关系：Main 进程负责系统能力，Renderer `utils` 只处理 UI 可用的数据形态。

`packages/desktop/src/common/config/i18n-config.json`、`locales/` 与该目录也可能相关。项目要求所有用户可见文本使用 i18n key，因此 `utils` 中如果产生错误文案、状态文案或提示文本，不应硬编码中文或英文，而应返回错误码、状态枚举或由调用方传入翻译函数。

## 核心对象

根据当前片段推断，`utils` 目录里的核心对象一般不是类，而是一组无状态函数、常量映射和类型辅助：

第一类是格式化函数，例如把时间、大小、计数、路径片段、模型状态或任务状态转换为 UI 展示所需的结构。它们应该保持纯函数特征，输入明确、输出稳定，不读取全局状态。

第二类是环境判断和浏览器侧能力封装，例如判断平台、主题、滚动容器、剪贴板能力、文件拖拽数据等。这类工具必须严格停留在 Renderer 可用 API 范围内。

第三类是数据归一化函数，用于把 preload/IPC、API 或 store 中拿到的数据整理成组件更容易消费的形状。它们适合处理空值、默认值、排序、分组和枚举映射，但不适合发起副作用请求。

第四类是 UI 辅助计算，例如 Arco 表格列配置前的数据准备、菜单项禁用条件、颜色 token 映射、布局尺寸计算等。由于项目偏好 UnoCSS 和语义 token，这类工具不应产出硬编码颜色。

## 运行流程

典型运行链路可以理解为：页面或组件接收用户操作，调用 hook、store 或 service；这些上层模块在需要通用处理时调用 `renderer/utils`；如果涉及系统能力，请求会先经过 `packages/desktop/src/preload` 提供的桥接 API，再到 `packages/desktop/src/process`；Main 返回结构化结果后，Renderer 侧再用 `utils` 做展示前处理，最后交给 Arco 组件、页面状态或通知系统渲染。

在纯前端场景中，流程更短：组件输入数据后调用 `utils` 完成格式化、过滤、排序或状态判断，然后渲染 UI。这里的重点是 `utils` 不应该反向依赖具体页面，也不应该知道某个路由、弹窗或组件的生命周期细节。它只提供可复用算法，生命周期和副作用由调用方控制。

## 上下游依赖

上游调用方通常包括 `packages/desktop/src/renderer` 下的页面、组件、hooks、stores 和业务 service。它们依赖 `utils` 来减少重复逻辑，并让同一类展示规则保持一致。

下游依赖应尽量轻。合理依赖包括 TypeScript 标准能力、浏览器 API、项目内公共类型、语义常量，以及少量稳定的第三方纯函数库。若引入 `@arco-design/web-react`、React 组件、store 实例或 IPC 客户端，就要谨慎判断是否已经越过“工具层”边界。一般来说，`utils` 可以处理传入的数据，但不应主动管理组件状态、弹出 UI、发请求或注册长期监听。

与 `packages/desktop/src/common` 的关系也需要清晰：通用且跨进程可复用的类型或常量更适合放到 common；只服务 Renderer 展示逻辑的函数才适合留在 `renderer/utils`。

## 修改时最容易踩的坑

最常见的问题是把 Renderer 工具函数写成“万能工具箱”，导致它同时包含 DOM 操作、IPC 调用、业务状态修改和 UI 提示。这会让依赖方向变乱，也让测试困难。修改时应先判断新函数是否真的是通用逻辑，还是只属于某个组件或业务模块。

第二个坑是误用 Node.js API。项目明确要求 Renderer 不能直接使用 Node.js 能力；即使本地开发环境能跑，也可能破坏 Electron 安全边界或打包行为。涉及系统能力时应走 `preload`。

第三个坑是硬编码用户可见文本和颜色。错误消息、按钮提示、状态标签等要通过 i18n 体系；颜色应使用 UnoCSS 语义 token 或 CSS 变量。

第四个坑是让工具函数吞掉错误。工具层可以规范化错误，但不应无声失败；调用方需要有机会决定是否重试、提示用户或上报。

第五个坑是把具体页面结构写进通用函数。例如某个表格的列、某个弹窗的标题、某个路由的特定状态，如果没有被多个模块稳定复用，就不应放进 `utils`。

## 推荐阅读顺序

建议先读 `docs/architecture/overview.md`，理解 Main、Preload、Renderer 的边界。然后读 `AGENTS.md` 和 `CONTRIBUTING.md`，确认 TypeScript、CSS、i18n、组件库和目录规模约束。接着阅读 `packages/desktop/src/preload`，理解 Renderer 能访问哪些系统能力。再回到 `packages/desktop/src/renderer`，从使用 `utils` 的页面、hooks 或 stores 入手，看哪些逻辑被抽到了工具层。最后再阅读 `packages/desktop/src/renderer/utils` 内的具体函数，按“纯格式化、环境判断、数据归一化、UI 辅助计算”的顺序建立心智模型。
