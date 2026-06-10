# 目录：src/commands/files

## 它负责什么

`src/commands/files` 实现的是内置斜杠命令 `/files`，作用是列出“当前会话上下文中已经被追踪的文件”。这里的“files”不是对工作区目录做 `find`、`glob` 或递归扫描，而是读取运行时的 `readFileState` 缓存，把缓存里记录过的文件路径展示给用户。

从当前代码看，这个命令的定位很窄：它只关心文件上下文状态的可视化，不负责读取文件内容、不负责判断文件是否变更、不负责把文件加入上下文，也不负责文件编辑前置校验。真正维护文件状态的是 `src/utils/fileStateCache.ts` 以及各类文件工具，例如 `packages/builtin-tools/src/tools/FileReadTool/FileReadTool.ts`、`packages/builtin-tools/src/tools/FileEditTool/FileEditTool.ts`、`packages/builtin-tools/src/tools/FileWriteTool/FileWriteTool.ts` 等。`/files` 只是把这些状态以用户可读的形式输出。

这个命令目前还带有内部开关：`isEnabled: () => process.env.USER_TYPE === 'ant'`。也就是说，它在命令定义层面被限制为 `USER_TYPE` 为 `ant` 时启用。根据当前片段推断，这属于 Anthropic 内部或调试辅助命令，虽然它被放进了主命令列表和 bridge 安全命令列表，但是否可见仍要经过命令启用判断。

## 直接子目录地图

`src/commands/files` 下面没有直接子目录，只有两个文件：

`src/commands/files/index.ts`：命令定义入口，声明 `/files` 的命令元信息，包括 `type`、`name`、`description`、启用条件、非交互支持，以及懒加载目标。

`src/commands/files/files.ts`：命令执行逻辑，导出 `call()` 函数。它从 `ToolUseContext` 中取 `readFileState`，通过 `cacheKeys()` 获取缓存键，再转换成相对当前工作目录的路径列表。

因为目录很小，阅读时不需要按子模块拆分理解。更合适的方式是把它放到整个 slash command 系统和文件状态缓存机制中看。

## 关键入口

最直接的入口是 `src/commands/files/index.ts`。这里定义了一个 `Command` 对象：

`type: 'local'` 表示它是本地执行命令，执行后直接返回本地结果，而不是生成 prompt 交给模型。

`name: 'files'` 对应用户输入的 `/files`。

`description: 'List all files currently in context'` 明确说明它列出的不是磁盘文件，而是当前上下文中的文件。

`isEnabled: () => process.env.USER_TYPE === 'ant'` 是启用门槛。命令注册后是否真的可用，还要看通用命令系统如何调用 `isCommandEnabled()`。

`supportsNonInteractive: true` 表示它可以在非交互模式下运行。

`load: () => import('./files.js')` 是懒加载入口，只有命令真正执行时才加载 `files.ts`。

实际逻辑入口是 `src/commands/files/files.ts` 的 `call(_args, context)`。这个函数忽略命令参数，只依赖 `context.readFileState`。如果缓存为空，返回文本 `No files in context`；如果不为空，就把缓存中的路径通过 `relative(getCwd(), file)` 转成相对当前工作目录的路径，并拼成：

`Files in context:`
加逐行文件列表。

## 主流程位置

从注册流程看，`src/commands.ts` 会导入 `files`：

`import files from './commands/files/index.js'`

随后它被加入主命令集合。也就是说 `/files` 不是孤立工具，而是普通内置 slash command 的一员。命令是否显示、是否能执行，遵循 `src/commands.ts` 和 `src/types/command.js` 里统一的命令系统规则。

从远程控制流程看，`src/commands.ts` 的 `BRIDGE_SAFE_COMMANDS` 也把 `files` 加入了允许列表，并注释为 `List tracked files`。这说明 `/files` 被认为是 bridge/mobile/web 远程入口可安全执行的 local command，因为它只返回文本，不打开本地 Ink UI，也不执行有副作用的文件操作。不过它仍然是 local command，并不等于远端可以绕过启用条件。

