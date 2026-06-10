# 子系统：packages/desktop/src/renderer/pages/conversation/Messages

## 解决什么问题
`Messages` 目录负责会话页里“消息流”这一段的完整渲染与交互逻辑。它不是单纯的文本列表，而是把一条对话消息拆成可组合的展示单元，覆盖普通回复、thinking 状态、工具调用、权限确认、计划展示、技能推荐、cron 触发、文件变更、ACP 相关消息等多种消息形态。根据当前片段推断，它承担的是 conversation 页面中间最核心的输出区：把后端或运行时产生的结构化消息，转换成用户可读、可滚动、可恢复状态的 UI。

## 相关目录和文件
最核心的入口是 `MessageList.tsx`，通常负责按顺序组织消息、控制列表渲染和滚动行为。`hooks.ts`、`useAutoScroll.ts`、`usePendingConfirmationsRecovery.ts` 这类文件负责列表级状态与副作用，例如自动滚到底部、恢复未完成的确认态。`types.ts` 和 `constants.ts` 定义本目录内部使用的消息类型、枚举和布局常量。

展示层主要分散在 `components/` 下：`MessageText.tsx`、`MessageThinking.tsx`、`MessageToolCall.tsx`、`MessagePlan.tsx`、`MessagePermission.tsx`、`MessageAgentStatus.tsx`、`MessageFileChanges.tsx`、`MessageToolGroup.tsx`、`MessageToolGroupSummary.tsx`、`MessageTips.tsx`、`MessageSkillSuggest.tsx`、`SkillSuggestCard.tsx`、`SelectionReplyButton.tsx`、`MessageCronTrigger.tsx`、`MessageCronBadge.tsx`、`TeammateMessageAvatar.tsx`。ACP 分支的专用消息放在 `acp/` 下，如 `MessageAcpToolCall.tsx`、`MessageAcpPermission.tsx`、`MessageAvailableCommands.tsx`。样式层则由 `messages.css`、`MessageThinking.module.css`、`MessageToolGroupSummary.css` 统一承接。

## 核心对象
这里的“核心对象”不是单一 class，而是一组消息模型与渲染分派器。第一类是消息数据结构，定义在 `types.ts`，决定一条消息具备哪些字段、状态和派生属性。第二类是列表控制器，典型是 `MessageList.tsx` 和 `hooks.ts`，它们把消息数组、滚动容器、选中状态、确认恢复等串起来。第三类是消息渲染单元，例如 `MessageText` 处理正文，`MessageToolCall` 处理工具调用过程，`MessageThinking` 处理推理/等待态，`MessagePermission` 处理需要用户决策的节点，`MessageFileChanges` 处理编辑结果。根据当前片段推断，`MessageToolGroup` 与 `MessageToolGroupSummary` 负责把多次相关工具调用折叠成更紧凑的阅读结构。

## 运行流程
典型流程是：conversation 页面拿到会话消息数组后交给 `MessageList`，`MessageList` 再根据消息类型分派到不同子组件。普通文本走 `MessageText`，状态类消息走 `MessageThinking` 或 `MessageAgentStatus`，工具链路走 `MessageToolCall`、`MessageToolGroup`、`MessageToolGroupSummary`，需要用户干预的节点走 `MessagePermission`、`MessageAcpPermission` 等。列表层在消息追加时触发 `useAutoScroll`，保证新消息进入视野；如果会话中存在未完成的确认或中断状态，则 `usePendingConfirmationsRecovery` 尝试恢复 UI 状态。根据当前片段推断，`artifacts.tsx` 还会在消息流中挂载某些结构化产物或可视化结果，作为消息内容的补充出口。

## 上下游依赖
上游主要来自 `packages/desktop/src/renderer/pages/conversation/index.tsx` 及其周边的 `components/`、`platforms/`、`runtime/`：这些模块决定当前会话属于哪种平台、是否是 ACP 或 legacy 流程、消息如何生成和更新。`conversationRuntime.ts`、`useConversationRuntimeView.ts`、`platforms/*/use*Message.ts` 这类模块会把运行时事件转换为消息模型，再喂给 `Messages`。下游则是这一目录内部的各个消息组件和样式文件，它们直接消费消息数据，负责最终 UI 呈现。换句话说，这个目录处在“运行时消息事件”和“用户可见对话流”之间，是承上启下的渲染枢纽。

## 修改时最容易踩的坑
第一，消息类型分发容易漏支线：新增一种消息后，只改 `types.ts` 不够，往往还要补 `MessageList.tsx`、相关 `components/` 和样式。第二，滚动与虚拟状态很敏感，改 `useAutoScroll.ts` 或列表容器时，容易把用户正在查看历史消息时的滚动位置弄丢。第三，`MessageToolGroup` 这类聚合组件和单条 `MessageToolCall` 之间存在显示边界，改动时要注意不要重复渲染或丢失摘要。第四，ACP 分支和常规消息流并不完全同构，`acp/` 下的组件不能默认复用普通消息的逻辑。第五，样式文件分散在 `.css` 和 `.module.css`，如果只改结构不对齐样式，消息间距、折行和状态徽标很容易失真。

## 推荐阅读顺序
先看 `types.ts` 和 `constants.ts`，建立消息模型和约束；再看 `MessageList.tsx` 与 `hooks.ts`，理解列表如何组织和驱动；然后按消息类型顺序读 `MessageText.tsx`、`MessageThinking.tsx`、`MessageToolCall.tsx`、`MessagePermission.tsx`、`MessageFileChanges.tsx`、`MessagePlan.tsx`、`MessageAgentStatus.tsx`；最后补 `MessageToolGroup.tsx`、`MessageToolGroupSummary.tsx`、`acp/` 下的专用组件，以及 `useAutoScroll.ts`、`usePendingConfirmationsRecovery.ts` 这类状态辅助逻辑。这样能先抓住主链路，再看分支能力。
