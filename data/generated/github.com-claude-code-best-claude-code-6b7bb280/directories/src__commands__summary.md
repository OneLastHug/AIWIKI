# 目录：src/commands/summary

## 它负责什么

`src/commands/summary` 实现的是 CLI 内部的 `/summary` 本地命令，用来“手动生成并展示当前会话摘要”。它不是通用的文本摘要工具，也不是 `/compact` 那种会话压缩命令；它的职责更窄：从当前命令上下文里取出会话消息，触发一次 Session Memory 的手动提取流程，然后读取更新后的摘要内容并返回给用户显示。

从 `src/commands/summary/index.ts` 的注释和实现看，这个命令面向“当前 session 的 memory summary”。它会调用 `manuallyExtractSessionMemory` 生成或刷新摘要，再调用 `getSessionMemoryContent` 读取摘要文件内容。返回结果统一是命令系统可展示的 `{ type: 'text', value: ... }`。因此这个目录更像是命令层的薄封装，真正的摘要生成逻辑位于 `src/services/SessionMemory/sessionMemory.js` 和 `src/services/SessionMemory/sessionMemoryUtils.js` 对应源码模块中。

该目录还处理了一个关键防御点：`context.messages` 里可能混有 progress、attachment 等 UI 或运行时消息，并不都适合送入 API 链路。`/summary` 会先把消息过滤到 `user`、`assistant`、`system` 三类，避免后续 `normalizeMessagesForAPI`、`addCacheBreakpoints` 一类 API 预处理逻辑因为非对话消息崩溃。根据当前片段推断，这个过滤是手动 `/summary` 路径特有的补偿，因为自动提取路径已经通过 `createCacheSafeParams(REPLHookContext)` 拿到了更干净的消息集合。

## 直接子目录地图

`src/commands/summary` 目前是一个很小的命令目录，直接内容包括：

- `src/commands/summary/index.ts`：命令实现入口，导出默认的 `summary` command 对象。
- `src/commands/summary/__tests__`：该命令的单元测试目录。
- `src/commands/summary/__tests__/summary.test.ts`：覆盖命令元数据、成功刷新摘要、提取失败、空内容、无消息等场景。

这个目录没有更深的业务子模块，也没有 UI 组件、prompt 模板或独立服务层。它的定位是命令注册系统到 Session Memory 服务之间的一层适配。

## 关键入口

最关键入口是 `src/commands/summary/index.ts` 默认导出的 `summary` 对象。它满足 `Command` 类型，主要字段包括：

- `type: 'local'`：说明这是本地命令，不是远程工具或 shell 子命令。
- `name: 'summary'`：命令名，对应用户输入的 `/summary`。
- `description: 'Generate and display a session summary'`：命令描述。
- `supportsNonInteractive: true`：表示支持非交互环境调用。
- `isHidden: false`：说明该命令不是隐藏命令，应该可以出现在正常命令列表或帮助中。
- `load: () => Promise.resolve({ call })`：懒加载命令执行函数。

命令真正执行逻辑在同文件的 `call` 函数中。`call` 接收 `_args` 和 `context`，但当前实现没有解析命令参数，核心只依赖 `context.messages` 以及传给 Session Memory 服务的上下文对象。

该命令通过 `src/commands.ts` 进入全局命令集合。那里有 `import summary from './commands/summary/index.js'`，并将 `summary` 放入命令列表，旁边注释为 `Summarize conversation`。所以从入口层看，`/summary` 的注册路径是：`src/commands.ts` 导入命令对象，CLI/REPL 命令分发系统再按 `name` 找到并执行其 `load().call(...)`。

## 主流程位置

主流程集中在 `src/commands/summary/index.ts` 的 `call` 函数，可按以下阶段理解：

