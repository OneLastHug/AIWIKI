# 目录：plans

## 它负责什么

`plans` 是一个轻量级的设计方案目录，用来存放尚未完全落入正式文档、测试或实现代码的工程计划。根据当前仓库片段，它不是运行时代码目录，也不参与包加载、插件发现或 CLI 命令注册；它更像维护者在实现前后留下的“路线图”和技术取舍记录。

当前目录下只有 `plans/gemini-oauth-provider.md`。这个文件描述的是为 Hermes 增加 Gemini OAuth Provider 的实现计划，主题包括：选择标准 Gemini API 而不是 Cloud Code Assist、OAuth Authorization Code + PKCE 流程、token 生命周期、Provider 集成点、预计新增/修改文件、测试与文档补充范围等。

需要注意的是，仓库当前实现状态已经和计划文档里的设想发生了部分分化：源码中已经存在 `plugins/model-providers/gemini/__init__.py`、`agent/gemini_native_adapter.py`、`agent/gemini_cloudcode_adapter.py`、`agent/google_oauth.py` 等相关实现痕迹。其中 `gemini` 当前是 API key 形态的 Google AI Studio Provider，而 `google-gemini-cli` 才是 Cloud Code Assist OAuth 形态。也就是说，`plans/gemini-oauth-provider.md` 更适合作为理解历史设计意图、比较实现演进的材料，而不应直接当成当前系统行为说明。

## 直接子目录地图

`plans` 当前没有直接子目录。

目录结构可以概括为：

```text
plans/
└── gemini-oauth-provider.md
```

`plans/gemini-oauth-provider.md` 是该目录唯一的内容文件，负责记录 Gemini OAuth Provider 的方案草案。它没有配套脚本、测试夹具或可被导入的 Python 模块。

由于目录没有分层，阅读时不需要按子目录建立地图；更重要的是把它和实际实现目录对应起来看，例如 `plugins/model-providers/gemini`、`agent`、`hermes_cli`、`tests`、`website/docs` 等。

## 关键入口

`plans` 自身没有程序入口。它的“入口”是文档入口，即 `plans/gemini-oauth-provider.md`。

该计划文件中提到的关键实现入口主要分布在几个位置：

`plugins/model-providers/gemini/__init__.py` 是当前 Gemini Provider Profile 的核心定义位置。它注册了 `gemini` 和 `google-gemini-cli` 两个 Provider：前者面向 Google AI Studio / Gemini API，使用 API key；后者面向 Cloud Code Assist OAuth，使用 `oauth_external` 类型。该文件还通过 `GeminiProfile.build_extra_body()` 处理 Gemini reasoning 配置到 `thinking_config` 的转换。

`agent/agent_runtime_helpers.py` 是运行期选择具体客户端适配器的位置。当前逻辑中，如果 provider 是 `google-gemini-cli` 或 base_url 走 Cloud Code Assist scheme，会创建 `GeminiCloudCodeClient`；如果 provider 是 `gemini` 且 base_url 是 Gemini native endpoint，会创建 `GeminiNativeClient`。这说明实际主流程已经不是直接依赖 OpenAI SDK 访问 Gemini，而是通过 Hermes 自己的适配器维持 OpenAI-shaped 的调用界面。

`agent/gemini_native_adapter.py` 是 Gemini native API 的 OpenAI-compatible facade。它把 Hermes 主循环中的 `messages[]`、`tools[]` 等 OpenAI 风格结构转换为 Gemini native `generateContent` 风格请求，再把响应转换回来。它承担了当前 `gemini` Provider 的主要协议适配职责。

`agent/gemini_cloudcode_adapter.py` 是 Cloud Code Assist backend 的适配器。它同样暴露类似 `.chat.completions.create()` 的接口，但底层请求面向 Cloud Code Assist，并依赖 `agent/google_oauth.py`、`agent/google_code_assist.py` 获取 OAuth token 和项目上下文。它对应当前的 `google-gemini-cli` Provider，而不是计划文件中想避免的“标准 Gemini OAuth”路线。

`hermes_cli/runtime_provider.py` 是 CLI / agent 启动时解析 provider、base_url、认证凭据和运行期配置的重要位置。搜索结果显示这里有 `resolve_gemini_oauth_runtime_credentials()` 和 `google-gemini-cli` 分支，用于处理 Gemini CLI OAuth 相关运行期凭据。

## 主流程位置

从当前源码推断，Gemini 相关主流程可以按“Provider 注册、运行期解析、客户端构造、协议适配、agent loop 调用”理解。

第一步是 Provider 注册。`plugins/model-providers/gemini/__init__.py` 定义 `gemini` 与 `google-gemini-cli`，并调用 `register_provider()` 注册。这里决定 provider 名称、别名、认证方式、默认 base_url、默认辅助模型和 `api_mode`。虽然两个 Provider 都报告 `api_mode="chat_completions"`，但实际底层并不一定走标准 OpenAI 传输。

