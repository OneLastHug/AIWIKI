# 目录：src/commands/perf-issue

## 它负责什么

`src/commands/perf-issue` 实现内置 slash command `/perf-issue`。它的职责是把当前 Claude Code 会话的性能现场整理成本地报告，方便用户在性能异常、token 消耗异常或工具调用过慢时附到 bug report 里。这个命令是 `local` 类型，不向模型生成 prompt，也不执行网络上报；它只读取本机会话 transcript、采集当前进程状态，然后写入 `~/.claude/perf-reports` 下的报告文件。

报告内容主要分三类：

1. 当前进程快照：`process.memoryUsage()`、`process.cpuUsage()`、`process.uptime()`、`process.pid`、平台、Bun/Node 版本等。
2. 会话 transcript 统计：输入/输出 token、cache creation/read token、用户 turn 数、日志条目数、会话 wall clock 时间、检测到的模型名。
3. 工具调用统计：按 `tool_use` 计数，基于 transcript 中 `tool_use` 与 `tool_result` 的 timestamp 配对计算平均执行时间。

它还做了一个轻量成本估算：通过 `MODEL_COST_RATES` 按模型 ID 前缀匹配 Claude 系列模型单价，计算 `estimatedCostUsd`。如果模型未知或未匹配，成本估算返回 `null`，避免输出过期或误导性的价格。

命令支持参数：

- `--format=json|csv|md`：选择报告格式，默认 `md`。
- `--limit N`：限制最多读取 JSONL transcript 的最后 N 行，默认 `20_000`，用于避免超大日志导致内存压力。

## 直接子目录地图

这个目录很小，只有一个直接子目录：

- `src/commands/perf-issue/__tests__`：`/perf-issue` 的单元测试目录，覆盖命令元数据、缺失日志、JSON/CSV/Markdown 输出、token 统计、工具耗时、成本估算、错误信息脱敏和 `--limit` 行数限制。

目录根部文件包括：

- `src/commands/perf-issue/index.ts`：命令实现主体，包含所有解析、统计、格式化和写文件逻辑。
- `src/commands/perf-issue/index.d.ts`：声明默认导出为 `Command`，用于类型声明/构建产物兼容。

## 关键入口

最关键的入口是 `src/commands/perf-issue/index.ts` 末尾的 `perfIssue: Command` 对象。它声明：

- `type: 'local'`：本地命令，不是 prompt command。
- `name: 'perf-issue'`：用户侧命令名为 `/perf-issue`。
- `supportsNonInteractive: true`：支持非交互执行。
- `bridgeSafe: true`：可通过 Remote Control bridge 安全执行。
- `isEnabled: () => true`：始终启用，不受 feature flag 控制。
- `load: async () => ({ call: async (args) => ... })`：真正执行逻辑在 `call` 内。

命令被注册到全局命令列表的位置在 `src/commands.ts`。该文件导入 `perfIssue`：

`import perfIssue from './commands/perf-issue/index.js'`

随后在 `COMMANDS` 数组中加入 `perfIssue`。因此 `/perf-issue` 的生命周期是：命令系统加载内置命令列表，用户输入 `/perf-issue`，命令分发器根据名称找到该 `Command`，调用 `load()`，再执行返回模块的 `call(args, context)`。

## 主流程位置

主流程集中在 `src/commands/perf-issue/index.ts` 的 `call` 函数中，逻辑可以按顺序理解：

1. 解析参数  
   使用正则从 `args` 中解析 `--format` 和 `--limit`。格式只接受 `json`、`csv`、`md`，其他输入会回落到默认 Markdown。`--limit` 会被 `Math.max(1, parseInt(...))` 限制为至少 1 行。

2. 准备输出路径  
   `getPerfReportDir()` 固定返回 `~/.claude/perf-reports`。命令创建目录后，根据当前 ISO 时间戳、`getSessionId()` 的前 8 位和格式后缀生成文件名，例如 `perf-<timestamp>-<session>.md`。

3. 定位 transcript  
   `getTranscriptPath()` 优先使用 `getSessionProjectDir()`。如果项目会话目录存在，则路径为 `<projectDir>/<sessionId>.jsonl`；否则回退到 Claude 配置目录下的 `projects/<sanitizePath(getOriginalCwd())>/<sessionId>.jsonl`。这里依赖 `src/bootstrap/state.js` 提供会话 ID、原始 cwd 和项目会话目录，依赖 `src/utils/envUtils.js` 获取配置目录，依赖 `src/utils/path.js` 做路径安全编码。

