# 子系统：src/channels/plugins/contracts

## 解决什么问题

`src/channels/plugins/contracts` 是 OpenClaw 通道插件体系的“契约测试层”。它不负责生产运行时的消息收发，而是用一组可复用的 Vitest contract suites，约束核心通道注册表、插件目录、会话绑定、配置写入、出站 payload、群组策略、导入边界等行为，避免不同通道插件或核心加载逻辑各自漂移。

这个目录的核心价值是把“通道插件必须长什么样、核心应该如何发现和读取它、哪些行为不能越界”固化成测试。对于 OpenClaw 这类同时支持 bundled plugins、external plugins、gateway、agent tools、setup/status/outbound/directory/threading 等多个表面的系统，单靠类型定义不足以防止运行时退化；这里的 contract 测试会验证插件注册后的实际可见行为、排序、catalog 合并、config 写入授权、目标解析和 lightweight artifact 边界。

根据当前片段推断，这个目录也承担了架构守门职责：`channel-import-guardrails.test.ts` 和 scoped `AGENTS.md` 都强调核心 contract helper 不能为了方便直接硬编码 `extensions/**` 私有路径，而应通过公共 plugin surface、SDK facade 或测试专用公共入口访问 bundled plugin 能力。

## 相关目录和文件

`src/channels/plugins/contracts/*.contract.test.ts` 是顶层测试入口，大多数文件只调用 `test-helpers/` 中的 suite。例如 `plugins-core.catalog.entries.contract.test.ts` 调用 catalog entries 契约，`session-binding.registry-backed.contract.test.ts` 调用 registry-backed session binding 契约，多个 `*-shard-a` 到 `*-shard-h` 文件用于把 registry-backed 合约拆片运行，降低单个测试文件的体量和并发压力。

`src/channels/plugins/contracts/test-helpers/` 是主要实现区，包含 `channel-plugin-catalog-contract-suites.ts`、`config-write-contract-suites.ts`、`threading-directory-contract-suites.ts`、`group-policy-contract-suites.ts`、`session-binding-registry-backed-contract.ts`、`surface-contract-suite.ts`、`surface-contract-registry.ts`、`registry-backed-contract-shards.ts` 等。它们组合出不同类型的契约用例，并提供测试插件、manifest、runtime artifacts 等 fixtures。

`src/channels/plugins/contracts/test-helpers.ts` 是较通用的 channel contract 断言集合，覆盖 inbound context、outbound send mock、turn dispatch result 等行为。它依赖 `src/channels/chat-type.ts`、`src/channels/conversation-label.ts`、`src/channels/sender-identity.ts`、`src/channels/turn/dispatch-result.ts`，说明这些 contract 不只关心插件注册，也关心消息上下文和自动回复分发结果的形状。

上游生产代码主要在 `src/channels/plugins/`、`src/plugins/`、`src/plugin-sdk/`。例如 `src/channels/plugins/catalog.ts` 提供 `listChannelPluginCatalogEntries`，`src/channels/plugins/index.ts` 暴露 `listChannelPlugins` 等核心读取入口，`src/plugins/runtime.ts`、`src/plugins/runtime-channel-state.ts` 管理 active plugin registry，`src/plugin-sdk/core.ts` 中的 `defineChannelPluginEntry`、`createChatChannelPlugin`、`createChannelPluginBase` 是插件作者或 bundled plugin 注册通道能力的公开路径。

## 核心对象

`ChannelPlugin` 是最重要的领域对象，定义一个通道插件对核心暴露的能力集合。`surface-contract-suite.ts` 对它的多个 surface 做最低契约检查：`actions` 需要 `describeMessageTool`，`setup` 需要 `applyAccountConfig`，`status` 需要 `buildAccountSnapshot`，`outbound` 需要明确 `deliveryMode` 并至少提供一种发送函数，`messaging` 需要目标解析或展示相关能力，`threading` 需要回复线程、tool context 或 focused binding 相关能力，`directory` 需要 self、peer、group、member 等目录能力之一，`gateway` 需要账号启动、停止、登录或登出能力之一。

`surface-contract-registry.ts` 和 `registry-backed-contract-shards.ts` 维护“哪些 bundled channel plugin 应该参加哪些 contract”的注册表和分片规则。根据当前片段可见，threading、directory 等 contract 会按 channel id 选择覆盖范围，不是所有插件都被要求实现所有 surface。

catalog contract 的核心对象是 channel plugin catalog entry。测试会构造外部 catalog 文件、临时 state dir 下发现的 plugin package，以及 rich manifest entry，验证 `listChannelPluginCatalogEntries` 是否保留 channel id、plugin id、install metadata、label、docsPath、排序和 override 优先级。

config write contract 的核心对象是配置写入授权与目标解析。它关注插件在 setup 或 runtime 中是否只能写入允许的 channel/plugin 配置目标，防止核心或插件绕过边界写错配置区域。

## 运行流程

运行时视角可以理解为四步。

第一步，插件通过 SDK 或核心测试 fixture 注册 `ChannelPlugin`。在真实插件中，常见路径是 `defineChannelPluginEntry` 包装 plugin entry，然后调用 `api.registerChannel`；在测试中，helper 会建立最小内存插件或加载 bundled plugin 的公共测试 surface。

