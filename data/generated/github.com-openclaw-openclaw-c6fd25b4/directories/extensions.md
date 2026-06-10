# 目录：extensions

## 它负责什么

`extensions` 是 OpenClaw 仓库里的 bundled plugins 集合区。根据 `extensions/AGENTS.md`，这里要被当成第三方插件能看到的同一条边界来理解：插件生产代码应通过 `openclaw/plugin-sdk/*`、本插件自己的 `api.ts`、`runtime-api.ts` 等公开面与核心交互，而不是直接穿透到 `src/**`、`src/channels/**`、`src/plugin-sdk-internal/**` 或其他插件的 `src/**`。

从目录形态看，`extensions` 承载了多类插件：模型 provider、消息 channel、工具能力、诊断能力、记忆能力、媒体生成/理解能力、迁移工具、QA/测试插件等。每个子目录通常就是一个独立 npm 包，`package.json` 里有 `@openclaw/plugin-sdk` 依赖和 `openclaw` 元数据块，用来支持插件发现、安装、setup、能力声明和运行时激活。这里不是“核心业务随手放置区”，而是插件边界、插件元数据和插件运行时实现的集中仓库。

## 直接子目录地图

这是一个大目录，不适合逐个叶子解释。按角色可粗略分组：

模型与推理 provider 主要包括 `openai`、`anthropic`、`google`、`xai`、`deepseek`、`qwen`、`moonshot`、`mistral`、`groq`、`ollama`、`openrouter`、`lmstudio`、`vllm`、`litellm`、`amazon-bedrock`、`azure` 相关包、`nvidia`、`together`、`fireworks`、`cerebras`、`minimax`、`zai`、`alibaba`、`volcengine` 等。它们通常负责模型目录、鉴权、请求适配、流式响应、工具 schema 兼容和 provider 本地策略。

消息 channel 插件包括 `discord`、`telegram`、`slack`、`whatsapp`、`signal`、`matrix`、`mattermost`、`msteams`、`googlechat`、`feishu`、`line`、`irc`、`twitch`、`zalo`、`zalouser`、`synology-chat`、`nextcloud-talk`、`qqbot` 等。它们负责接收外部消息、路由到 agent、处理回复、thread/channel 绑定、原生交互和平台特有鉴权。

工具和能力插件包括 `browser`、`brave`、`duckduckgo`、`searxng`、`tavily`、`exa`、`firecrawl`、`web-readability`、`file-transfer`、`document-extract`、`diffs`、`canvas`、`oc-path`、`llm-task` 等。它们更像是给 agent 增加可调用能力或上下文处理能力。

媒体、语音和生成相关插件包括 `image-generation-core`、`video-generation-core`、`media-understanding-core`、`speech-core`、`deepgram`、`elevenlabs`、`azure-speech`、`voice-call`、`tts-local-cli`、`runway`、`fal`、`comfy`、`senseaudio` 等。名称带 `*-core` 的目录更像运行时能力包或共享能力层，根据当前片段推断，它们为具体 provider 或插件提供统一抽象。

记忆和知识类包括 `memory-core`、`memory-lancedb`、`memory-wiki`、`active-memory`。诊断和管理类包括 `diagnostics-otel`、`diagnostics-prometheus`、`admin-http-rpc`、`policy`。测试与内部验证类包括 `qa-channel`、`qa-lab`、`qa-matrix`、`synthetic`、`test-support`。迁移类包括 `migrate-claude`、`migrate-hermes`。还有 `codex`、`opencode`、`opencode-go`、`github-copilot`、`kilocode`、`kimi-coding` 等 harness 或开发者工作流相关插件。

## 关键入口

多数插件的第一入口是 `extensions/<plugin>/index.ts`。命令扫描显示大量子目录都有这个文件，例如 `extensions/openai/index.ts`、`extensions/anthropic/index.ts`、`extensions/discord/index.ts`、`extensions/telegram/index.ts`、`extensions/browser/index.ts`、`extensions/qa-lab/index.ts`。学习时可以把它当作“插件声明和注册入口”，先看它导出了什么、如何引用 SDK、如何把本地实现挂到插件定义上。

`extensions/<plugin>/package.json` 是另一个关键入口。这里保存包名、描述、依赖、exports，以及 `openclaw` 元数据。对 channel 插件，`package.json` 里常能看到 `channel` 配置、`docsPath`、`pluginApi` 版本要求等字段，例如 `extensions/telegram/package.json`、`extensions/discord/package.json`、`extensions/qa-channel/package.json`。这些元数据支持插件发现和 setup 流程，不应依赖执行运行时代码才能知道插件是否存在。

`api.ts` 是对外公开的轻量 API 面。很多 provider 或 channel 都有，例如 `extensions/openai/api.ts`、`extensions/anthropic/api.ts`、`extensions/google/api.ts`、`extensions/discord/api.ts`。如果核心或测试确实需要使用 bundled plugin 的 helper，按边界规则应先通过 `api.ts` 暴露，而不是 deep import 插件内部文件。

