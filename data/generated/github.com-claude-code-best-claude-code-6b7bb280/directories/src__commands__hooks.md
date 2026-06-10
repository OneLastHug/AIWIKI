# 目录：src/commands/hooks

## 它负责什么

`src/commands/hooks` 负责内置斜杠命令 `/hooks` 的注册与启动。它不是 hooks 运行时本身，也不是 hooks 配置的解析、校验或执行核心；它更像一个“命令入口适配层”，把用户在 REPL 中输入的 `/hooks` 转换为一个 Ink/React 终端界面：`HooksConfigMenu`。

从当前代码看，这个目录的职责非常收敛：

1. 向全局命令系统声明一个名为 `hooks` 的本地 JSX 命令。
2. 在命令被调用时记录一次 analytics 事件 `tengu_hooks_command`。
3. 读取当前可用工具列表，包括普通 builtin tools 和 MCP tool 名称的上游入口。
4. 渲染 `src/components/hooks/HooksConfigMenu.tsx`，让用户浏览当前配置的 hook event、matcher 和具体 hook 详情。

这里的关键词是“浏览”。`HooksConfigMenu` 文件头部注释明确说明它是 read-only browser：用户可以逐层查看已配置的 hooks，但新增或修改 hooks 应该通过编辑 `settings.json`，或让 Claude 代为修改配置。旧的编辑 UI 只支持 command 类型 hook，而现在 hook 类型已经扩展到 command、prompt、agent、http 等，继续在菜单里维护完整编辑能力会增加维护成本，所以这个界面被定位为只读查看器。

## 直接子目录地图

`src/commands/hooks` 当前没有直接子目录，只有两个文件：

`src/commands/hooks/index.ts`：命令元信息注册文件。它导出默认对象 `hooks`，声明命令类型为 `local-jsx`，命令名为 `hooks`，描述为 `View hook configurations for tool events`，并通过 `load: () => import('./hooks.js')` 懒加载实际执行模块。

`src/commands/hooks/hooks.tsx`：命令执行文件。它导出 `call`，类型为 `LocalJSXCommandCall`。执行时获取当前 `AppState`，从 `toolPermissionContext` 推导可用工具列表，然后返回 `<HooksConfigMenu toolNames={toolNames} onExit={onDone} />`。

因此，这个目录本身不是一个复杂模块树，而是命令系统和 hooks 配置 UI 之间的一层薄入口。

和它关系最近的目录包括：

`src/components/hooks`：真正的 hooks 配置浏览 UI 所在位置，包含 `HooksConfigMenu.tsx`、`SelectEventMode.tsx`、`SelectMatcherMode.tsx`、`SelectHookMode.tsx`、`ViewHookMode.tsx`、`PromptDialog.tsx` 等组件。

`src/utils/hooks`：hooks 配置、执行、事件、session hooks、frontmatter hooks、skill hooks、http/prompt/agent hook 执行等工具逻辑所在位置。`/hooks` 命令只读取其中一部分配置管理能力，不负责执行。

`src/schemas/hooks.ts`：hooks 配置 schema 所在位置，用于描述和校验 settings 中可持久化的 hook 结构。

`src/types/hooks.ts`：hooks 相关类型定义所在位置，供 UI、执行器、工具权限流程等共享。

## 关键入口

第一层入口是 `src/commands.ts`。这里统一导入各个内置命令，其中包含：

`import hooks from './commands/hooks/index.js'`

随后 `hooks` 被放入 `COMMANDS` 数组。只要命令系统调用 `getCommands()` 或相关命令解析流程，`/hooks` 就会作为内置命令之一暴露出来。它没有 feature flag 包裹，因此根据当前片段推断，它是默认可用命令，而不是实验功能命令。

第二层入口是 `src/commands/hooks/index.ts`。这个文件定义：

`type: 'local-jsx'`

`name: 'hooks'`

`immediate: true`

