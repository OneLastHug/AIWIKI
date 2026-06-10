# 目录：src/flows

## 它负责什么

`src/flows` 是 OpenClaw 中“交互式配置流程”和“健康检查流程”的编排层。它不直接代表某一个底层能力，而是把配置、插件、渠道、模型、搜索、doctor 检查、修复等已有模块串成面向 CLI / wizard 的用户流程。

从文件命名和导入关系看，这个目录主要承担三类职责：

第一类是 setup/onboarding 流程。`channel-setup.ts` 负责渠道配置向导，围绕 `ChannelSetupPlugin`、trusted catalog、已安装插件、账户 ID、DM 策略、配置写入后的 hook 等对象组织流程。`provider-flow.ts`、`provider-flow.runtime.ts`、`model-picker.ts`、`search-setup.ts` 则分别处理 provider 选择、模型选择和 web search provider 配置。

第二类是 doctor / health 流程。`doctor-health.ts` 是 `openclaw doctor` 一类命令的高层入口，负责创建 prompter、加载配置、迁移 doctor 配置，并调用健康贡献执行。`doctor-core-checks.ts` 定义核心健康检查，`doctor-health-contributions.ts` 汇总 core 与 plugin 的健康贡献，`doctor-lint-flow.ts`、`doctor-repair-flow.ts` 分别跑只读检查和修复流程。

第三类是 health check 通用协议。`health-checks.ts` 定义 `HealthFinding`、`HealthCheck`、`HealthRepairResult` 等核心类型；`health-check-registry.ts` 提供注册表；`health-check-adapter.ts` 把不同形态的检查统一成可运行对象；`health-check-runner-types.ts` 定义 runner 侧类型。这个小框架让 core check 和 plugin check 可以在 doctor、lint、fix 三种模式中复用。

整体上，`src/flows` 更像“应用流程层”：它靠近用户操作入口，但大量具体实现仍分布在 `src/commands`、`src/channels`、`src/plugins`、`src/config`、`src/gateway`、`src/agents` 等目录中。

## 直接子目录地图

`src/flows` 当前没有直接子目录，所有文件都平铺在目录根部。理解时可以按主题分组，而不是按文件树分层：

`channel-setup.*` 是渠道设置流程组，包含主流程、状态收集、提示文案、测试辅助和测试。

`doctor-*` 是 doctor 健康检查流程组，包含 doctor 命令入口、core 检查、health contribution、lint flow、repair flow、启动维护、错误信息清洗、转换计划以及对应测试。

`health-check-*` 与 `health-checks.ts` 是健康检查协议与注册运行机制。

`provider-flow.*`、`model-picker.ts`、`search-setup.ts` 是 provider、模型、搜索相关的设置流程。

`types.ts` 是通用 flow contribution / option 的轻量类型工具，供 provider/channel 等流程排序和展示选项使用。

## 关键入口

最重要的 CLI / doctor 入口是 `src/flows/doctor-health.ts` 中的 `doctorCommand`。它负责加载 runtime、创建 doctor prompter、打印 wizard header、处理 update 提示、执行若干平台和安装提示，然后加载并可能迁移 doctor config，最后调用 `runDoctorHealthContributions`。

渠道配置入口是 `src/flows/channel-setup.ts` 中的 `setupChannels`。这个函数接收 `OpenClawConfig`、`RuntimeEnv`、`WizardPrompter` 和 `SetupChannelsOptions`，负责发现可见 channel plugin、预加载已配置外部插件、收集状态、处理选择、调用对应 channel setup adapter，并收集配置写入后的 post-write hook。

健康检查注册入口是 `src/flows/doctor-core-checks.ts` 中的 `registerCoreHealthChecks` 和 `createCoreHealthChecks`。前者把 core checks 注册进全局 health check registry，后者构造 core 自带检查列表。`CORE_HEALTH_CHECKS` 是静态核心检查集合。

健康检查运行入口分两条：`src/flows/doctor-lint-flow.ts` 的 `runDoctorLintChecks` 偏只读检查；`src/flows/doctor-repair-flow.ts` 的 `runDoctorHealthRepairs` 偏修复，并会在修复后重新验证相关 finding。

provider 设置入口是 `src/flows/provider-flow.ts` 的 `resolveProviderSetupFlowContributions`，它把 manifest 提供的 provider auth choices 和 install catalog 提供的 provider entries 合并成 setup flow contributions，并用 manifest 结果优先去重。

搜索设置入口是 `src/flows/search-setup.ts` 的 `runSearchSetupFlow`，周边函数负责列出搜索 provider、解析已有 key、应用搜索 provider 选择和 key 写入。

## 主流程位置

