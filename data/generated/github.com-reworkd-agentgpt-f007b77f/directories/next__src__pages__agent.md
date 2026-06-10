# 目录：next/src/pages/agent

## 它负责什么

`next/src/pages/agent` 是 Next.js Pages Router 下的一个页面目录，用来承载 `/agent` 路由。它不是 Agent 运行引擎目录，也不是 API 目录，而是一个“已保存 Agent 详情页 / 历史会话查看页”的页面入口。

从当前目录内容看，这个目录只有 `index.tsx` 一个页面文件，没有下级业务模块。页面通过 URL query 中的 `id` 参数读取某个已保存 Agent 记录，然后把该 Agent 的历史 `tasks` 当作聊天消息渲染到 `ChatWindow` 中。页面还提供三个用户动作：返回首页、删除当前 Agent、复制分享链接。

需要注意的是，真正的 Agent 创建、执行、暂停、停止、任务分析、任务执行等主流程并不在这个目录，而主要分散在 `next/src/pages/index.tsx`、`next/src/services/agent`、`next/src/stores`、`next/src/server/api/routers/agentRouter.ts` 等位置。`next/src/pages/agent` 更像是运行结果的回看入口。

## 直接子目录地图

当前片段显示 `next/src/pages/agent` 没有直接子目录，目录结构非常扁平：

`next/src/pages/agent/index.tsx`：`/agent` 页面入口。负责读取 `?id=...`，调用 `api.agent.findById.useQuery` 获取 Agent 及其任务列表，渲染聊天窗口，并提供 Back、Delete、Share 三个按钮。

因此，这个目录没有“子模块地图”意义上的分层。学习时不要在这里寻找 Agent 编排逻辑、模型调用逻辑或任务队列逻辑，这些都在邻近目录中。

## 关键入口

关键入口只有一个：`next/src/pages/agent/index.tsx`。

它导出 `AgentPage: NextPage`，这就是 `/agent` 路由对应的 React 页面组件。页面顶部引入了几个关键依赖：

`useRouter`：从路由中读取 `router.query.id`，并在删除成功后跳回 `/`。

`api`：来自 `next/src/utils/api`，这里使用 `api.agent.findById.useQuery` 和 `api.agent.deleteById.useMutation`。根据当前片段推断，这里的 `api.agent` 对应后端 tRPC router 中的 `agentRouter`。

`DashboardLayout`：页面外层布局，说明这个详情页属于主应用 dashboard 框架的一部分，而不是独立公开落地页。

`ChatWindow`、`ChatMessage`、`FadeIn`：负责把数据库里的任务消息展示为聊天式 UI。`messages` 的来源是 `getAgent.data.tasks as Message[]`，也就是说页面并不重新执行 Agent，只复用已保存的任务数据。

`Toast`：分享链接复制成功后显示提示，提示文本通过 `next-i18next` 的 `useTranslation` 获取。

此外，文件末尾导出 `getStaticProps`，用于加载国际化资源。它根据当前 `locale` 与 `languages` 列表选择合法语言，然后调用 `serverSideTranslations` 注入翻译内容。这里没有 `getStaticPaths`，也没有服务端根据 Agent ID 预渲染详情内容；Agent 数据是在客户端通过 tRPC query 拉取的。

## 主流程位置

这个目录内部的主流程可以概括为“读 ID、查 Agent、渲染消息、执行页面操作”。

第一步，页面通过 `useRouter()` 获取当前路由对象，并从 `router.query.id` 中提取 `agentId`。代码只接受字符串类型的 `id`，否则使用空字符串。

第二步，页面调用 `api.agent.findById.useQuery(agentId, { enabled: router.isReady })`。`enabled: router.isReady` 的作用是等待 Next.js router 准备好以后再发起查询，避免 query 参数尚未注入时提前请求。

第三步，页面把查询结果转换成消息数组：如果 `getAgent.data` 存在，就取 `getAgent.data.tasks as Message[]`；否则使用空数组。随后将 `messages` 传给 `ChatWindow`，并逐条渲染为 `ChatMessage`。

