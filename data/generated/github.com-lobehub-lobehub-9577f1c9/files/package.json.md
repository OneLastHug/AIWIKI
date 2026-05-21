# 文件：package.json

## 它负责什么

`package.json` 是这个仓库的根级工程清单，负责把 LobeHub 这个大型 monorepo 组织成一个可安装、可开发、可构建、可发布的项目。它不是业务代码文件，但它决定了开发者日常最常接触的入口：依赖怎么装、哪些目录属于 workspace、开发服务怎么启动、SPA 和 Next.js 怎么构建、数据库迁移怎么跑、桌面端怎么打包、测试和 lint 怎么执行。

从 `name: "@lobehub/lobehub"`、`version: "2.2.0"`、`workspaces` 和大量 `@lobechat/*` 的 `workspace:*` 依赖可以看出，这个根包既是应用主包，也是 monorepo 的调度中心。它把根目录的 `src/`、`packages/`、`apps/desktop/`、`e2e/`、`scripts/` 等目录串起来。

这个文件本身没有 TypeScript 意义上的 `import/export`，它的“导出”方式是 npm/pnpm 生态约定：对外暴露包元信息、脚本命令、依赖版本、workspace 边界和 pnpm 配置；对内被 `pnpm`、`bun`、`npm scripts`、Vercel/Docker/CI、Git hooks、lint-staged 等工具读取。

## 关键组成

第一部分是包元信息：

- `name`: `@lobehub/lobehub`
- `version`: `2.2.0`
- `description`、`keywords`、`homepage`、`bugs`、`repository`、`license`、`author`

这些字段主要服务 npm 生态、开源仓库展示、发布和自动化工具。虽然根包带有 `publishConfig`，但从项目结构看，它更像应用型根包，而不是普通库包。

`sideEffects` 只声明了：

```json
[
  "./src/initialize.ts"
]
```

这表示打包器做 tree-shaking 时，需要保留 `src/initialize.ts` 的副作用。小白要注意：这个字段不是“哪些文件会被执行”，而是告诉构建工具“这个文件即使没有显式使用导出，也不要随便删”。

第二部分是 workspace 配置：

```json
"workspaces": [
  "packages/*",
  "packages/business/*",
  "e2e",
  "apps/desktop/src/main"
]
```

它说明根项目管理几个子包区域：普通共享包、业务扩展包、端到端测试包、Electron 主进程包。同目录的 `pnpm-workspace.yaml` 也声明了 workspace 范围，并额外包含 `.` 和 `packages/**`。两者共同服务包管理工具，但实际以 `pnpm-workspace.yaml` 对 pnpm 的 workspace 识别更直接。根据当前片段推断，`package.json` 的 `workspaces` 兼容 npm/yarn 风格或其他工具读取，`pnpm-workspace.yaml` 则是 pnpm 的主要 workspace 配置来源。

第三部分是 `scripts`，这是全文件最重要的区域。可以按用途分组理解：

开发入口：

- `dev`: 执行 `tsx scripts/devStartupSequence.mts`
- `dev:next`: 启动 Next.js，端口 `3010`
- `dev:spa`: 启动 Vite SPA，端口 `9876`
- `dev:spa:mobile`: 以 `MOBILE=true` 启动移动端 SPA，端口 `3012`
- `dev:desktop`: 进入 `apps/desktop` 后运行桌面端开发命令
- `dev:docker`: 启动本地依赖服务，如 PostgreSQL、Redis、RustFS、SearXNG

构建入口：

- `build`: 先构建 SPA，再复制/生成 SPA 模板，最后构建 Next.js
- `build:spa`: 设置较大内存后运行 SPA 构建
- `build:spa:raw`: 清理 `public/_spa` 后执行 `vite build`
- `build:spa:copy`: 执行 `scripts/copySpaBuild.mts` 和 `scripts/generateSpaTemplates.mts`
- `build:next`: 设置内存后执行 `next build`
- `build:docker`: 面向 Docker 镜像的构建流程
- `build:vercel`: 面向 Vercel 的构建流程，并在构建后跑 `db:migrate`

数据库相关：

- `db:generate`: `drizzle-kit generate` 后生成 DBML
- `db:migrate`: 通过 `scripts/migrateServerDB/index.ts` 跑服务端数据库迁移
- `db:studio`: 打开 Drizzle Studio
- `db:visualize`: 用 `dbdocs` 生成数据库文档视图

