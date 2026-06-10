# 子系统：src/commands/models

## 解决什么问题

`src/commands/models` 是 OpenClaw CLI 中“模型管理”相关命令的实现层，负责把用户在命令行里表达的模型意图，转换成稳定的配置、认证状态和可展示的模型清单。它不是模型推理运行时本身，而是围绕 `openclaw models ...` 这一组命令提供管理能力：设置默认文本模型、设置默认图像模型、维护 fallback 列表、列出可用模型、查看模型认证概况、登录或粘贴模型供应商凭据。

这个目录的核心职责可以概括为三类。第一类是配置写入，例如 `models set`、`models fallbacks add/remove/clear`、`models image-fallbacks` 会修改 `agents.defaults.model`、`agents.defaults.imageModel` 和 `agents.defaults.models`。第二类是模型发现和展示，例如 `models list` 会合并已配置模型、插件 manifest、provider catalog、PI 模型注册表和认证可用性，输出表格、JSON 或 plain 文本。第三类是认证管理，例如 `models auth login`、`models auth list` 等命令会对接 provider 插件声明的认证方法，并写入 agent 级 auth profile。

## 相关目录和文件

`src/commands/models/shared.ts` 是该目录的基础层，集中放置配置加载、配置替换、模型引用解析、别名处理、格式化工具和默认模型写入逻辑。它依赖 `src/agents/model-selection.js`、`src/config/config.js`、`src/config/model-input.js` 等模块，保证 CLI 输入最后落到规范化的 `provider/model` key 上。

`src/commands/models/set.ts` 处理默认文本模型设置，`src/commands/models/set-image.ts` 处理默认图像模型设置。二者都围绕 `applyDefaultModelPrimaryUpdate` 工作，并在必要时触发 Codex runtime plugin 安装修复。

`src/commands/models/fallbacks.ts`、`src/commands/models/image-fallbacks.ts` 和 `src/commands/models/fallbacks-shared.ts` 维护文本模型和图像模型的 fallback 列表。共享实现负责 list、add、remove、clear，并复用统一的模型引用解析和 canonical key 写入。

`src/commands/models/list.list-command.ts` 是 `models list` 的主入口。它协调配置读取、auth profile 读取、manifest metadata snapshot、模型注册表加载、source plan 决策、row 构建和最终打印。周边的 `list.rows.ts`、`list.model-row.ts`、`list.table.ts`、`list.source-plan.ts`、`list.registry.ts`、`list.registry-load.ts`、`list.configured.ts`、`list.auth-index.ts` 等文件构成列表子流水线。

`src/commands/models/auth.ts` 是交互式认证入口，使用 `@clack/prompts` 收集 token、API key 或 OAuth 选择，并调用 provider 插件的认证 helper。`src/commands/models/auth-list.ts` 则读取 agent 的 auth profile store，按 provider、agent 过滤并输出认证摘要。

## 核心对象

`OpenClawConfig` 是所有命令共同处理的配置对象。该目录通常不会直接只改运行时配置，而是通过 `readConfigFileSnapshot` 同时拿到 source config 和 runtime config，再用 `replaceConfigFile` 带 hash 写回，避免覆盖并发修改。

模型引用的核心形态是 `{ provider, model }` 和 `modelKey(provider, model)` 生成的字符串 key，例如 `openai/gpt-5.5`。`resolveModelTarget` 会结合默认 provider、别名索引和输入解析，把用户输入统一成这个形态。`upsertCanonicalModelConfigEntry` 负责把 legacy key 合并到 canonical key，避免配置里出现重复或旧格式残留。

`PrimaryFallbackConfig` 表示 `agents.defaults.model` 或 `agents.defaults.imageModel` 的结构，包含 `primary` 和 `fallbacks`。`mergePrimaryFallbackConfig` 会规范化 primary/fallbacks 中的模型引用，确保写入配置时格式稳定。

列表侧的核心对象是 `ConfiguredEntry`、`ModelRow`、`ModelListSourcePlan` 和 `ModelListAuthIndex`。`ConfiguredEntry` 表示用户配置过的模型及 tag、alias；`ModelRow` 是最终展示行；`ModelListSourcePlan` 决定 `models list --all` 或 `--provider` 该优先走 registry、manifest、provider index 还是 provider runtime；`ModelListAuthIndex` 把 auth profile、环境变量、models.json、synthetic auth 等信号汇总成可用性判断。

认证侧的核心对象是 `ProviderPlugin`、`ProviderAuthMethod`、`ProviderAuthResult` 和 `AuthProfileCredential`。`auth.ts` 不硬编码每个供应商的登录流程，而是通过插件声明的 auth 方法、setup registry 和 OAuth helper 来决定如何收集并保存凭据。

## 运行流程

设置默认模型时，命令入口调用 `modelsSetCommand` 或图像模型对应命令，随后进入 `updateConfig`。`updateConfig` 读取并校验配置快照，把 source config 交给 mutator，把 runtime config 作为解析上下文。`applyDefaultModelPrimaryUpdate` 解析用户输入，补齐或迁移 `agents.defaults.models` 中的 canonical 条目，然后把 `agents.defaults.model.primary` 或 `agents.defaults.imageModel.primary` 指向该 key。写回后命令打印配置更新信息。

