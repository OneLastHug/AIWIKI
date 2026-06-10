# 目录：src/commands/onboarding

## 它负责什么

`src/commands/onboarding` 负责实现交互式 REPL 里的 `/onboarding` 斜杠命令。它不是首启 onboarding 流程本体，而是给已经进入 Claude Code 交互界面的用户提供一个“重新触发或查看 onboarding 相关状态”的入口。

从代码结构看，这个目录的职责主要有三类：

第一，声明 `/onboarding` 命令的元信息，包括命令名、描述、参数提示、是否隐藏、是否可用、是否 bridge-safe，以及按需加载真正执行逻辑。这个声明位于 `src/commands/onboarding/index.ts`。

第二，实现 `/onboarding` 的子命令分发。`src/commands/onboarding/launchOnboarding.tsx` 支持 `full`、`theme`、`trust`、`model`、`mcp`、`status` 等子命令，也把空参数和 `reset` 归一化为 `full`。

第三，把 onboarding 相关的配置开关写回全局或项目配置。例如 `full` 会把全局配置里的 `hasCompletedOnboarding` 改成 `false`，让下一次启动时走真正的首启设置流程；`trust` 会把当前项目的 `hasTrustDialogAccepted` 改成 `false`，让下一次启动重新显示信任确认。

这个目录的定位更接近“onboarding 控制台入口”或“onboarding 维护命令”，而不是完整的新用户引导 UI。完整的首启 UI 在 `src/components/Onboarding.tsx`，启动时机由 `src/interactiveHelpers.tsx` 的 `showSetupScreens()` 控制。

## 直接子目录地图

`src/commands/onboarding` 下面只有一个直接子目录：

`src/commands/onboarding/__tests__`：存放 `/onboarding` 命令的单元测试。测试覆盖命令元信息、子命令解析、`callOnboarding` 对不同参数的行为、状态展示、配置写入，以及未知参数处理。它用于保证这个目录作为斜杠命令入口的行为稳定。

目录根部有两个源码文件：

`src/commands/onboarding/index.ts`：命令注册文件，导出默认的 `Command` 对象。它只负责描述 `/onboarding` 这个命令，并通过 `load()` 动态 import `./launchOnboarding.js`，避免在命令声明阶段加载完整 JSX/UI 实现。

`src/commands/onboarding/launchOnboarding.tsx`：命令执行文件，包含参数解析、各子命令的具体逻辑、内联 `ThemePicker` 渲染、状态展示组件，以及对全局/项目配置的更新。

## 关键入口

最外层入口是 `src/commands/onboarding/index.ts` 里的默认导出 `onboarding`。这个对象的关键字段包括：

`type: 'local-jsx'`：说明它是本地 JSX 命令，需要在本地 Ink 交互 UI 中运行。

`name: 'onboarding'`：对应用户输入的 `/onboarding`。

`argumentHint: '[full|theme|trust|model|mcp|status]'`：提示支持的子命令。

`bridgeSafe: false`：明确该命令不能在 bridge/remote 这类非本地交互环境中安全执行。原因是 onboarding 相关步骤依赖本地终端 UI、主题选择器、工作区信任确认等能力。

`load()`：动态加载 `src/commands/onboarding/launchOnboarding.tsx`，并返回 `callOnboarding` 作为实际调用函数。

真正的执行入口是 `launchOnboarding.tsx` 里的 `callOnboarding: LocalJSXCommandCall`。它接收 `onDone`、命令上下文和原始参数字符串，先调用 `parseSubcommand(args)` 解析子命令，然后记录 `tengu_onboarding_step` telemetry，再根据子命令分支执行不同逻辑。

参数解析入口是 `parseSubcommand(args)`。它把参数 trim 后转小写，规则很直接：空字符串和 `reset` 都视为 `full`；合法子命令直接返回；未知参数返回 `{ sub: 'full', unknownArg }`，后续由 `callOnboarding` 输出错误信息并停止执行。

## 主流程位置

`/onboarding` 命令本身的主流程在 `src/commands/onboarding/launchOnboarding.tsx` 的 `callOnboarding` 中。

流程可以概括为：

用户在 REPL 输入 `/onboarding ...` 后，命令系统根据 `src/commands/onboarding/index.ts` 的声明加载 `launchOnboarding.tsx`。`callOnboarding` 首先解析参数，然后记录一次 `tengu_onboarding_step` 事件。如果参数未知，直接通过 `onDone()` 输出合法参数列表。

如果子命令是 `theme`，它返回一个 JSX 节点 `<ThemeSubcommand />`。该组件用 `@anthropic/ink` 的 `useTheme()` 获取主题更新函数，并渲染 `src/components/ThemePicker.js`。用户选中主题后，组件调用 `setTheme(setting)`，记录 `theme` 事件，再通过 `onDone()` 结束命令。

如果子命令是 `trust`，它调用 `saveCurrentProjectConfig()`，把当前项目配置里的 `hasTrustDialogAccepted` 置为 `false`。这不会立即弹出信任对话框，而是提示用户下一次 `claude` 启动时会重新确认。

