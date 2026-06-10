# 目录：src/commands/share

## 它负责什么

`src/commands/share` 实现 Claude Code 内置斜杠命令 `/share`，用于把当前会话的 JSONL transcript 上传成可分享内容。它是一个本地命令目录，不负责渲染复杂 Ink UI，也不参与模型请求主循环；它的边界很清晰：定位当前 session 的日志文件、按用户参数处理日志内容、调用外部命令上传、返回一段文本结果给命令系统展示。

从当前代码看，`/share` 的默认目标是 GitHub Gist，依赖本机 `gh` CLI。命令支持 `--public`、`--private`、`--mask-secrets`、`--summary-only`、`--allow-public-fallback` 等参数：默认是 secret Gist；`--public` 改为公开；`--mask-secrets` 会在上传前对常见 API key、Bearer token、AWS key、GitHub token、Slack token、password/secret 字段做正则脱敏；`--summary-only` 只上传 user/assistant 每轮前 200 个字符；`--allow-public-fallback` 允许在没有 `gh` 或 Gist 上传失败时改用公共 paste 服务。注意 fallback 服务地址在文档中不展开，源码里由 `uploadTo0x0` 处理。

这个目录还承担一部分隐私保护职责：一是提供脱敏选项，二是失败信息通过 `sanitizeErrorMessage` 把 home 目录替换为 `~` 并截断错误文本，三是成功或失败返回文案中反复提示 JSONL 包含本会话输入和工具输出。但它不是安全审计模块，默认不会自动脱敏，用户必须显式传 `--mask-secrets`。

## 直接子目录地图

`src/commands/share` 目前只有一个直接子目录：

`src/commands/share/__tests__`：围绕 `/share` 命令的单元测试目录。测试覆盖命令元数据、参数解析、会话日志不存在、会话日志存在、`gh` CLI 可用或不可用、Gist 上传成功/失败、fallback 上传、`getTranscriptPath` 的 `projectDir` 分支、summary 内容构造异常分支等。测试中会 mock `node:child_process`、`bun:bundle` 和 analytics，避免真实调用外部上传命令。

目录根部文件包括：

`src/commands/share/index.ts`：命令实现的唯一核心文件，包含命令对象、参数解析、日志路径计算、内容处理、上传逻辑和 telemetry 事件。

`src/commands/share/index.d.ts`：声明文件，只声明默认导出为 `Command`。根据当前片段推断，它可能来自构建或类型声明保留，用于让某些导入场景识别命令模块形状；实际业务逻辑不在这里。

## 关键入口

最直接的入口是 `src/commands/share/index.ts` 默认导出的 `share: Command` 对象。这个对象声明：

`type: 'local'`：表示它是本地命令，执行后返回 `LocalCommandResult`，不直接进入模型 prompt 扩展。

`name: 'share'`：对应用户输入 `/share`。

`supportsNonInteractive: true`：允许非交互模式使用。

`bridgeSafe: true`：表示可通过 Remote Control bridge 安全执行，前提是无需本地交互 UI。

`load: async () => ({ call })`：命令系统懒加载后调用 `call(args)` 执行实际流程。

命令注册入口在 `src/commands.ts`。该文件静态导入 `share`：`import share from './commands/share/index.js'`，并在命令数组中加入 `share`。因此 `/share` 不是 feature flag 条件加载命令，`isEnabled: () => true` 也说明它默认总是可用。

命令类型来自 `src/types/command.ts`，其中 `LocalCommandResult` 决定 `/share` 最终只能返回文本、compact 结果或 skip。`/share` 实际只返回 `{ type: 'text', value: string }`。

## 主流程位置

主流程集中在 `src/commands/share/index.ts` 的 `share.load().call(args)` 内，可以按阶段理解。

第一阶段是参数解析。`parseShareArgs(args)` 把用户输入拆分为 flag 列表，只接受 `--public`、`--private`、`--mask-secrets`、`--summary-only`、`--allow-public-fallback`。出现未知 `--flag` 时返回 usage 文本，不继续执行。这里没有复杂冲突处理，例如同时传 `--public` 和 `--private` 时，当前逻辑只看 `parts.includes('--public')` 决定 `isPublic`，因此公开优先是实际行为。

第二阶段是定位 transcript。`getTranscriptPath()` 先取 `getSessionId()` 和 `getSessionProjectDir()`；如果 `projectDir` 存在，路径是 `projectDir/<sessionId>.jsonl`。否则用 `getOriginalCwd()` 经 `sanitizePath()` 编码后，落到 `getClaudeConfigHomeDir()/projects/<encoded>/<sessionId>.jsonl`。这说明 `/share` 复用 CLI 会话日志约定，而不是自己记录会话。

