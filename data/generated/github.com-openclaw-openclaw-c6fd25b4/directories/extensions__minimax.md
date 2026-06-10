# 目录：extensions/minimax

## 它负责什么

`extensions/minimax` 是 OpenClaw 内置的 MiniMax provider/plugin 包，包名是 `@openclaw/minimax-provider`。从 `package.json` 和 `openclaw.plugin.json` 看，它同时承担两类职责：一是把 MiniMax 注册为模型与多媒体能力 provider，二是维护 MiniMax 相关的认证、OAuth、onboarding、配置 schema 与静态发现元数据。

这个目录属于 `extensions/` 下的 bundled plugin。按 `extensions/AGENTS.md` 的边界规则，生产代码应通过 `openclaw/plugin-sdk/*` 和本插件自己的本地 API 暴露能力，不能直接依赖 core 内部 `src/**`。因此学习这个目录时要把它看成“第三方插件也能使用的边界样本”：核心系统通过 manifest、package 的 `openclaw.extensions`、插件入口和 SDK contract 识别它，而不是靠 core 深入读取插件内部实现。

从 `openclaw.plugin.json` 可以看到它声明的 provider id 主要是 `minimax` 与 `minimax-portal`，还保留了 `legacyPluginIds`：`minimax-portal-auth`。能力覆盖面较广，包括 speech、media understanding、image generation、music generation、video generation、web search。也就是说，这不是一个单一聊天模型插件，而是一个聚合 MiniMax 文本模型、视觉理解、语音、图像、音乐、视频和搜索能力的 provider 包。

## 直接子目录地图

这个目录结构很浅，直接子目录只有一个：

`extensions/minimax/src`

`src` 目前承载的是 MiniMax web search 的运行时相关实现与测试入口，例如 `src/minimax-web-search-provider.ts`、`src/minimax-web-search-provider.runtime.ts`、`src/minimax-web-search-provider.test.ts`。根据当前片段推断，web search 被单独放进 `src/`，是因为它有独立的 provider contract、运行时边界或私有实现细节；而多数 MiniMax provider 文件仍平铺在 `extensions/minimax` 根层，作为插件主入口、注册、认证和各能力 provider 的主要实现位置。

目录根层文件可以粗略分为几组：插件入口与公开 API、provider 注册与模型目录、各能力 provider、认证/onboarding、测试与契约文件、插件元数据。

## 关键入口

`extensions/minimax/package.json` 是 npm/package 级入口提示。它的 `openclaw.extensions` 指向 `./index.ts`，说明 OpenClaw 的插件发现流程会把 `extensions/minimax/index.ts` 当成该包的插件入口。

`extensions/minimax/openclaw.plugin.json` 是控制平面入口。它声明插件 id、是否默认启用、provider id、认证环境变量、认证选择、能力 contract、配置 schema、UI hint 和媒体理解元数据。很多不需要执行插件代码的发现、设置、配置校验和 UI 提示都应该从这里读取。学习时应优先看这个文件，因为它回答“这个插件对外声称自己提供什么”。

`extensions/minimax/index.ts` 是运行时插件入口。虽然当前任务只读取到文件清单和 manifest，未展开源码细节，但根据 `package.json` 的 `openclaw.extensions` 指向，可以确定它是插件被激活时最关键的 TypeScript 入口。它大概率负责把 MiniMax provider、OAuth/onboarding 或相关 hooks 交给 OpenClaw plugin runtime。

`extensions/minimax/api.ts` 和 `extensions/minimax/test-api.ts` 是本插件的本地 API 边界。按 `extensions/AGENTS.md` 的规则，如果 core 或测试需要使用 bundled plugin 的 helper，应先通过 `api.ts` 这类公开 barrel 暴露，而不是 deep import 插件私有实现。`test-api.ts` 则从命名看更偏测试辅助或测试专用导出。

`extensions/minimax/provider-registration.ts`、`extensions/minimax/provider-contract-api.ts`、`extensions/minimax/provider-discovery.contract.test.ts`、`extensions/minimax/plugin-registration.contract.test.ts` 是 provider 接入与契约校验的关键区域。它们共同说明这个目录不只是写功能实现，还要证明插件发现、注册、contract 声明与 OpenClaw 期望一致。

## 主流程位置

第一条主流程是插件发现与注册。控制面先看 `extensions/minimax/openclaw.plugin.json`，知道插件 id 是 `minimax`，默认启用，且提供 `minimax`、`minimax-portal` 两个 provider。随后从 `extensions/minimax/package.json` 的 `openclaw.extensions` 找到 `extensions/minimax/index.ts`。根据当前片段推断，`index.ts` 再连接 `provider-registration.ts`、`provider-catalog.ts`、`provider-models.ts` 和各能力 provider 文件，完成运行时注册。

