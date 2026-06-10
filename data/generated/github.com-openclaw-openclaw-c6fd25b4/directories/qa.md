# 目录：qa

## 它负责什么

`qa` 是 OpenClaw 仓库里的“场景化 QA 资产目录”，主要保存给私有 `qa-lab` 插件消费的 repo-backed 测试素材。它不是普通单元测试目录，也不是运行时产品代码目录，而是把一组可执行或半可执行的质量验证任务组织成 Markdown 场景包：入口说明、场景索引、按主题分组的场景文件、以及 live credential 租约 broker。

从 `qa/README.md` 和 `qa/scenarios/index.md` 看，这个目录的核心职责有三类：第一，定义 QA suite 的种子资产，例如 kickoff mission、QA operator identity、场景包元数据；第二，用 `qa/scenarios/<theme>/*.md` 描述可运行的场景，每个场景通过 Markdown 内的 `qa-scenario` 与 `qa-flow` 块表达输入、断言、覆盖面和运行约束；第三，为真实渠道或 live lane 提供辅助设施，例如 `qa/convex-credential-broker` 维护共享凭据池的租约接口。

它和真正执行逻辑的边界也很清楚：`qa` 目录更像数据与说明层，执行器主要在 `extensions/qa-lab`，命令入口通过 `openclaw qa ...` 暴露，邻近文档 `docs/concepts/qa-e2e-automation.md` 也把 `qa/` 描述为 repo-backed seed assets。根据当前片段推断，新增 QA 覆盖通常先在这里补场景，再由 `qa-lab`、QA gateway、mock provider 或 live transport lane 读取并执行。

## 直接子目录地图

`qa/scenarios` 是主目录，保存 canonical QA scenario pack。它下面按主题分组，每个主题目录只承载一类行为面，不是独立包。当前可见的主题包括：`agents` 负责 agent 指令遵循、subagent、child link 等行为；`channels` 负责 DM、频道、thread、reaction/edit/delete、webchat routing 等消息面；`character` 负责 persona 和 style eval；`config` 负责配置 patch、apply、restart、capability flip；`jsonl-replay` 保存 JSONL 形式的 replay fixture；`media` 负责图片理解和生成；`memory` 负责 recall、ranking、active memory、thread isolation；`models` 负责 provider 能力、model switch、thinking visibility 等；`personal` 负责个人助手场景，如提醒、回复、redaction、安全工具跟进；`plugins` 负责 plugin、skill、MCP、manifest、hot reload 等集成；`runtime` 覆盖 turn recovery、compaction、approval、observability smoke、inventory drift、soak 等运行时行为；`scheduling` 负责 cron 和 recurring work；`security` 当前聚焦 secret redaction；`ui` 负责 Control UI 与 qa-channel 图像 roundtrip；`workspace` 负责读仓库、产物构建、长任务审计等 workspace 场景。

`qa/convex-credential-broker` 是单独的 Convex v1 项目，用于 live QA 共享凭据池。它包含 `package.json`、`convex.json` 和 `convex/` 实现目录，提供 acquire、heartbeat、release、admin add/list/remove 等租约与管理接口。它的定位不是场景包本身，而是 Telegram、Discord、Slack、WhatsApp 等真实渠道测试所需的凭据协调服务。

根下的 `qa/README.md` 是目录说明；`qa/scenarios.md` 是轻量跳转说明，指出 canonical source 已迁到 `qa/scenarios/index.md` 和各主题场景文件；`qa/frontier-harness-plan.md` 与 `qa/new-scenarios-2026-04.md` 更像规划和扩展记录，不是主执行入口。

## 关键入口

最重要的阅读入口是 `qa/README.md`。它用很短的篇幅说明目录里有哪些资产，并直接点出三个关键工作流：`qa suite` 是可执行 frontier subset / regression loop，`qa manual` 是可控的 personality/style probe，`qa coverage` 用来从场景 frontmatter 生成覆盖清单。

场景包入口是 `qa/scenarios/index.md`。它定义 pack-level bootstrap data，包括 QA operator identity、kickoffTask、coverage 规则、runtimeParityTier 语义，以及主题目录清单。对于理解整个 `qa/scenarios` 的组织方式，这个文件比任意单个场景更关键。

单场景入口是 `qa/scenarios/<theme>/*.md`。每个 Markdown 文件通常代表一个 runnable scenario，内部用 `qa-scenario` 描述元数据、覆盖 ID、运行限制、相关源码路径等，再用 `qa-flow` 描述步骤和断言。不要把这些文件当普通说明文档，它们同时是测试数据。

live credential 入口是 `qa/convex-credential-broker/README.md`。它说明 broker 的 HTTP contract、凭据 kind、租约策略和 maintainer CLI 管理方式。涉及真实渠道 QA 或 Convex credential source 时，应从这里开始确认凭据生命周期。

