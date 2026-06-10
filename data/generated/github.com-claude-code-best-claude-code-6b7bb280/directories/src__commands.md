# 目录：src/commands

## 它负责什么

根据当前片段推断，`src/commands` 是这个 CLI/TUI 项目的“命令层”聚合目录：这里放的是用户在终端里直接调用的各类命令、面板、向导和诊断入口。它既包含真正执行逻辑的实现文件，也包含每个命令的注册描述、参数解析和视图入口。

这个目录的定位不是单一业务模块，而是一个“命令注册仓库”。从 `src/commands.ts` 可以看出，上层会把这里的大量命令统一收集成一个 `Command[]` 注册表，再按条件、特性开关和运行环境决定哪些命令可见。另一个共用层是 `src/commands/_shared/launchCommand.ts`，它把很多本地 JSX 命令的参数解析、异常处理、`onDone` 回调和渲染流程收拢成统一模板。

## 直接子目录地图

`src/commands` 的直接子目录很多，规模已经接近“命令全集”而不是普通功能模块。按角色看，主要可以分成几类：

- 基础交互与会话类：`login`、`logout`、`resume`、`status`、`session`、`context`、`help`、`model`、`usage`、`output-style`、`permissions`、`theme`、`vim`、`skills`、`skill-search`、`skill-store`、`local-memory`、`local-vault`、`vault`、`schedule`
- 自动化与工作流类：`autofix-pr`、`branch`、`commit`、`commit-push-pr`、`fork`、`claim-main`、`send`、`attach`、`detach`、`pipes`、`pipe-status`、`history`、`rewind`、`summary`、`recap`、`tasks`、`workflows`
- 集成与外部系统类：`mcp`、`plugin`、`bridge`、`remoteControlServer`、`chrome`、`mobile`、`desktop`、`terminalSetup`、`onboarding`、`install-github-app`、`install-slack-app`
- 调试与诊断类：`doctor`、`debug-tool-call`、`heapdump`、`break-cache`、`perf-issue`、`security-review`、`reset-limits`、`mock-limits`、`backfill-sessions`
- 其他工具面板类：`agents`、`agents-platform`、`assistant`、`tui`、`plan`、`review`、`thinkback`、`thinkback-play`、`launchers` 这类带 UI 或半交互流程的命令目录

另外，目录下也有不少“直接文件型命令”，例如 `commit.ts`、`init.ts`、`bridge-kick.ts`、`version.ts`、`autonomy.ts`、`advisor.ts`、`provider.ts`、`statusline.tsx`、`install.tsx`。也就是说，这里并不要求每个命令都必须放在子目录里。

## 关键入口

最关键的总入口是 `src/commands.ts`。它负责把各个命令模块汇总成统一注册表，并按 feature flag、环境变量和运行模式决定是否加载某些命令。这里能看到两种很典型的入口形态：

- 静态导入：常规命令在模块初始化时就被收集进去
- 条件加载：一部分命令通过 `feature('XXX') ? require(...) : null` 懒加载，说明它们只在特定能力打开时才进入命令集合

第二层入口是每个子目录里的 `index.ts` 或 `index.tsx`。从 `src/commands/plugin/index.tsx`、`src/commands/mcp/index.ts` 这类文件可以看出，它们通常只是返回一个标准 `Command` 对象，描述命令名、别名、说明和 `load()` 回调，真正实现延迟到同目录下的主文件。

第三层是 `src/commands/_shared/launchCommand.ts`。它不是单个业务命令，而是一个通用命令工厂，很多 `launch*`、`parseArgs`、`View` 组合型命令会复用它来减少样板代码。

## 主流程位置

如果只看“命令如何被执行”，主流程其实分三层：

1. `src/entrypoints/cli.tsx` 决定是否直接进入某个快速路径，或者进入完整 CLI
2. `src/main.tsx` 负责解析命令、查找命令、校验环境和路由执行
3. `src/commands.ts` 提供命令集合，`findCommand()` 会在这里面做匹配

从当前片段能确认，`src/main.tsx` 会显式引用部分命令注册辅助函数，例如 `src/commands/mcp/addCommand.js`、`src/commands/mcp/xaaIdpCommand.js`，说明有些命令不只是静态列表，还会在主程序中被单独挂接。`src/commands.ts` 内部则通过 `memoize()` 延迟构建命令数组，并把 `INTERNAL_ONLY_COMMANDS`、feature-gated 命令和普通命令合并成最终集合。

简化理解就是：`src/commands` 提供“有哪些命令”和“每个命令怎么长”，`src/main.tsx` 决定“用户输入后先走哪条路”，`src/commands/_shared/launchCommand.ts` 统一“命令内部怎么跑”。

## 推荐阅读顺序

1. 先看 `src/commands.ts`，建立整体命令地图，先知道这里有哪些大类和哪些是条件命令
2. 再看 `src/commands/_shared/launchCommand.ts`，理解本目录里大量 JSX 命令的通用执行模型
3. 选 2 到 3 个代表性目录看 `index.ts`，比如 `mcp`、`plugin`、`context`，把“命令描述对象”这个模式看实
4. 最后回到 `src/main.tsx`，看命令如何被检索、校验并转入实际执行

## 常见误区

- 不要把 `src/commands` 当成“纯业务目录”。它更像命令注册层，很多文件只是入口描述，不是完整业务实现。
- 不要假设所有子目录都会进默认构建。`src/commands.ts` 里有大量 feature flag 条件，某些目录在当前构建里可能根本不加载。
- 不要忽略顶层 `.ts` / `.tsx` 文件。这里不少命令并不在子目录里，而是直接放在 `src/commands/*.ts`。
- 不要把 `index.ts` 看成业务主体。很多 `index` 文件只负责导出 `Command` 元数据，真正的逻辑通常在同目录下的主实现文件里。
- 不要把命令名和实现路径一一硬绑定。这里存在别名、懒加载和历史兼容入口，例如某些命令在注册表里是别名或包装器，而不是唯一实现。
