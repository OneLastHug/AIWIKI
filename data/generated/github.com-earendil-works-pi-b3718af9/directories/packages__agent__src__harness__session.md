# 子系统：packages/agent/src/harness/session

## 解决什么问题

这个目录负责 Agent harness 的“会话树”管理：把一次对话拆成可持久化、可分叉、可回放的 session entry 流，并能从这些 entry 重新拼出当前上下文。它解决的不是单纯存消息，而是同时处理“当前叶子在哪”“历史如何分支”“如何做 compaction 后的上下文恢复”“如何给会话打标签/命名”等问题。

从当前片段看，它是 harness 的状态底座：`AgentHarness` 只关心业务运行，真正的会话生命周期、追加、移动分支、fork、列表与删除，都落在这里。

## 相关目录和文件

核心文件是 `packages/agent/src/harness/session/session.ts`，它提供 `Session` 类和 `buildSessionContext()`，前者是对存储的高层封装，后者把树路径还原成运行时上下文。

`packages/agent/src/harness/session/jsonl-storage.ts` 和 `memory-storage.ts` 是两种存储实现：前者面向磁盘 JSONL 文件，后者面向测试或临时场景的内存结构。

`packages/agent/src/harness/session/jsonl-repo.ts`、`memory-repo.ts` 是仓库级 API，负责 `create/open/list/delete/fork`。`repo-utils.ts` 提供公共工具，`uuid.ts` 提供 entry id 生成。它们和 `packages/agent/src/harness/messages.ts`、`packages/agent/src/harness/types.ts` 强耦合，因为会话最终要还原成 `AgentMessage` 和 `SessionContext`。

## 核心对象

`Session<TMetadata>`：包裹一个 `SessionStorage`，提供追加消息、追加模型/思考层级变化、追加 compaction、打标签、改叶子位置等方法。它本身不关心介质，只依赖存储接口。

`SessionStorage<TMetadata>`：底层抽象，负责 `getLeafId()`、`getPathToRoot()`、`appendEntry()`、`createEntryId()`、`findEntries()` 等树操作。JSONL 和内存实现都遵循它。

`SessionTreeEntry`：会话树上的统一节点类型。它有 `message`、`custom_message`、`compaction`、`branch_summary`、`session_info`、`label` 等多种变体，说明这个目录管理的是“事件树”，不是单一消息列表。

`JsonlSessionRepo` / `InMemorySessionRepo`：面向外部的会话仓库。前者把会话按 cwd 分目录、按时间和 id 落盘；后者用 Map 保存，适合测试和无文件系统环境。

## 运行流程

典型路径是：repo 创建 session -> storage 初始化 -> harness 运行过程中不断 append entry -> 需要上下文时从 leaf 向 root 取路径 -> `buildSessionContext()` 把路径压成 `SessionContext`。

`buildSessionContext()` 的逻辑很关键：它扫描路径上的 entry，最后一次出现的 `thinking_level_change`、`model_change`、`active_tools_change` 会成为当前状态；如果存在 `compaction`，会先插入 compaction summary，再从 `firstKeptEntryId` 开始重建可见消息，只保留压缩后仍应进入上下文的部分。`message`、`custom_message`、`branch_summary` 会被转换成 `AgentMessage`，供 `convertToLlm()` 或 harness 后续处理。

`JsonlSessionRepo.fork()` 和 `InMemorySessionRepo.fork()` 会先用 `getEntriesToFork()` 选出分叉点之前的树，再创建新 session 并把选中的 entry 逐条写入新存储，因此 fork 不是简单复制文件，而是复制一段可解释的历史。

## 上下游依赖

上游主要来自 `packages/agent/src/harness/agent-harness.ts`：它需要 session 提供运行态读取、持久化写入和分叉能力。`harness/messages.ts` 负责把 `branchSummary`、`compactionSummary`、`custom` 这些会话专用消息转成 LLM 可读格式。

下游依赖的是通用能力：`FileSystem`、`SessionRepo`、`SessionStorage`、`SessionError`、`AgentMessage`、`SessionMetadata`、`SessionContext`。JSONL 版本还依赖路径操作、文件读写、目录枚举；内存版本则依赖内存集合和复制逻辑。根据当前片段推断，`jsonl-storage.ts` 还承担了头部版本校验、entry 校验、label 缓存和 leaf 追踪，这些都直接决定 session 文件能否被正确打开。

## 修改时最容易踩的坑

最容易出问题的是 tree 语义而不是 I/O 语义。改 `append` 或 `moveTo` 时，如果 parentId、leafId、entry 顺序处理不一致，就会破坏分支结构。改 `compaction` 相关逻辑时，要同步考虑 `buildSessionContext()`、`messages.ts` 的上下文还原格式，否则历史会“看起来还在，实际进不了模型上下文”。

JSONL 版本还有几个常见风险：header 版本号、entry 解析、文件名编码、cwd 分桶规则。如果改了 `encodeCwd()` 或文件路径生成，旧 session 可能找不到；如果改了 `SessionTreeEntry` 结构但没同步校验与 fork 逻辑，`list()` 会跳过或拒绝无效文件。

另外，`SessionError("not_found" | "invalid_session" | "invalid_entry")` 是对外稳定错误面，改动时不要随意换码，否则上层 `AgentHarness` 的错误归类会失真。

## 推荐阅读顺序

先看 `packages/agent/src/harness/session/session.ts`，理解会话树如何被抽象成高层 API；再看 `packages/agent/src/harness/session/repo-utils.ts`，把 create/fork 的公共拼装逻辑理清；然后看 `memory-repo.ts` 和 `jsonl-repo.ts`，对比测试版与持久化版的差异；接着读 `memory-storage.ts`、`jsonl-storage.ts`，确认树结构和持久化格式；最后回到 `packages/agent/src/harness/messages.ts`、`packages/agent/src/harness/agent-harness.ts`，把 session 如何进入运行时上下文串起来。
