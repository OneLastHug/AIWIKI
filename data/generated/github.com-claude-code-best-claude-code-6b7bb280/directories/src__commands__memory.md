# 目录：src/commands/memory

## 它负责什么

`src/commands/memory` 是 `/memory` 本地斜杠命令的实现目录，职责很聚焦：在终端交互界面里打开一个“Memory”对话框，让用户选择要编辑的 Claude memory 文件，并调用本机编辑器打开对应文件。它本身不负责记忆文件的发现规则、内容解析、`@include` 递归加载、上下文注入，也不负责把 memory 内容发送给模型；这些主逻辑主要在 `src/utils/claudemd.ts` 和上下文构建链路中。

从代码结构看，这个目录是命令层的薄封装。`index.ts` 把命令注册为 `local-jsx` 类型，名称是 `memory`，描述是 `Edit Claude memory files`，并通过懒加载导入 `./memory.js`。`memory.tsx` 则渲染 Ink UI，复用 `src/components/memory/MemoryFileSelector.tsx` 做候选文件选择，最终调用 `editFileInEditor()` 打开文件。

这个目录处理的是“编辑入口”，不是“记忆系统”。它会在命令启动前调用 `clearMemoryFileCaches()` 和 `getMemoryFiles()`，目的是刷新并预热 memory 文件列表，避免打开选择器时出现 Suspense fallback 闪烁。用户选择某个 memory 路径后，它会必要时创建 `~/.claude` 目录，使用 `writeFile(..., flag: 'wx')` 尝试创建空文件，并保留已有内容，然后交给 `$VISUAL`、`$EDITOR` 或默认编辑器打开。

## 直接子目录地图

`src/commands/memory` 下面没有直接子目录，只有两个文件：

- `src/commands/memory/index.ts`：命令注册入口，声明 `/memory` 命令的类型、名称、描述和懒加载模块。
- `src/commands/memory/memory.tsx`：命令执行入口和 UI 组件，负责弹出 Memory 对话框、选择文件、创建缺失文件、调用编辑器、返回系统提示。

虽然目标目录没有子目录，但它依赖几个邻近路径：

- `src/components/memory/MemoryFileSelector.tsx`：memory 文件选择器，负责展示可编辑的 User / Project 等候选项。
- `src/components/memory/MemoryUpdateNotification.tsx`：提供 `getRelativeMemoryPath()`，用于把绝对路径转换成更适合提示用户的相对显示文本。
- `src/utils/claudemd.ts`：memory 文件发现、缓存、加载、解析和上下文注入相关的核心工具。
- `src/utils/memory/types.ts`、`src/utils/memory/versions.ts`：memory 类型和版本相关辅助定义。

## 关键入口

第一入口是 `src/commands/memory/index.ts`。它导出默认 `Command` 对象：

- `type: 'local-jsx'` 表示这是一个在本地 React/Ink UI 中执行的命令，而不是纯文本命令或远程工具调用。
- `name: 'memory'` 对应用户输入的 `/memory`。
- `load: () => import('./memory.js')` 表示真正实现被懒加载，只有命令被触发时才导入 `memory.tsx` 编译后的模块。

第二入口是 `src/commands/memory/memory.tsx` 中导出的 `call`：

```ts
export const call: LocalJSXCommandCall = async onDone => {
  clearMemoryFileCaches();
  await getMemoryFiles();
  return <MemoryCommand onDone={onDone} />;
};
```

这里体现了命令执行的最小生命周期：先清理 memory 文件缓存，再重新加载 memory 文件列表，最后返回一个 `MemoryCommand` React 节点交给 Ink 渲染。`onDone` 是命令系统传进来的完成回调，后续打开成功、失败或取消都会通过它向会话输出结果。

第三入口是 `MemoryCommand` 组件内部的 `handleSelectMemoryFile(memoryPath)`。它是用户选中文件后的动作入口，主逻辑包括：

- 如果路径位于 Claude 配置目录下，确保 `getClaudeConfigHomeDir()` 对应目录存在。
- 使用 `writeFile(memoryPath, '', { flag: 'wx' })` 创建缺失文件，遇到 `EEXIST` 时忽略，避免覆盖已有 memory。
- 调用 `editFileInEditor(memoryPath)` 打开编辑器。
- 根据 `VISUAL` 或 `EDITOR` 环境变量生成提示文本。
- 调用 `onDone()` 输出“Opened memory file at ...”等系统消息。

