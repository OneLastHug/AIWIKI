# 目录：src/commands/skills

## 它负责什么

`src/commands/skills` 是内置斜杠命令 `/skills` 的命令入口目录，职责很窄：把“列出并选择当前可用 skills”的能力注册到全局命令系统，并在执行时渲染对应的 Ink UI。它本身不负责扫描磁盘、不解析 `SKILL.md`、不安装 skill、也不执行 skill 内容；这些能力分别分布在 `src/skills/loadSkillsDir.ts`、`src/commands/skill-store`、`src/utils/processUserInput/processSlashCommand.tsx` 等位置。

从形态看，`/skills` 是一个 `local-jsx` 命令。也就是说，用户输入 `/skills` 后，它不会生成 prompt 发给模型，而是在本地终端 UI 中打开一个可搜索的 `SkillsMenu`，展示当前命令上下文里的 skills，并允许用户选择某个 skill。选中后，菜单通过 `onDone` 返回 `/<skillName>`，后续仍走普通 slash command 处理链路。

这个目录更像“技能列表入口适配层”：它把全局 command registry 中已经加载好的 `commands` 传给 UI，由 UI 从中筛出 skill 类型命令并展示。

## 直接子目录地图

`src/commands/skills` 当前没有直接子目录，只有两个文件：

`src/commands/skills/index.ts`：命令声明文件，导出名为 `skills` 的 `Command` 对象。它定义命令类型为 `local-jsx`，命令名为 `skills`，描述为 `List available skills`，并通过 `load: () => import('./skills.js')` 延迟加载真正的 UI 执行模块。

`src/commands/skills/skills.tsx`：命令执行模块，导出 `call(onDone, context)`。它返回 React 节点 `<SkillsMenu onExit={onDone} commands={context.options.commands} />`，把命令完成回调和当前可用命令列表交给组件层。

因此，这个目录没有复杂的内部层级。真正的“地图”要顺着它指向的邻近模块看：`src/commands.ts` 注册 `/skills`，`src/components/skills/SkillsMenu.tsx` 负责展示，`src/skills/loadSkillsDir.ts` 负责 skill 来源加载。

## 关键入口

最直接的入口是 `src/commands/skills/index.ts`。它的默认导出会被 `src/commands.ts` 以 `import skills from './commands/skills/index.js'` 引入，并放入 `COMMANDS()` 的内置命令数组中。全局命令加载时，`getCommands(cwd)` 会把 built-in commands、磁盘 skills、bundled skills、plugin skills、workflow commands 等合并成一个命令列表，`/skills` 作为内置命令出现在这个列表里。

运行时入口是 `src/commands/skills/skills.tsx` 的 `call` 函数。`local-jsx` 类型命令在 slash command 处理流程中会动态加载模块并渲染返回的 React 节点。这里的关键点是：`call` 没有重新读取文件系统，而是依赖 `context.options.commands`。这意味着 `/skills` 展示的是当前会话已经解析出的命令视图，而不是自己重新构建 skill 索引。

UI 入口是 `src/components/skills/SkillsMenu.tsx`。它从传入的 `commands` 中筛选 `cmd.type === 'prompt'` 且 `loadedFrom` 属于 `skills`、`commands_DEPRECATED`、`plugin`、`mcp` 的命令，然后按来源分组、排序、支持搜索过滤，并显示大致 token 估算。选择某个条目时，它调用 `onExit(\`/${getCommandName(skill)}\`, { display: 'user' })`，相当于把用户选择转换成新的斜杠命令输入。

## 主流程位置

主流程可以按“注册、打开、选择、执行”四段理解。

注册阶段在 `src/commands.ts`。`skills` 被加入 `COMMANDS()`，而 `getCommands(cwd)` 会调用 `loadAllCommands(cwd)` 合并多类命令源。skill 类命令主要来自 `getSkillDirCommands(cwd)`、`getPluginSkills()`、`getBundledSkills()`、`getBuiltinPluginSkillCommands()`，动态 skill 还会从 `getDynamicSkills()` 插入。`/skills` 本身只是其中一个内置 `local-jsx` 命令。

