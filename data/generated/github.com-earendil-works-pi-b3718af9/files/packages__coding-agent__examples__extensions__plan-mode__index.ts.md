# 文件：packages/coding-agent/examples/extensions/plan-mode/index.ts

## 一句话定位

`packages/coding-agent/examples/extensions/plan-mode/index.ts` 是一个示例级 `pi-coding-agent` 扩展入口，用来给交互式 coding agent 增加“Plan mode”：先进入只读探索和计划生成阶段，再由用户确认是否切换回正常工具权限并按计划执行、追踪进度。

## 它暴露/定义了什么

该文件默认导出 `planModeExtension(pi: ExtensionAPI): void`，这是扩展系统加载后调用的工厂函数。它没有导出业务类，而是在函数内部通过闭包维护三类运行状态：

- `planModeEnabled`：是否处于只读计划模式。
- `executionMode`：是否正在执行已生成的计划。
- `todoItems`：从模型输出的 `Plan:` 段落中提取出的计划步骤，类型来自同目录 `utils.ts` 的 `TodoItem`。

它还定义了两个工具集合：`PLAN_MODE_TOOLS` 和 `NORMAL_MODE_TOOLS`。前者限制为 `read`、`bash`、`grep`、`find`、`ls`、`questionnaire`，后者恢复到 `read`、`bash`、`edit`、`write`。这说明该扩展的核心不是实现新工具，而是动态控制 agent 可用工具、注入上下文、拦截工具调用和更新 UI 状态。

文件内的 `isAssistantMessage` 与 `getTextContent` 是类型收窄和文本抽取辅助函数，用于从 agent 消息里读取 assistant 的纯文本内容。

## 谁调用它

根据当前片段推断，调用方是 `packages/coding-agent` 的扩展加载与运行时系统。依据是该文件默认导出符合 `ExtensionAPI` 约定的函数，并且仓库中存在扩展发现、加载相关代码与示例说明，例如 `packages/coding-agent/src/core/extensions`、`packages/coding-agent/test/extensions-discovery.test.ts`、`packages/coding-agent/examples/sdk/06-extensions.ts`。实际使用时，用户可以把该目录或入口注册为 extension，CLI 或 SDK 创建会话时加载它，然后扩展运行时调用默认导出函数，把 `pi` API 传入。

用户层面触发入口有三个：启动参数 `--plan` 对应 `pi.registerFlag("plan")`，交互命令 `/plan` 对应 `pi.registerCommand("plan")`，快捷键 `Ctrl+Alt+P` 对应 `pi.registerShortcut(Key.ctrlAlt("p"))`。

## 它调用谁

它主要调用 `ExtensionAPI` 和 `ExtensionContext` 提供的能力：

- `pi.registerFlag`、`pi.getFlag`：声明并读取 `plan` 启动标志。
- `pi.registerCommand`、`pi.registerShortcut`：注册 `/plan`、`/todos` 和快捷键。
- `pi.setActiveTools`：在计划模式和正常模式之间切换可用工具集合。
- `pi.on(...)`：订阅 `tool_call`、`context`、`before_agent_start`、`turn_end`、`agent_end`、`session_start` 等生命周期事件。
- `pi.sendMessage`、`pi.sendUserMessage`：向会话插入扩展消息或用户消息，并决定是否触发下一轮模型调用。
- `pi.appendEntry`：把 plan-mode 状态持久化到 session entry。

它还调用 `ctx.ui` 的 `setStatus`、`setWidget`、`notify`、`select`、`editor` 来显示状态栏、待办列表、通知和用户选择框；调用 `ctx.sessionManager.getEntries()` 从历史 session 中恢复扩展状态。

同目录 `utils.ts` 提供关键纯函数：`isSafeCommand` 判断 bash 命令是否只读安全，`extractTodoItems` 从 assistant 输出中解析编号计划，`markCompletedSteps` 根据 `[DONE:n]` 标记更新完成状态。

## 核心流程

启动或恢复会话时，`session_start` 首先检查 `--plan` 标志和历史 `plan-mode` 自定义 entry。如果恢复到计划模式，就调用 `pi.setActiveTools(PLAN_MODE_TOOLS)`；如果恢复到执行模式，则扫描上一次 `plan-mode-execute` 之后的 assistant 消息，重新用 `[DONE:n]` 标记推导完成进度，最后刷新 UI。

用户通过 `/plan` 或 `Ctrl+Alt+P` 切换模式时，`togglePlanMode` 会翻转 `planModeEnabled`，清空执行状态和旧 todo，并按模式切换工具权限。进入计划模式后，agent 启动前的 `before_agent_start` 会注入一条隐藏的 `plan-mode-context`，明确告诉模型只能读、不能改，并要求输出 `Plan:` 标题下的编号计划。

