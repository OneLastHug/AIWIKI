# 文件：packages/coding-agent/src/core/model-resolver.ts

## 一句话定位

`model-resolver.ts` 是 `packages/coding-agent` 的模型选择与模型作用域解析中心：把用户输入的 `--model`、`--provider`、`--models`、默认配置、可用模型列表，解析成内部可直接使用的 `Model<Api>`，并附带可选的 `ThinkingLevel`。

## 它暴露/定义了什么

这个文件主要定义四类内容。

第一类是默认模型表 `defaultModelPerProvider`，按 `KnownProvider` 维护每个 provider 的首选模型 ID，例如 `openai`、`anthropic`、`openai-codex`、`google`、`zai`、`moonshotai` 等。它既影响初始模型兜底，也影响自定义模型 ID 的基础模型模板选择。

第二类是结果类型：`ScopedModel` 表示一个可参与轮换或限定范围的模型及其可选 thinking level；`ParsedModelResult` 表示单个 pattern 的解析结果；`ResolveCliModelResult` 表示 CLI 单模型解析的结果；`InitialModelResult` 表示最终初始模型、thinking level 和 fallback 信息。

第三类是模型匹配 API：`findExactModelReferenceMatch`、`parseModelPattern`、`resolveModelScope`、`resolveCliModel`。这些是该文件最核心的公共能力。

第四类是初始模型选择 API：`findInitialModel`。从代码注释和实现片段看，它用于按优先级选择启动时模型，不过当前调用证据显示主入口 `packages/coding-agent/src/main.ts` 主要直接使用 `resolveCliModel` 和 `resolveModelScope`，未在可见片段中导入 `findInitialModel`。

## 谁调用它

明确调用者有两处。

`packages/coding-agent/src/main.ts` 导入 `resolveCliModel`、`resolveModelScope` 和 `ScopedModel`。它在启动阶段解析 `parsed.models` 得到 `scopedModels`，并在 CLI 指定 provider/model 时解析单个模型。

`packages/coding-agent/src/modes/interactive/interactive-mode.ts` 导入 `defaultModelPerProvider`、`findExactModelReferenceMatch`、`resolveModelScope`。交互模式里它用于模型选择器的精确搜索、判断 provider 是否有默认模型，以及处理运行中更新模型 scope 的命令或 UI 操作。

测试侧 `packages/coding-agent/test/model-resolver.test.ts` 覆盖 `parseModelPattern` 和默认模型表，说明这个文件的冒号解析、别名优先、provider/model 语法是稳定行为边界。

## 它调用谁

它依赖 `@earendil-works/pi-ai` 的 `Model`、`Api`、`KnownProvider` 和 `modelsAreEqual`，其中 `modelsAreEqual` 用于去重，避免同一模型在 scope 中重复出现。

它调用 `ModelRegistry`，主要使用 `getAvailable()`、`getAll()`、`find()`：`getAvailable()` 面向有可用认证或可运行条件的模型，`getAll()` 面向 CLI 首次配置场景，允许用户通过 `--api-key` 指定还未预配置认证的模型。

它调用 `isValidThinkingLevel` 校验 `:high`、`:medium` 等 thinking suffix，调用 `DEFAULT_THINKING_LEVEL` 提供默认 thinking 行为。它还用 `minimatch` 处理 glob scope，例如 `anthropic/*` 或 `*sonnet*`，用 `chalk` 输出黄色 warning 或红色 error。

## 核心流程

模型解析有两个入口场景。

`resolveModelScope(patterns, modelRegistry)` 面向 `--models` 或交互式 scope。它先取 `modelRegistry.getAvailable()`，只在可用模型中解析。每个 pattern 如果包含 glob 字符，就把最后一个冒号后的合法 thinking level 拆出，再用 `minimatch` 同时匹配 `provider/modelId` 和裸 `modelId`。非 glob pattern 则交给 `parseModelPattern`。解析成功后用 `modelsAreEqual` 去重；失败时只打印 warning 并跳过，因此 scope 解析是宽松的。

