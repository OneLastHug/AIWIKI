# 目录：packages/coding-agent/src/modes/interactive/components

## 它负责什么

`packages/coding-agent/src/modes/interactive/components` 是 `coding-agent` 交互式终端界面的组件层，面向的是 TUI，而不是浏览器 UI。这里的组件大多基于 `@earendil-works/pi-tui` 的 `Component`、`Container`、`Text`、`Box`、`Editor`、`Focusable` 等抽象，负责把会话消息、工具调用、选择器、输入框、页脚、加载状态、快捷键提示等渲染成终端里的多行字符串。

从职责上看，它不直接承载 agent 的核心业务逻辑。核心会话、模型、工具、扩展、信任、session 管理等逻辑主要在 `packages/coding-agent/src/core` 和 `packages/coding-agent/src/modes/interactive/interactive-mode.ts` 中组织；本目录更像“终端显示与局部交互控件库”。例如 `AssistantMessageComponent`、`UserMessageComponent` 负责消息展示，`ToolExecutionComponent`、`BashExecutionComponent` 负责工具和 bash 执行状态展示，`ModelSelectorComponent`、`SessionSelectorComponent`、`SettingsSelectorComponent`、`TreeSelectorComponent` 等负责各类选择弹层或可聚焦列表。

这个目录还有一类工具型渲染函数，例如 `renderDiff`、`keyHint`、`truncateToVisualLines`，它们会被交互模式、core tools、HTML 导出等代码复用。因此它不仅是 `interactive-mode.ts` 的私有实现，也暴露了一部分可复用 UI 能力。

## 直接子目录地图

当前目标目录下没有直接子目录，是一个扁平组件目录。文件大致可以按角色分成几组：

消息展示类：`assistant-message.ts`、`user-message.ts`、`custom-message.ts`、`branch-summary-message.ts`、`compaction-summary-message.ts`、`skill-invocation-message.ts`。这些组件用于把不同来源或不同语义的消息追加到聊天区域。

执行状态类：`tool-execution.ts`、`bash-execution.ts`、`bordered-loader.ts`、`countdown-timer.ts`、`dynamic-border.ts`。它们处理工具调用、bash 输出、加载动画和视觉分隔。

输入与编辑类：`custom-editor.ts`、`extension-editor.ts`、`extension-input.ts`。这些围绕用户输入框和扩展提供的输入 UI。

选择器类：`model-selector.ts`、`scoped-models-selector.ts`、`oauth-selector.ts`、`login-dialog.ts`、`session-selector.ts`、`config-selector.ts`、`settings-selector.ts`、`theme-selector.ts`、`thinking-selector.ts`、`show-images-selector.ts`、`trust-selector.ts`、`tree-selector.ts`、`user-message-selector.ts`、`extension-selector.ts`。这组是交互式界面中弹出式或嵌入式选择流程的主要组成。

辅助工具类：`diff.ts`、`keybinding-hints.ts`、`visual-truncate.ts`、`session-selector-search.ts`、`footer.ts`。它们分别处理 diff 着色、快捷键文案、按视觉宽度截断、session 搜索过滤和底部状态栏。

另外还有 `armin.ts`、`daxnuts.ts`、`earendil-announcement.ts` 这类较特殊的展示组件，按命名和调用位置看，属于隐藏命令、公告或品牌化展示组件。

## 关键入口

本目录的聚合出口是 `packages/coding-agent/src/modes/interactive/components/index.ts`。它集中导出主要组件、类型和工具函数，例如 `AssistantMessageComponent`、`ToolExecutionComponent`、`TreeSelectorComponent`、`renderDiff`、`keyHint`、`truncateToVisualLines` 等。外部如果需要复用这些 UI 组件，优先看这个文件能得到一张公开 API 清单。

交互式模式的主入口是 `packages/coding-agent/src/modes/interactive/interactive-mode.ts`。该文件直接导入本目录大量组件，并在 `InteractiveMode` 类中持有核心 UI 容器状态，例如 `chatContainer`、`pendingMessagesContainer`、`statusContainer`、`editorContainer`、`footer`、`defaultEditor`、`pendingTools`、`streamingComponent`、`bashComponent` 等。根据当前片段推断，`interactive-mode.ts` 是把业务事件转换成组件实例、再加入 TUI 容器树的调度中心。

还有几个跨目录入口值得注意：`packages/coding-agent/src/cli/startup-ui.ts` 会使用 `ExtensionInputComponent`、`ExtensionSelectorComponent`；`packages/coding-agent/src/cli/config-selector.ts` 使用 `ConfigSelectorComponent`；`packages/coding-agent/src/cli/session-picker.ts` 使用 `SessionSelectorComponent`；`packages/coding-agent/src/index.ts` 从 `components/index.ts` 再导出部分 UI 能力。这说明本目录并非只服务运行中的 chat 界面，也服务启动配置、session 选择和包级 API 暴露。

