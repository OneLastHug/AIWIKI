# 子系统：packages/coding-agent/test

## 解决什么问题

`packages/coding-agent/test` 是 `@earendil-works/pi-coding-agent` 的行为验证层，目标不是测试某个单点函数，而是持续约束 coding agent CLI、交互模式、会话运行时、扩展系统、配置/认证、工具调用、导出、剪贴板、主题和 RPC/SDK 等用户可感知能力。

这个目录承担三类职责：第一，给 `packages/coding-agent/src` 的核心对象建立回归保护，例如 `AgentSession`、`SessionManager`、`SettingsManager`、`ModelRegistry`、`AuthStorage`、interactive components；第二，提供稳定的测试基建，让测试可以在没有真实 API key、没有真实模型调用、没有网络和付费 token 的情况下运行；第三，用 issue 编号形式沉淀历史 bug 的回归用例，避免 session 切换、队列、扩展、工具过滤、上下文压缩等复杂状态机再次退化。

## 相关目录和文件

`packages/coding-agent/test/*.test.ts` 是传统的包级测试入口，覆盖范围很宽，包括 `agent-session-*`、`interactive-mode-*`、`sdk-*`、`rpc-*`、`extensions-*`、`config*`、`clipboard*`、`theme*`、`tools*` 等主题。它们通常直接 import `../src/...` 中的实现对象，围绕具体模块或 CLI 行为构造断言。

`packages/coding-agent/test/suite/` 是较新的 harness-based 测试区，`README.md` 明确要求这里用于 `AgentSession` 和 `AgentSessionRuntime` 的新测试。广义生命周期和刻画测试放在 `test/suite/` 根下，issue 级回归放在 `test/suite/regressions/`，命名采用 `<issue-number>-<short-slug>.test.ts`。

`packages/coding-agent/test/suite/harness.ts` 是新测试基建核心。它通过 `registerFauxProvider` 注册 `packages/ai` 提供的 faux provider，构造内存态 `SessionManager`、`SettingsManager`、`AuthStorage`、`ModelRegistry` 和 `AgentSession`，并暴露 `setResponses`、`appendResponses`、`eventsOfType`、`cleanup` 等测试辅助能力。

`packages/coding-agent/test/test-harness.ts` 是旧 harness，文件注释说明它也能创建 faux stream、完整 `AgentSession` 和事件捕获，但 `test/suite/README.md` 建议新测试优先使用 `test/suite/harness.ts`，除非缺少能力才扩展旧路径。

`packages/coding-agent/test/utilities.ts` 是共享工具集合，提供 `createTestResourceLoader`、`createTestExtensionsResult`、`userMsg`、`assistantMsg`，也包含读取真实 `~/.pi/agent/auth.json` 的辅助函数。这里既服务纯单元测试，也服务少量需要模拟扩展、skills、prompts、OAuth 状态的集成式测试。

`packages/coding-agent/test/fixtures/` 保存测试夹具，例如 session JSONL、空 agent/cwd、skills 与 skills-collision 等。它不是业务数据目录，而是用于稳定复现资源发现、技能解析、会话压缩和迁移等场景。

包级运行配置在 `packages/coding-agent/vitest.config.ts`，它把 `@earendil-works/pi-ai`、`@earendil-works/pi-agent-core`、`@earendil-works/pi-tui` alias 到 monorepo 内的源码入口，确保测试验证当前工作区源码，而不是已发布包。根目录 `test.sh` 会临时移走真实 auth 文件、清除各类 provider 环境变量并设置 `PI_NO_LOCAL_LLM=1`，用于避免测试意外命中真实服务。

## 核心对象

`AgentSession` 是测试中最核心的被测对象，负责消息、工具、模型、扩展事件、上下文压缩、重试、队列、运行时事件和会话树等行为。大量 `agent-session-*` 文件以及 `test/suite/*` 都围绕它建立状态机断言。

`AgentSessionRuntime` 是更高一层的运行时协调对象，根据当前片段推断，它负责把 session 的新建、恢复、fork、跨 cwd 替换、扩展事件和 runtime 事件连接起来；依据是 `test/suite/agent-session-runtime.test.ts` 中对 `createAgentSessionRuntime`、`createAgentSessionServices`、`createAgentSessionFromServices` 的组合测试。

`SessionManager` 管理会话持久化、树遍历、标签、自定义 session id、文件操作和迁移，集中测试在 `test/session-manager/` 以及 session selector 相关测试中。

`SettingsManager`、`AuthStorage`、`ModelRegistry` 共同支撑配置、认证和模型解析。测试通常使用 `inMemory()` 或临时目录，避免污染真实用户配置；涉及真实 OAuth 的工具函数被隔离在 `utilities.ts`，并且运行脚本会主动清空环境变量。