第二步，核心注册表接管插件。`src/plugins/runtime.ts` 可切换 active plugin registry，`src/channels/plugins/index.ts` 等读取入口再按 id、order、capability 或当前 runtime state 列出通道插件。`plugins-core.registry.contract.test.ts` 验证这类排序、替换和读取行为。

第三步，contract suite 对不同 surface 做行为验证。surface-only contract 检查插件暴露的能力形状；registry-backed contract 会通过真实注册表路径拿到插件再验证 threading、directory、session binding 等行为；catalog contract 会模拟外部 catalog 和已发现插件的合并；outbound-payload contract 验证发送 payload 的规范化和结果形状。

第四步，guardrails 测试检查边界。`channel-import-guardrails.test.ts` 与 `test-helpers/AGENTS.md` 的规则一致：contract helper 需要 bundled plugin 公共能力时，应通过 `src/test-utils/bundled-plugin-public-surface.ts` 之类的公共测试路径，而不是直接读 `extensions/<id>/src/**` 私有实现。

## 上下游依赖

上游是通道插件定义和注册来源，包括 bundled plugins、external plugins、plugin manifest、SDK entrypoint，以及测试里的 in-memory fixtures。关键生产边界是 `src/plugin-sdk/core.ts`、`src/plugin-sdk/channel-contract.ts`、`src/channels/plugins/types.plugin.ts`、`src/channels/plugins/types.core.ts`、`src/channels/plugins/types.adapters.ts`。

中游是核心 plugin runtime 和 channel registry，包括 `src/plugins/runtime.ts`、`src/plugins/runtime-channel-state.ts`、`src/channels/plugins/registry-loaded-read.ts`、`src/channels/plugins/catalog.ts`、`src/channels/plugins/configured-binding-consumers.ts` 等。contract 测试通过这些入口证明“注册后的真实读取行为”，而不是只检查某个对象字面量。

下游是会依赖 channel plugin surface 的功能：agent 消息工具、auto-reply dispatch、gateway account lifecycle、directory lookup、thread binding、outbound delivery、setup/status UI、配置写入和 doctor/compat 流程。这个目录通过测试把这些下游对通道插件的最低期待固化下来。

## 修改时最容易踩的坑

最常见的坑是把 contract helper 写成“知道某个 bundled plugin 私有目录结构”的测试。`src/channels/plugins/contracts/test-helpers/AGENTS.md` 明确禁止硬编码 repo-relative `extensions/**` 私有导入；如果确实需要 bundled plugin 的测试能力，应走公共 surface loader 或提升一个窄的公共 artifact。

第二个坑是只改一个通道 surface，却忘了 registry-backed 契约覆盖的是整条读取链。比如新增 `threading`、`directory` 或 `messaging` 能力时，类型通过并不代表 contract 通过；测试还可能要求注册表、catalog、runtime artifact、session binding hint、target resolver 一起保持一致。

第三个坑是配置写入边界。通道插件的 setup 或 doctor 逻辑如果新增 config/default surface，既要考虑 schema/help/docs，也要通过 authorize/resolve config write contract 证明写入目标是明确且受控的。

第四个坑是测试生命周期污染。`src/channels/AGENTS.md` 提醒，如果 helper 反复调用插件注册表，registry install/reset 应与 runtime reset 在同一生命周期；否则后续测试可能意外落回 bundled/default runtime loading，造成顺序相关问题。

第五个坑是热路径导入。通道入口和 lightweight artifact 不能随手静态导入重 runtime 模块，否则会破坏启动成本和 lazy boundary；contract 里如果为了测试方便拉入大 barrel，也会掩盖生产边界问题。

## 推荐阅读顺序

1. 先读 `src/channels/AGENTS.md` 和 `src/channels/plugins/contracts/test-helpers/AGENTS.md`，理解通道边界、公共 surface 和 bundled plugin 导入规则。
2. 再读 `src/channels/plugins/types.plugin.ts`、`src/channels/plugins/types.core.ts`、`src/plugin-sdk/core.ts` 中 `ChannelPlugin`、`defineChannelPluginEntry`、`createChatChannelPlugin` 相关定义。
3. 读 `src/channels/plugins/contracts/test-helpers/surface-contract-suite.ts`，快速掌握 contract 对各个 channel surface 的最低要求。
4. 读 `src/channels/plugins/contracts/test-helpers/surface-contract-registry.ts` 和 `registry-backed-contract-shards.ts`，理解哪些插件参加哪些 registry-backed 契约，以及为什么分片。
5. 按关注点选择 suite：catalog 看 `channel-plugin-catalog-contract-suites.ts`，配置写入看 `config-write-contract-suites.ts`，threading/directory 看 `threading-directory-contract-suites.ts`，群组策略看 `group-policy-contract-suites.ts`，会话绑定看 `session-binding-registry-backed-contract.ts`。
6. 最后回到顶层 `*.contract.test.ts` 文件，理解这些 suite 如何被拆成 CI 可运行的测试入口。
