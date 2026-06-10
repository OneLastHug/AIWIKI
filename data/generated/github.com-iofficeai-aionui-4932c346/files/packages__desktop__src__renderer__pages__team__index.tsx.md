# 文件：`packages/desktop/src/renderer/pages/team/index.tsx`
## 一句话定位
这是团队详情页的“数据入口 + 容器层”组件：它从路由参数拿到团队 `id`，通过 `ipcBridge` 拉取团队数据，再把结果交给真正的展示页 `TeamPage`。

## 它暴露/定义了什么
这个文件默认导出一个 React 组件 `TeamIndex`。它本身不负责复杂 UI，而是负责把“当前路由对应的团队对象”解析出来，并处理加载态、空态和页面切换。根据当前片段推断，它是 `team` 路由下的入口页，外部一般直接渲染这个默认导出。

## 谁调用它
通常是前端路由系统调用它，`react-router-dom` 的某个路由配置会把团队详情路径映射到这个组件。由于这里使用了 `useParams<{ id: string }>()`，可以推断它依赖 URL 中的动态参数 `id`，因此上层调用方应当保证路由形如“团队详情/某个 id”的页面入口。它本身没有被其他业务组件显式调用的痕迹。

## 它调用谁
它调用了 `useParams` 读取路由参数，调用 `useSWR` 做数据请求与缓存管理，调用 `ipcBridge.team.get.invoke({ id })` 从主进程获取团队详情，调用 `Spin` 渲染加载态，最后把 `team` 传给 `TeamPage` 作为真实内容页。这里的核心依赖链是 `react-router-dom`、`swr`、`ipcBridge` 和本地的 `./TeamPage`。

## 核心流程
组件先从路由中取出 `id`。如果 `id` 不存在，`useSWR` 不发请求；如果存在，就以 `team/${id}` 作为缓存 key，异步调用 `ipcBridge.team.get.invoke` 获取数据。请求未完成时显示 `Spin`；如果请求结束后没有拿到 `team`，直接返回 `null`，避免渲染错误内容；当 `team` 可用时，渲染 `TeamPage`，并用 `key={team.id}` 强制在团队切换时重建子树，减少旧状态残留。

## 关键函数的高层作用
`TeamIndex` 的作用不是拼 UI，而是把路由参数、异步加载和页面展示串起来。`useSWR` 负责缓存、去重和加载状态管理，属于这页最关键的状态编排点。`ipcBridge.team.get.invoke` 是真正的数据来源，说明团队详情不直接走浏览器本地数据，而是通过预加载层/IPC 去主进程拿。`TeamPage` 才是承载业务内容的页面主体，这个文件只是它的外壳。

## 修改风险
这个文件改动看似小，但很容易影响页面进入链路。最主要的风险是 `id` 为空或路由参数变化时，数据请求和缓存 key 不一致，导致页面空白或显示旧数据。其次是 `key={team.id}` 会强制重挂载 `TeamPage`，如果子页内部有未保存状态，切换团队时会被清掉。再往下还有 IPC 合约风险：`ipcBridge.team.get.invoke` 的入参或返回结构一旦变动，这里会最先出问题。最后，`if (!team) return null` 会把异常、空数据和未找到都折叠成“什么都不显示”，排障时要特别注意。
