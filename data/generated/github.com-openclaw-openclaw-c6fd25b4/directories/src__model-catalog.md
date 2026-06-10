# 目录：src/model-catalog

## 它负责什么

`src/model-catalog` 是 OpenClaw 的“模型目录控制平面”基础模块。它不直接负责调用模型，也不是某个具体 provider 的运行时实现；它负责把来自插件 manifest、内置 provider index、配置或运行时刷新等来源的模型元数据整理成统一、可排序、可去重、可合并的目录行。

从当前片段看，这个目录主要解决四类问题：第一，定义模型目录的数据结构，例如 provider、model、alias、suppression、cost、input、status、discovery 等；第二，把插件 manifest 中的 `modelCatalog` 标准化成 `NormalizedModelCatalogRow`；第三，加载并规范化 OpenClaw 内置的 provider index，用于展示可安装 provider、认证选项和 preview 模型；第四，在多个来源提供同一模型时，按照来源权威度合并，避免重复或冲突污染上层列表。

它处在插件元数据、SDK、gateway 模型浏览、配置校验之间。上层看到的是“某 provider 有哪些模型、模型能力是什么、是否 preview/deprecated、来自 manifest 还是 provider-index”；下层则仍由各 provider/plugin 自己负责真实调用、认证、运行时刷新和能力实现。

## 直接子目录地图

`src/model-catalog` 本身是一个小型模块目录，没有多层复杂结构。直接子目录只有：

`src/model-catalog/provider-index`：内置 provider index 的定义、加载和规范化逻辑。这里描述 provider 条目，例如 provider id、展示名称、关联插件、安装来源、文档路径、分类、认证选择，以及 `previewCatalog`。它面向“OpenClaw 知道有哪些 provider 可以被发现或安装”的场景，不等同于已安装插件的真实运行时目录。

根目录文件承担通用模型目录能力：

`src/model-catalog/types.ts` 定义核心类型，包括 `ModelCatalog`、`ModelCatalogProvider`、`ModelCatalogModel`、`NormalizedModelCatalogRow`、`UnifiedModelCatalogEntry` 等。

`src/model-catalog/normalize.ts` 负责把松散输入清洗成规范结构。它会处理 provider id、model id、输入类型、状态、API 类型、成本、上下文窗口、compat、media input、headers、alias、suppression 等字段。

`src/model-catalog/manifest-planner.ts` 负责从插件 registry 的 manifest 中规划模型目录行，同时处理 provider filter、alias 映射、冲突检测和 suppression 规划。

`src/model-catalog/provider-index-planner.ts` 负责从 provider index 的 `previewCatalog` 规划模型目录行，默认把预览目录中的模型标记为 `preview`。

`src/model-catalog/authority.ts` 负责多来源合并时的权威度排序。

`src/model-catalog/refs.ts` 负责统一构造 provider/model 引用和 merge key。

`src/model-catalog/index.ts` 是对外 barrel，集中导出上述能力和类型。

## 关键入口

最核心的公共入口是 `src/model-catalog/index.ts`。外部模块通常不需要直接知道内部文件分布，而是从这里使用：

`normalizeModelCatalog`、`normalizeModelCatalogRows`：用于把原始 catalog 输入转成规范形态或行列表。

`planManifestModelCatalogRows`：从插件 registry 的 manifest 中生成模型目录计划。它会遍历 `registry.plugins`，读取每个插件的 `modelCatalog.providers`，根据 owned provider 和 alias 关系生成目录行，并记录冲突。

`planManifestModelCatalogSuppressions`：从插件 manifest 中提取 suppression 规则。它会校验 suppression 指向的是插件拥有的 provider 或合法 alias，避免任意插件压制不属于自己的 provider/model。

`loadOpenClawProviderIndex`：加载内置 provider index，内部使用 `OPENCLAW_PROVIDER_INDEX` 并通过 `normalizeOpenClawProviderIndex` 清洗。如果输入无效，会回退到空的 `{ version: 1, providers: {} }`。

`planProviderIndexModelCatalogRows`：把 provider index 的 `previewCatalog` 转成统一模型目录行，供模型浏览或安装前预览使用。

`mergeModelCatalogRowsByAuthority`：把多来源目录按 `mergeKey` 去重，并按来源权威度选择保留项。

## 主流程位置

一个典型流程可以按“来源进入、规范化、规划、合并、上层展示”理解。

manifest 来源从插件 registry 进入 `planManifestModelCatalogRows`。该函数读取每个插件的 `modelCatalog.providers`，先规范化 provider id，再结合 `modelCatalog.aliases` 判断某个 alias 是否指向插件拥有的 provider。随后它调用 `normalizeModelCatalogProviderRows` 生成 `NormalizedModelCatalogRow`。如果不同插件声明了同一个 `mergeKey`，planner 不会盲目覆盖，而是记录 `conflicts` 并从最终 `rows` 中排除冲突项。

