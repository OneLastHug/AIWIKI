# 目录：extensions/qa-lab/src/providers

## 它负责什么

`extensions/qa-lab/src/providers` 是 `qa-lab` 的“模型提供方测试车道”层。它不直接定义 QA 场景本身，而是把同一套 QA suite 可以运行在哪种 provider 后端上抽象成统一的 `QaProviderDefinition`：本地 mock、AIMock、真实 frontier 模型都通过同一个注册表暴露给上层。

从当前代码看，这个目录承担几类职责：声明可接受的 `providerMode`，给每个 mode 提供默认 primary model、alternate model、image generation model，决定 gateway 的 `models.providers` 配置是替换还是合并，给模型请求补充 runtime params，例如 `transport: "sse"`、`fastMode`、`thinking`，并在 mock 车道下启动本地 provider server。真实模型车道则不启动本地服务，而是使用已有 provider plugin、环境变量别名和 live provider config。

这里的边界很清楚：上层 suite、gateway、CLI、live transport 应该通过 `providers/index.ts` 查询 provider 能力，而不是在各处写 `providerMode === "mock-openai"` 这类分支。`providers/README.md` 明确说明：如果共享 suite 代码需要 provider-specific 行为，优先扩展 registry contract，而不是把 provider 名称判断散落到 `suite`、`gateway`、manual lane 或 live transport runtime 中。

## 直接子目录地图

`extensions/qa-lab/src/providers/mock-openai` 是默认 mock 车道。`index.ts` 通过 `createMockQaProviderDefinition` 注册 `mock-openai`，`server.ts` 实现本地 mock OpenAI Responses API 风格服务，测试主要在 `server.test.ts`。它还模拟不同 provider variant，例如 OpenAI、Anthropic，以便在没有真实 API key 的情况下跑 parity 场景。

`extensions/qa-lab/src/providers/aimock` 是另一个 mock 车道。它同样复用 `shared/mock-provider-definition.ts`，但本地服务由 `aimock/server.ts` 提供，注册的 mode 是 `aimock`。根据当前片段推断，它用于把 QA suite 跑在 AIMock 兼容服务上，依据是 `aimock/index.ts` 声明 `commandName: "aimock"`，并且 `server-runtime.ts` 会按 `provider.mode` 动态启动 `startQaAimockServer`。

`extensions/qa-lab/src/providers/live-frontier` 是真实模型车道。`index.ts` 注册 `live-frontier`，默认模型是 `openai/gpt-5.5`，默认图片模型是 `openai/gpt-image-1`，并声明 `usesModelProviderPlugins: true`、`appliesLiveEnvAliases: true`。同目录下的 `auth.ts`、`catalog.ts`、`model-selection.runtime.ts`、`parity.ts`、`character-eval.ts` 分别围绕真实 provider 的鉴权、模型目录、模型选择、parity 和角色评估组织逻辑。

`extensions/qa-lab/src/providers/shared` 是 provider 定义的公共契约和 mock 构造工具。`types.ts` 定义 `QaProviderMode`、`QaProviderDefinition`、`QaMockProviderServer` 等核心类型；`mock-provider-definition.ts` 把 mock 车道的默认模型、gateway provider map、runtime params、本地命令、mock auth providers 等规则集中起来；`mock-model-config.ts` 和 `mock-auth.ts` 提供 mock provider 配置和认证占位能力；`auth-store.ts` 处理认证存储相关公共逻辑。

## 关键入口

最重要入口是 `extensions/qa-lab/src/providers/index.ts`。它导入 `mockOpenAiProviderDefinition`、`aimockProviderDefinition`、`liveFrontierProviderDefinition`，组成 `PROVIDERS` 注册表，并导出 `getQaProvider`、`normalizeQaProviderMode`、`formatQaProviderModeHelp`、`listQaStandaloneProviderCommands`。上层几乎都应该从这里进入 provider 层。

类型入口是 `extensions/qa-lab/src/providers/shared/types.ts`。这里的 `QaProviderDefinition` 是理解整个目录的核心：它规定每个 provider 必须回答“默认模型是什么”“是否使用真实 provider plugin”“是否清理 live env”“如何构造 gateway models”“如何解析 model params”“是否有 standalone server command”等问题。

mock 复用入口是 `extensions/qa-lab/src/providers/shared/mock-provider-definition.ts`。`mock-openai/index.ts` 和 `aimock/index.ts` 都很薄，只传入 mode、命令描述、server label、mock auth providers，然后由 `createMockQaProviderDefinition` 生成完整定义。

服务启动入口是 `extensions/qa-lab/src/providers/server-runtime.ts`。它接收 `providerMode`，通过 `getQaProvider` 归一化后决定是否动态 import mock server。`mock-openai` 返回 `startQaMockOpenAiServer`，`aimock` 返回 `startQaAimockServer`，`live-frontier` 返回 `null`，表示真实 provider 不需要本地 mock 服务。

