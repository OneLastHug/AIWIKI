# 文件：next/src/stores/configStore.ts

## 一句话定位

`next/src/stores/configStore.ts` 是前端全局配置状态的 Zustand store，主要负责持久化 UI 布局开关和当前组织角色信息，为 dashboard 布局、任务侧边栏等组件提供跨组件共享状态。

## 它暴露/定义了什么

该文件最终暴露 `useConfigStore`。它是一个经过 `createSelectors` 包装的 Zustand hook，既可以像普通 store 一样整体读取，也支持 `useConfigStore.use.xxx()` 这类自动 selector 访问方式。

内部定义了两组 slice：

`LayoutSlice` 管理 `layout`，目前包含 `showRightSidebar` 和 `showLogSidebar` 两个布尔值，以及 `setLayout(layout: Partial<Layout>)`。

`AuthSlice` 管理 `organization`，类型为 `OrganizationRole | undefined`，并提供 `setOrganization(orgRole)`。`OrganizationRole` 包含 `id`、`name`、`role`，表示当前组织及用户在组织内的角色。

store 使用 `persist` 中间件持久化到浏览器 `localStorage`，存储 key 为 `reworkd-config-2`，版本为 `1`。

## 谁调用它

明确调用点主要有两个：

`next/src/layout/dashboard.tsx` 导入 `useConfigStore`，读取 `layout` 和 `setLayout`，用于控制右侧 sidebar 是否显示，并根据 `layout.showRightSidebar` 给主内容区域添加右侧 padding。

`next/src/components/drawer/TaskSidebar.tsx` 也导入 `useConfigStore`，读取 `layout.showRightSidebar` 作为任务侧边栏的显示状态，并通过 `setLayout({ showRightSidebar: show })` 打开或关闭它。

根据当前片段推断，`organization` 目前在已检索到的 `next/src` 范围内没有直接使用点；它可能是为组织权限、团队上下文或历史功能预留，也可能由未覆盖路径、运行时逻辑或未来功能使用。

## 它调用谁

该文件直接依赖 `zustand` 的 `create` 创建 store，依赖 `zustand/middleware` 的 `persist` 和 `createJSONStorage` 做本地持久化。

它还调用本地 helper `createSelectors`，该 helper 位于 `next/src/stores/helpers.ts`，作用是遍历 store 当前 state 的 key，自动生成 `store.use.<key>()` selector。这样组件可以按字段订阅，减少不必要的渲染。

持久化层调用浏览器 `localStorage`。这意味着该 store 是面向客户端环境的状态；如果在服务端渲染阶段直接触发相关逻辑，需要注意 `localStorage` 不存在的问题。不过当前写法通过 `createJSONStorage(() => localStorage)` 交给 Zustand middleware 处理，通常在客户端组件使用场景下成立。

## 核心流程

初始化时，`create<LayoutSlice & AuthSlice>()` 创建一个合并 store。传给 `persist` 的 state creator 会展开 `createLayoutSlice(...a)` 和 `createAuthSlice(...a)`，把两个 slice 的初始状态和 action 合并成一个对象。

`layout` 初始状态为两个右侧相关面板都关闭：`showRightSidebar: false`、`showLogSidebar: false`。`organization` 初始为 `undefined`。

组件调用 `setLayout` 时，函数先检查传入的 partial layout。如果要打开 `showLogSidebar`，会把 `showRightSidebar` 设为 `false`；如果要打开 `showRightSidebar`，会把 `showLogSidebar` 设为 `false`。之后它将传入值和旧的 `prev.layout` 合并，写回 store。

这段逻辑的核心约束是：右侧任务栏和日志栏不能同时打开。dashboard 现在明确消费的是 `showRightSidebar`；`showLogSidebar` 的调用点在当前检索范围内没有出现，根据当前片段推断，它可能对应过去或计划中的日志侧栏。

状态更新后，`persist` 会把 store 内容写入 `localStorage` 的 `reworkd-config-2`。页面刷新后，Zustand 会尝试从该 key 恢复状态，因此用户的侧栏开关和组织信息可能跨刷新保留。

## 关键函数的高层作用

`createLayoutSlice` 定义布局配置的初始值和更新规则。它不是简单 setter，而是带有互斥规则的布局状态入口：打开日志侧栏会关闭右侧任务栏，打开右侧任务栏会关闭日志侧栏。

`setLayout` 是最关键的 action。它接收 `Partial<Layout>`，允许调用方只传要改的字段。它会先调整互斥字段，再和原状态浅合并。这个设计让调用方写法很轻，但也意味着所有布局字段都共享同一套互斥规则。

`createAuthSlice` 只负责保存和替换 `organization`。它没有权限校验、异步加载或 token 处理逻辑，只是一个前端状态容器。

`setOrganization` 是组织上下文 setter。它可以接受具体 `OrganizationRole`，也可以传 `undefined` 清空当前组织。

`useConfigStore` 是文件对外的唯一入口。它把 layout slice、auth slice、持久化和自动 selector 组合起来，供 React 组件读取和更新配置状态。

## 修改风险

最大风险在 `setLayout` 的互斥逻辑。若新增右侧面板字段，或改变 `showRightSidebar`、`showLogSidebar` 的含义，需要同步审视这里的互斥规则，否则可能出现多个侧栏同时占位、主内容 padding 不正确、按钮状态和实际显示不一致等 UI 问题。

第二个风险是持久化 schema。当前 key 是 `reworkd-config-2`，`version` 为 `1`，但没有定义 migrate。修改 `layout` 或 `organization` 结构后，旧浏览器中的 `localStorage` 仍可能保留历史数据。若字段改名、类型改变或删除，应该考虑 bump 存储 key、增加迁移逻辑，或在读取时兼容旧值。

第三个风险是 `localStorage` 客户端依赖。这个 store 适合在浏览器组件中使用，不应随意搬到服务端代码、API route 或 SSR-only 逻辑里。若未来 Next.js 迁移到更多 server component，需要避免在服务端直接消费它。

第四个风险是 `organization` 的语义边界。它看起来像认证或租户上下文，但这里只是本地持久化状态，并不代表后端已授权。任何安全判断都不能依赖这个 store；它最多用于 UI 展示、默认选择或请求前的上下文辅助。
