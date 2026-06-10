# 目录：src/entrypoints

## 它负责什么

`src/entrypoints` 是这个 CLI 工程的“入口层”。它不承载完整业务逻辑，而是负责在进程刚启动时做分流：根据命令行参数、feature flag、运行环境，决定是走轻量快速路径，还是加载完整 CLI 主程序。

从当前代码看，这个目录主要承担四类职责：

第一，提供真正的 CLI 启动文件 `src/entrypoints/cli.tsx`。它是带有 `#!/usr/bin/env bun` 的 Bun 可执行入口，先处理 `--version`、特殊 MCP server、daemon worker、remote-control、background session、template job、runner 等快速路径；只有没有命中特殊路径时，才动态加载 `src/main.tsx`。

第二，提供全局初始化逻辑 `src/entrypoints/init.ts`。完整 CLI 进入 `src/main.tsx` 后，会调用这里的 `init()`，完成配置系统启用、环境变量应用、优雅退出、账号信息预热、远程配置加载、policy limits、mTLS、proxy、Sentry、Langfuse、API 预连接、Windows shell 适配、LSP 清理注册等启动期基础设施。

第三，提供 MCP stdio server 入口能力 `src/entrypoints/mcp.ts`。这里把内部工具系统包装成 MCP server，对外暴露工具列表和工具调用能力，核心函数是 `startMCPServer(cwd, debug, verbose)`。

第四，集中放置 SDK 对外类型与 schema。`src/entrypoints/sdk` 以及顶层的 `agentSdkTypes.ts`、`sandboxTypes.ts` 等文件更像“公开接口边界”，用于 SDK 消费者、Agent SDK、runtime/control/core 类型生成和运行时校验。

这个目录的定位可以概括为：进程入口、启动分流、初始化边界、SDK 类型出口。真正的 Commander 命令定义、交互 UI、查询循环、API 请求、工具实现都在邻近目录中。

## 直接子目录地图

`src/entrypoints` 当前只有一个直接子目录：

`src/entrypoints/sdk`：SDK 类型与 schema 区域。这里包含 `coreSchemas.ts`、`coreTypes.ts`、`coreTypes.generated.ts`、`controlSchemas.ts`、`controlTypes.ts`、`runtimeTypes.ts`、`toolTypes.ts`、`settingsTypes.generated.ts`、`sdkUtilityTypes.ts` 等文件。根据当前片段推断，这个目录服务于 SDK 的公共类型定义和运行时校验：schema 文件用于 Zod 校验，generated 类型由脚本生成，入口型类型文件再把生成类型、工具类型、sandbox 类型等重新导出。

顶层文件与 `sdk` 子目录形成互补：顶层是可执行入口和少量跨 SDK 类型，`sdk` 子目录是更系统化的 SDK 类型集合。

## 关键入口

`src/entrypoints/cli.tsx` 是最关键入口，也是整个 CLI 的真正启动点。它的设计重点是“尽量晚加载”。文件开头先加载 `performanceShim`，补齐 `MACRO` fallback，处理部分环境修正；随后 `main()` 根据 `process.argv` 依次判断快速路径。比如 `--version` 直接打印版本，不加载完整 CLI；`--dump-system-prompt` 只加载配置、模型和 prompt；`--claude-in-chrome-mcp`、`--chrome-native-host`、`--computer-use-mcp` 会进入对应 MCP/native host；`--acp` 进入 ACP agent；`remote-control`、`rc`、`bridge` 等进入 bridge；`daemon` 或 `--daemon-worker` 进入 daemon；`--bg`、`ps/logs/attach/kill` 进入后台会话兼容路径；最后才 `import('../main.jsx')` 并调用 `cliMain()`。

`src/entrypoints/init.ts` 是完整 CLI 的启动初始化入口。它导出 `init` 和 `initializeTelemetryAfterTrust`。`init` 使用 `memoize` 包装，说明它预期在一次进程生命周期内只执行一次。它不负责解析命令，而是建立运行环境：配置、证书、proxy、诊断、远程设置、策略限制、用户、追踪、清理回调等。

`src/entrypoints/mcp.ts` 是 MCP server 入口。它创建 `@modelcontextprotocol/sdk` 的 `Server`，通过 `ListToolsRequestSchema` 返回内部工具的 JSON schema 描述，通过 `CallToolRequestSchema` 找到对应工具并调用。它把 Claude Code 内部工具系统接到 MCP stdio transport 上。

