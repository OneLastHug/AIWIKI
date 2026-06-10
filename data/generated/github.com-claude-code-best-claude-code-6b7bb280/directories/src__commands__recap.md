# 目录：src/commands/recap

## 它负责什么

`src/commands/recap` 实现的是交互式 CLI 里的手动会话回顾命令：用户输入 `/recap`、`/away` 或 `/catchup` 后，系统基于当前会话已有上下文生成一段很短的“回来后快速定位”摘要。它的目标不是压缩上下文、保存总结，也不是生成完整任务报告，而是在用户离开一段时间后，用 1-2 句纯文本说明当前高层目标、正在处理的任务，以及下一步最该做什么。

这个目录的实现刻意很轻：命令入口只负责声明 slash command 元数据、特性开关判断、调用生成函数并把结果转换成 CLI 文本；真正的生成逻辑在 `generateRecap.ts`，它复用主对话循环保存的 `CacheSafeParams`，通过 `runForkedAgent` 发起一次临时的单轮模型请求。请求被限制为不可使用工具、最多一轮、跳过 transcript 写入、跳过 cache 写入，因此它更像是对现有上下文的一次只读旁路询问，不会污染主会话记录。

## 直接子目录地图

该目录很小，直接结构如下：

`src/commands/recap/index.ts` 是命令声明与本地命令入口，导出默认的 `recap` command。

`src/commands/recap/generateRecap.ts` 是摘要生成核心，负责选择中英文 prompt、读取最近一次可安全复用缓存的请求参数、运行 forked agent，并把模型返回规整为 `RecapResult`。

`src/commands/recap/__tests__/recap.test.ts` 是单元测试目录，目前主要覆盖命令元数据、开关行为、别名、非交互支持情况，以及 `call()` 对不同 `RecapResult.kind` 的文本映射。

没有更深层的业务子目录，也没有 UI 组件、状态存储或服务端模块。它依赖外部工具函数和命令注册系统完成上下文复用、模型调用和 slash command 接入。

## 关键入口

最直接的入口是 `src/commands/recap/index.ts` 中的默认导出 `recap`。它是一个 `Command` 对象，关键字段包括：

`type: 'local'` 表示这是本地执行的 slash command，而不是 prompt command。

`name: 'recap'` 定义主命令 `/recap`。

`aliases: ['away', 'catchup']` 提供 `/away` 和 `/catchup` 两个等价入口。

`supportsNonInteractive: false` 说明它只面向交互式会话，不支持非交互模式。

`isEnabled()` 同时检查 `feature('AWAY_SUMMARY')` 和 GrowthBook flag `tengu_sedge_lantern`。根据代码注释，这样做是为了让手动 `/recap` 与 REPL 中自动 “while you were away” 卡片的开关保持一致。

`load()` 返回包含 `call` 的对象。`call` 是真正被命令系统执行的函数，它动态导入 `./generateRecap.js`，取 `context.abortController?.signal`，然后调用 `generateRecap(signal)`。动态导入的目的在注释中写得很清楚：避免在命令模块加载阶段引入较重的 `forkedAgent` 依赖。

全局接入点在 `src/commands.ts`。该文件导入 `./commands/recap/index.js`，并把 `recap` 放入 `COMMANDS` 数组。也就是说，命令能否被 slash command 系统看到，首先取决于它是否出现在这里；能否展示或执行，再由 `isEnabled()` 这类命令元数据控制。

## 主流程位置

主流程可以按“命令注册、命令调用、摘要生成、结果映射”理解。

第一步，`src/commands.ts` 把 `recap` 放入内置命令列表。CLI 或 REPL 的命令发现逻辑会从这个列表中读取可用命令。

第二步，用户在交互式会话中输入 `/recap`、`/away` 或 `/catchup`。命令系统命中 `src/commands/recap/index.ts` 的 `call`。在调用前，`isEnabled()` 会要求 `AWAY_SUMMARY` feature flag 开启，并且 `tengu_sedge_lantern` flag 为真。

