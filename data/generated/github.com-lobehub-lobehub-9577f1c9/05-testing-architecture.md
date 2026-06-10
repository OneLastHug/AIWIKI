# LobeHub 自动化测试体系架构设计

这篇文档把 LobeHub 的自动化测试体系视为一个工程质量基础设施，而不是简单的“多写几个测试用例”。LobeHub 是一个复杂 monorepo：前端包含 Next.js、React、SPA 路由、Zustand 状态管理和丰富的业务 UI；后端包含 tRPC、server services、任务调度、模型运行时、文档与文件处理；共享层又分布在 `packages/*`、`apps/*` 和 `e2e/` 中。测试体系的设计目标，是用可分层、可渐进、可在 CI 中稳定运行的方式保护核心路径。

## 总体目标

自动化测试体系首先要解决四件事：第一，防止核心功能回归，例如会话、模型调用、任务调度、插件执行、文件处理、数据库读写等主路径；第二，降低大型重构风险，尤其是 `src/server`、`src/routes`、`src/store`、`packages/*` 之间的边界变化；第三，提高 PR 反馈速度，让本地开发能快速跑相关测试，让 CI 分层执行；第四，形成长期可维护的测试规范，让团队知道测试该放在哪里、什么改动必须补测试、什么检查应该在本地跑、什么检查应该交给 CI。

这套体系不追求一开始把全仓库覆盖率堆满，而是先保护架构边界、核心状态、服务编排和用户主路径。对于 LobeHub 这种复杂项目，测试最怕两种极端：一种是没有测试，重构全靠肉眼；另一种是一上来平均铺开，写出大量低价值、易碎、维护成本高的测试。更合适的路径是先建立测试分层，再按风险优先级逐步补齐。

## 测试分层

推荐使用五层结构：静态检查、单元测试、集成测试、契约测试、E2E / Smoke 测试。

静态检查是第一道门，主要包含类型检查、ESLint、stylelint 和循环依赖检查。它们速度快、反馈直接，应该在所有测试之前运行。LobeHub 已有 `type-check`、`lint:ts`、`lint:style`、`lint:circular` 等命令，这些不需要重新发明，只需要在 CI 中拆成清晰 job。

单元测试使用 Vitest，负责保护纯逻辑和局部状态。适合覆盖 formatter、parser、mapper、Zustand store action、selector、配置解析、权限判断、provider adapter 中不触网的转换逻辑。单元测试应该靠近源码，可以使用 `*.test.ts`、`*.test.tsx` 或 `__tests__/`，但需要统一规范。

集成测试关注多个模块协作，例如 tRPC router 加 service、server service 加 repository、database schema 加 repository、queue 加 task scheduler、model runtime 加 provider adapter。集成测试不应该真实调用外部模型或外部云服务，网络、provider、OAuth、远端存储都需要 mock 或 fake 实现。

契约测试专门保护边界稳定。LobeHub 的边界很多：前端调用后端、tRPC router、provider adapter、数据库 schema、plugin/tool runtime、Electron 与 Web 层、CLI 与服务端。契约测试的价值不是覆盖完整业务，而是保证接口形状、输入输出结构、错误格式和关键导出不在重构中悄悄断掉。

E2E / Smoke 测试使用现有 Playwright / Cucumber 体系。E2E 不应该承担所有业务细节验证，只负责主路径和白屏风险。PR 阶段跑少量 smoke，主分支或 nightly 再跑完整 E2E。

## 建议目录结构

测试文件不必全部集中在根目录，应该遵循“源码附近放单元测试，跨模块放 `tests/`，package 自治测试放 package 内部，E2E 放 `e2e/`”的原则。

推荐结构如下：

```text
src/**/*.test.ts
src/**/*.test.tsx
src/**/__tests__/*
packages/*/src/**/*.test.ts
packages/*/tests/**/*.test.ts
tests/integration/**/*.test.ts
tests/contracts/**/*.test.ts
e2e/**/*.spec.ts
e2e/**/*.feature
```

