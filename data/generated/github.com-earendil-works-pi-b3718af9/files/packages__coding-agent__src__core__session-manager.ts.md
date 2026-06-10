# 文件：packages/coding-agent/src/core/session-manager.ts

## 一句话定位

`packages/coding-agent/src/core/session-manager.ts` 是 `coding-agent` 的会话存储与会话树管理核心：它把一次对话记录为 append-only JSONL 文件，同时用 `id`、`parentId`、`leafId` 表达可分支、可回溯、可压缩的会话历史，并负责把当前分支还原成可发送给 LLM 的上下文。

## 它暴露/定义了什么

文件主要导出三类内容。

第一类是会话数据结构：`SessionHeader`、`SessionEntry`、`SessionMessageEntry`、`CompactionEntry`、`BranchSummaryEntry`、`CustomEntry`、`CustomMessageEntry`、`LabelEntry`、`SessionInfoEntry`、`SessionTreeNode`、`SessionContext`、`SessionInfo`。这些类型定义了 JSONL 文件中每一行的语义：首行是 `session` header，后续行是消息、模型切换、thinking level 切换、压缩摘要、分支摘要、扩展自定义数据、标签和会话展示信息。

第二类是工具函数：`assertValidSessionId` 校验用户指定 session id；`parseSessionEntries`、`loadEntriesFromFile` 读取 JSONL；`migrateSessionEntries` 迁移旧格式；`buildSessionContext` 从会话树当前路径生成 LLM 上下文；`findMostRecentSession` 查找最近会话。

第三类是核心类 `SessionManager`。它提供创建、打开、继续、fork、内存会话、追加条目、分支、导出分支会话、读取树结构、列出会话等能力。

## 谁调用它

主要调用者在 `packages/coding-agent/src/main.ts` 和 `packages/coding-agent/src/core/agent-session-runtime.ts`。`main.ts` 根据 CLI 参数决定新建、继续、打开、fork 或列出 session；`agent-session-runtime.ts` 在程序化运行、恢复运行、切换会话文件时持有 `SessionManager` 并追加运行过程中的消息。

`packages/coding-agent/src/core/export-html/index.ts` 用它打开会话并导出 HTML。`packages/coding-agent/src/cli/session-picker.ts` 消费 `SessionInfo` 做会话选择。大量测试文件直接使用 `SessionManager.inMemory()` 或 `SessionManager.create()` 构造可控会话，覆盖迁移、树遍历、压缩、分支、文件损坏恢复、session id 等行为。

## 它调用谁

它依赖 `@earendil-works/pi-agent-core` 的 `AgentMessage`、`uuidv7`，依赖 `@earendil-works/pi-ai` 的消息内容类型。文件系统层面直接调用 Node `fs`、`fs/promises`、`readline`、`path`、`crypto`，实现 JSONL 的同步追加、重写、按行读取和目录扫描。

项目内它调用 `../config.ts` 的 `getAgentDir`、`getSessionsDir` 计算默认会话目录；调用 `../utils/paths.ts` 的 `normalizePath`、`resolvePath` 规范化路径；调用 `./messages.ts` 的 `createCompactionSummaryMessage`、`createBranchSummaryMessage`、`createCustomMessage` 把特殊 session entry 转换为 LLM 可消费的 message。

## 核心流程

新建会话时，`SessionManager.create()` 计算 session 目录，构造 `SessionHeader`，生成 `sessionId` 和文件名，但持久化有延迟策略：在没有 assistant 消息前不一定立即写完整文件。这能避免只有用户输入或空会话时留下不完整历史。

打开会话时，`SessionManager.open()` 先读取 JSONL，取 header 中的 `cwd`，再进入构造函数的 `setSessionFile()`。`setSessionFile()` 会读取文件、处理空文件或损坏 header、执行 v1 到 v3 的迁移、重写迁移后的文件，并通过 `_buildIndex()` 建立 `byId`、标签 map 和当前 `leafId`。

追加消息或状态变化时，`appendMessage()`、`appendModelChange()`、`appendThinkingLevelChange()`、`appendCompaction()` 等都会创建一个新的 entry，`parentId` 指向当前 `leafId`，然后 `_appendEntry()` 把它放入内存、更新 `leafId`、并调用 `_persist()` 追加到 JSONL。历史不被修改，所有变化都是追加。

构建上下文时，`buildSessionContext()` 从当前 leaf 逆向追溯到 root，得到一条分支路径。它沿路径计算最新 thinking level、模型信息和最近一次 compaction；如果存在压缩，则先注入压缩摘要，再保留 `firstKeptEntryId` 之后的消息和压缩后的消息；否则按路径追加普通消息、`custom_message` 和 `branch_summary`。

分支时，`branch()` 只移动 `leafId`，下一次 append 会从旧节点长出新分支；`branchWithSummary()` 会先移动 leaf，再追加一个 `branch_summary`。`createBranchedSession()` 则把某个 leaf 的 root-to-leaf 路径复制为一个新 session 文件，并保留路径上已解析的标签。

## 关键函数的高层作用

`migrateV1ToV2()` 为旧线性 session 补齐 `id` 和 `parentId`，把历史转成树结构；`migrateV2ToV3()` 把旧的 `hookMessage` role 改为 `custom`。`migrateToCurrentVersion()` 串联这些迁移。

`loadEntriesFromFile()` 是底层读取入口，使用固定大小 buffer 和 `StringDecoder` 逐行解析，跳过坏行，并要求第一条有效记录必须是合法 session header。

`buildSessionInfo()` 是列表页摘要构建器，只扫描文件生成 `SessionInfo`，包括创建时间、最近活动时间、首条用户消息、全部文本索引和用户自定义名称。

`_persist()` 是最敏感的持久化逻辑：它根据是否已有 assistant 消息、是否已经 flush，决定延迟创建、全量写入或追加写入。

`getTree()` 从所有 entry 构造防御性树视图，并把孤儿节点当 root 返回，避免坏数据直接导致 UI 无法展示。

`forkFrom()` 从另一个 session 文件复制非 header 条目，并写入新的 header，把 `parentSession` 指向源文件。

## 修改风险

最高风险在文件格式和迁移。`SessionEntry` 的字段语义、`CURRENT_SESSION_VERSION`、`migrateV1ToV2()`、`migrateV2ToV3()` 一旦改错，会影响旧会话打开、上下文重建和测试夹具。新增 entry 类型时，必须同步考虑 `SessionEntry` union、`buildSessionContext()`、`getTree()`、`buildSessionInfo()` 和导出/渲染侧是否需要识别。

第二个风险是 `_persist()` 的延迟写入协议。这里和“没有 assistant 前不落完整文件”的产品行为绑定，贸然改成立即写入或全量重写，可能重新引入重复 header、空会话污染列表、损坏文件恢复异常等问题。

第三个风险是树语义。`leafId` 不是“最后一行”的同义词，而是当前操作位置；`branch()` 只移动 leaf，不删除历史。任何把 session 当线性数组处理的修改，都可能破坏重试、编辑早期消息、分支摘要和压缩上下文。

第四个风险是上下文构建。`buildSessionContext()` 决定真正发给模型的内容，特别是 compaction、`custom_message`、`branch_summary` 的注入顺序。改动这里会直接改变模型行为，并影响扩展系统对会话状态的预期。

第五个风险是路径和目录过滤。`list()`、`listAll()`、`continueRecent()` 对默认 session 目录和自定义 flat session 目录有不同过滤规则；修改 `cwd` 匹配或默认目录编码时，容易导致会话列表缺失、跨项目串会话或继续到错误 session。
