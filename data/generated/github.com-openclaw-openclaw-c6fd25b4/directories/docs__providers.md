# 目录：docs/providers

## 它负责什么

`docs/providers` 是 OpenClaw 文档体系里“模型与能力提供方”的公开说明目录，主要面向想把 OpenClaw 接到不同 AI 服务、网关、本地推理引擎或语音/图像能力的用户。它不承载运行时代码，也不是 provider 注册表本身；它的角色是把“支持哪些 provider、如何认证、如何选择默认模型、哪些 provider 支持附加能力”整理成 Mintlify 文档页面。

从 `docs/providers/index.md` 和 `docs/providers/models.md` 可以看出，这个目录的核心叙事是：OpenClaw 可以使用多个 LLM provider；用户先选择 provider，完成认证，再把默认模型配置给 agent。单个 provider 页面则围绕具体服务展开，例如 `docs/providers/openai.md`、`docs/providers/anthropic.md`、`docs/providers/google.md`、`docs/providers/openrouter.md`、`docs/providers/ollama.md` 等。目录里也包含不完全等同于传统 LLM 的能力页，例如 `docs/providers/deepgram.md`、`docs/providers/azure-speech.md`、`docs/providers/elevenlabs.md`、`docs/providers/comfy.md`、`docs/providers/fal.md`、`docs/providers/runway.md`，说明这里的“providers”在文档层面覆盖了模型、语音、转录、图像/媒体生成、统一网关和本地推理等入口。

## 直接子目录地图

`docs/providers` 当前没有直接子目录，是一个扁平 Markdown 页面集合。所有 provider 文档都直接放在这一层，例如 `docs/providers/alibaba.md`、`docs/providers/bedrock.md`、`docs/providers/deepseek.md`、`docs/providers/mistral.md`、`docs/providers/qwen.md`、`docs/providers/xai.md`、`docs/providers/zai.md`。

这个扁平结构意味着读者不应该按文件系统层级理解 provider 分类，而应该按导航和索引页理解分类。实际分组主要来自 `docs/docs.json` 中 Models tab 下的导航配置，以及 `docs/providers/index.md` 内部的段落：先是 provider 总入口和 provider 列表，再是 image generation 相关入口、transcription providers、社区或特殊代理说明等。换句话说，文件层级只负责存放页面；信息架构主要由 `docs/docs.json` 和索引页文本决定。

## 关键入口

最重要的入口是 `docs/providers/index.md`。它的 frontmatter 标识为 provider directory，正文给出 provider 文档列表，并把用户引向更概念化的 `docs/concepts/model-providers`。学习这个目录时，应把它当作总目录和分类导览，而不是某个具体 provider 的配置教程。

第二个入口是 `docs/providers/models.md`。它同样解释 OpenClaw 可使用多个 LLM provider，但更像“模型 provider 的入门页”，列出 starter set，并指向模型选择、模型 CLI、provider 概念说明等相关页面。根据当前片段推断，`models.md` 更适合新用户从“我要选模型”角度进入，而 `index.md` 更适合从“我要找某个 provider 文档”角度进入；依据是两者标题和列表范围不同，且 `docs/docs.json` 把二者一起放在 Models tab 的 Get started 分组里。

第三个入口是 `docs/docs.json`。它不是 provider 文档正文，但决定这些页面如何出现在站点导航中：Models tab 下有 `providers/index`、`providers/models`；Concepts 分组包含 `concepts/models`、`concepts/model-providers`、`concepts/model-failover`；Providers 分组列出大量 `providers/*` 页面。它还维护旧路径或短路径到 provider 页的 redirects，例如 `/openai` 到 `providers/openai`、`/anthropic` 到 `providers/anthropic`、`/providers/glm` 到 `providers/zai`。这些 redirects 说明 provider 文档还承担兼容旧文档路径和常用入口的职责。

## 主流程位置

从文档主流程看，`docs/providers` 位于“概念理解”和“具体配置”之间。上游概念页是 `docs/concepts/models`、`docs/concepts/model-providers`、`docs/concepts/model-failover`，它们解释模型、provider、failover 这类抽象。`docs/providers/index.md` 和 `docs/providers/models.md` 把这些概念落到可选 provider 清单。具体 provider 页面则继续下钻到认证、环境变量、模型名称、CLI 或本地服务配置。

