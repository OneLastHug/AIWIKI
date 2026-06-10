# 目录：src/model-catalog/provider-index

## 它负责什么

`src/model-catalog/provider-index` 是 OpenClaw 模型目录体系里的“provider 预安装索引”模块。它不负责真实运行模型，也不负责读取已安装 plugin 的完整 manifest；它维护的是一份 OpenClaw 自带的、可被标准化读取的 provider 元数据，用于在 provider plugin 尚未安装或尚未加载时，仍然能让产品层知道“有哪些 provider 可以展示、安装、预览”。

这个目录的核心产物是 `OpenClawProviderIndex`：一个版本化对象，包含 `providers` 映射。每个 provider 记录包括 provider id、名称、所属 plugin、文档路径、分类、认证选项、以及可选的 `previewCatalog`。其中 `previewCatalog` 复用 `model-catalog` 的模型目录结构，但语义上是预览信息，不应被理解为已安装 plugin 的权威运行能力。源码注释也明确说：已安装 plugin manifest 仍然是 authoritative；这里的索引只是 installable-provider 和 pre-install model picker surfaces 的 fallback。

从架构角色看，这个目录连接了三类信息：provider 安装入口所需的 plugin 元数据、模型选择界面可提前展示的 preview model 信息、以及认证/引导流程可能需要的 auth choice 信息。它的职责边界比较克制：只提供索引、类型和规范化，不直接决定 provider runtime、auth 实现或模型调用细节。

## 直接子目录地图

该目录当前没有直接子目录，只有一组扁平的 TypeScript 文件：

`src/model-catalog/provider-index/index.ts` 是导出门面。

`src/model-catalog/provider-index/types.ts` 定义 provider index 的数据结构。

`src/model-catalog/provider-index/openclaw-provider-index.ts` 放置 OpenClaw 内置的 provider index 常量。

`src/model-catalog/provider-index/load.ts` 提供加载函数，把默认常量或外部传入 source 规范化为稳定索引。

`src/model-catalog/provider-index/normalize.ts` 是主要的清洗、校验、排序逻辑。

`src/model-catalog/provider-index/normalize.test.ts` 覆盖 provider index 的规范化行为和默认索引加载行为。

因此这里不是“大目录”，阅读时不需要逐文件铺开；可以把它看成一个小型数据入口模块：类型定义、内置数据、加载、规范化、测试五部分。

## 关键入口

最外层入口是 `src/model-catalog/provider-index/index.ts`。它重新导出 `loadOpenClawProviderIndex`、`normalizeOpenClawProviderIndex`，以及 `OpenClawProviderIndex`、`OpenClawProviderIndexProvider` 等类型。上层通常不直接深入 import `load.ts` 或 `normalize.ts`，而是通过这个 barrel 使用模块能力。

运行时最常用入口是 `loadOpenClawProviderIndex`，位置在 `src/model-catalog/provider-index/load.ts`。它默认读取 `OPENCLAW_PROVIDER_INDEX`，调用 `normalizeOpenClawProviderIndex`，如果输入不合法则返回 `{ version: 1, providers: {} }`。这个设计说明 provider index 是可失败降级的展示/安装辅助数据，而不是启动时必须存在的强依赖。

数据入口是 `OPENCLAW_PROVIDER_INDEX`，位置在 `src/model-catalog/provider-index/openclaw-provider-index.ts`。当前片段中包含 `moonshot` 和 `deepseek` 两个 provider。每个 provider 包括 `id`、`name`、`plugin`、`docs`、`categories` 和 `previewCatalog`。注释强调这里的 preview catalog 应保持稳定展示字段，避免和已安装 plugin manifest 的 runtime adapter metadata 发生权威性冲突。

规范化入口是 `normalizeOpenClawProviderIndex`，位置在 `src/model-catalog/provider-index/normalize.ts`。它负责版本检查、provider id 规范化、危险对象 key 过滤、plugin/install/authChoices/previewCatalog 清洗，以及最终按 provider id 排序输出。

## 主流程位置

主流程可以按“内置数据加载 -> 结构规范化 -> 上层规划/消费”理解。

第一步，`loadOpenClawProviderIndex` 从 `OPENCLAW_PROVIDER_INDEX` 或调用方传入的 unknown source 开始。这里的参数类型是 `unknown`，说明模块允许外部来源进入，但必须经过统一 normalize 后才形成可信结构。

第二步，`normalizeOpenClawProviderIndex` 检查 `version` 是否等于当前支持的 `1`，并要求 `providers` 是 record。随后逐个 provider 处理。provider key 会经过 `normalizeModelCatalogProviderId`，并通过 `isBlockedObjectKey` 避免 `__proto__` 这类原型污染风险。provider 自身如果声明了 `id`，也必须和 key 规范化后保持一致，否则会被丢弃。

