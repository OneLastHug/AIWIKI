# 目录：src/commands/compact

## 它负责什么

`src/commands/compact` 是 `/compact` 这个本地命令的实现目录，职责很单一：把当前对话压缩成更短的上下文，同时尽量保留可用摘要。它属于命令层，不直接承载模型调用细节，而是负责把“什么时候压缩、走哪条压缩路径、压缩完怎么收尾”这些决策串起来。

从 `src/commands/compact/index.ts` 可以看出，这个命令默认名称就是 `compact`，描述是“Clear conversation history but keep a summary in context”。它还支持非交互模式，并且会读取 `DISABLE_COMPACT` 环境变量决定是否启用。也就是说，这个目录本质上是一个命令入口壳层，而不是某个单独算法模块。

## 直接子目录地图

根据当前片段推断，这个目录下面没有更深的子目录，只有两个文件：

- `src/commands/compact/index.ts`：命令注册与懒加载入口
- `src/commands/compact/compact.ts`：实际执行逻辑

这种结构很典型，说明这里不是按功能再拆目录，而是用一个索引文件对外暴露命令定义，真正的流程集中在单文件里。

## 关键入口

主入口是 `src/commands/compact/index.ts`。它导出一个符合 `Command` 类型的对象，关键字段有：

- `type: 'local'`
- `name: 'compact'`
- `isEnabled()`：受 `DISABLE_COMPACT` 控制
- `supportsNonInteractive: true`
- `load: () => import('./compact.js')`

这意味着命令系统先注册这个目录下的“声明”，真正执行时再动态加载 `compact.ts` 编译后的模块。

上层注册点在 `src/commands.ts`，那里直接 `import compact from './commands/compact/index.js'`。所以整个链路是：命令表注册 `compact`，用户触发后再进入这个目录下的懒加载实现。

## 主流程位置

核心流程集中在 `src/commands/compact/compact.ts` 的 `call()` 函数。它基本上就是 `/compact` 的控制塔，按顺序处理以下步骤：

1. 先拿到当前 `messages`，再通过 `getMessagesAfterCompactBoundary()` 过滤掉 REPL 里被截断但不该被继续总结的内容。
2. 如果没有消息，直接报错 `No messages to compact`。
3. 读取用户在 `/compact` 后面附加的自定义说明，作为 `customInstructions`。
4. 如果没有自定义说明，优先尝试 `trySessionMemoryCompaction()`，这是一个更轻量的会话记忆压缩分支。
5. 如果开启了 `REACTIVE_COMPACT`，则走 `compactViaReactive()`，这是一条依赖 reactive 模块的分支。
6. 否则回退到传统压缩：先 `microcompactMessages()` 缩短上下文，再调用 `compactConversation()` 做正式摘要。
7. 成功后统一做收尾：`setLastSummarizedMessageId(undefined)`、`suppressCompactWarning()`、清理 `getUserContext.cache`、执行 `runPostCompactCleanup()`。
8. 出错时根据是否中断、是否是特定错误文案做分流，最后统一包装成“Compaction canceled.” 或 `Error during compaction: ...`。

`compactViaReactive()` 是这条链路里最值得注意的分叉点。它会并行执行 `executePreCompactHooks()` 和 `getCacheSharingParams()`，然后调用 `reactiveCompactOnPromptTooLong()`。这说明这个目录虽然名字叫 compact，但真正的摘要生成并不只靠一条后端路径，而是有“会话记忆压缩、reactive 压缩、传统压缩”三层策略。

## 推荐阅读顺序

1. 先看 `src/commands/compact/index.ts`，确认命令是如何声明、启用和懒加载的。
2. 再看 `src/commands.ts` 里对 `compact` 的注册位置，建立它在全局命令体系中的位置感。
3. 然后读 `src/commands/compact/compact.ts` 的 `call()`，把主分支顺序看清楚。
4. 接着只追 `compactViaReactive()`，理解 reactive 模式下为什么要先跑 hooks。
5. 最后再顺着 import 名称去看 `src/services/compact/compact.ts`、`microCompact.ts`、`sessionMemoryCompact.ts`，这些才是具体压缩能力的承载处。

## 常见误区

- 容易把这个目录当成“压缩算法本体”。实际上它更像调度层，真正的压缩细节分散在 `src/services/compact/` 下。
- 容易忽略 `index.ts` 的作用。这里不是实现逻辑，而是命令注册与动态加载入口。
- 容易以为 `/compact` 永远走同一条路径。实际上它会先试 session memory compaction，再看 `REACTIVE_COMPACT`，最后才走传统 `compactConversation()`。
- 容易忘记 REPL 的历史截断问题。`getMessagesAfterCompactBoundary()` 的存在说明这个命令只应该总结“边界之后”的消息，不该把 UI 里故意 snip 掉的内容混进去。
- 容易低估收尾动作的重要性。像 `runPostCompactCleanup()`、`suppressCompactWarning()`、`markPostCompaction()` 这类调用，决定了压缩后系统状态是否一致，不只是“摘要写完就结束”。
