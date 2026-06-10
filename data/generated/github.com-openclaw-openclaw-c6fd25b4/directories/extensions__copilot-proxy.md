# 目录：extensions/copilot-proxy

## 它负责什么

`extensions/copilot-proxy` 是一个 bundled provider plugin，作用是把本机运行的 Copilot Proxy 服务接入 OpenClaw 的模型提供方体系。这里的 Copilot Proxy 指 VS Code 侧提供的本地代理服务，插件本身不实现模型推理，也不直接连接 GitHub Copilot 云端；它负责在 OpenClaw 插件系统中注册一个 `copilot-proxy` provider，并在登录/配置流程里生成 OpenClaw 能识别的模型 provider 配置。

从边界上看，这个目录属于 `extensions/` 下的插件包。按照 `extensions/AGENTS.md` 的约束，插件生产代码应通过 `openclaw/plugin-sdk/*` 这类公开 SDK seam 与核心交互，不能深 import core 内部实现。`copilot-proxy` 正是这种轻量 provider 插件：清单声明元数据，入口注册 provider，运行时 API 文件只做 SDK re-export，实际配置写入发生在 provider auth 的 custom flow 中。

它的核心产物是配置补丁：把 `models.providers.copilot-proxy` 写成一个 OpenAI-compatible completions provider，默认 `baseUrl` 为本地 `/v1` 端点，`api` 为 `openai-completions`，并把用户输入的 model ids 转换成 OpenClaw 的 model definitions。同时它会写入 `agents.defaults.models`，让这些 `copilot-proxy/<modelId>` 模型引用能作为 agent 默认模型候选。

## 直接子目录地图

这个目录当前没有直接子目录，全部内容都在 `extensions/copilot-proxy` 顶层。可以把它理解为一个非常扁平的插件包：

`openclaw.plugin.json` 是插件发现和控制面的静态元数据；`package.json` 是 npm/package workspace 元数据，并通过 `openclaw.extensions` 指向插件入口；`index.ts` 是运行时入口和主逻辑；`runtime-api.ts` 是本插件使用的 SDK facade；`README.md` 是面向使用者的启用、认证和运行前提说明；`tsconfig.json` 是 TypeScript 编译配置。

因为没有 `src/`、`tests/` 或更深层模块，阅读时不需要按传统“入口、服务层、适配层、测试”去拆。它更像一个单文件 provider registration 插件，关键路径集中在 `index.ts`。

## 关键入口

第一个入口是 `extensions/copilot-proxy/openclaw.plugin.json`。它声明插件 id 为 `copilot-proxy`，`enabledByDefault` 为 `true`，provider 列表包含 `copilot-proxy`，并声明 `providerAuthChoices`。这些信息用于插件发现、设置向导和认证选项展示。这里还可以看到它的认证方式是 `local`，choice 文案指向 “Configure base URL + model ids”，说明这个插件的认证重点不是 OAuth，而是配置本地代理地址与模型列表。

第二个入口是 `extensions/copilot-proxy/package.json`。其中 `openclaw.extensions` 指向 `./index.ts`，这说明插件运行时加载会进入 `index.ts`。包名是 `@openclaw/copilot-proxy`，依赖只声明 `@openclaw/plugin-sdk`，也印证了它没有本地代理实现或外部 HTTP client 依赖。

第三个入口是 `extensions/copilot-proxy/index.ts`。这里默认导出 `definePluginEntry(...)`，插件 id、name、description 都在这里定义。真正的 provider 注册发生在 `register(api)` 内部的 `api.registerProvider(...)`。provider id 是 `copilot-proxy`，认证数组里只有一个 `kind: "custom"` 的 `local` 方法，运行函数 `run(ctx)` 会通过 `ctx.prompter.text` 询问 base URL 和 model ids，然后返回 `profiles`、`configPatch`、`defaultModel` 和提示 notes。

第四个入口是 `extensions/copilot-proxy/runtime-api.ts`。它从 `openclaw/plugin-sdk/plugin-entry` 和 `openclaw/plugin-sdk/core` re-export `definePluginEntry`、`OpenClawPluginApi`、`ProviderAuthContext`、`ProviderAuthResult`。这个文件的意义不是增加业务逻辑，而是把插件入口依赖固定在公开 SDK facade 上，避免生产代码直接穿透核心内部路径。

## 主流程位置

主流程集中在 `extensions/copilot-proxy/index.ts`，可以按“输入规范化 -> provider 注册 -> 认证配置生成”三段理解。