第二条主流程是模型与 provider 目录。`extensions/minimax/model-definitions.ts`、`extensions/minimax/provider-models.ts`、`extensions/minimax/provider-catalog.ts` 是理解“有哪些 MiniMax 模型、如何归类、如何暴露给 OpenClaw”的核心位置。对应的 `model-definitions.test.ts` 用来约束模型定义不漂移。manifest 中出现的 `MiniMax-M2.7`、`MiniMax-VL-01` 等默认模型线索，也应回到这些文件中确认。

第三条主流程是认证与 onboarding。`extensions/minimax/oauth.ts`、`extensions/minimax/oauth.runtime.ts`、`extensions/minimax/onboard.ts` 负责 MiniMax OAuth、API key 或 portal 登录相关体验。`openclaw.plugin.json` 中的 `providerAuthChoices` 显示它支持 global 与 CN 两组选择，并区分 `oauth`、`oauth-cn`、`api-global`、`api-cn`。环境变量包括 `MINIMAX_CODE_PLAN_KEY`、`MINIMAX_CODING_API_KEY`、`MINIMAX_API_KEY`、`MINIMAX_OAUTH_TOKEN`。学习这里时要注意认证逻辑是插件自有职责，不应被挪到 core。

第四条主流程是各能力 provider。`speech-provider.ts` 对应 speech；`media-understanding-provider.ts` 对应图片/文档理解；`image-generation-provider.ts`、`music-generation-provider.ts`、`video-generation-provider.ts` 分别对应生成式媒体能力；`web-search-provider.ts`、`web-search-contract-api.ts` 和 `src/minimax-web-search-provider*.ts` 对应 web search。测试文件基本与能力文件一一对应，是确认行为边界的最好辅助材料。

第五条主流程是 HTTP 与 live 验证。`provider-http.test-helpers.ts` 提供 provider 测试中的 HTTP 辅助；`minimax.live.test.ts` 表明这个插件存在真实服务或 live 环境验证路径。overview 阶段不需要先跑 live test，但要知道它是证明 MiniMax 真实行为的证据入口。

## 推荐阅读顺序

建议先读 `extensions/minimax/openclaw.plugin.json`，建立插件 id、provider id、认证方式、配置 schema、能力 contract 的全局地图。

第二步读 `extensions/minimax/package.json` 和 `extensions/minimax/index.ts`，确认 OpenClaw 如何发现并激活这个插件。

第三步读 `extensions/minimax/provider-registration.ts`、`extensions/minimax/provider-catalog.ts`、`extensions/minimax/provider-models.ts`、`extensions/minimax/model-definitions.ts`，理解 MiniMax provider 与模型目录如何被组织。

第四步按能力选读 provider：文本/模型目录看 provider 相关文件，图片理解看 `media-understanding-provider.ts`，语音看 `speech-provider.ts` 与 `tts.ts`，图像/音乐/视频生成分别看对应 `*-generation-provider.ts`，搜索看 `web-search-provider.ts`、`web-search-contract-api.ts`、`src/minimax-web-search-provider.ts`、`src/minimax-web-search-provider.runtime.ts`。

第五步读认证链路：`oauth.ts`、`oauth.runtime.ts`、`onboard.ts`。这里应和 manifest 的 `providerAuthChoices`、`providerAuthEnvVars` 对照看。

最后读测试：优先看 `plugin-registration.contract.test.ts`、`provider-discovery.contract.test.ts`、`model-definitions.test.ts`，再看各能力 provider 的单测和 `minimax.live.test.ts`。这样能先掌握契约，再看具体行为。

## 常见误区

不要把 `extensions/minimax` 当成 core provider 实现。它位于 bundled plugin 区域，原则上应遵守第三方插件能看到的 SDK 边界；生产代码不应依赖 OpenClaw core 内部路径。

不要只看 `index.ts` 就认为能力范围很小。真正的对外能力大多在 `openclaw.plugin.json`、provider catalog、model definitions 和各 `*-provider.ts` 中声明或实现。

不要混淆 `minimax` 与 `minimax-portal`。manifest 中两者都被声明为 provider，并且认证方式、OAuth/API key、global/CN endpoint 选择有差异。读认证和 provider 注册时要确认当前逻辑作用于哪个 provider id。

不要把 `src/` 理解成整个插件源码根。这个插件的大量实现文件直接位于 `extensions/minimax` 根层，`src/` 目前更像 web search 相关私有实现区域。根据当前片段推断，根层平铺是该插件既有组织方式，不代表这些文件都是公开 API。

不要跳过 contract test。`plugin-registration.contract.test.ts`、`provider-discovery.contract.test.ts`、`provider-registration` 相关文件比普通单测更能说明插件与 OpenClaw runtime 的稳定边界。

不要把环境变量、配置 key 或 legacy id 当成可随意清理的内部细节。manifest 中的 `legacyPluginIds`、`providerAuthAliases`、`configContracts.compatibilityRuntimePaths` 都暗示存在升级或兼容语义；修改这类内容通常需要迁移、doctor 或更广验证。