质量检查：

- `lint`: 聚合执行 TypeScript lint、stylelint、type-check、循环依赖检查
- `lint:ts`: 对 `src/` 和 `tests/` 跑 ESLint
- `lint:style`: 对 JS/TS/React 文件跑 stylelint
- `lint:circular`: 用 `dpdm` 检查主应用和 packages 的循环依赖
- `type-check`: 使用 `tsgo --noEmit`
- `type-check:tsc`: 使用传统 `tsc --noEmit`

测试相关：

- `test`: 聚合 `test-app` 和 `test-server`，但当前片段没有看到 `test-server` 的定义，可能由外部脚本、历史遗留或未同步配置造成；这是一个阅读时应留意的点。
- `test-app`: `vitest run`
- `test:update`: `vitest -u`
- `test:e2e`: 通过 pnpm filter 运行 `@lobechat/e2e-tests`
- `e2e`: 进入 `e2e` 目录执行测试

桌面端相关：

- `desktop:build:*`
- `desktop:package:*`
- `desktop:build-channel`
- `workflow:set-desktop-version`

这些脚本要么委托给 `apps/desktop`，要么调用 `scripts/electronWorkflow/*`，说明 Electron 桌面端不是根包里直接构建，而是由根脚本统一调度。

文档、国际化和发布：

- `i18n`
- `i18n:unused`
- `docs:cdn`
- `docs:i18n`
- `docs:seo`
- `release`
- `release:branch`
- `workflow:changelog`
- `workflow:readme`

这些命令说明仓库内存在一套较成熟的自动化工作流，许多非业务操作都落在 `scripts/*Workflow/` 下。

第四部分是 `lint-staged`，它定义提交前对不同文件类型的自动修复规则。例如：

- Markdown 用 `remark` 和 `prettier`
- JSON 用 `prettier`
- TS/TSX 用 `stylelint`、`eslint`、`prettier`
- YAML 用 `eslint --fix`

这和 `prepare: git config core.hooksPath .githooks` 配合，说明仓库使用自定义 Git hooks，并在提交前自动格式化和修复部分问题。

第五部分是依赖：

`dependencies` 里既有运行时依赖，也有大量 workspace 内部包。可以按系统层次看：

- 前端框架：`next`、`react`、`react-dom`、`vite`、`react-router-dom`
- UI 和样式：`@lobehub/ui`、`antd`、`antd-style`、`lucide-react`、`@ant-design/icons`
- 状态和数据：`zustand`、`swr`、`@tanstack/react-query`、`@trpc/*`
- AI/模型供应商：`openai`、`@anthropic-ai/sdk`、`@google/genai`、`ollama`、`@aws-sdk/client-bedrock-runtime`、`@huggingface/inference`
- 数据库和服务端：`drizzle-orm`、`pg`、`@neondatabase/serverless`、`ioredis`
- 鉴权和安全：`better-auth`、`jose`、`oidc-provider`
- 文档和文件处理：`pdfjs-dist`、`pdf-parse`、`mammoth`、`officeparser`、`epub2`
- 可观测性和云平台：`@opentelemetry/*`、`@vercel/*`、`langfuse`
- 内部包：大量 `@lobechat/*` 和 `@lobehub/*` 的 `workspace:*`

`devDependencies` 主要是开发、构建、测试、lint、发布工具，例如 `eslint`、`typescript`、`vitest`、`@playwright/test`、`drizzle-kit`、`prettier`、`stylelint`、`semantic-release`、`tsx`。

第六部分是版本约束：

根级 `overrides` 和 `pnpm.overrides` 都在锁定关键依赖版本，例如：

- `react`
- `react-dom`
- `@types/react`
- `antd`
- `drizzle-orm`
- `pdfjs-dist`
- `lexical`
- `better-auth`

这类字段通常是为了解决 monorepo 中多包依赖版本不一致、上游兼容问题或构建稳定性问题。阅读时要把它看作“全仓强制版本策略”，不是普通依赖声明。

第七部分是 pnpm 专属配置：

```json
"packageManager": "pnpm@10.33.0+sha512..."
```

