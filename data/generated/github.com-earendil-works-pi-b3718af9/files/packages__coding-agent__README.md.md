# 文件：packages/coding-agent/README.md

## 一句话定位

`packages/coding-agent/README.md` 是 `@earendil-works/pi-coding-agent` 包的主入口说明文档，用面向用户的方式解释 Pi 这个终端编码代理的安装、认证、交互模式、会话管理、自定义扩展、程序化使用和 CLI 参数；它不是实现文件，而是把 `packages/coding-agent` 的主要能力组织成一张产品级地图。

## 它暴露/定义了什么

这个文件暴露的是包的使用契约，而不是 TypeScript API。核心内容包括：全局安装方式、`pi` 命令的启动方式、内置工具模型、交互式 TUI 的组成、编辑器操作、斜杠命令、快捷键、消息队列、会话恢复与分支、配置文件、`AGENTS.md` 上下文文件、自定义能力体系，以及 print、JSON、RPC、SDK 等运行模式。

从 `package.json` 看，真正对外暴露的 npm 入口是 `dist/index.js` 和二进制命令 `dist/cli.js`，README 则解释这些入口在用户层面的行为。文档还定义了大量约定名称，例如 `/login`、`/model`、`/settings`、`/resume`、`/tree`、`/compact`、`/share`、`~/.pi/agent/settings.json`、`~/.pi/agent/sessions/` 等，这些名称会成为用户、测试和第三方扩展依赖的稳定界面。

## 谁调用它

严格来说，没有运行时代码“调用” README。它主要被三类对象消费：npm 包页面和发布产物读取它作为包说明；终端用户、贡献者和扩展作者把它当作总览文档；仓库内其他 docs 页面、示例和测试根据它描述的行为保持一致。

根据当前片段推断，发布流程也会间接依赖它：`package.json` 的 `copy-binary-assets` 会把 `README.md` 复制到 `dist/`，`files` 字段也把文档和 `docs` 纳入发布包，因此 README 是 npm/binary 分发的一部分，而不只是仓库说明。

## 它调用谁

README 本身不调用代码，但它引用并组织了多个下游文档和模块能力。相邻文档包括 `packages/coding-agent/docs/providers.md`、`docs/models.md`、`docs/custom-provider.md`、`docs/keybindings.md`、`docs/settings.md`、`docs/session-format.md`、`docs/extensions.md`、`docs/skills.md`、`docs/prompt-templates.md`、`docs/themes.md`、`docs/rpc.md`、`docs/sdk.md` 等。

从包结构看，它描述的能力主要落到 `packages/coding-agent/src/cli.ts`、`src/main.ts`、`src/modes/print-mode.ts`、`src/core/agent-session.ts`、`src/core/session-manager.ts`、`src/core/model-registry.ts`、`src/core/settings-manager.ts`、`src/core/skills.ts`、`src/core/prompt-templates.ts`、`src/core/package-manager.ts`、`src/core/sdk.ts`、`src/modes/interactive/*` 这些实现区域。它还依赖工作区包 `@earendil-works/pi-agent-core`、`@earendil-works/pi-ai`、`@earendil-works/pi-tui` 提供代理核心、模型接入和终端 UI 能力。

## 核心流程

用户路径从安装开始：通过 npm 或安装脚本获得 `pi` 命令，然后用 API key 或 `/login` 完成认证。启动后，默认进入 interactive mode，模型获得 `read`、`write`、`edit`、`bash` 四类基础工具，围绕当前工作目录执行读写、编辑和命令操作。

交互模式中，用户在底部编辑器输入自然语言、文件引用、斜杠命令或 shell 命令；TUI 展示消息、工具调用、结果、错误、状态栏和模型信息。用户可以通过 `/model` 切换模型，通过 `/settings` 调整思考级别、主题和传输方式，通过快捷键处理取消、折叠输出、切换模型等高频操作。

会话层面，消息被保存为 JSONL 树结构，支持恢复、分支、克隆、fork 和 compact。上下文层面，Pi 会读取项目里的 `AGENTS.md`，再加载用户安装的 skills、prompt templates、extensions 和 themes。扩展层面，第三方包可以注册命令、工具、UI、模型或 provider，从而把 README 中的“可定制编码代理”落到实际插件机制。

## 关键函数的高层作用

这个 README 不定义函数。与它最相关的关键入口可以按职责理解：`src/cli.ts` 负责把命令行参数、模式选择和启动参数接到运行时；`src/main.ts` 是普通 Node CLI 的启动汇合点；`src/bun/cli.ts` 面向编译后的 Bun 二进制入口；`src/core/agent-session.ts` 负责单个代理会话的消息、工具调用、模型流式响应和状态推进；`src/core/session-manager.ts` 负责会话文件、恢复、分支和元数据；`src/core/model-registry.ts`、`src/core/model-resolver.ts` 负责 provider/model 列表和选择；`src/core/settings-manager.ts` 管理用户配置；`src/core/skills.ts`、`src/core/prompt-templates.ts`、`src/core/package-manager.ts` 分别对应 README 中的 skills、模板和 Pi Packages。

辅助模块如 `src/utils/clipboard.ts`、`src/utils/image-resize.ts`、`src/utils/git.ts`、`src/utils/syntax-highlight.ts` 支撑具体体验细节，不是 README 的主叙事中心。

## 修改风险

README 是用户入口和发布包内容，修改风险主要在“承诺漂移”。如果新增或删除命令、快捷键、配置路径、会话行为、provider 名称、安装参数，但实现没有同步，会直接误导用户，也可能让测试、示例和第三方扩展文档失配。

外部链接和徽章需要特别小心：最终文档或镜像环境可能要求隐藏真实网址；但仓库 README 中这些链接会影响 npm 页面、社区入口和安装指引。修改安装命令、认证说明、默认工具列表、支持 provider 列表时风险更高，因为这些内容会影响新用户能否成功启动。修改自定义体系的术语也有兼容风险，例如 `Extensions`、`Skills`、`Prompt Templates`、`Themes`、`Pi Packages` 是贯穿 docs、examples、tests 和源码目录的概念，随意改名会制造跨文档断裂。
