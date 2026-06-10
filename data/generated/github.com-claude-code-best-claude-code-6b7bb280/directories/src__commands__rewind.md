# 目录：src/commands/rewind

## 它负责什么

`src/commands/rewind` 是交互式 slash command `/rewind` 的最薄入口层，职责不是直接修改会话或文件，而是把用户意图转交给 REPL 的“消息选择器”流程。它提供一个本地命令：让用户从历史 user message 中选择一个回退点，然后在 UI 中决定是否只回退对话、只回退代码，或同时回退二者。

这个目录可以理解为 `/rewind` 的命令壳：声明命令元信息、提供懒加载实现、在执行时调用 `ToolUseContext.openMessageSelector()` 打开 `MessageSelector`。真正的状态裁剪、输入框恢复、文件快照恢复、确认交互、diff 元数据展示都在目录外完成，主要集中在 `src/screens/REPL.tsx`、`src/components/MessageSelector.tsx`、`src/utils/fileHistory.ts`。

命令描述里写的是 “Restore the code and/or conversation to a previous point”，这也准确反映了它的业务边界：它触发“恢复到某个历史点”的交互，但恢复动作由 REPL 与 file history 子系统完成。

## 直接子目录地图

`src/commands/rewind` 当前没有直接子目录，只有两个文件：

`src/commands/rewind/index.ts`：命令注册文件。声明 `rewind` 这个 `Command` 对象，包括命令名、别名、描述、类型、交互模式支持情况和懒加载入口。

`src/commands/rewind/rewind.ts`：命令执行文件。导出 `call()`，在本地命令被触发时打开消息选择器，并返回 `{ type: 'skip' }`，避免把 `/rewind` 本身追加成一条会话消息。

从目录结构看，这个命令没有自己的状态模型、UI 组件或文件操作逻辑。它遵循仓库中许多命令的常见模式：`index.ts` 做轻量声明，实际 `call()` 放在同名实现文件中，并通过 `load: () => import('./rewind.js')` 延迟加载。

## 关键入口

第一个入口是 `src/commands/rewind/index.ts` 中的默认导出 `rewind`。它的关键字段包括：

`name: 'rewind'`：注册 `/rewind` 命令。

`aliases: ['checkpoint']`：允许用户用 `/checkpoint` 触发同一功能。

`type: 'local'`：说明这是本地命令，不是构造 prompt 发给模型的命令。

`supportsNonInteractive: false`：说明它依赖交互式 UI，不支持非交互模式直接执行。

`load: () => import('./rewind.js')`：实际执行逻辑懒加载到 `rewind.ts`。

第二个入口是 `src/commands/rewind/rewind.ts` 中的 `call(_args, context)`。它只做一件事：如果 `context.openMessageSelector` 存在，就调用它。之后返回 `skip` 类型结果。这里没有解析参数，`_args` 明确未使用，也说明 `/rewind` 当前不是通过命令参数指定回退点，而是通过交互列表选择。

第三个入口在命令集合层：`src/commands.ts` 导入 `./commands/rewind/index.js`，并把 `rewind` 放入 `COMMANDS` 数组。也就是说，`/rewind` 能被发现、补全和执行，是通过全局命令注册表接入的。

## 主流程位置

`src/commands/rewind` 只负责启动流程，主流程分散在三个邻近模块里。

对话回退的核心在 `src/screens/REPL.tsx`。`/rewind` 通过 `openMessageSelector` 打开选择器；选择消息后，REPL 使用 `rewindConversationTo(message)` 将 `messages` 裁剪到目标 user message 之前，并重置 `conversationId`。这个函数还会重置 microcompact 状态、在启用 `CONTEXT_COLLAPSE` 时重置 context collapse 状态，并从目标消息恢复 `permissionMode`，同时清空旧的 `promptSuggestion`。

输入内容恢复也在 `src/screens/REPL.tsx`。`restoreMessageSync(message)` 会先调用 `rewindConversationTo(message)`，再通过 `textForResubmit(message)` 把被回退的用户输入重新放回输入框。如果原消息包含 pasted image，它还会恢复 `pastedContents`。因此 `/rewind` 的语义不是简单删除历史，而是“回到发送这条消息之前，并让用户可以重新编辑/发送”。

交互确认和选项展示在 `src/components/MessageSelector.tsx`。这个组件展示可回退的 user message 列表，加载每个候选点的 file history 元数据，并在确认阶段让用户选择恢复选项。根据当前片段可见，它会根据 `isFileHistoryEnabled`、`diffStatsForRestore`、`canRestoreCode` 决定是否允许代码恢复，并提示 “Rewinding does not affect files edited manually or via bash.” 这说明代码回退只覆盖 file history 能追踪到的变更，不是完整的工作区时间机器。