从用户路径看，典型流程是：先读 `docs/providers/models.md` 理解 OpenClaw 如何选择默认 provider 和 model；再到 `docs/providers/index.md` 找到目标 provider；然后进入具体页面，例如 `docs/providers/openai.md`、`docs/providers/anthropic.md`、`docs/providers/ollama.md` 或 `docs/providers/litellm.md`；最后回到相关运行文档，例如 `docs/cli/models` 或 agent 配置页面，完成实际启用。根据当前片段推断，provider 页面本身主要解决“这个服务如何接入 OpenClaw”，而跨 provider 的选择策略、故障切换和模型抽象不在本目录展开，依据是索引页把这类内容指向 `concepts/model-providers` 和 `concepts/model-failover`。

从维护流程看，新增 provider 文档不只是新增一个 `docs/providers/*.md` 文件，还需要检查 `docs/providers/index.md` 是否列出、`docs/docs.json` 是否加入 Models tab 的 Providers 分组、是否需要 redirects，以及是否与文档规则保持一致。`docs/AGENTS.md` 还要求 provider/service 列表按字母排序，除非页面明确描述运行时顺序或自动检测顺序。

## 推荐阅读顺序

1. 先读 `docs/providers/models.md`，建立“OpenClaw 支持多 provider、需要认证、需要设置默认模型”的基本认识。
2. 再读 `docs/providers/index.md`，把目录里的 provider 按用途粗分：主流 LLM API、统一网关、本地模型、云厂商、语音转录、图像/媒体生成、社区代理。
3. 接着读 `docs/concepts/model-providers`、`docs/concepts/model-failover`，理解 provider 选择和 failover 不只是某个页面的配置项，而是 OpenClaw 的模型运行抽象。
4. 然后按目标服务读具体 provider 页，例如 OpenAI 读 `docs/providers/openai.md`，Anthropic 读 `docs/providers/anthropic.md`，本地 Ollama 读 `docs/providers/ollama.md`，统一转发读 `docs/providers/openrouter.md` 或 `docs/providers/litellm.md`。
5. 如果关注非文本能力，再读 `docs/providers/deepgram.md`、`docs/providers/elevenlabs.md`、`docs/providers/senseaudio.md`、`docs/providers/comfy.md`、`docs/providers/fal.md`、`docs/providers/runway.md` 等页面，并结合对应 tools 文档理解实际调用入口。
6. 最后查看 `docs/cli/models` 或相关 agent/session 配置文档，把 provider 文档中的模型名、认证方式和默认选择落到实际命令或配置里。

## 常见误区

一个常见误区是把 `docs/providers` 当成运行时 provider 实现目录。它只是文档目录；真正的 provider 路由、插件 SDK、运行时注册、认证存储和模型调用逻辑在源码其他位置。学习源码时可以用这里建立名称和能力地图，但不能直接从文档文件推断实现细节。

第二个误区是以为这里有按类型划分的子目录。当前目录没有 `llm/`、`speech/`、`image/` 之类子目录，分类来自 `docs/docs.json` 导航和 `index.md` 段落。因此查找时优先看索引和导航，不要期待文件系统体现完整 IA。

第三个误区是把所有 provider 页面都看成同一类 LLM 配置。目录中有 OpenAI、Anthropic、Google、Mistral、Moonshot、Qwen 等 LLM provider，也有 Deepgram、Azure Speech、SenseAudio 这类转录/语音能力，还有 ComfyUI、fal、Runway 这类图像或媒体相关 provider。阅读时要先判断页面对应的是模型聊天、转录、语音、图像、网关还是本地推理。

第四个误区是忽略 redirects 和旧称。`docs/docs.json` 里保留了若干 provider 旧路径或别名，例如 Qwen Model Studio 迁移到 Qwen、GLM 迁移到 Z.AI。这说明文档对外部链接有兼容责任；维护时不能只改文件名，还要考虑旧入口是否需要继续跳转。

第五个误区是把 provider 文档当作唯一事实来源。provider 能力、认证字段和默认模型往往依赖上游服务和 OpenClaw 运行时实现；如果要做修复或深入源码学习，需要继续阅读 runtime、plugin、SDK、CLI 和测试，而不是只依据 `docs/providers/*.md` 下结论。本次环境中 `pnpm docs:list` 因缺少 `pnpm` 未能执行，以上概览主要依据 `docs/AGENTS.md`、`docs/docs.json`、`docs/providers/index.md`、`docs/providers/models.md` 和目录文件清单。
