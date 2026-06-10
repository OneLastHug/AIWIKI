# 子系统：src/agents/pi-embedded-helpers

## 解决什么问题

`src/agents/pi-embedded-helpers` 是 Pi embedded agent 运行链路里的“请求整理与失败恢复”辅助层。它不直接承担完整 runner，而是在真正调用模型、复用历史会话、注入工作区上下文、处理工具结果和做 provider fallback 之前，把各种容易破坏模型请求的边界问题收拢起来：bootstrap 文件裁剪、`AGENTS.md` 策略摘要、历史消息图像压缩/清理、tool call id 兼容、thinking level 降级、provider 错误分类、用户可见文本脱敏，以及重复消息判定。

从职责看，它位于 agent 核心循环和 provider SDK 之间。上层希望传入的是“当前会话、工作区上下文、模型参数和 provider 结果”，而下游 provider 往往对消息格式、图片大小、thinking 参数、错误码、工具调用 id 有不同约束。本目录把这些差异做成小而纯的 helper，避免 `pi-embedded-runner` 主流程堆满 provider 特判。

## 相关目录和文件

核心文件集中在目标目录本身：

`src/agents/pi-embedded-helpers/bootstrap.ts` 处理 bootstrap 内容预算、`AGENTS.md` 摘要、thought signature 清理，以及从配置解析 bootstrap 限额。

`src/agents/pi-embedded-helpers/images.ts` 处理会话消息里的图片、空文本块、tool result 内容和 assistant 历史消息。它调用 `src/agents/tool-images.ts` 与 `src/agents/tool-call-id.ts`，说明图片与工具调用 id 的底层规则不属于本目录，而是 agent 公共能力。

`src/agents/pi-embedded-helpers/errors.ts`、`provider-error-patterns.ts`、`failover-matches.ts` 共同负责错误识别与 fallback 判定。它们把 rate limit、overload、server error、timeout、billing、auth、format、reasoning constraint 等错误归类，供上层决定是否重试、切换模型或停止。

`src/agents/pi-embedded-helpers/thinking.ts` 负责从 provider 错误中选择 fallback thinking level，例如把不被支持的 reasoning 参数降到 `minimal` 或 `off`。

`src/agents/pi-embedded-helpers/openai.ts`、`google.ts` 是 provider 相关的格式适配入口。根据当前片段推断，它们服务于 OpenAI 兼容接口和 Google/Gemini 兼容接口的请求清理，依据是 `bootstrap.ts` 中有 `sanitizeGoogleAssistantFirstOrdering` 和 thought signature 的 Gemini 注释，`images.ts` 也区分了 Anthropic/Gemini 签名保留策略。

`src/agents/pi-embedded-helpers/messaging-dedupe.ts` 处理消息去重比较，避免渠道消息或模型输出重复投递。

`src/agents/pi-embedded-helpers/types.ts` 承载 embedded helper 共享类型，例如 bootstrap/context file 形态。

同级与上游相关目录包括 `src/agents/pi-embedded-runner`、`src/agents/agent-scope.ts`、`src/agents/workspace.ts`、`src/auto-reply/thinking.ts`、`src/shared`、`src/config`。这些路径分别提供 runner 主流程、agent 配置解析、工作区文件、thinking 枚举规范化、字符串规范化和 OpenClaw 配置类型。

## 核心对象

`AgentMessage` 是本目录处理的主要消息对象，来自 `@earendil-works/pi-agent-core`。`images.ts` 围绕它识别 `user`、`assistant`、`toolResult` 等角色，并对每类消息应用不同清理策略。

`EmbeddedContextFile` 和 `WorkspaceBootstrapFile` 表示要注入模型上下文的文件片段。`bootstrap.ts` 通过 `DEFAULT_BOOTSTRAP_MAX_CHARS`、`DEFAULT_BOOTSTRAP_TOTAL_MAX_CHARS`、`resolveBootstrapMaxChars()`、`resolveBootstrapTotalMaxChars()` 控制单文件和总预算，避免上下文无限膨胀。

`stripThoughtSignatures()` 是跨 provider 兼容的关键函数。Claude 风格内容块可能携带 `thought_signature` 或 `thoughtSignature`，但 Gemini 期望的是 base64 形式签名。该函数默认只移除 `msg_` 风格签名，也支持 `allowBase64Only` 和 `includeCamelCase`，说明它既要保护 provider 可用签名，又要避免把不兼容字段传给下游。

错误分类函数围绕 `ERROR_PATTERNS` 与若干匹配器展开，如 rate limit、billing、auth、format、timeout 等。它们不是业务错误模型，而是从 provider 返回的文本、状态码和 JSON 片段中提取“是否可重试、是否可 fallback、是否应提示用户”的判断信号。

`pickFallbackThinkingLevel()` 是 reasoning 参数恢复对象。它接收错误消息和已尝试的 `ThinkLevel` 集合，先识别 reasoning constraint，再解析 provider 提示的 supported values，最后选择还没试过的 `minimal`、`off` 或 provider 支持值。

## 运行流程

