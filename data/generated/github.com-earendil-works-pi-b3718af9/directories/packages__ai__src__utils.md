# 子系统：packages/ai/src/utils

## 解决什么问题

`packages/ai/src/utils` 是 `packages/ai` 的通用基础设施层，主要服务于“模型请求、流式响应、工具调用校验、OAuth 登录、错误诊断和运行时兼容”这些横切能力。它不是某个单一 provider 的实现，而是被 `packages/ai/src/providers`、`packages/ai/src/cli.ts`、`packages/ai/src/types.ts` 和测试代码共同复用的一组底层工具。

这个目录解决的核心问题有三类。第一类是请求生命周期：`abort-signals.ts` 合并多个取消信号，`headers.ts` 把 `Headers` 转成普通对象，`node-http-proxy.ts` 根据环境变量解析 HTTP/HTTPS 代理，保证 provider 发请求时可以统一处理超时、取消、响应头和代理。第二类是流式消息与数据修复：`event-stream.ts` 把 provider 产生的增量事件包装成 `AsyncIterable`，最终还能返回完整 `AssistantMessage`；`json-parse.ts` 面向模型流式输出中常见的不完整 JSON、非法转义和控制字符做容错解析；`sanitize-unicode.ts` 处理非法 surrogate，避免跨 provider 或终端输出时出现 Unicode 破损。第三类是面向 AI 语义的辅助判断：`overflow.ts` 识别不同 provider 的上下文溢出错误，`validation.ts` 根据 `typebox` schema 校验并尽量修正工具调用参数，`diagnostics.ts` 把异常整理成可挂在 assistant message 上的诊断信息。

## 相关目录和文件

`packages/ai/src/utils` 本层文件包括 `event-stream.ts`、`validation.ts`、`json-parse.ts`、`overflow.ts`、`diagnostics.ts`、`abort-signals.ts`、`node-http-proxy.ts`、`headers.ts`、`hash.ts`、`sanitize-unicode.ts`、`typebox-helpers.ts`。这些文件大多不直接知道具体模型，只依赖 `packages/ai/src/types.ts` 中的 `AssistantMessage`、`AssistantMessageEvent`、`Tool`、`ToolCall` 等核心类型。

`packages/ai/src/utils/oauth` 是同一目录下较大的子系统，包含 `types.ts`、`index.ts`、`device-code.ts`、`pkce.ts`、`oauth-page.ts`、`anthropic.ts`、`github-copilot.ts`、`openai-codex.ts`。它定义统一的 `OAuthProviderInterface`，并内置 Anthropic、GitHub Copilot、OpenAI Codex 的登录和刷新逻辑。顶层 `packages/ai/src/oauth.ts` 直接 re-export 这个子目录，`packages/ai/src/cli.ts` 则通过 `getOAuthProvider`、`getOAuthProviders` 暴露命令行登录入口。

主要下游在 `packages/ai/src/providers`。例如 `openai-responses.ts`、`azure-openai-responses.ts`、`openai-codex-responses.ts` 使用 `AssistantMessageEventStream` 和 `headersToRecord`；`openai-codex-responses.ts` 还使用 `combineAbortSignals` 和 diagnostics 工具；`faux.ts` 使用 `createAssistantMessageEventStream` 构造测试用流。

## 核心对象

`EventStream<T, R>` 是最基础的异步事件队列。它内部维护事件队列、等待中的 consumer、完成状态和最终结果 Promise。调用方通过 `push()` 放入事件，通过 `for await` 消费事件，通过 `result()` 等待最终结果。`AssistantMessageEventStream` 是它的 AI 专用版本，事件类型是 `AssistantMessageEvent`，最终结果是 `AssistantMessage`，当事件为 `done` 或 `error` 时完成。

`AssistantMessageDiagnostic` 描述一次诊断记录，包含 `type`、`timestamp`、`error` 和 `details`。`createAssistantMessageDiagnostic` 负责从未知 thrown value 中提取结构化错误，`appendAssistantMessageDiagnostic` 则把诊断追加到 message 上，供调用链在失败时保留上下文。

OAuth 子系统的核心对象是 `OAuthProviderInterface`。它描述 provider 的 `id`、展示信息、登录方式、刷新令牌能力、可选的模型匹配关系，以及把 OAuth credentials 转成 API key 的逻辑。`index.ts` 中的 registry 提供 `registerOAuthProvider`、`unregisterOAuthProvider`、`resetOAuthProviders`、`refreshOAuthToken`、`getOAuthApiKey`，让内置和扩展 provider 都走统一入口。

`validateToolCall` 和 `validateToolArguments` 是工具调用边界的关键函数。它们以 `Tool.parameters` 的 `typebox` schema 为依据，先对模型输出的参数做有限的 primitive coercion，再用 `Compile` 后的 validator 校验，并缓存 validator 以减少重复编译。

## 运行流程

