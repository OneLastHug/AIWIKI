# 文件：agent/error_classifier.py

## 一句话定位

`agent/error_classifier.py` 是 Hermes Agent 的 API 调用失败分类中枢：它把各类 SDK 异常、HTTP 状态码、错误 body、错误文本统一归类为 `FailoverReason`，并给主对话重试循环提供“是否重试、是否压缩上下文、是否切换凭据、是否 fallback”的结构化决策。

## 它暴露/定义了什么

这个文件主要定义三类内容。第一是 `FailoverReason` 枚举，覆盖认证、计费、限流、服务端错误、超时、上下文溢出、payload/image 过大、模型不存在、内容策略拦截、请求格式错误，以及若干 provider-specific 恢复场景。第二是 `ClassifiedError` dataclass，封装分类结果、HTTP 状态、provider/model、可读消息和恢复 hint。第三是公开入口 `classify_api_error()`，这是外部真正调用的分类函数。其余 `_classify_by_status()`、`_classify_400()`、`_classify_by_message()`、`_extract_*()` 等都是内部辅助函数。

## 谁调用它

直接调用 `classify_api_error()` 的核心位置是 `agent/conversation_loop.py`。在模型 API 调用抛出异常后，对话循环会把异常、当前 provider、model、估算 token 数、上下文长度、消息数传入分类器，然后根据 `ClassifiedError` 决定后续恢复路径。

`FailoverReason` 还被多个运行时模块引用：`run_agent.py` 暴露或转用该枚举；`agent/agent_runtime_helpers.py` 的 `recover_with_credential_pool()` 根据分类后的 reason 做凭据池轮换；`agent/chat_completion_helpers.py` 的 `try_activate_fallback()` 根据限流/计费类 reason 给主 provider 设置 cooldown 并切换 fallback。测试侧大量覆盖在 `tests/agent/test_error_classifier.py` 以及若干 `tests/run_agent/*` 回归测试中。

## 它调用谁

这个文件基本不依赖 Hermes 其他业务模块，属于底层纯分类逻辑。它调用 Python 标准库的 `enum`、`logging`、`dataclasses`、`typing`，并在需要解析嵌套错误 body 或 OpenRouter metadata raw 时局部导入 `json`。它不会直接执行重试、压缩、fallback、刷新 token 或改写消息，这些动作都由 `agent/conversation_loop.py` 和 runtime helper 根据分类结果完成。

## 核心流程

`classify_api_error()` 的流程是优先级管线，而不是简单状态码表。它先从异常链中提取 `status_code`，兼容 `.status_code`、`.status` 和 cause/context 链；再提取 structured body 和 error code；随后把 `str(error)`、body 中的 `error.message`、以及部分 provider 包裹的 `metadata.raw` 合并成小写 `error_msg` 用于模式匹配。

分类顺序很关键：先处理内容安全拦截、Anthropic thinking signature、long context tier、OAuth 1M beta 禁用、llama.cpp grammar、xAI Grok entitlement 等特殊场景；再按 HTTP status 分类；再按结构化 error code 分类；再按文本模式分类；最后处理 SSL/TLS 临时错误、server disconnect 与大上下文的组合、通用 transport timeout，兜底为 `unknown` 且可重试。

结果通过内部 `_result()` 构造，统一带上 `reason`、`status_code`、`provider`、`model`、可读 `message`，并按分类设置 `retryable`、`should_compress`、`should_rotate_credential`、`should_fallback`。

## 关键函数的高层作用

`classify_api_error()` 是唯一应被外部使用的入口，负责收集异常上下文并按优先级返回 `ClassifiedError`。

`_classify_by_status()` 处理 HTTP 状态码主干：401/403 归 auth 或 billing，402 交给 `_classify_402()` 区分真实欠费与临时 usage limit，404 区分模型不存在、OpenRouter policy block 和普通未知错误，413 触发压缩，429 归限流，400 交给 `_classify_400()`，5xx 多数视为可重试服务端错误。

`_classify_400()` 是风险最高的分支之一，因为很多 provider 把不同问题都塞进 400。它按优先级识别 multimodal tool content 不支持、图片过大、OpenAI Responses encrypted replay 失效、上下文溢出、模型不存在、限流/计费伪装，最后才归为不可重试的 `format_error`。

`_classify_by_message()` 用于无状态码异常，例如 SDK 包装错误、SSE error frame、本地代理错误。它依靠模式列表判断 payload/image/context/auth/rate/billing/model 等问题。

`_extract_status_code()`、`_extract_error_body()`、`_extract_error_code()`、`_extract_message()` 只是防御性提取工具，负责适配不同 SDK 的异常形状。

## 修改风险

最大风险是分类优先级变化。很多模式会互相重叠，例如 “exceeds” 既可能出现在图片过大，也可能出现在上下文溢出；400 既可能是格式错误，也可能是可恢复的 replay、tool content 或 context 问题。把某个分支提前或后移，可能导致主循环走错恢复路径。

第二类风险是 `retryable` 和 hint 设置错误。把 billing、auth、content policy 误标为可重试，会烧请求、刷日志甚至触发循环；把 context overflow、payload too large、long_context_tier 误标为不可重试，会跳过压缩恢复；把 provider policy block 错标为 fallback，可能让用户以为自动切换能解决账号级配置问题。

第三类风险是新增 pattern 过宽。文件里的注释多次强调不要匹配泛化词，例如单独的 “policy” 或 “content filter” 可能误伤正常配置文本。新增 provider 规则时应优先写窄模式，并补充 `tests/agent/test_error_classifier.py` 中的正反例。

第四类风险是与 `agent/conversation_loop.py` 的耦合。新增 `FailoverReason` 如果只在枚举中加入，但没有在主循环、凭据池、fallback 或最终报错路径里处理，可能会退化成普通 retry/abort 行为。修改该文件时应同时检查 `agent/conversation_loop.py`、`agent/agent_runtime_helpers.py`、`agent/chat_completion_helpers.py` 的 reason 分支是否需要同步。