渠道主流程集中在 `src/flows/channel-setup.ts`。主线大致是：从当前配置推导 workspace 和默认 agent；读取 active channel setup plugins；必要时通过 channel setup plugin registry snapshot 加载 scoped plugin；合并 active 与 scoped plugin 得到可见渠道；收集 status；展示现有配置状态；根据用户选择或 options 决定是否配置；调用对应 channel 的 setup wizard adapter；写回配置并延迟执行 post-write hook。根据当前片段推断，真正的渠道发现、插件安装、registry snapshot 和 trusted catalog 逻辑不在本目录，而是在 `src/commands/channel-setup/*`、`src/channels/plugins/*` 和 `src/plugins/*`。

doctor 主流程集中在 `src/flows/doctor-health.ts`、`src/flows/doctor-health-contributions.ts`、`src/flows/doctor-core-checks.ts`、`src/flows/doctor-lint-flow.ts`、`src/flows/doctor-repair-flow.ts`。其中 `doctor-health.ts` 负责命令级串联，`doctor-health-contributions.ts` 负责把健康贡献跑起来，`doctor-core-checks.ts` 负责定义 core 层检查项目，`doctor-lint-flow.ts` 负责收集 finding，`doctor-repair-flow.ts` 负责 detect -> repair -> validate 的闭环。

health check 主流程的抽象位于 `src/flows/health-checks.ts`、`src/flows/health-check-registry.ts`、`src/flows/health-check-adapter.ts`。`HealthCheck` 的核心协议是 `detect(ctx, scope)`，可选 `repair(ctx, findings)`。修复流程会先 detect，若存在 finding 且 check 支持 repair，则执行 repair；非 dry-run 情况下还会用 validation scope 再跑一次 detect，确认修复后是否仍有 remaining findings。

provider / model / search 的主流程比 doctor 更轻量，主要是把插件 manifest、安装 catalog、配置状态、用户选择映射成 flow options，然后由更上层 wizard 或 command 使用。

## 推荐阅读顺序

1. 先读 `src/flows/types.ts`，理解 `FlowOption`、`FlowContribution` 以及按 label 排序的基础工具。

2. 再读 `src/flows/health-checks.ts`，掌握 finding、check、repair result、mode、context 等核心协议。读完后再看 `src/flows/health-check-registry.ts` 和 `src/flows/health-check-adapter.ts`，能更容易理解 doctor 为什么可以统一运行 core 与 plugin 检查。

3. 然后读 `src/flows/doctor-health.ts`，把 `doctorCommand` 当作总入口，建立 doctor 的命令级调用链。

4. 接着读 `src/flows/doctor-health-contributions.ts`、`src/flows/doctor-core-checks.ts`、`src/flows/doctor-lint-flow.ts`、`src/flows/doctor-repair-flow.ts`。这组文件能串起“注册检查、运行检查、展示问题、尝试修复、再次验证”的完整 doctor 模型。

5. 渠道配置建议从 `src/flows/channel-setup.ts` 开始，再补看 `src/flows/channel-setup.status.ts` 和 `src/flows/channel-setup.prompts.ts`。主流程在前者，状态展示和交互提示被拆到后两个文件。

6. 最后读 `src/flows/provider-flow.ts`、`src/flows/provider-flow.runtime.ts`、`src/flows/model-picker.ts`、`src/flows/search-setup.ts`，它们更像配置向导中的分支功能，适合在已有整体流程图之后阅读。

## 常见误区

不要把 `src/flows` 理解成底层业务实现目录。这里大量代码是编排、适配和流程决策，真正的 plugin registry、channel setup adapter、config 读写、gateway auth、agent model catalog 等实现主要在相邻目录中。

不要认为 `src/flows` 有清晰的子目录边界。当前它是平铺目录，边界靠文件名前缀和导出函数体现：`channel-setup.*`、`doctor-*`、`health-check-*` 各自构成逻辑模块。

不要把 `doctor-health.ts` 当成全部 doctor 逻辑。它只是命令入口和高层串联；具体检查项在 `doctor-core-checks.ts`，插件或扩展贡献通过 `doctor-health-contributions.ts` 汇入，修复闭环在 `doctor-repair-flow.ts`。

不要绕过 `HealthCheck` 协议直接在流程里写散装检查逻辑。这个目录已经把 finding、severity、repair、diff、effect、dry-run、validation 等概念抽象出来，新检查通常应接入 registry / contribution 机制。

不要假设 provider、channel、search 的选项是硬编码在 flow 中。根据当前片段推断，这些选项主要来自 manifest、install catalog、active plugin registry 和当前配置状态；flow 的职责是合并、过滤、排序和驱动用户选择。

不要把测试文件当成叶子实现逐个阅读。`src/flows` 的测试很多，但 overview 阶段只需要用它们确认主题边界：channel setup、doctor core checks、doctor lint/repair、provider flow、search setup、health conversion 等是否各自有行为覆盖。
