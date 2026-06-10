# 目录：src/commands/status

## 它负责什么

`src/commands/status` 是交互式 REPL 里的 `/status` 斜杠命令入口目录。它本身不负责采集状态数据，也不直接渲染所有状态字段；它的职责更像一个很薄的“命令适配层”：把 `/status` 注册成一个 `local-jsx` 命令，并在执行时打开统一的 `Settings` 面板，默认定位到 `Status` 标签页。

从当前片段看，`/status` 展示的范围包括版本、会话、当前工作目录、账号、API provider、模型、IDE、MCP、sandbox、设置来源以及系统诊断等。真正的数据拼装和 UI 展示主要下沉在 `src/components/Settings/Status.tsx`、`src/components/Settings/Settings.tsx`、`src/utils/status.js` 这一组模块里，而不是放在 `src/commands/status` 内部。

这个目录的定位可以概括为：把“用户输入 `/status`”转换为“打开 Settings 对话框并选中 Status tab”。因此阅读时不要期待这里有复杂状态检查逻辑，它只是连接命令系统和设置面板的桥。

## 直接子目录地图

`src/commands/status` 当前没有直接子目录，只有两个文件：

`src/commands/status/index.ts`：命令声明文件。定义命令名 `status`、类型 `local-jsx`、描述文本、`immediate: true`，并通过 `load: () => import('./status.js')` 延迟加载实现模块。

`src/commands/status/status.tsx`：命令执行文件。导出 `call(onDone, context)`，返回一个 React/Ink 节点：`<Settings onClose={onDone} context={context} defaultTab="Status" />`。这说明 `/status` 复用了 Settings 面板，而不是单独实现一套状态页。

因为没有子目录，这里没有进一步的领域拆分。真正值得继续看的邻近目录是 `src/components/Settings` 和 `src/utils/status.js`。

## 关键入口

第一个关键入口是 `src/commands/status/index.ts`。它导出的默认对象满足 `Command` 类型，核心字段是：

`type: 'local-jsx'` 表示该命令执行后会在终端 Ink UI 中渲染本地 JSX，而不是生成 prompt 发给模型，也不是只返回一段纯文本。

`name: 'status'` 决定用户在 REPL 中输入的斜杠命令名，即 `/status`。

`immediate: true` 表示它可以作为即时命令处理。结合 `src/screens/REPL.tsx` 里的即时命令分发逻辑看，正在处理模型请求时，带 `immediate` 的 `local-jsx` 命令可以更快打开本地界面，而不必等当前请求队列完成。

`load: () => import('./status.js')` 是懒加载入口。命令列表先注册轻量元信息，真正执行 `/status` 时才加载 `status.tsx` 编译后的模块。

第二个关键入口是 `src/commands/status/status.tsx` 的 `call()`。它接收 `LocalJSXCommandOnDone` 和 `LocalJSXCommandContext`，然后把它们传给 `Settings` 组件，并指定 `defaultTab="Status"`。这里没有条件分支、参数解析或状态计算，说明 `/status` 命令当前只负责打开指定 tab。

第三个相关入口在 `src/commands.ts`。该文件导入 `status from './commands/status/index.js'`，并把 `status` 放入 `COMMANDS` 数组。REPL 的斜杠命令系统最终从这里拿到内置命令集合。

## 主流程位置

主流程可以按四段理解。

第一段是命令注册。`src/commands.ts` 汇总内置命令，`src/commands/status/index.ts` 提供 `/status` 的元信息。此时只知道有一个名为 `status` 的 `local-jsx` 命令，真正实现还没有加载。

第二段是 REPL 分发。用户在交互界面输入 `/status` 后，REPL 的斜杠命令处理逻辑会在命令集合中找到 `status`。由于它是 `local-jsx` 且声明了 `immediate: true`，相关即时命令路径会优先考虑直接打开本地 JSX UI。根据当前片段推断，主要依据是 `src/screens/REPL.tsx` 中围绕 `matchingCommand?.immediate`、`matchingCommand.type === 'local-jsx'` 的处理逻辑，以及 `src/utils/handlePromptSubmit.ts` 中对 immediate local-jsx 命令的分发。

