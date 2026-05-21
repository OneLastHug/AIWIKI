# 目录：src/server/routers/async

## 它负责什么

`src/server/routers/async` 是 LobeHub 服务端的“异步任务 TRPC 路由层”。它不直接面向普通页面交互的即时请求，而是承接那些耗时较长、需要后台执行并写回任务状态的工作，例如：

- 文件解析成 chunks：`file.parseFileToChunks`
- 文件 chunks 生成 embedding：`file.embeddingChunks`
- 图片生成后的下载、转存、资产落库、计费：`image.createImage`
- 视频生成后的轮询、转存、资产落库、计费或退款：`video.createVideo`
- RAG 评测记录执行：`ragEval.runRecordEvaluation`

这个目录的核心职责可以概括为：**把“已经创建好的异步任务”真正执行完，并把结果、错误、耗时和相关资产写回数据库**。

它和普通业务 router 的区别在于：这里的 procedure 大多会显式更新 `AsyncTaskStatus.Processing`、`AsyncTaskStatus.Success`、`AsyncTaskStatus.Error`，并且普遍带有超时、错误归类、资源转存、模型运行时调用等后台任务逻辑。

## 关键组成

`index.ts` 是聚合入口：

```ts
export const asyncRouter = router({
  document: documentRouter,
  file: fileRouter,
  healthcheck: publicProcedure.query(() => "i'm live!"),
  image: imageRouter,
  ragEval: ragEvalRouter,
  video: videoRouter,
});
```

它从 `@/libs/trpc/async` 引入 `asyncRouter as router` 和 `publicProcedure`，然后把各个子 router 组合成最终的 `asyncRouter`。同时导出：

- `AsyncRouter`：整个 async router 的类型
- `UnifiedAsyncCaller`：异步调用器类型
- `createAsyncCaller`
- `createAsyncServerClient`

`caller.ts` 是服务端内部调用 async router 的封装。它做了两层事情：

1. `createAsyncServerClient(userId)` 创建一个 TRPC HTTP client，目标地址是 `appEnv.INTERNAL_APP_URL + /trpc/async`。
2. `createAsyncCaller({ userId })` 用 `Proxy` 包装 HTTP client，让调用方可以写成类似 `caller.file.parseFileToChunks(...)` 的形式。

这里有几个重要细节：

- 它通过 `signInternalJWT()` 生成内部调用的 `Authorization`。
- 它用 `KeyVaultsGateKeeper` 加密 `{ userId }`，写入 `LOBE_CHAT_AUTH_HEADER`。
- 如果存在 `VERCEL_AUTOMATION_BYPASS_SECRET`，会额外加 `x-vercel-protection-bypass`，用于绕过 Vercel protection。
- `createAsyncCaller` 的 Proxy 最终只调用目标 procedure 的 `.mutate(...)`，所以它主要服务 mutation 型异步任务。`healthcheck` 虽然是 query，但并不是这个 caller 的典型目标。

`file.ts` 是知识库文件处理的核心。它定义了 `fileProcedure`，在 `asyncAuthedProcedure` 的上下文里注入：

- `AsyncTaskModel`
- `ChunkModel`
- `ChunkService`
- `DocumentService`
- `EmbeddingModel`
- `FileModel`
- `FileService`

`fileRouter` 暴露两个 mutation：

- `parseFileToChunks`
- `embeddingChunks`

`parseFileToChunks` 的流程是：查文件、跳过 `internal://` 内联文档、从文件服务读取二进制内容、更新异步任务为 `Processing`、尝试生成 document 记录、调用 `chunkService.chunkContent` 分块、写入 chunks、必要时写入 unstructured chunks、更新任务为 `Success`，如果开启 `fileEnv.CHUNKS_AUTO_EMBEDDING`，再触发 `chunkService.asyncEmbeddingFileChunks`。

`embeddingChunks` 的流程是：查文件和异步任务、读取默认 embedding model/provider、把 chunks 按 `fileEnv.EMBEDDING_BATCH_SIZE` 分批，用 `p-map` 按 `fileEnv.EMBEDDING_CONCURRENCY` 并发调用模型 embedding，最后批量写入 `EmbeddingModel` 并把任务标记为成功。

