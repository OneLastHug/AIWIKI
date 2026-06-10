# 目录：src/commands/poor

## 它负责什么

`src/commands/poor` 实现的是 CLI 里的“穷鬼模式 / Poor mode”开关命令。它的目标很直接：让用户通过 `/poor` 在交互式会话中切换一个省 token 的运行状态。开启后，系统会跳过若干后台增强能力，例如 `extract_memories`、`prompt_suggestion`，并在部分消费点进一步跳过 `verification_agent`、`session memory`、`agent summary`、`auto dream` 等会额外消耗模型调用或上下文预算的逻辑。

这个目录本身不实现这些后台能力，也不直接改动主查询循环。它只提供三类东西：命令元数据、命令执行函数、全局可查询的 poor mode 状态。真正的行为收敛发生在仓库其他模块中：那些模块通过 `isPoorModeActive()` 判断当前是否应跳过昂贵逻辑。

状态是持久化的。`poorMode.ts` 会读取 `settings.json` 里的 `poorMode` 字段，并通过 `updateSettingsForSource('userSettings', { poorMode })` 写回用户设置。关闭时写入的是 `poorMode: undefined`，意图是移除该键，使设置文件保持干净，而不是显式保存 `false`。

## 直接子目录地图

这个目录很小，只有一个测试子目录：

`src/commands/poor`：命令实现目录，包含 `/poor` 的注册描述、执行逻辑和状态管理模块。

`src/commands/poor/__tests__`：针对 poor mode 状态读写的单元测试目录。当前重点测试 `poorMode.ts` 是否从 settings 初始读取、是否能写入 `userSettings`、关闭时是否用 `undefined` 清理配置项，以及多次切换后内存状态是否一致。

没有更深层的业务子模块，也没有 UI 组件、服务层或独立 provider。这个目录更像一个轻量 command package。

## 关键入口

第一个入口是 `src/commands/poor/index.ts`。它导出默认的 `Command` 定义，核心字段包括：

`type: 'local'`：说明它是本地命令，不是远程或外部命令。

`name: 'poor'`：对应用户输入的 `/poor`。

`description`：描述为切换 poor mode，并说明会禁用 `extract_memories` 和 `prompt_suggestion` 来节省 token。

`supportsNonInteractive: false`：表示它不支持非交互式模式，主要面向 REPL slash command。

`load: () => import('./poor.js')`：采用懒加载方式，真正执行命令时才加载 `poor.ts`。

第二个入口是 `src/commands/poor/poor.ts`。这里导出 `call: LocalCommandCall`，是 `/poor` 被触发后的执行函数。它会读取 `isPoorModeActive()`，取反得到新状态，调用 `setPoorMode(newState)` 持久化，然后通过 `context.setAppState` 同步调整 `promptSuggestionEnabled`。最后返回一条文本结果，例如 `Poor mode ON` 或 `Poor mode OFF`。

第三个入口是 `src/commands/poor/poorMode.ts`。这是其他模块真正依赖的状态 API，暴露两个函数：

`isPoorModeActive()`：读取并缓存 poor mode 当前状态。首次调用时从 `getInitialSettings().poorMode === true` 初始化，后续返回模块级变量 `poorModeActive`。

`setPoorMode(active: boolean)`：更新模块级缓存，并写入用户设置源 `userSettings`。开启时保存 `poorMode: true`，关闭时保存 `poorMode: undefined`。

## 主流程位置

命令注册主流程在 `src/commands.ts`。这里通过 feature flag 控制是否装载 poor command：

`feature('POOR') ? require('./commands/poor/index.js').default : null`

随后在命令数组中通过 `...(poor ? [poor] : [])` 注入。也就是说，`/poor` 不是无条件存在的命令，必须在构建或运行时启用 `POOR` feature 后才会进入 slash command 列表。

用户执行 `/poor` 后，流程大致是：

1. 命令系统从 `src/commands.ts` 提供的列表中找到 `poor`。
2. `index.ts` 的 `load()` 动态导入 `src/commands/poor/poor.ts`。
3. `poor.ts` 的 `call()` 执行状态翻转。
4. `setPoorMode()` 把新状态写入 settings，并更新模块级缓存。
5. `call()` 同步更新当前 `AppState.promptSuggestionEnabled`，让当前会话里的 prompt suggestion 状态立即反映变化。
6. 后续各业务模块调用 `isPoorModeActive()`，决定是否跳过额外后台任务。