如果子命令是 `model`，它不直接打开模型选择器，而是提示用户运行 `/model`。代码注释说明 onboarding 不拥有 model picker，当前入口主要是为了 discoverability。

如果子命令是 `mcp`，它也不进入 MCP 子系统执行复杂交互，只输出 MCP 设置提示，包括 `/mcp`、`claude mcp add <name> <command>`、`claude mcp remove <name>`，以及 `.mcp.json` 和全局配置的加载来源。

如果子命令是 `status`，它读取 `getGlobalConfig()`，渲染 `StatusView`，展示当前 theme、`hasCompletedOnboarding`、`lastOnboardingVersion`。

如果子命令是 `full`，它调用 `saveGlobalConfig()` 把 `hasCompletedOnboarding` 改为 `false`，然后输出说明：完整首启设置会在下一次 `claude` 启动时运行。这里有一个重要设计点：它不会在当前 REPL 中直接挂载完整 `<Onboarding />`。注释说明完整 onboarding 拥有 terminal setup detection、OAuth flow、最终跳转到 prompt 等流程，不适合在活跃 REPL 会话中间强行挂载。

真正完整的首启流程在 `src/interactiveHelpers.tsx` 的 `showSetupScreens()`。该函数读取 `getGlobalConfig()`，当 `theme` 缺失或 `hasCompletedOnboarding` 不是 true 时，动态 import `src/components/Onboarding.js` 并通过 `showSetupDialog()` 渲染 `<Onboarding />`。用户完成后调用 `completeOnboarding()`，把 `hasCompletedOnboarding` 设为 `true`，并把 `lastOnboardingVersion` 写成 `MACRO.VERSION`。

`showSetupScreens()` 的调用位置在 `src/main.tsx` 的交互式启动路径中。它在 Ink root 创建之后、正式进入 REPL 之前运行。若 onboarding 刚刚完成，`src/main.tsx` 后续还会刷新 auth 相关服务、策略限制、GrowthBook 和 remote control 可信设备状态。

## 推荐阅读顺序

建议先读 `src/commands/onboarding/index.ts`。这个文件很短，可以快速建立命令的外部形态：它是 `/onboarding`，类型是 `local-jsx`，不支持 bridge，执行逻辑按需加载。

第二步读 `src/commands/onboarding/launchOnboarding.tsx` 的顶部注释和 `OnboardingSubcommand`。这里直接列出了这个目录支持的功能边界，也解释了哪些子命令是真执行，哪些只是提示或延迟到下次启动。

第三步读 `parseSubcommand()` 和 `callOnboarding()`。这是目录内最核心的流程。重点看每个分支对配置的影响：`theme` 是当前会话内联 UI，`trust` 是项目配置，`status` 是全局配置读取，`full` 是全局 onboarding 完成标记重置。

第四步跳到 `src/interactiveHelpers.tsx`，阅读 `completeOnboarding()`、`showSetupDialog()`、`showSetupScreens()`。这里能理解为什么 `/onboarding full` 只清标记、不直接渲染完整 onboarding：完整首启流程是在启动阶段集中处理的。

第五步看 `src/main.tsx` 中调用 `showSetupScreens()` 的启动片段。它能帮助理解 onboarding 与 auth、trust、GrowthBook、remote control 等后续初始化之间的顺序关系。

最后再看 `src/commands/onboarding/__tests__/onboarding.test.tsx`。测试适合作为行为清单使用，不需要逐行研究，但可以确认边界条件，比如 `reset` 等价于 `full`、未知参数如何处理、`bridgeSafe` 期望为 false。

## 常见误区

一个常见误区是把 `src/commands/onboarding` 当成完整 onboarding UI。实际上完整 UI 是 `src/components/Onboarding.tsx`，这个目录只是 REPL 里的 `/onboarding` 命令入口。它负责重置标记、提示用户、展示状态，以及在 `theme` 子命令中内联渲染主题选择器。

第二个误区是认为 `/onboarding full` 会立即重跑首启向导。代码明确没有这么做。`full` 只是把 `hasCompletedOnboarding` 置为 `false`，完整流程要等下一次启动时由 `showSetupScreens()` 判断并渲染。

第三个误区是把 `trust` 当成当前会话立刻弹窗。`trust` 只修改当前项目配置里的 `hasTrustDialogAccepted`，提示下一次启动时重新显示 TrustDialog。真正的信任对话框仍在 `showSetupScreens()` 中统一处理。

第四个误区是认为 `model` 和 `mcp` 子命令会代理执行 `/model` 或 `mcp` 命令。当前实现只是输出提示文字；根据当前片段推断，这样设计是为了避免在一个 local JSX 命令内部再切换到另一个复杂交互命令，依据是 `model` 分支中的说明文字和 `full` 分支注释中对“不能在活跃 REPL 中安全挂载完整流程”的解释。

第五个误区是忽略 `bridgeSafe: false`。onboarding 依赖本地终端和 Ink UI，不适合 remote/bridge 环境；如果从桥接环境调用，命令声明会返回专门的错误说明。
