# 目录：src/commands/heapdump

## 它负责什么

`src/commands/heapdump` 是内置斜杠命令 `/heapdump` 的命令适配层，职责很窄：把用户输入的本地命令转成一次 JavaScript heap snapshot 采集，并把执行结果以文本形式返回给命令系统。它本身不实现内存诊断、文件写入、V8 快照生成等重逻辑，而是委托给 `src/utils/heapDumpService.ts`。

从命令定义看，`/heapdump` 是一个 `local` command，描述为 `Dump the JS heap to ~/Desktop`，并且 `isHidden: true`。这说明它不是面向普通用户的显式功能入口，更像是内部诊断或故障排查工具。它支持 `supportsNonInteractive: true`，因此除了交互式 REPL 中输入 `/heapdump`，也可以在非交互式命令处理链路中运行。

这个目录可以理解为“命令壳”：负责注册命令名、懒加载实现、调用服务函数、格式化成功或失败的返回文本。真正的主业务边界在 `src/utils/heapDumpService.ts`，其中包含内存指标采集、诊断 JSON 生成、`.heapsnapshot` 写入、日志和 analytics 事件上报。

## 直接子目录地图

当前片段显示 `src/commands/heapdump` 下没有直接子目录，只有两个文件：

`src/commands/heapdump/index.ts`：命令元信息入口。定义 `heapDump` command 对象，声明命令类型、名称、描述、隐藏状态、非交互支持，以及 `load: () => import('./heapdump.js')` 懒加载实现模块。

`src/commands/heapdump/heapdump.ts`：命令执行入口。导出 `call()`，内部调用 `performHeapDump()`，然后根据 `success` 返回 `{ type: 'text', value: ... }`。成功时返回 heap snapshot 路径和 diagnostics JSON 路径；失败时返回错误文本。

因此这个目录没有复杂的树状结构，也没有 UI 组件、测试夹具或多级子命令。阅读时不要把它当成 heap dump 功能的完整实现目录，它只是 `/heapdump` 与底层服务之间的一层薄封装。

## 关键入口

命令声明入口是 `src/commands/heapdump/index.ts`。其中 `name: 'heapdump'` 决定用户侧斜杠命令名是 `/heapdump`；`type: 'local'` 决定它走本地命令执行分支，不会生成 prompt 让模型继续处理；`load()` 决定实际运行时才加载 `src/commands/heapdump/heapdump.ts`。

全局注册入口在 `src/commands.ts`。该文件 import `heapDump from './commands/heapdump/index.js'`，并把 `heapDump` 放入内置命令列表。根据当前片段推断，命令系统通过 `getCommands()` / `loadAllCommands()` 一类逻辑汇总这些内置命令、插件命令和 skill 命令，再供 REPL 或输入处理模块查找。

执行入口是 `src/commands/heapdump/heapdump.ts` 的 `call()`。这个函数没有读取参数，也没有使用命令上下文，说明 `/heapdump` 当前不支持用户传入输出目录、触发模式或 dump 编号等选项。它固定执行一次手动 heap dump，并返回两行路径文本。

底层服务入口是 `src/utils/heapDumpService.ts` 的 `performHeapDump()`。虽然不在目标目录内，但它是理解该命令行为必须阅读的邻近上下文。

## 主流程位置

主流程从用户输入 `/heapdump` 开始。斜杠命令处理逻辑位于 `src/utils/processUserInput/processSlashCommand.tsx`。根据当前片段，命令被识别后会进入 `getMessagesForSlashCommand()`，再按 `command.type` 分发。因为 `heapdump` 是 `local`，所以会进入 `case 'local'` 分支。

在 `local` 分支中，系统会先构造用户输入消息，然后执行 `const mod = await command.load()`，也就是懒加载 `src/commands/heapdump/heapdump.ts`；随后调用 `await mod.call(args, context)`。`/heapdump` 的 `call()` 会调用 `performHeapDump()`，拿到 `HeapDumpResult` 后返回文本型 `LocalCommandResult`。

`performHeapDump()` 的内部流程大致是：先调用 `captureMemoryDiagnostics()` 采集当前进程内存状态；再确定桌面目录 `getDesktopPath()`；按当前 session id 生成两个文件名：`${sessionId}.heapsnapshot` 和 `${sessionId}-diagnostics.json`；先写 diagnostics JSON，再通过 `writeHeapSnapshot()` 写 V8 heap snapshot；最后记录 `tengu_heap_dump` analytics 事件并返回 `{ success: true, heapPath, diagPath }`。失败时会 `logError()`，上报失败事件，并把错误 message 返回给命令层。

一个细节是 diagnostics 会先于 heap snapshot 写入。源码注释给出的原因是 heap snapshot 序列化本身可能因大堆内存而崩溃，而且生成快照会分配额外内存、污染后续读数。因此先保存轻量诊断信息，即使快照失败，也能留下内存状态证据。

## 推荐阅读顺序

1. 先读 `src/commands/heapdump/index.ts`，确认 `/heapdump` 是隐藏的 `local` command，并理解它通过 `load()` 懒加载实现。

2. 再读 `src/commands/heapdump/heapdump.ts`，看清命令层只做三件事：调用 `performHeapDump()`、判断 `success`、返回文本结果。这里是目标目录内最核心的执行代码。

3. 接着读 `src/utils/heapDumpService.ts` 的 `HeapDumpResult`、`MemoryDiagnostics`、`captureMemoryDiagnostics()`、`performHeapDump()`。这是实际功能所在，尤其要关注内存指标来源、文件命名、写入顺序和错误处理。

4. 然后读 `src/commands.ts` 中 `heapDump` 的导入和命令数组位置，理解它如何进入全局命令集合。

5. 最后按需读 `src/utils/processUserInput/processSlashCommand.tsx` 的 `case 'local'` 分支，理解 `/heapdump` 的返回文本如何变成 `<local-command-stdout>...</local-command-stdout>` 类型的系统本地命令输出，而不是继续发给模型查询。

## 常见误区

第一，容易误以为 `src/commands/heapdump` 实现了 heap dump 的全部逻辑。实际上它只负责命令注册和调用，核心实现在 `src/utils/heapDumpService.ts`。

第二，`/heapdump` 是隐藏命令，不代表不可用。`isHidden: true` 通常只是让它不出现在普通帮助或命令推荐里；只要命令集合包含它，用户直接输入仍可能触发。

第三，`supportsNonInteractive: true` 不等于它会自动运行。它只是声明该 local command 可在非交互场景执行，具体是否触发仍取决于上层命令解析和用户输入。

第四，heap snapshot 只覆盖 V8 heap，不覆盖全部进程 RSS。服务层 diagnostics 特意记录 `external`、`arrayBuffers`、`rss`、`resourceUsage`、active handles、open file descriptors 等信息，就是为了辅助判断泄漏是否来自 native memory、文件句柄、socket、timer 或其他非 JS 堆区域。

第五，不要把成功返回的两行路径理解成模型回答。根据 `processSlashCommand` 的 local 分支，文本结果会作为本地命令 stdout 进入消息流，`shouldQuery: false`，即执行 `/heapdump` 本身不会要求模型继续推理或回答。