`ResourceLoader` 和 extension runtime 是扩展、skills、prompts 的入口。`createTestResourceLoader` 默认返回空 extensions/skills/prompts，测试需要扩展行为时通过 `createTestExtensionsResult` 注入 factory，从而验证 `before_provider_request`、`after_provider_response`、context transform、compaction hooks、tool/command 注册等机制。

`FauxProviderRegistration` 是新 suite 的关键模拟模型对象。测试通过它排队响应、追加响应、查询剩余响应数，既能模拟普通文本，也能模拟 tool call、错误、usage、不同模型返回等 provider 行为。

## 运行流程

典型 suite 测试流程是：调用 `createHarness` 创建临时目录和 faux provider；构造内存态 session/config/auth/model registry；必要时注册 tools、extensions、resource loader 或 settings；用 `setResponses` 安排模型响应；驱动 `session` 执行 prompt、tool 或 runtime 操作；最后从 `harness.session.messages`、`events`、`eventsOfType`、`SessionManager` 状态中断言结果，并调用 `cleanup` 释放临时资源。

传统测试流程更分散：一部分直接测试纯函数，例如路径、ANSI、frontmatter、truncate、format resume command；一部分实例化 UI component 并检查渲染文本或键盘行为；一部分调用 CLI `main` 或 spawn 子进程检查参数、stdout/stderr、包管理命令和启动流程；还有一部分用 `vi.mock` 替换 clipboard、child_process、网络或文件系统边界。

默认包脚本是 `packages/coding-agent/package.json` 中的 `npm test`，实际执行 `vitest --run`。仓库规则更推荐从根目录使用 `./test.sh` 跑非 e2e 测试，因为它会屏蔽本机 API key 和真实 auth，降低测试因开发者环境不同而不稳定的概率。

## 上下游依赖

上游主要是 `packages/coding-agent/src` 的实现层，以及 monorepo 内的 `packages/ai/src`、`packages/agent/src`、`packages/tui/src`。Vitest alias 使测试直接依赖这些源码入口：`@earendil-works/pi-ai` 提供模型、stream、OAuth、faux provider；`@earendil-works/pi-agent-core` 提供 `Agent`、tool/message 类型和基础执行语义；`@earendil-works/pi-tui` 支撑交互组件渲染相关测试。

下游是开发流程和发布质量门槛。这里的测试结果会影响 `npm run check`、包级 `npm test`、根级 `./test.sh` 以及回归验证。对 `src/core`、`src/modes/interactive`、`src/utils`、`src/main.ts`、SDK/RPC API 的修改，通常都需要回到这个目录补充或更新测试。

## 修改时最容易踩的坑

最常见的问题是误用真实 provider。`test/suite/README.md` 明确要求 suite 使用 faux provider，不使用真实 API、真实 key、网络调用或付费 token。新增 `AgentSession`/runtime 测试时，应优先放入 `test/suite/` 并使用 `test/suite/harness.ts`。

第二个坑是污染本机状态。部分工具函数知道真实 `~/.pi/agent/auth.json` 的位置，但普通测试应使用 `inMemory()` 或临时目录。运行测试也应注意根目录 `test.sh` 会备份并恢复 auth 文件，同时清空 provider 环境变量。

第三个坑是扩展旧 harness。`test/test-harness.ts` 仍存在，但新 suite 的说明要求不要继续扩展旧路径，除非新 harness 缺少必要能力。否则测试基建会继续分叉，增加维护成本。

第四个坑是回归测试命名和位置不一致。issue 专属回归应放在 `packages/coding-agent/test/suite/regressions/`，并按 `<issue-number>-<short-slug>.test.ts` 命名，方便追溯历史问题。

第五个坑是把 UI 渲染测试写成脆弱快照。此目录更多通过 `stripAnsi`、宽度计算、事件和状态断言来锁定行为；修改 footer、selector、theme、tool execution component 时，要同时考虑终端宽度、ANSI 清理和键盘输入路径。

## 推荐阅读顺序

1. 先读 `packages/coding-agent/test/suite/README.md`，理解新测试组织规则和 faux provider 要求。
2. 再读 `packages/coding-agent/test/suite/harness.ts`，掌握当前推荐的 `AgentSession` 测试搭建方式。
3. 接着读 `packages/coding-agent/test/utilities.ts`，了解 extensions、resource loader、auth 和消息夹具如何复用。
4. 然后选择 `packages/coding-agent/test/suite/agent-session-runtime.test.ts`、`packages/coding-agent/test/suite/agent-session-prompt.test.ts`、`packages/coding-agent/test/suite/regressions/` 中一个具体文件，观察 harness 在真实测试中的用法。
5. 最后按修改领域阅读对应传统测试：配置看 `config*.test.ts`，交互看 `interactive-mode-*` 和 selector/theme 测试，SDK/RPC 看 `sdk-*`、`rpc-*`，扩展与 skills 看 `extensions-*`、`skills.test.ts`。