`runtime-api.ts` 是运行时公开面，常见于 channel、工具或较复杂插件，例如 `extensions/discord/runtime-api.ts`、`extensions/telegram` 目录下的运行时实现、`extensions/browser/runtime-api.ts`、`extensions/canvas/runtime-api.ts`、`extensions/memory-core/runtime-api.ts`、`extensions/qa-lab/runtime-api.ts`。它通常帮助运行时代码与插件内部实现、测试替身或核心 runtime seam 对齐。

`src/` 是插件内部实现区。例如 `extensions/discord/src`、`extensions/feishu/src`、`extensions/telegram/src`、`extensions/browser/src`。这里的文件在插件外部默认是私有实现，除非被显式提升到 `api.ts` 或 SDK facade。

## 主流程位置

插件主流程大致从元数据开始：核心或插件加载器读取每个 `package.json` 的包信息和 `openclaw` 元数据，判断插件类型、能力、版本兼容、setup 信息和 channel/provider 描述。根据 `extensions/AGENTS.md`，控制面元数据应尽量与运行时逻辑分离，发现、配置校验、setup hints、onboarding hints、activation planning 都应能由 manifest 或 descriptor 表达。

激活阶段进入 `index.ts`。这里通常组装插件定义，引用 `openclaw/plugin-sdk/*`，再连接到本插件的 provider、channel、tool、setup 或 runtime 实现。对 provider 插件，主流程会落到模型 catalog、认证、请求构造、流式处理、工具 schema 归一化和厂商兼容逻辑。对 channel 插件，主流程会进入平台客户端、消息监听、入站路由、会话绑定、回复派发、原生 command 或 approval 流程。对工具插件，主流程则进入工具声明、参数 schema、执行函数和返回结果规范化。

根据当前片段推断，复杂 channel 的核心实现通常在 `src/monitor`、`src/channel*`、`src/runtime*`、`src/send*` 一类文件附近；例如扫描结果显示 `extensions/discord/src/monitor/provider.ts`、`extensions/discord/src/monitor/agent-components.dispatch.ts`、`extensions/feishu/src/channel.ts`、`extensions/feishu/src/send.ts` 等。provider 插件则更常在 `index.ts`、`api.ts` 和本地 `src` 实现之间完成封装。

## 推荐阅读顺序

第一步读 `extensions/AGENTS.md`，先建立边界意识：插件只能依赖 SDK 和本插件公开面，不能把核心内部当作公共 API。

第二步选一个简单 provider，例如 `extensions/openai/package.json`、`extensions/openai/index.ts`、`extensions/openai/api.ts`，理解 provider 插件如何声明包、公开 API、接入 SDK。

第三步选一个 channel 插件，例如 `extensions/telegram/package.json`、`extensions/telegram/index.ts`、`extensions/telegram/src`，再对照 `extensions/discord/package.json`、`extensions/discord/index.ts`、`extensions/discord/runtime-api.ts`。channel 更复杂，适合在理解 provider 后阅读。

第四步看工具类插件，例如 `extensions/browser/index.ts`、`extensions/file-transfer/index.ts`、`extensions/web-readability/index.ts`，重点看工具能力如何从插件注册到 agent 可用能力。

第五步再看能力核心包，例如 `extensions/memory-core`、`extensions/image-generation-core`、`extensions/speech-core`。这些目录更像跨插件能力抽象，适合最后理解复用关系。

## 常见误区

不要把 `extensions` 当成 core 的子模块来读。它虽然在同一仓库中，但设计上要遵守第三方插件边界；生产代码不应直接 import `src/**` 或其他插件内部 `src/**`。

不要只看 `src/`。插件的发现、安装、setup 和 UI 展示很依赖 `package.json` 的 `openclaw` 元数据，很多“为什么能被识别”的答案不在运行时代码里。

不要把 `api.ts`、`runtime-api.ts` 和 `src/` 混为一谈。`api.ts` 是可被外部安全引用的窄公开面；`runtime-api.ts` 通常服务运行时 seam；`src/` 默认是插件私有实现。

不要复制 provider 兼容逻辑。`extensions/AGENTS.md` 明确要求先检查 `openclaw/plugin-sdk/*` 里是否已有共享 helper，再考虑新增本地 `wrapStreamFn`、`normalizeToolSchemas`、compat patch 等逻辑。

不要在 core 中硬编码 bundled plugin 的厂商行为。provider 的 auth、onboarding、catalog selection、vendor-only product behavior 应留在对应插件内；核心只保留通用 seam。

不要把 channel 插件理解为普通 webhook。像 `discord`、`telegram`、`feishu` 这类目录通常包含入站消息、路由、会话、回复、approval、原生交互、配置和 setup 多条流程，阅读时应按主流程拆开，而不是逐文件线性阅读。
