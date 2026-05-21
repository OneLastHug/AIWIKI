# 目录：src/server/routers/tools/_helpers

## 它负责什么

这个目录现在只有一个核心职责：**把工具调用结果整理成上报数据，并在响应返回后异步发送到 marketplace 的统计接口**。

从代码形态看，它不是一组通用工具库，而是专门服务于 `src/server/routers/tools/` 下的两条工具调用链路：

- `mcp.ts`
- `market.ts`

它解决的问题很明确：

1. 记录一次 tool call 的耗时。
2. 计算请求和响应的字节大小。
3. 补齐插件/会话/版本等元数据。
4. 在不阻塞主请求的前提下，把埋点上报出去。

`index.ts` 只是一个导出入口，真正的逻辑集中在 `scheduleToolCallReport.ts`。

## 关键组成

### `index.ts`
这是目录级出口：

```ts
export * from './scheduleToolCallReport';
```

作用很简单，让上层可以统一写：

```ts
import { scheduleToolCallReport } from './_helpers';
```

而不用关心具体文件名。

### `scheduleToolCallReport.ts`
这是目录核心文件，主要由三部分构成。

1. `calculateObjectSizeBytes(obj)`
   - 用 `JSON.stringify` 把对象转成字符串。
   - 再用 `TextEncoder` 计算 UTF-8 字节数。
   - 如果对象不可序列化，比如循环引用，就返回 `0`。
   - 这是一个很实用的“近似报文大小”计算方式，不追求精确协议字节，只追求可比较的统计口径。

2. 类型定义
   - `ToolCallReportMeta`
   - `ScheduleToolCallReportParams`

   这两个类型把上报所需输入显式列出来了，能看出它依赖的上下文包括：
   - `identifier`
   - `toolName`
   - `mcpType`
   - `requestPayload`
   - `result`
   - `startTime`
   - `success`
   - `telemetryEnabled`
   - `marketAccessToken`

3. `scheduleToolCallReport(params)`
   - 先判断 `telemetryEnabled` 和 `marketAccessToken`。
   - 条件不满足就直接返回。
   - 满足时调用 Next.js 的 `after()`，把上报放到响应之后执行。
   - 组装 `CallReportRequest`。
   - 通过 `DiscoverService.reportCall()` 真正发送出去。
   - 失败时只记录 `console.error`，不影响主流程。

### `scheduleToolCallReport.test.ts`
这是一个比较完整的单元测试文件，主要验证：

- 普通对象、嵌套对象、数组、字符串、数字、`null` 的字节计算。
- 循环引用对象会返回 `0`。
- telemetry 关闭时不会上报。
- 缺少 `marketAccessToken` 时不会上报。
- `after()` 和 `DiscoverService` 都被 mock 掉，说明它的测试目标是“行为和参数”，不是网络副作用。

## 上下游关系

### 上游是谁

根据当前代码片段推断，这个 helper 的直接调用方只有两个：

- `src/server/routers/tools/mcp.ts`
- `src/server/routers/tools/market.ts`

它们都在各自 mutation 的 `finally` 块里调用 `scheduleToolCallReport()`。

这意味着它不是业务流程里的主逻辑，而是**统一收口的异步统计层**。

### 下游是谁

`scheduleToolCallReport()` 内部会实例化：

- `new DiscoverService({ accessToken: marketAccessToken })`

然后调用：

- `discoverService.reportCall(reportData)`

继续往下看，`DiscoverService.reportCall()` 最终转给：

- `this.market.plugins.reportCall(params)`

也就是说，这个 helper 的最终目标是 **market / plugins 的 reportCall 接口**，它只是中间的适配和调度层。

### 依赖的外部能力

- `next/server` 的 `after()`：保证不阻塞响应。
- `@lobechat/const` 的 `CURRENT_VERSION`：写入应用版本。
- `@lobehub/market-types` 的 `CallReportRequest`：约束上报数据结构。
- `DiscoverService`：负责把数据送到 market SDK。

## 运行/调用流程

1. `mcp.ts` 或 `market.ts` 开始执行工具调用。
2. 记录 `startTime`。
3. 业务逻辑执行成功时拿到 `result`，失败时写入 `errorCode` 和 `errorMessage`。
4. 无论成功失败，`finally` 都会调用 `scheduleToolCallReport()`。
5. helper 先检查：
   - 是否开启 telemetry
   - 是否有 `marketAccessToken`
6. 条件满足后，`after(async () => { ... })` 延后执行上报。
7. 在回调里：
   - 计算 `callDurationMs`
   - 计算 `requestSizeBytes`
   - 成功且有结果时计算 `responseSizeBytes`
   - 组装 `CallReportRequest`
8. 通过 `DiscoverService.reportCall()` 发往 marketplace。
9. 如果上报失败，只打印错误，不影响主请求返回。

这个流程的关键点是：**上报与主请求解耦**。工具调用本身已经结束，统计失败不会回滚业务结果。

## 小白阅读顺序

1. 先看 `src/server/routers/tools/_helpers/index.ts`
   - 先建立“这是一个导出入口”的概念。

2. 再看 `src/server/routers/tools/_helpers/scheduleToolCallReport.ts`
   - 重点理解三个点：
     - 为什么要算字节数
     - 为什么要用 `after()`
     - `CallReportRequest` 是怎么组装出来的

3. 然后看调用方：
   - `src/server/routers/tools/mcp.ts`
   - `src/server/routers/tools/market.ts`

   只看 `finally` 部分就够了，重点是它们如何传入：
   - `identifier`
   - `mcpType`
   - `requestPayload`
   - `result`
   - `success`
   - `telemetryEnabled`

4. 最后看 `src/server/services/discover/index.ts` 里的 `reportCall()`
   - 这样能把“helper 调用服务”与“服务再调用 market SDK”串起来。

## 常见误区

1. **把它当成通用工具函数目录**
   - 其实它不是泛用 helper 集合，而是工具调用统计的专用辅助层。

2. **误以为上报会阻塞请求**
   - 它用的是 `after()`，设计目标就是在响应后异步执行。

3. **忽略 `telemetryEnabled` 和 `marketAccessToken` 的前置判断**
   - 这两个条件不满足时根本不会上报。

4. **把 `responseSizeBytes` 理解成“只要有 result 就算”**
   - 代码里是 `success && result` 才计算，否则是 `0`。

5. **以为字节大小是精确协议大小**
   - 这里是 `JSON.stringify` 后的 UTF-8 字节数，属于统计口径，不是网络层真实传输字节。

6. **忽略循环引用的兜底**
   - `calculateObjectSizeBytes()` 对不可序列化对象会返回 `0`，这是为了避免上报流程因为数据问题崩掉。

7. **误判它的最终下游**
   - 它不是直接打业务接口，而是经由 `DiscoverService -> MarketService -> market.plugins.reportCall()` 发送出去。

根据当前片段推断，这个目录的定位非常清晰：它不是业务决策层，而是**工具调用埋点的异步上报适配层**。
