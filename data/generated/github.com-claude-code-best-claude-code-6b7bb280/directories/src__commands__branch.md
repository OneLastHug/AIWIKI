# 目录：src/commands/branch

## 它负责什么

`src/commands/branch` 是“会话分支”命令的实现目录，作用不是操作 Git 分支，而是把当前 Claude Code 对话复制出一条新的会话线。它会读取当前会话的 transcript，把主对话消息和必要的元数据重写到一个新的 session 文件里，再把用户带到这个新分支上继续聊。

根据当前片段推断，这个目录的职责非常集中：只服务 `/branch` 这类“从当前对话点分叉”的交互，不承担通用会话管理，也不直接处理其它命令的参数解析。

## 直接子目录地图

这个目录没有更深层的子目录，只有两个文件：

- `src/commands/branch/index.ts`：命令定义入口，负责把 `branch` 作为一个 `Command` 注册出去。
- `src/commands/branch/branch.ts`：实际执行逻辑，负责复制 transcript、生成新 session、保存标题、回切到新分支。

从结构上看，这是一个典型的“轻入口 + 重实现”命令目录，`index.ts` 只做暴露，真正的工作都在 `branch.ts`。

## 关键入口

最关键的入口有两个。

第一是 `src/commands/branch/index.ts` 中导出的默认对象。这里定义了：

- `type: 'local-jsx'`
- `name: 'branch'`
- `aliases: feature('FORK_SUBAGENT') ? [] : ['fork']`
- `description: 'Create a branch of the current conversation at this point'`
- `argumentHint: '[name]'`
- `load: () => import('./branch.js')`

这说明它是一个懒加载命令，只有真正触发时才加载实现文件。`fork` 这个别名是否可用，取决于 `FORK_SUBAGENT` feature flag。也就是说，`branch` 和 `fork` 在某些构建/运行配置下并不是固定双入口。

第二是 `src/commands/branch/branch.ts` 里的 `call()`，这是命令的主执行入口。它接收 `onDone`、`context` 和 `args`，然后完成整个分支流程。

## 主流程位置

主流程基本都在 `src/commands/branch/branch.ts`，可以按这条链路理解：

1. `call()` 读取用户输入的可选标题 `args`
2. `createFork()` 生成新的 session：
   - 取当前 session id
   - 定位 transcript 文件
   - 读入当前 transcript
   - 用 `parseJSONL()` 解析日志行
   - 过滤出主对话消息，排除 sidechain 和非消息条目
   - 保留 `content-replacement` 记录，避免分支后上下文重建错误
   - 重写 `sessionId`、`parentUuid`、`forkedFrom`
   - 写入新的 transcript 文件
3. `deriveFirstPrompt()` 从第一条用户消息中提取分支标题候选
4. `getUniqueForkName()` 检查标题冲突，避免重复的 `"(Branch)"` 名称
5. `saveCustomTitle()` 写入可恢复的会话标题
6. `logEvent('tengu_conversation_forked', ...)` 记一次分析事件
7. 构建 `LogOption`，把新分支交给 `context.resume()` 或回退输出提示文本

其中最核心的业务判断点有三个：是否存在可分支的消息、如何继承 content replacement 状态、如何命名新分支。前两个决定分支是否能正确恢复，后一个决定 `/resume` 和列表展示是否好用。

## 推荐阅读顺序

建议按下面顺序看：

1. `src/commands/branch/index.ts`：先确认命令是怎么挂载和懒加载的。
2. `src/commands/branch/branch.ts` 的前半段：先看 `deriveFirstPrompt()`、`createFork()`、`getUniqueForkName()`，理解分支数据如何构造。
3. `src/commands/branch/branch.ts` 的 `call()`：再看如何把 fork 写回会话系统并返回 UI。
4. `src/utils/sessionStorage.ts`：如果想理解 `getTranscriptPathForSession`、`saveCustomTitle`、`searchSessionsByCustomTitle` 的具体行为，这里是下游依赖。
5. `src/types/logs.ts`：如果要弄清 `TranscriptMessage`、`ContentReplacementEntry`、`LogOption` 的结构，这里是类型来源。

## 常见误区

最常见的误区是把这里理解成 Git 的 `branch` 命令。实际上它分叉的是“对话会话”，不是仓库历史，虽然内部会保留 `gitBranch` 等 transcript 元数据。

第二个误区是以为只要复制消息数组就够了。这里还要同步 `content-replacement` 记录，否则后续恢复时会把此前被压缩过的 tool_result 当成完整内容处理，导致缓存和上下文状态偏掉。

第三个误区是忽略 `feature('FORK_SUBAGENT')`。`fork` 这个别名不是永远存在的，是否暴露取决于 feature flag，所以文档或调用路径里不要默认它恒定可用。

第四个误区是把 `context.resume()` 当成必然可用。代码里已经准备了 fallback：如果没有 resume 能力，就只输出 `/resume <sessionId>` 提示。也就是说，这个目录既面向完整 TUI 流程，也兼容较弱的运行上下文。