`load: () => import('./hooks.js')`

`local-jsx` 表示该命令不是生成 prompt 交给模型，而是在本地渲染一个 JSX UI。`immediate: true` 表示它倾向于立即执行，而不是进入普通对话流。`load` 使用动态 import，避免在命令列表初始化时加载较重的 UI 依赖。

第三层入口是 `src/commands/hooks/hooks.tsx` 中的 `call` 函数。这个函数是实际运行 `/hooks` 时进入的代码。它会：

1. 调用 `logEvent('tengu_hooks_command', {})` 记录命令使用。
2. 通过 `context.getAppState()` 拿到当前应用状态。
3. 从 `appState.toolPermissionContext` 取工具权限上下文。
4. 调用 `getTools(permissionContext)` 获取当前工具列表。
5. 提取工具名数组 `toolNames`。
6. 渲染 `HooksConfigMenu`，并把退出回调 `onDone` 作为 `onExit` 传入。

真正的浏览状态机不在这个目录，而在 `src/components/hooks/HooksConfigMenu.tsx`。

## 主流程位置

`/hooks` 的主流程可以分成“命令注册流程”和“菜单浏览流程”。

命令注册流程位于 `src/commands.ts` 和 `src/commands/hooks/index.ts`。`src/commands.ts` 负责把 `hooks` 命令加入全局命令数组；`index.ts` 负责声明命令元信息和懒加载模块。这个阶段只决定“命令存在、叫什么、如何加载”。

菜单启动流程位于 `src/commands/hooks/hooks.tsx`。这里是 `/hooks` 从命令系统进入 UI 的桥接点。它不读取 settings 文件、不解析 hook event，也不处理按键导航，只准备工具名和退出回调。

菜单浏览主流程位于 `src/components/hooks/HooksConfigMenu.tsx`。这个组件内部维护 `modeState`，有四种主要模式：

`select-event`：选择 hook event，例如 `PreToolUse`、`PostToolUse`、`SessionStart`、`Stop`、`PreCompact`、`PostCompact` 等。

`select-matcher`：当某个事件支持 matcher 时，进入 matcher 选择层。例如 tool 相关事件通常按 `tool_name` 匹配，`SessionStart` 按 `source` 匹配，`PreCompact` 按 `trigger` 匹配。

`select-hook`：在某个 event + matcher 下选择具体 hook。

`view-hook`：查看单个 hook 的详情。

菜单的数据整理主要通过 `src/utils/hooks/hooksConfigManager.ts` 完成。当前片段中可以看到这些关键函数被 `HooksConfigMenu` 使用：

`getHookEventMetadata`：提供各类 HookEvent 的摘要、说明和 matcher 元信息。

`groupHooksByEventAndMatcher`：将 AppState 中的 hook 配置按 event 和 matcher 分组。

`getSortedMatchersForEvent`：获取某个 event 下排序后的 matcher。

`getHooksForMatcher`：获取某个 event + matcher 下的 hook 列表。

`getMatcherMetadata`：判断某个 event 是否支持 matcher，以及 matcher 对应字段和值域。

此外，`HooksConfigMenu` 会读取 settings 状态，判断 `disableAllHooks` 和 `allowManagedHooksOnly` 等策略。若 hooks 被禁用，它会显示一个禁用说明界面，并提示配置的 hooks 当前不会运行。若没有禁用，则进入 event -> matcher -> hook -> detail 的只读浏览流程。

真正执行 hooks 的主流程不在 `src/commands/hooks`。从邻近上下文看，执行逻辑分散在 `src/utils/hooks`、`src/services/tools/toolHooks.ts`、`src/services/tools/toolExecution.ts`、`src/services/compact/compact.ts`、`src/screens/REPL.tsx`、`src/commands/clear/conversation.ts` 等位置。例如工具执行前后的 `PreToolUse` / `PostToolUse`、压缩前后的 `PreCompact` / `PostCompact`、会话启动和结束的 `SessionStart` / `SessionEnd`，都由各自业务流程触发，而不是由 `/hooks` 菜单触发。

