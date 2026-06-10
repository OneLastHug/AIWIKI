# 文件：next/src/server/api/routers/agentRouter.ts

## 一句话定位

`next/src/server/api/routers/agentRouter.ts` 是 Agent 历史记录的 tRPC 服务端路由，负责创建 Agent、保存执行消息、查询列表/详情，以及软删除用户自己的 Agent。

## 它暴露/定义了什么

这个文件主要导出三类内容：输入结构、类型、路由本体。

它用 `zod` 定义了 `createAgentParser` 和 `saveAgentParser`。前者只接收 `goal: string`，用于创建 Agent；后者接收 `id: string` 和 `tasks: messageSchema[]`，用于把一次 Agent 运行过程中产生的消息保存为数据库任务记录。对应类型 `CreateAgentProps`、`SaveAgentProps` 被前端 hook 复用，保证调用端和服务端输入结构一致。

核心导出是 `agentRouter`，其中包含五个 tRPC procedure：`create`、`save`、`getAll`、`findById`、`deleteById`。其中 `create`、`save`、`getAll`、`deleteById` 是 `protectedProcedure`，要求登录态；`findById` 是 `publicProcedure`，允许公开按 id 读取未删除 Agent 及任务，这也支撑分享链接场景。

## 谁调用它

`agentRouter` 被 `next/src/server/api/root.ts` 挂载到根路由的 `agent` 字段，因此客户端通过 `api.agent.*` 调用。

前端主要调用点包括：`next/src/hooks/useAgent.ts` 通过 `api.agent.create.useMutation` 和 `api.agent.save.useMutation` 封装创建与保存；`next/src/services/agent/agent-api.ts` 在 Agent 运行开始时调用 `createAgent()`，并在有 `agentId` 后用 `saveMessages()` 保存消息；`next/src/components/drawer/LeftSidebar.tsx` 用 `api.agent.getAll.useQuery` 展示当前用户最近 Agent 列表；`next/src/pages/agent/index.tsx` 用 `api.agent.findById.useQuery` 展示详情，用 `api.agent.deleteById.useMutation` 删除当前 Agent。

## 它调用谁

它调用 tRPC 基础设施 `createTRPCRouter`、`protectedProcedure`、`publicProcedure` 来注册接口；调用 `prisma` 或 `ctx.prisma` 访问数据库中的 `Agent`、`AgentTask` 表；调用 `OpenAI` SDK 的 `chat.completions.create` 为用户目标生成一个更短的 Agent 名称；读取 `env.OPENAI_API_KEY` 判断是否启用自动命名；复用 `messageSchema` 校验保存的消息结构，并用 `MESSAGE_TYPE_TASK` 判断是否写入任务状态字段。

## 核心流程

创建流程从客户端提交 `goal` 开始。`create` 先尝试调用 `generateAgentName(goal)`，如果环境中没有 `OPENAI_API_KEY` 或 OpenAI 调用失败，就退回使用原始 `goal` 作为名称。随后写入 `Agent` 表，保存 `name`、`goal` 和当前登录用户 id。

保存流程由运行中的 Agent 服务层触发。`save` 先按 `id` 和 `ctx.session.user.id` 查询 Agent，确保只能保存自己的记录；找不到则抛出 `Agent not found`。随后把传入的 `tasks` 映射成多条 `AgentTask` 创建操作，写入 `agentId`、`type`、`info`、`value`，如果消息类型是 `MESSAGE_TYPE_TASK`，额外保存 `status`。这些创建操作通过 `Promise.all` 并发执行。

查询列表流程 `getAll` 只返回当前用户、未软删除的 Agent，按 `createDate` 倒序取 20 条。详情流程 `findById` 根据 id 查询未删除 Agent，并 include 其 `tasks`，任务按 `createDate` 升序排列。删除流程 `deleteById` 不物理删除，而是用 `updateMany` 给匹配当前用户的 Agent 写入 `deleteDate`。

## 关键函数的高层作用

`generateAgentName(goal)` 是自动命名辅助函数。它把用户目标发给 OpenAI，要求生成“一两个词 + GPT + emoji”的短名称。这个函数失败时不会阻断主流程，只记录错误并返回 `undefined`，因此 `create` 可以退回原目标作为名称。

`create` 是 Agent 持久化入口，负责把一次新运行与登录用户绑定。

`save` 是运行结果落库入口，负责把前端/服务层中的消息列表转换为 `AgentTask` 记录。它的权限校验依赖先查 `Agent` 的 `userId`，然后用查到的 `agent.id` 写任务。

`getAll` 是侧边栏历史列表的数据源；`findById` 是详情页和分享查看的数据源；`deleteById` 是软删除入口，不处理关联任务的删除。

## 修改风险

第一，`findById` 是公开接口。它不校验 `userId`，只要知道 id 就能读取 Agent 和任务。根据当前片段推断，这是为了支持 `Share` 功能，因为详情页会生成分享链接；但如果任务内容可能包含敏感信息，这里就是访问控制风险。

第二，`save` 每次调用都会追加 `AgentTask`，没有去重、清空旧任务或幂等键。如果前端重复调用保存，数据库会出现重复消息。修改保存语义时要同步检查 `AgentApi.saveMessages()` 的调用时机。

第三，`save` 中 `sort` 固定写 `0`，实际展示依赖 `createDate` 排序。并发写入时，时间顺序通常可用但不是严格业务顺序；如果未来需要稳定复现执行序列，应引入真实序号并调整查询排序。

第四，`create` 使用 OpenAI 生成名称会引入外部调用延迟和失败可能。当前失败会降级，不影响创建；如果改成强依赖自动命名，会直接影响 Agent 创建可用性。

第五，文件里同时使用 `ctx.prisma` 和直接导入的 `prisma`。功能上可运行，但如果项目未来在 tRPC context 中加入事务、租户隔离或测试 mock，这种混用会增加维护成本。

第六，`deleteById` 只软删除 Agent，不软删除 `AgentTask`。当前详情查询通过 Agent 的 `deleteDate` 屏蔽已删除记录，所以表现上可接受；但任务数据仍留在表中，涉及数据清理、隐私删除或统计时需要额外处理。