第三步，provider 内部字段被分层处理。`plugin` 必须有安全的 `id`；`install` 会分别校验 `clawhubSpec` 和 `npmSpec`，只有能被 `parseClawHubPluginSpec` 或 `parseRegistryNpmSpec` 解析的安装规格才保留；`authChoices` 要求 `method`、`choiceId`、`choiceLabel` 有效；`onboardingScopes` 只接受 `text-inference`、`image-generation`、`music-generation`；`assistantVisibility` 只接受 `visible` 或 `manual-only`。

第四步，`previewCatalog` 会委托 `src/model-catalog/normalize.ts` 的 `normalizeModelCatalog` 处理，并限制 owned provider 为当前 provider id。模型如果没有显式 `status`，会被补成 `preview`。这点很关键：provider index 里的模型行不是已安装可用模型的强承诺，而是预安装/预览视图的候选信息。

第五步，上层把索引转成模型目录行。这个流程不在目标目录内，而在 `src/model-catalog/provider-index-planner.ts`。`planProviderIndexModelCatalogRows` 接收 `OpenClawProviderIndex`，可按 `providerFilter` 过滤 provider，再把每个 `previewCatalog` 转成 `NormalizedModelCatalogRow`，source 标记为 `provider-index`，并按 provider 和 model id 排序。命令侧入口可见于 `src/commands/models/list.provider-index-catalog.ts`，安装目录消费可见于 `src/plugins/provider-install-catalog.ts`。根据当前片段推断，这些调用点分别服务于模型列表预览和 provider 安装目录展示，依据是它们直接调用 `loadOpenClawProviderIndex` 或相关 planner。

## 推荐阅读顺序

建议先读 `src/model-catalog/provider-index/types.ts`，建立字段地图：provider、plugin、install、auth choice、preview catalog 分别是什么。

然后读 `src/model-catalog/provider-index/openclaw-provider-index.ts`，把类型和真实数据对上，尤其注意注释里关于“installed plugin manifests remain authoritative”的边界说明。

接着读 `src/model-catalog/provider-index/load.ts` 和 `src/model-catalog/provider-index/index.ts`，理解对外 API 很窄：加载、规范化、类型导出。

之后读 `src/model-catalog/provider-index/normalize.ts`，重点看几个分层函数：`normalizeInstall`、`normalizePlugin`、`normalizeAuthChoice`、`normalizePreviewCatalog`、`normalizeProvider`、`normalizeOpenClawProviderIndex`。不要陷入每个字段的细枝末节，重点看它如何把不可信输入收束成安全、稳定、排序后的索引。

最后再跳到邻近文件 `src/model-catalog/provider-index-planner.ts`、`src/commands/models/list.provider-index-catalog.ts`、`src/plugins/provider-install-catalog.ts`，观察索引如何被消费。测试方面可读 `src/model-catalog/provider-index/normalize.test.ts` 和 `src/model-catalog/provider-index-planner.test.ts`，它们比逐行读实现更快揭示预期行为。

## 常见误区

不要把 `OPENCLAW_PROVIDER_INDEX` 当成已安装 provider 的权威 manifest。源码注释明确区分：已安装 plugin manifest 才是 authoritative；这里是未安装或预安装场景的 fallback/preview 元数据。

不要把 `previewCatalog` 里的模型理解为一定可运行。规范化会默认补 `status: "preview"`，planner 也把 source 标为 `provider-index`，这说明它更接近展示候选，而不是 runtime capability contract。

不要绕过 `normalizeOpenClawProviderIndex` 直接信任原始对象。该模块对 provider id、blocked key、安装规格、auth choice、model catalog 字段都有过滤逻辑；直接使用原始 source 会丢掉安全和一致性保证。

不要在这里加入 provider runtime 策略。目录职责是索引和预览，不是 provider adapter、auth 实现、模型请求参数、fallback 路由或插件加载器。真实 plugin 运行相关逻辑应沿 plugin manifest、plugin SDK 和 provider runtime 边界处理。

不要误以为目录没有子目录就不重要。它虽然文件少，但位于 `model-catalog` 和 `plugins` 安装展示之间，是“plugin 未安装前仍能展示 provider 和模型预览”的关键数据层。

不要把 `docs` 字段当成真实外部网址。当前数据使用类似 `/providers/moonshot` 的站内文档路径；在学习本文档中如需提到外部地址，应按要求写成 `[URL已移除]`。