典型模型请求从 provider 开始。provider 创建一个 `AssistantMessageEventStream`，初始化 `AssistantMessage`，发出网络请求，然后把上游响应事件转换成本项目统一的 `AssistantMessageEvent`。流开始时通常推入 `start`，中间推入文本、thinking、tool call 或其它增量事件，结束时推入 `done`；如果失败，则把 `stopReason` 置为 `error` 或 `aborted`，再推入 `error`。

在这个过程中，`headersToRecord` 会把原生响应头交给 `onResponse` 回调；`combineAbortSignals` 会把用户取消、内部超时等多个信号合成一个 signal；`parseStreamingJson` 会在工具调用参数还没完整到达时尽可能解析出当前对象；`validateToolArguments` 在工具实际执行前拦截 schema 不匹配的调用；`isContextOverflow` 则可在失败 message 生成后判断是否属于上下文窗口溢出。

OAuth 流程相对独立。CLI 或外部调用者先通过 registry 找到 provider，再调用其 login。浏览器授权类 provider 会生成 PKCE、启动本地 callback server、渲染 `oauthSuccessHtml` 或 `oauthErrorHtml`；设备码类 provider 会用 `pollOAuthDeviceCodeFlow` 按 interval 轮询，处理 `authorization_pending`、`slow_down`、超时和取消。拿到 credentials 后，后续请求可通过 `refreshOAuthToken` 刷新，通过 `getOAuthApiKey` 转换成 provider 实际需要的令牌。

## 上下游依赖

上游类型主要来自 `packages/ai/src/types.ts`，模型信息来自 `packages/ai/src/models.ts`，OAuth 的 GitHub Copilot 实现还会读取 model registry 来关联可用模型。外部依赖包括 `typebox`、`typebox/compile`、`typebox/value`、`partial-json`、`http-proxy-agent`、`https-proxy-agent`，以及运行时的 Web API，如 `AbortController`、`Headers`、`crypto.subtle`、`fetch`。OAuth 的部分实现依赖 Node/Bun 可用的 HTTP server、随机数和浏览器打开能力。

下游主要是 provider 实现、CLI 登录命令、公开类型出口和测试。`packages/ai/src/types.ts` re-export `AssistantMessageEventStream`，说明事件流是包级 API 的一部分，不只是内部实现。`packages/ai/test` 中有针对 OAuth、overflow、validation、proxy、streaming JSON 和 OpenAI Codex stream 的测试，修改 utils 时应优先参考这些测试来判断兼容面。

## 修改时最容易踩的坑

`EventStream.end()` 只有在传入 result 或收到 complete event 时才 resolve final result；如果新增结束路径却没有推入 `done`、`error` 或显式 result，调用 `result()` 的代码可能悬挂。

`json-parse.ts` 的修复逻辑只应该修复模型输出中常见的 JSON 字符串问题，不能把任意非 JSON 语法“猜”成合法对象，否则工具调用参数会被悄悄改写。`parseStreamingJson` 失败时返回空对象，这对 UI 预览友好，但对最终执行前校验不能替代 `validateToolArguments`。

`validation.ts` 会做 primitive coercion，例如字符串数字转 number、字符串布尔值转 boolean。修改这块要注意不要扩大到复杂对象的任意转换，否则模型输出错误会被掩盖。它还用 `WeakMap` 缓存 schema validator，schema 对象身份变化会影响缓存命中。

`overflow.ts` 是 provider 错误文案的集中知识库。新增正则时要同时考虑 `NON_OVERFLOW_PATTERNS`，避免把 rate limit、throttling 这类“不是上下文太长”的错误误判为 overflow。

OAuth 文件中有本地回调端口、state、PKCE、device code interval 和 token refresh 逻辑。修改登录流程时要保持取消、超时和错误页面路径都能关闭 server 或停止轮询；不要在文档、日志或错误中泄露 token。

## 推荐阅读顺序

1. 先读 `packages/ai/src/types.ts`，理解 `AssistantMessage`、`AssistantMessageEvent`、`StreamOptions`、`Tool`、`Model` 的公共契约。
2. 再读 `packages/ai/src/utils/event-stream.ts`，把 provider 如何向外暴露流式结果搞清楚。
3. 接着读 `packages/ai/src/providers/faux.ts`，它用较少外部依赖演示了如何构造 `AssistantMessageEventStream`。
4. 然后读 `packages/ai/src/providers/openai-responses.ts` 或 `packages/ai/src/providers/openai-codex-responses.ts`，观察真实 provider 如何组合 `headers`、abort、diagnostics 和 stream。
5. 工具调用方向读 `packages/ai/src/utils/json-parse.ts`、`packages/ai/src/utils/validation.ts`、`packages/ai/src/utils/typebox-helpers.ts`。
6. 登录认证方向读 `packages/ai/src/utils/oauth/types.ts`、`packages/ai/src/utils/oauth/index.ts`，再按 provider 选择 `openai-codex.ts`、`github-copilot.ts` 或 `anthropic.ts`。
