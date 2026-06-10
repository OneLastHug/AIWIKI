# 目录：packages/tui

## 它负责什么

`packages/tui` 是仓库中的终端用户界面层。根据当前片段可确认，仓库采用 `packages/agent`、`packages/ai`、`packages/coding-agent`、`packages/tui` 这样的多包结构；其中 `packages/tui` 与 AI 模型封装、Agent 运行逻辑、Coding Agent 业务逻辑分离，职责更接近“把交互式命令行体验渲染出来并接收用户输入”。

从包名和仓库规则中关于 “Testing pi Interactive Mode with tmux” 的说明推断，`packages/tui` 很可能承载 `pi` 交互模式的终端界面：包括输入框、消息列表、状态栏、快捷键、终端尺寸适配、流式输出展示、错误或中断状态展示等。它不应被理解为模型调用层，也不应被理解为 Coding Agent 的核心决策层；它更像是用户和底层运行时之间的交互外壳。

由于当前可读取证据只确认了目标目录存在和工作区包结构，下面对内部子目录与入口的说明属于“根据当前片段推断”。依据是：仓库根目录存在 `pi-test.sh`、`packages/coding-agent`、`packages/ai`、`packages/agent`、`packages/tui`，以及 `AGENTS.md` 中明确把交互模式称为 TUI 并要求用 tmux 验证。

## 直接子目录地图

根据当前片段推断，`packages/tui` 通常会按终端 UI 的职责拆成几类路径：

`src`：主源码目录，预计包含 TUI 应用组件、输入处理、状态管理、渲染适配和对外导出的入口。阅读这个目录时应先找 `index.ts`、`main.tsx`、`app.tsx`、`App.tsx` 这类入口文件，再顺着组件和 hooks 往下看。

`test` 或 `tests`：TUI 行为测试目录。仓库规则提到交互模式可用 tmux 进行人工验证，但包内仍可能有单元测试或快照测试，用来覆盖按键处理、文本换行、布局计算、状态转换等纯逻辑。

`dist`、`build` 或生成产物目录：如果存在，应视为构建输出，不是学习主线。除非排查发布问题，否则不要从这里理解源码。

`examples`：如果存在，通常用于展示 TUI 组件或交互模式的最小运行样例。它适合在理解入口之后补充阅读，不适合作为第一阅读对象。

`CHANGELOG.md`、`package.json`、`tsconfig.json`：这些不是子目录，但通常是理解包边界的关键文件。`package.json` 能确认包名、导出入口、依赖的 TUI 框架或终端库；`CHANGELOG.md` 能看出这个包近期变更集中在哪些交互行为上；`tsconfig.json` 能确认编译边界。

## 关键入口

优先寻找 `packages/tui/package.json`。它通常能回答三个问题：这个包对外暴露哪些模块、运行时依赖哪些终端 UI 库、是否有独立的开发或测试命令。对于学习文档来说，`exports`、`main`、`types`、`scripts`、`dependencies` 是最重要的字段。

源码入口预计在 `packages/tui/src/index.ts` 或相近文件。它很可能导出 TUI 的公共组件、启动函数或类型定义。这个入口用于说明 `packages/coding-agent` 或 CLI 层如何调用 TUI，而不是直接解释每个内部组件。

交互应用入口预计在 `packages/tui/src/app.tsx`、`packages/tui/src/App.tsx`、`packages/tui/src/main.tsx` 这类文件。这里通常是终端界面的根组件：接收外部会话状态、把消息流渲染成屏幕区域、把输入事件转换成提交、取消、编辑、历史切换等动作。

输入和快捷键入口可能位于 `packages/tui/src/input`、`packages/tui/src/keybindings` 或类似路径。仓库规则特别强调不要硬编码快捷键检查，而是放进 `DEFAULT_EDITOR_KEYBINDINGS` 或 `DEFAULT_APP_KEYBINDINGS`，因此 TUI 包大概率包含默认键位、按键匹配、编辑器行为或输入缓冲相关模块。

