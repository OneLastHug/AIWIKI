# 架构与模块边界

仓库的顶层边界很清晰：`next` 面向浏览器和 Next.js 服务端，`platform` 面向 FastAPI 后端，`cli` 面向本地初始化，`db` 面向 MySQL 容器，`docs` 是产品文档。根目录的 `docker-compose.yml` 把这些边界连接起来：前端挂载 `next` 目录，后端挂载 `platform` 目录，后端与前端都通过环境变量访问同一个 MySQL 服务。依赖方向上，浏览器页面不会直接导入 Python 代码；它通过 `NEXT_PUBLIC_BACKEND_URL` 指向 FastAPI。Next.js 服务端通过 Prisma 访问数据库，FastAPI 通过 SQLAlchemy async engine 访问数据库，两边共享数据库但各自有独立的数据访问层。

`next/src/pages` 是用户入口层。`index.tsx` 是默认工作台，它组合 landing、chat、对话框、layout、hook、store 和 agent service。`agent/index.tsx` 是单个历史 agent 的展示页，通过 tRPC `api.agent.findById` 读取保存的 tasks。`pages/api/auth` 和 `pages/api/trpc` 是 Next.js API 边界：前者交给 NextAuth，后者交给 tRPC handler。`next/src/server/api` 是服务端 tRPC 层，目前根路由只注册 `agentRouter`；它负责创建、保存、列出、查找、软删除 agent 历史，并调用 Prisma。

`next/src/services/agent` 是前端 agent 编排层，是理解业务的核心。`autonomous-agent.ts` 管理生命周期、`workLog` 和错误重试；`agent-run-model.tsx` 把运行状态映射到 `useAgentStore` 与 `useTaskStore`；`agent-api.ts` 把前端 work 转为 FastAPI 请求；`message-service.ts` 负责把 goal、task、analysis、error 等转成 UI message；`agent-work` 下每个类代表一个步骤。这个目录依赖 `stores`、`types`、`utils/interfaces`、`services/api-utils` 与 `services/stream-utils`，但不依赖 UI 组件，因此它是比较好的业务边界。

`platform/reworkd_platform/web` 是后端 Web 边界。`application.py` 构造 FastAPI app，`api/router.py` 注册 monitoring、agent、models、auth、metadata 子路由。`web/api/agent/views.py` 是 agent HTTP 层，只做依赖注入、请求对象接收、调用 service、包装响应；真正业务在 `web/api/agent/agent_service/open_ai_agent_service.py`。它用 prompt、LangChain、OpenAI function calling、tool 和 tokenizer 来实现 start/analyze/execute/create/summarize/chat。`agent_service/agent_service.py` 是 Protocol，说明这是一个可替换实现点，`mock_agent_service.py` 则支持 mock 模式。

工具层在 `platform/reworkd_platform/web/api/agent/tools`。`tool.py` 定义抽象基类，`tools.py` 汇总可用工具并提供 name 到 class 的映射。默认工具是 `Search`，外部工具包括 `Image`、`Code`、`SID`；`Wikipedia` 文件存在但在 `get_external_tools()` 中被注释掉。`open_ai_function.py` 把 tool 描述转换成 OpenAI function schema，`OpenAIAgentService.analyze_task_agent` 使用这些 schema 让模型选择 action 和 arg。扩展新工具通常需要新增 `Tool` 子类，并在 `tools.py` 注册。

数据层有前后端两套边界。Next.js 的 `next/prisma/schema.prisma` 覆盖 NextAuth、agent 历史、组织与 OAuth credential；`next/src/server/db.ts` 提供 Prisma client。FastAPI 的 `platform/reworkd_platform/db` 包含 SQLAlchemy base、engine、session dependency、crud 和 models。`web/lifetime.py` 在 app startup 初始化 async session factory 和 tokenizer，shutdown 时释放 engine。认证边界也跨前后端：NextAuth 生成 session token，前端请求 FastAPI 时把 `session.accessToken` 放入 Authorization bearer，FastAPI 的 `get_current_user` 再用该 token 查询 `Session` 表。

扩展点可以按责任拆开：要扩展前端运行步骤，看 `agent-work` 与 `AutonomousAgent.next()` 链；要扩展后端 step，看 `views.py`、`schemas/agent.py` 和 `AgentService`；要扩展工具，看 `tools/tool.py` 与 `tools/tools.py`；要扩展持久化历史，看 `next/prisma/schema.prisma` 和 `agentRouter`；要扩展 OAuth 集成，看 `platform/reworkd_platform/services/oauth_installers.py` 与 `web/api/auth/views.py`。根据当前文件推断，项目更偏“前端驱动循环”，后端不长期托管 agent 状态，而是按请求记录 run/task 并返回本轮结果。