## 推荐阅读顺序

建议先读 `src/commands/hooks/index.ts`。这个文件很短，可以快速理解 `/hooks` 在命令系统里的声明方式：它是 `local-jsx` 命令，通过动态 import 加载实际实现。

第二步读 `src/commands/hooks/hooks.tsx`。这里能看到命令真正做的事情：记录事件、取 AppState、收集工具名、渲染 `HooksConfigMenu`。读完这里就能明确：`src/commands/hooks` 本身只是一个入口，不是完整 hooks 子系统。

第三步读 `src/components/hooks/HooksConfigMenu.tsx`。这是理解 `/hooks` 用户界面的核心文件。重点看 `ModeState`、`modeState.mode` 的四种分支，以及它如何调用 `SelectEventMode`、`SelectMatcherMode`、`SelectHookMode`、`ViewHookMode`。

第四步读 `src/utils/hooks/hooksConfigManager.ts`。这里定义了 hook event 的展示元数据，并提供配置分组、matcher 排序和 hook 查询能力。对于 overview 层级，不必逐行研究每种 event 的说明，只要理解它是 UI 和 settings 配置之间的整理层即可。

第五步再看 `src/utils/hooks/hooksSettings.ts` 和 `src/schemas/hooks.ts`。前者更靠近“从配置中拿到 hooks”的逻辑，后者更靠近“配置应该长什么样”的 schema。读这两个文件可以补齐 `/hooks` 菜单为什么能展示 settings 中的 hook 配置。

最后再按需求跳到运行时位置：工具相关看 `src/services/tools/toolHooks.ts` 和 `src/services/tools/toolExecution.ts`；会话相关看 `src/utils/hooks/sessionHooks.ts`、`src/screens/REPL.tsx`；压缩相关看 `src/services/compact/compact.ts` 和 `src/commands/compact/compact.ts`。这些才是 hook 被实际触发和执行的地方。

## 常见误区

第一个误区是把 `src/commands/hooks` 当成 hooks 系统的核心。实际上它只是 `/hooks` 命令入口。配置解析、事件元数据、执行器、session hook、tool hook 都在其他目录中。

第二个误区是以为 `/hooks` 可以编辑 hooks。根据 `HooksConfigMenu` 的注释和实现，它当前是只读浏览器。新增、修改、禁用 hooks 应该通过 settings 文件或其他配置写入流程完成。

第三个误区是把 React hooks 和 Claude Code hooks 混在一起。这里的 `hooks` 主要指 Claude Code 的事件钩子，例如 `PreToolUse`、`PostToolUse`、`SessionStart`、`Stop` 等；而 `useState`、`useMemo`、`useKeybinding` 这些才是 React/Ink 层面的 hooks。两者名称相同，但语义完全不同。

第四个误区是认为 `/hooks` 会触发某个 hook。它只展示配置，不执行配置中的命令、prompt、agent 或 http hook。真正触发发生在工具调用、用户提交 prompt、session start/end、compact、MCP elicitation 等业务流程中。

第五个误区是只看 builtin tools。`hooks.tsx` 先传入 builtin tool names，而 `HooksConfigMenu` 内部还会合并 `mcp.tools.map(tool => tool.name)`，所以 UI 中用于 matcher 展示的工具名包含 MCP 工具。只从 `getTools(permissionContext)` 看会漏掉这部分动态工具。

第六个误区是忽略策略配置。`HooksConfigMenu` 会检查 `disableAllHooks` 和 `allowManagedHooksOnly`，并区分普通 settings 与 `policySettings`。这意味着同样有 hooks 配置，界面也可能显示“已禁用”或“受策略限制”，不能仅凭 settings 中存在 hooks 就判断它们一定会运行。