## 主流程位置

从 `/memory` 命令触发到编辑器打开，主流程大致是：

1. 命令系统发现并加载 `src/commands/memory/index.ts` 注册的 `memory` 命令。
2. 用户输入 `/memory` 后，命令系统懒加载 `src/commands/memory/memory.tsx`。
3. `call(onDone)` 执行，先调用 `clearMemoryFileCaches()`，再调用 `getMemoryFiles()`。
4. 返回 `<MemoryCommand onDone={onDone} />`，Ink 渲染 `Dialog title="Memory"`。
5. `MemoryCommand` 内部挂载 `MemoryFileSelector`，由选择器列出可编辑 memory 文件。
6. 用户选中某个路径后，`handleSelectMemoryFile()` 创建必要目录或空文件，并调用 `editFileInEditor()`。
7. 编辑器打开成功后，通过 `onDone()` 向终端显示打开路径和编辑器来源提示；取消时显示 `Cancelled memory editing`；异常时记录 `logError()` 并显示错误。

真正的 memory 发现规则不在本目录。`src/utils/claudemd.ts` 的文件头注释和相关逻辑显示，它把 memory 分为多类：Managed memory、User memory、Project memory、Local memory。它会处理 `CLAUDE.md`、`.claude/CLAUDE.md`、`.claude/rules/*.md`、`CLAUDE.local.md` 等路径，还支持 `--add-dir` 带来的额外目录。`src/commands/memory` 只是调用 `getMemoryFiles()` 获取这些规则产出的候选列表。

根据当前片段推断，memory 内容最终进入模型上下文的主链路在 `src/context.ts` 与 `src/utils/claudemd.ts` 的协作中：`claudemd.ts` 负责发现、读取、缓存和格式化 memory 文件，`context.ts` 在构建系统/用户上下文时使用这些结果。依据是 `src/context.ts` 中出现 `--add-dir` 与 CLAUDE.md 自动发现相关注释，而 `src/utils/claudemd.ts` 包含 `memory_files_started`、`memory_files_completed`、`getMemoryFiles()`、memory 文件路径识别和内容格式化逻辑。

## 推荐阅读顺序

1. 先读 `src/commands/memory/index.ts`，确认 `/memory` 是一个 `local-jsx` 命令，以及它如何懒加载实现。
2. 再读 `src/commands/memory/memory.tsx`，重点看 `call()`、`MemoryCommand`、`handleSelectMemoryFile()`，理解命令层只负责“打开编辑器”。
3. 接着读 `src/components/memory/MemoryFileSelector.tsx`，看候选文件是如何展示的，尤其是 User memory 和 Project memory 即使文件不存在也会创建可选项。
4. 然后读 `src/components/memory/MemoryUpdateNotification.tsx`，理解用户提示中 memory 路径如何被相对化展示。
5. 最后读 `src/utils/claudemd.ts` 的高层注释和 `getMemoryFiles()` 附近逻辑，建立完整 memory 发现、缓存、加载、格式化的地图。
6. 如果要追到模型上下文，再看 `src/context.ts` 中与 CLAUDE.md、`--add-dir`、简单模式相关的上下文构建逻辑。

## 常见误区

- 不要把 `src/commands/memory` 理解成 memory 系统核心。它只是 `/memory` 编辑入口，核心规则在 `src/utils/claudemd.ts`。
- `/memory` 打开的文件不一定已经存在。命令会用 `wx` 模式创建空文件，但不会覆盖已有文件。
- User memory 和 Project memory 的候选项可能由 `MemoryFileSelector` 主动构造出来，并不代表磁盘上已经有对应文件。
- 取消命令不会修改 memory，只会通过 `onDone()` 输出取消提示。
- 编辑器选择不在 memory 目录里实现，实际打开动作在 `src/utils/promptEditor.ts` 的 `editFileInEditor()`。
- `clearMemoryFileCaches()` 加 `getMemoryFiles()` 是为了让 `/memory` 选择器看到最新文件状态，不代表这里会重新构建完整模型上下文。
- `Learn more` 中的文档链接属于 UI 提示，输出文档时不应暴露真实网址，可记为 `[URL已移除]`。
- `src/utils/claudemd.ts` 中提到的 `CLAUDE.md`、`.claude/rules/*.md`、`CLAUDE.local.md` 等都是 memory 发现规则的一部分，但 `/memory` 命令本身不逐个解析这些文件内容。