主流程的消费点分散在目录外。`src/query/stopHooks.ts` 在每轮结束后的 stop hook 中检查 poor mode，开启时跳过 `executePromptSuggestion`、`executeExtractMemories` 和 `executeAutoDream`。`src/constants/prompts.ts` 在构建 session guidance 时检查 poor mode，开启时不注入 verification agent 的强制说明。`src/services/SessionMemory/sessionMemory.ts` 在 session memory 抽取前检查 poor mode，开启时直接返回。`src/services/AgentSummary/agentSummary.ts` 在 agent summary 定时任务触发时检查 poor mode，开启时跳过本次 summary 并重新调度。

此外，`src/components/Settings/Config.tsx` 也提供了设置界面的 poor mode 开关。它直接调用 `isPoorModeActive()` 和 `setPoorMode(enabled)`，并同步设置 `promptSuggestionEnabled: !enabled`。这说明 poor mode 不只可通过 `/poor` 命令切换，也可通过设置 UI 切换；两者共享同一个状态模块和 settings 字段。

## 推荐阅读顺序

建议先读 `src/commands/poor/index.ts`，因为它说明 `/poor` 作为命令暴露给命令系统时的形态，包括命令名、描述、是否支持非交互、懒加载目标。

然后读 `src/commands/poor/poor.ts`。这里能看到用户执行 `/poor` 后的完整交互行为：翻转状态、写入状态、同步 `AppState`、返回提示文本。这个文件最适合理解“命令本身做了什么”。

第三步读 `src/commands/poor/poorMode.ts`。这是 poor mode 的核心状态边界。要重点注意它的模块级缓存 `poorModeActive`，以及首次读取 settings、后续写回 settings 的机制。

第四步跳到 `src/commands.ts`，看 `feature('POOR')` 如何控制命令是否注册。这一步能避免误以为 `/poor` 永远存在。

第五步再读几个外部消费点：`src/query/stopHooks.ts`、`src/constants/prompts.ts`、`src/services/SessionMemory/sessionMemory.ts`、`src/services/AgentSummary/agentSummary.ts`。这些地方才体现 poor mode 的实际节省效果。

最后读 `src/commands/poor/__tests__/poorMode.test.ts`。测试文件说明这个功能曾经有过“只存在内存中、重启后丢失”的问题，因此当前实现强调 settings 持久化。

## 常见误区

第一个误区是把 poor mode 理解成只影响 `/poor` 命令返回文本。实际上 `/poor` 只是开关入口，真正效果来自其他模块对 `isPoorModeActive()` 的检查。这个目录是状态和命令层，不是所有节省逻辑的实现地。

第二个误区是认为 poor mode 只禁用 `extract_memories` 和 `prompt_suggestion`。命令描述中重点提到这两个能力，但从当前片段看，其他模块也会借用这个状态跳过更多后台逻辑，例如 verification guidance、session memory、agent summary、auto dream。更准确的说法是：`src/commands/poor` 定义了一个省 token 模式，至少明确覆盖 `extract_memories` 和 `prompt_suggestion`，并被多个后台增强功能作为跳过条件使用。

第三个误区是认为关闭 poor mode 会写入 `poorMode: false`。实际 `setPoorMode(false)` 写入的是 `poorMode: undefined`，测试也明确断言这一点。根据当前片段推断，settings 更新层会把 `undefined` 视为删除或清理该配置项，依据是测试注释写明“key should be removed to keep settings clean”。

第四个误区是忽略 feature flag。`/poor` 在 `src/commands.ts` 里受 `feature('POOR')` 控制；如果没有启用 `POOR`，命令不会注册。不过部分源码文件可能仍然静态或动态引用 `poorMode.ts`，是否生效要看对应调用点是否也包在 feature 判断内。

第五个误区是把 `promptSuggestionEnabled` 当成唯一状态源。当前会话 UI 状态会被 `poor.ts` 和设置界面同步修改，但跨会话的权威状态来自 settings 中的 `poorMode` 字段，以及 `poorMode.ts` 的 `isPoorModeActive()` / `setPoorMode()`。