这要求项目使用特定 pnpm 版本。`pnpm.onlyBuiltDependencies` 控制哪些依赖允许执行构建脚本；`pnpm.patchedDependencies` 声明 `@upstash/qstash` 使用本地 patch：

```json
"@upstash/qstash": "patches/@upstash__qstash.patch"
```

这说明安装依赖时，pnpm 会把仓库内的补丁应用到第三方包上。不要误以为所有行为都来自 npm registry 原包。

## 上下游关系

上游读取方主要是工具链，而不是业务源码：

- `pnpm` 读取 `packageManager`、`dependencies`、`devDependencies`、`pnpm`、workspace 配置
- `bun` 主要用于执行脚本，例如 `bun run dev`、`bun run build`
- `npm` 在部分脚本中作为兼容执行器出现，例如 `npm run workflow:i18n`
- `vite` 由 `dev:spa`、`build:spa:*` 调起，服务 SPA
- `next` 由 `dev:next`、`build:next`、`start` 调起，服务 Next.js 后端/API/SSR 部分
- `drizzle-kit` 和迁移脚本读取数据库配置并生成/执行迁移
- `vitest`、`eslint`、`stylelint`、`tsgo`、`dpdm` 读取源码并进行质量检查
- `semantic-release`、`commitlint`、`lint-staged`、Git hooks 读取发布和提交约束

下游被调度的代码集中在这些区域：

- `src/`: 主应用源码，包括 Next.js 后端、SPA 页面、features、store、services
- `packages/`: 内部 workspace 包，如模型运行时、数据库、工具、agent runtime
- `apps/desktop/`: Electron 桌面端
- `e2e/`: 端到端测试
- `scripts/`: 构建、迁移、文档、i18n、发布、桌面端工作流脚本
- `public/_spa`: SPA 构建产物目标之一
- `docs/`、`locales/`: 文档和国际化资源

从依赖关系看，根包是“消费者”和“聚合器”。它通过 `workspace:*` 依赖本仓内部包，同时用脚本把这些包和主应用组织成完整产品。它不是某个具体业务模块的上游，而是整个工程运行的上游入口。

## 运行/调用流程

本地开发时，典型流程是：

1. 使用 `pnpm` 安装依赖，pnpm 根据 `packageManager`、workspace 配置、`pnpm.overrides` 和 `patchedDependencies` 解析依赖。
2. 执行 `bun run dev`，进入 `scripts/devStartupSequence.mts`。根据当前片段推断，这个脚本负责组织 Next.js、Vite SPA 或相关开发前置检查，因为真正的底层命令也分别存在于 `dev:next` 和 `dev:spa`。
3. 如果只开发 SPA，可以执行 `bun run dev:spa`，它直接启动 `vite --port 9876`。
4. 如果需要完整 Next.js 服务，可以执行 `bun run dev:next`，它启动 `next dev -p 3010`。
5. 如果需要本地数据库、Redis、对象存储等依赖，可以先执行 `dev:docker`。

生产构建时，核心流程是：

1. `build` 先执行 `build:spa`。
2. `build:spa` 设置 `NODE_OPTIONS=--max-old-space-size=8192`，再执行 `build:spa:raw`。
3. `build:spa:raw` 清空 `public/_spa`，然后执行 `vite build`。
4. `build:spa:copy` 调用 `scripts/copySpaBuild.mts` 和 `scripts/generateSpaTemplates.mts`，把 SPA 构建结果转成 Next.js 可服务的模板或静态资源。
5. `build:next` 执行 `next build`，构建 Next.js 部分。
6. 对 Vercel 场景，`build:vercel` 会跑 `build:raw`，然后执行 `db:migrate`。

数据库变更流程一般是：

1. 修改 Drizzle schema。
2. 执行 `db:generate` 生成 migration，并同步 DBML 文档。
3. 执行 `db:migrate` 应用迁移。
4. 如需查看结构，使用 `db:studio` 或 `db:visualize`。

提交代码时，流程是：

1. `prepare` 设置 Git hooks 路径为 `.githooks`。
2. Git hook 触发 `lint-staged`。
3. `lint-staged` 根据文件类型运行格式化、lint 和修复。
4. CI 或开发者手动执行 `lint`、`type-check`、`test-app`、`test:e2e` 等进一步验证。

## 小白阅读顺序

建议不要从依赖列表一行行看起，会很容易迷失。更好的顺序是：

