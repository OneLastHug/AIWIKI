# AgentGPT 源码阅读索引

本索引给刚接触该仓库的读者一个推荐阅读顺序。仓库根目录下的 `README.md` 说明它是一个在浏览器中配置并运行 autonomous AI agent 的项目；源码本身把系统拆成 `next` 前端、`platform` 后端、`cli` 初始化工具、`db` 数据库镜像与根目录 Docker 编排。阅读时不要先陷入每个 UI 组件，而应先理解“用户输入目标 -> 前端 agent 循环 -> 后端 FastAPI 生成/分析/执行任务 -> 数据库存储运行与历史”的主线。

推荐先读这些总览页：

1. [00-overview.md](00-overview.md)：先建立项目解决的问题、核心能力、主要模块与初学者切入点。
2. [01-tech-stack.md](01-tech-stack.md)：理解 Next.js、tRPC、NextAuth、Prisma、FastAPI、SQLAlchemy、LangChain、OpenAI、Docker 等技术信号。
3. [02-architecture.md](02-architecture.md)：看清目录分层、模块边界、关键依赖方向和扩展点。
4. [03-runtime-flow.md](03-runtime-flow.md)：按启动、配置、认证、任务流、流式返回、持久化来串起调用链。
5. [04-reading-guide.md](04-reading-guide.md)：按“必读、后读、可跳过”的节奏继续下钻。

后续最值得看的源码目录是 `next/src/pages`、`next/src/services/agent`、`next/src/server/api`、`next/src/server/auth`、`next/src/stores`、`platform/reworkd_platform/web/api/agent`、`platform/reworkd_platform/web/api/agent/tools`、`platform/reworkd_platform/db`、`platform/reworkd_platform/schemas`、`cli/src`。关键种子文件包括 `docker-compose.yml`、`.env.example`、`next/package.json`、`platform/pyproject.toml`、`next/src/pages/index.tsx`、`next/src/services/agent/autonomous-agent.ts`、`next/src/services/agent/agent-api.ts`、`platform/reworkd_platform/__main__.py`、`platform/reworkd_platform/web/application.py`、`platform/reworkd_platform/web/api/agent/views.py`、`platform/reworkd_platform/web/api/agent/agent_service/open_ai_agent_service.py`、`platform/reworkd_platform/web/api/agent/tools/tools.py`、`next/prisma/schema.prisma`。读这些文件能覆盖用户入口、API 边界、agent 循环、工具选择、认证、数据库结构和部署方式。