`src/entrypoints/sdk/coreTypes.ts` 代表 SDK 类型出口的风格：注释说明类型由 `coreSchemas.ts` 生成，修改方式是先改 Zod schema，再运行生成脚本。它还导出 `HOOK_EVENTS`、`EXIT_REASONS` 等运行时常量。

## 主流程位置

主流程不是完整写在 `src/entrypoints` 内，而是从这里跳转出去。

启动链路是：`src/entrypoints/cli.tsx` 解析参数。如果命中特殊模式，就直接动态导入对应模块并执行，例如 `src/bridge/bridgeMain.js`、`src/daemon/main.js`、`src/services/acp/entry.js`、`src/environment-runner/main.js` 等。如果没有命中特殊模式，则启动 early input 捕获，然后动态导入 `src/main.jsx`，执行 `main()`。

完整 CLI 的主流程位置在 `src/main.tsx`。该文件导入 `init`、`initializeTelemetryAfterTrust`，负责 Commander.js 命令定义、全局 option 处理、主 action 分发、REPL/Headless 模式选择、权限和 MCP 初始化等。根据当前片段，`src/main.tsx` 在早期解析 `--settings`、`-p/--print`、`--init-only` 等状态后调用 `await init()`，之后再继续加载更重的 CLI 行为。

进入会话后的核心循环继续在 `src/query.ts`、`src/QueryEngine.ts`、`src/screens/REPL.tsx`。其中 `src/query.ts` 处理请求 Claude API、流式响应、工具调用和 turn loop；`src/QueryEngine.ts` 管理对话状态、压缩、文件历史和归因；`src/screens/REPL.tsx` 管理 Ink 交互界面。

## 推荐阅读顺序

建议先读 `src/entrypoints/cli.tsx`。它能最快建立“命令如何进入系统”的地图，尤其要注意大量 `feature('FLAG')` 条件和动态 `import()`。这个文件的核心不是业务，而是启动路径分流和性能优化。

第二读 `src/main.tsx` 中靠前的初始化与主 action 区域，重点找 `init()` 调用点、Commander option 定义、`-p/--print` 与交互模式的分支。这样可以把 `cli.tsx` 的“默认路径”接上完整 CLI。

第三读 `src/entrypoints/init.ts`。它解释为什么很多全局状态、网络配置、遥测、远程设置不是在 `cli.tsx` 里完成，而是在完整 CLI 主流程中完成。理解它有助于判断哪些代码属于启动环境，哪些属于业务命令。

第四读 `src/entrypoints/mcp.ts`。它是一个相对独立的小入口，适合理解内部 `tools` 如何被包装成外部协议。

最后再读 `src/entrypoints/sdk`。这里不需要逐文件展开，先掌握 `schemas -> generated types -> public re-export` 的模式即可；需要做 SDK 类型变更时，再进入具体 schema 文件。

## 常见误区

一个常见误区是把 `src/entrypoints/cli.tsx` 当成完整 CLI。实际上它主要是 bootstrap 和 fast-path router，完整命令系统在 `src/main.tsx`，核心对话循环在 `src/query.ts` 和 `src/QueryEngine.ts`。

第二个误区是忽略动态导入的意义。这里大量使用 `await import(...)`，不是随意写法，而是为了避免普通命令启动时加载不需要的模块。尤其 `--version` 路径刻意做到几乎零额外模块加载。

第三个误区是把 `init.ts` 理解为所有模式都会执行。许多快速路径会自己启用必要配置，甚至完全绕过 `init()`。例如 daemon worker、某些 MCP/native host、runner 路径会走各自的轻量初始化。判断某段初始化是否生效时，必须先确认启动参数命中了哪条路径。

第四个误区是随意改 `feature()` 使用方式。仓库约定 `feature('X')` 要直接出现在 `if` 或三元条件位置，不能先赋值给变量，也不要放到复杂表达式里替代。`src/entrypoints/cli.tsx` 是 feature flag 最密集的区域之一，改动时尤其要遵守这个限制。

第五个误区是把 `src/entrypoints/sdk` 当成业务 SDK 实现。根据当前片段推断，它主要是类型、schema、常量和生成类型出口；真正的运行逻辑在服务层、工具层、查询层等目录中。
