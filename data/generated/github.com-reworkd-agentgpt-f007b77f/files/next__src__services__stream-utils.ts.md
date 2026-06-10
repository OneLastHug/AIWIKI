# 文件：next/src/services/stream-utils.ts

## 一句话定位

`next/src/services/stream-utils.ts` 是前端调用后端 `text/event-stream` 风格接口的轻量封装，用于把后端连续返回的文本片段读出来，并通过回调实时交给 agent 工作流更新消息内容。

## 它暴露/定义了什么

这个文件对外只暴露一个核心函数：`streamText<T>()`。

它内部还定义了几个辅助结构：

`TextStream`：`ReadableStreamDefaultReader<Uint8Array>` 的类型别名，表示从 `fetch` 响应体上拿到的二进制流读取器。

`fetchData<T>()`：负责拼接后端地址、发起 `POST` 请求、设置鉴权和流式响应头，并返回 `response.body.getReader()`。

`readStream()`：从 reader 读取一个 chunk，把 `Uint8Array` 用 `TextDecoder` 解码成字符串；流结束时返回 `null`。

`processStream()`：循环读取流，调用 `onStart`、`onText`，并在 `shouldClose()` 为真时主动 `reader.cancel()`。

整体看，它没有实现复杂协议解析，也没有处理 SSE 的 `data:` 字段、事件名、重连等语义；它只是把后端响应体作为原始文本流逐块消费。

## 谁调用它

当前检索到的直接调用方有三处，全部位于 agent 工作流层：

`next/src/services/agent/agent-work/execute-task-work.ts` 调用 `streamText()` 请求 `/api/agent/execute`，用于执行单个任务并把后端生成内容持续追加到任务消息 `info`。

`next/src/services/agent/agent-work/chat-work.ts` 调用 `streamText()` 请求 `/api/agent/chat`，用于用户与 agent 对话时流式显示回复。

`next/src/services/agent/agent-work/summarize-work.ts` 调用 `streamText()` 请求 `/api/agent/summarize`，用于基于已完成任务结果生成总结。

这说明该文件是 agent 前端体验里“边生成边显示”的公共基础设施，而不是某个单一业务动作的私有工具。

## 它调用谁

它直接依赖 `next/src/env/client.mjs` 中的 `env.NEXT_PUBLIC_BACKEND_URL`，将调用方传入的相对路径拼成完整后端 URL。

它调用浏览器原生 `fetch()` 发起请求，并使用 `ReadableStream` 相关 API：`response.body?.getReader()`、`reader.read()`、`reader.cancel()`。

请求头中设置了：

`Content-Type: application/json`，表示请求体是 JSON。

`Accept: text/event-stream`，表示期望后端以流式文本方式返回。

`Authorization: Bearer ${accessToken}`，把调用方传入的会话 token 透传给后端。

根据当前片段推断，真正生成文本的是后端服务的 `/api/agent/execute`、`/api/agent/chat`、`/api/agent/summarize` 接口；依据是三个调用方都传入这些路径，而 `stream-utils.ts` 只是把路径拼到 `NEXT_PUBLIC_BACKEND_URL` 后请求。

## 核心流程

调用方先准备业务请求体，例如 `run_id`、`goal`、`task`、`analysis`、`model_settings`、历史任务结果等，然后把请求体、access token 和三个回调传给 `streamText()`。

`streamText()` 调用 `fetchData()`。`fetchData()` 将相对 URL 拼成后端完整地址，发起 `POST`，请求体使用 `JSON.stringify(body)`。如果后端返回 `409`，它会读取 JSON 错误体，并用 `error.detail` 抛出异常；其他非成功状态没有特殊处理。

拿到 reader 后，`streamText()` 进入 `processStream()`。`processStream()` 先执行 `onStart()`，调用方通常在这里把原本的 `"Loading..."` 清空。之后进入无限循环：每轮先检查 `shouldClose()`，如果 agent 生命周期已经变成 `"stopped"`，就取消 reader 并返回；否则读取一个 chunk，读到 `null` 代表流结束，循环退出；读到文本则调用 `onText(text)`。

在三个调用方中，`onText` 的共同模式是把文本追加到 `executionMessage.info`，再通过 `messageService.updateMessage()` 刷新 UI。`ExecuteTaskWork` 还会同步更新任务结果，流结束后保存消息并把任务标记为 `completed`。

## 关键函数的高层作用

`streamText()` 是唯一面向业务层的入口。它屏蔽了 fetch、reader、循环读取、提前关闭等细节，让调用方只需要关心“开始时做什么”“收到文本时做什么”“什么时候应该停止”。

`fetchData()` 是网络边界函数。它决定了所有流式 agent 请求都走同一套后端地址、HTTP 方法、缓存策略、鉴权头和 `Accept` 头。这里的行为变化会影响所有执行、聊天、总结流。

`processStream()` 是流生命周期控制器。它把读取循环和取消逻辑集中在一起，确保调用方可以通过 `shouldClose()` 把前端生命周期变化传递给底层连接。

`readStream()` 只是最小解码器：读取一个二进制 chunk，转成字符串。它不负责拼包、分隔事件或恢复半个字符之外的更高层协议语义。

## 修改风险

最大风险是这个文件的影响面集中但隐蔽：表面只有一个 `streamText()`，实际支撑了 agent 执行任务、聊天、总结三条核心路径。修改请求头、错误处理或读取循环，都可能同时破坏多个用户可见流程。

`fetchData()` 目前只对 `409` 做业务错误解析，其他状态即使是 `401`、`500` 也可能继续尝试读取 `response.body`。如果要增强错误处理，需要确认后端错误响应是否仍可能通过流返回，否则可能改变现有调用方的错误展示路径。

`readStream()` 每次新建 `TextDecoder` 并直接解码单个 chunk。对于普通英文文本通常问题不明显，但如果多字节字符刚好跨 chunk，理论上存在解码边界风险。若改成持久 `TextDecoder` 并使用 streaming decode，需要验证中文、emoji、Markdown 等输出是否保持一致。

`processStream()` 在每次读取前检查 `shouldClose()`，但如果 `reader.read()` 正在等待后端数据，停止信号不会立即中断，必须等下一次循环机会。若要提升停止响应速度，可能需要引入 `AbortController`，但这会改变 `fetchData()`、调用方和取消语义。

`Accept: text/event-stream` 容易让人以为这里完整支持 SSE。实际上当前实现只是原始 chunk 文本拼接。如果后端未来返回标准 SSE 格式，例如 `data: ...\n\n`，这里会把协议字段也交给 `onText()`，调用方显示内容可能异常。修改前应先确认后端真实返回格式。