`image.ts` 是图片生成的后台落地逻辑。它定义 `imageProcedure`，注入：

- `AsyncTaskModel`
- `FileModel`
- `GenerationModel`
- `GenerationBatchModel`
- `GenerationService`

核心 mutation 是 `createImage`。输入包括 `taskId`、`generationId`、`generationBatchId`、`generationTopicId`、`provider`、`model` 和图片生成参数 `params`。它会：

- 检查 `generationBatch` 是否存在
- 更新异步任务为 `Processing`
- 解析业务模型映射：`resolveBusinessModelMapping`
- 通过 `initModelRuntimeFromDB` 初始化用户的 provider runtime
- 调用 `modelRuntime.createImage`
- 下载或转换图片：`generationService.transformImageForGeneration`
- 上传图片和缩略图：`uploadImageForGeneration`
- 创建 generation asset 和 file：`generationModel.createAssetAndFile`
- 更新异步任务为 `Success`
- 尝试发送完成通知：`notifyImageCompleted`
- 在商业功能开启时调用 `chargeAfterGenerate`

它还包含较完整的错误归类函数 `categorizeError`，会把 ComfyUI、API key、模型不存在、内容审核、超时、网络错误等转换成 `AsyncTaskErrorType`。

`video.ts` 是视频生成的后台轮询和落地逻辑。它定义 `videoProcedure`，注入：

- `AsyncTaskModel`
- `GenerationModel`
- `VideoGenerationService`

核心 mutation 是 `createVideo`。输入里比较关键的是 `inferenceId`，说明视频生成请求可能已经由上游发起，这里负责后台轮询结果。`pollUntilCompletion` 每 5 秒轮询一次，最多 120 次。成功后会：

- 调用 `videoService.processVideoForGeneration` 下载、处理视频、封面和缩略图
- 读取 `generationBatch`
- 调用 `generationModel.createAssetAndFile` 创建视频 asset 和 file
- 更新异步任务为 `Success`
- 商业功能开启时进行生成后计费

失败时会尝试读取 provider 内容政策错误信息，并把任务更新为 `Error`。如果存在 `prechargeResult`，还会在失败分支调用 `chargeAfterGenerate({ isError: true })` 进行退款或冲正逻辑。

`ragEval.ts` 是 RAG 评测任务执行器。它注入：

- `ChunkModel`
- `ChunkService`
- `EvalDatasetRecordModel`
- `EvalEvaluationModel`
- `EvaluationRecordModel`
- `EmbeddingModel`
- `FileModel`

核心 mutation 是 `runRecordEvaluation`。它根据 `evalRecordId` 找到评测记录，然后：

- 如缺少问题 embedding，则调用 OpenAI provider 生成 embedding 并保存
- 如缺少 context，则基于参考文件做语义检索
- 用 `chainAnswerWithContext` 构造带上下文的问题
- 调用模型生成 JSON 模式回答
- 更新评测记录为 `Success`
- 出错时更新评测记录和评测任务为 `Error`

`document.ts` 目前是空 router，只保留结构：

```ts
export const documentRouter = router({
  // Document history compaction is no longer needed with the simplified history schema
});
```

这说明历史上可能有 document 相关异步任务，但当前简化后已经不需要实际 procedure。

`contentPolicyError.ts` 是图片生成错误处理的辅助模块。它把一些 provider 返回的错误码或错误消息识别为内容政策错误，例如：

- `InputTextSensitiveContentDetected`
- `content_policy_violation`
- `moderation_blocked`
- message 中包含 `content policy`
- message 中包含 `safety system`
- message 中包含 `sensitive information`

匹配时返回统一文案：`Content policy check failed. Revise your prompt and try again.`

测试文件包括：

- `__tests__/caller.test.ts`
- `__tests__/file.test.ts`
- `contentPolicyError.test.ts`

其中 `caller.test.ts` 重点覆盖 `createAsyncServerClient` 的 URL、header、加密和 Vercel bypass 行为；`file.test.ts` 覆盖文件异步处理；`contentPolicyError.test.ts` 覆盖内容政策错误识别。

## 上下游关系

上游入口主要有两类。

第一类是 Next.js TRPC route：

