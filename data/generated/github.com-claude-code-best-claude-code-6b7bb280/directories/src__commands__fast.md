# 目录：src/commands/fast

## 它负责什么

`src/commands/fast` 负责 Claude Code 里的 `/fast` 命令和 Fast mode 交互入口。它不是模型推理、API 请求或限流处理的核心实现目录，而是一个很薄的命令层：把 `/fast` 注册到命令系统中，并在用户执行命令或触发快捷键时展示 Fast mode 开关界面，最终把用户选择写入 settings 和 `AppState`。

从当前代码片段看，Fast mode 的业务规则主要在 `src/utils/fastMode.ts`：例如是否启用、是否可用、当前模型是否支持、组织/账号是否禁用、冷却状态、预取状态等。`src/commands/fast` 调用这些工具函数完成校验和状态变更，但不直接承担底层判断逻辑。

这个目录的用户可见能力主要有两类：

第一类是 slash command：用户输入 `/fast`、`/fast on`、`/fast off`。无参数时打开一个 Ink 对话框；带 `on/off` 参数时直接切换。

第二类是 PromptInput 快捷入口：`src/components/PromptInput/PromptInput.tsx` 直接导入 `FastModePicker`，在 `chat:fastMode` keybinding 被触发时弹出同一个选择器。因此，这个目录既服务命令系统，也被输入框组件复用为 UI 控件。

## 直接子目录地图

`src/commands/fast` 当前没有直接子目录，只有两个文件：

`src/commands/fast/index.ts`：命令注册描述文件。它导出默认的 `fast` command metadata，声明命令类型、名称、描述、可用环境、是否隐藏、参数提示、是否 immediate，以及真正执行逻辑的动态加载入口。

`src/commands/fast/fast.tsx`：命令执行和 UI 实现文件。它导出 `call` 函数供 local JSX command 调用，也导出 `FastModePicker` 供 PromptInput 快捷键路径复用。这个文件还包含内部辅助函数 `applyFastMode` 和 `handleFastModeShortcut`。

因为目录规模很小，不需要按“子模块”理解。更准确的地图是：`index.ts` 负责挂到命令系统，`fast.tsx` 负责执行 `/fast` 和渲染选择器。

## 关键入口

`src/commands/fast/index.ts` 是命令层入口。这里定义的对象满足 `Command` 类型，关键字段包括：

`type: 'local-jsx'` 表示它是一个本地 JSX 命令，执行后可以返回 React/Ink 节点。

`name: 'fast'` 表示 slash command 名称是 `/fast`。

`description` 使用 `FAST_MODE_MODEL_DISPLAY` 动态展示目标模型，例如当前片段里显示为 `Opus 4.7`。

`isEnabled` 和 `isHidden` 都围绕 `isFastModeEnabled()`。如果环境变量或配置禁用了 Fast mode，命令会不可用或隐藏。

`argumentHint: '[on|off]'` 说明它支持直接传参。

`immediate` 来自 `shouldInferenceConfigCommandBeImmediate()`，说明该命令是否作为“推理配置类命令”立即执行，而不是进入普通消息流。根据当前片段推断，这和模型、模式、配置切换类命令的统一处理有关，依据是它没有自己实现提交到对话的逻辑，而是声明式挂在 command metadata 上。

`load: () => import('./fast.js')` 是真正执行文件的懒加载入口。也就是说，命令列表加载时只加载轻量 metadata，用户实际执行 `/fast` 时才加载 `fast.tsx`。

命令集合的注册位置在 `src/commands.ts`。该文件导入 `fast`，并在命令数组中包含它。当前搜索结果显示导入位置为 `import fast from './commands/fast/index.js'`，注册数组里也有 `fast`。

另一个关键入口是 `src/components/PromptInput/PromptInput.tsx`。它直接 `import { FastModePicker } from '../../commands/fast/fast.js';`，通过 `showFastModePicker` 状态决定是否渲染该 picker，并用 `useKeybinding('chat:fastMode', ...)` 绑定快捷键路径。

## 主流程位置

`/fast` 命令主流程在 `src/commands/fast/fast.tsx` 的 `call` 函数。

流程可以概括为：

用户执行 `/fast` 后，命令系统通过 `index.ts` 的 `load` 懒加载 `fast.tsx`，然后调用导出的 `call(onDone, context, args)`。

`call` 首先检查 `isFastModeEnabled()`。如果 Fast mode 全局不可用，直接返回 `null`，不显示 UI。

随后调用 `prefetchFastModeStatus()`。注释说明这里会在展示 picker 前获取组织级 Fast mode 状态；如果启动时已经有预取请求在进行，这里会等待它完成。这个步骤很关键，因为组织禁用时不能让用户继续切换。