一次典型调用中，上层 runner 先准备工作区 bootstrap。`bootstrap.ts` 会读取配置中的 agent 默认值或 agent 专属值，计算单文件和总字符预算。普通文件按头尾保留并插入截断提示；`AGENTS.md` 会额外提取策略摘要，优先保留包含 must、never、security、credential、test、validation、command 等关键词的行。这样模型能看到关键规则，同时不会被超长策略文件挤爆上下文。

随后 runner 会整理历史 `AgentMessage`。`sanitizeSessionMessagesImages()` 会按角色遍历消息：`toolResult` 和 `user` 的数组内容会清理图片并移除空文本块；`assistant` 消息如果是错误停止，会尽量保留非空内容；正常 assistant 消息会根据选项决定是否保留 thought signatures，再清理图片。若内容被清空，函数会跳过或填入 `[empty content omitted]`，避免 provider 收到非法空数组。

模型请求失败后，上层会把错误文本交给错误匹配 helper。错误可能被归为限流、过载、服务器错误、超时、计费、认证、格式错误或 reasoning 参数错误。根据当前片段推断，`failover-matches.ts` 会进一步把这些分类映射到 fallback 决策，因为该目录同时存在 provider error patterns 与 failover matches 测试文件，且错误分类覆盖了可恢复和不可恢复两类信号。

当失败原因是 thinking/reasoning 参数不兼容时，`thinking.ts` 会选择下一个 thinking level。这样从支持 Claude thinking 的模型切换到 OpenAI、OpenRouter、MiniMax 或 Gemini 兼容模型时，不需要上层为每个 provider 编写独立分支。

## 上下游依赖

上游主要是 `src/agents/pi-embedded-runner` 和 agent 会话构建逻辑。它们负责决定何时调用 helper、选择 provider/model、维护 fallback 链和实际请求生命周期。

下游包括 `@earendil-works/pi-agent-core` 的消息类型、`src/config/types.openclaw.ts` 的配置结构、`src/agents/agent-scope.ts` 的 agent 配置解析、`src/agents/workspace.ts` 的 bootstrap 文件定义、`src/agents/tool-images.ts` 的图像清理、`src/agents/tool-call-id.ts` 的工具调用 id 兼容、`src/auto-reply/thinking.ts` 的 thinking level 标准化，以及 `src/shared/string-coerce.ts`、`src/shared/string-normalization.ts` 等字符串工具。

Provider 依赖不是通过强绑定 SDK 表达，而是通过错误文本、消息字段和 provider 兼容规则体现。例如 Google/Gemini 对 assistant 首条顺序和 thought signature 有特殊要求；Cloud Code Assist 对 tool call id 形态有要求；OpenAI/OpenRouter/MiniMax 风格接口可能对 reasoning 参数支持不同。

## 修改时最容易踩的坑

第一，不要把 provider 错误简单按关键词扩大匹配。`provider-error-patterns.ts` 里很多正则有意限制上下文，例如 generic `503` 不一定等于 provider overload。过宽匹配会导致本应暴露给用户的认证、计费或格式错误被错误 fallback。

第二，thought signature 清理要保守。Claude、Gemini 和 Anthropic 兼容路径的签名字段含义不同，删除过多会丢失 provider 需要的上下文，删除过少又会触发请求格式错误。

第三，历史消息清理不能只关注图片。空文本块、空 tool result、assistant error stop、tool call id 格式都会影响 provider 是否接受请求。`images.ts` 实际是在做“消息可提交性”清理，不只是压缩图片。

第四，bootstrap 截断不能破坏 `AGENTS.md` 规则可见性。该文件的摘要逻辑优先保留策略关键词，修改预算比例或提示文本时要确认模型仍能看到 scoped policy、security、validation、command 等关键约束。

第五，thinking fallback 要记录已尝试集合。没有 `attempted` 保护时，unsupported reasoning level 容易在 fallback 链里重复尝试，造成无意义重试甚至循环。

## 推荐阅读顺序

1. 先读 `src/agents/pi-embedded-helpers/types.ts`，了解目录共享的数据形态。
2. 再读 `src/agents/pi-embedded-helpers/bootstrap.ts`，掌握上下文注入、预算和 `AGENTS.md` 摘要。
3. 读 `src/agents/pi-embedded-helpers/images.ts`，理解历史消息进入 provider 前如何被规范化。
4. 读 `src/agents/pi-embedded-helpers/errors.ts`、`src/agents/pi-embedded-helpers/provider-error-patterns.ts`、`src/agents/pi-embedded-helpers/failover-matches.ts`，建立错误分类到 fallback 的整体图。
5. 读 `src/agents/pi-embedded-helpers/thinking.ts`、`src/agents/pi-embedded-helpers/openai.ts`、`src/agents/pi-embedded-helpers/google.ts`，补齐 provider 特定约束。
6. 最后查看同目录 `*.test.ts`，重点看测试名和边界样例，而不是逐行看实现。测试能说明哪些字符串、provider 响应和消息结构已经被当作稳定兼容契约。