执行命令的产品入口不在 `qa` 目录内，而是在 CLI 与 `extensions/qa-lab` 一侧。邻近证据显示 `package.json` 中有 `qa:lab:build`、`qa:lab:up`、`qa:lab:up:fast`、`qa:prometheus:smoke` 等脚本，`scripts/qa-lab-up.ts`、`scripts/qa-parity-report.ts` 会转到 `extensions/qa-lab/src/cli.runtime.ts`。所以 `qa` 存场景，`extensions/qa-lab` 执行场景。

## 主流程位置

主流程可以按“选择场景、读取场景包、启动 QA lane、执行并汇总”理解。

第一步是场景发现。`qa/scenarios/index.md` 是包级索引，`qa/scenarios/<theme>/*.md` 是实际场景文件。`qa coverage` 会读取这些场景里的 coverage metadata，输出覆盖 inventory。`runtimeParityTier` 用于决定哪些场景进入 Codex-vs-Pi mock gate、optional、live-only 或 soak 分层。

第二步是场景执行。根据文档，`qa suite` 是 repo-backed scenarios 的主要执行命令。场景不直接在 `qa` 里运行，而是由 `qa-lab` 通过 QA gateway lane、mock-openai、qa-channel 或 live transport adapters 执行。常见执行面包括合成消息渠道 `extensions/qa-channel`、调试与报告插件 `extensions/qa-lab`、以及 Matrix/Telegram/Discord/Slack 等 live transport lane。

第三步是观察与报告。`docs/concepts/qa-e2e-automation.md` 描述的 operator flow 是两栏 QA site：左侧 Gateway dashboard，右侧 QA Lab，QA Lab 展示 transcript 和 scenario plan，并导出 Markdown report。根据当前片段推断，场景文件中的断言、coverage ID、docs/code refs 会进入报告或 summary，用于判断场景是否通过、是否覆盖预期行为。

第四步是真实渠道凭据管理。需要 live credentials 的场景不会把 secret 写在 `qa/scenarios` 中，而是通过 `qa/convex-credential-broker` 的租约机制获取。broker 按 `kind` 分池，租约有 heartbeat 和 release，admin 管理接口需要 maintainer secret。这保证 live lane 能共享有限账号，同时避免并发踩踏。

## 推荐阅读顺序

1. 先读 `qa/README.md`，建立 `qa` 目录不是测试 runner、而是 QA 场景资产的基本定位。
2. 再读 `qa/scenarios/index.md`，重点看 pack-level bootstrap、coverage 规则、runtimeParityTier 和主题目录说明。
3. 选一个主题目录抽样读两三个场景，例如 `qa/scenarios/channels/channel-chat-baseline.md`、`qa/scenarios/runtime/otel-trace-smoke.md`、`qa/scenarios/plugins/plugin-manifest-contract-health.md`，理解 `qa-scenario` 与 `qa-flow` 的结构。
4. 如果关注执行链路，再读 `docs/concepts/qa-e2e-automation.md`，把 `qa suite`、`qa coverage`、`qa manual`、`qa ui` 与 `extensions/qa-lab` 的关系串起来。
5. 如果关注 live transport 或真实账号，再读 `qa/convex-credential-broker/README.md`，理解 credential lease 的 acquire、heartbeat、release、admin 管理流程。
6. 最后再看规划类文件 `qa/frontier-harness-plan.md`、`qa/new-scenarios-2026-04.md`，它们适合了解演进方向，不适合作为主流程入口。

## 常见误区

不要把 `qa/scenarios` 当成普通文档目录。里面的 Markdown 文件包含机器可读的 YAML/flow 块，是 QA runner 的数据源；随意改标题、coverage、lane filter 或断言，可能会影响 `qa suite` 和 `qa coverage`。

不要在 `qa` 里找主要执行实现。`qa` 保存场景和辅助资产，执行逻辑主要在 `extensions/qa-lab`、QA CLI、mock provider、transport adapter 和 gateway 相关代码中。根据当前片段推断，`scripts/qa-lab-up.ts` 只是脚本桥接，核心 runtime 在 `extensions/qa-lab/src/cli.runtime.ts` 附近。

不要把所有场景都视为默认 release gate。`qa/scenarios/index.md` 明确区分 `standard`、`optional`、`live-only`、`soak`。有些场景依赖外部服务、真实 provider、长时间运行或人工/VM 环境，只能作为特定 lane 的证据。

不要在场景或说明里写入真实凭据。live QA 的凭据生命周期由 `qa/convex-credential-broker` 管理，场景文件应描述行为和断言，不应承载 secret。

不要逐文件扩展主题目录来理解全局。这个目录的规模已经较大，更有效的方式是先按主题地图建立行为面，再按当前修改或验证目标选择少量代表场景阅读。