4. 分析 transcript  
   `analyzeLog(logPath, lineLimit)` 是核心统计函数。它读取 JSONL 文件，最多保留最后 `lineLimit` 行，然后逐行 `JSON.parse`。单行解析失败会被跳过，不会中断整个报告。它累加 `usage` 字段里的 token，统计 `role === 'user'` 的 turn 数，记录首末 timestamp，检测第一条带 `model` 的日志作为模型名，并扫描 `content` 数组里的 `tool_use` / `tool_result`。工具耗时不是用当前时间估算，而是用日志条目的 timestamp 差值计算。

5. 生成报告内容  
   根据格式分派到三个 formatter：
   - `formatReportMarkdown(sessionId, logPath, analyzed)`：面向人工阅读，包含 Memory、CPU、Session Token Usage、Cost Estimate、Tool Call Counts、Tool Average Execution Time 和 Notes。
   - `formatReportJSON(sessionId, analyzed)`：结构化输出，包含 `memory`、`cpu`、`tokens`、`tool_counts`、`tool_avg_ms` 等字段。
   - `formatReportCSV(analyzed)`：简单 `metric,value` 表，适合表格或脚本处理。

6. 写文件并返回提示  
   使用 `writeFileSync(reportPath, reportContent, 'utf8')` 写入本地报告。成功时返回 `LocalCommandResult` 的 `{ type: 'text', value: ... }`，提示报告路径、格式和后续编辑说明。失败时会走 `sanitizeErrorMessage()`，把 home 目录替换为 `~`，并截断到约 200 字符，避免把绝对路径或长堆栈直接暴露给用户。

## 推荐阅读顺序

1. 先读 `src/commands/perf-issue/index.ts` 末尾的 `perfIssue` 对象，明确它是一个 `local` slash command，以及命令名、可用性、非交互支持和 bridge 安全属性。
2. 再读 `call(args)` 主体，理解参数解析、报告路径、transcript 路径、分析和写文件的顺序。
3. 接着读 `analyzeLog()`，这是目录里最有业务含量的部分，重点看 token 汇总、timestamp 处理、工具调用配对和 `MAX_LOG_LINES` 截断策略。
4. 然后读三个 formatter：`formatReportMarkdown()`、`formatReportJSON()`、`formatReportCSV()`，了解同一份 `AnalyzedLog` 如何映射到不同输出格式。
5. 最后读 `src/commands/perf-issue/__tests__/perf-issue.test.ts`，它能帮助确认边界行为：无日志仍生成报告、已知模型才估算成本、未知模型为 `null`、工具耗时基于日志 timestamp、`--limit` 只统计尾部 N 行、错误信息需要脱敏。
6. 如需理解命令如何出现在全局命令列表，再看 `src/commands.ts` 中的导入和 `COMMANDS` 数组注册位置。

## 常见误区

- 不要把 `/perf-issue` 理解成远程反馈命令。当前实现明确只写本地报告，Markdown notes 中也说明不会向 Anthropic 发送 perf report。
- 不要以为它会分析完整历史。默认只分析当前 session transcript，并且最多读取最后 `20_000` 行；传入 `--limit N` 后只统计最后 N 行。
- 不要把工具耗时当成实时测量。它是根据 transcript 中 `tool_use` 和 `tool_result` 所在日志条目的 timestamp 差值推导出来的；如果日志没有 timestamp 或配对缺失，就不会产生对应耗时数据。
- 不要认为成本估算覆盖所有模型。`MODEL_COST_RATES` 只按若干 Claude 模型前缀匹配；未知模型会输出 unknown/null，这是刻意避免陈旧估算。
- 不要忽略 `getTranscriptPath()` 的双路径逻辑。项目会话目录存在时走 `getSessionProjectDir()`，否则走配置目录下按 cwd 编码后的 `projects` 路径。
- 不要把 `index.d.ts` 当成实现文件。它只声明默认导出的类型，真正逻辑全部在 `index.ts`。
- 根据当前片段推断，命令的 UI 展示和执行调度由通用命令系统处理，依据是 `src/commands.ts` 将 `perfIssue` 加入 `COMMANDS`，而本目录内没有独立的 Ink 组件或交互界面。
