# 文件：src/server/routers/tools/_helpers/index.ts

## 它负责什么

`src/server/routers/tools/_helpers/index.ts` 是 `tools` TRPC router 内部 helper 的统一导出入口，也就是常见的 barrel file。

它当前只有一行：

```ts
export * from './scheduleToolCallReport';
```

这意味着它本身不写业务逻辑，而是把同目录的 `scheduleToolCallReport.ts` 重新导出，让上层 router 可以用更短、更稳定的路径导入：

```ts
import { scheduleToolCallReport } from './_helpers';
```

而不是：

```ts
import { scheduleToolCallReport } from './_helpers/scheduleToolCallReport';
```

所以，学习这个文件时不要只停留在 `index.ts` 这一行。它真正代表的是 `tools/_helpers` 这个小型 helper 模块边界：目前这个边界只暴露一个能力，即“在工具调用结束后异步上报调用数据”。

## 关键组成

当前 `index.ts` 只有一个导出：

```ts
export * from './scheduleToolCallReport';
```

它会导出 `scheduleToolCallReport.ts` 中的公开成员，主要包括：

- `scheduleToolCallReport`
- `ScheduleToolCallReportParams`
- `ToolCallReportMeta`

核心实现位于：

```txt
src/server/routers/tools/_helpers/scheduleToolCallReport.ts
```

这个 helper 负责把一次 tool 调用的统计信息整理成 `CallReportRequest`，然后通过 `DiscoverService.reportCall()` 上报到 market/discover 服务。

### `scheduleToolCallReport`

函数签名大致是：

```ts
export function scheduleToolCallReport(params: ScheduleToolCallReportParams): void
```

它接收工具调用上下文，包括：

- `identifier`：插件或工具标识
- `toolName`：被调用的方法名
- `mcpType`：MCP 连接类型
- `requestPayload`：请求参数，用来计算请求体大小
- `result`：调用结果，用来计算响应体大小
- `startTime`：调用开始时间，用来计算耗时
- `success`：调用是否成功
- `errorCode` / `errorMessage`：失败时的错误信息
- `telemetryEnabled`：是否允许遥测
- `marketAccessToken`：market 访问令牌
- `meta`：前端或调用方补充的元数据

### `ToolCallReportMeta`

`meta` 里主要放后端不一定能直接判断的信息：

```ts
export interface ToolCallReportMeta {
  customPluginInfo?: {
    avatar?: string;
    description?: string;
    name?: string;
  };
  isCustomPlugin?: boolean;
  sessionId?: string;
  version?: string;
}
```

这些字段用于上报时补充插件展示信息、是否自定义插件、会话 ID 和插件版本。

### `calculateObjectSizeBytes`

这是 `scheduleToolCallReport.ts` 内部私有函数，没有通过 `index.ts` 导出。

它的职责是估算对象序列化后的字节大小：

```ts
const calculateObjectSizeBytes = (obj: unknown): number => {
  try {
    const jsonString = JSON.stringify(obj);
    return new TextEncoder().encode(jsonString).length;
  } catch {
    return 0;
  }
};
```

关键点：

- 使用 `JSON.stringify()` 转成字符串。
- 使用 `TextEncoder` 计算 UTF-8 字节长度。
- 如果对象无法序列化，例如循环引用，返回 `0`。
- 它计算的是 JSON 表示的字节大小，不是 JavaScript 对象在内存里的真实占用。

### `after`

实现里使用了：

```ts
import { after } from 'next/server';
```

然后：

```ts
after(async () => {
  // report call
});
```

这表示上报逻辑不会阻塞当前接口响应，而是在响应之后执行。对工具调用接口来说，这很重要：用户应该先拿到工具调用结果，统计上报属于后台副作用。

## 上下游关系

### 上游调用方

当前能看到两个主要调用方：

```txt
src/server/routers/tools/mcp.ts
src/server/routers/tools/market.ts
```

它们都通过 `index.ts` 导入：

```ts
import { scheduleToolCallReport } from './_helpers';
```

这说明 `index.ts` 是 `tools` router 内部 helper 的公开门面。

### `mcp.ts` 中的使用方式

在 `src/server/routers/tools/mcp.ts` 里，`callTool` mutation 会调用 MCP 工具：

```ts
result = await mcpService.callTool(...)
```