打开阶段在用户输入 `/skills` 后触发。输入解析主要在 `src/utils/slashCommandParsing.ts` 和 `src/utils/processUserInput/processSlashCommand.tsx`。`processSlashCommand` 会检查命令是否存在，然后根据命令类型分发。对于 `local-jsx` 命令，会加载对应模块，让 Ink 渲染本地交互界面。`src/commands/skills/index.ts` 的 `load()` 就是在这里发挥作用。

展示阶段在 `src/components/skills/SkillsMenu.tsx`。该组件会过滤出 prompt 型 skill 命令，展示来源标签和 token 估算。来源顺序由 `ORDERED_SOURCES` 控制，大致包括 `projectSettings`、`localSettings`、`userSettings`、`flagSettings`、`policySettings`、`plugin`、`mcp`。如果没有 skill，它会提示用户在 `.claude/skills/` 或 `~/.claude/skills/` 创建 skill。

选择阶段仍回到 slash command 机制。用户在菜单中选中某个 skill 后，`SkillsMenu` 返回形如 `/commit`、`/some-skill` 的文本。这个文本后续会按普通 slash command 继续处理。真正执行 skill prompt 的逻辑在 `src/skills/loadSkillsDir.ts` 创建的 `PromptCommand.getPromptForCommand()`，以及 `src/utils/processUserInput/processSlashCommand.tsx` 的 prompt command 处理分支中。

## 推荐阅读顺序

第一步读 `src/commands/skills/index.ts`。它只有命令元数据和 lazy load 声明，能快速确认 `/skills` 的命令类型是 `local-jsx`，不是 prompt command。

第二步读 `src/commands/skills/skills.tsx`。这里能看到 `/skills` 本体只是把 `context.options.commands` 交给 `SkillsMenu`，没有额外业务逻辑。

第三步读 `src/components/skills/SkillsMenu.tsx`。这是理解用户看到什么的核心位置：筛选规则、来源分组、搜索、空状态、选择后的返回值都在这里。

第四步读 `src/commands.ts` 中的 `COMMANDS()`、`getSkills()`、`loadAllCommands()`、`getCommands()`。这部分解释 `/skills` 为什么能拿到完整的 skill 列表，以及 bundled、plugin、磁盘、本地动态 skill 如何进入同一个命令数组。

第五步按需读 `src/skills/loadSkillsDir.ts`。如果只做 overview，不需要逐行读完；重点看 `getSkillDirCommands()`、`loadSkillsFromSkillsDir()`、`createSkillCommand()`，即可理解 `.claude/skills/<name>/SKILL.md` 如何变成 `Command`。

第六步再看 `src/utils/processUserInput/processSlashCommand.tsx`。这能串起用户从 `/skills` 菜单选择某个 skill 后，如何进入真正的 slash command 执行流程。

## 常见误区

一个常见误区是把 `src/commands/skills` 当成 skill 加载器。实际上它只是 `/skills` 菜单命令入口；磁盘扫描、frontmatter 解析、路径去重、动态发现都在 `src/skills/loadSkillsDir.ts`。

另一个误区是把 `/skills` 和 `src/commands/skill-store` 混为一谈。`/skills` 是本地列出并选择已有 skills；`skill-store` 更像远端 skill 商店相关功能，涉及 API、安装、版本等概念，两者目录相邻但职责不同。

还容易误解的是 `/skills` 选中条目后并不是直接执行 React 组件里的逻辑。`SkillsMenu` 只是返回 `/<skillName>`，真正的 skill 执行仍然走 slash command 管线，包括参数解析、权限、模型调用与可能的 fork agent 流程。

最后，`SkillsMenu` 展示的 skill 范围和 `SkillTool` 可供模型调用的范围并不完全等价。UI 里主要筛选 `loadedFrom` 为 `skills`、legacy commands、plugin、mcp 的 prompt commands；而模型可调用列表还会受 `disableModelInvocation`、`hasUserSpecifiedDescription`、`whenToUse`、bundled skill 等规则影响，相关过滤在 `src/commands.ts` 的 `getSkillToolCommands()` 和 `getSlashCommandToolSkills()` 中。
