# 目录：src/auto-reply

## 它负责什么

`src/auto-reply` 是 OpenClaw 收到外部消息后“是否回复、怎么回复、把回复送到哪里”的核心编排区。它不直接代表某一个 channel，也不等同于某个模型 provider；它更像位于 channel 输入、agent runtime、session 状态、命令系统和 outbound delivery 之间的自动回复中枢。

从当前片段看，这个目录承担几类职责：第一，规范化 inbound message 上下文，例如 `MsgContext` 到 `FinalizedMsgContext`；第二，识别用户文本里的命令、directive、模型选择、队列策略、权限状态、心跳语义；第三，初始化或恢复 session，并决定本轮是否创建新会话、复用会话、重置会话或转发到目标 session；第四，把消息交给 agent runner 执行，期间处理 media/link understanding、typing、block streaming、tool reply、final reply、pending final delivery 等中间状态；第五，通过 dispatcher 把不同阶段的回复投递回 channel 或 gateway 调用者。

这个目录里测试很多，说明它覆盖的是用户可见行为和跨模块契约：命令解析、回复路由、队列、abort、ACP、subagents、session、typing、media、heartbeat、export 等都在这里形成行为边界。

## 直接子目录地图

`src/auto-reply/reply` 是主体子目录，承载自动回复主流程的大部分实现。入口型文件包括 `get-reply.ts`、`dispatch-from-config.ts`、`reply-dispatcher.ts`、`get-reply-run.ts`、`agent-runner.ts`。周边文件按功能拆成命令、directive、session、queue、routing、delivery、typing、media、provider dispatch 等模块。

`src/auto-reply/reply/queue` 是队列子系统，包含 `enqueue.ts`、`drain.ts`、`state.ts`、`settings.ts`、`cleanup.ts`、`normalize.ts`、`types.ts`。它负责把需要排队或串行化的回复请求收敛成可执行的 turn，避免同一会话或目标上的并发混乱。

`src/auto-reply/reply/exec` 目前从目录列表看主要是 directive 相关代码，和执行指令覆盖、shell/exec 语义相邻。根据当前片段推断，它不是 agent runner 本体，而是对“本轮如何执行”的局部指令解析/适配层，依据是顶层 `reply.ts` 导出 `extractExecDirective`，主执行仍在 `get-reply-run.ts` 与 `agent-runner.ts`。

`src/auto-reply/reply/commands-subagents` 是 subagents 命令动作拆分区，例如 focus、list、log、info、agents、help 等。它服务于 `commands-subagents.ts` 这类上层命令入口，把面向子代理的用户命令分派到具体 action。

`src/auto-reply/reply/commands-acp` 是 ACP 命令相关模块，包含 context、diagnostics、install hints、lifecycle、runtime options、targets、shared 等。它和 `dispatch-acp*.ts`、`acp-*.ts` 文件一起构成 ACP 会话/投影/流式设置/重置目标等路径。

`src/auto-reply/reply/export-html` 放导出会话或轨迹时使用的 HTML 模板资产，包括 `template.html`、`template.css`、`template.js` 和安全测试；`vendor` 是模板依赖资产区。

`src/auto-reply/reply/test-fixtures` 与 `src/auto-reply/test-helpers` 是测试支撑目录，分别服务 reply 子系统和 auto-reply 顶层测试。

## 关键入口

最外层聚合入口是 `src/auto-reply/reply.ts`。它只做导出，不承载业务主逻辑：导出 `getReplyFromConfig`、directive 提取函数、`extractExecDirective`、`extractQueueDirective`、`extractReplyToTag`，以及 `GetReplyOptions`、`ReplyPayload` 类型。外部如果只是“拿一个回复”，通常会通过这里或 `src/auto-reply/reply.runtime.ts` 引到 `getReplyFromConfig`。

调度入口是 `src/auto-reply/dispatch.ts`。它提供 `dispatchInboundMessage`、`dispatchInboundMessageWithBufferedDispatcher`、`dispatchInboundMessageWithDispatcher`。这层负责把上下文 finalize，创建或接收 `ReplyDispatcher`，安装 message_sending hook、silent reply context、typing dispatcher、foreground reply fence，然后调用 `dispatchReplyFromConfig`。它面向 channel/gateway 侧，比 `getReplyFromConfig` 更靠近“收到消息并投递结果”的完整路径。

回复生成入口是 `src/auto-reply/reply/get-reply.ts` 的 `getReplyFromConfig`。它读取 runtime config，解析 agent、session、默认模型、channel model override、heartbeat override、workspace、typing、media/link understanding、message hooks、session state、pending final delivery，然后进入 prepared reply。它是“根据配置和消息上下文生成 ReplyPayload”的核心函数。

运行入口在 `src/auto-reply/reply/get-reply-run.ts` 的 `runPreparedReply`，以及 `src/auto-reply/reply/agent-runner.ts` 的 `runReplyAgent`。前者把已经解析好的命令、directive、模型状态、队列策略、session 信息组装成一次可运行 turn；后者负责真正驱动 agent runtime 并处理 agent 输出。

