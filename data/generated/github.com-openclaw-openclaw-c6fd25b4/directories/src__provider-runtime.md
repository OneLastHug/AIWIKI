# 目录：src/provider-runtime

## 它负责什么

`src/provider-runtime` 是 provider 调用运行期的共享小目录，目前只承载一类能力：provider 操作的瞬时错误重试策略。它不负责具体 provider 的鉴权、HTTP 请求组装、媒体理解业务逻辑，也不直接实现某个模型厂商 API；它提供的是跨 provider 可复用的“同一个操作是否应该重试、重试几次、间隔多久、哪些阶段默认启用”的基础规则。

当前目录的核心文件是 `src/provider-runtime/operation-retry.ts`。从导出看，它围绕 `ProviderOperationRetryStage`、`TransientProviderRetryConfig`、`TransientProviderRetryOptions`、`executeProviderOperationWithRetry` 组织。调用方可以把一次 provider 操作包装成 `operation: () => Promise<T>`，并声明阶段 `read`、`poll`、`download` 或 `create`。目录内逻辑会判断错误是否属于临时失败，例如 500/502/503/504、网络瞬断、超时类错误，然后用指数退避再次执行。

它的定位偏“运行期策略层”：上游业务只关心“我在读、轮询、下载或创建 provider 资源”，这里负责把可重试错误和不可重试错误分开，避免把 400、401、403、404、invalid api key、permission denied、model not found、validation、unsupported model 这类确定性失败误判为瞬时失败。

## 直接子目录地图

当前 `src/provider-runtime` 没有直接子目录，只有一个文件：

`src/provider-runtime/operation-retry.ts`：provider 操作重试策略的唯一实现文件，包含类型定义、默认配置、错误分类、延迟计算、重试决策和通用执行包装器。

根据当前片段推断，这个目录未来可能用于继续收纳 provider 运行期通用机制，例如限流、超时、调度或执行上下文，但当前仓库片段里尚未出现这些拆分；依据是目录名比现有文件职责更宽，而实际文件列表只有 `operation-retry.ts`。

## 关键入口

最重要的入口是 `executeProviderOperationWithRetry`。调用方传入 `provider`、`stage`、`operation` 和可选 `retry`。函数内部先通过 `providerOperationRetryConfig` 得到阶段默认策略，再用 `resolveTransientProviderRetryOptions` 解析成具体选项，随后循环执行 operation。失败时，它会用 `formatErrorMessage` 取错误文本，再调用 `shouldRetrySameKeyProviderOperation` 判断是否继续。如果继续，则用 `resolveTransientProviderDelayMs` 算出退避时间，并通过 `sleepWithAbort` 或调用方注入的 `sleep` 等待。

第二组入口是策略解析函数：`defaultTransientProviderRetryForStage`、`providerOperationRetryConfig`、`resolveTransientProviderRetryOptions`、`resolveTransientProviderAttempts`、`resolveTransientProviderDelayMs`。它们决定默认是否重试、最多执行几次、延迟如何增长。当前默认配置是 `attempts: 2`、`baseDelayMs: 250`、`maxDelayMs: 1000`。其中 `create` 阶段默认不重试，其他阶段默认重试；这很关键，因为创建类请求可能产生计费任务或远端副作用。

第三组入口是错误判断函数：`isTransientProviderOperationError` 和 `shouldRetrySameKeyProviderOperation`。前者判断错误是否瞬时，后者在前者基础上叠加最大尝试次数、abort signal、自定义 `shouldRetry` 等条件。

## 主流程位置

主流程可以从 `src/plugin-sdk/provider-http.ts` 看起。这个文件把 `executeProviderOperationWithRetry` 和相关类型重新导出给 plugin SDK，同时也导出 provider HTTP 相关工具。也就是说，插件或 provider-facing 代码通常不会直接把 `src/provider-runtime` 当业务入口，而是通过 `openclaw/plugin-sdk/provider-http` 这一层拿到能力。

