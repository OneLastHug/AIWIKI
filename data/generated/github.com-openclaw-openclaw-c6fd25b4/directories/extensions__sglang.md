# 目录：extensions/sglang

## 它负责什么

`extensions/sglang` 是 OpenClaw 内置的 SGLang provider plugin。它的职责不是实现 SGLang 服务本身，而是把一个自托管、OpenAI-compatible 的 SGLang 推理服务接入 OpenClaw 的 provider 体系：提供插件元数据、注册 provider、引导用户配置 base URL/API key/model，并在配置阶段通过 OpenAI-compatible 接口发现可用模型。

从边界上看，它属于 `extensions/` 下的 bundled plugin。根据 `extensions/AGENTS.md`，这里的生产代码应当只通过 `openclaw/plugin-sdk/*` 与核心系统交互，不应深度导入 `src/**`、其他插件内部文件或 core 私有实现。因此这个目录可以理解为“一个用插件 SDK 包装 SGLang provider 能力的最小插件包”。

它面向的运行形态是本地或自托管服务，默认 base URL 是 `[URL已移除] `SGLANG_API_KEY`，默认模型占位符是 `Qwen/Qwen3-8B`。这些默认值集中在 `extensions/sglang/defaults.ts`，供入口注册和 provider 构建复用。

## 直接子目录地图

这个目录当前没有直接子目录，所有主要文件都平铺在 `extensions/sglang` 下。地图式理解如下：

`extensions/sglang/openclaw.plugin.json` 是插件静态清单，描述插件 id、是否默认启用、provider 归属、请求能力、价格外部性、认证环境变量、向导选项和配置 schema。

`extensions/sglang/package.json` 是插件包声明，包名为 `@openclaw/sglang-provider`，通过 `openclaw.extensions` 指向 `./index.ts`，说明插件运行入口在 `index.ts`。

`extensions/sglang/index.ts` 是注册入口，调用 `definePluginEntry` 定义插件，并在 `register` 中调用 `api.registerProvider` 把 `sglang` provider 注册进 OpenClaw。

`extensions/sglang/api.ts` 是对外轻量 barrel，重新导出默认值和 `buildSglangProvider`。如果 core 或测试需要使用插件静态/轻量能力，应优先从这里走，而不是深度读取内部文件。

`extensions/sglang/defaults.ts` 保存 SGLang provider 的默认 label、base URL、API key 环境变量和模型占位符。

`extensions/sglang/models.ts` 负责构造 OpenClaw provider config，并调用 SDK 中的 OpenAI-compatible 本地模型发现能力。

`extensions/sglang/index.test.ts` 和 `extensions/sglang/provider-discovery.contract.test.ts` 是行为与契约测试，前者关注 replay policy，后者关注 provider discovery contract。

`extensions/sglang/README.md` 只有简短说明：这是用于 SGLang discovery 和 setup 的 bundled provider plugin。

## 关键入口

最关键入口是 `extensions/sglang/index.ts` 的默认导出。它通过 `definePluginEntry({ id, name, description, register })` 声明插件身份。`register(api)` 内部调用 `api.registerProvider`，注册 id 为 `sglang`、label 为 `SGLang` 的 provider。

注册内容分为几块：

认证入口在 `auth` 数组中，目前只有 `custom` 方法。交互式路径调用 `promptAndConfigureOpenAICompatibleSelfHostedProviderAuth`，非交互式路径调用 `configureOpenAICompatibleSelfHostedProviderNonInteractive`。这两个函数不是本插件实现的，而是通过动态加载 `openclaw/plugin-sdk/provider-setup` 获得。根据当前片段推断，这样做是为了让 setup 相关逻辑保持在 SDK provider setup seam 中，同时避免插件在纯元数据发现阶段过早加载较重运行时代码。

模型目录入口在 `catalog.run`。它同样动态加载 `provider-setup`，然后调用 `discoverOpenAICompatibleSelfHostedProvider`，并把 `buildSglangProvider` 作为构造 provider config 的函数传入。

Provider 构造入口在 `extensions/sglang/models.ts` 的 `buildSglangProvider`。它先规范化 `baseUrl`，去掉末尾斜杠；再调用 `discoverOpenAICompatibleLocalModels` 获取模型列表；最后返回 OpenClaw config 需要的 provider 片段，形如 `{ baseUrl, api: "openai-completions", models }`。

静态入口是 `extensions/sglang/openclaw.plugin.json`。它让系统在不执行插件代码的情况下知道：插件 id 是 `sglang`，provider 是 `sglang`，默认启用，启动时不自动激活，认证环境变量是 `SGLANG_API_KEY`，provider request family 是 `sglang`，OpenAI completions 支持 `supportsStreamingUsage`。

## 主流程位置

主流程可以按“发现插件 -> 注册 provider -> 配置认证 -> 发现模型 -> 运行时 replay 适配”理解。

第一步，插件发现主要依赖 `extensions/sglang/package.json` 和 `extensions/sglang/openclaw.plugin.json`。`package.json` 告诉 OpenClaw 插件入口是 `./index.ts`；清单文件提供静态 provider、认证选择和 schema 信息。这里的 `activation.onStartup: false` 表示它不需要在启动时靠副作用激活，可由插件系统按需加载。

第二步，加载入口后进入 `extensions/sglang/index.ts`。`definePluginEntry` 把插件包装成 SDK 能识别的 entry，`registerProvider` 把 SGLang 接入 provider registry。`docsPath: "/providers/sglang"` 是 provider 文档路径标识；最终文档站点地址不在本学习文档中展开。

第三步，用户配置 provider 时走 `auth.custom.run` 或 `auth.custom.runNonInteractive`。两条路径都把 `providerId`、`providerLabel`、默认 base URL、默认 API key 环境变量和模型占位符传给 SDK 的 OpenAI-compatible self-hosted provider setup helper。也就是说，SGLang 插件本身只提供身份和默认值，通用配置流程由 SDK 负责。

第四步，模型发现走 `catalog.run` 到 `discoverOpenAICompatibleSelfHostedProvider`，再进入本地 `buildSglangProvider`。`buildSglangProvider` 内部调用 `discoverOpenAICompatibleLocalModels`，说明 SGLang 被当作 OpenAI-compatible local server 来枚举模型，而不是使用 SGLang 专用私有协议。

第五步，replay 行为通过 `buildProviderReplayFamilyHooks({ family: "openai-compatible", dropReasoningFromHistory: false })` 接入。测试 `extensions/sglang/index.test.ts` 证明默认情况下它继承 OpenAI-compatible replay 族的工具调用 id 清理、ordering fix 和 turn validation 等策略，同时默认不丢弃 reasoning history；但对 `google/gemma-4-26b-a4b-it` 这类 Gemma 4 chat-completions 模型，仍会 drop historical reasoning。这说明具体模型仍可能被共享 replay family 的模型级规则特殊处理。

## 推荐阅读顺序

建议先读 `extensions/sglang/openclaw.plugin.json`，理解这个插件暴露给系统的静态能力：id、provider、认证入口、request family 和 schema。

第二步读 `extensions/sglang/package.json`，确认插件包名、SDK 依赖和 OpenClaw entrypoint。这个文件能帮助你把“包级插件”与“运行入口”联系起来。

第三步读 `extensions/sglang/index.ts`。这是主流程核心，应重点看 `definePluginEntry`、`api.registerProvider`、`auth`、`catalog`、`wizard` 和 `buildProviderReplayFamilyHooks`。读完这里基本就知道 SGLang provider 如何进入 OpenClaw。

第四步读 `extensions/sglang/defaults.ts` 和 `extensions/sglang/models.ts`。前者解释默认配置来源，后者解释如何把用户输入或默认值转换成 OpenClaw provider config，并如何发现模型。

第五步读 `extensions/sglang/api.ts`。它很短，但能体现插件对外暴露的轻量 API 边界：默认值和 provider builder 通过 barrel 导出，避免外部调用者依赖更深的内部结构。

最后读 `extensions/sglang/index.test.ts`、`extensions/sglang/provider-discovery.contract.test.ts`。前者帮助理解 replay policy 的具体承诺，后者帮助理解 SDK provider discovery contract 对这个插件的要求。

## 常见误区

第一个误区是把 `extensions/sglang` 当作 SGLang 服务实现。它不是推理服务器，也不启动模型服务；它只是 OpenClaw 的 provider 插件，默认指向一个已经运行的 OpenAI-compatible SGLang endpoint。

第二个误区是以为这里必须维护一套 SGLang 专用模型发现协议。当前代码通过 `discoverOpenAICompatibleLocalModels` 发现模型，并返回 `api: "openai-completions"`。根据当前片段推断，OpenClaw 将 SGLang 作为 OpenAI-compatible provider 处理，而不是另建一条独立 API 栈。

第三个误区是忽略 `openclaw.plugin.json`。这个清单不是装饰文件；它承载 provider request、auth env vars、wizard choice、config schema 等控制面信息。很多发现和设置流程可以在不执行插件 runtime 的情况下读取这些信息。

第四个误区是把 setup helper 直接内联进插件。`index.ts` 通过 `loadProviderSetup()` 动态导入 `openclaw/plugin-sdk/provider-setup`，并复用 SDK 的 self-hosted OpenAI-compatible 配置流程。这符合 `extensions/AGENTS.md` 中“通过 SDK seam 交互”的边界要求。

第五个误区是认为 `dropReasoningFromHistory: false` 对所有模型绝对生效。测试显示，SGLang provider 默认不丢弃 reasoning history，但共享 replay family 仍可能按模型规则处理特例，例如 Gemma 4 chat-completions 模型。

第六个误区是从 core 或其他插件深度导入 `models.ts`、`defaults.ts`。如果需要复用 SGLang 的轻量能力，应优先看 `extensions/sglang/api.ts` 暴露了什么；生产代码跨边界访问插件内部实现通常不符合 bundled plugin 的边界约束。
