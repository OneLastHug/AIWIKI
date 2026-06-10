# 目录：src/commands/rename

## 它负责什么

`src/commands/rename` 实现的是交互式 CLI 中的 `/rename` 本地命令，用来给当前会话改名。它的职责边界很窄：接收用户输入的名称，或者在用户没有提供名称时基于当前对话内容自动生成一个短名称；随后把这个名称写入会话存储，并同步更新当前 AppState 中用于提示栏展示的独立 agent 名称。

从当前片段看，这个目录不负责命令解析框架、不负责会话列表展示，也不负责 transcript 的整体读写机制。它只调用外部能力完成这些事情：通过 `getSessionId()` 取得当前会话 id，通过 `getTranscriptPath()` 定位 transcript，通过 `saveCustomTitle()` 和 `saveAgentName()` 持久化名称，通过 `context.setAppState()` 更新 UI 状态。换句话说，它是“会话标题变更”这个行为的命令层封装。

这个命令还有两个额外约束：第一，如果当前进程是 swarm teammate，会拒绝重命名，因为 teammate 名称由 team leader 管理；第二，如果当前会话存在 `replBridgeSessionId`，会尝试把标题同步到 bridge session，这个同步是 best-effort、非阻塞的，失败会被吞掉，不影响本地重命名结果。

## 直接子目录地图

`src/commands/rename` 没有直接子目录，只有三个主要文件：

`src/commands/rename/index.ts` 是命令元信息入口，声明命令名、描述、参数提示、加载方式等。

`src/commands/rename/rename.ts` 是 `/rename` 的执行主体，导出 `call()`，负责参数判断、权限/角色限制、持久化和状态更新。

`src/commands/rename/generateSessionName.ts` 是自动命名辅助模块，在用户只输入 `/rename` 而没有参数时，根据当前对话内容调用轻量模型生成 kebab-case 名称。

因此这个目录不是一个复杂子系统，更像是 `src/commands` 下一个标准的 local-jsx slash command 小模块。

## 关键入口

最外层入口是 `src/commands/rename/index.ts` 中的默认导出对象 `rename`。它满足 `Command` 类型，关键字段包括：

`type: 'local-jsx'` 表示这是一个本地执行的 JSX 命令类型，命令不需要作为普通模型请求发送出去。

`name: 'rename'` 决定用户侧命令名是 `/rename`。

`description: 'Rename the current conversation'` 用于命令说明或命令选择界面。

`immediate: true` 表示命令应立即执行，而不是等待更多交互步骤。

`argumentHint: '[name]'` 说明参数是可选名称；不传名称时进入自动生成逻辑。

`load: () => import('./rename.js')` 是实际执行模块的动态加载入口。根据当前片段推断，命令系统会先收集这些 `Command` 元信息，用户触发 `/rename` 时再通过 `load()` 加载 `rename.ts` 编译后的模块，并调用其中约定的 `call()` 函数。这个推断依据是 `index.ts` 只暴露元数据和动态 import，而真正的执行函数位于 `rename.ts`。

## 主流程位置

主流程集中在 `src/commands/rename/rename.ts` 的 `call()` 函数。

流程第一步是 teammate 检查。`call()` 先调用 `isTeammate()`，如果当前会话属于 swarm teammate，就通过 `onDone()` 输出系统消息：当前 session 不能重命名，因为 teammate 名称由 team leader 设置，然后直接返回 `null`。这说明 `/rename` 在 swarm 场景下不是普适命令，而是受角色约束的会话命令。

第二步是确定新名称。如果 `args` 为空或只有空白字符，命令会调用 `generateSessionName()` 自动生成名称。传入的消息不是完整历史，而是 `getMessagesAfterCompactBoundary(context.messages)` 的结果，也就是压缩边界之后的对话内容。这可以避免旧上下文或已压缩内容干扰当前会话主题。如果自动生成失败，例如没有可用对话内容，命令会提示 `Usage: /rename <name>`。如果用户提供了参数，则直接使用 `args.trim()` 作为名称，不做额外格式化。

第三步是本地持久化。函数通过 `getSessionId()` 取得当前 session id，通过 `getTranscriptPath()` 取得当前 transcript 路径，然后调用 `saveCustomTitle(sessionId, newName, fullPath)` 保存自定义标题。这里的 custom title 更接近会话列表或 transcript 元数据里的显示标题。

