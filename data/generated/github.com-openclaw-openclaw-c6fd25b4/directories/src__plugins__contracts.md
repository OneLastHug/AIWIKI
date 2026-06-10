# 子系统：src/plugins/contracts

## 解决什么问题

`src/plugins/contracts` 是 OpenClaw 插件系统的“契约验证层”。它不负责真实业务请求执行，而是用一组 Vitest 契约测试和测试注册表，持续证明插件边界、SDK 暴露面、manifest 声明、provider 注册、host hook 行为、运行时导入成本等关键约束没有被破坏。

这个目录的核心价值是把插件体系里容易漂移的规则固化成测试：哪些能力必须从 manifest 可发现，哪些能力可以加载 runtime，哪些 API 是插件作者可见的公开面，哪些内部 runtime 不能泄露到 `openclaw/plugin-sdk`，以及 bundled plugins、external plugins、provider families、web search/fetch、speech/TTS、session hooks 等是否仍按约定注册。换句话说，它是 `src/plugins` 架构规则的自动化护栏。

## 相关目录和文件

`src/plugins/contracts/registry.ts` 是契约测试的中心注册表，负责按能力聚合 bundled plugin 的 provider、web search、web fetch、speech、realtime、image/video/music generation 等契约条目。它优先使用 public artifacts，必要时再通过 `loadBundledCapabilityRuntimeRegistry` 走较重的 runtime 注册路径。

`src/plugins/contracts/inventory/bundled-capability-metadata.ts` 负责构建测试用的 bundled plugin 能力快照。文件注释明确说明这些快照只用于 build/test inventory，runtime 代码应优先查询 manifest 或 runtime registry。

`src/plugins/contracts/shared.ts` 提供很小的共享工具，例如 `uniqueStrings`，用于规范化契约测试里的 ID 列表。

大量 `*.contract.test.ts` 和 `*.test.ts` 是具体契约套件：`loader.contract.test.ts` 验证 bundled provider 兼容注册和 allowlist 逻辑；`providers.contract.test.ts` 调用 SDK 测试辅助验证 provider、web search provider；`plugin-registration.*.contract.test.ts` 针对各 bundled provider 插件跑注册契约；`plugin-sdk-index.test.ts` 验证 SDK root export 边界；`host-hooks.contract.test.ts` 验证插件 host hook、命令、session extension、trusted tool policy 等 SDK seam。

相邻上游主要在 `src/plugins/manifest-registry.ts`、`src/plugins/plugin-registry.ts`、`src/plugins/bundled-capability-runtime.ts`、`src/plugins/provider-contract-public-artifacts.ts`、`src/plugins/web-provider-public-artifacts.explicit.ts`。测试辅助和公开契约来自 `src/plugin-sdk/test-helpers/*` 以及 `openclaw/plugin-sdk/plugin-test-contracts` 导出的测试接口。

## 核心对象

`BundledPluginContractSnapshot` 是能力快照对象，记录一个 bundled plugin 声明的 `pluginId`、`cliBackendIds`、`providerIds`、各类 `contracts` 能力 ID、`providerAuthEnvVars` 和 `toolNames`。它把 plugin manifest 中分散的声明压成测试可比较的稳定形状。

`providerContractRegistry`、`webSearchProviderContractRegistry`、`webFetchProviderContractRegistry`、`speechProviderContractRegistry` 等是面向测试的能力注册表视图。它们由 `createLazyArrayView` 包装成惰性数组，只有测试真正读取时才加载对应能力，避免契约测试初始化阶段就把所有 bundled runtime 都导入。

`pluginRegistrationContractRegistry` 代表 bundled plugin 的注册契约快照，用于验证各插件 manifest 声明与注册实现是否一致。

`requireProviderContractProvider`、`resolveProviderContractPluginIdsForProvider`、`resolveProviderContractPluginIdsForProviderAlias` 是 provider 契约测试的查询入口。它们把 provider ID、alias、hook alias 映射回 owning plugin，用于证明别名和归属关系没有断。

`loadScopedCapabilityRuntimeRegistryEntries` 是一个关键加载 helper。它按单个 `pluginId` 加载 scoped runtime registry，并在插件状态或声明能力异常时带诊断重试一次。根据当前片段推断，这主要用于让契约失败信息更接近真实原因，而不是只报“没有 entries”。

## 运行流程

契约测试通常先从 manifest 或快照确定“应该有哪些插件/能力”。在 Vitest 环境下，`resolveBundledManifestContracts` 会优先使用 `BUNDLED_PLUGIN_CONTRACT_SNAPSHOTS`，减少对真实 runtime 的依赖；非 Vitest 情况下则通过 `loadPluginManifestRegistry({})` 从 manifest registry 解析 bundled 插件。

