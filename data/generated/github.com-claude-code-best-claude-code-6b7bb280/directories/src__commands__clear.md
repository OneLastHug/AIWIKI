# 目录：src/commands/clear

## 它负责什么

`src/commands/clear` 是“清空当前会话”的命令实现目录，职责不是简单删掉消息，而是把一次 `/clear` 做成完整的会话重置动作。根据当前片段推断，这里同时覆盖了两类状态：一类是对话内容本身，另一类是会话级缓存、任务状态、会话元数据、工作树状态和部分后台钩子。

它的设计思路很清楚：`clear` 命令先被注册成一个轻量入口，真正的清理逻辑再按需懒加载。这样既能减少启动期开销，也能把“清消息”和“清缓存”拆开处理，避免每次都把重型依赖拉进来。

## 直接子目录地图

这个目录下面没有更深层的子目录，只有 4 个文件，分别承担不同层次的职责：

- `src/commands/clear/index.ts`：命令元数据入口，只负责把 `clear` 挂到命令系统里，并声明懒加载。
- `src/commands/clear/clear.ts`：命令调用薄包装，收到执行请求后转交给真正的会话清理函数。
- `src/commands/clear/conversation.ts`：主流程，负责清空消息、重置会话 ID、处理任务保留/终止、执行 hooks、刷新工作树和会话状态。
- `src/commands/clear/caches.ts`：缓存清理集合，专门处理各种 session 相关缓存、上下文缓存和按需保留的派生状态。

## 关键入口

最外层入口是 `src/commands/clear/index.ts`。它导出一个 `Command` 描述对象，名字是 `clear`，别名包含 `reset` 和 `new`，并且显式标记 `supportsNonInteractive: false`。这意味着它主要面向交互式会话，而不是管道化的无界面调用。

这个入口还定义了 `load: () => import('./clear.js')`。也就是说，真正执行逻辑的模块不会在启动时立刻加载，而是在命令触发时才加载。

第二层入口是 `src/commands/clear/clear.ts`。它几乎不做事情，只是接收命令调用上下文，然后调用 `clearConversation(context)`。这层的价值在于把命令协议和业务逻辑解耦。

## 主流程位置

主流程集中在 `src/commands/clear/conversation.ts`，它基本定义了 `/clear` 的完整语义：

1. 先执行 `SessionEnd` hooks，给外部扩展一个收尾机会。
2. 上报一次缓存驱逐提示，用于分析和推理侧的状态回收。
3. 扫描当前任务，分出需要保留的后台任务和需要终止的前台任务。
4. 清空消息列表，并通过 bridge 通知外部“conversation cleared”。
5. 清掉上下文阻塞状态，让 proactive / kairos 之类的机制可以重新恢复。
6. 调用 `clearSessionCaches(preservedAgentIds)`，清 session 级缓存。
7. 重置 API 请求状态、成本状态、文件状态、技能名称缓存等。
8. 重建 AppState 中的任务、MCP、file history、attribution 等关键字段。
9. 清理计划 slug、会话元数据，重新生成 session ID，并重设工作树 / 目录相关状态。
10. 对保留下来的本地 agent 任务重新挂接输出路径，避免它们写入旧 session 的快照。
11. 最后再跑 `SessionStart` hooks，把新会话状态交回给上层。

与之配套的 `src/commands/clear/caches.ts` 负责“缓存层”而不是“对话层”。它会清掉 context cache、命令缓存、文件建议缓存、session ingress、prompt cache break detection、MagicDocs、动态技能、LSP 状态、图像路径、WebFetch 缓存等。`main.tsx` 里还能看到它被用于 `continue` / `resume` 流程，说明它不只服务 `/clear`，也服务会话恢复。

## 推荐阅读顺序

1. `src/commands/clear/index.ts`：先看命令如何被注册。
2. `src/commands/clear/clear.ts`：确认命令调用的转发方式。
3. `src/commands/clear/conversation.ts`：看完整重置流程。
4. `src/commands/clear/caches.ts`：补齐缓存清理范围。
5. `src/main.tsx` 里调用 `clearSessionCaches` 的位置：理解它在 `resume`、`continue` 等路径中的复用方式。

## 常见误区

- 以为 `/clear` 只是把消息数组清空。实际上它还会重置 session ID、元数据、任务状态和大量缓存。
- 以为所有任务都会被无差别杀掉。这里会保留一部分后台任务，尤其是 agent 相关的保活状态。
- 以为 `clear.ts` 才是核心逻辑。它只是薄包装，真正的业务在 `conversation.ts` 和 `caches.ts`。
- 以为 `clearSessionCaches()` 只属于 `/clear`。从 `src/main.tsx` 的调用点看，它也用于 resume / continue 这类恢复流程。
- 忽略 hooks 顺序。这里先执行 `SessionEnd`，清理后再执行 `SessionStart`，这会影响扩展、插件和自动化行为。
