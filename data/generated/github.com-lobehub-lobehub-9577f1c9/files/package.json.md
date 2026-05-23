# 文件：package.json

## 一句话定位

这是整个仓库的“总入口合同”：它定义了项目身份、工作区边界、依赖版本约束，以及开发、构建、测试、数据库、文档和发布这套流水线的统一命令。根据当前片段推断，仓库里大多数日常操作都不是直接跑底层工具，而是先经由这里的 `scripts` 再落到 `next`、`vite`、`tsx`、`drizzle-kit`、`vitest` 等具体执行器。

## 它暴露/定义了什么

它暴露了几类核心信息。第一类是包元数据：`name`、`version`、`description`、`repository`、`license`、`homepage`、`bugs`、`author`，这决定了仓库对外身份。第二类是工作区定义：`workspaces` 把 `packages/*`、`packages/business/*`、`e2e`、`apps/desktop/src/main` 纳入同一套依赖管理。第三类是执行入口：`scripts` 提供构建、开发、测试、lint、i18n、docs、db migration、desktop 打包等命令。第四类是依赖治理：`dependencies`、`devDependencies`、`overrides`、`pnpm.onlyBuiltDependencies`、`patchedDependencies`，它们共同锁定运行时与构建时环境。最后还有 `packageManager`，明确使用 `pnpm@10.33.0`，这会影响安装和 workspace 解析行为。

## 谁调用它

最直接的调用者是开发者和 CI，它们通常通过 `pnpm run ...`、`npm run ...`、`bun run ...` 触发这里的脚本。其次是仓库内的自动化脚本：`scripts/devStartupSequence.mts`、`scripts/copySpaBuild.mts`、`scripts/generateSpaTemplates.mts`、`scripts/migrateServerDB/index.ts` 等，都被这里的脚本名间接调度。再往下是框架和工具链本身：`next`、`vite`、`vitest`、`eslint`、`stylelint`、`drizzle-kit`、`semantic-release`、`playwright` 等依赖这个文件里的版本约束来工作。根据当前片段推断，桌面端、SPA 构建、数据库迁移、文档生成和国际化流程也都以它作为统一入口。

## 它调用谁

它不直接执行业务逻辑，而是把任务转交给外部命令和仓库脚本。比如 `build` 先串起 `build:spa`、`build:spa:copy`、`build:next`；`build:spa:copy` 再调用 `scripts/copySpaBuild.mts` 和 `scripts/generateSpaTemplates.mts`；`build:vercel` 还会接上 `db:migrate`。`dev` 会走 `scripts/devStartupSequence.mts`，后者同时启动 `next dev` 和 `vite`。`db:migrate` 指向 `scripts/migrateServerDB/index.ts`，`workflow:i18n`、`workflow:docs`、`workflow:mdx` 则分别把任务交给对应工作流脚本。也就是说，它更像路由表和编排层，而不是实现层。

## 核心流程

最核心的流程是“安装-开发-构建-发布”四段式。安装阶段，`workspaces` 和 `pnpm` 配置决定依赖如何联邦管理，`overrides` 用来强行统一关键包版本，避免 workspace 间漂移。开发阶段，`dev` 会并行拉起 Next 和 Vite，形成一个既能跑后端页面又能跑 SPA 的混合开发环境。构建阶段，`build:spa` 先产出 `public/_spa`，`build:spa:copy` 再复制静态产物并生成模板，`build:next` 最后交给 Next 编译。测试和质量控制阶段，`lint`、`type-check`、`test-app`、`test-server`、`lint:circular` 负责把类型、样式、循环依赖和单测卡住。发布或部署阶段，`build:docker`、`build:vercel`、`release`、`self-hosting:docker` 则把同一套项目切换到不同交付场景。

## 关键函数的高层作用

这个文件里没有业务函数，但有几类“关键脚本入口”的高层作用值得看。`dev` 和 `dev:next`、`dev:spa` 负责启动本地开发形态；`build:spa:raw`、`build:spa:copy`、`build:next:raw` 负责拆分前端产物与服务端编译；`db:migrate`、`db:generate` 负责数据库 schema 生命周期；`workflow:i18n`、`workflow:docs`、`workflow:mdx` 负责内容资产同步；`lint:*`、`type-check`、`test*` 负责质量门禁。`copySpaBuild.mts` 和 `generateSpaTemplates.mts` 的作用尤其关键：前者把 SPA 构建产物汇聚到 `public/_spa`，后者把 HTML 模板写回 `src/app/spa/[variants]/[[...path]]/spaHtmlTemplates.ts`，让 Next 侧能消费 Vite 产物。

## 修改风险

改这个文件的风险很高，因为它是全仓库的“连接器”。改错脚本名会直接让开发、构建或部署链路失效；改 `overrides` 可能引发隐蔽的兼容性回归；改 `workspaces` 可能让包解析、发布和本地链接失真；改 `packageManager` 会影响锁文件和安装行为。`build`、`dev`、`db:migrate`、`workflow:*` 这类入口还会牵连多个脚本文件，容易出现“单点改动、多处失配”。最稳妥的方式是：只改必要项，改完立刻验证对应脚本链路是否仍然闭合。