它在调用前记录：

```ts
const startTime = Date.now();
```

然后用 `try/catch/finally` 捕获成功或失败状态。无论调用成功还是抛错，最后都会执行：

```ts
scheduleToolCallReport({
  errorCode,
  errorMessage,
  identifier: input.params.name,
  marketAccessToken: ctx.marketAccessToken,
  mcpType: 'http',
  meta: input.meta,
  requestPayload: input.args,
  result,
  startTime,
  success,
  telemetryEnabled: ctx.telemetryEnabled,
  toolName: input.toolName,
});
```

这说明 `scheduleToolCallReport` 不负责执行工具，也不负责错误处理的主流程；它只消费调用结果和上下文，做后置上报。

有一个细节：`mcp.ts` 对 `stdio` 环境做了检查，但传给 report 的 `mcpType` 当前是固定 `'http'`。根据当前片段推断，这可能是因为该上报语义关注 cloud/market 侧的 MCP 调用类型，或者这里还没有细分 `input.params.type`。只从当前片段看，不能断言这是 bug。

### `market.ts` 中的使用方式

`src/server/routers/tools/market.ts` 也从 `./_helpers` 导入 `scheduleToolCallReport`。结合文件中的 schema：

```ts
const callCloudMcpEndpointSchema = z.object({
  apiParams: z.record(z.any()),
  identifier: z.string(),
  meta: metaSchema,
  toolName: z.string(),
});
```

可以判断它用于 cloud MCP endpoint 或 market tool 调用后的上报。根据当前片段推断，`market.ts` 和 `mcp.ts` 的角色类似：实际执行由 market/discover/MCP service 完成，`scheduleToolCallReport` 只负责统一格式的统计上报。

### 下游依赖

`scheduleToolCallReport.ts` 依赖这些外部模块：

```ts
import { CURRENT_VERSION } from '@lobechat/const';
import { type CallReportRequest } from '@lobehub/market-types';
import { after } from 'next/server';

import { DiscoverService } from '@/server/services/discover';
```

分别代表：

- `CURRENT_VERSION`：当前应用版本，写入上报 metadata。
- `CallReportRequest`：market 上报接口的数据结构类型。
- `after`：Next.js 的响应后任务机制。
- `DiscoverService`：真正发起上报请求的服务层。

最终上报的数据形状是：

```ts
const reportData: CallReportRequest = {
  callDurationMs,
  customPluginInfo: meta?.customPluginInfo,
  errorCode,
  errorMessage,
  identifier,
  isCustomPlugin: meta?.isCustomPlugin,
  metadata: {
    appVersion: CURRENT_VERSION,
    mcpType,
  },
  methodName: toolName,
  methodType: 'tool',
  requestSizeBytes,
  responseSizeBytes,
  sessionId: meta?.sessionId,
  success,
  version: meta?.version || 'unknown',
};
```

然后：

```ts
const discoverService = new DiscoverService({ accessToken: marketAccessToken });
await discoverService.reportCall(reportData);
```

## 运行/调用流程

一次工具调用上报的大致流程如下：

1. 用户或 agent 触发工具调用，例如 MCP tool 或 market cloud MCP tool。
2. `tools` router 中的 mutation 接收到请求。
3. router 记录 `startTime`。
4. router 调用真正的执行服务，例如 `mcpService.callTool()` 或 market 相关 service。
5. 如果执行成功，保存 `result`，`success` 保持为 `true`。
6. 如果执行失败，进入 `catch`，设置：
   - `success = false`
   - `errorCode`
   - `errorMessage`
7. 无论成功或失败，`finally` 中调用 `scheduleToolCallReport(...)`。
8. `scheduleToolCallReport` 先判断：
   - `telemetryEnabled` 必须为 `true`
   - `marketAccessToken` 必须存在
9. 如果任一条件不满足，直接返回，不上报。
10. 如果允许上报，调用 Next.js `after()` 注册一个响应后任务。
11. 在 `after()` 回调里计算：
   - `callDurationMs = Date.now() - startTime`
   - `requestSizeBytes`
   - `responseSizeBytes`
12. 组装 `CallReportRequest`。
13. 创建 `DiscoverService`。
14. 调用 `discoverService.reportCall(reportData)`。
15. 如果上报自身失败，只打印：
   ```ts
   console.error('Failed to report tool call: %O', reportError);
   ```
   不影响原工具调用结果。

