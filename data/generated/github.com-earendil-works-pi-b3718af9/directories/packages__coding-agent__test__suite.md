# 目录：packages/coding-agent/test/suite

## 它负责什么

`packages/coding-agent/test/suite` 是 `packages/coding-agent` 里围绕新测试框架建立的会话级测试目录，主要覆盖 `AgentSession` 和 `AgentSessionRuntime` 的核心行为。它不是端到端真实模型测试，而是使用 `test/suite/harness.ts` 搭配 `@earendil-works/pi-ai` 的 `faux` provider，把模型响应、工具调用、扩展事件、设置、认证和会话存储都控制在本地内存或临时目录中，从而保证测试可重复、CI 安全、不依赖真实 API key、网络或付费 token。

从测试主题看，这个目录承担的是“编码代理运行时语义”的行为刻画：一次 prompt 如何进入模型、assistant 消息如何落库、工具调用如何执行并继续下一轮、扩展如何拦截或改写事件、bash 输出如何记录、队列消息如何插入、自动重试与压缩如何触发、运行时如何切换或 fork session。也就是说，它关注的不是 UI 表现，也不是单个工具函数的低层单测，而是 `coding-agent` 核心会话循环在各种边界条件下是否稳定。

目录中的测试多使用 `characterization` 命名，说明它们既是回归保护，也是当前系统行为的可执行说明。新增 issue 级别回归通常不直接混入主测试文件，而是放到 `regressions` 子目录，并按 issue 编号命名。

## 直接子目录地图

当前直接子目录只有一个：

`packages/coding-agent/test/suite/regressions`：issue 或缺陷修复导向的回归测试区。文件名遵循 `<issue-number>-<short-slug>.test.ts` 风格，例如 `2023-queued-slash-command-followup.test.ts`、`2781-skill-collision-precedence.test.ts`、`3302-find-path-glob.test.ts`、`5109-exclude-tools.test.ts`。这里的测试覆盖范围比主干测试更分散，可能涉及 session、extensions、tools、resource loader、interactive mode、settings reload、OAuth prompt 等。它们的共同点不是模块归属，而是“曾经出过问题，需要固定住行为”。

根目录本身还放置一组宽主题测试文件：`agent-session-prompt.test.ts`、`agent-session-queue.test.ts`、`agent-session-retry-events.test.ts`、`agent-session-bash-persistence.test.ts`、`agent-session-compaction.test.ts`、`agent-session-model-extension.test.ts`、`agent-session-runtime.test.ts`。这些文件构成主行为地图，按能力域组织，而不是按源码文件一一对应。

## 关键入口

`packages/coding-agent/test/suite/README.md` 是规则入口。它明确说明该目录用于新的 harness-based 测试，要求使用 `test/suite/harness.ts`，使用 `packages/ai/src/providers/faux.ts` 的 faux provider，禁止真实 provider、真实 API key、网络调用和付费 token。它还规定了组织方式：宽泛生命周期和行为刻画测试放在 `test/suite/` 根部，issue 级回归放在 `test/suite/regressions/`。

`packages/coding-agent/test/suite/harness.ts` 是技术入口。它导出 `createHarness`、`getMessageText`、`getUserTexts`、`getAssistantTexts` 以及 `Harness` 类型。`createHarness` 会创建临时目录，注册 `fauxProvider`，构造 `Agent`、`SessionManager.inMemory()`、`SettingsManager.inMemory()`、`AuthStorage.inMemory()`、`ModelRegistry.inMemory()`，再实例化 `AgentSession`。测试通过 `setResponses`、`appendResponses` 控制模型返回，通过 `events` 和 `eventsOfType` 观察 session 事件，通过 `cleanup` 释放临时目录和注销 faux provider。

`agent-session-runtime.test.ts` 是运行时入口。它不只使用 `createHarness`，而是直接围绕 `createAgentSessionRuntime`、`createAgentSessionServices`、`createAgentSessionFromServices` 构造更接近真实 runtime 的环境，用来测试 session 切换、恢复、fork、cwd 更新、session lifecycle extension events 等。

## 主流程位置

被测主流程在源码侧主要落在 `packages/coding-agent/src/core/agent-session.ts` 和 `packages/coding-agent/src/core/agent-session-runtime.ts`。前者定义 `AgentSessionEvent` 和 `AgentSession`，是 prompt、消息、工具调用、扩展事件、重试、压缩、bash 记录、模型切换等行为的核心位置；后者定义 `AgentSessionRuntime`，负责更高一层的 session 生命周期、切换、fork、服务组装和运行时状态更新。测试中还会间接触达 `packages/coding-agent/src/core/agent-session-services.ts`、`settings-manager.ts`、`session-manager.ts`、`model-registry.ts`、`auth-storage.ts`、`core/extensions` 等配套模块。