第三阶段是 telemetry 和前置校验。命令调用 `logEvent('tengu_share_started', ...)` 记录启动事件，然后用 `existsSync(logPath)` 检查日志是否存在。不存在时返回 “Session log not found”，并记录 `tengu_share_failed`，reason 为 `log_not_found`。

第四阶段是检测外部上传工具。`ghAvailable()` 通过 `execFileAsync('gh', ['--version'], { timeout: 3000 })` 判断 GitHub CLI 是否存在。若没有 `gh` 且用户没允许 fallback，命令不会上传，而是返回手动上传指引和隐私提示。这里的源码文案包含外部链接，阅读源码时可关注含义即可，文档不展开真实 URL。

第五阶段是准备上传内容。若传入 `--summary-only`，走 `buildSummaryContent(logPath)`，逐行解析 JSONL，只保留 `role` 为 `user` 或 `assistant` 的内容，字符串内容直接截断，数组内容取第一个 `type === 'text'` 的块并截断。若没传该参数，则直接读取完整 JSONL。随后如果传入 `--mask-secrets`，调用导出的 `maskSecrets(text)` 做正则替换。最终内容写入临时目录 `cc-share-*` 下的 `claude-session.jsonl`，这样上传的是处理后的副本，不改原始会话日志。

第六阶段是上传与收尾。若 `gh` 可用，优先调用 `uploadToGist(tmpFile, opts.isPublic)`，内部执行 `gh gist create`，并校验 stdout 必须像 HTTPS URL。若 Gist 失败且允许 fallback，则调用 `uploadTo0x0(tmpFile)`。若 `gh` 不可用但允许 fallback，也直接走 fallback。成功后记录 `tengu_share_succeeded` 并返回 URL、session、visibility、method、summary/mask 标记。失败则记录 `upload_error` 并返回错误和下一步提示。无论成功失败，`finally` 都会 `rmSync(tmpDir, { recursive: true, force: true })` 清理临时目录。

## 推荐阅读顺序

1. 先读 `src/commands.ts` 中对 `share` 的导入和命令数组位置，建立它如何进入全局斜杠命令系统的概念。

2. 再读 `src/types/command.ts` 的 `Command`、`LocalCommandResult`、`LocalCommandModule`，理解为什么 `share.load().call()` 返回文本即可。

3. 然后读 `src/commands/share/index.ts` 的命令对象声明，从 `const share: Command = { ... }` 开始向内看 `call(args)`，这是业务主线。

4. 回头读同文件顶部的辅助函数：`maskSecrets`、`buildSummaryContent`、`getTranscriptPath`、`ghAvailable`、`uploadToGist`、`uploadTo0x0`。这些函数分别对应内容处理、路径定位和上传通道。

5. 最后按需要浏览 `src/commands/share/__tests__/share.test.ts`、`src/commands/share/__tests__/share-gh.test.ts`、`src/commands/share/__tests__/share-projectdir.test.ts`。测试比实现更清楚地展示了边界情况，尤其是 `child_process.execFile` 的 mock 方式和 `projectDir` 分支。

## 常见误区

`/share` 不是“生成摘要并发给模型”的命令。`--summary-only` 是本地裁剪 JSONL 内容，截取每轮文本前 200 字符，不调用 Claude API，也不做语义摘要。

`--private` 不等于完全私密。这里的 private 实际对应 GitHub Gist 的 secret visibility，源码中返回文案也写成 `secret`。拥有链接的人仍可能访问，因此源码持续提示用户分享前审查 JSONL。

`--mask-secrets` 不是默认行为。默认上传完整日志副本，只有显式传参才会脱敏。并且脱敏基于有限正则，注释中明确避免泛化匹配 32 位以上 hex 字符串，以免误伤 git commit SHA 或 base64 内容。

fallback 不是私有上传。`--allow-public-fallback` 的语义是允许公开 fallback；当 `gh` 不存在或 Gist 失败时，内容可能被上传到公共 paste 服务。阅读或修改时不要把它理解成 GitHub Gist 的另一种 secret 模式。

`getTranscriptPath()` 有两套路径规则。存在 `getSessionProjectDir()` 时直接使用 project dir；否则才使用 Claude config home 下的 `projects/<encoded cwd>/<sessionId>.jsonl`。测试目录专门覆盖了这个分支，说明路径行为对兼容性比较重要。

`index.d.ts` 不是实现入口。它只声明默认导出类型；真正逻辑都在 `index.ts`。对于源码学习，优先看 `index.ts` 和注册点 `src/commands.ts`。
