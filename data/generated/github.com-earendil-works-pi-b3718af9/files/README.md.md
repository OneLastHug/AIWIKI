# 文件：README.md

## 一句话定位

`README.md` 是整个 `pi-mono` 仓库的入口说明页，用来向新用户、贡献者和维护者概览 Pi Agent Harness 的项目定位、包结构、安全边界、开发命令和供应链策略；它不是运行时代码，而是仓库级导航与约束说明。

## 它暴露/定义了什么

这个文件主要暴露五类信息。第一是项目身份：`Pi Agent Harness Mono Repo`，说明仓库包含一个可自扩展的 coding agent 体系。第二是包边界：`packages/ai` 提供多 provider LLM API，`packages/agent` 提供 agent runtime、tool calling 和状态管理，`packages/coding-agent` 提供交互式 CLI，`packages/tui` 提供终端 UI 渲染能力。第三是安全定位：Pi 默认不内置 filesystem、process、network、credential 级别的权限隔离，而是继承启动进程权限；需要强隔离时应使用容器或沙箱。第四是开发入口：`npm install --ignore-scripts`、`npm run build`、`npm run check`、`./test.sh`、`./pi-test.sh`。第五是供应链硬化规则：依赖精确锁定、`package-lock.json` 作为事实来源、发布包包含 `packages/coding-agent/npm-shrinkwrap.json`、CI 使用 `npm ci --ignore-scripts`，并通过检查阻止未经审查的生命周期脚本依赖进入发布链路。

## 谁调用它

严格说，`README.md` 不被 TypeScript/Node 运行时代码调用。它的“调用者”是阅读和展示系统：代码托管平台会把它作为仓库首页渲染，npm 或其他包浏览场景可能间接引用它的项目说明，贡献者会用它找到开发命令和贡献入口，维护者会用它向新 issue/PR 参与者解释项目边界。根据当前片段推断，AI coding agent 也会把它作为仓库背景材料之一，因为文件明确指向 `AGENTS.md`，并提示贡献者查看项目特定规则。

## 它调用谁

作为 Markdown 文档，它不执行调用，但它引用并组织了多个下游文档和目录。仓库内重点引用 `CONTRIBUTING.md`、`AGENTS.md`、`packages/coding-agent/docs/containerization.md`、`packages/coding-agent`、`packages/agent`、`packages/ai`、`packages/tui`。仓库外部链接包括项目站点、文档站、社区、聊天自动化仓库、session 发布工具、Hugging Face 数据集和 X 帖子；这些在本文档中统一视为外部说明入口，具体地址不展开，记为 `[URL已移除]`。

## 核心流程

读者进入仓库后，README 的信息流是先建立项目品牌和贡献准入提醒，再说明 monorepo 的核心目标：Pi 是 agent harness 项目，包含 CLI、agent runtime 和 LLM API。随后它引导读者了解开源 coding agent session 的共享背景，这是项目数据与社区协作层面的补充。接着进入 `All Packages`，把 monorepo 拆成清晰的模块地图。然后是 `Permissions & Containerization`，提前澄清安全边界，避免用户误以为 CLI 自带强权限控制。最后进入贡献、开发、供应链和许可证信息，为本地开发、审查依赖、发布前验证提供路线。

## 关键函数的高层作用

`README.md` 没有函数、类或可执行模块，因此不存在传统意义上的关键函数。可以把其中的命令视为关键操作入口：`npm install --ignore-scripts` 负责安全安装依赖；`npm run build` 负责构建所有 package；`npm run check` 负责 lint、format 和 type check，并承载依赖固定、导入兼容性、shrinkwrap 生成校验等质量门禁；`./test.sh` 负责运行测试并跳过缺少 API key 的 LLM 相关测试；`./pi-test.sh` 用源码直接启动 Pi，便于本地验证 CLI 行为。辅助链接如 `CONTRIBUTING.md` 和 `AGENTS.md` 只承担规则跳转，不应被理解为运行链路的一部分。

## 修改风险

修改这个文件的主要风险不是破坏运行时，而是误导用户和维护流程。包描述如果与 `packages/*` 的真实职责不一致，会让新贡献者找错模块。开发命令如果过时，会造成安装、检查或测试方式偏离项目规则，尤其是 `--ignore-scripts`、`npm run check`、`./test.sh` 这类安全和质量入口。权限说明如果弱化，用户可能错误地把 Pi 当作自带沙箱的工具使用，带来 credential 或文件访问风险。供应链段落如果删除或写得含糊，会削弱项目对锁文件、生命周期脚本、shrinkwrap 和发布 smoke test 的审查意识。外部链接、徽章和图片变更风险较低，但会影响仓库首页可信度与导航体验。总体上，修改应优先保持 README 与 `CONTRIBUTING.md`、`AGENTS.md`、`package.json`、`packages/coding-agent/docs/containerization.md` 的一致性。
