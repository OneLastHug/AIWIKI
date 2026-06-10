# 目录：packages/coding-agent

## 它负责什么

`packages/coding-agent` 是仓库中面向“代码代理”能力的核心包。根据当前片段推断，它承载的是一个可在真实工作区中读取代码、规划任务、调用模型、执行工具、处理交互会话并产出修改结果的 agent 层，而不是单纯的 CLI 外壳或 UI 组件。依据包括仓库规则中多次提到 `packages/coding-agent/test/suite/`、`packages/coding-agent/examples`、`packages/coding-agent/npm-shrinkwrap.json`，以及要求该包使用 faux provider 做测试、避免真实 provider API 的说明。

从职责边界看，它大概率位于 monorepo 的中间层：上游会依赖 `packages/ai` 之类的模型抽象和 provider 能力，下游会被 CLI、TUI 或其他执行入口调用。它关心的核心问题不是“如何展示界面”，而是“一个编码任务如何被拆解、上下文化、执行、验证和汇报”。因此阅读这个目录时，应把它理解为 Pi 的 agent runtime，而不是普通工具函数集合。

这个目录还包含比较严格的测试和发布约束。仓库规则明确要求，涉及 `packages/coding-agent/test/suite/` 的测试应使用 `test/suite/harness.ts` 和 faux provider，不能调用真实模型服务； issue 级回归测试放在 `packages/coding-agent/test/suite/regressions/`，命名为 `<issue-number>-<short-slug>.test.ts`。这说明该包的行为很大一部分通过端到端式的 agent 场景测试来约束。

## 直接子目录地图

根据当前片段推断，`packages/coding-agent` 至少包含以下角色型目录：

`src` 是主体实现目录，预计放置 agent runtime、会话状态、工具调用、模型交互、任务规划、文件系统上下文读取、补丁应用、命令执行协调等代码。仓库规则还特别指出 `packages/*/src` 受 Node strip-only TypeScript 约束，说明这里的源码需要避免 `enum`、parameter properties、namespace 等需要额外 JS emit 的 TypeScript 语法。

`test` 是测试目录，其中最关键的是 `test/suite/`。这个 suite 不是普通单元测试集合，而是用于模拟 coding agent 行为的场景测试区域。`test/suite/harness.ts` 是主要测试夹具入口，`test/suite/regressions/` 用于放 issue 级回归用例。阅读测试时优先看 harness，因为它通常能解释 agent 如何被实例化、输入如何喂入、工具调用如何伪造、输出如何断言。

`examples` 是示例目录。仓库规则把 `packages/coding-agent/examples` 也纳入 strip-only TypeScript 约束，说明示例可能不是文档片段，而是能被直接运行或类型检查的代码。它适合用来理解对外 API 的最小使用方式，以及 coding-agent 作为包被外部调用时的预期形态。

`scripts` 根据当前片段推断用于包内构建、打包或发布辅助。仓库规则提到 `packages/coding-agent/npm-shrinkwrap.json` 需要通过根部 `scripts/generate-coding-agent-shrinkwrap.mjs` 生成或校验，说明该包可能有独立发布、可执行分发或依赖冻结需求。

此外，包根部应有 `package.json`、可能有 `CHANGELOG.md`、`npm-shrinkwrap.json`、TypeScript 配置或测试配置。`CHANGELOG.md` 需要在 `## [Unreleased]` 下维护变更；`npm-shrinkwrap.json` 是发布和依赖安全的一部分，不能手工随意改。

## 关键入口

第一类入口是包级入口，通常在 `package.json` 的 `exports`、`bin`、`main` 或 `types` 字段中声明。阅读时应先确认这些字段指向 `src` 下哪些文件，因为这决定了外部包真正依赖的公共 API。若存在 `bin`，说明 `coding-agent` 可能也能直接提供可执行命令；若只有 `exports`，它更可能是被 `agent`、`tui` 或 CLI 包调用的库。

第二类入口是运行时入口，预计位于 `src` 下负责创建 agent、启动会话或处理一次任务请求的模块。命名可能包含 `agent`、`coding-agent`、`session`、`run`、`runner`、`task`、`orchestrator` 等。这个入口通常会串起模型 provider、上下文收集、工具注册、消息循环、结果输出几个部分。

第三类入口是测试入口，即 `test/suite/harness.ts`。对于学习代码来说，它经常比正式入口更直观，因为 harness 会显式构造假模型、假工具、临时工作区和断言流程。尤其当正式入口依赖外部 CLI 或复杂上下文时，测试夹具能展示最小闭环。

第四类入口是示例入口，即 `examples` 下的可运行示例。示例适合回答“这个包对外怎么用”，但不一定能覆盖所有内部机制。建议把示例和测试结合看：示例看公开用法，测试看边界行为和异常路径。

## 主流程位置