第三段是实现加载和组件创建。执行时调用 `load()` 动态导入 `src/commands/status/status.tsx`，随后调用其 `call()`。`call()` 返回 `Settings` 组件，并把 `defaultTab` 设成 `Status`。

第四段是状态页实际渲染。`src/components/Settings/Settings.tsx` 创建包含 `Status`、`Config`、`Usage` 三个 tab 的设置面板，并在打开时启动一次 `buildDiagnostics()`。`src/components/Settings/Status.tsx` 再从 AppState、bootstrap state、cwd、session storage、MCP 状态和 `src/utils/status.js` 的工具函数中组合展示内容。关键函数包括 `buildPrimarySection()`、`buildSecondarySection()`、`buildDiagnostics()`，以及来自 `src/utils/status.js` 的 `buildAccountProperties()`、`buildAPIProviderProperties()`、`buildIDEProperties()`、`buildMcpProperties()`、`buildSandboxProperties()`、`buildSettingSourcesProperties()`、`buildInstallationDiagnostics()` 等。

需要特别区分的是，`src/main.tsx` 中也有一个 `auth status` 子命令，描述为 `Show authentication status`，调用 `src/cli/handlers/auth.js` 的 `authStatus()`。那是顶层 CLI 的 `claude auth status`，不是 REPL 内的 `/status`。两者名字相近，但路径和展示范围不同。

## 推荐阅读顺序

建议先读 `src/commands/status/index.ts`，确认 `/status` 在命令系统中的声明方式，尤其是 `local-jsx`、`immediate` 和 `load()` 这三个字段。

然后读 `src/commands/status/status.tsx`。这个文件很短，但能立即看清 `/status` 并没有独立页面，而是复用 `Settings`，并默认打开 `Status` tab。

接着读 `src/commands.ts` 中导入和 `COMMANDS` 数组附近的内容，理解这个命令如何进入全局斜杠命令集合。

再读 `src/components/Settings/Settings.tsx`，看 `Status`、`Config`、`Usage` 三个 tab 的组织方式，以及诊断信息为何在 Settings 层创建 promise，而不是在 Status tab 每次挂载时重新请求。

最后读 `src/components/Settings/Status.tsx` 和 `src/utils/status.js`。前者负责状态页结构，后者负责把账号、API、IDE、MCP、sandbox、诊断等状态转换成可展示属性。对于 overview 深度，重点看函数边界即可，不必逐个诊断项追到底。

## 常见误区

第一个误区是把 `/status` 和 `claude auth status` 混为一谈。`/status` 位于 `src/commands/status`，打开交互式 Settings 状态页；`claude auth status` 注册在 `src/main.tsx` 的 `auth.command('status')` 下，主要输出认证状态，并支持 `--json`、`--text`。

第二个误区是以为 `src/commands/status/status.tsx` 负责状态采集。实际上它只返回 `Settings` 组件。状态采集和格式化主要在 `src/components/Settings/Status.tsx` 与 `src/utils/status.js`。

第三个误区是忽略 `immediate: true`。这个字段会影响 REPL 中命令的调度体验，尤其是在模型请求进行中打开本地状态面板的场景。它不是展示字段，而是执行时机相关的命令元数据。

第四个误区是把 `Status` 看成独立顶层页面。当前设计中，`Status` 是 `Settings` 面板的一个 tab。`/status` 只是以 `defaultTab="Status"` 进入同一个设置容器，因此 Esc 关闭、tab 切换、高度控制、诊断 promise 复用等行为都由 `src/components/Settings/Settings.tsx` 统一管理。

第五个误区是只读这个目录就试图理解所有状态字段来源。这个目录只能说明“如何进入状态页”，不能完整说明“每个状态值怎么算出来”。要理解字段来源，需要继续看 `src/components/Settings/Status.tsx` 的 section 构建函数和 `src/utils/status.js` 的属性构建函数。