另一个横切入口是 `extensions/qa-lab/src/providers/env.ts`，负责 live provider 环境变量别名、清理和归一化。它会根据 provider 定义中的 `scrubsLiveProviderEnv`、`appliesLiveEnvAliases` 决定 mock 与 live 车道的环境处理差异。

## 主流程位置

主流程从 CLI 或 suite 参数里的 `providerMode` 开始。`extensions/qa-lab/src/run-config.ts` 和 `extensions/qa-lab/src/cli.ts` 负责接收、归一化 provider mode，并用 `defaultQaModelForMode` 推导默认模型。默认普通 provider mode 是 `mock-openai`，默认 live provider mode 是 `live-frontier`。

执行 suite 时，核心位置在 `extensions/qa-lab/src/suite.ts` 的 `runQaSuite`。它先归一化 `providerMode`，确定 `primaryModel`、`alternateModel`、`fastMode`，选择场景，然后在非 isolated worker 主流程里启动 lab、创建 transport、调用 `startQaProviderServer(providerMode)`。如果返回 mock server，则把 `mock.baseUrl` 作为 `providerBaseUrl` 传给 gateway；如果是 `live-frontier`，这里得到的是 `null`，gateway 后续依赖真实 provider plugin 和 live config。

gateway 配置主流程在 `extensions/qa-lab/src/qa-gateway-config.ts` 的 `buildQaGatewayConfig`。它用 `getQaProvider(providerMode)` 取到 provider 定义，然后通过 `provider.defaultImageGenerationModel`、`provider.usesModelProviderPlugins`、`provider.resolveModelParams`、`provider.buildGatewayModels` 组装 OpenClaw gateway config。mock 车道通常 `models.mode` 是 `replace`，用本地 mock base URL 替换 provider config；live 车道通常是 `merge`，把调用方传入的真实 provider config 合入。

图片生成补丁流程在 `extensions/qa-lab/src/providers/image-generation.ts`。它同样通过 `getQaProvider` 查询当前车道的默认图片模型，并在需要时为 mock 或 live provider 构造 gateway model patch 与 enabled plugin 列表。

## 推荐阅读顺序

1. 先读 `extensions/qa-lab/src/providers/README.md`，明确 provider lane 的边界：上层只问 registry，不散落 provider 分支。
2. 再读 `extensions/qa-lab/src/providers/shared/types.ts`，把 `QaProviderDefinition` 的字段看懂，这是目录内所有实现的共同接口。
3. 接着读 `extensions/qa-lab/src/providers/index.ts`，理解三个 provider mode 如何注册，以及默认 live/mock mode 的来源。
4. 然后读 `extensions/qa-lab/src/providers/shared/mock-provider-definition.ts`，看 mock 车道如何复用一套定义生成逻辑。
5. 分别浏览 `extensions/qa-lab/src/providers/mock-openai/index.ts`、`extensions/qa-lab/src/providers/aimock/index.ts`、`extensions/qa-lab/src/providers/live-frontier/index.ts`，比较 mock 与 live 定义差异。
6. 最后回到调用方：读 `extensions/qa-lab/src/suite.ts` 的 provider 启动片段，以及 `extensions/qa-lab/src/qa-gateway-config.ts` 的 `buildQaGatewayConfig`，把 provider 定义如何影响实际 gateway 启动串起来。

## 常见误区

不要把 `providers` 理解成通用 provider plugin 实现目录。它属于 `qa-lab` 插件内部，是 QA 测试车道抽象；真实 provider plugin 的运行由 OpenClaw 插件系统和 gateway config 驱动，`live-frontier` 只是选择、配置和认证这些真实 provider。

不要在 suite、CLI、live transport 中随手增加 provider 名称判断。当前设计意图是把 provider 差异收敛到 `QaProviderDefinition`，共享代码通过 `getQaProvider` 询问能力。如果某个新行为无法表达，通常应该扩展 `shared/types.ts` 的 registry contract，并让各 provider 定义各自实现。

不要以为所有 provider mode 都会启动本地 HTTP server。`mock-openai` 和 `aimock` 会通过 `server-runtime.ts` 启动本地服务；`live-frontier` 返回 `null`，表示它走真实 provider plugin、真实环境变量和真实模型配置。

不要把 mock 的 `openai/gpt-image-1`、`gpt-5.5` 等默认模型看成真实调用保证。mock 车道里的模型 ref 更像 QA 契约和路由输入，用来让 gateway、agent runtime、工具调用、图片生成路径按同一形状跑通；真实质量和真实 provider 行为需要 `live-frontier` 车道验证。

不要忽略 `env.ts`。mock 车道会倾向于清理 live provider 环境，避免本地 mock 测试误用真实密钥；live 车道会应用 live env aliases，让 QA 运行能找到真实 provider 凭据。这是 mock/live 行为隔离的重要部分。
