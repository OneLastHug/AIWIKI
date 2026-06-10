# 目录：src/commands/autofix-pr

## 它负责什么

这个目录实现的是 `autofix-pr` 命令的完整闭环，目标是自动接管一个 PR 的 CI 失败修复流程。它不是单纯的参数解析器，而是把“本地命令触发、仓库识别、远程会话启动、单例监控、轮询判定、结果回传”串成了一条线。

根据当前片段推断，它的职责大致分成四层：第一层是命令入口与可用性控制；第二层是把用户输入解析成“启动、停止、非法、自由文本”等动作；第三层是启动远程修复会话并注册成长期任务；第四层是后台监控 PR 状态，直到判断出修复完成、失败或被中止。

## 直接子目录地图

这个目录的生产代码基本是平铺的，没有再往下拆出功能子目录。唯一的直接子目录是 `__tests__`，用于放置命令相关的单测。

可以把它理解成“一个命令一个小工作区”：

- `__tests__`：覆盖参数解析、入口注册、监控状态、结果抽取、启动流程和进度组件。
- 其余文件都在目录根部，按功能各自分工，不再继续分层。

这种结构说明这里的重点不是通用框架，而是围绕 `autofix-pr` 这条业务链做局部编排。

## 关键入口

真正的命令注册入口是 `index.ts`。它定义了 `autofix-pr` 这个 `Command`，并通过 `load()` 动态加载 `launchAutofixPr.js`，把实际执行逻辑延迟到需要时再引入。

`index.ts` 还有两个关键点：

- 用 `feature('AUTOFIX_PR')` 控制命令是否启用。
- 用 `getBridgeInvocationError()` 限制桥接调用的参数形态，支持 `PR_NUMBER`、`stop`、`OWNER/REPO#N` 三类输入。

因此，从 CLI 角度看，`index.ts` 是目录对外的门面；从执行角度看，真正的主入口在 `launchAutofixPr.ts` 的 `callAutofixPr()`。

## 主流程位置

主流程几乎都集中在 `launchAutofixPr.ts`，这也是这个目录最值得看的文件。

它的执行顺序大致是：

1. `parseArgs.ts` 先把原始输入解析成结构化动作。
2. 如果是 `stop`，则从 `monitorState.ts` 里清理当前监控锁。
3. 如果是启动动作，则先用 `detectCurrentRepositoryWithHost()` 确认当前目录是 GitHub 仓库。
4. 再做仓库匹配检查，避免 `owner/repo#n` 和当前工作目录不一致。
5. 调用 `checkRemoteAgentEligibility()` 判断远程 agent 是否可用。
6. 用 `skillDetect.ts` 找可选的本地技能说明，拼进初始提示词。
7. 通过 `createAutofixTeammate()` 构造一个临时协作者，再借助 `trySetActiveMonitor()` 抢占单例监控锁。
8. 调用 `teleportToRemote()` 启动远程会话。
9. 用 `fetchPrHeadSha()` 记录初始 head SHA，供后续轮询比较。
10. 通过 `registerRemoteAgentTask()` 注册长期任务，并把锁的 taskId 更新成框架分配的真实值。
11. 最后返回 `AutofixProgress.tsx` 作为内联进度展示。

后续的完成检测逻辑则分散在两处：

- `prFetch.ts` 负责调用 `gh pr view` 拉取 PR 快照，再交给纯函数 `summariseAutofixOutcome()`。
- `prOutcomeCheck.ts` 负责判断“已合并、已关闭、已推送新提交、CI 成功/失败/待定”等状态。

结果回传方面，`extractAutofixResult.ts` 会从远程会话日志里提取 `<autofix-result>` 标签，给本地侧一个结构化摘要，而不是只给一条“任务已完成”的笼统通知。

状态控制则由 `monitorState.ts` 统一管理，确保同一时刻只能有一个活跃的 `autofix-pr` 监控实例。

## 推荐阅读顺序

1. `index.ts`：先看命令如何暴露出来，以及 feature flag 怎么控制启用。
2. `parseArgs.ts`：了解用户输入会被拆成哪些动作。
3. `launchAutofixPr.ts`：这是主编排器，先读整体流程，再回头看细节。
4. `monitorState.ts`：理解为什么这里需要单例锁，以及 taskId 为什么会被更新。
5. `prFetch.ts`、`prOutcomeCheck.ts`：看完成判定是怎么从 PR 状态推出来的。
6. `extractAutofixResult.ts`、`AutofixProgress.tsx`：最后看结果展示和进度 UI。

## 常见误区

1. 它不是一个“只负责修 PR 的简单命令”。这里实际上包含了远程会话生命周期管理、状态轮询和结果抽取。
2. `OWNER/REPO#N` 并不代表真的支持跨仓库自动修复。`launchAutofixPr.ts` 里只是做了安全校验，核心执行仍然依赖当前工作目录的仓库上下文。
3. `stop` 只是停止本地监控锁，不等于立刻终止远程 session。代码里已经明确说明，云端会话可能继续运行到结束或被单独取消。
4. 结果完成判定不是只看“PR 关了没有”。`prOutcomeCheck.ts` 还会结合 head SHA 和 CI rollup 判断是否真的已经推送修复、CI 是否通过。
5. `extractAutofixResult.ts` 不是通用 XML 解析器，它只是面向 `<autofix-result>` 的定向提取器，而且优先扫描最新的 hook 输出和 assistant 文本块。
6. `__tests__` 里的测试不是附属装饰，它们实际上覆盖了这个目录最关键的边界：参数合法性、监控锁、结果判定和启动失败路径。