1. 读取命令上下文中的 `messages`。
2. 使用 `API_SAFE_TYPES` 过滤消息，只保留 `user`、`assistant`、`system` 类型。
3. 如果过滤后没有消息，直接返回 `No messages to summarize.`，不会调用 Session Memory。
4. 动态导入 `../../services/SessionMemory/sessionMemory.js` 中的 `manuallyExtractSessionMemory`。
5. 动态导入 `../../services/SessionMemory/sessionMemoryUtils.js` 中的 `getSessionMemoryContent`。
6. 构造 `safeContext = { ...context, messages: safeMessages }`，把过滤后的消息回填到上下文。
7. 调用 `manuallyExtractSessionMemory(safeMessages, safeContext)` 触发手动摘要生成。
8. 如果生成失败，返回 `Failed to generate session summary: ...`。
9. 如果生成成功，调用 `getSessionMemoryContent()` 读取摘要内容。
10. 如果内容为空或只有空白，返回 `Session summary was updated, but the content is empty.`。
11. 否则返回 `Session summary updated.\n\n${content}`，把最新摘要展示给用户。
12. 任意异常都会被捕获并转为文本错误结果。

这里的“生成”和“读取”是两个分开的步骤：`manuallyExtractSessionMemory` 负责更新 Session Memory，`getSessionMemoryContent` 负责拿到最终展示内容。命令层没有直接操作摘要文件路径，也没有自己拼 prompt 或调用模型；这些都被封装在 `src/services/SessionMemory` 相关模块里。

## 推荐阅读顺序

建议先读 `src/commands/summary/index.ts`，因为它只有一个核心执行函数，能快速建立 `/summary` 的职责边界。重点看 `API_SAFE_TYPES`、`safeMessages`、动态 import、`manuallyExtractSessionMemory` 和 `getSessionMemoryContent` 的调用顺序。

第二步读 `src/commands/summary/__tests__/summary.test.ts`。测试文件能帮助确认命令的外部行为：成功时必须包含 `Session summary updated.`，失败时暴露错误信息，摘要内容为空时给出明确提示，没有可摘要消息时提前返回。这里还通过 mock 隔离了 Session Memory 服务，说明该目录测试关注的是命令适配逻辑，而不是模型生成质量。

第三步再看 `src/commands.ts`。这里可以确认 `/summary` 作为普通命令进入全局命令注册表，而不是 feature flag 条件命令。它与 `clear`、`compact`、`context`、`memory`、`share` 等命令并列，属于 REPL 命令体系的一部分。

最后，如果要继续追踪真正摘要生成机制，再进入 `src/services/SessionMemory/sessionMemory.js` 和 `src/services/SessionMemory/sessionMemoryUtils.js` 对应源码。根据当前片段推断，那里才会涉及摘要文件、memory 提取策略、模型调用参数和自动提取路径。

## 常见误区

第一个误区是把 `/summary` 理解成 `/compact`。`/compact` 的目标是清理或压缩对话历史并保留摘要上下文；`/summary` 的目标是刷新并显示 Session Memory 摘要。两者都和“摘要”有关，但对会话状态的影响和使用场景不同。

第二个误区是认为 `src/commands/summary` 内部实现了摘要算法。实际上这里没有 prompt 组装、模型流式处理或摘要文件写入逻辑，只是过滤消息、调用 Session Memory 服务、读取结果并包装成命令输出。

第三个误区是忽略 `API_SAFE_TYPES`。这个过滤不是随意优化，而是为了避免手动命令路径把 UI 进度、附件、工具状态等非 API 安全消息传入模型请求链路。修改这段逻辑时需要确认下游 API 预处理函数能接受新增消息类型，否则可能引入运行时错误。

第四个误区是以为 `supportsNonInteractive: true` 表示该命令不依赖上下文。它仍然依赖 `context.messages`；非交互支持只是说明命令系统允许在非交互模式下调用。若上下文里没有有效消息，它会直接返回无消息提示。

第五个误区是把 `getSessionMemoryContent()` 的返回内容当作一定非空。实现里专门处理了空字符串、空白内容和 `null`，说明“提取成功”不等价于“有可展示摘要”。这也是测试覆盖的一个重要边界。
