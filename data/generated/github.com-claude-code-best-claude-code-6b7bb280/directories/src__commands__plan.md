# 目录：src/commands/plan

## 它负责什么

`src/commands/plan` 是内置斜杠命令 `/plan` 的本地命令实现目录，职责很集中：让用户在交互式会话中手动进入 plan mode，或在已经处于 plan mode 时查看、打开当前会话的计划文件。它不是完整的 plan mode 系统本身，而是 plan mode 的一个用户入口。

从当前代码看，这个目录处理的是“命令层”的事情：注册 `/plan` 命令、处理 Remote Control 下的可调用性、切换当前会话的权限模式、读取计划文件内容、把计划渲染成终端可显示文本，以及在本地编辑器中打开计划文件。真正的 plan mode 工具协议、模型提示词、退出审批、计划写入与恢复等能力分散在邻近模块，例如 `packages/builtin-tools/src/tools/EnterPlanModeTool/EnterPlanModeTool.ts`、`packages/builtin-tools/src/tools/ExitPlanModeTool/ExitPlanModeV2Tool.ts`、`src/utils/plans.ts`、`src/utils/permissions/permissionSetup.ts` 等。

换句话说，`src/commands/plan` 可以理解为“用户手动控制 plan mode 的命令壳”。它把 `/plan` 输入转成 AppState 权限模式变化，或把已有计划文件展示出来；但 plan mode 的完整生命周期不是由这个目录单独完成。

## 直接子目录地图

当前 `src/commands/plan` 没有直接子目录，只有三个文件：

`src/commands/plan/index.ts`：命令注册入口，声明 `/plan` 的元信息、参数提示、加载方式和 Remote Control 安全规则。

`src/commands/plan/plan.tsx`：命令执行主体，包含进入 plan mode、展示当前 plan、执行 `/plan open` 打开编辑器等逻辑。

`src/commands/plan/index.test.ts`：针对命令注册层的轻量测试，主要验证 Remote Control 场景下哪些 `/plan` 调用允许、哪些禁止。

目录结构说明上，它不是大目录，也没有按子功能拆分；阅读时应把它作为一个非常薄的 command module 来看。

## 关键入口

最直接的入口是 `src/commands/plan/index.ts`。这里导出默认命令对象 `plan`，其关键字段包括：

`name: 'plan'`：注册命令名 `/plan`。

`type: 'local-jsx'`：说明这是一个本地 JSX 命令，执行结果可以借助 Ink/React 组件渲染，但最终由命令框架处理。

`description: 'Enable plan mode or view the current session plan'`：概括了命令的两种行为：启用 plan mode 或查看当前计划。

`argumentHint: '[open|<description>]'`：提示支持 `/plan open`，也支持传入一段描述。

`load: () => import('./plan.js')`：真正执行逻辑被懒加载到 `plan.tsx`，这符合仓库中命令系统常见的“index 注册、实现文件懒加载”模式。

`bridgeSafe: true` 和 `getBridgeInvocationError()` 是这个命令比较值得注意的地方。它允许通过 Remote Control 调用普通 `/plan` 或 `/plan <description>`，但明确禁止 `/plan open`，因为打开本地编辑器依赖当前机器的交互环境，不适合远程控制通道。

命令被纳入全局命令表的位置在 `src/commands.ts`。该文件导入 `src/commands/plan/index.js`，并把 `plan` 放进 `COMMANDS()` 返回的内置命令数组中。因此 `/plan` 的可发现性和调度入口来自全局 commands registry，而不是 `src/main.tsx` 中单独硬编码。

## 主流程位置

核心主流程在 `src/commands/plan/plan.tsx` 的 `call(onDone, context, args)` 函数。

第一段流程是“当前不在 plan mode 时进入 plan mode”。函数通过 `context.getAppState()` 读取 `appState.toolPermissionContext.mode`。如果当前模式不是 `'plan'`，它会调用 `handlePlanModeTransition(currentMode, 'plan')` 记录模式迁移，然后通过 `setAppState()` 更新 `toolPermissionContext`。更新时组合使用 `prepareContextForPlanMode()` 和 `applyPermissionUpdate()`，最终把权限模式设置为 session 级别的 `plan`。如果用户传入了描述文本，并且不是 `open`，命令会通过 `onDone('Enabled plan mode', { shouldQuery: true })` 表示进入 plan mode 后还要继续触发一次模型查询；如果只是 `/plan`，则只返回 `Enabled plan mode`。

第二段流程是“已经在 plan mode 时查看计划”。此时命令调用 `getPlan()` 读取当前会话计划内容，并用 `getPlanFilePath()` 得到计划文件路径。二者来自 `src/utils/plans.ts`。如果没有内容，直接返回 `Already in plan mode. No plan written yet.`。这说明 `/plan` 不负责生成计划；它只展示已经存在的计划文件。

