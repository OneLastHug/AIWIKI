# 文件：src/utils/handlePromptSubmit.ts

## 一句话定位
这是 REPL 和输入链路的“提交入口总控”，负责把用户按下回车后的内容，按普通文本、Slash 命令、立即执行命令、队列中的待执行命令这几条路径分流，然后统一进入 `processUserInput` / `onQuery` 的核心执行链。它同时处理输入清理、图片引用展开、退出命令、打断当前生成、自治队列收尾等会影响整次 turn 的事情。

## 它暴露/定义了什么
这个文件主要暴露两个东西：

1. `handlePromptSubmit(params)`  
   对外主函数，接受一大组和 UI、状态、查询、工具权限相关的参数，完成一次提交。

2. `PromptInputHelpers` / `HandlePromptSubmitParams`  
   前者是给输入框层用的辅助接口，控制光标、缓冲区和历史；后者是提交时的参数集合，描述了这条链路需要的所有外部依赖。

根据当前片段推断，它没有作为公共业务 API 单独对外扩散，而是作为终端交互层和执行层之间的连接点使用。

## 谁调用它
从仓库内的引用看，主调用者是 `src/screens/REPL.tsx`，那里负责把真正的用户输入、初始化输入、快捷命令和远程消息送进来。  
另外，`src/components/PromptInput/PromptInput.tsx`、`src/hooks/useCommandKeybindings.tsx` 以及队列处理相关链路也依赖这里导出的 `PromptInputHelpers` 类型，说明它不仅是一个函数，也是在输入组件、快捷键和 REPL 之间共享提交协议的一部分。

## 它调用谁
它内部依赖面很广，核心上调用了这些模块：

- `processUserInput`：把提交内容转成消息、命令和后续查询决策，这是最核心的下沉执行层。
- `enqueue`：把需要延后执行的输入放入队列。
- `queryGuard`、`queryCheckpoint`、`startQueryProfile`：控制 turn 的并发、时序和性能埋点。
- `expandPastedTextRefs`、`parseReferences`：处理粘贴内容和文本引用。
- `claimConsumableQueuedAutonomyCommands`、`finalizeAutonomyCommandsForTurn`：自治命令的领取与收尾。
- `runWithWorkload`：把整个 turn 包进工作负载上下文，保证跨 `await` 仍能保留 workload。
- `fileHistoryMakeSnapshot`、`fileHistoryEnabled`：在合适时机生成文件历史快照。
- `resolveSkillModelOverride`：把局部模型覆盖应用到最终查询模型。
- 还会触发 `logEvent`、`logError`、`gracefulShutdownSync` 等日志和退出相关动作。

## 核心流程
1. **队列优先**  
   如果传入的是 `queuedCommands`，它直接走执行路径，不再做输入校验、引用展开和再次入队。这条路径适合已经被预处理过的命令。

2. **普通输入预处理**  
   对直接输入先做空串判断、图片引用过滤、文本引用展开、退出命令识别，并记录粘贴统计埋点。图片只有在文本里仍保留对应占位符时才会继续保留。

3. **立即命令短路**  
   如果输入以 `/` 开头，它会尝试匹配 immediate 的 `local-jsx` 命令，比如本地配置页、诊断页这类命令。命中后不会进入普通查询，而是加载命令实现，设置 `toolJSX` 或执行 `onDone` 回调。

4. **忙碌态分流**  
   如果当前 `queryGuard` 正在运行，或者处于外部加载状态，它不会立刻执行，而是把输入压入队列。这里还会处理可中断工具的取消逻辑。

5. **直通执行**  
   如果当前没有忙碌，它会把这次输入包装成 `QueuedCommand`，然后统一交给 `executeUserInput`。这样无论是“立刻提交”还是“队列恢复”，最后都走同一条执行管线。

6. **统一执行与收尾**  
   `executeUserInput` 会创建新的 `AbortController`，锁定 `queryGuard`，批量处理命令，调用 `processUserInput` 生成消息，再决定是否进入 `onQuery`。如果有 next input 或自治命令，还会继续排队或补发。最后通过 `finally` 确保 guard 释放、临时状态清空。

## 关键函数的高层作用
- `handlePromptSubmit`：提交入口的分流器和调度器，负责“这次输入该不该立刻执行，还是先入队”。
- `executeUserInput`：真正的 turn 执行器，负责把命令变成消息、把消息送入 query，并维护 turn 级别状态一致性。
- `exit()`：非常薄，只是通过 `gracefulShutdownSync(0)` 触发退出。
- `makeContext()`：为每个命令生成工具执行上下文，避免共享脏状态。

## 修改风险
这个文件属于高风险边界层，改动容易引起连锁问题：

- **Slash 命令语义**很脆弱，尤其是 `skipSlashCommands`、`local-jsx`、立即命令和普通文本的分流，错一层就会导致远程消息误触发本地命令。
- **队列与直通执行的统一性**不能破坏。只要某条路径没走 `executeUserInput`，就可能丢掉历史、图片重缩放、hook 或 workload 上下文。
- **`queryGuard` / `AbortController`** 的生命周期是并发安全关键点，改错会出现重复 turn、无法打断、spinner 卡住等问题。
- **自治命令收尾**依赖 turn 成功与否来决定 completed/failed，若时机不对，后续队列会被误终止或重复触发。
- **文件历史和消息历史**的更新位置有意分工，直接挪动可能造成重复入历史或漏记历史。
- **埋点与退出路径**看似次要，但它们经常被当成行为校验的旁证，改动后容易让调试和 telemetry 断裂。

如果要改这个文件，优先确认三件事：直接提交、队列恢复、远程/桥接消息这三条路径是否仍然一致。