文件回退的核心在 `src/utils/fileHistory.ts`。`fileHistoryRewind(updateFileHistoryState, messageId)` 会检查 file history 是否启用，捕获当前 `FileHistoryState`，找到目标 `messageId` 对应的 snapshot，然后调用 `applySnapshot()` 把文件系统恢复到该快照。它本身说明“Rewind is a pure filesystem side-effect and does not mutate FileHistoryState”，也就是文件恢复是 I/O 副作用，状态对象只用于读取快照。用于快速判断是否需要代码回退的逻辑则是 `fileHistoryHasAnyChanges(state, messageId)`。

此外，非交互或 SDK 相关的文件回退还有另一条路径：`src/cli/print.ts` 中能看到 `--rewind-files` 和 `handleRewindFiles()`，以及 SDK control request 的 `rewind_files` 分支。但这不是 `src/commands/rewind` 目录本身的主流程。根据当前片段推断，`/rewind` 面向 TUI 用户，`--rewind-files` 面向 resumed session 或 SDK/print 管线中的独立文件恢复操作，二者共享 file history 能力但入口不同。

## 推荐阅读顺序

建议先读 `src/commands/rewind/index.ts`，理解命令如何暴露给全局命令系统。这个文件很短，能快速确认 `/rewind` 是 local command、别名是 `/checkpoint`、不支持非交互模式。

第二步读 `src/commands/rewind/rewind.ts`。这里能看清该目录的真实职责：调用 `context.openMessageSelector()`，然后返回 `skip`。读完这里就应该意识到：不要在这个目录里寻找回退算法，它只是打开 UI。

第三步跳到 `src/commands.ts`，看 `rewind` 如何进入 `COMMANDS` 数组。这个位置用于理解命令发现和注册，而不是业务逻辑。

第四步读 `src/screens/REPL.tsx` 中 `handleShowMessageSelector`、`rewindConversationTo`、`restoreMessageSync`、`handleRestoreMessage` 以及渲染 `MessageSelector` 的片段。这是理解 `/rewind` 行为的核心：消息列表如何截断，输入如何恢复，文件回退回调如何接入。

第五步读 `src/components/MessageSelector.tsx`。重点看候选消息列表、确认界面、restore option、file history metadata 展示。这里解释了用户为什么会看到“conversation / code / both”等不同选择。

第六步读 `src/utils/fileHistory.ts` 的 `fileHistoryRewind()`、`fileHistoryHasAnyChanges()` 和相关 snapshot 逻辑。只需要概览即可，不必追完每个备份文件恢复细节；overview 层面只要知道它通过 message snapshot 恢复被追踪文件。

## 常见误区

第一个误区是把 `src/commands/rewind` 当成完整回退实现。实际上它只是命令入口，真正逻辑在 REPL、MessageSelector 和 file history。修改 `/rewind` 行为时，如果涉及消息裁剪、确认选项或文件恢复，通常不应该只看这个目录。

第二个误区是认为 `/rewind` 会自动回退所有文件变化。根据 `MessageSelector` 的提示和 `fileHistory` 设计，它只处理 file history 追踪到的文件快照；手动编辑或通过 bash 造成的变化可能不受影响。这里的“code rewind”不是 Git reset，也不是完整文件系统快照。

第三个误区是认为 `/rewind` 会向模型发送一条消息。`call()` 返回 `{ type: 'skip' }`，目的就是不把命令本身追加到对话历史。它是本地 UI 操作，不是 prompt command。

第四个误区是忽略 `supportsNonInteractive: false`。`/rewind` 依赖交互式消息选择器；如果要研究非交互文件回退，应看 `src/cli/print.ts` 的 `--rewind-files` 和 SDK control schema，而不是期待这个命令目录支持参数化恢复。

第五个误区是把 `/rewind` 和 `/clear`、`/compact` 混为一类。它们都会影响消息历史，但 `/rewind` 的特点是回到某条 user message 之前，并把那条消息内容恢复到输入框，形成“从旧点重新分叉”的体验；`compact` 更偏向压缩上下文，`clear` 更偏向清空会话状态。

第六个误区是忽略权限模式恢复。`rewindConversationTo()` 会从目标消息恢复 `permissionMode`，这意味着回退不只是消息数组截断，还会影响后续工具权限上下文。对于调试“回退后权限行为变化”的问题，这一点很关键。
