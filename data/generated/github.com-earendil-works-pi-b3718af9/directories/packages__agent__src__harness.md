# 子系统：packages/agent/src/harness

## 解决什么问题

`packages/agent/src/harness` 是 `packages/agent` 里负责“把一次 agent 对话变成可运行、可持久化、可恢复流程”的编排层。它不直接实现模型推理核心，也不直接实现具体 UI，而是把模型、工具、执行环境、会话树、技能、提示模板、压缩摘要和分支摘要组织成一个稳定的运行外壳。

从职责看，这个目录解决三类问题：第一，如何以统一接口驱动 `runAgentLoop`，包括模型、系统提示词、可用工具、stream 选项和 API 鉴权头；第二，如何把对话过程写入 `Session`，并支持 fork、navigate、compact 等长期会话能力；第三，如何把本地执行能力抽象成 `ExecutionEnv`，让文件读写、目录遍历、shell 执行、临时文件等能力既可在 Node 环境运行，也可在测试或其他宿主环境替换。

## 相关目录和文件

核心入口是 `packages/agent/src/harness/agent-harness.ts`，其中的 `AgentHarness` 是对外主要对象，负责运行状态、事件订阅、队列、会话写入和 agent loop 调用。`packages/agent/src/harness/types.ts` 定义公共类型和错误模型，包括 `ExecutionEnv`、`FileSystem`、`SessionStorage`、`AgentHarnessOptions`、`AgentHarnessEvent` 等。

会话相关代码集中在 `packages/agent/src/harness/session`：`session.ts` 提供 `Session` 和 `buildSessionContext`；`memory-storage.ts`、`memory-repo.ts` 提供内存实现；`jsonl-storage.ts`、`jsonl-repo.ts` 提供基于 JSONL 文件的持久化实现；`repo-utils.ts` 处理创建 ID、时间戳、fork 条目选择；`uuid.ts` 生成 UUID v7。

上下文压缩在 `packages/agent/src/harness/compaction`：`compaction.ts` 负责主线历史压缩，`branch-summarization.ts` 负责离开分支后的摘要，`utils.ts` 提供会话序列化等共用逻辑。环境适配在 `env/nodejs.ts`，消息转换在 `messages.ts`，技能加载在 `skills.ts`，系统提示词技能块格式化在 `system-prompt.ts`，shell 输出截断和保存在 `utils/shell-output.ts`、`utils/truncate.ts`。

`packages/agent/src/index.ts` 会重新导出 harness 的主要能力，说明该目录是包级公开 API 的一部分，而不只是内部实现。

## 核心对象

`AgentHarness` 是最重要的对象。它持有 `env`、`session`、`model`、`thinkingLevel`、`systemPrompt`、`streamOptions`、`resources`、`tools` 和事件 handlers。它还维护运行阶段 `phase`、当前 abort controller、待写入 session 的队列，以及三类对话队列：`steerQueue`、`followUpQueue`、`nextTurnQueue`。这些队列让宿主可以在一次运行中追加引导、后续输入或下一轮消息。

`Session` 表示一棵可分支的会话树，而不是简单线性聊天记录。`SessionTreeEntry` 包含普通消息、工具结果、模型切换、thinking level 切换、active tools 切换、label、leaf、compaction、branch summary 等条目。`buildSessionContext` 会沿当前路径把树条目转换成运行 agent 需要的上下文消息，同时恢复当前模型、思考级别和可用工具状态。

`ExecutionEnv` 是 harness 与真实环境之间的边界。`NodeExecutionEnv` 是 Node.js 实现，封装路径解析、`fileInfo`、`listDir`、`readTextFile`、`writeFile`、`appendFile`、`createTempFile`、`createTempDir`、`remove`、`canonicalPath` 和 `exec`。这些接口统一返回 `Result`，用 `FileError`、`ExecutionError` 表达可预期失败，避免把宿主差异泄漏到上层。

`Skill` 和 `PromptTemplate` 是可注入资源。`loadSkills` 会遍历技能目录，读取 `SKILL.md` 或根目录 markdown 文件，解析 frontmatter，并尊重 `.gitignore`、`.ignore`、`.fdignore`。`formatSkillsForSystemPrompt` 把可见技能格式化为模型可读的 XML 风格列表；`formatSkillInvocation` 则用于显式调用某个技能。

## 运行流程

典型流程是：宿主先创建 `ExecutionEnv` 和 `Session`，再用模型、工具、资源、系统提示词和 stream 选项构造 `AgentHarness`。用户输入进入 harness 后，会被包装成 `UserMessage`，与当前 session path 通过 `buildSessionContext` 组合成模型上下文。