实际 HTTP 调用主流程在 `src/media-understanding/shared.ts`。`fetchProviderOperationResponse` 会把普通 provider HTTP 请求包装进 `executeProviderOperationWithRetry`，阶段由调用方传入。`fetchProviderDownloadResponse` 固定把阶段设为 `download`。`pollProviderOperationJson` 的轮询读取会间接走 `fetchProviderOperationResponse` 或 guarded fetch 分支，并使用 `poll` 阶段。`postGuardedRequest` 里也能看到一个重要边界：POST 默认不重试，只有调用方显式传入 `retryStage` 才会包装重试；注释说明原因是很多 provider 端点会创建可计费任务。

另一个重要使用点是 `src/agents/api-key-rotation.ts`。这里不是直接调用 `executeProviderOperationWithRetry`，而是复用 `resolveTransientProviderRetryOptions`、`resolveTransientProviderAttempts`、`resolveTransientProviderDelayMs` 和 `shouldRetrySameKeyProviderOperation`，把“同一 key 的瞬时错误重试”和“API key 限流后的换 key”组合起来。也就是说，`src/provider-runtime` 的策略不只服务单次 HTTP 包装器，也服务更高层的 provider key 轮换执行器。

`src/media-understanding/runner.entries.ts` 使用 `providerOperationRetryConfig("read")` 将读取类默认重试策略传入媒体理解 provider 入口。根据当前片段推断，媒体理解的图片、音频、视频等 provider 调用会共享这套瞬时重试语义；依据是 `src/media-understanding/shared.ts` 集中了 transcription、download、poll、guarded fetch 等 provider HTTP 工具，并导入了该目录的 retry 类型与执行器。

## 推荐阅读顺序

1. 先读 `src/provider-runtime/operation-retry.ts` 顶部类型：理解 `ProviderOperationRetryStage`、`TransientProviderRetryConfig` 和默认配置，尤其注意 `create` 阶段默认不重试。

2. 再读同文件的错误分类：`readErrorStatus`、`hasTransientNetworkSignal`、`hasTimeoutSignal`、`isTransientProviderOperationError`。这一段决定哪些错误会被认为是临时 provider 故障。

3. 接着读执行包装器：`shouldRetrySameKeyProviderOperation` 和 `executeProviderOperationWithRetry`。这里能看到最大尝试次数、abort signal、自定义 `shouldRetry`、指数退避和最终抛错的完整闭环。

4. 然后读 `src/plugin-sdk/provider-http.ts`，确认该能力如何暴露给 SDK 层。这个文件更像“出口地图”，能帮助理解 provider runtime 为什么放在 core 内部但又被 SDK-facing helper 复用。

5. 最后读 `src/media-understanding/shared.ts` 和 `src/agents/api-key-rotation.ts`。前者展示 HTTP read/poll/download/create-like 请求如何接入重试，后者展示 API key 轮换如何复用同一套瞬时重试判断。

## 常见误区

不要把 `src/provider-runtime` 理解成完整 provider 框架。它当前不管理 provider 注册表、不解析模型配置、不处理鉴权，也不做请求头、proxy、SSRF、防护策略组装；这些分别在 `src/media-understanding`、`src/agents/provider-request-config.ts`、`src/agents/model-auth.js` 以及 SDK HTTP helper 周边完成。

不要以为所有 provider 请求都会自动重试。`defaultTransientProviderRetryForStage` 明确让 `create` 默认不重试，POST helper 也要求显式传入 `retryStage` 才会重试。这是为了避免重复创建远端任务、重复计费或重复产生副作用。

不要把“失败后换 API key”和“同 key 瞬时重试”混在一起。`src/provider-runtime/operation-retry.ts` 只定义同一次 provider 操作的瞬时失败重试规则；`src/agents/api-key-rotation.ts` 才负责在限流等情况下切换 key，并且只是复用这里的判断与退避工具。

不要把所有 `fetch failed` 都当成可重试。`isTransientProviderOperationError` 对 `fetch failed` 会继续检查是否有 `ECONNRESET`、`ECONNREFUSED`、`ETIMEDOUT`、`EAI_AGAIN` 等瞬时网络信号。缺少这些信号时，它不会盲目重试。

不要在阅读时忽略 `signal` 和 `sleep`。`TransientProviderRetryOptions` 允许传入 `AbortSignal` 和自定义 `sleep`，这让测试和上层取消逻辑可以控制等待行为。实际执行中，如果 signal 已 abort，`shouldRetrySameKeyProviderOperation` 会停止重试。