`resolveCliModel({ cliProvider, cliModel, modelRegistry })` 面向 `--provider` 和 `--model`。它使用 `modelRegistry.getAll()`，因为 CLI 可能同时传入新 API key。它先建立 provider 的大小写无关映射；如果 `--model` 形如 `provider/model` 且前缀是已知 provider，会优先解释成 provider 限定，而不是模型 ID 本身含 slash。若未限定 provider，会先尝试精确匹配裸 ID 或 canonical `provider/id`。之后用 `parseModelPattern` 在候选集合中解析，并在严格模式下禁止“无效 thinking suffix 回退”。如果 provider 存在但模型未找到，会通过 `buildFallbackModel` 构造一个自定义模型 ID，并返回 warning；否则返回适合 CLI 展示的 error。

初始模型选择由 `findInitialModel` 负责。优先级是 CLI 参数、非继续会话时的第一个 scoped model、保存的默认 provider/model、可用模型中的 provider 默认模型、最后是第一个可用模型。根据当前片段推断，这个函数的后半段会在没有匹配默认模型时返回首个 available model 或空结果，依据是其注释和已读到的控制流。

## 关键函数的高层作用

`findExactModelReferenceMatch` 做“无歧义精确匹配”。它支持裸模型 ID，也支持 `provider/modelId`。裸 ID 如果跨 provider 出现多个匹配，会返回 `undefined`，避免静默选错。

`parseModelPattern` 是冒号语法的核心。它先把完整 pattern 当模型匹配，解决 OpenRouter 这类模型 ID 本身含 `:` 的情况；失败后才按最后一个冒号拆 thinking level。合法 suffix 会附加到解析结果；非法 suffix 在 scope 宽松模式下会尝试回退到前缀并给 warning，在 CLI 严格模式下直接失败。

`resolveModelScope` 把一组 pattern 扩展成可轮换的 `ScopedModel[]`，支持 glob、模糊匹配、thinking suffix、warning 和去重。

`resolveCliModel` 把 CLI 单模型输入解析为唯一模型，处理 provider 推断、slash 歧义、OpenRouter 风格 ID、thinking suffix 和自定义模型 ID fallback。

`tryMatchModel`、`isAlias`、`buildFallbackModel` 是辅助函数：前者实现精确优先再模糊匹配，`isAlias` 用于偏好无日期或 `-latest` 的别名版本，后者在 provider 已知但模型 ID 不在注册表时生成可用的自定义模型对象。

## 修改风险

最高风险是改变 `parseModelPattern` 的冒号拆分顺序。这里刻意先完整匹配，再拆最后一个冒号，是为了兼容模型 ID 内含 `:` 的 provider；如果改成简单 `split(":")`，会破坏 `qwen/qwen3-coder:exacto`、`openai/gpt-4o:extended` 这类模型。

第二个风险是 provider/model slash 规则。`resolveCliModel` 需要在“`provider/model` 语法”和“模型 ID 自身带 slash”之间做优先级判断，尤其 OpenRouter、Vercel AI Gateway、Workers AI 等 provider 常见嵌套 ID。调整 provider 推断时必须覆盖这些歧义用例。

第三个风险是 `getAvailable()` 与 `getAll()` 的使用边界。scope 应该只包含当前可用模型；CLI 单模型解析则需要支持首次传 `--api-key`。混用会导致模型不可选或错误放宽。

第四个风险是默认模型表。`defaultModelPerProvider` 不只是展示数据，还参与初始模型兜底和 `buildFallbackModel` 的模板选择。新增 provider、改默认 ID 或删除旧 provider 时，需要同步测试和模型注册表，否则可能出现 provider 有模型但首选模型永远匹配不到的情况。

第五个风险是 warning/error 语义。`resolveModelScope` 是容错跳过，`resolveCliModel` 是可返回 fatal error，`findInitialModel` 里还可能 `process.exit(1)`。把这些路径合并或改变错误策略，会直接影响 CLI 启动体验和交互模式的可恢复性。
