# 文件：next/src/pages/agent/index.tsx

## 一句话定位

`next/src/pages/agent/index.tsx` 是 Agent 历史详情页：它根据 URL 查询参数里的 `id` 读取一个已保存 Agent 及其任务消息，按聊天窗口形式展示，并提供返回首页、软删除、复制分享链接三个操作。

## 它暴露/定义了什么

该文件默认导出 `AgentPage`，这是一个 Next.js Pages Router 页面组件，对应路由 `/agent`。页面本身不负责运行 Agent，也不负责生成新任务，只负责展示数据库中已有 Agent 的 `tasks`。

它还导出 `getStaticProps`，用于在构建/静态生成阶段注入 `next-i18next` 翻译资源。这里没有 `getStaticPaths`，因为页面不是 `/agent/[id]` 这种动态路径，而是通过 `/agent?id=...` 的 query string 读取目标 Agent。

## 谁调用它

直接调用方是 Next.js 路由系统：用户访问 `/agent?id=<agentId>` 时渲染该页面。

仓库内最明确的入口在 `next/src/components/drawer/LeftSidebar.tsx`：侧边栏通过 `api.agent.getAll.useQuery` 拉取当前用户的 Agent 列表，然后对每个条目执行 `router.push(`/agent?id=${agent.id}`)`。因此，这个页面主要服务于“从侧边栏点击历史 Agent”这一流程。

复制出来的分享链接也会指向同一个页面。根据当前片段推断，分享访问依赖 `agentRouter.findById` 是 `publicProcedure`，也就是说读取详情本身不要求登录；但删除仍然是受保护操作。

## 它调用谁

页面主要调用四类依赖。

第一类是 Next 和 i18n：`useRouter` 读取 `router.query.id`、导航回首页；`useTranslation` 和 `serverSideTranslations` 提供 Toast 文案本地化。

第二类是 tRPC：`api.agent.findById.useQuery(agentId, { enabled: router.isReady })` 读取 Agent 详情；`api.agent.deleteById.useMutation` 删除 Agent，并在成功后 `router.push("/")`。

第三类是展示组件：`DashboardLayout` 提供整体应用布局；`ChatWindow` 提供消息窗口壳；`ChatMessage` 渲染单条消息；`FadeIn` 给每条消息加进入动画；`Button` 和 `Toast` 负责底部操作区与复制提示。

第四类是环境与类型：`env.NEXT_PUBLIC_VERCEL_URL` 用来拼接分享链接，`Message` 用于把后端返回的 `tasks` 作为聊天消息数组处理。

## 核心流程

页面加载后，`AgentPage` 先通过 `useRouter` 获取当前路由状态。`agentId` 只在 `router.query.id` 是字符串时有效，否则退化为空字符串。随后页面发起 `findById` 查询，但通过 `enabled: router.isReady` 避免在 Next router 尚未准备好时过早请求。

当 `getAgent.data` 返回后，页面把 `getAgent.data.tasks` 转成 `Message[]`，传给 `ChatWindow`。`ChatWindow` 接收 `messages` 和标题 `getAgent.data.name`，内部渲染窗口头部、滚动区和思考状态；本页通过 `messages.map` 把每条消息包进 `FadeIn`，再交给 `ChatMessage` 展示。

底部三个按钮是页面的主要交互：`Back` 直接跳回 `/`；`Delete` 调用 `deleteAgent.mutate(agentId)`，后端软删除成功后回到首页；`Share` 调用浏览器剪贴板 API 写入 `shareLink()`，成功后把 `showCopied` 设为 `true`，触发 `Toast` 显示“已复制”类提示。

## 关键函数的高层作用

`AgentPage` 是核心组件，职责是把路由参数、后端 Agent 数据、消息展示和页面操作串起来。它本身没有复杂业务算法，更多是一个页面编排层。

`shareLink` 是本页唯一的本地辅助函数，用 `env.NEXT_PUBLIC_VERCEL_URL` 加上 `router.asPath` 生成当前页面地址并 `encodeURI`。它依赖运行环境正确配置公开站点地址，否则复制出的链接可能不完整或不符合预期。

`getStaticProps` 的职责是选择合法 locale 并加载翻译命名空间。它先从 `languages` 提取支持的语言代码，不支持时回退到 `"en"`，再调用 `serverSideTranslations(chosenLocale, nextI18NextConfig.ns)`。这段是 i18n 样板逻辑，不参与 Agent 数据读取。

## 修改风险

最大的风险是误解权限边界。`findById` 在 `next/src/server/api/routers/agentRouter.ts` 中是 `publicProcedure`，只按 `id` 和 `deleteDate: null` 查找，没有限制 `userId`；而 `deleteById` 是 `protectedProcedure`，并按 `userId` 更新。修改详情页或路由时要明确：这个页面当前具备“知道 id 即可查看”的分享语义。如果改成私有访问，会影响分享；如果继续公开，则要注意任务内容是否可能包含敏感信息。

第二个风险是 URL 参数形态。页面使用 `/agent?id=...`，不是路径参数。把路由改成 `/agent/[id]` 时，需要同步修改侧边栏跳转、分享链接生成、可能的静态/服务端数据策略，否则会出现空 `agentId` 或请求时机错误。

第三个风险是消息类型假设。页面直接把 `getAgent.data.tasks` 断言为 `Message[]`，依赖后端 `agentTask` 字段形状与前端 `ChatMessage` 期望一致。若后端任务模型、`messageSchema`、`MESSAGE_TYPE_TASK` 或 `ChatMessage` 展示协议变化，这里可能不会在运行前暴露明显类型错误。

第四个风险是删除交互没有显式确认，也没有处理 mutation 错误。当前 `Delete` 一点即删，成功后跳首页；如果加入确认框、乐观更新或错误提示，要和 `LeftSidebar` 的 `getAll` 缓存失效策略一起考虑，否则侧边栏可能短时间仍显示已删除 Agent。

第五个风险是分享链接依赖 `NEXT_PUBLIC_VERCEL_URL` 和 `router.asPath`。在本地、预览环境或反向代理部署下，环境变量不正确会导致复制链接不可用。改动时应避免把真实外部地址硬编码进页面。