`src/app/(backend)/trpc/async/[trpc]/route.ts`

它把 HTTP 请求挂到 `/trpc/async`，并使用 `asyncRouter` 作为实际 router。也就是说，`src/server/routers/async/index.ts` 只是 router 定义，真正暴露 HTTP 端点的是 App Router 里的 route 文件。

第二类是服务端业务模块通过 `createAsyncCaller` 发起内部调用。搜索结果显示典型调用方包括：

- `src/server/services/chunk/index.ts`
- `src/server/routers/lambda/ragEval.ts`
- `src/server/routers/lambda/image/index.ts`

根据当前片段推断，lambda router 或 service 通常负责创建任务、保存初始记录、返回给前端；真正耗时的处理则通过 `createAsyncCaller` 调用 `/trpc/async` 下的 mutation 执行。

下游依赖主要分为几组。

数据库模型层：

- `AsyncTaskModel`：异步任务状态、耗时、错误写回
- `FileModel`：文件元数据读取
- `ChunkModel`：chunks 读取和写入
- `EmbeddingModel`：embedding 写入和查询
- `GenerationModel`：图片/视频 asset 与 file 绑定
- `GenerationBatchModel`：生成批次读取
- `EvalDatasetRecordModel`、`EvalEvaluationModel`、`EvaluationRecordModel`：RAG 评测相关数据

服务层：

- `ChunkService`
- `DocumentService`
- `FileService`
- `GenerationService`
- `VideoGenerationService`

模型运行时：

- `initModelRuntimeFromDB`
- `modelRuntime.embeddings`
- `modelRuntime.chat`
- `modelRuntime.createImage`
- `modelRuntime.handlePollVideoStatus`

业务中间件和商业逻辑：

- `checkEmbeddingUsage`
- `createImageBusinessMiddleware`
- `chargeAfterGenerate`
- `notifyImageCompleted`
- `getProviderContentPolicyErrorMessage`
- `resolveBusinessModelMapping`
- `buildMappedBusinessModelFields`

配置和环境变量：

- `ASYNC_TASK_TIMEOUT`
- `fileEnv.EMBEDDING_BATCH_SIZE`
- `fileEnv.EMBEDDING_CONCURRENCY`
- `fileEnv.CHUNKS_AUTO_EMBEDDING`
- `appEnv.INTERNAL_APP_URL`
- `VERCEL_AUTOMATION_BYPASS_SECRET`

## 运行/调用流程

一个典型的文件解析流程大致是：

1. 上游业务创建 `AsyncTask`，拿到 `taskId`。
2. 上游通过 `createAsyncCaller({ userId })` 创建内部 caller。
3. 调用 `caller.file.parseFileToChunks({ fileId, taskId })`。
4. `caller.ts` 把这个调用转换成对 `/trpc/async/file.parseFileToChunks` 的 HTTP mutation。
5. async route context 从内部 JWT 和加密 header 里恢复调用身份。
6. `fileProcedure` 注入各种 model/service。
7. `parseFileToChunks` 把任务置为 `Processing`。
8. 读取文件内容，解析 document，执行 chunk。
9. 写入 chunks 和 unstructured chunks。
10. 把任务置为 `Success`；如失败则写入 `AsyncTaskError` 并置为 `Error`。
11. 如果开启自动 embedding，再触发 embedding 异步任务。

图片生成流程类似，但上游通常已经有 generation batch 和 generation 记录。`image.createImage` 负责调用模型生成图片，然后把 provider 返回的图片统一下载、转存、生成缩略图、写入资产表和文件表，最后更新任务状态并处理通知和计费。

视频生成稍有不同：它不是直接发起生成，而是根据 `inferenceId` 轮询 provider 的视频生成状态。轮询成功后才进入视频下载、处理、资产落库流程。这个设计说明视频生成的第一阶段很可能在上游 router 中完成，而 async router 承担“等待结果并落库”的后台职责。

RAG 评测流程则以 `evalRecordId` 为中心。它补齐问题 embedding、检索上下文、调用语言模型回答，再写回单条评测记录状态。它不使用 `AsyncTaskStatus`，而是使用 `EvalEvaluationStatus`。

