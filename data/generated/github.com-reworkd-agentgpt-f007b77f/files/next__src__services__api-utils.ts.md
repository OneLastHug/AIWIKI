# 文件：next/src/services/api-utils.ts

## 一句话定位

`next/src/services/api-utils.ts` 是前端服务层访问后端 HTTP API 的轻量工具文件：统一拼接 `NEXT_PUBLIC_BACKEND_URL`、携带 `next-auth` 会话里的 Bearer Token，并为 agent 执行流程提供一个通用重试包装器 `withRetries`。

## 它暴露/定义了什么

该文件主要导出四类能力：

`post<T>(url, body, session?)`：向后端发送 POST 请求，返回 `axios.post(...).data` 并按调用方指定的泛型 `T` 做类型断言。

`get<T>(url, session?)`：向后端发送 GET 请求，行为与 `post` 类似。

`delete_<T>(url, accessToken?)`：向后端发送 DELETE 请求。这里函数名带下划线，是为了避开 JavaScript 关键字 `delete`。

`getHeaders(session?)`：从 `Session` 中读取 `accessToken`，生成 `{ Authorization: "Bearer ..." }` 请求头。

`withRetries(fn, onError, retries = 3)`：执行异步任务，失败后交给 `onError` 判断是否继续重试，最多尝试 `retries + 1` 次。

内部还有 `getUrl(url)`，负责把相对 API 路径拼成完整后端地址：`env.NEXT_PUBLIC_BACKEND_URL + url`。

## 谁调用它

当前片段中直接调用者主要有两个：

`next/src/services/agent/agent-api.ts` 通过 `import * as apiUtils from "../api-utils"` 使用 `apiUtils.post`。`AgentApi` 的 `getInitialTasks`、`getAdditionalTasks`、`analyzeTask` 最终都会走这里，把 agent 的目标、模型设置、任务上下文等提交给 `/api/agent/start`、`/api/agent/create`、`/api/agent/analyze`。

`next/src/services/agent/autonomous-agent.ts` 直接导入 `withRetries`，在 `AutonomousAgent.runWork` 中包裹每个 `AgentWork` 的执行过程。也就是说，agent 自动运行、总结、聊天等工作单元遇到可重试错误时，重试逻辑由本文件提供。

根据当前片段推断，`get` 和 `delete_` 是为同一服务层风格预留或被其他未检索范围使用；在已检索的 `next/src` 片段里没有发现直接调用。

## 它调用谁

它直接依赖三个外部/邻近模块：

`axios`：实际 HTTP 客户端，`post`、`get`、`delete_` 都只是对 `axios` 的薄封装。

`next-auth` 的 `Session` 类型：用于静态描述会话对象，尤其是项目扩展出的 `session.accessToken` 字段。

`next/src/env/client.mjs` 导出的 `env`：提供客户端环境变量，并在 `getUrl` 中读取 `NEXT_PUBLIC_BACKEND_URL`。环境变量校验逻辑在 `client.mjs` 内完成，本文件只消费结果。

`withRetries` 本身不关心具体错误类型。是否可重试由调用方传入的 `onError` 决定；在 `autonomous-agent.ts` 中，这个判断进一步交给 `next/src/types/errors.ts` 的 `isRetryableError`。

## 核心流程

HTTP 请求流程很短：调用方传入相对路径，例如 `/api/agent/start`；工具函数先调用 `getHeaders(session)`，如果当前用户会话存在 `accessToken`，就生成 Bearer 认证头；随后调用 `getUrl(url)`，把相对路径拼到 `NEXT_PUBLIC_BACKEND_URL` 后面；最后使用 `axios` 发送请求，并只把响应体 `data` 返回给上层。

在 agent 场景中，链路大致是：`next/src/pages/index.tsx` 创建 `AgentApi` 和 `AutonomousAgent`；`AutonomousAgent` 执行 `AgentWork`；具体工作通过 `AgentApi` 请求后端 agent API；`AgentApi` 的私有 `post` 方法补齐 `goal`、`model_settings`、`run_id` 后调用 `apiUtils.post`；后端返回数据和 `run_id`，`AgentApi` 保存首个 `run_id` 以维持同一次 agent 运行上下文。

重试流程则是：`AutonomousAgent.runWork` 把 `work.run()` 作为 `fn` 传给 `withRetries`；如果抛错，`withRetries` 调用 `onError(error)`；调用方根据错误类型决定是否停止 agent、等待 2 秒、继续重试或直接结束。

## 关键函数的高层作用

`post` 是最关键的请求函数，因为当前 agent 的任务启动、任务扩展、任务分析都走 POST。它不处理业务错误，也不改写响应结构，只负责认证头、基础 URL 和响应体解包。

`getHeaders` 是认证边界。它假设 `Session` 上可能有 `accessToken`，并把它转换成后端能识别的 Bearer Token。若未来认证字段改名、token 类型变化或需要额外头信息，这里会影响所有复用该工具的请求。

`getUrl` 是后端地址边界。它把所有传入路径都视为相对后端路径，并直接字符串拼接到 `NEXT_PUBLIC_BACKEND_URL` 后面。因此环境变量末尾是否有斜杠、调用方路径是否以斜杠开头，会共同决定最终 URL 是否正确。

`withRetries` 是通用控制流工具。它不返回业务值，类型固定为 `Promise<void>`，适合包裹“执行一个会产生副作用的异步步骤”。它把“捕获错误、询问是否继续、循环尝试”抽象出来，但退避时间、错误分类、UI 状态变化都留给调用方。

`get` 和 `delete_` 是同风格的 HTTP 辅助函数，目前从已检索上下文看不是 agent 主链路核心。

## 修改风险

认证风险较高。修改 `getHeaders` 或 `Session.accessToken` 的读取方式，会直接影响所有依赖 Bearer Token 的后端请求，可能导致登录用户请求变成未授权请求。

URL 拼接风险较高。`getUrl` 使用简单字符串拼接，没有处理双斜杠、缺斜杠、绝对 URL、查询参数规范化等问题。调整 `NEXT_PUBLIC_BACKEND_URL` 或调用路径格式时，需要同步检查所有调用方。

错误处理风险中等。`post/get/delete_` 不捕获 `axios` 错误，错误会原样向上抛；当前 agent 流程依赖上层 `withRetries` 和 `isRetryableError` 判断。如果在这里吞掉错误、包装错误或只返回空值，可能破坏 `AutonomousAgent.runWork` 的停止与重试逻辑。

重试语义风险中等。`withRetries` 当前最多执行 `retries + 1` 次，且如果 `onError` 返回 `false` 会直接结束，不再抛出最后一次错误。这个行为适合当前 agent 流程，但如果被用于需要向 UI 显示最终失败原因的场景，可能造成失败被静默消费。

类型安全风险中等。HTTP 函数通过 `as T` 断言响应体类型，没有运行时校验；如果后端响应结构变化，TypeScript 不会发现，错误会在业务代码读取字段时才暴露。

命名兼容风险较低但需要注意。`delete_` 的下划线命名是有意规避关键字；重命名为 `delete` 或调整导出方式，可能影响调用方导入习惯和代码可读性。