第二步是运行期配置解析。`hermes_cli/runtime_provider.py` 根据用户选择的 provider、环境变量、OAuth 状态或配置文件，解析出运行所需的 key、token、base_url 等参数。计划文件原本设想新增标准 Gemini OAuth 的配置分支，但当前实现中能明确看到的是 `google-gemini-cli` 相关 OAuth 分支，以及 `gemini` 的 API key 路径。

第三步是客户端构造。`agent/agent_runtime_helpers.py` 在构建 LLM client 时检查 provider 和 base_url：`google-gemini-cli` 进入 `GeminiCloudCodeClient`；`gemini` 且为 native Gemini endpoint 时进入 `GeminiNativeClient`。这一步是从抽象 provider 配置落到具体协议适配器的关键位置。

第四步是请求/响应转换。`agent/gemini_native_adapter.py` 负责标准 Gemini native API 的 schema 转换，`agent/gemini_cloudcode_adapter.py` 负责 Cloud Code Assist 的 schema 和 envelope 转换。两者都试图对上层保持 OpenAI chat completions 风格接口，让 `run_agent.py` 的主循环不需要为 Gemini 单独重写。

第五步才是主 agent loop。`run_agent.py` 和 `agent/chat_completion_helpers.py` 继续围绕 OpenAI-shaped messages、tool calls、streaming response 等抽象工作。Gemini 的差异主要被压在 provider profile 和 adapter 层，而不是扩散到主循环。

## 推荐阅读顺序

建议先读 `plans/gemini-oauth-provider.md`，把它当成历史设计提案看，重点关注它的目标、架构取舍、token 生命周期和列出的修改点。读的时候要留意它提到“标准 Gemini API + OAuth”的方向，这和当前实现中的 `google-gemini-cli` Cloud Code Assist OAuth 并不完全相同。

然后读 `plugins/model-providers/gemini/__init__.py`，确认当前仓库实际注册了哪些 Gemini Provider，以及它们的 `auth_type`、`base_url`、别名和默认模型。这个文件能帮助你快速修正对计划文档的理解：当前 `gemini` 是 API key provider，`google-gemini-cli` 是 OAuth provider。

接着读 `agent/agent_runtime_helpers.py` 中 Gemini client 创建分支，理解 provider 如何映射到 `GeminiNativeClient` 或 `GeminiCloudCodeClient`。这里是连接配置层和协议适配层的枢纽。

之后读 `agent/gemini_native_adapter.py`，这是理解当前 `gemini` 主路径的重点。它解释了为什么 Hermes 仍保持 `chat_completions` 形态，同时绕过 Google 的 OpenAI-compatible endpoint，直接对接 Gemini native API。

最后再读 `agent/gemini_cloudcode_adapter.py`、`agent/google_oauth.py` 和 `agent/google_code_assist.py`。这组文件对应 Cloud Code Assist OAuth 路径，适合用来和计划文件中“NOT Path B”的设计选择做对照。

## 常见误区

第一个误区是把 `plans` 当成实现目录。它不是 Python package，没有被 provider discovery、tool registry 或 CLI command registry 直接加载。它只是设计材料，不能通过修改这里来改变 Hermes 行为。

第二个误区是认为 `plans/gemini-oauth-provider.md` 描述的就是当前 Gemini 行为。根据当前片段推断，该文档更像早期或中途计划：它提出要做标准 Gemini API OAuth，但当前源码中 `gemini` Provider 的 `auth_type` 是 `api_key`，而 OAuth 路径主要落在 `google-gemini-cli` / Cloud Code Assist 上。判断当前行为应以 `plugins/model-providers/gemini/__init__.py` 和 `agent/agent_runtime_helpers.py` 为准。

第三个误区是混淆 `gemini` 与 `google-gemini-cli`。`gemini` 当前对应 Google AI Studio / Gemini native API，走 `GeminiNativeClient`；`google-gemini-cli` 对应 Cloud Code Assist OAuth，走 `GeminiCloudCodeClient`。两者都向上伪装成 chat completions 风格，但底层认证、endpoint、请求 envelope 和风险边界不同。

第四个误区是以为 `api_mode="chat_completions"` 就表示一定使用 OpenAI 官方 SDK 或 OpenAI-compatible HTTP endpoint。当前 Gemini 实现说明，Hermes 可以保留 OpenAI-shaped 上层接口，同时用自定义 adapter 转译到底层 provider 的 native API。

第五个误区是照计划文件里的 URL、token 存储路径或待修改文件清单直接开发。计划中的条目需要和当前源码重新核对；例如当前已经有 `agent/google_oauth.py`，也已经有 Gemini provider plugin 和 native adapter。继续开发时应先确认现有实现的边界，再决定是补齐“标准 Gemini OAuth”，还是维护已有的 API key / Cloud Code Assist 双路径。