计划模式期间，`tool_call` 会额外拦截 `bash`。即使 `bash` 工具仍可用，也必须通过 `isSafeCommand` 的白名单和破坏性模式检查，否则返回 `block: true` 阻止执行。这是该扩展只读语义的第二道防线。

一轮 agent 结束后，`agent_end` 会从最后一条 assistant 消息里提取 `Plan:` 下的步骤，展示成 `plan-todo-list`，然后通过 UI 让用户选择“执行计划”“停留在计划模式”或“细化计划”。如果选择执行，它会关闭 `planModeEnabled`，开启 `executionMode`，恢复 `NORMAL_MODE_TOOLS`，并发送 `plan-mode-execute` 消息触发下一轮执行。

执行模式下，`before_agent_start` 会注入剩余步骤和约定：完成每一步后在回复中包含 `[DONE:n]`。每轮结束的 `turn_end` 读取 assistant 文本，用 `markCompletedSteps` 更新 `todoItems`，刷新状态栏和 widget，并持久化状态。后续 `agent_end` 如果发现所有步骤完成，就发送 `plan-complete` 展示完成清单，清空执行状态并恢复正常工具。

## 关键函数的高层作用

`planModeExtension` 是总装配函数：注册 flag、命令、快捷键、事件处理器，并用闭包保存当前扩展状态。理解这个函数时应按“入口注册、权限切换、上下文注入、计划提取、执行追踪、恢复状态”几个阶段看，而不是逐行看。

`togglePlanMode` 负责模式开关。它既改变内存状态，也调用 `pi.setActiveTools` 改变 agent 可用工具，还更新 UI。这里是计划模式权限边界最直接的控制点。

`updateStatus` 负责用户可见状态同步。计划模式只显示状态栏提示；执行模式还会显示 todo widget，并把已完成项用完成样式和删除线渲染。它不改变业务状态，只消费 `planModeEnabled`、`executionMode`、`todoItems`。

`persistState` 把当前扩展状态写成 `customType: "plan-mode"` 的 session entry，供 `session_start` 恢复。它是执行进度可恢复的基础。

`before_agent_start` 事件处理器是提示词注入点。计划模式下注入只读限制和输出格式要求；执行模式下注入剩余步骤和 `[DONE:n]` 协议。模型是否能按计划执行，很大程度依赖这里的约束文本。

`agent_end` 事件处理器是模式转换的核心。它在计划模式中解析计划、询问用户下一步；在执行模式中判断是否完成并收尾。

`turn_end` 事件处理器是进度追踪点。它只在执行模式工作，从 assistant 文本中识别完成标记，不检查实际代码变更是否真的完成。

`isAssistantMessage`、`getTextContent` 是消息处理辅助函数；`extractTodoItems`、`isSafeCommand`、`markCompletedSteps` 的细节在 `utils.ts`，本文件只把它们接入生命周期。

## 修改风险

最大风险是权限边界被破坏。`PLAN_MODE_TOOLS` 中仍包含 `bash`，真正的只读约束依赖 `tool_call` 对 bash 命令的拦截以及 `utils.ts` 的正则判断。如果新增安全命令、放宽 `curl`、`sed`、`awk`、管道或重定向规则，可能让计划模式具备写文件、改依赖、发网络请求或启动进程的能力。

第二个风险是工具集合与真实工具名不同步。`PLAN_MODE_TOOLS`、`NORMAL_MODE_TOOLS` 是字符串数组，如果底层工具注册名变化，计划模式可能缺工具或误开权限。尤其是 `edit`、`write` 这类写入工具，一旦被加入计划模式，就会违背扩展语义。

第三个风险是状态恢复重复或串计划。`session_start` 通过最后一个 `plan-mode-execute` 之后的消息重新扫描 `[DONE:n]`，这是为了避免旧计划污染新计划。修改 `customType` 名称、entry 写入时机或恢复扫描范围，可能导致恢复后进度错误、旧 todo 复活或执行模式卡住。

第四个风险是模型输出格式耦合。`extractTodoItems` 只识别 `Plan:` 标题和编号列表，执行进度只识别 `[DONE:n]`。如果改提示词、改语言、改格式但不同步 `utils.ts`，UI 可能提取不到计划，或无法标记完成。

第五个风险是 UI 假设。`agent_end` 中只有 `planModeEnabled && ctx.hasUI` 时才弹出选择框；这意味着该扩展主要面向交互式 TUI。若要用于非交互模式，需要重新设计“执行/停留/细化”的决策来源，否则可能只注入计划提示但不会进入执行流程。

第六个风险是 `context` 过滤逻辑。它在非计划模式移除旧的 `plan-mode-context` 和包含 `[PLAN MODE ACTIVE]` 的用户内容，避免旧限制污染正常模式。若过滤过宽，可能误删用户真实消息；若过滤不足，恢复正常工具后模型仍可能相信自己处于只读模式。