第一段是输入规范化。`normalizeBaseUrl(value)` 会 trim 用户输入，空值回落到 `DEFAULT_BASE_URL`，再去掉末尾 `/`，并保证最终以 `/v1` 结尾。`validateBaseUrl(value)` 基于规范化后的值调用 `URL.canParse`，给配置向导提供校验错误。`parseModelIds(input)` 把逗号和换行分隔的模型字符串转成数组，并通过 `normalizeStringEntries`、`uniqueStrings` 做清理和去重。`buildModelDefinition(modelId)` 则把每个 model id 转为 OpenClaw 模型定义，字段包括 `api: "openai-completions"`、`input: ["text", "image"]`、`contextWindow` 和 `maxTokens`。

第二段是 provider 注册。`definePluginEntry` 内的 `register(api)` 调用 `api.registerProvider`，把 `copilot-proxy` 注册到 OpenClaw 的 provider registry。这里的 `docsPath` 指向 provider/model 文档页路径，`wizard.setup` 把设置向导的 choice 绑定到 `local` 认证方式。根据当前片段推断，OpenClaw 的插件加载器会先从 `package.json` 或 `openclaw.plugin.json` 发现这个入口，再在激活时执行默认导出的 plugin entry，依据是 `package.json` 的 `openclaw.extensions` 和 `index.ts` 的默认导出形态。

第三段是认证配置生成。`auth[0].run(ctx)` 是最重要的运行时位置。它先提示用户输入 `Copilot Proxy base URL`，再提示 `Model IDs (comma-separated)`。随后它构造一个 token 类型 credential，但 token 默认是 `n/a`，并在 provider 配置里设置 `authHeader: false`。这说明它并不依赖真实 API key，而是假定本地 Copilot Proxy 处理了上游认证。最后返回的 `configPatch` 会落到 `models.providers.copilot-proxy` 和 `agents.defaults.models`，`defaultModel` 使用第一个 model id 拼成 `copilot-proxy/<modelId>`。

## 推荐阅读顺序

建议先读 `extensions/copilot-proxy/README.md`，了解这个插件的使用前提：需要先启用插件，认证时选择 `copilot-proxy`，并确保 Copilot Proxy 已在 VS Code 中运行，base URL 需要包含 `/v1`。

然后读 `extensions/copilot-proxy/openclaw.plugin.json`。这里能看到它在 OpenClaw 控制面中的身份：插件 id、provider id、认证 choice、默认启用状态和空的 `configSchema`。这一层帮助你理解“插件被发现和展示”的方式。

第三步读 `extensions/copilot-proxy/package.json`，重点看 `openclaw.extensions`。它把插件包和 `index.ts` 入口连起来，也说明依赖边界很窄，只通过 plugin SDK 工作。

第四步读 `extensions/copilot-proxy/runtime-api.ts`。这个文件很短，但能帮助你确认它遵守 `extensions/` 的边界规则：入口只从 `openclaw/plugin-sdk/*` 获得公开类型和 helper。

最后读 `extensions/copilot-proxy/index.ts`。阅读时先看顶部常量，理解默认 base URL、默认 API key、默认 context window、默认 max tokens 和默认 model ids；再看几个 normalization helper；最后看 `definePluginEntry` 和 `api.registerProvider`，这就是完整主流程。

## 常见误区

第一个误区是把 `copilot-proxy` 当成 GitHub Copilot 官方认证插件。当前代码并没有 OAuth、设备码或 GitHub token 流程；它只要求本地 Copilot Proxy 服务已经可用，然后把 OpenClaw 的 provider 指向这个本地 `/v1` endpoint。

第二个误区是以为 `DEFAULT_API_KEY = "n/a"` 是可用密钥。实际上 provider 配置里同时设置了 `authHeader: false`，所以这个 token 更像是满足 OpenClaw credential/profile 形状的占位值，而不是要发给上游服务的真实凭据。

第三个误区是忽略 `/v1`。`normalizeBaseUrl` 会自动补 `/v1`，README 也强调 base URL 必须包含 `/v1`。如果排查请求路径问题，先看最终写入 `models.providers.copilot-proxy.baseUrl` 的规范化结果，而不是只看用户输入。

第四个误区是把默认 model ids 当成服务端能力保证。`DEFAULT_MODEL_IDS` 只是初始提示和默认配置来源，`notes` 明确提示模型可用性取决于用户的 Copilot plan，必要时需要编辑 `models.providers.copilot-proxy`。

第五个误区是从核心目录寻找这个 provider 的业务逻辑。根据 `extensions/AGENTS.md` 的插件边界，provider 的 auth、onboarding、vendor 行为应留在插件内。对于这个目标目录，主逻辑就在 `extensions/copilot-proxy/index.ts`，核心侧只应通过插件 SDK 和配置结果与它交互。