## 主流程位置

交互主流程主要不在组件目录内，而在 `packages/coding-agent/src/modes/interactive/interactive-mode.ts`。组件目录提供“可渲染对象”，主流程负责在合适时机创建它们、更新它们、把它们加入容器或从容器移除。

一个典型路径是：用户输入由 `CustomEditor` 或扩展输入组件承载；`InteractiveMode` 捕获提交、快捷键或 slash command；随后调用 `AgentSession`、`AgentSessionRuntime`、工具执行或扩展 runner；执行过程中把状态写入 `statusContainer`、`pendingMessagesContainer` 或 `chatContainer`；当 agent 流式输出时使用 `AssistantMessageComponent` 更新 assistant 消息；工具调用则通过 `ToolExecutionComponent` 追踪 pending、展开、折叠和结果展示；用户消息进入 `UserMessageComponent`；底部状态通过 `FooterComponent` 读取 `FooterDataProvider` 渲染。

选择流程也集中由 `InteractiveMode` 或 CLI 包装触发。例如模型选择对应 `ModelSelectorComponent` 和 `ScopedModelsSelectorComponent`，session 选择对应 `SessionSelectorComponent`，配置资源选择对应 `ConfigSelectorComponent`，项目信任选择对应 `TrustSelectorComponent`，设置页对应 `SettingsSelectorComponent`。组件内部通常负责列表渲染、焦点移动、搜索过滤、确认/取消回调；真正修改会话、配置或运行时状态的位置仍在调用方。

工具渲染还有一条复用路径：`packages/coding-agent/src/core/tools/edit.ts` 使用 `renderDiff`；多个 core tools 使用 `keyHint`、`keyText`；`packages/coding-agent/src/core/export-html/tool-renderer.ts` 会创建组件并调用 `render(width)`，把终端风格输出转换为 HTML。根据当前片段推断，这些组件的 `render(width): string[]` 是核心渲染协议。

## 推荐阅读顺序

先读 `packages/coding-agent/src/modes/interactive/components/index.ts`，用它建立组件清单和公开 API 边界。它能快速回答“哪些组件被认为可以被外部复用”。

然后读 `packages/coding-agent/src/modes/interactive/interactive-mode.ts` 的 imports、字段定义和与组件相关的方法。重点看 `InteractiveMode` 如何持有 `chatContainer`、`statusContainer`、`editorContainer`，以及如何创建 `AssistantMessageComponent`、`ToolExecutionComponent`、`BashExecutionComponent`、各类 selector。

接着按主界面路径读核心组件：`custom-editor.ts`、`footer.ts`、`assistant-message.ts`、`user-message.ts`、`tool-execution.ts`、`bash-execution.ts`。这能覆盖输入、消息、工具执行和底部状态栏。

再读选择器组件：优先 `model-selector.ts`、`session-selector.ts`、`settings-selector.ts`、`tree-selector.ts`、`config-selector.ts`。这些文件更大，建议从导出的 component 类和构造参数开始看，不必一开始逐行追内部列表实现。

最后读辅助函数：`keybinding-hints.ts`、`visual-truncate.ts`、`diff.ts`、`session-selector-search.ts`。这些通常比较独立，适合理解显示宽度、快捷键提示、搜索和 diff 渲染细节。

## 常见误区

不要把这个目录理解成完整的交互模式实现。真正的会话生命周期、agent 事件订阅、工具调度、模型切换、配置落盘和扩展运行都在外层，尤其是 `interactive-mode.ts` 和 `core` 目录。本目录更多是 UI 组件和局部交互控件。

不要假设这里使用 React 或 Ink。当前片段显示它使用的是 `@earendil-works/pi-tui` 的自定义组件协议，核心方法是 `render(width): string[]`，组件之间通过 `Container`、`Component`、`Focusable` 等组合。

不要把所有 selector 看成同一种业务逻辑。它们在视觉和键盘交互上相似，但背后的数据来源不同：session、model、settings、trust、config resource、message tree 分别连接不同 core 模块。阅读时应先看构造参数和 callback，而不是先陷入渲染细节。

不要忽略 `index.ts` 的边界意义。有些组件虽然存在于目录中，但是否对外公开、是否被 CLI 或 package root 复用，要以 `components/index.ts` 和跨目录 import 为准。

不要只看组件文件来判断主流程。比如工具输出展开、流式消息更新、bash 执行状态迁移、pending 区域和 chat 区域的切换，都需要回到 `interactive-mode.ts` 看调用顺序。组件负责“怎么显示”，主流程负责“什么时候显示”和“显示什么状态”。