provider index 来源从 `loadOpenClawProviderIndex` 进入。`provider-index/normalize.ts` 会清洗 provider id、plugin install spec、auth choices、categories、docs、previewCatalog 等字段。`previewCatalog` 复用根目录的 `normalizeModelCatalog`，说明 provider index 的模型描述与插件 manifest 的模型描述共享同一套 catalog shape。之后 `planProviderIndexModelCatalogRows` 把这些 preview 模型转换为 `source: "provider-index"` 的行。

合并逻辑在 `authority.ts`。当前来源权威度从高到低大致是：`config`、`manifest`、`cache`/`runtime-refresh`、`provider-index`。代码中数值越小越优先，因此同一 `mergeKey` 下，用户配置或已安装 manifest 会压过 provider index 的 preview 信息。这个设计可以避免“安装前预览目录”覆盖真实安装后的目录。

上层使用位置根据当前搜索片段可见，模型目录与 `src/agents/model-catalog.js`、`src/gateway/server-model-catalog.ts`、`src/gateway/server-methods/models.ts`、`src/gateway/server-methods/sessions.ts`、`src/plugin-sdk/provider-entry.ts`、`src/plugin-sdk/provider-catalog-shared.ts` 等相邻模块有关。根据当前片段推断，`src/model-catalog` 更像底层纯数据/规划模块，而 agent、gateway、SDK 层负责把目录暴露给 UI、会话、插件 runtime 或模型选择流程。

## 推荐阅读顺序

建议先读 `src/model-catalog/types.ts`。这里能建立完整词汇表：`ModelCatalog` 是原始声明形态，`NormalizedModelCatalogRow` 是内部规划后的行形态，`UnifiedModelCatalogEntry` 则更接近 SDK/运行时统一目录条目。

然后读 `src/model-catalog/refs.ts` 和 `src/model-catalog/authority.ts`。这两个文件短，但能解释为什么 provider id 要统一小写、为什么要有 `ref` 和 `mergeKey`，以及多来源目录冲突时谁覆盖谁。

第三步读 `src/model-catalog/normalize.ts`。不用逐函数背诵，重点看它如何把 provider/model 的松散字段变成可依赖的数据：默认 input 是 `text`，默认 status 是 `available`，只接受受支持的 API、input、discovery、status，并过滤 prototype pollution 风险 key。

第四步读 `src/model-catalog/manifest-planner.ts`。这是理解插件 manifest 模型目录的主入口，重点看 owned provider、alias、provider filter、conflicts、suppressions 几段。

第五步读 `src/model-catalog/provider-index`。先看 `types.ts`，再看 `normalize.ts` 和 `openclaw-provider-index.ts`，最后看 `provider-index-planner.ts`。这样能区分“内置 provider 发现信息”和“已安装插件 manifest 信息”。

最后再看邻近调用点，例如 `src/plugin-sdk/provider-catalog-shared.ts`、`src/gateway/server-model-catalog.ts`、`src/gateway/server-methods/models.ts`。这些文件能帮助理解目录数据如何进入 SDK 约束、gateway 缓存和模型浏览接口。

## 常见误区

不要把 `src/model-catalog` 理解成模型调用层。它不负责发送请求、选择 API endpoint、处理 provider auth，也不实现具体模型能力；这些属于 provider/plugin runtime、agent runtime 或 gateway 其他模块。

不要把 `provider-index` 当成真实安装状态。`provider-index/openclaw-provider-index.ts` 更像 OpenClaw 内置的 provider 发现清单，里面的 `previewCatalog` 默认是 preview 语义，用来在插件加载前提供有限展示信息。安装后的 manifest、配置、缓存或运行时刷新可能提供更权威的数据。

不要忽略 alias 的所有权约束。`manifest-planner.ts` 只接受 alias 指向插件 own 的 provider；这避免插件通过 alias 影响不属于自己的 provider 目录。

不要用 `ref` 代替 `mergeKey` 理解去重。`ref` 形如 `provider/modelId`，保留原模型 id；`mergeKey` 使用规范化 provider 和小写 model id，更适合合并判断。

不要以为所有来源平级。`mergeModelCatalogRowsByAuthority` 明确规定了来源优先级，`provider-index` 的权威度最低，主要是预览和发现；`config` 最高，体现用户或本地配置对目录的覆盖能力。

不要把 `UnifiedModelCatalogEntry` 和 `NormalizedModelCatalogRow` 混为一谈。前者面向更统一的 SDK/运行时目录表达，包含 `kind`、`configured`、`capabilities`、`modes`、`fetchedAt` 等字段；后者是本目录规划 manifest/provider-index 行时的内部规范行。
