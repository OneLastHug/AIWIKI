# 项目总览阅读顺序

这是一个面向 LobeHub 仓库新读者的阅读入口。先看 [00-overview.md](/data/project/AIWIKI/data/generated/github.com-lobehub-lobehub-9577f1c9/00-overview.md)，先建立“这个项目要解决什么问题”的整体认识；再看 [01-tech-stack.md](/data/project/AIWIKI/data/generated/github.com-lobehub-lobehub-9577f1c9/01-tech-stack.md)，把运行环境、构建方式和主要技术栈对齐；接着读 [02-architecture.md](/data/project/AIWIKI/data/generated/github.com-lobehub-lobehub-9577f1c9/02-architecture.md) 理清目录分层和依赖方向；然后看 [03-runtime-flow.md](/data/project/AIWIKI/data/generated/github.com-lobehub-lobehub-9577f1c9/03-runtime-flow.md) 追踪启动与请求流转；最后用 [04-reading-guide.md](/data/project/AIWIKI/data/generated/github.com-lobehub-lobehub-9577f1c9/04-reading-guide.md) 选择最适合继续下钻的入口。

优先关注的目录是 `src/app`、`src/spa`、`src/routes`、`src/features`、`src/server`、`src/services`、`src/store`、`packages/database`、`packages/agent-runtime`、`packages/model-runtime`、`packages/builtin-tools`、`apps/desktop` 和 `apps/cli`。它们分别对应请求入口、SPA 启动、页面层、业务组件、服务端路由、客户端服务、状态层、数据库、Agent runtime、模型 runtime、内建工具、桌面端和命令行入口，是理解整仓最省力的顺序。

如果只准备先看少量文件，建议从根目录 `package.json`、`README.zh-CN.md`、`next.config.ts`、`vite.config.ts`、`src/app/spa/[variants]/[[...path]]/route.ts`、`src/spa/entry.web.tsx` 和 `src/utils/router.tsx` 开始，再向 `src/server/routers/lambda/index.ts`、`src/server/services/agentRuntime/AgentRuntimeService.ts`、`packages/database/src/schemas/index.ts` 继续扩展。