典型测试流程是：测试调用 `createHarness()` 创建内存化 session 环境；用 `harness.setResponses([...])` 准备 faux 模型响应；调用 `harness.session.prompt("...")` 或 `sendUserMessage`、`compact`、`setModel`、`executeBash` 等 session API；然后断言 `harness.session.messages`、`harness.sessionManager.getEntries()`、`harness.events`、工具执行记录或扩展回调记录。涉及工具调用时，faux assistant response 会返回 `fauxToolCall`，`AgentSession` 执行本地测试 tool，记录 `toolResult`，再继续消费后续 faux assistant response。

队列相关主流程在 `agent-session-queue.test.ts` 中最集中：它构造一个等待释放的 `wait` tool，让 session 处于 streaming 或 tool execution 状态，然后测试 extension-origin 的 `steer`、`followUp`、`nextTurn` 消息在当前轮或下一轮中的插入顺序。重试和事件顺序集中在 `agent-session-retry-events.test.ts`；压缩集中在 `agent-session-compaction.test.ts`；模型与扩展 hook 集中在 `agent-session-model-extension.test.ts`；bash 和持久化集中在 `agent-session-bash-persistence.test.ts`。

## 推荐阅读顺序

建议先读 `packages/coding-agent/test/suite/README.md`，理解这个测试目录的边界：它是 deterministic suite，不应接触真实 provider。然后读 `packages/coding-agent/test/suite/harness.ts`，重点看 `HarnessOptions`、`Harness`、`createHarness` 的组装过程，弄清楚 faux provider、in-memory managers、extensionFactories、tool override 和事件收集是如何注入的。

接着读 `agent-session-prompt.test.ts`。这个文件最适合作为会话主循环入门：普通 prompt、工具调用、多工具调用、附件、skill command、prompt template、extension command、空 model 或无 auth 异常都在这里。之后读 `agent-session-queue.test.ts`，理解 streaming 期间用户消息和扩展消息如何排队。再读 `agent-session-retry-events.test.ts`，把事件顺序、自动重试、错误和 abort 的语义补齐。

然后按关注点阅读：想理解上下文压缩读 `agent-session-compaction.test.ts`；想理解模型选择、thinking level、extension hook 读 `agent-session-model-extension.test.ts`；想理解 bash 记录和 session persistence 读 `agent-session-bash-persistence.test.ts`；想理解跨 session 的生命周期读 `agent-session-runtime.test.ts`。最后再进入 `regressions`，按 issue 文件名挑选相关问题阅读，不需要从头到尾逐个展开。

## 常见误区

第一个误区是把这里当成真实 provider 集成测试。这个目录明确使用 faux provider，测试的是 `AgentSession` 周边控制流和状态变化，不验证真实模型服务、真实网络错误或实际 API 兼容性。即使测试里出现 provider、model、apiKey，也通常是内存注册出来的 `faux-key`。

第二个误区是认为 `harness.ts` 只是工具函数。实际上它定义了本目录测试的世界模型：临时 cwd、内存 session manager、内存 settings、内存 auth、faux model registry、extension runner 引用、base tools override 都在这里统一搭建。读测试前不理解 harness，很多断言会显得像魔法。

第三个误区是把 `regressions` 看成低优先级杂项。它确实按 issue 聚合，但不少文件覆盖关键边界，例如 queued slash command、skill precedence、tool allowlist/exclude、settings reload、session replacement、signal shutdown cleanup。这些测试经常说明系统在真实使用中最容易破坏的行为。

第四个误区是按源码文件机械寻找一一对应关系。根部测试文件是按行为域组织的：prompt、queue、retry/events、bash/persistence、compaction、model/extension、runtime。一个测试文件可能同时触达 `AgentSession`、`SessionManager`、`ExtensionRunner`、`ModelRegistry` 和资源加载逻辑。阅读时应沿“用户动作或 extension 事件如何改变 session 状态”这条线看，而不是只看 import 列表。

第五个误区是忽略清理逻辑。测试通常在 `afterEach` 中调用 `harness.cleanup()` 或 runtime cleanup，释放临时目录并注销 faux provider。新增测试如果忘记清理，可能污染 provider registry、临时文件或后续测试状态，导致顺序相关的隐性失败。