维护 fallback 时，`fallbacks-shared.ts` 先读取当前 `agents.defaults.model` 或 `imageModel` 的 fallback 列表。新增时会解析目标模型、确保 `agents.defaults.models` 中存在对应 canonical 条目，再追加去重后的 key；删除时会用别名索引解析已有项，按 canonical key 过滤；清空时直接把 fallback 列表写成空数组。

列出模型时，`modelsListCommand` 先处理 `--json`、`--plain`、`--provider`、`--local`、`--all` 等参数，再加载配置、默认 agent 目录、auth profile store、workspace dir 和 manifest metadata。接着 `list.source-plan.ts` 根据是否有 provider filter、是否 `--all`、manifest 是否存在静态 catalog、provider index 是否有条目来决定数据源计划。之后系统加载模型 registry 或配置模型，调用 `appendConfiguredModelRowSources` 或 `appendAllModelRowSources` 生成 `ModelRow`。最后 `printModelTable` 负责按用户请求输出表格、JSON 或纯文本。

认证登录时，`auth.ts` 先解析目标 provider 和 agent，再合并 runtime provider 与 setup provider。命令会根据 provider 插件声明的认证方法选择 OAuth、token、API key 或外部 CLI 发现路径。拿到凭据后，通过 auth profile store 写入 agent 目录，并可选择更新默认模型或 provider auth 配置。`models auth list` 则是只读路径，读取 profile、usage stats 和外部 CLI 发现结果，输出 profile 标签、类型、过期时间、冷却或禁用状态。

## 上下游依赖

上游输入主要来自 CLI 参数、OpenClaw 配置文件、agent auth profile、插件 manifest、provider setup registry、PI 模型发现结果和环境变量。该目录大量依赖 `src/agents` 下的模型选择、默认 agent、workspace、auth profile、PI discovery 和 suppression 逻辑；依赖 `src/config` 下的配置类型、配置读写、模型输入规范化和日志；依赖 `src/plugins` 下的 provider runtime、manifest metadata、setup registry、provider auth helper 和 OAuth flow。

下游消费方包括实际 agent runtime 和状态展示路径。`agents.defaults.model`、`agents.defaults.imageModel`、`agents.defaults.models` 最终会被 `src/agents/pi-embedded-runner/model.ts` 等运行时解析，用来构建 provider 请求、能力信息、context window、参数覆盖和 fallback 尝试顺序。`models list` 的输出也会被用户、脚本或测试用来判断当前模型配置和认证是否可用。

## 修改时最容易踩的坑

最容易出问题的是模型 key 规范化。用户输入可能是裸 model、`provider/model`、带层级的 OpenRouter native id、alias 或 legacy key。修改时应优先复用 `resolveModelTarget`、`resolveModelKeysFromEntries`、`upsertCanonicalModelConfigEntry`、`normalizeAgentModelRefForConfig`，不要手写字符串拼接规则。

第二个风险是 source config 和 runtime config 的区别。`updateConfig` 的 mutator 写的是 source config，但解析时有时需要 runtime config，因为 runtime config 可能已经经过兼容迁移或默认值补全。`applyDefaultModelPrimaryUpdate` 中对 alias authored target 的特殊处理就是为了避免把运行时解析结果错误写回用户配置。

第三个风险是 `models list` 的数据源顺序。根据当前片段推断，它刻意避免一上来加载所有 runtime/provider 模块，而是通过 lazy import 和 source plan 控制冷启动成本。随意增加静态 import、全量 registry 加载或 availability 查询，可能影响 CLI 启动速度，也可能破坏插件控制面冷导入测试。

第四个风险是认证可用性判断不能等同于“模型存在”。`availableKeys` 可能来自 registry `getAvailable()`，也可能因为 provider 不支持模型级可用性而退回 provider-level auth heuristic。改 `list.rows.ts`、`list.auth-index.ts` 或 `list.errors.ts` 时，需要保留这类降级语义，否则某些 provider 会被错误标成 unavailable。

第五个风险是核心与插件边界。该目录可以通过 provider plugin、manifest、SDK helper 获取能力和认证流程，但不应把某个插件的内部路径或供应商私有策略硬编码进核心命令。供应商特定行为应优先放在插件 manifest、provider runtime 或 setup/auth helper 中。

## 推荐阅读顺序

1. 先读 `src/commands/models/shared.ts`，理解配置读写、模型引用解析、canonical key 和默认模型结构。
2. 再读 `src/commands/models/set.ts`、`src/commands/models/set-image.ts`、`src/commands/models/fallbacks-shared.ts`，掌握写配置命令的共同模式。
3. 接着读 `src/commands/models/list.types.ts`、`src/commands/models/list.list-command.ts`、`src/commands/models/list.source-plan.ts`，建立 `models list` 的整体流水线。
4. 然后读 `src/commands/models/list.rows.ts`、`src/commands/models/list.model-row.ts`、`src/commands/models/list.table.ts`，看模型行如何从配置、registry、catalog 和认证信息合成。
5. 最后读 `src/commands/models/auth.ts`、`src/commands/models/auth-list.ts`，理解 provider 插件认证、auth profile 存储和认证状态展示。
6. 如果要继续追下游运行时，再读 `src/agents/model-selection.js`、`src/agents/pi-model-discovery.js`、`src/agents/pi-embedded-runner/model.ts`、`src/plugins/provider-auth-choice-helpers.js`。