第四步是 bridge 同步。`call()` 从 `context.getAppState()` 读取 `replBridgeSessionId`。如果存在 bridge session，就动态 import `src/bridge/createSession.js`，调用 `updateBridgeSessionTitle()` 把新名称同步到远端 bridge 会话。同步使用 `getBridgeBaseUrlOverride()` 和 `getBridgeTokenOverride()` 支持配置覆盖。这里特意使用 `void import(...).then(...).catch(() => {})`，说明同步不阻塞命令完成，也不把失败暴露给用户。

第五步是更新 agent 名称和 UI 状态。命令调用 `saveAgentName(sessionId, newName, fullPath)`，把新名称也作为 session 的 agent name 持久化；随后通过 `context.setAppState()` 更新 `standaloneAgentContext.name`。注释中说明这个名称用于 prompt-bar display，也就是输入栏或会话提示区域的展示。

最后，`call()` 通过 `onDone()` 输出 `Session renamed to: ${newName}`，并返回 `null`。整个命令没有返回 React 组件，也没有持续交互状态，属于一次性本地命令。

自动生成名称的流程在 `src/commands/rename/generateSessionName.ts`。`generateSessionName()` 先调用 `extractConversationText(messages)` 抽取对话文本；如果没有文本，直接返回 `null`。有文本时，它调用 `queryHaiku()`，用 system prompt 要求生成 2 到 4 个词的 lowercase kebab-case 名称，并要求返回 JSON，schema 中只有必需字段 `name`。模型响应回来后，函数用 `extractTextContent()` 抽取文本，再用 `safeParseJSON()` 解析，只有当解析结果里存在字符串类型的 `name` 字段时才返回该名称。异常不会抛出到命令层，而是用 `logForDebugging()` 记录后返回 `null`。

## 推荐阅读顺序

建议先读 `src/commands/rename/index.ts`，它能快速确认 `/rename` 是什么类型的命令、用户如何触发、执行模块在哪里。

然后读 `src/commands/rename/rename.ts`，这是理解目录职责的核心。重点看 `call()` 的几个分支：`isTeammate()` 限制、空参数自动生成、`saveCustomTitle()`、bridge title sync、`saveAgentName()` 和 `setAppState()`。

最后读 `src/commands/rename/generateSessionName.ts`。这个文件只服务于“无参数 `/rename`”场景，阅读时重点关注它如何从消息中提取上下文、如何调用 `queryHaiku()`、如何用 JSON schema 和 `safeParseJSON()` 控制输出格式。

如果要继续向外扩展阅读，可以看 `src/utils/sessionStorage.js` 中的 `saveCustomTitle()`、`saveAgentName()`、`getTranscriptPath()`，了解名称最终如何写入 transcript 或会话元数据；也可以看 `src/utils/sessionTitle.js` 的 `extractConversationText()`，理解自动命名到底取了哪些消息内容。根据当前片段推断，命令注册和调度逻辑在更上层的 `src/commands.js` 或相关命令聚合模块中，因为 `index.ts` 引用了 `../../commands.js` 的 `Command` 类型，但本目录没有展示注册表本身。

## 常见误区

一个常见误区是把 `/rename` 理解成只改 UI 显示名。实际上它至少写了两类本地数据：`saveCustomTitle()` 保存会话标题，`saveAgentName()` 保存 agent name；同时还更新了 `standaloneAgentContext.name`，让当前运行中的 UI 立即反映变化。

另一个误区是认为不带参数的 `/rename` 一定会成功。自动命名依赖当前对话内容和 `queryHaiku()` 调用；如果压缩边界之后没有可抽取文本，或者模型调用失败、超时、限流、返回非 JSON，都会返回 `null`，最终提示用户手动传入名称。

还要注意，用户手动传入的名称不会被转换成 kebab-case。kebab-case 约束只存在于自动生成名称的 prompt 中。`/rename My Session` 会保存为 `My Session`，因为 `rename.ts` 对参数只做了 `trim()`。

bridge 同步也不应被理解成本地重命名的必要步骤。`updateBridgeSessionTitle()` 是动态加载且非阻塞的，失败会被捕获并忽略；本地保存和 AppState 更新才是命令的主路径。

最后，swarm teammate 场景下这个命令会被明确拒绝。这里不是权限系统漏掉了重命名能力，而是业务规则规定 teammate 名称由 team leader 维护。
