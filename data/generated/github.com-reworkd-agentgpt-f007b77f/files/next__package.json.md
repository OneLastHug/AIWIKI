# 文件：next/package.json

## 一句话定位

`next/package.json` 是 AgentGPT 前端/全栈 Next.js 应用的包清单和运行入口定义文件，集中声明 Node 版本约束、npm scripts、运行时依赖、开发依赖、提交钩子与脚手架元信息；仓库根目录没有顶层 `package.json`，因此它基本承担了 `next` 子应用的项目入口职责。

## 它暴露/定义了什么

它定义的核心内容有五类。第一是包身份：`name` 为 `agent-gpt`，`private: true` 表明该包不用于发布到 npm。第二是运行环境：`engines.node` 约束为 `>=18.0.0 <19.0.0`，CI 也使用 Node 18。第三是脚本入口：`build`、`dev`、`postinstall`、`lint`、`start`、`prepare`、`test`。第四是业务依赖：Next 13、React 18、NextAuth、Prisma、tRPC、React Query、OpenAI SDK、i18n、Tailwind、Zustand、Markdown/PDF/动画/可视化相关包等。第五是工程依赖：TypeScript、Jest、ESLint、Prettier、Husky、lint-staged、Prisma CLI、Tailwind/PostCSS 等。

## 谁调用它

直接调用者主要是 npm、CI、Docker 和开发者本地命令。`.github/workflows/node.js.yml` 在 `next` 目录执行 `npm ci`、`npm test`、`npm run postinstall`，因此 CI 的安装、测试和 Prisma Client 生成都依赖这里的配置。`next/Dockerfile` 复制 `package*.json` 后运行 `npm ci`，容器启动命令是 `npm run dev`。开发者本地通常通过 `npm run dev`、`npm run build`、`npm run lint`、`npm test` 使用它。`prepare` 还会在安装生命周期中配置 `next/.husky` Git hooks。

## 它调用谁

`package.json` 自身不执行业务逻辑，但它的 scripts 会委托给多个工具链。`dev`、`build`、`start` 调用 `next` CLI，进一步读取 `next/next.config.mjs`、`src/pages`、`src/server`、`public`、`styles` 等应用代码。`postinstall` 调用 `prisma generate`，依赖 `next/prisma/schema.prisma` 生成 `@prisma/client`。`lint` 调用 `cross-env` 设置 `SKIP_ENV_VALIDATION=1` 后执行 `next lint --fix`。`test` 同样通过 `cross-env` 跳过环境变量校验，再调用 `jest`，Jest 配置来自 `next/jest.config.cjs`。`prepare` 调用 `husky install next/.husky`。依赖层面，它把页面渲染、认证、数据库访问、API RPC、状态管理、AI 调用、国际化和样式构建分别交给 `next`、`next-auth`、`@prisma/client`、`@trpc/*`、`zustand`、`openai`、`next-i18next`、`tailwindcss` 等包。

## 核心流程

本地开发流程通常是进入 `next` 目录后安装依赖，`npm ci` 会根据 `package-lock.json` 安装精确版本，并触发 `postinstall` 生成 Prisma Client；随后 `npm run dev` 启动 Next 开发服务器。启动 Next 时会加载 `next.config.mjs`，该配置默认导入 `src/env/server.mjs` 做环境变量校验，除非脚本显式设置 `SKIP_ENV_VALIDATION=1`。构建流程由 `npm run build` 触发 `next build --no-lint`，也会经过 Next 配置、页面编译、webpack 自定义规则、i18n 配置和服务端代码打包。测试流程由 `npm test` 调用 Jest，`jest.config.cjs` 使用 `next/jest` 读取 Next 配置，并在 `jest-environment-jsdom` 中执行 `__tests__`。容器流程中，`Dockerfile` 先 `npm ci`，入口脚本 `entrypoint.sh` 等待数据库、执行 Prisma migrate/db push/generate，最后执行 `npm run dev`。

## 关键函数的高层作用

该文件没有传统意义上的函数，关键“入口”是 npm scripts。`dev` 是开发态入口，负责把应用交给 Next dev server。`build` 是生产构建入口，但使用 `--no-lint`，说明 lint 不在构建阶段强制执行。`postinstall` 是数据库客户端生成入口，保证 `@prisma/client` 与 `schema.prisma` 同步。`lint` 是代码风格和静态检查入口，并自动修复。`test` 是单元测试入口，通过跳过环境校验降低测试对真实密钥和数据库环境的依赖。`prepare` 是 Git hook 初始化入口。辅助配置如 `lint-staged` 只在提交前对部分文件运行 ESLint/Prettier，属于工程质量兜底。

## 修改风险

风险最高的是依赖版本和脚本语义。升级 `next`、`react`、`next-auth`、`@trpc/*`、`@prisma/client`、`prisma`、`openai` 可能引发框架 API、构建产物、认证回调、数据库生成代码或 AI 调用接口变化；尤其 `@prisma/client` 与 `prisma` 版本应保持兼容，否则 `postinstall` 或运行时数据库访问可能失败。修改 `engines.node` 也要同步 CI、Docker 基础镜像和本地开发环境；当前 `package.json` 要求 Node `<19`，但 `next/Dockerfile` 使用 `node:19-alpine`，根据当前片段推断这里存在环境约束不一致，依据是 `engines.node` 与 Dockerfile 镜像版本冲突。删除或改动 `SKIP_ENV_VALIDATION=1` 会让 lint/test 受真实环境变量影响，可能使无密钥 CI 失败。改动 `build` 的 `--no-lint` 会改变构建门槛。新增依赖必须更新 `package-lock.json`，否则 `npm ci`、Docker 构建和 CI 缓存会不一致。修改 `prepare` 或 `lint-staged` 会影响提交钩子安装与提交前自动修复流程，属于团队协作风险。