随后测试注册表按能力选择加载路径。provider 和 web search 会优先读取 public artifacts，例如 `resolveBundledExplicitProviderContractsFromPublicArtifacts` 或 `resolveBundledExplicitWebSearchProvidersFromPublicArtifacts`；未被 public artifacts 覆盖的插件才进入 `loadBundledCapabilityRuntimeRegistry`。speech、realtime、media、generation 等能力在 Vitest 下可走 `speech-vitest-registry.ts` 的轻量测试注册表，否则按 manifest 声明的插件 ID 加载 bundled capability runtime registry。

具体测试再消费这些注册表。例如 plugin registration 测试调用 `describePluginRegistrationContract`，provider 测试调用 `describeProviderContracts` 和 `describeWebSearchProviderContracts`，host hook 测试构造 fixture registry 并用 `registerTestPlugin` 注册模拟插件，最后断言 registry 中 commands、sessionExtensions、toolMetadata、typedHooks、diagnostics 等行为是否符合 SDK 契约。

## 上下游依赖

上游输入主要是 bundled plugin 的 `package.json`、插件 manifest、public artifacts、plugin SDK 测试 helper，以及 `src/plugins` 内的 discovery、manifest registry、runtime registry、provider registry 等实现。`bundled-capability-metadata.ts` 会读取 bundled plugin 目录，提取 manifest 里的 `providers`、`contracts`、`legacyPluginIds`、`autoEnableWhenConfiguredProviders` 等字段。

下游消费者是测试套件本身和 CI。它们通过契约失败提醒维护者：某个插件声明了能力但没有正确注册，某个 public SDK export 意外变宽，某个 bundled/external 插件边界被绕过，或某个 provider family 的注册逻辑与 manifest 不再一致。

它也间接约束 `extensions/` 下的 bundled plugins 和 `src/plugin-sdk/*`。例如 `plugin-sdk-index.test.ts` 证明 root SDK surface 只暴露少量稳定 API，不能把 channel runtime、dispatch、monitor、media IO 等内部实现泄露给插件作者。`host-hooks.contract.test.ts` 则证明外部插件不能注册 trusted policy 或 reserved command ownership，除非符合官方插件例外规则。

## 修改时最容易踩的坑

第一，容易把契约测试注册表误当成生产 registry。`BUNDLED_PLUGIN_CONTRACT_SNAPSHOTS` 明确是 build/test inventory；runtime 应该走 manifest/runtime registry，而不是依赖测试快照。

第二，容易破坏“manifest-first”和“lazy loading”。如果新增契约时直接导入 bundled plugin runtime barrel，可能让 discovery、inventory、setup-state 这类冷路径提前加载重 runtime，违反 `src/plugins/AGENTS.md` 对控制面和运行面的分离要求。

第三，public SDK surface 不能随手扩张。`plugin-sdk-index.test.ts` 对 root runtime export 有白名单，新增导出如果只是为了内部方便，会把内部 channel、gateway、config 或 runtime helper 暴露成外部兼容承诺。

第四，provider 能力必须同时考虑 manifest 声明、public artifact、runtime 注册和兼容 allowlist。只改其中一处，`loader.contract.test.ts`、provider family 契约或 plugin registration 契约都可能失败。

第五，新增 plugin capability 时不要只加测试。还要检查 manifest contract key、`BundledPluginContractSnapshot` 字段、`registry.ts` 的 resolver、相关 SDK test helper 和 docs 是否需要同步。

## 推荐阅读顺序

1. 先读 `src/plugins/AGENTS.md`，理解插件 discovery、manifest、loading、registry、contract enforcement 的边界规则。
2. 再读 `src/plugins/contracts/registry.ts`，掌握契约测试如何从 manifest/public artifacts/runtime registry 聚合能力。
3. 接着读 `src/plugins/contracts/inventory/bundled-capability-metadata.ts`，理解 bundled plugin 能力快照的来源和用途。
4. 然后读 `src/plugins/contracts/loader.contract.test.ts`、`src/plugins/contracts/providers.contract.test.ts`，看 provider 和 web search 契约如何落地。
5. 再读一个具体插件注册测试，例如 `src/plugins/contracts/plugin-registration.openai.contract.test.ts`，理解 SDK 暴露的通用契约入口。
6. 最后读 `src/plugins/contracts/plugin-sdk-index.test.ts`、`src/plugins/contracts/host-hooks.contract.test.ts`，把公开 SDK surface 与 host hook 权限边界串起来。