接着解析参数：如果 `args` 是 `on` 或 `off`，走 `handleFastModeShortcut`。这个路径不弹 UI，而是先检查 `getFastModeUnavailableReason()`，再调用 `applyFastMode(enable, context.setAppState)`，记录 analytics 事件，最后通过 `onDone(result)` 输出结果。

如果没有 `on/off` 参数，`call` 会读取 `getFastModeUnavailableReason()`，记录 `tengu_fast_mode_picker_shown` 事件，然后返回 `<FastModePicker ... />`。这就是 `/fast` 无参数时的交互界面。

`FastModePicker` 的主流程是：读取当前 `mainLoopModel` 和 `fastMode` app state，初始化本地 `enableFastMode` 状态，展示 Dialog。用户按 Tab 或相关确认上下键时切换本地选择，按 Enter 时执行 `handleConfirm`，按 Esc 时执行 `handleCancel`。

真正写状态的是 `applyFastMode(enable, setAppState)`。启用时它会清除 Fast mode cooldown，更新 `userSettings.fastMode` 为 `true`，并在当前模型不支持 Fast mode 时把 `mainLoopModel` 切换到 `getFastModeModel()`，同时把 `mainLoopModelForSession` 置空。关闭时它把 `fastMode` app state 设为 `false`，并把用户 settings 中的 `fastMode` 写为 `undefined`。

快捷键路径的主流程在 `src/components/PromptInput/PromptInput.tsx`。它维护 `showFastModePicker`，在 `chat:fastMode` keybinding 激活时切换显示状态，然后复用 `FastModePicker`。用户完成选择后，PromptInput 的回调会关闭 picker 并把结果接入输入框/系统显示流程。根据当前片段推断，这条路径和 `/fast` 命令共享同一个 UI，但不是通过 command registry 调用 `call`，依据是 PromptInput 直接导入并渲染 `FastModePicker`。

## 推荐阅读顺序

建议先读 `src/commands/fast/index.ts`。它很短，能快速确认 `/fast` 在命令系统中的身份：local JSX command、隐藏条件、参数形式、懒加载文件。

然后读 `src/commands/fast/fast.tsx`，重点看四个符号：`call`、`FastModePicker`、`applyFastMode`、`handleFastModeShortcut`。这四个符号基本覆盖命令执行、UI 展示、状态落盘和无 UI 快捷切换。

第三步读 `src/utils/fastMode.ts`。这个文件不属于目标目录，但它是理解 Fast mode 真实规则的必要邻近上下文。`src/commands/fast` 里大量判断都来自这里，包括 `isFastModeEnabled`、`getFastModeUnavailableReason`、`isFastModeSupportedByModel`、`prefetchFastModeStatus`、`getFastModeRuntimeState`、`clearFastModeCooldown`。

第四步读 `src/commands.ts`，只需要定位 `fast` 的导入和注册位置，确认它如何进入全局 slash command 列表。

最后读 `src/components/PromptInput/PromptInput.tsx` 中和 `FastModePicker`、`chat:fastMode`、`showFastModePicker` 相关的片段，理解为什么这个目录的 UI 组件会被命令系统之外的输入框直接复用。

## 常见误区

不要把 `src/commands/fast` 当成 Fast mode 的完整实现。它只负责命令和交互层，真正的可用性判断、组织状态、模型支持、冷却状态、API 拒绝后的处理，都在 `src/utils/fastMode.ts` 等邻近模块。

不要认为 `/fast` 一定会展示 UI。`/fast on` 和 `/fast off` 会走 shortcut 路径，直接调用状态更新并通过 `onDone` 返回结果；只有无参数或非 `on/off` 参数时才会展示 `FastModePicker`。

不要忽略组织状态预取。`call` 在展示 picker 前会等待 `prefetchFastModeStatus()`，这是为了避免用户在组织禁用或账号不满足条件时看到可切换的 UI。

不要把 `fastMode` app state 和运行时 cooldown 混为一谈。`fastMode` 表示用户是否启用该模式；`getFastModeRuntimeState()` 表示当前 Fast mode 是否因为 rate limit 或 overloaded 进入冷却。UI 会把 cooldown 作为提示展示，但它不是用户开关本身。

不要把模型切换看成独立命令。启用 Fast mode 时，如果当前 `mainLoopModel` 不支持，`applyFastMode` 会自动切到 `getFastModeModel()`。因此 `/fast on` 可能同时改变 `fastMode` 和当前主循环模型。

不要在文档里保留源码中的真实外部链接。`FastModePicker` 底部包含 Learn more 的外部文档链接；在学习文档中如需提及，应写成 `[URL已移除]`。
