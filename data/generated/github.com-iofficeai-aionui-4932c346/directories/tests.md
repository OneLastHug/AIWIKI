# 目录：tests

## 它负责什么

`tests` 是这个仓库的测试总入口，覆盖三类不同粒度的验证：`unit` 负责模块级逻辑，`integration` 负责跨模块或真实 fixture 的组合验证，`e2e` 负责把 Electron 应用真正跑起来，从 UI 到后端链路做端到端检查。根据当前片段推断，它不是单一测试框架的“测试目录”，而是整个项目的测试编排层，既包含 Vitest 的 Node/jsdom 测试，也包含 Playwright + Electron 的 E2E 测试，还有少量测试专用 fixtures 和说明文档。

从结构上看，这个目录的职责很清楚：一边是快速、密集、可并行跑的逻辑测试，另一边是启动真实应用后验证用户行为的高成本测试。`tests` 目录就是把这两种测试组织到同一套约定里，并通过顶层脚本和配置文件接起来。

## 直接子目录地图

- `tests/unit`：体量最大的单测区，按业务域再切分成 `common`、`renderer`、`preview`、`conversation`、`extension`、`skills`、`workspace`、`cron`、`bootstrap` 等子目录。整体上是“按模块归档”，而不是按测试技术分类。
- `tests/integration`：放跨模块集成测试。当前可见的文件显示它会使用真实 fixture 或较重的协作路径，粒度比单测更大，但仍低于 E2E。
- `tests/e2e`：Playwright + Electron 的端到端测试区，是最接近真实用户操作的部分。
- `tests/fixtures`：测试专用假实现与替身资源，例如 `fake-acp-cli`、`fake-extension`，用来把外部依赖隔离掉。
- `tests/e2e/helpers`：E2E 的共用工具层，提供导航、断言、选择器、桥接调用、截图等能力。
- `tests/e2e/specs`：主 E2E 用例集合，面向应用的核心功能场景。
- `tests/e2e/cases`：更细的专题用例分组，目前能看到 `teams` 这类功能簇。
- `tests/e2e/features`：按功能域再拆的场景集，通常比 `specs` 更强调流程化用例。
- `tests/e2e/docs`：E2E 用例设计文档和讨论记录，偏规范和方案说明，不是执行入口。
- `tests/unit/_helpers`：单测共用辅助代码，承载 mock、桥接层替身这类基础设施。

## 关键入口

- `tests/vitest.setup.ts`：Vitest 的 Node 环境全局准备文件。这里会注册平台服务并注入 `electronAPI` 的 mock，保证依赖平台能力的模块可以在纯 Node 环境下跑。
- `tests/vitest.dom.setup.ts`：Vitest 的 jsdom 环境准备文件。除了 `electronAPI` mock，还补了 `ResizeObserver`、`IntersectionObserver`、`requestAnimationFrame`、`localStorage` 等浏览器能力，主要服务 React 组件和 hook 测试。
- `vitest.config.ts`：虽然不在 `tests` 目录下，但它决定了 `tests/unit/**/*.test.ts`、`tests/unit/**/*.dom.test.tsx`、`tests/integration/**/*.test.ts` 的扫描范围，以及 Node/jsdom 两个 Vitest project 的分流方式。
- `tests/e2e/fixtures.ts`：E2E 的核心启动器。它负责启动 Electron、解析主窗口、复用单例 app、在失败时附加截图。这里就是 E2E 的实际运行底座。
- `tests/e2e/helpers/index.ts`：E2E 工具总出口，通常测试文件不会直接深挖到具体 helper，而是统一从这里导入。
- `tests/e2e/specs/README.md`：团队场景的规范文档，说明这类测试如何走真实 UI 链路、哪些操作必须通过聊天框而不是测试桥接触发。
- `package.json` 里的 `test`、`test:e2e`、`test:integration`、`test:e2e:team:*`：这是从命令行进入 `tests` 目录各测试分区的主要入口。

## 主流程位置

主流程可以理解成两条线。

第一条是 Vitest 线。`package.json` 里的 `test` 会触发 `vitest run`，然后由 `vitest.config.ts` 把 `tests/unit`、`tests/integration` 按环境拆成两个 project：Node 项走 `tests/vitest.setup.ts`，jsdom 项走 `tests/vitest.dom.setup.ts`。这条线的特点是快、稳定、易定位回归，适合验证纯逻辑、转换函数、状态管理、UI hook 和组件行为。

第二条是 E2E 线。`package.json` 里的 `test:e2e` 会走 Playwright 配置，真正进入 `tests/e2e/fixtures.ts` 启动 Electron 应用，再通过 `tests/e2e/helpers` 和具体的 `tests/e2e/specs`、`tests/e2e/cases`、`tests/e2e/features` 去驱动 UI。这里的关键不是单个文件，而是这条链路的分工：`fixtures.ts` 负责“把应用跑起来并保持住”，helpers 负责“把重复动作封装掉”，specs/features/cases 负责“描述业务场景”。

还有一条比较轻的支线是 `tests/integration`。从命名和脚本看，它介于单测与 E2E 之间，通常用来验证真实数据流、迁移、兼容性或依赖协作的边界。根据当前片段推断，它更像“回归型集成测试层”，不是 UI 主线。

## 推荐阅读顺序

1. 先看 `package.json` 的测试脚本，确认有哪些测试分区，以及每个脚本对应的执行方式。
2. 再看 `vitest.config.ts`，搞清楚 `unit`、`integration`、`dom` 三者是怎样被 Vitest 分流的。
3. 接着看 `tests/vitest.setup.ts` 和 `tests/vitest.dom.setup.ts`，理解测试环境里补了哪些平台能力。
4. 然后看 `tests/e2e/fixtures.ts`，这是端到端测试真正的启动器和共享窗口管理层。
5. 再看 `tests/e2e/helpers/index.ts` 及其子 helper，理解 E2E 是怎么把导航、断言、桥接和选择器收束成统一 API 的。
6. 最后进入 `tests/e2e/specs`、`tests/e2e/cases`、`tests/e2e/features`，按功能场景去读具体用例。
7. 如果关注团队场景，优先看 `tests/e2e/specs/README.md`，它定义了这类测试的业务约束和写法边界。

## 常见误区

- 把 `tests/e2e` 当成“纯 Playwright 页面测试”来读，忽略了它其实是 Electron 应用测试；真正的入口在 `tests/e2e/fixtures.ts`，不是浏览器页面本身。
- 误以为 E2E 可以直接测源码状态。这里的 E2E 依赖 `out/` 里的构建产物，源代码变更后通常要先 rebuild，不然测到的是旧产物。
- 在 E2E 里把 `invokeBridge` 当成用户操作入口。`tests/e2e/specs/README.md` 明确强调它只适合 setup、读取和断言，不应拿来代替真实 UI 交互。
- 混淆 Vitest 的 Node 环境和 jsdom 环境。`tests/vitest.setup.ts` 与 `tests/vitest.dom.setup.ts` 的补丁不同，前者偏平台 mock，后者偏浏览器 API mock。
- 认为所有测试都应该放在 `unit`。这个目录的设计明显是分层的：快速逻辑测试、集成回归、真实 UI 流程各自承担不同职责。
- 把 `tests/e2e/docs` 当成可执行测试。它们更像规范、方案和讨论沉淀，适合用来理解测试设计，而不是直接跑。
- 在 `tests/e2e` 里频繁重启应用。`fixtures.ts` 的设计就是单 worker 复用一个 Electron 实例，避免每个 describe 都重启导致测试成本暴涨。
