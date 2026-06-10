# 子系统：packages/desktop/src/renderer/pages/guid/hooks

## 解决什么问题

`packages/desktop/src/renderer/pages/guid/hooks` 按命名应属于桌面端 Renderer 进程中 `guid` 页面下的 Hooks 子系统，用来承载该页面的状态组织、事件封装、副作用管理和跨组件复用逻辑。根据当前片段推断，这一层的目标不是渲染 UI，而是把页面组件中容易膨胀的逻辑拆出，例如读取页面数据、维护表单或步骤状态、订阅 IPC 返回、协调异步请求、处理页面生命周期等。

但需要明确：在当前可读取的工作树中，目标路径 `packages/desktop/src/renderer/pages/guid/hooks` 以及其上游目录 `packages/desktop/src/renderer/pages/guid`、`packages/desktop/src/renderer/pages`、`packages/desktop/src/renderer` 均未能定位到。因此以下文档只能基于项目约定、路径命名和 `AGENTS.md` 中的架构说明进行学习性说明，不能替代对实际源码的逐文件确认。

## 相关目录和文件

理论上，这个目录应位于 Renderer 进程页面层：

`packages/desktop/src/renderer/pages/guid/hooks`

其邻近目录通常包括：

`packages/desktop/src/renderer/pages/guid`：`guid` 页面入口、页面级组件、页面样式和局部状态容器。

`packages/desktop/src/renderer/pages/guid/components`：页面拆分出的展示组件或交互组件，可能消费 hooks 暴露的状态和回调。

`packages/desktop/src/renderer/pages/guid/constants.ts`、`packages/desktop/src/renderer/pages/guid/types.ts`：页面内常量与类型定义，hooks 应优先复用这些类型，避免在 hook 内重复定义结构。

`packages/desktop/src/renderer/styles`：全局样式和 Arco 覆盖样式。hooks 不应直接处理样式，但它们返回的状态可能驱动组件 class 或 Arco 组件属性。

`packages/desktop/src/preload`：Renderer 与 Main 之间的 IPC 桥。若 hooks 需要访问本地能力，应通过 preload 暴露的安全 API，而不是直接使用 Node.js API。

## 核心对象

这个子系统的核心对象一般是以 `use` 开头的自定义 Hook，例如 `useGuidState`、`useGuidActions`、`useGuidData`、`useGuidForm` 这类命名。它们的价值在于把页面逻辑按职责拆开：

状态类 Hook 负责维护当前页面选择、步骤、加载状态、错误状态等。

数据类 Hook 负责请求、缓存、刷新和转换页面需要的数据。

动作类 Hook 负责封装用户操作，例如创建、保存、复制、删除、跳转或提交。

桥接类 Hook 负责和 preload 暴露的 IPC API 交互，并把底层接口转成 Renderer 组件更容易消费的 `loading`、`data`、`error`、`refresh` 形式。

根据项目约定，TypeScript 开启 strict mode，因此这些 Hook 的返回值应有明确类型，不应使用 `any`。如果存在用户可见文案，例如错误提示、按钮提示或空状态说明，也不应硬编码在 hook 或组件里，而应走 i18n key。

## 运行流程

典型运行流程是：`guid` 页面组件挂载后调用 hooks，hooks 初始化本地状态，并在 `useEffect` 中触发必要的数据加载或订阅。数据来源可能是 Renderer 内部 store、业务服务封装，或通过 `packages/desktop/src/preload` 暴露的 IPC API 间接访问 Main 进程能力。

用户在页面上操作 Arco 组件后，组件调用 hook 返回的处理函数。hook 对输入进行校验、组装参数、调用下游服务，并更新页面状态。完成后，hook 将成功结果、异常信息或刷新动作反馈给页面组件。页面组件只负责展示和交互编排，不应把异步流程、IPC 细节和复杂状态转换堆在 JSX 中。

如果该页面存在多步骤引导、GUID 生成、标识管理或配置向导等语义，那么 hooks 很可能负责把“当前步骤、可否继续、提交中、结果展示、重试”等流程状态集中起来。这里属于根据路径名 `guid` 的当前片段推断，实际含义仍需以源码为准。

## 上下游依赖

上游调用方主要是 `packages/desktop/src/renderer/pages/guid` 下的页面入口和局部组件。它们通过 hooks 获取状态、派发动作、读取派生数据。

平级依赖通常是同页面目录中的 `types.ts`、`constants.ts`、`utils` 或 `components`。hooks 应避免反向依赖展示组件，避免形成页面逻辑和 UI 的循环耦合。

下游依赖可能包括 Renderer 公共 hooks、状态管理模块、i18n 工具、Arco 消息组件封装，以及 preload 暴露的安全桥接 API。按照项目架构，Renderer 禁止直接使用 Node.js API；任何文件系统、系统信息或主进程能力都应通过 `packages/desktop/src/preload` 和 `packages/desktop/src/process` 的 IPC 合约完成。

## 修改时最容易踩的坑

第一，目标目录当前不可见，修改前必须先确认实际分支或仓库快照是否包含 `packages/desktop/src/renderer/pages/guid/hooks`。如果路径是历史路径或拼写错误，直接按该路径新增文件可能会制造错误架构。

第二，hooks 虽然不直接渲染 UI，但它们可能间接包含用户可见文案。项目要求所有用户可见文本使用 i18n key，不能在错误信息、提示信息或默认标题里硬编码中文或英文。

第三，Renderer 进程不能直接调用 Node.js API。若 hook 里需要访问本地资源，应先检查 preload 是否已有桥接方法，必要时再扩展 IPC 合约。

第四，Hook 返回值要稳定。把对象、数组、回调每次渲染都重新创建，容易造成子组件重复渲染；需要时应使用 `useMemo`、`useCallback`，但也要避免无意义包裹。

第五，依赖数组要准确。异步加载、订阅和清理逻辑通常是 hook 中最容易出错的地方，遗漏依赖会产生陈旧闭包，过度依赖会导致重复请求。

第六，目录规模需要受控。项目规定单个目录直接子项不超过 10 个，若 hooks 增多，应按业务职责继续拆分，而不是把所有 hook 平铺在同一层。

## 推荐阅读顺序

1. 先确认 `packages/desktop/src/renderer/pages/guid` 是否存在，并阅读页面入口文件，理解页面承担的业务目标。
2. 再阅读 `packages/desktop/src/renderer/pages/guid/types.ts` 和 `packages/desktop/src/renderer/pages/guid/constants.ts`，掌握 hooks 操作的数据结构。
3. 然后阅读 `packages/desktop/src/renderer/pages/guid/hooks` 中被页面入口直接调用的 hook，优先看导出面和返回值。
4. 接着阅读调用 preload、store 或服务层的 hook，梳理数据来源和副作用边界。
5. 最后回到 `packages/desktop/src/renderer/pages/guid/components`，观察组件如何消费这些 hooks，从而判断逻辑拆分是否清晰、状态是否重复、交互流程是否完整。