投递入口是 `src/auto-reply/reply/reply-dispatcher.ts`。`createReplyDispatcher` 和 `createReplyDispatcherWithTyping` 把 `ReplyPayload` 的 block/tool/final 等阶段送入实际 `deliver` 函数，并管理 idle、取消、失败计数、typing 等状态。

## 主流程位置

主流程可以按四段理解。

第一段是 channel/gateway 触发。邻近上下文里 `src/channels/turn/kernel.ts` 出现 `dispatchReplyWithBufferedBlockDispatcher`，`src/gateway/server-restart-sentinel.ts` 也调用 provider dispatcher。根据当前片段推断，channel turn kernel 或 gateway 相关逻辑会把 inbound message 交给 auto-reply 的 dispatch 层，依据是 `rg` 结果显示这些路径引用 auto-reply dispatcher 或 provider dispatcher。

第二段是 `src/auto-reply/dispatch.ts`。这里调用 `finalizeInboundContext`，记录 diagnostics，创建 dispatcher，并进入 `src/auto-reply/reply/dispatch-from-config.ts` 的 `dispatchReplyFromConfig`。`dispatch-from-config.ts` 是一个很大的流程控制点，负责 turn admission、abort、ACP bypass/delivery、reply hook、block/final 投递、operation 生命周期等。

第三段是 `src/auto-reply/reply/get-reply.ts`。当需要实际生成回复时，`dispatchReplyFromConfig` 会懒加载或调用 `getReplyFromConfig`。这一层先处理 native slash fast path，再确保 workspace，做 media/link understanding，触发 pre-agent message hooks，初始化 session，处理 pending final delivery、reset model override、模型覆盖和 fallback，然后构造 prepared reply 参数。

第四段是 `src/auto-reply/reply/get-reply-run.ts` 到 `src/auto-reply/reply/agent-runner.ts`。`runPreparedReply` 处理命令、directive、队列、模型状态、block streaming 和 agent 调用前后的粘合逻辑；`runReplyAgent` 才是具体 agent 执行点。执行结果回到 dispatcher，由 `reply-dispatcher.ts` 和 delivery/routing 模块决定如何发出。

## 推荐阅读顺序

先读 `src/auto-reply/reply.ts`，建立公共导出边界：外部看见的是哪些能力，而不是先陷入命令文件海量细节。

再读 `src/auto-reply/dispatch.ts`，理解 inbound message 进入 auto-reply 后如何被 finalize、包上 dispatcher、hook、typing 和 foreground reply fence。这里是最适合建立全局地图的地方。

第三读 `src/auto-reply/reply/dispatch-from-config.ts`，只看 `dispatchReplyFromConfig` 附近的主分支，不必从头逐行读完整文件。目标是弄清“什么时候直接处理命令、什么时候进入 getReply、什么时候投递 block/final、什么时候 abort 或排队”。

第四读 `src/auto-reply/reply/get-reply.ts` 的 `getReplyFromConfig`，重点看上下文准备、session 初始化、模型选择、media/link understanding、pending final delivery、fast path 和 `runPreparedReply` 调用点。

第五读 `src/auto-reply/reply/get-reply-run.ts` 的 `runPreparedReply`，再跳到 `src/auto-reply/reply/agent-runner.ts` 的 `runReplyAgent`。这样可以把“配置解析”和“真正跑 agent”分开理解。

最后按兴趣读专题：命令看 `src/auto-reply/reply/commands.ts`、`commands-core.ts`、`commands-subagents.ts`；队列看 `src/auto-reply/reply/queue.ts` 和 `src/auto-reply/reply/queue/*`；投递看 `reply-dispatcher.ts`、`reply-delivery.ts`、`route-reply.ts`；ACP 看 `dispatch-acp.ts`、`commands-acp.ts`、`reply/commands-acp/*`。

## 常见误区

不要把 `src/auto-reply/reply.ts` 当成主实现。它只是聚合导出，真正主流程分散在 `dispatch.ts`、`dispatch-from-config.ts`、`get-reply.ts`、`get-reply-run.ts`、`agent-runner.ts`。

不要把 auto-reply 理解成单纯“调用模型返回文本”。它还负责 session、命令、权限、队列、typing、heartbeat、media/link preprocessing、pending final delivery、block streaming、silent reply、hook 和 channel 投递策略。

不要把 `reply/commands-*` 的数量误解为主流程入口很多。大多数命令文件是被命令注册、解析或 dispatch 层调用的叶状能力；学习 overview 时应先抓住 `commands.ts`、`commands-core.ts`、`commands-registry*`、`commands-slash-parse.ts` 这类汇合点。

不要忽略 `dispatch-from-config.ts`。如果只读 `get-reply.ts`，会漏掉 admission、abort、ACP、reply dispatch hook、block/final delivery 等“回复是否真的发出去”的控制逻辑。

不要把 queue 当作普通数组工具。`reply/queue` 关系到会话 turn 的串行化、去重、drain、cleanup 和设置解析，影响多消息连续进入时的用户可见顺序。

不要把测试文件视为噪声。这个目录行为面广，很多真实契约只能从 `*.test.ts`、`*.e2e.test.ts` 看出边界，例如 heartbeat、pending final delivery、ACP abort、subagent routing、media-only run、typing policy。对于 overview 可以不逐个展开，但深入修改前应按专题补读对应测试。