1. 先看顶部元信息，确认这是根包：`name`、`version`、`description`、`repository`。
2. 看 `workspaces`，建立 monorepo 地图：`packages/*`、`packages/business/*`、`e2e`、`apps/desktop/src/main`。
3. 看 `scripts`，只先记住几条主线命令：`dev`、`dev:spa`、`dev:next`、`build`、`build:docker`、`db:generate`、`db:migrate`、`lint`、`type-check`、`test-app`。
4. 回到项目目录结构，把脚本和目录对应起来：`vite.config.ts` 对应 SPA，`next.config.ts` 对应 Next.js，`scripts/` 对应自动化流程，`apps/desktop` 对应桌面端。
5. 再看 `dependencies`，按功能分组识别，不要试图背版本号：React/Next/Vite、UI、状态、TRPC、数据库、AI SDK、内部 workspace 包。
6. 最后看 `overrides`、`pnpm`、`patchedDependencies`，理解为什么某些依赖版本被强制锁定。

如果只是为了跑项目，优先理解这些命令：

```bash
bun run dev
bun run dev:spa
bun run dev:next
bun run build
bun run lint
bun run type-check
bunx vitest run --silent='passed-only' <file>
```

如果只是为了改业务代码，`package.json` 不是每天都要改，但它能告诉你项目用了哪些基础设施。

## 常见误区

误区一：以为 `package.json` 里的 `workspaces` 就是 pnpm 的唯一 workspace 来源。  
实际同目录还有 `pnpm-workspace.yaml`，pnpm 更直接读取它。两个文件的范围相近但不完全相同，例如 `pnpm-workspace.yaml` 使用了 `packages/**` 并包含 `.`。阅读 workspace 时要两个文件一起看。

误区二：以为所有脚本都应该用同一个包管理器。  
这个仓库里同时出现了 `bun run`、`pnpm run`、`npm run`、`bunx`、`pnpx`。这不是随意混用，而是不同场景下的历史兼容和工具选择。根要求里也明确包管理用 `pnpm`，脚本常用 `bun` 执行。

误区三：以为 `build` 只是 `next build`。  
这里的 `build` 是组合流程：先构建 SPA，再复制和生成 SPA 模板，最后构建 Next.js。LobeHub 是 Next.js 内嵌 SPA 的结构，不能只看传统 Next.js 应用的构建方式。

误区四：以为 `dev:spa` 就是完整后端。  
`dev:spa` 只启动 Vite SPA，端口是 `9876`。完整 Next.js 开发服务是 `dev:next`，端口是 `3010`。根级 `dev` 则通过 `scripts/devStartupSequence.mts` 编排更完整的启动体验。

误区五：以为 `dependencies` 里的 `workspace:*` 是外部 npm 包。  
`workspace:*` 表示依赖当前 monorepo 内部包，比如 `@lobechat/agent-runtime`、`@lobechat/database`、`@lobechat/model-runtime`。这些包的源码在 `packages/` 或相关 workspace 目录中。

误区六：忽略 `overrides` 和 `pnpm.overrides`。  
大型 monorepo 里，依赖版本被强制覆盖很常见。如果某个包实际安装版本和子包声明不同，先检查 overrides，而不是只看单个 package 的依赖声明。

误区七：看到 `test` 就直接跑。  
根脚本里 `test` 会聚合测试，可能耗时较长；仓库说明也强调不要随便跑完整 `bun run test`。日常应优先跑目标文件相关的 `vitest run`。

误区八：以为 `sideEffects` 是运行入口。  
`sideEffects` 是给打包器看的 tree-shaking 配置。`./src/initialize.ts` 被标记为有副作用，只说明它不能被构建优化轻易移除，不代表它是应用启动主入口。

误区九：忽略本地 patch。  
`pnpm.patchedDependencies` 声明了 `@upstash/qstash` 使用 `patches/@upstash__qstash.patch`。如果排查 Upstash QStash 行为，不能只看官方包源码，也要看本仓 patch。

误区十：把根 `package.json` 当成业务模块。  
它不承载具体聊天、agent、数据库、UI 业务逻辑；它负责把这些业务所在的 `src/`、`packages/`、`apps/desktop/`、`scripts/` 组织起来。读业务逻辑时，它是地图，不是目的地。