运行前，harness 会快照当前 turn 状态：消息、资源、stream options、sessionId、system prompt、model、thinkingLevel、tools、activeTools。随后它调用 `runAgentLoop`，并把 `streamSimple`、工具列表、上下文和事件回调传给底层 agent loop。模型输出、工具调用、工具结果、错误或 abort 都会转成 `AgentEvent` / harness 自有事件，再由事件订阅者消费，并写入 session。

当上下文过长时，`prepareCompaction` 和 `compact` 会选择可压缩历史，调用模型生成摘要，再插入 `compaction` 条目。压缩后的上下文不再保留完整旧消息，而是通过 `createCompactionSummaryMessage` 转换为一条摘要消息继续参与后续推理。会话从一个分支切回另一个分支时，`collectEntriesForBranchSummary` 和 `generateBranchSummary` 会总结被离开的分支，并把读过、改过的文件信息附加到摘要里。根据当前片段推断，这样做的依据是 `branch-summarization.ts` 会收集 abandoned branch entries，并把摘要以前缀 “The user explored a different conversation branch...” 注入未来上下文。

## 上下游依赖

上游依赖主要来自 `@earendil-works/pi-ai` 和 `packages/agent/src/agent-loop.ts`。前者提供 `Model`、消息内容类型、`streamSimple`、`completeSimple` 等模型调用能力；后者是真正执行多轮 agent loop 和工具交互的核心。harness 负责把这些底层能力组织成有状态的产品级会话。

下游主要是包的消费者：TUI、CLI、应用层或测试可以通过 `packages/agent/src/index.ts` 使用 `AgentHarness`、session repo、skills、compaction 工具和 shell capture 工具。测试目录 `packages/agent/test/harness` 覆盖了 Node 环境、session UUID、system prompt、session storage 等行为，是理解公开契约的重要依据。

横向依赖包括 `ignore` 和 `yaml`，用于技能加载；Node 内置 `fs/promises`、`child_process`、`path`、`readline`、`os` 等用于 `NodeExecutionEnv`。这些依赖都被隔离在 harness 层，避免 agent loop 直接绑定 Node 文件系统。

## 修改时最容易踩的坑

第一，不要把 session 当成线性数组处理。当前设计是树结构，`leaf`、`parentId`、fork、navigate 和 branch summary 都依赖条目父子关系。修改 `SessionStorage` 或 `buildSessionContext` 时，必须确认分支路径、当前 leaf、摘要条目的语义没有被破坏。

第二，错误模型是 API 的一部分。文件和执行操作大量使用 `Result<T, FileError | ExecutionError>`，而不是直接 throw。仓库层会在边界处把文件错误转为 `SessionError`，harness 再归一为 `AgentHarnessError`。随意抛异常会让宿主无法按稳定 code 处理错误。

第三，压缩和分支摘要会影响模型上下文，不只是存储优化。`messages.ts` 里 `convertToLlm` 会把 `bashExecution`、`custom`、`branchSummary`、`compactionSummary` 转成模型可见消息；其中 `excludeFromContext`、摘要前后缀、文件操作列表都会改变模型看到的事实。

第四，`ExecutionEnv` 的路径语义要保持一致。`NodeExecutionEnv` 对相对路径按 `cwd` 解析，`fileInfo` 不自动跟随 symlink，`canonicalPath` 才做真实路径解析。改动文件系统相关逻辑时，要特别注意 symlink、权限错误、目录/文件类型错误和 abort 行为。

第五，技能加载不是简单递归读 markdown。它会处理 ignore 规则、frontmatter 校验、`disable-model-invocation`、根目录 markdown 与子目录 `SKILL.md` 的优先级。修改 `skills.ts` 时要同步考虑 `system-prompt.ts` 的模型可见格式。

## 推荐阅读顺序

1. 先读 `packages/agent/src/harness/types.ts`，建立错误类型、环境接口、session 接口和 harness options 的整体词汇表。
2. 再读 `packages/agent/src/harness/agent-harness.ts`，理解 `AgentHarness` 如何把模型、工具、session、事件和队列串起来。
3. 接着读 `packages/agent/src/harness/session/session.ts`、`packages/agent/src/harness/session/memory-storage.ts`、`packages/agent/src/harness/session/jsonl-storage.ts`，弄清会话树和持久化格式。
4. 然后读 `packages/agent/src/harness/messages.ts`，确认各种内部消息如何进入 LLM 上下文。
5. 再读 `packages/agent/src/harness/compaction/compaction.ts` 和 `packages/agent/src/harness/compaction/branch-summarization.ts`，理解长会话和分支恢复策略。
6. 最后读 `packages/agent/src/harness/env/nodejs.ts`、`packages/agent/src/harness/skills.ts`、`packages/agent/src/harness/system-prompt.ts`，补齐运行环境与资源注入细节。