对于通用测试工具，可以新增：

```text
tests/utils/render.tsx
tests/utils/createTestStore.ts
tests/utils/createMockRouter.ts
tests/utils/createMockProvider.ts
tests/mocks/providers/fakeProvider.ts
tests/mocks/fixtures/
```

这些工具目录的目标是让测试写法统一，避免每个模块自己临时 mock 一套环境。

## `src/spa` 与路由测试

`src/spa` 是 SPA 入口和 router config 的核心区域。LobeHub 的开发约定里已经强调，`desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 必须保持同步，否则可能出现某个构建路径白屏。因此这里最值得先做结构性测试。

建议测试点包括：desktop、mobile、popup router 是否能加载；route path 是否重复；关键路径是否存在；desktop 两份 router config 的路径集合是否一致；lazy component 是否能 resolve。这里的测试不需要关心每个页面细节，重点是防止路由树断裂。

推荐建立或完善：

```text
src/spa/router/desktopRouter.sync.test.tsx
src/spa/router/mobileRouter.smoke.test.tsx
src/spa/router/popupRouter.smoke.test.tsx
```

## `src/routes` 边界测试

`src/routes` 应该是薄路由层，只放 `_layout/index.tsx`、`index.tsx`、`page.tsx` 和动态 segment 入口。业务逻辑和复杂 UI 应该放在 `src/features/*`。测试体系应该把这个约定变成自动检查，而不是只靠代码评审记忆。

建议新增一个静态边界检查脚本，例如 `scripts/check-route-boundaries.ts`。它可以检查 `src/routes` 下文件是否过长、是否直接引入 server service、是否出现复杂 business hooks、是否在 routes 内部新建了 feature-like 业务目录。这个脚本可以接入 CI 的 static job，作为架构边界保护。

这类测试的价值很高，因为它不是验证某个按钮是否能点，而是防止项目结构慢慢失控。

## `src/features` 测试

`src/features` 是业务 UI 和交互逻辑所在地。这里不建议对每个展示组件平均铺测试，而应按业务风险分层。

P0 级别包括 Chat、AgentTasks、ModelSwitchPanel、SkillStore、Provider settings、File upload / parsing status。它们应该至少有 smoke render、关键交互、loading/error 状态和主要分支测试。

P1 级别包括 CommandMenu、UserMemory、Session、Search 等重要但非所有请求都经过的功能。P2 级别的纯展示组件不强制覆盖率，只在存在复杂条件渲染或历史回归时补测试。

前端测试建议使用 Vitest、React Testing Library 和统一 render helper。网络请求通过 MSW 或 spy 方式模拟，避免测试真实服务。

## `src/store` 测试

Zustand store 是 LobeHub 中非常高价值的测试对象。store action、selector、slice 组合、持久化初始化、reset/clear 行为都很容易在重构中被破坏。

建议优先覆盖：

```text
src/store/chat
src/store/session
src/store/task
src/store/tool
src/store/userMemory
src/store/serverConfig
```

测试原则是：每个测试重建 store 初始状态；外部 service 全部 mock；只测试状态变化和 action 行为，不测试 UI；异步 action 要覆盖 loading、success、error 三种状态。这样可以用较低成本保护大量业务逻辑。

## `src/server` 测试

`src/server` 是后端服务、router 和 server-side workflow 的核心。这里建议分成单元、集成和契约三类。

单元测试覆盖 service 内部逻辑，例如 global config、task scheduler、queue service、document service、agent runtime hooks。集成测试覆盖 router + service、service + repository、scheduler + queue 等协作。契约测试覆盖 tRPC router 暴露的方法、参数 schema、返回结构和错误格式。

优先模块包括：

```text
src/server/globalConfig
src/server/routers
src/server/services/agentRuntime
src/server/services/taskScheduler
src/server/services/document
src/server/services/toolExecution
src/server/services/queue
```

这里尤其要避免真实调用模型 provider、OAuth、远端存储或外部 crawler。测试应该使用 fake provider、fake queue、fixture 文件和测试数据库。

## `packages/*` 测试

`packages/*` 是 monorepo 的复用层，应该比普通 UI 层更重视契约稳定性。优先级建议如下。

P0：

```text
packages/model-runtime
packages/agent-runtime
packages/database
packages/tool-runtime
packages/file-loaders
packages/openapi
```

P1：

```text
packages/prompts
packages/fetch-sse
packages/ssrf-safe-fetch
packages/web-crawler
packages/shared-tool-ui
```

P2：

```text
types
const
utils
```

package 内部应能独立跑测试。provider adapter 必须使用 fake 网络响应；database 测试分成 repository 单元测试和真实测试库集成测试；utils 类 package 可以追求更高覆盖率，因为这类测试成本低且稳定。

## Apps 测试策略

`apps/desktop` 不建议一开始铺大量 E2E。更现实的做法是先测主进程逻辑、IPC handler、配置管理、local file bridge、preload 暴露 API 契约。最后再补少量 desktop smoke：应用能启动、主窗口能加载、基础路由不白屏。

`apps/cli` 的测试重点是命令解析、参数校验、stdout/stderr、exit code、配置文件读写和网络请求 mock。可以使用临时目录和 fixture，确保每个测试隔离。

`apps/device-gateway` 如果承担设备通信或本地服务桥接，需要重点测试协议边界、错误恢复、重连和配置加载，但不应在普通单测里依赖真实设备。

## Mock 与测试数据

测试体系必须建立统一 mock 规范。真实外部服务一律不进自动化测试，包括模型 provider、OAuth、crawler、remote storage、支付、第三方 API。

推荐 mock 层：

```text
tests/mocks/server.ts
tests/mocks/providers/
tests/mocks/fixtures/
```

单元测试优先使用 `vi.spyOn`，因为 LobeHub 本身也建议优先 spy 而不是全量 mock。集成测试可以使用 MSW 或 fake server。provider contract 可以使用 fake streaming provider、fake error provider 和 fake timeout provider 覆盖正常流、错误流、超时流。

数据库测试建议分两档。repository 单元测试 mock db client，验证 query builder 和参数；集成测试使用测试数据库，每个测试独立 transaction 或测试后 truncate。CI 中可以使用 service container。

## CI 流水线设计

CI 不应该只有一个巨大的 `npm run test`。建议拆成多个 job。

PR 快速检查：

```text
ci-static
ci-unit-affected
ci-contract-core
ci-e2e-smoke
```

`ci-static` 运行类型检查、TS lint 和循环依赖检查。`ci-unit-affected` 只跑受影响测试，可以基于 git diff、turbo affected、pnpm filter 或自定义脚本。`ci-contract-core` 固定跑核心契约测试。`ci-e2e-smoke` 跑少量主路径。

canary/main 分支检查：

```text
ci-static
ci-unit-all
ci-integration
ci-e2e-smoke
ci-build
```

nightly 全量检查：

```text
full unit
full integration
full e2e
coverage report
dependency audit
flaky report
```

这样 PR 反馈可以保持较快，慢测试交给主分支和 nightly。

## 推荐命令规范

LobeHub 已有测试命令，但可以整理成更清晰的用户入口。

建议保留本地快速测试习惯：

```bash
bunx vitest run --silent='passed-only' <具体测试文件>
```

不建议开发者随手运行全量 `test`，因为大型仓库全量测试会很慢。可以增加或整理：

```text
test:unit
test:unit:watch
test:integration
test:contracts
test:e2e:smoke
test:e2e
test:changed
test:ci
```

其中 `test:changed` 是最值得做的开发体验增强：根据变更文件找相关测试，减少开发者手动猜命令的成本。

## 覆盖率策略

覆盖率不应该一刀切。建议按风险分层。

P0 核心模块目标 80% 以上，包括 model-runtime、agent-runtime、database repository、server routers、task scheduler、queue service、tool execution、auth/session、store/chat、store/session。

P1 重要模块目标 60% 以上，包括关键 features、file-loaders、web-crawler、provider settings、SkillStore、CommandMenu。

P2 展示层不强制覆盖率，只要求关键页面 smoke、核心交互和不白屏。

更重要的是 coverage diff，而不是全仓库数字。PR 改了核心逻辑却没有新增相关测试，比全仓库覆盖率低几个点更值得警惕。

## Flaky Test 治理

复杂前端项目一定会遇到 flaky test。治理策略应该提前设计。

规则包括：单测禁止依赖真实时间，使用 fake timers；E2E 禁止固定 sleep，使用 locator wait；CI 对 E2E 可以 retry，但 retry 成功也要记录；长期 flaky case 必须标记 owner 和治理期限；nightly 生成 flaky report，统计失败次数、重试成功率和所属模块。

E2E 的价值是发现主路径断裂，不是制造噪音。如果某条 E2E 长期不稳定，要么降级成集成测试，要么重写等待条件，要么拆成更小的 smoke case。

## 测试准入规则

建议在 PR 规范里明确：以下改动必须补测试或说明已有测试覆盖。

```text
修改核心 store action
修改 server service
修改 tRPC router
修改 provider adapter
修改数据库 schema/repository
修改 task scheduler/queue
修改文件解析逻辑
修复 bug
修改关键路由配置
```

以下改动可以不补测试，但仍需跑相关检查：

```text
文案
纯样式
README
icon
类型名称微调
无逻辑展示组件
```

如果纯样式改动影响关键页面，至少跑 smoke E2E。

## 落地路线

第一阶段先写测试策略文档和命令规范，不大改代码。新增 `docs/testing/strategy.md`、`docs/testing/running-tests.md`、`docs/testing/writing-tests.md`，把测试分层、命名、mock、CI、准入规则写清楚。

第二阶段建立核心契约测试。优先做 provider contract、tRPC router contract、desktop router sync test。这一阶段用较低成本保护架构边界。

第三阶段补核心 store 和 server 单测。优先 `src/store/chat`、`src/store/session`、`src/store/task`、`src/server/globalConfig`、`src/server/services/taskScheduler`。这些测试能快速降低重构风险。

第四阶段补 package 测试。优先 `packages/model-runtime`、`packages/agent-runtime`、`packages/database`、`packages/file-loaders`。package 是复用层，测试收益高。

第五阶段建立 E2E smoke。设计 5 到 10 条稳定主路径：首页可打开、onboarding 可进入、主会话页不白屏、设置页可打开、provider 配置页可打开、任务页可打开、SkillStore 可打开、模型切换面板可打开。

第六阶段优化 CI。把 PR、canary/main、nightly 三类流水线分开，避免慢测试拖垮开发反馈。

## 第一批建议任务

第一批可以按这个顺序落地：

```text
1. 新增 docs/testing/strategy.md
2. 新增 docs/testing/running-tests.md
3. 新增 docs/testing/writing-tests.md
4. 新增 tests/utils/render.tsx
5. 新增 tests/mocks/providers/fakeProvider.ts
6. 完善 src/spa/router/desktopRouter.sync.test.tsx
7. 新增 tests/contracts/provider-contract.test.ts
8. 选择 src/store/session 做 store 测试样板
9. 选择 src/server/globalConfig 做 server service 测试样板
10. 调整 CI，把 static、unit、contracts、e2e-smoke 拆开
```

这批任务的重点不是追求数量，而是建立模式：以后补测试时能照着同一套写法扩展。

## 结论

LobeHub 的自动化测试体系应该是分层质量网，而不是一个全量测试大命令。静态检查守基础质量，单元测试守局部逻辑，集成测试守模块协作，契约测试守边界稳定，E2E smoke 守用户主路径，nightly 全量测试守长期健康。

最优先的不是铺满所有文件，而是保护最容易出事故的地方：路由同步、核心 store、server service、provider adapter、database repository、task scheduler 和主用户路径。这样才能用可控成本，把测试体系变成长期可靠的工程资产。
