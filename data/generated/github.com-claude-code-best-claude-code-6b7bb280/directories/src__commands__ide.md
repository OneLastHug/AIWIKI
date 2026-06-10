# 目录：src/commands/ide

## 它负责什么

`src/commands/ide` 是交互式 `/ide` slash command 的实现目录，负责在 Claude Code 的 REPL 中管理 IDE 集成：发现已安装并运行 Claude Code 扩展或插件的 IDE、让用户选择要连接的 IDE、把选中的 IDE 注入为动态 MCP server、断开当前 IDE 连接，以及在没有检测到可用扩展时触发扩展/插件安装流程。

这个目录本身不实现底层 IDE 探测、插件安装、MCP transport 或 REPL 状态容器。它更像一个命令层的“编排入口”：把 `src/utils/ide.ts` 提供的 IDE 检测能力、`src/services/mcp/*` 提供的 MCP 连接能力、`src/state/AppState.tsx` 提供的运行态状态、以及 Ink/React 对话框组件组合成用户可操作的 `/ide` 命令界面。

它覆盖两个主要使用场景：

1. 用户输入 `/ide`：显示 IDE 选择对话框，连接、切换或断开 IDE。
2. 用户输入 `/ide open`：选择一个检测到的 IDE，并尝试把当前 project 或 worktree 打开到 IDE 中。

从职责边界看，`src/commands/ide` 只处理命令交互和动态配置更新；真正的自动连接逻辑在 `src/hooks/useIDEIntegration.tsx`，真正的 IDE lockfile 探测和扩展安装在 `src/utils/ide.ts`，真正的 MCP 连接生命周期在 `src/services/mcp/MCPConnectionManager.tsx`、`src/services/mcp/useManageMCPConnections.ts`、`src/services/mcp/client.ts`。

## 直接子目录地图

当前目录没有直接子目录，只有两个文件：

`src/commands/ide/index.ts`：命令注册描述文件。它声明 `/ide` 的命令名、描述、参数提示和 lazy load 入口。

`src/commands/ide/ide.tsx`：命令主体。这里包含 `/ide` 的 `call()` 函数、多个 Ink/React 选择界面组件，以及 IDE 动态 MCP 配置的创建、删除和连接结果等待逻辑。

因此阅读这个目录时，不需要按子目录分层理解；重点是把 `index.ts` 看作“命令元数据”，把 `ide.tsx` 看作“命令运行流程”。

## 关键入口

第一层入口是 `src/commands/ide/index.ts`。它导出默认命令对象：

`name: 'ide'` 表示 slash command 名称是 `/ide`；`type: 'local-jsx'` 表示这是一个本地 JSX 命令，会返回 React/Ink 节点；`argumentHint: '[open]'` 表明它支持可选参数 `open`；`load: () => import('./ide.js')` 表示命令主体按需加载。

第二层入口在 `src/commands.ts`。这里通过 `import ide from './commands/ide/index.js'` 引入命令定义，并把 `ide` 放进内置命令列表。也就是说，`/ide` 并不是 Commander 顶层子命令，而是 REPL 内 slash command 系统中的一员。

第三层入口是 `src/commands/ide/ide.tsx` 中导出的 `call(onDone, context, args)`。这是 `/ide` 被实际执行时进入的函数。它接收命令完成回调 `onDone`、本地 JSX 命令上下文 `LocalJSXCommandContext`，以及用户传入参数 `args`。该函数会先记录 analytics 事件，然后根据 `args` 走 `/ide open` 分支或常规 `/ide` 分支。

常规分支中，`call()` 会读取 `context.options.dynamicMcpConfig` 和 `context.onChangeDynamicMcpConfig`。这两个字段是 `/ide` 和 REPL/MCP 系统之间最重要的桥：命令通过更新 `dynamicMcpConfig.ide` 来声明“当前会话应该连接这个 IDE MCP server”。

## 主流程位置

`/ide` 的主流程集中在 `src/commands/ide/ide.tsx` 的 `call()` 和 `IDECommandFlow`。

当用户输入 `/ide open` 时，`call()` 会先通过 `getCurrentWorktreeSession()` 判断当前是否处于 worktree session。如果是，则目标路径使用 worktree 路径；否则使用 `getCwd()`。随后调用 `detectIDEs(true)` 检测 IDE，过滤出 `isValid` 的可用 IDE。如果没有可用 IDE，直接 `onDone('No IDEs with Claude Code extension detected.')`。如果有，则返回 `IDEOpenSelection` 对话框。用户选择后，对于 VS Code、Cursor、Windsurf 这类 Code 系 IDE，会调用 `execFileNoThrow('code', [targetPath])` 尝试打开路径；其他 IDE 则提示用户手动打开。

当用户输入普通 `/ide` 时，`call()` 先调用 `detectIDEs(true)`。如果完全没有检测到 IDE 扩展，并且上下文提供了 `onInstallIDEExtension`，还会调用 `detectRunningIDEs()` 检测正在运行的 IDE，进入安装扩展/插件流程：多个 IDE 时显示 `RunningIDESelector`，单个 IDE 时通过 `InstallOnMount` 在组件挂载后触发安装。JetBrains 系 IDE 安装后会提示重启 IDE。