第三步，`call` 调用 `generateRecap(signal)`。`generateRecap.ts` 先通过 `getLastCacheSafeParams()` 读取上一轮主对话保存的可安全缓存参数。如果没有上一轮上下文，就返回 `{ kind: 'no-turn' }`，入口层会显示 “Nothing to recap yet — send a message first.”。

第四步，如果存在 `cacheSafeParams`，代码创建内部 `AbortController`，并把父级 signal 的 abort 传递进去。随后调用 `runForkedAgent()`，传入一条由 `createUserMessage()` 构造的 recap prompt。prompt 会根据 `getResolvedLanguage()` 选择英文或中文；如果语言模块加载失败，则回退英文 prompt。

第五步，`runForkedAgent()` 的参数体现了这个功能的边界：`canUseTool` 永远返回 deny，`maxTurns: 1` 限制只跑一轮，`querySource` 和 `forkLabel` 都标为 `away_summary`，`skipCacheWrite: true` 与 `skipTranscript: true` 表示不写主缓存、不写会话记录。根据当前片段推断，这个 forked agent 会复用主循环缓存前缀来节省上下文成本，依据是文件注释和 `cacheSafeParams` 参数传递。

第六步，生成函数检查结果。如果被取消，返回 `aborted`；如果消息中有 `isApiErrorMessage` 的 assistant message，返回 `api-error` 并透传文本；否则取最后一条正常 assistant message 的文本，修剪空白后返回 `ok`。没有有效 assistant 文本则返回 `failed`。入口层再把这些分支映射成用户可见的短文本。

## 推荐阅读顺序

建议先读 `src/commands/recap/index.ts`。这个文件能快速建立功能边界：它是 local command，有哪些别名，何时启用，执行后会对不同结果显示什么。

第二步读 `src/commands/recap/generateRecap.ts`。重点看 `RecapResult` 联合类型、`getRecapPrompt()`、`generateRecap()` 里对 `getLastCacheSafeParams()` 和 `runForkedAgent()` 的使用。读懂这部分，就能理解 recap 为什么依赖上一轮会话，以及为什么它不会调用工具或写入 transcript。

第三步看 `src/commands.ts` 中 `recap` 的导入和 `COMMANDS` 数组位置，确认它如何被全局命令系统发现。

最后再读 `src/commands/recap/__tests__/recap.test.ts`。测试不需要逐行看，关注它覆盖了哪些行为：元数据、别名、开关、`load()`、`call()` 的结果映射，以及 abort signal 是否传入生成函数。这些测试相当于该目录公共契约的简表。

## 常见误区

不要把 `/recap` 理解成 `/summary` 或上下文压缩。`recap` 只生成临时短摘要，不承担长期记忆、会话压缩或恢复上下文的职责。目录中也没有写入 summary 文件、更新 state、修改 transcript 的逻辑。

不要以为它可以在没有历史消息时工作。`generateRecap()` 明确依赖 `getLastCacheSafeParams()`；没有上一轮主对话参数时直接返回 `no-turn`。

不要在这里寻找工具调用权限流程。`runForkedAgent()` 虽然是 agent 形式，但这里的 `canUseTool` 固定 deny，并且提示信息是 `Recap cannot use tools`。这意味着 recap 只能根据已有上下文回答，不能读取文件、执行命令或访问外部资源。

不要忽略 feature flag。即使 `recap` 已经注册到 `src/commands.ts`，`isEnabled()` 仍要求 `AWAY_SUMMARY` 开启，并且 GrowthBook flag 通过。手动命令和自动 away summary 卡片共享开关语义，这是它与普通 always-on 命令的主要差异。

不要把测试里的 mock 当成真实运行链路。`__tests__/recap.test.ts` 会 mock `generateRecap` 等依赖，用于验证命令层行为；真实模型调用路径仍在 `generateRecap.ts` 通过 `runForkedAgent()` 完成。