第四步，页面底部提供操作按钮。Back 按钮调用 `router.push("/")` 返回首页。Delete 按钮调用 `deleteAgent.mutate(agentId)`，对应后端 `agentRouter.deleteById`，删除成功后跳回 `/`。Share 按钮调用 `window.navigator.clipboard.writeText(shareLink())`，复制当前页面分享地址，并展示 `Toast`。

后端数据来源可以从 `next/src/server/api/routers/agentRouter.ts` 理解。`findById` 是 `publicProcedure`，按 `id` 和 `deleteDate: null` 查找 Agent，并 `include` 其 `tasks`，任务按 `createDate: "asc"` 排序。`deleteById` 是 `protectedProcedure`，只允许当前登录用户把自己的 Agent 标记为删除，即写入 `deleteDate`。

与此相对，Agent 的实际运行主流程不在 `/agent` 页面中，而在 `next/src/pages/index.tsx`。首页中 `handleNewAgent` 会创建 `DefaultAgentRunModel`、`MessageService`、`AgentApi` 和 `AutonomousAgent`，然后调用 `newAgent.run()`。`AutonomousAgent` 的具体工作流位于 `next/src/services/agent/autonomous-agent.ts` 及 `next/src/services/agent/agent-work`。所以 `/agent` 是“查看保存结果”，`/` 是“启动和运行 Agent”。

## 推荐阅读顺序

建议先读 `next/src/pages/agent/index.tsx`，建立这个目录的边界感：它只处理详情展示、删除和分享，不负责 Agent 执行。

然后读 `next/src/server/api/routers/agentRouter.ts`，重点看 `findById`、`deleteById`、`create`、`save`。这样可以理解详情页的数据从哪里来，以及历史任务为什么能作为 `Message[]` 被展示出来。

接着读 `next/src/pages/index.tsx`，对比首页运行入口和 `/agent` 详情页的职责差异。首页负责根据 goal 创建 Agent、启动运行、处理登录前后的本地缓存、重置状态；详情页只读取已保存结果。

再读 `next/src/services/agent/autonomous-agent.ts` 和 `next/src/services/agent/agent-api.ts`。前者解释 Agent 如何循环执行工作单元，后者解释前端 Agent 如何调用 `/api/agent/start`、`/api/agent/create`、`/api/agent/analyze` 等接口，并通过 `useAgent` 保存 Agent。

最后读 UI 组件：`next/src/components/console/ChatWindow.tsx`、`next/src/components/console/ChatMessage.tsx`、`next/src/layout/dashboard.tsx`。这些文件帮助理解 `/agent` 页面为什么只需要把 `messages` 交给聊天窗口就能完成展示。

## 常见误区

第一个误区是把 `next/src/pages/agent` 当成 Agent 引擎目录。实际上它只是 Next.js 页面路由目录，负责 `/agent?id=...` 的展示。Agent 运行逻辑在 `next/src/services/agent`，运行入口主要在 `next/src/pages/index.tsx`。

第二个误区是以为 `/agent` 会启动或恢复一个 Agent。根据当前片段，它不会调用 `AutonomousAgent.run()`，也没有创建 `DefaultAgentRunModel`。它只是从后端读取保存过的 Agent 和任务记录，并渲染为聊天历史。

第三个误区是忽略 `findById` 的权限特征。`agentRouter.findById` 是 `publicProcedure`，只按 `id` 和未删除状态查询；而 `deleteById` 是 `protectedProcedure`，要求当前用户匹配 `userId`。这意味着分享链接的查看和删除权限不是同一套约束。根据当前片段推断，分享功能依赖这个公开查询能力。

第四个误区是认为 `getStaticProps` 会预取 Agent 数据。这里的 `getStaticProps` 只加载翻译资源，不处理 Agent ID，也不访问数据库。真正的数据请求发生在客户端 tRPC hook 中。

第五个误区是把 `tasks` 和运行时任务队列混为一谈。详情页里的 `tasks` 来自数据库中的历史记录，被强转为 `Message[]` 后用于显示；运行时任务状态则还涉及 `next/src/stores/taskStore`、`next/src/services/agent/agent-work` 等模块。两者名称相近，但所处阶段不同：一个是已保存展示数据，一个是运行过程中的工作流状态。
