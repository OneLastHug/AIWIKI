# 目录：src/commands/tasks

## 它负责什么

`src/commands/tasks` 是一个很薄的命令包装目录，职责不是实现“任务系统”本身，而是把一个名为 `tasks` 的本地 JSX 命令接到 Claude Code 的命令注册体系里。根据当前片段推断，它对应的是“查看和管理后台任务”的入口，主要面对终端内的交互式面板，而不是纯文本输出。

这里要区分两个层次：

1. `src/commands/tasks` 负责“命令定义 + 入口调度”。
2. 真正的界面和任务列表展示，落在 `src/components/tasks/BackgroundTasksDialog.tsx` 及其相关组件里。

所以这个目录更像是一个路由器，作用是把 `/tasks` 这种命令映射到具体 UI，而不是承载业务规则。

## 直接子目录地图

这个目录下**没有直接子目录**。当前能看到的只有两个文件：

- `src/commands/tasks/index.ts`
- `src/commands/tasks/tasks.tsx`

这种结构说明它不是一个功能树，而是一个极小的命令入口封装层。它的所有职责都集中在这两个文件中，基本没有拆分出更细的辅助模块。

## 关键入口

最重要的入口是 `src/commands/tasks/index.ts`。这里定义了命令对象：

- `type: 'local-jsx'`，说明它不是普通文本命令，而是会渲染 Ink UI 的本地界面命令。
- `name: 'tasks'`，命令名就是 `tasks`。
- `aliases: ['bashes']`，说明它还有一个别名 `bashes`。
- `description: 'List and manage background tasks'`，可以直接看出它面向后台任务查看与管理。
- `load: () => import('./tasks.js')`，采用懒加载，真正执行时才加载渲染逻辑。

第二个入口是 `src/commands/tasks/tasks.tsx`。它导出 `call(onDone, context)`，并直接返回：

- `<BackgroundTasksDialog toolUseContext={context} onDone={onDone} />`

也就是说，这个文件只是把命令上下文转交给后台任务对话框组件，自己不做额外编排。

## 主流程位置

这条链路的主流程可以按下面理解：

1. `src/commands.ts` 把 `tasks` 注册进全局命令列表。这里能看到 `tasks` 被纳入统一的 command registry。
2. 用户在 REPL 或命令系统里触发 `tasks`。
3. 系统根据 `index.ts` 的 `load` 懒加载 `tasks.tsx`。
4. `tasks.tsx` 的 `call()` 被执行，返回 `BackgroundTasksDialog`。
5. 具体的交互、列表、详情、状态切换，转入 `src/components/tasks/BackgroundTasksDialog.tsx` 和同目录下的相关组件。

另外，`src/commands.ts` 里对 `local-jsx` 有明确说明：这类命令会渲染 Ink UI，默认不属于 Remote Control 的可桥接安全命令。因此 `tasks` 更偏向本地交互场景，而不是远程文本执行场景。

## 推荐阅读顺序

1. 先看 `src/commands/tasks/index.ts`，弄清楚这个命令如何被定义、命名和懒加载。
2. 再看 `src/commands/tasks/tasks.tsx`，确认它如何把上下文交给 UI 组件。
3. 然后跳到 `src/components/tasks/BackgroundTasksDialog.tsx`，看真正的任务面板如何组织。
4. 如果想理解它为什么会出现在全局命令体系里，再回看 `src/commands.ts` 中的命令注册段。
5. 最后按需要延伸到 `src/components/tasks/` 里的其他文件，理解后台任务的详情弹窗、状态渲染和辅助视图。

## 常见误区

最容易搞混的是“命令目录”和“任务系统目录”不是一回事。`src/commands/tasks` 只是 `/tasks` 的入口壳；真正的任务状态、任务类型、执行上下文，通常分散在 `src/tasks`、`src/state` 和 `src/components/tasks` 里。

第二个误区是把 `aliases: ['bashes']` 理解成 shell 实现。这里它只是命令别名，指向同一个后台任务面板，不代表这里在执行 bash 任务本身。

第三个误区是以为这个目录会包含很多子模块。根据当前片段推断，这里刻意保持很薄，主要靠懒加载和组件复用来完成职责分离，所有重逻辑都在别处。