主流程可以按“输入任务到产出结果”理解。根据当前片段推断，`packages/coding-agent` 的主流程大致分为以下阶段。

第一阶段是任务接收和会话初始化。入口会拿到用户 prompt、当前工作目录、模型配置、权限配置、可用工具列表和已有上下文。这里通常会创建一个 agent session 或 run context，用于保存消息历史、工具结果、状态变更和最终输出。

第二阶段是上下文收集。coding agent 需要读取文件、搜索代码、理解仓库规则和目标范围。这个阶段会涉及文件系统访问、`rg` 风格搜索、目录扫描、可能还有对 `AGENTS.md` 或类似规则文件的加载。主流程中与“上下文预算”“路径过滤”“只读/可写权限”相关的代码通常也在这里。

第三阶段是模型循环。agent 会把任务、上下文、工具说明和历史消息交给模型，由模型决定下一步是回复、调用工具、请求更多信息，还是生成补丁。这个循环是最核心的位置：它决定了工具调用如何被解析，调用结果如何回灌给模型，错误如何重试，以及何时判定任务完成。

第四阶段是工具执行。coding-agent 的工具通常包括 shell 命令、文件读取、补丁应用、测试运行、计划更新等。工具层既要实现能力，也要执行安全策略，例如只读限制、禁止破坏性 git 命令、测试命令约束、网络限制、审批策略等。这里是行为风险最高的区域，读代码时要特别关注权限模型和错误处理。

第五阶段是验证和收尾。代码修改任务一般会运行类型检查或指定测试，并把结果汇总为最终答复。仓库规则要求代码变更后运行 `npm run check`，测试文件变更后运行对应测试；虽然当前任务不修改代码，但这说明 coding-agent 的常规流程需要把“验证是否完成”当作一等环节。

## 推荐阅读顺序

建议先读 `packages/coding-agent/package.json`。重点看包名、入口、脚本、依赖和对内 workspace 依赖。它能快速回答这个包是库、命令、还是两者兼有。

第二步读 `packages/coding-agent/README.md` 或包内说明文件。如果存在，这通常是最省力的全局地图；如果不存在，就直接看 `examples`，用示例反推公开 API。

第三步读 `test/suite/harness.ts`。这是理解 coding-agent 行为闭环的关键：它会展示如何创建 agent、如何注入 faux provider、如何设置临时仓库、如何模拟工具调用、如何判断输出正确。

第四步读 `test/suite/regressions/` 中少量最近或命名清晰的回归用例。不要逐个展开所有测试，挑能代表真实 bug 的用例看即可。回归测试通常能揭示主流程中最容易出错的边界：权限、上下文遗漏、工具失败、模型输出格式异常、并发修改、git 状态污染等。

第五步回到 `src`，沿着 package 入口进入运行时主线。优先找创建 agent、运行任务、处理模型响应、执行工具的模块。阅读时按调用链走，不要从工具函数或类型定义开始，否则容易陷入细节。

第六步再看 `scripts` 和 `npm-shrinkwrap.json` 相关逻辑。它们属于发布和分发层，理解主流程后再看更合适。

## 常见误区

第一个误区是把 `packages/coding-agent` 当成 UI 层。它虽然服务于交互式编码体验，但核心职责不是渲染界面，而是驱动 agent 完成编码任务。界面层更可能在 CLI、TUI 或其他 package 中。

第二个误区是只看 `src`，不看 `test/suite/harness.ts`。这个包的很多真实约束来自 agent 行为测试，尤其是 faux provider 如何模拟模型、工具调用如何断言、回归用例如何描述 bug。跳过测试会导致只理解静态结构，不理解运行语义。

第三个误区是随意运行完整测试。仓库规则明确提醒不要直接运行完整 vitest suite，因为 e2e 测试可能在存在 endpoint 或 auth 环境变量时触发真实服务。非 e2e 测试使用根目录 `./test.sh`，特定测试从包根运行 `node ../../node_modules/vitest/dist/cli.js --run test/specific.test.ts`。

第四个误区是把 `npm-shrinkwrap.json` 当成普通 lockfile 手改。该文件与 coding-agent 的发布包依赖冻结有关，需要通过指定脚本生成或校验；新增带 lifecycle scripts 的依赖还需要显式审查和 allowlist。

第五个误区是在源码中使用非 erasable TypeScript 语法。`packages/coding-agent/src`、`packages/coding-agent/test`、`packages/coding-agent/examples` 都受根配置约束，应避免 `enum`、parameter properties、namespace、`import =`、`export =` 等需要编译擦除以外处理的语法。

第六个误区是为了修类型错误而降级或移除依赖功能。仓库规则明确要求不能通过移除或降级代码来适配过旧依赖；如果外部 API 类型不确定，应查看 `node_modules` 中的真实类型，而不是猜测。