这个流程的重点是：工具执行结果和上报结果是解耦的。上报失败不会让工具调用失败。

## 小白阅读顺序

建议按这个顺序阅读：

1. 先看目标文件：

   ```txt
   src/server/routers/tools/_helpers/index.ts
   ```

   理解它只是统一导出入口，不承载业务逻辑。

2. 再看实际导出的文件：

   ```txt
   src/server/routers/tools/_helpers/scheduleToolCallReport.ts
   ```

   重点看三个部分：

   - `ScheduleToolCallReportParams`
   - `ToolCallReportMeta`
   - `scheduleToolCallReport()`

3. 接着看调用方之一：

   ```txt
   src/server/routers/tools/mcp.ts
   ```

   重点找 `callTool` mutation。这里能看到为什么上报函数要接收 `startTime`、`success`、`errorCode`、`result` 等字段。

4. 再看另一个调用方：

   ```txt
   src/server/routers/tools/market.ts
   ```

   重点理解 market/cloud MCP 相关工具调用也复用同一个上报 helper。

5. 最后看测试：

   ```txt
   src/server/routers/tools/_helpers/scheduleToolCallReport.test.ts
   ```

   测试覆盖了几个关键行为：

   - 遥测关闭时不上报。
   - 没有 `marketAccessToken` 时不上报。
   - 成功时计算响应大小。
   - 失败或无结果时响应大小为 `0`。
   - 循环引用对象大小计算为 `0`。
   - Unicode 字符按 UTF-8 字节计算。
   - `DiscoverService.reportCall()` 被调用。
   - 上报失败不会向外抛出。

## 常见误区

### 误区一：以为 `index.ts` 是业务实现文件

这个文件只有：

```ts
export * from './scheduleToolCallReport';
```

它是导出聚合层，不是逻辑层。真正要学习的是它暴露出去的 helper。

### 误区二：以为 `scheduleToolCallReport` 会执行工具

不会。工具执行发生在 `mcpService.callTool()` 或 market 相关 service 中。

`scheduleToolCallReport` 只处理“调用结束后的统计上报”。

### 误区三：以为上报会阻塞接口响应

不会。它使用 Next.js 的 `after()`：

```ts
after(async () => {
  // report
});
```

设计目的就是把上报放到响应之后执行，减少对用户请求链路的影响。

### 误区四：以为没有 token 也会上报

不会。函数开头有明确判断：

```ts
if (!telemetryEnabled || !marketAccessToken) return;
```

也就是说必须同时满足：

- 用户或系统允许 telemetry。
- 当前上下文有 `marketAccessToken`。

否则不会产生上报请求。

### 误区五：以为 request/response size 是真实网络包大小

不是。这里的大小计算逻辑是：

```ts
JSON.stringify(obj)
TextEncoder().encode(jsonString).length
```

它估算的是对象 JSON 序列化后的 UTF-8 字节数。它不包含 HTTP headers、传输编码、压缩等网络层开销。

### 误区六：以为 `result: {}` 会被当成无响应

不会。实现里是：

```ts
const responseSizeBytes = success && result ? calculateObjectSizeBytes(result) : 0;
```

在 JavaScript 中 `{}` 是 truthy，所以成功且结果是 `{}` 时，会计算为 `2`，也就是 `"{}"` 的字节数。

但如果 `result` 是 `undefined`、`null`、`0`、`''` 这类 falsy 值，即使 `success` 为 `true`，当前逻辑也会把 `responseSizeBytes` 记为 `0`。测试里明确覆盖了 `undefined` 的情况。

### 误区七：以为上报失败会影响工具调用

不会。上报包在 `try/catch` 中：

```ts
try {
  await discoverService.reportCall(reportData);
} catch (reportError) {
  console.error('Failed to report tool call: %O', reportError);
}
```

失败只记录日志，不重新抛错。这个 helper 的设计边界是“尽力上报”，不是“强一致审计”。

### 误区八：忽略 `meta` 的来源

`meta` 不是 helper 自己计算出来的，而是调用方从输入里透传：

```ts
meta: input.meta
```

这说明 session、custom plugin 信息、version 等上下文需要前端或上游调用方提供。helper 只负责把它们放进 `CallReportRequest`。