第三段流程是“已经在 plan mode 且输入 `/plan open`”。命令解析 `args.trim().split(/\s+/)`，如果第一个参数是 `open`，就调用 `editFileInEditor(planPath)` 尝试用外部编辑器打开计划文件。成功或失败都通过 `onDone()` 返回文本结果。Remote Control 中这个分支在 `index.ts` 已被拦截。

第四段流程是“渲染当前计划”。如果有计划内容且不是 `open`，命令通过 `getExternalEditor()` 和 `toIDEDisplayName()` 获取编辑器展示名，然后渲染 `PlanDisplay` 组件。该组件显示标题 `Current Plan`、计划文件路径、计划内容，并在可识别编辑器时提示可以使用 `"/plan open"` 编辑。最后通过 `renderToString(display)` 把 JSX 渲染成字符串交给 `onDone(output)`。

计划文件的底层位置和命名逻辑不在本目录，而在 `src/utils/plans.ts`。该模块负责 `getPlansDirectory()`、`getPlanSlug()`、`getPlanFilePath()`、`getPlan()` 等能力。根据当前片段推断，计划默认写在 Claude 配置目录下的 `plans` 子目录，也可以通过 settings 中的 `plansDirectory` 指定项目内路径；该推断依据是 `getPlansDirectory()` 对 `settings.plansDirectory` 和 `getClaudeConfigHomeDir()` 的处理。

与模型主动进入 plan mode 对应的是 `packages/builtin-tools/src/tools/EnterPlanModeTool/EnterPlanModeTool.ts`。它也会调用 `handlePlanModeTransition()`、`prepareContextForPlanMode()`、`applyPermissionUpdate()`，但它是工具调用路径，带有工具 schema、权限交互、工具结果映射和模型提示。退出 plan mode 的主流程在 `packages/builtin-tools/src/tools/ExitPlanModeTool/ExitPlanModeV2Tool.ts`，其中包含读取或写回 plan、审批、恢复权限模式等逻辑。`src/commands/plan` 本身不处理退出审批。

## 推荐阅读顺序

1. 先读 `src/commands/plan/index.ts`，确认 `/plan` 的命令元信息、懒加载方式和 Remote Control 约束。这个文件很短，可以快速建立边界感。

2. 再读 `src/commands/plan/plan.tsx`，重点看 `call()` 的三个分支：不在 plan mode 时启用、在 plan mode 但没有计划时提示、在 plan mode 且有计划时展示或打开编辑器。

3. 接着读 `src/utils/plans.ts` 中的 `getPlanFilePath()`、`getPlan()`、`getPlansDirectory()`，理解 `/plan` 展示的文件到底从哪里来、如何按 session 生成 slug、恢复会话时如何找回计划。

4. 然后看 `packages/builtin-tools/src/tools/EnterPlanModeTool/EnterPlanModeTool.ts`，对比“用户手动 `/plan` 进入”和“模型调用工具进入”两条路径的相同点与差异。

5. 最后看 `packages/builtin-tools/src/tools/ExitPlanModeTool/ExitPlanModeV2Tool.ts`，理解 plan mode 如何结束、计划如何提交给用户审批、权限模式如何恢复。

如果只想掌握本目录，前两步足够；如果要理解完整 plan mode 生命周期，需要继续读后三步。

## 常见误区

第一个误区是把 `src/commands/plan` 当成 plan mode 的完整实现。实际上它只是 `/plan` 命令入口。模型工具、权限审批、计划落盘、恢复、退出等都在其他模块。

第二个误区是认为 `/plan <description>` 会直接把描述写入计划文件。当前 `call()` 中没有写计划文件的逻辑；传入描述只是在首次进入 plan mode 时让 `onDone()` 带上 `{ shouldQuery: true }`，从而让后续模型回合处理这个描述。

第三个误区是认为 `/plan open` 总是可用。它只适合本地交互环境，`index.ts` 明确在 Remote Control 调用中拦截 `open` 子命令，原因是远程通道无法可靠打开调用端本地编辑器。

第四个误区是忽略权限模式的 session 作用域。这里通过 `applyPermissionUpdate(..., { type: 'setMode', mode: 'plan', destination: 'session' })` 设置的是会话级模式，不是永久配置。退出或恢复权限模式的细节要去看 `ExitPlanModeV2Tool` 和权限相关工具。

第五个误区是认为计划内容存在 AppState 里。`/plan` 展示时调用的是 `getPlan()`，也就是从计划文件读取内容；AppState 里主要保存当前权限上下文，而不是计划正文。
