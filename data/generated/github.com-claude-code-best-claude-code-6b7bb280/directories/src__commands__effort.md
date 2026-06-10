# 目录：src/commands/effort

## 它负责什么
这个目录实现的是 Claude Code 里的 `/effort` 命令，也就是“推理力度 / effort level”的交互入口。它负责让用户在运行中的会话里查看、设置、清空 effort，并把这个选择同步到当前会话状态或用户设置里。

根据当前片段推断，这里是一个很小的命令目录，职责很集中：只处理 effort 命令本身，不负责 effort 级别的底层判定逻辑。真正的 effort 规则、默认值、描述文案与解析函数，主要在 `src/utils/effort.ts`。

## 直接子目录地图
我在 `src/commands/effort` 下只看到两个文件，没有更深层的子目录。

- `index.ts`：命令定义入口，向命令系统暴露 `/effort`
- `effort.tsx`：命令的实际执行与 JSX 生命周期处理

这意味着这个目录不是“组件树”式结构，而是一个典型的“命令定义 + 命令执行器”组合。

## 关键入口
- `src/commands/effort/index.ts`：命令元数据入口。这里把命令声明成 `type: 'local-jsx'`，名字是 `effort`，并通过 `load: () => import('./effort.js')` 懒加载真正实现。
- `src/commands/effort/effort.tsx`：命令执行入口。这里导出了 `call`，这是 `/effort` 真正被调用时走的主函数。
- `src/commands.ts`：全局命令注册表里把 `effort` 挂进了 `COMMANDS` 数组，所以它会作为内建命令出现在系统里。
- `src/main.tsx`：还提供了会话启动参数 `--effort <level>`，这是另一个入口，但它属于启动期参数，不是 `/effort` 命令本身。

## 主流程位置
主流程基本都集中在 `src/commands/effort/effort.tsx`：

1. `call()` 先清理参数，识别 `help`、`-h`、`--help`。
2. 如果用户输入空参数、`current` 或 `status`，就走 `ShowCurrentEffort`，读取当前 app state 和当前模型，返回“当前 effort”说明。
3. 如果输入的是具体值，就走 `executeEffort(args)`。
4. `executeEffort()` 负责分流：
   - `auto` / `unset` -> `unsetEffortLevel()`
   - 合法 effort 值 -> `setEffortValue()`
   - 非法值 -> 返回错误提示
5. `setEffortValue()` 和 `unsetEffortLevel()` 会调用 `updateSettingsForSource('userSettings', ...)`，把 effort 写进用户设置；同时还会 `logEvent('tengu_effort_command', ...)` 做埋点。
6. `ApplyEffortAndClose` 会把结果回写到 `AppState`，让当前会话立即生效。
7. `showCurrentEffort()` 则负责把当前显示值、环境变量覆盖和模型默认值拼成用户能读懂的消息。

这里有一个很重要的分层：  
命令目录只负责“用户操作的入口和状态回写”，真正的 effort 计算与展示规则在 `src/utils/effort.ts`，持久化在 `src/utils/settings/settings.js`。

## 推荐阅读顺序
- 先看 `src/commands/effort/index.ts`，理解这个命令是怎么被系统挂载的。
- 再看 `src/commands/effort/effort.tsx`，重点盯 `call()`、`executeEffort()`、`setEffortValue()`、`unsetEffortLevel()`、`showCurrentEffort()`。
- 然后看 `src/utils/effort.ts`，补齐 effort 值、描述文案、默认策略和环境变量解析。
- 接着看 `src/commands.ts`，确认它在整套命令体系中的位置。
- 最后看 `src/main.tsx` 里 `--effort` 的参数定义，分清“启动参数”和“交互命令”的区别。

## 常见误区
- `/effort` 不是只改当前一轮，它可能会写入 `userSettings`，所以它有持续性，不只是临时开关。
- `auto` 和 `unset` 在命令层都能清空设置，但如果环境变量 `CLAUDE_CODE_EFFORT_LEVEL` 已经固定了值，命令提示里会说明它仍然会覆盖本次会话。
- `src/main.tsx` 的 `--effort` 和 `/effort` 不是同一个入口。前者是启动参数，后者是运行时命令。
- 命令帮助里提到的 `xhigh`，在这个目录的实际命令实现里是支持的；但 `src/main.tsx` 的 `--effort` 参数校验只接受 `low`、`medium`、`high`、`max`，两者范围并不完全一致。
- 这里没有测试文件，不代表功能简单，只能说明这一层更偏命令胶水层，核心逻辑被下沉到别的模块了。
