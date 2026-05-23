# 目录：e2e

## 它负责什么

`e2e` 是仓库的端到端测试工程，负责用 `Cucumber + Playwright` 验证应用在真实浏览器里的关键用户路径。根据当前片段推断，它不是业务源码的一部分，而是一个独立的测试工作区：通过 Gherkin `.feature` 文件描述场景，再由 TypeScript 步骤实现具体操作，最后驱动浏览器访问本地或指定的 `BASE_URL`。

这个目录的定位很明确：覆盖社区页、首页、页面编辑、路线跳转、Agent 交互等跨层流程，重点验证“页面能不能跑通”和“核心交互是否退化”。

## 直接子目录地图

- `e2e/src/features/`：测试用例声明区，按业务域分组。当前可见的主域有 `community`、`home`、`journeys`、`page`、`routes`。
- `e2e/src/steps/`：步骤定义实现区，和 `features` 一一对应。可见子域有 `agent`、`common`、`community`、`home`、`page`、`routes`。
- `e2e/src/support/`：测试基础设施和上下文封装，放 `world.ts`、`webServer.ts`、`seedTestUser.ts` 这类共用能力。
- `e2e/src/mocks/`：接口和数据模拟层，当前能看到 `community`、`llm` 两类 mock。
- `e2e/docs/`：测试工程说明文档，包含本地接入、LLM mock、调试提示等。
- `e2e/scripts/`：辅助脚本，当前能看到 `setup.ts`，通常用于测试环境准备。
- `e2e/README.md`、`e2e/CLAUDE.md`：工程说明与约束入口。
- `e2e/cucumber.config.js`：Cucumber 运行配置。
- `e2e/package.json`：测试脚本和依赖入口。

## 关键入口

- `e2e/package.json` 是命令入口，定义了 `test`、`test:ci`、`test:headed`、`test:routes`、`test:smoke`、`test:community` 等运行方式。
- `e2e/cucumber.config.js` 是主配置入口，决定了 feature 搜索范围、步骤加载路径、并行度、超时、标签过滤和报告输出。
- `e2e/src/features/**/*.feature` 是场景入口，Cucumber 会从这里读取测试叙述。
- `e2e/src/steps/**/*.ts` 与 `e2e/src/support/**/*.ts` 是执行入口，前者实现场景动作，后者提供 World、服务启动、测试种子等支撑能力。
- `e2e/docs/local-setup.md` 和 `e2e/README.md` 是上手入口，说明如何连接本地开发服务、怎么安装浏览器、怎么跑测试。

## 主流程位置

主流程可以概括为：`package.json` 脚本启动 `cucumber-js`，`cucumber.config.js` 扫描 `src/features/**/*.feature`，再加载 `src/steps/**/*.ts` 和 `src/support/**/*.ts`。执行时，步骤文件通过 `@cucumber/cucumber` 绑定 Given/When/Then，`support/world.ts` 提供共享上下文，`support/webServer.ts` 负责测试期间的站点连接或启动逻辑，`mocks/` 则在需要时替换后端或 LLM 行为。

按目录看，最常见的主链路是：
`src/features/<domain>/*.feature` → `src/steps/<domain>/*.steps.ts` → `src/support/world.ts` / `webServer.ts` → 浏览器页面与接口交互。

从当前文件名看，`community`、`home`、`page`、`routes`、`journeys/agent` 是主要测试流，说明这里既有页面级冒烟，也有更细的编辑器与 Agent 交互验证。

## 推荐阅读顺序

1. 先看 `e2e/package.json`，了解有哪些测试命令和覆盖范围。
2. 再看 `e2e/cucumber.config.js`，建立对扫描范围、标签、报告、超时的整体认知。
3. 接着看 `e2e/README.md` 和 `e2e/docs/local-setup.md`，确认本地运行前提。
4. 然后看 `e2e/src/support/world.ts`、`webServer.ts`、`seedTestUser.ts`，理解测试上下文怎么搭起来。
5. 最后按业务域读 `src/features/` 和 `src/steps/` 的配对文件，从一个场景追到实现。

## 常见误区

- 把 `e2e` 当成应用源码目录。它是测试工程，不是产品功能实现地。
- 只看 `.feature` 不看 `src/steps/`。真正的页面操作、断言和等待逻辑都在步骤里。
- 忽略 `src/support/`。很多稳定性问题其实出在 World、服务连接、测试数据初始化，而不是场景本身。
- 误以为所有测试都走同一套入口。`package.json` 里已经按 `smoke`、`routes`、`community` 等拆了不同运行面。
- 忽略 `BASE_URL`、`PORT`、`HEADLESS` 这类环境变量。README 明确说明了测试会依赖开发服务地址，默认是 `[URL已移除]
- 只盯着 README 里的示例目录名。当前片段里真实可见的目录重点是 `community`、`home`、`journeys`、`page`、`routes`，README 中的 `discover` 示例更像历史示意。