所有长任务都围绕“开始时置为处理中，结束时置为成功，异常时置为错误”的模式展开。`file` 用 `Promise.race` 对任务逻辑和 timeout promise 做竞争；`image` 和 `video` 用 `AbortController` 在超时时中止后续流程。

## 小白阅读顺序

1. 先读 `index.ts`  
   理解 async router 暴露了哪些模块：`document`、`file`、`image`、`ragEval`、`video`、`healthcheck`。

2. 再读 `caller.ts`  
   重点看 `createAsyncServerClient` 和 `createAsyncCaller`。这是理解“为什么服务端内部还要通过 HTTP 调自己”的关键。这里的 `INTERNAL_APP_URL`、内部 JWT、加密用户 header 都很重要。

3. 接着读 `file.ts`  
   这是最适合理解异步任务状态机的文件。先看 `fileProcedure` 如何注入上下文，再看 `parseFileToChunks`，最后看 `embeddingChunks`。

4. 然后读 `image.ts`  
   关注 `createImageInputSchema`、`createImage`、`categorizeError`。这个文件能帮助你理解模型 runtime、生成资产、内容审核错误、计费之间的关系。

5. 再读 `video.ts`  
   对比图片生成。视频逻辑的核心是 `pollUntilCompletion`，它体现了异步轮询型任务和一次性生成型任务的差异。

6. 最后读 `ragEval.ts` 和 `contentPolicyError.ts`  
   `ragEval.ts` 展示 async router 不只服务文件和媒体，也服务评测任务；`contentPolicyError.ts` 是一个小而独立的错误归类工具。

7. 有余力再看调用方  
   推荐看 `src/server/services/chunk/index.ts`、`src/server/routers/lambda/image/index.ts`、`src/server/routers/lambda/ragEval.ts`。它们能帮助你理解 async router 是如何被触发的。

## 常见误区

1. 误以为 `asyncRouter` 会自己后台运行  
   它本质上仍然是 TRPC router。后台执行来自上游调用 `/trpc/async`，不是目录里的代码自动调度。

2. 误以为 `createAsyncCaller` 是本地函数调用  
   它不是直接 `createCaller` 执行 router，而是创建 TRPC HTTP client，发请求到 `INTERNAL_APP_URL/trpc/async`。这使它更像服务端到服务端的内部 HTTP 调用。

3. 误以为所有 async procedure 都支持 query  
   `createAsyncCaller` 的 Proxy 最终查找 `.mutate` 并执行，因此主要服务 mutation。`healthcheck` 是 `publicProcedure.query`，但不是这个 caller 封装的主要使用场景。

4. 误以为文件解析失败会删除文件记录  
   `parseFileToChunks` 中遇到存储 `NoSuchKey` 时明确不会删除 file row，而是把任务标记为错误。注释说明这是为了避免 S3 短暂故障、IAM 配置问题或孤儿记录导致级联删除。

5. 误以为内联文档也会走 chunking  
   `file.url.startsWith('internal://')` 的内联文档会被跳过，任务会被标记为错误并返回 skipped 信息。注释说明这类内容通过 BM25 搜索，不需要 chunking。

6. 误以为图片和视频生成只负责调用模型  
   `image.createImage` 和 `video.createVideo` 的职责远不止模型调用。它们还负责下载、转换、上传、创建 asset/file、更新任务状态、通知、计费或退款。

7. 误以为 timeout 一定能停止所有外部请求  
   `file.ts` 使用 `Promise.race`，超时后会返回错误路径，但底层已经发出的异步工作未必被真正取消。`image.ts` 和 `video.ts` 使用 `AbortController`，取消语义更明确，但仍取决于下游操作是否检查 `signal`。

8. 误以为所有错误都直接暴露给用户  
   图片和视频会把 provider 错误转换成 `AsyncTaskErrorType`，尤其是内容审核、API key、模型不存在、服务错误、超时等。前端或上层通常应基于错误类型做展示，而不是只依赖原始错误文本。

9. 误以为 `documentRouter` 漏实现了功能  
   当前 `document.ts` 明确注释“Document history compaction is no longer needed with the simplified history schema”。根据当前片段推断，它是保留命名空间兼容或未来扩展用的空 router，而不是未完成的主要逻辑。
