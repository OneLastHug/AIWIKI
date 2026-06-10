# 文件：packages/desktop/src/common/adapter/httpBridge.ts
## 一句话定位
这是桌面端“桥接适配层”的底座，把原本依赖 `@office-ai/platform` 的 bridge 调用，统一转换成 HTTP REST 和 WebSocket 调用；对上尽量保持同样的 `provider / invoke / on / emit` 形状，对下直接对接后端 `aioncore`。根据当前片段推断，它是 `ipcBridge.ts` 的核心依赖，也是 renderer、process 两端共享的网络入口。

## 它暴露/定义了什么
这个文件主要暴露三类能力：一是基础连接能力，如 `getBaseUrl()`、内部的 WebSocket 地址解析；二是错误与请求封装，如 `BackendHttpError`、`isBackendHttpError()`、`httpRequest()`；三是适配器工厂，如 `httpGet`、`httpPost`、`httpPut`、`httpPatch`、`httpDelete`、`withResponseMap`、`wsEmitter`、`wsMappedEmitter`、`stubProvider`、`stubEmitter`。这些接口的目标不是做完整业务逻辑，而是让上层模块用统一方式访问后端。

## 谁调用它
从调用面看，`ipcBridge.ts` 大量复用这里的工厂函数来拼出各类 API：`assistants`、`conversation`、`shell` 等。除此之外，`configMigration.ts`、`runBackendMigrations.ts`、`webuiConfig.ts`、`closeToTraySetting.ts`、`catalog.ts`、`useMcpConnection.ts`、`previewError.ts`、`platform.ts`、`FileService.ts` 等也直接依赖它。根据当前片段推断，这说明它既服务渲染层，也服务主进程中的一些启动和迁移逻辑。

## 它调用谁
它主要调用浏览器/运行时原生能力：`fetch`、`WebSocket`、`console`、`setTimeout`、`JSON`、`window`、`globalThis`。它不直接依赖业务模块，只有在上层通过工厂函数传入路径、body 映射函数和数据转换器时，才间接参与业务流程。

## 核心流程
核心流程分两条线。HTTP 线先通过 `getBaseUrl()` 和 `getBackendPort()` 解析地址，再由 `httpRequest()` 发起请求；失败时解析错误体，打印日志，并抛出结构化的 `BackendHttpError`；成功时自动解包后端常见的 `{ success, data }` 包装。WebSocket 线则由 `ensureWs()` 维护单例连接、自动重连和消息分发，`wsEmitter()` 负责订阅事件，`wsMappedEmitter()` 负责把原始消息转换成上层需要的类型。

## 关键函数的高层作用
`httpRequest()` 是最核心的通用请求入口，决定了日志、错误处理、JSON 解包和静默状态码策略。`BackendHttpError` 让上层能按 `status`、`code`、`details` 做分支，而不是只看字符串。`withResponseMap()` 负责把后端原始返回映射成前端模型，是连接 API 和领域对象的转换层。`stubProvider()`、`stubEmitter()` 则提供占位实现，避免尚未落地的后端能力阻断前端编译或运行。

## 修改风险
这个文件是横向复用点，改动会扩散到很多页面和进程。最大风险有三类：一是 base URL 或 WS URL 解析错误，会导致 WebUI、Electron renderer、主进程三种运行模式中的某一种失联；二是 `httpRequest()` 的错误体结构变化，会影响大量依赖 `isBackendHttpError()` 的分支判断；三是 WebSocket 重连、事件名、消息体字段一旦变动，会让多个订阅点表现为“能连上但收不到数据”。此外，它还承担日志脱敏，若 `redactForLog()` 规则收紧或放宽过头，都可能带来信息泄露或排障困难。
