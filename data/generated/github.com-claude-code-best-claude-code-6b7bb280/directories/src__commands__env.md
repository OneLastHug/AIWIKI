# 目录：src/commands/env

## 它负责什么

`src/commands/env` 实现的是 Claude Code 内部的 `/env` 斜杠命令，用来在当前会话中输出一份“本地运行环境快照”。它不是外部 shell 的 `env` 命令，也不是 `claude env` 这种顶层 CLI 子命令；它属于 `Command` 系统中的 `local` 命令，主要服务于调试、排查配置和确认 feature flag 状态。

从当前实现看，`/env` 输出两块内容：`Runtime` 和 `Environment Variables`。`Runtime` 包括 `process.platform`、`process.arch`、`process.cwd()`、`process.pid`、`Bun.version`、`process.version`，以及从 `src/bootstrap/state.js` 读取的 `getSessionId()`。环境变量部分不是全量打印，而是只展示 allowlist 前缀命中的变量，例如 `CLAUDE_`、`FEATURE_`、`ANTHROPIC_`、`BUN_`、`NODE_`、`GEMINI_`、`OPENAI_`、`GROK_`、`CCR_`、`KAIROS_`、`BUGHUNTER_`。

这个目录还承担一个重要的安全边界：它会识别疑似敏感 key，并对 value 做掩码。匹配规则包括 `token`、`secret`、`password`、`api_key` / `api-key`、`auth`、`private`、`credential`、`jwt`、以 `session_id` / `session-id` 结尾的 key。短值显示为 `***`，长值只保留开头和末尾少量字符，并附带长度。

## 直接子目录地图

`src/commands/env` 目前是一个很小的命令目录，没有业务子模块拆分。

- `src/commands/env/index.ts`：`/env` 命令的实际实现，包含命令元数据、环境变量筛选、敏感值识别、输出格式化逻辑。
- `src/commands/env/index.d.ts`：类型声明文件，声明默认导出是 `Command`。根据当前片段推断，它主要用于兼容编译产物或反编译后类型补齐，不承载运行时逻辑。
- `src/commands/env/__tests__`：测试目录。
- `src/commands/env/__tests__/env.test.ts`：覆盖命令元数据、输出结构、allowlist 前缀、敏感值掩码，以及 `KAIROS_` 前缀回归场景。

## 关键入口

本目录的关键入口是 `src/commands/env/index.ts` 的默认导出 `env`。它是一个 `Command` 对象，关键字段如下：

- `type: 'local'`：表示它是本地命令，执行时不会把请求交给模型生成 prompt。
- `name: 'env'`：用户通过 `/env` 调用。
- `description: 'Show current environment, runtime, and feature flags'`：用于命令列表、补全或帮助展示。
- `isHidden: false`：不是隐藏命令。
- `isEnabled: () => true`：始终启用，不依赖 feature flag 或用户类型。
- `supportsNonInteractive: true`：允许在非交互模式中执行。
- `load()`：返回带 `call()` 的本地命令模块，真正执行时拼接 Markdown 文本并返回 `{ type: 'text', value: text }`。

辅助入口函数集中在同一个文件内：`shouldShowEnv()` 负责按前缀过滤环境变量，`isSecretKey()` 负责判断 key 是否敏感，`maskValue()` 负责掩码展示，`formatEnvVars()` 负责生成环境变量段落，`formatRuntime()` 负责生成运行时段落。

## 主流程位置

主注册流程在 `src/commands.ts`。该文件导入 `src/commands/env/index.js`，然后把 `env` 放进 `COMMANDS()` 返回的内置命令数组中。之后 `getCommands(cwd)` 会合并内置命令、skills、plugins、workflows 等来源，并通过 `meetsAvailabilityRequirement()` 和 `isCommandEnabled()` 做过滤。因为 `/env` 没有 `availability` 限制，且 `isEnabled()` 恒为 `true`，所以它会稳定出现在可用命令集合中。

交互式调用流程根据当前片段推断大致是：用户在 REPL 输入 `/env`，输入处理逻辑会进入 `src/utils/processUserInput/processSlashCommand.tsx`，在那里根据命令名找到 `Command`，对于 `type === 'local'` 的命令调用其 `load()`，再调用返回模块的 `call()`，最后把 `LocalCommandResult` 渲染回消息流。这个推断依据是仓库中对 `LocalCommandResult`、`type === 'local'`、`load()/call()` 的检索结果，以及 `src/types/command.ts` 对 `LocalCommand` 的类型定义。

非交互式流程也会经过命令集合过滤。`src/main.tsx` 中有针对命令 `supportsNonInteractive` 的判断；`src/cli/print.ts` 也会调用 `getCommands(cwd())`。因此 `/env` 标记 `supportsNonInteractive: true` 的意义是：它不仅能在 REPL 中执行，也能在 print/headless 类路径中被接受，而不需要 Ink 交互 UI。

## 推荐阅读顺序

建议先读 `src/types/command.ts`，理解 `Command`、`LocalCommandResult`、`LocalCommand`、`supportsNonInteractive` 的基本合同。这样再看 `src/commands/env/index.ts` 时，会很清楚为什么它要导出一个 `Command` 对象，以及 `load()` 为什么返回 `{ call }`。

第二步读 `src/commands/env/index.ts`。重点看三个层次：命令元数据、环境变量过滤和输出拼装。这里逻辑很直，不需要逐行深挖，抓住“本地读取 process 信息、allowlist 展示、敏感值掩码、返回 text 结果”即可。

第三步读 `src/commands.ts` 中 `env` 的 import 和 `COMMANDS()` 数组位置，确认它如何进入全局命令表。顺带看 `getCommands()` 如何合并动态命令来源，这能帮助区分内置 slash command、plugin command、skill command 的加载边界。

最后读 `src/commands/env/__tests__/env.test.ts`。测试比实现更清楚地表达了设计意图：`/env` 必须可用、支持非交互、输出 runtime 和 env section、只显示允许前缀、隐藏敏感值，并且 `KAIROS_` 必须精确带下划线匹配。

## 常见误区

不要把 `src/commands/env` 理解成全局环境变量管理模块。它不负责设置、合并或持久化环境变量，也不参与 provider 选择、settings.json env 注入、feature flag 求值。它只是读取当前 `process.env` 的一个安全展示命令。

不要以为 `/env` 会打印所有环境变量。它只打印 allowlist 前缀命中的变量，普通的 `PATH`、`HOME`、`USER` 等不会因为存在于 `process.env` 就自动出现，除非未来 allowlist 被扩展。

不要把 `description` 里的 “feature flags” 理解成它会调用 `feature('X')` 列出所有编译期 feature。当前实现只是展示 `FEATURE_` 前缀环境变量；真正的 `bun:bundle` feature flag 编译/运行机制在其他位置，例如构建脚本和使用 `feature()` 的模块中。

不要认为敏感值掩码是完整的密钥防泄漏系统。它依赖 key 名模式识别，只能降低 `/env` 输出中常见 secret 泄露风险；如果某个敏感变量使用了非典型命名，且前缀又在 allowlist 中，当前逻辑可能不会识别为 secret。

不要忽略 `supportsNonInteractive: true`。这说明 `/env` 的实现被刻意做成纯文本、纯本地、无 UI 依赖，所以它适合 headless/print 路径；这和很多 `local-jsx` 或需要用户交互的命令不同。
