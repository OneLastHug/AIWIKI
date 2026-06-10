# 目录：docs

## 它负责什么

`docs` 是这个仓库的项目级说明文档目录，主要承担“约束说明”和“架构导航”两类职责，而不是运行时代码的一部分。根据当前片段推断，它面向贡献者和维护者，帮助读者理解 AionUi 的工程边界、目录组织规则、进程划分、开发规范以及变更前需要遵守的工作流。依据来自仓库根部的项目指南：贡献者需要先阅读 `CONTRIBUTING.md`，并在创建文件、修改架构、处理 i18n、测试、PR 等场景下参考对应文档和技能说明。

这个目录的价值在于提供“全局规则的解释层”。源码目录告诉你系统如何运行，`docs` 告诉你为什么要这样分层、哪些位置不能混用、贡献时应该怎样避免破坏既有结构。它不应被理解为 API 实现入口，也不是桌面端主进程或渲染进程的代码入口。

需要说明的是，本次读取到的仓库片段中，命令执行环境没有成功切入目标仓库根目录，直接访问相对路径 `docs` 时显示未找到。因此下面的地图主要根据仓库根部说明中明确引用的 `docs/...` 路径进行概览；证据不足的部分会标注“根据当前片段推断”。

## 直接子目录地图

`docs/contributing`：贡献规范相关文档区。当前片段明确引用了 `docs/contributing/file-structure.md`，说明这里至少包含文件与目录结构规则。它负责解释目录大小限制、拆分责任边界、文件命名和模块组织等约束。对新增模块、移动文件、拆目录这类改动，应优先查这里，而不是只看已有代码风格做猜测。

`docs/architecture`：架构说明相关文档区。当前片段明确引用了 `docs/architecture/overview.md`，说明这里至少包含系统总体架构概览。它重点解释项目的进程边界：`packages/desktop/src/process/` 属于 Main 侧，不应使用 DOM API；`packages/desktop/src/renderer/` 属于 Renderer 侧，不应直接使用 Node.js API；跨进程通信要经过 `packages/desktop/src/preload/` 的 IPC bridge。

根据当前片段推断，`docs` 可能还会随着项目维护继续承载更多主题文档，例如测试、发布、PR 流程或平台约束。但当前证据只确认了 `contributing` 和 `architecture` 两条主线，不应假定这里已经有完整的用户手册或产品说明体系。

## 关键入口

`docs/contributing/file-structure.md` 是理解仓库组织规则的关键入口。项目指南明确要求单个目录的直接子项不能超过 10 个，接近限制时要按职责拆分。这个约束会直接影响新增文件放在哪里、是否需要新建子目录、模块是否应该按 domain、feature 或 process 边界拆开。学习这个目录时，先看它能避免把 `docs` 当作普通说明目录，也能避免在源码中随意堆文件。

`docs/architecture/overview.md` 是理解系统边界的关键入口。AionUi 是桌面应用项目，从根部说明可见它至少区分 Main、Renderer、Preload 三类职责。架构入口的核心不是列文件，而是建立边界感：主进程负责桌面运行环境和系统能力，渲染进程负责 UI 与用户交互，预加载层负责安全桥接。后续阅读 `packages/desktop/src/process/`、`packages/desktop/src/renderer/`、`packages/desktop/src/preload/` 时，都应回到这个架构入口校准理解。

`CONTRIBUTING.md` 虽不在 `docs` 内，但它是进入 `docs` 的上游入口。根部说明要求所有贡献者在 PR 前遵守它，并且它会把读者引导到更细的 `docs` 文档。因此推荐把它看成总索引，把 `docs/contributing/...` 和 `docs/architecture/...` 看成展开说明。

## 主流程位置

文档目录本身没有运行时主流程；它的“主流程”体现在开发者做变更时的决策路径。

新增或调整文件时，主流程从 `CONTRIBUTING.md` 开始，进入 `docs/contributing/file-structure.md`，再结合根部说明中的命名、CSS、TypeScript、i18n、测试约束决定落点。比如组件用 PascalCase，工具函数用 camelCase，hook 使用 `use` 前缀；用户可见文本不能硬编码，要走 i18n；UI 组件优先使用 `@arco-design/web-react`，图标使用 `@icon-park/react`。

理解应用结构时，主流程从 `docs/architecture/overview.md` 开始，再进入实际源码：Main 侧看 `packages/desktop/src/process/`，Renderer 侧看 `packages/desktop/src/renderer/`，跨进程桥接看 `packages/desktop/src/preload/`。这个顺序很重要，因为 IPC 边界决定了功能应该放在哪一侧，不能为了调用方便在 Renderer 中直接使用 Node.js API，也不能在 Main 中引入 DOM 依赖。

提交前验证流程虽然不属于 `docs` 的运行逻辑，但文档会服务于这个流程。常规开发中会运行 `bun run lint:fix`、`bun run format`、`bunx tsc --noEmit`；触及 renderer、locales 或 i18n 配置时，还要运行 `bun run i18n:types` 和 `node scripts/check-i18n.js`。推送前要求使用 `just push`，它串联 lint、格式检查、类型检查、测试与 git push。

## 推荐阅读顺序

第一步读 `CONTRIBUTING.md`，先建立贡献规则总览，了解这个仓库对提交、PR、测试和目录结构的基本要求。

第二步读 `docs/contributing/file-structure.md`，重点看目录拆分、文件放置、目录直接子项上限、命名方式等规则。它会影响你后面阅读源码时对“为什么这里多一层目录”的判断。

第三步读 `docs/architecture/overview.md`，把 Main、Renderer、Preload 的职责边界先记清楚。之后再去看 `packages/desktop/src/process/`、`packages/desktop/src/renderer/`、`packages/desktop/src/preload/`，会更容易判断代码属于哪条链路。

第四步回到根部说明中的专题规则：UI、CSS、TypeScript、i18n、Testing、Workflow。它们虽然不一定都在 `docs` 内，但和 `docs` 的贡献规范、架构规范共同构成项目的约束体系。

第五步再进入具体业务代码。不要一上来逐文件扫描 `docs` 或源码叶子文件；这个目录更适合作为地图，先用它建立边界，再带着问题去找实现。

## 常见误区

误区一：把 `docs` 当成用户手册目录。当前片段显示它更偏工程贡献和架构说明，不是产品功能说明中心。学习它时应关注“开发者如何正确改代码”，而不是寻找应用功能的完整使用教程。

误区二：只看源码现状，不看 `docs/contributing/file-structure.md`。这个项目有明确的目录直接子项上限和拆分规则，新增文件时仅模仿附近目录可能会违反结构约束。

误区三：忽略 Main 和 Renderer 的边界。`docs/architecture/overview.md` 的关键价值就在于避免 API 混用：Main 不碰 DOM，Renderer 不直接碰 Node.js，跨进程能力通过 `packages/desktop/src/preload/` 暴露。

误区四：认为文档目录没有主流程。`docs` 没有运行时入口，但它有开发流程入口：从贡献规范到架构边界，再到测试和提交检查。对维护者来说，这条流程比单个 Markdown 文件的内容更重要。

误区五：把根部说明、`.claude/skills/` 和 `docs` 割裂来看。当前片段中多次提到 architecture、i18n、testing、oss-pr 等技能说明，它们和 `docs` 共同构成项目规则。根据当前片段推断，`docs` 负责稳定的文字化规范，技能文件负责具体任务场景下的操作流程。