## 主流程位置

主流程可以按“启动、渲染、输入、状态回传”四段理解。

第一段是启动流程。CLI 或上层 `coding-agent` 选择进入交互模式后，会调用 `packages/tui` 暴露的启动函数或根组件，将会话配置、模型列表、工作目录、初始消息、回调函数等传入。这个位置通常在 `packages/tui/src/index.ts` 和根组件附近。

第二段是渲染流程。TUI 根组件把会话状态拆成若干区域：历史消息区、当前模型响应区、输入区、状态栏、错误提示或确认弹窗。终端 UI 的难点不是单个组件，而是空间有限、宽度变化、流式文本更新和光标位置变化。因此主流程中很重要的一层会负责布局计算和文本折行。

第三段是输入流程。用户在交互模式中输入 prompt、使用方向键或快捷键编辑、按下提交键、触发取消或退出。输入模块把原始 key event 转换成语义动作，例如 submit、cancel、newline、historyPrevious、historyNext、openEditor。根据仓库规则推断，快捷键配置应集中在默认 keybindings 常量里，而不是散落在组件判断中。

第四段是回传流程。TUI 不应直接承担模型推理；它通常把用户动作通过回调交给 `packages/coding-agent` 或 `packages/agent`，再订阅后者产生的状态变化。模型流式输出、工具调用状态、错误信息、完成状态再反向进入 TUI，触发重新渲染。

## 推荐阅读顺序

1. 先读 `packages/tui/package.json`，确认包名、导出入口、依赖和测试命令。这样可以先建立“这个包被谁消费、依赖什么 UI 技术”的边界。

2. 再读 `packages/tui/src/index.ts` 或同级入口文件，弄清对外 API。学习这个目录时不要从叶子组件开始，否则容易陷入布局细节。

3. 接着读根组件，例如 `packages/tui/src/App.tsx`、`packages/tui/src/app.tsx` 或类似文件。重点看传入 props、内部状态、子组件分区和事件回调，而不是每一行样式。

4. 然后读输入与快捷键相关路径，重点确认默认 keybindings、按键匹配和输入编辑状态如何组织。这部分通常是交互模式问题最容易出 bug 的地方。

5. 再读消息渲染、状态栏、错误展示、弹窗确认等组件。此时已经知道状态从哪里来、动作往哪里去，组件细节会更容易理解。

6. 最后读测试和 tmux 验证脚本相关说明。`pi-test.sh` 和仓库中关于 tmux 的说明更偏端到端验证，用来确认真实终端里的光标、换行、快捷键和流式刷新行为。

## 常见误区

不要把 `packages/tui` 当成模型调用层。模型列表、provider、token、请求流等核心逻辑更可能在 `packages/ai` 或 Agent 层；TUI 只是展示这些状态并收集用户操作。

不要把终端 UI 的布局问题当成普通 Web 页面问题。终端宽度、ANSI 控制、光标位置、换行、流式刷新都会影响行为，很多问题只能在真实 TTY 或 tmux 中复现。

不要在组件里临时硬编码快捷键。仓库规则已经明确要求默认键位应进入 `DEFAULT_EDITOR_KEYBINDINGS` 或 `DEFAULT_APP_KEYBINDINGS`，这样用户配置和测试都能共享同一套定义。

不要从构建产物或发布文件学习主流程。如果 `dist`、`build` 这类目录存在，它们只能帮助排查发布结果，不能替代 `src` 中的源码阅读。

不要把每个叶子组件都当成入口。overview 阶段只需要掌握包边界、根组件、输入事件、状态回传和渲染区域；具体组件可以在排查对应问题时再深入。

不要忽略 `packages/coding-agent` 与 `packages/tui` 的接口边界。交互模式的行为通常由二者共同形成：`coding-agent` 决定任务如何运行，`tui` 决定用户如何看到和操控这个过程。