从数据来源看，`/files` 的核心输入是 `ToolUseContext.readFileState`。这个上下文在多个主流程中被传递，例如 `src/QueryEngine.ts`、`src/screens/REPL.tsx`、`src/query.ts`、`src/entrypoints/mcp.ts`、`src/cli/print.ts` 等。`readFileState` 的类型来自 `src/utils/fileStateCache.ts`，本质是一个带大小限制的 LRU 文件状态缓存，默认最大 100 个条目，并带有总内容大小限制。缓存值包含 `content`、`timestamp`、`offset`、`limit`、`isPartialView` 等信息，但 `/files` 只使用 key，也就是文件路径。

从文件加入缓存的路径看，主要来源包括文件读取工具、编辑/写入工具、附件和记忆文件注入、压缩恢复、非交互 transcript 恢复、子代理上下文克隆等。`/files` 不关心这些来源差异，只把当前缓存能看到的路径列出来。

## 推荐阅读顺序

1. 先读 `src/commands/files/index.ts`，确认 `/files` 是一个 `local` 命令，并注意 `USER_TYPE === 'ant'` 的启用限制和 `load()` 懒加载模式。

2. 再读 `src/commands/files/files.ts`，理解实际行为非常简单：取 `context.readFileState`、调用 `cacheKeys()`、路径相对化、返回文本。

3. 接着读 `src/commands.ts` 中导入 `files`、加入主命令集合、加入 `BRIDGE_SAFE_COMMANDS` 的位置。这样能知道 `/files` 在整个 slash command 系统和远程控制安全白名单中的角色。

4. 然后读 `src/utils/fileStateCache.ts`，重点看 `FileStateCache`、`READ_FILE_STATE_CACHE_SIZE`、`cacheKeys()`、`cloneFileStateCache()`、`mergeFileStateCaches()`。这能解释为什么 `/files` 列出的文件有 LRU 和大小限制，也解释为什么它是“上下文文件列表”而不是完整项目文件列表。

5. 最后按需要跳到文件状态的生产者，例如 `packages/builtin-tools/src/tools/FileReadTool/FileReadTool.ts`、`packages/builtin-tools/src/tools/FileEditTool/FileEditTool.ts`、`src/utils/attachments.ts`、`src/services/compact/compact.ts`。overview 阶段不需要逐行看这些文件，只要知道它们会写入或清理 `readFileState` 即可。

## 常见误区

第一，容易把 `/files` 理解成列出当前目录下所有文件。实际上它只列 `readFileState` 缓存里的 key。没有被读取、注入、恢复或工具写入缓存的文件，即使存在于磁盘上，也不会出现在 `/files` 输出中。

第二，容易忽略 LRU 限制。`readFileState` 默认是 100 条、带大小限制的缓存。较早的文件可能被淘汰，大文件内容也受缓存大小策略影响。因此 `/files` 输出更接近“近期或当前仍被追踪的上下文文件”，不是永久会话索引。

第三，容易以为 `/files` 会展示文件内容或变更状态。当前实现只展示路径，不输出 `content`、`timestamp`、`offset`、`limit`，也不判断文件是否已经被外部修改。文件新旧校验主要在编辑、写入、diff、compact 等路径中完成。

第四，容易忽略 `USER_TYPE === 'ant'`。虽然命令被注册，也被加入 bridge 安全列表，但 `index.ts` 明确限制了启用条件。排查“为什么看不到 `/files`”时，应先检查命令启用逻辑和环境变量，而不是只看 `commands.ts` 是否导入。

第五，容易把 `readFileState` 当作只由 `Read` 工具产生。根据当前片段推断，除了 `FileReadTool`，编辑/写入工具、CLAUDE.md 或 memory 注入、compact、非交互恢复、子代理上下文等也可能影响它。判断 `/files` 输出来源时，需要结合具体会话路径，而不是只追一个工具实现。