如果检测到了 IDE lockfile，`call()` 会把结果拆成 `availableIDEs` 和 `unavailableIDEs`。其中 `availableIDEs` 是当前 cwd 与 IDE workspace 匹配的 IDE；`unavailableIDEs` 是运行着但 workspace/project 目录不匹配的 IDE。然后通过 `findCurrentIDE()` 从 `dynamicMcpConfig.ide` 中反查当前已连接 IDE，最后返回 `IDECommandFlow`。

`IDECommandFlow` 是连接状态编排点。用户在 `IDEScreen` 中选择 IDE 后，`handleSelectIDE()` 会构造新的 `dynamicMcpConfig`。如果选择 `None`，它会删除 `newConfig.ide`，并在存在已连接 `ideClient` 时清理 MCP client、IDE MCP tools 和 IDE MCP commands，同时调用 `clearServerCache('ide', ideClient.config)`。如果选择某个 IDE，它会写入：

`type: 'ws-ide'` 或 `type: 'sse-ide'`、`url`、`ideName`、`authToken`、`ideRunningInWindows`、`scope: 'dynamic'`

这个配置随后由 REPL 中的 `MCPConnectionManager` 消费。`src/screens/REPL.tsx` 中持有 `dynamicMcpConfig` state，并在渲染处把它传给 `<MCPConnectionManager dynamicMcpConfig={dynamicMcpConfig} ...>`。连接真正建立后，`IDECommandFlow` 通过 `useAppState()` 观察 `s.mcp.clients.find(c => c.name === 'ide')`，根据 client 状态输出连接成功、失败或超时。

需要注意，自动连接不在这个目录里。REPL 初始化阶段会调用 `useIDEIntegration()`，位于 `src/hooks/useIDEIntegration.tsx`。它会基于全局配置、`--ide` 标志、内置 IDE terminal、`CLAUDE_CODE_SSE_PORT`、环境变量等条件，调用 `initializeIdeIntegration()` 并自动写入 `dynamicMcpConfig.ide`。`/ide` 命令则是用户手动管理这一配置的入口。

## 推荐阅读顺序

1. 先读 `src/commands/ide/index.ts`，理解 `/ide` 如何以 `local-jsx` 命令注册，以及为什么主体是 lazy import。
2. 再读 `src/commands.ts` 中导入和命令数组附近，确认 `/ide` 属于内置 slash command 列表。
3. 接着读 `src/commands/ide/ide.tsx` 的 `call()`，先分清 `/ide open` 和普通 `/ide` 两条分支。
4. 然后读 `IDECommandFlow` 和 `IDEScreen`，重点看 `dynamicMcpConfig.ide` 如何被创建、删除，以及连接结果如何从 AppState 的 MCP clients 中观察。
5. 再跳到 `src/hooks/useIDEIntegration.tsx`，理解自动连接与手动 `/ide` 的关系。
6. 最后读 `src/utils/ide.ts` 的 `detectIDEs()`、`findAvailableIDE()`、`maybeInstallIDEExtension()`，以及 `src/services/mcp/client.ts` 中 `sse-ide`、`ws-ide` 分支，补齐底层检测和连接细节。

## 常见误区

第一个误区是把 `/ide` 当成普通顶层 CLI 命令。它不是 `claude ide` 这种 Commander 子命令，而是 REPL 内的 slash command。顶层 CLI 相关的是 `--ide` flag，它会把 `autoConnectIdeFlag` 传入 REPL；真正的 `/ide` 命令注册在 `src/commands.ts`。

第二个误区是认为 `src/commands/ide` 负责 IDE 自动连接。根据当前片段推断，自动连接主要由 `src/hooks/useIDEIntegration.tsx` 触发，依据是 REPL 中直接调用 `useIDEIntegration()`，并由该 hook 写入 `setDynamicMcpConfig()`。`src/commands/ide` 主要负责用户显式执行 `/ide` 时的选择和切换。

第三个误区是认为连接 IDE 等于直接调用 IDE API。实际这里走的是 MCP 抽象。`/ide` 只是把 IDE 暴露的 SSE 或 WebSocket endpoint 写成 `sse-ide` 或 `ws-ide` 类型的动态 MCP server 配置；后续连接、工具注册、通知和错误处理由 MCP 层完成。

第四个误区是忽略 cwd/workspace 校验。`detectIDEs(true)` 会返回有效和无效 IDE，`ide.tsx` 会把 workspace 不匹配的 IDE 显示为 unavailable，而不是直接连接。这样可以避免多个 IDE 窗口同时运行时连到错误项目。

第五个误区是把 `None` 当成纯 UI 选项。选择 `None` 不只是关闭对话框，它会删除动态 MCP 配置，并在已有连接时清理 `ide` client、`mcp__ide__*` tools 和 commands，防止断开后残留 IDE 工具。
