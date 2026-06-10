# 目录：src/commands/help

## 它负责什么

`src/commands/help` 负责实现交互式 REPL 中的 `/help` 斜杠命令。它不是 Commander 层面的 `claude --help`，而是 Claude Code 进入会话后，用户在输入框中键入 `/help` 时打开的 Ink 帮助界面。

这个目录的职责很集中：声明一个名为 `help` 的内置命令，并在命令被调用时渲染 `HelpV2` 组件。实际帮助内容、Tab 布局、命令列表筛选、终端尺寸适配、关闭快捷键等 UI 逻辑并不在本目录内，而是在 `src/components/HelpV2/` 下实现。因此可以把 `src/commands/help` 理解为“命令注册壳 + UI 入口桥接”。

它展示的命令列表来自运行时传入的 `commands` 集合，而不是在本目录中硬编码。这一点很重要：`/help` 会看到当前环境下已经加载、通过 feature flag、鉴权条件、插件、skills、workflow 等过滤后的命令集合。

## 直接子目录地图

`src/commands/help` 当前没有直接子目录，只有两个文件：

`src/commands/help/index.ts`：命令元数据入口。声明命令类型、名称、描述和 lazy load 方式。

`src/commands/help/help.tsx`：命令执行入口。导出 `call`，把运行时上下文里的 `commands` 传给 `HelpV2`，并把关闭回调 `onDone` 传入 UI。

根据当前片段看，这个目录没有自己的状态管理、参数解析、测试文件或样式文件；它依赖全局命令系统与 `HelpV2` 组件完成主要行为。

## 关键入口

第一层入口是 `src/commands/help/index.ts`。它默认导出一个满足 `Command` 类型的对象：

`type: 'local-jsx'` 表示这是一个本地 JSX 命令，执行结果是 React/Ink 节点，而不是纯文本 prompt 或普通本地命令。

`name: 'help'` 表示用户输入 `/help` 会匹配到它。

`description: 'Show help and available commands'` 用于 typeahead、帮助列表或命令展示。

`load: () => import('./help.js')` 表示实现模块被懒加载，只有真正调用 `/help` 时才加载 `help.tsx`。

第二层入口是 `src/commands/help/help.tsx` 的 `call`。它的类型是 `LocalJSXCommandCall`，签名上接收 `onDone` 和上下文。这里从 `context.options.commands` 取到当前命令列表，然后返回：

`<HelpV2 commands={commands} onClose={onDone} />`

也就是说，本目录没有直接处理键盘事件、Tab 切换、命令排序或过滤，而是把控制权交给 `src/components/HelpV2/HelpV2.tsx`。

## 主流程位置

主流程可以按“注册、加载、渲染、关闭”理解。

注册阶段在 `src/commands.ts`。该文件 import `src/commands/help/index.ts`，并把 `help` 放入内置 `COMMANDS()` 数组。随后 `getCommands(cwd)` 会把内置命令、skills、插件命令、workflow 命令、动态 skills 等合并，并按 `availability`、`isEnabled()` 等条件过滤。`/help` 拿到的 `commands` 就来自这条命令加载链路。

调用阶段位于用户输入处理链路。根据当前片段推断，`src/utils/processUserInput/processSlashCommand.tsx` 负责解析和执行斜杠命令；依据是它导入了 `Command`、`getCommand`、`hasCommand`、`PromptCommand` 等命令工具，并承担 slash command 执行逻辑。对 `local-jsx` 类型命令，它会加载命令模块并将 React 节点交给 UI 层显示。

渲染阶段在 `src/components/HelpV2/HelpV2.tsx`。`HelpV2` 会读取终端尺寸，计算最大高度，注册关闭快捷键，并生成多个 Tab：`general`、`commands`、`custom-commands`，在 `USER_TYPE === 'ant'` 且有内部命令时还会显示 `[ant-only]`。它还会根据 `builtInCommandNames()` 区分内置命令和自定义命令，并过滤 `isHidden` 命令。

命令列表展示在 `src/components/HelpV2/Commands.tsx`。该组件会对命令按名称去重、排序，并使用 `formatDescriptionWithSource(cmd)` 生成描述。为了适配终端宽度，它会用 `truncate` 截断描述，并通过 `Select` 以只读列表形式展示命令。

关闭阶段由 `HelpV2` 内部的 `close` 回调完成。关闭时会调用 `onClose('Help dialog dismissed', { display: 'system' })`，也就是回到 `help.tsx` 传入的 `onDone`，由命令执行框架把结果作为系统显示处理。

## 推荐阅读顺序

先读 `src/commands/help/index.ts`，确认 `/help` 作为 `local-jsx` 命令如何注册，以及 lazy load 的边界在哪里。

再读 `src/commands/help/help.tsx`，理解这个目录真正做的事情只有一件：把 `commands` 和 `onDone` 接到 `HelpV2`。

然后读 `src/types/command.ts` 中的 `Command`、`LocalJSXCommandCall`、`LocalJSXCommandModule`、`CommandBase`。这些类型能解释为什么 `index.ts` 只需要声明元数据，为什么 `help.tsx` 需要导出 `call`。

接着读 `src/commands.ts`，重点看 `COMMANDS()`、`builtInCommandNames()`、`getCommands(cwd)`。这里能看懂 `/help` 的数据来源，以及为什么帮助页里会混合内置命令、自定义命令、插件命令和 skills。

最后读 `src/components/HelpV2/HelpV2.tsx` 和 `src/components/HelpV2/Commands.tsx`。前者负责整体帮助弹窗和 Tab，后者负责命令列表展示。若只做 overview，不需要深入 `General.tsx` 或 `CustomSelect` 的内部实现。

## 常见误区

第一个误区是把 `/help` 和 `claude --help` 混为一谈。`claude --help` 属于 CLI 参数帮助，主要由 `src/main.tsx` 中 Commander 配置控制；`src/commands/help` 实现的是会话内斜杠命令 `/help`。

第二个误区是以为帮助内容在 `src/commands/help` 中维护。实际上这里几乎不维护展示内容，真正的 UI 和内容组织在 `src/components/HelpV2/`，命令数据则来自 `src/commands.ts` 的运行时命令集合。

第三个误区是认为 `/help` 会列出所有源码里存在的命令。它展示的是当前可用命令：隐藏命令会被过滤，feature flag 未开启的命令不会进入集合，不满足鉴权或 provider 条件的命令也可能不可见，插件和 skills 则可能动态加入。

第四个误区是忽略 `local-jsx` 的执行模型。`/help` 不会生成 prompt 发给模型，也不是返回一段文本；它会渲染 Ink React 节点，因此它的主行为是 UI 交互，关闭后才通过 `onDone` 把“Help dialog dismissed”作为系统显示结果交回命令框架。

第五个误区是只看 `help.tsx` 就认为 `/help` 功能很简单。目录本身确实很薄，但它连接的是全局命令注册、动态命令加载、终端 UI、快捷键和隐藏/内部命令过滤等多条链路；理解它时应把它当作 HelpV2 的命令入口，而不是完整帮助系统本体。
