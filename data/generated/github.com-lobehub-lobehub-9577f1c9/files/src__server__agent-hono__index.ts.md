# 文件：src/server/agent-hono/index.ts

## 它负责什么

`src/server/agent-hono/index.ts` 是 `/api/agent/*` 这一组服务端 API 的 Hono 路由聚合入口。

它本身不实现具体业务逻辑，而是做三件事：

1. 创建一个以 `/api/agent` 为 `basePath` 的 Hono app。
2. 把不同路径映射到对应的 handler。
3. 为部分路径挂载认证 middleware，例如 QStash 签名、Bearer secret、service token、API key 等。

这个文件最终被 Next.js App Router 的 catch-all 路由挂载：

```ts
// src/app/(backend)/api/agent/[[...route]]/route.ts
import app from '@/server/agent-hono';

const handler = (request: Request) => app.fetch(request);

export const GET = handler;
export const POST = handler;
```

也就是说，请求进入 Next.js 的 `/api/agent/[[...route]]` 后，会交给这里的 Hono app 继续分发。

文件顶部注释里还说明了一个重要迁移策略：已有的静态 `route.ts` 优先级高于 catch-all，所以可以逐个路径迁移到 Hono。某个路径如果还存在单独的静态 Next.js route，它会先于这个 catch-all 生效；删除静态 route 后，再由这里接管。

## 关键组成

这个文件的核心代码很短：

```ts
const app = new Hono().basePath('/api/agent');
```

之后全部是 `app.get(...)` / `app.post(...)` 路由注册。

### 1. Agent 执行入口

```ts
app.post('/', qstashOrApiKeyAuth(), execAgent);
```

对应：

```txt
POST /api/agent
```

作用是启动一个新的 agent operation。

从 `handlers/execAgent.ts` 可见，请求体大致包含：

```ts
{
  userId,
  agentId | slug,
  prompt,
  appContext?,
  autoStart?,
  existingMessageIds?
}
```

它会：

1. 解析 JSON body。
2. 校验 `userId`、`agentId` 或 `slug`、`prompt`。
3. 通过 `getServerDB()` 获取服务端数据库连接。
4. 创建 `AiAgentService`。
5. 调用 `aiAgentService.execAgent(...)`。
6. 返回 operation 结果和 `executionTime`。

认证使用 `qstashOrApiKeyAuth()`，也就是二选一：

- 有效的 QStash 签名；
- 或 `Authorization: Bearer <AGENT_EXEC_API_KEY>`。

这说明该入口既可以被 QStash 调度调用，也可以被受信任的外部调用方用 API key 触发。

### 2. Agent 单步执行

```ts
app.post('/run', qstashAuth(), runStep);
app.get('/run', runStepHealth);
```

对应：

```txt
POST /api/agent/run
GET  /api/agent/run
```

`POST /run` 用于执行 agent operation 的某一步。根据 `handlers/runStep.ts`，请求体里核心字段是：

```ts
{
  operationId,
  stepIndex,
  context,
  humanInput?,
  approvedToolCall?,
  rejectionReason?,
  rejectAndContinue?,
  toolMessageId?
}
```

它会：

1. 读取 JSON body。
2. 从 header `upstash-retried` 读取 QStash 外部重试次数。
3. 根据 `operationId` 通过 `AgentRuntimeCoordinator` 读取 operation metadata。
4. 从 metadata 中拿到 `userId`。
5. 创建 `AgentRuntimeService`。
6. 调用 `agentRuntimeService.executeStep(...)`。
7. 返回 step 执行状态，例如 `status`、`success`、`nextStepScheduled`、`waitingForHuman`、`pendingApproval`、`totalCost` 等。

如果某一步被其他实例锁住，会返回 `429` 和 `Retry-After: 37`，让 QStash 稍后重试。

`GET /run` 是健康检查，返回：

```ts
{
  healthy: true,
  message: 'Agent execution service is running',
  timestamp: ...
}
```

### 3. 工具结果回传

```ts
app.post('/tool-result', serviceTokenAuth(), toolResult);
```

对应：

```txt
POST /api/agent/tool-result
```

注释写明这是 gateway-side tool result，会被 `LPUSH` 到 Redis。结合搜索结果里的 `ToolResultWaiter` 注释，可以看出它属于 agent runtime 等待外部工具结果的链路：工具结果由网关侧推回来，服务端再交给 runtime 后续步骤读取。

认证使用 `serviceTokenAuth()`，不是 QStash。这类 endpoint 更像内部服务之间的回调通道。

### 4. abandoned operation 收尾

```ts
app.post('/finalize-abandoned', serviceTokenAuth(), finalizeAbandoned);
app.get('/finalize-abandoned', (c) => c.json(...));
```

对应：

```txt
POST /api/agent/finalize-abandoned
GET  /api/agent/finalize-abandoned
```

`POST` 用于 watchdog reverse-trigger finalize，也就是对被判定为 abandoned 的 agent operation 做收尾处理。

`GET` 是健康检查，返回：

```ts
{
  healthy: true,
  message: 'Agent finalize-abandoned endpoint is running',
  timestamp: ...
}
```

### 5. Message gateway 相关入口

```ts
app.get(
  '/gateway',
  bearerSecretAuth(() => process.env.CRON_SECRET),
  gatewayCron,
);
```

对应：

```txt
GET /api/agent/gateway
```

这是 Vercel cron 入口，使用 `CRON_SECRET` 做 Bearer 认证。

```ts
app.post(
  '/gateway/start',
  bearerSecretAuth(() => process.env.KEY_VAULTS_SECRET),
  gatewayStart,
);
```

对应：

```txt
POST /api/agent/gateway/start
```

这是非 Vercel 场景下的 `ensureRunning` 入口，使用 `KEY_VAULTS_SECRET` 做 Bearer 认证。

```ts
app.post('/gateway/callback', gatewayCallback);
```

对应：

```txt
POST /api/agent/gateway/callback
```

这是 message gateway 的状态变化回调。这里没有在 `index.ts` 里挂 middleware。代码注释说明原因是：认证逻辑在 handler 内部，这样 disabled-feature 场景可以先返回 `204`，避免不必要认证。

这个细节很重要：不能简单认为没有 middleware 就是无认证；有些认证被放到了 handler 内部。

### 6. Bot callback 与平台 webhook

```ts
app.post('/webhooks/bot-callback', qstashAuth(), botCallback);
```

对应：

```txt
POST /api/agent/webhooks/bot-callback
```

这是 agent step/completion webhook，使用 QStash 签名认证。

```ts
app.post('/webhooks/:platform/:appId?', platformWebhook);
```

对应：

```txt
POST /api/agent/webhooks/:platform
POST /api/agent/webhooks/:platform/:appId
```

这是 Chat SDK bot platform webhook。`:platform` 表示平台，例如 Telegram、Slack、Discord、Feishu、QQ、Wechat 等；`:appId?` 是可选应用 ID。

从调用方搜索结果可以看到，多处平台 client 会生成类似 URL：

```txt
/api/agent/webhooks/slack/<applicationId>
/api/agent/webhooks/discord/<applicationId>
/api/agent/webhooks/telegram/<applicationId>
/api/agent/webhooks/wechat/<applicationId>
```

根据当前片段推断，`platformWebhook` 负责把不同平台的入站消息转交给 bot/message router 层处理；依据是 `src/server/services/bot/BotMessageRouter.ts` 的注释提到了 `POST /api/agent/webhooks/[platform]/[appId]`。

### 7. Messenger 安装、OAuth、共享 webhook

```ts
app.get('/messenger/:platform/install', messengerInstall);
```

对应：

```txt
GET /api/agent/messenger/:platform/install
```

用于启动 per-tenant OAuth install。前端入口里可以看到，例如：

```txt
/api/agent/messenger/slack/install
/api/agent/messenger/discord/install
```

```ts
app.get('/messenger/:platform/oauth/callback', messengerOAuthCallback);
```

对应：

```txt
GET /api/agent/messenger/:platform/oauth/callback
```

这是 OAuth redirect target。`messengerOAuthCallback.ts` 中会构造类似：

```txt
/api/agent/messenger/<platform>/oauth/callback
```

的 redirect URI。

```ts
app.post('/messenger/webhooks/:platform', messengerWebhook);
```

对应：

```txt
POST /api/agent/messenger/webhooks/:platform
```

这是共享 Messenger bot webhook。`messengerWebhook.ts` 注释说明它和 `/api/agent/webhooks/:platform/:appId` 不同：后者偏 per-user/per-agent 路由，前者是 Messenger 集成的共享 webhook。

## 上下游关系

### 上游：请求如何进来

主要上游是 Next.js App Router：

```txt
HTTP request
  -> src/app/(backend)/api/agent/[[...route]]/route.ts
  -> app.fetch(request)
  -> src/server/agent-hono/index.ts
  -> 对应 Hono route
```

此外，还有一些具体上游来源：

- CLI 或其他客户端调用 `POST /api/agent` 启动 agent。
- QStash 调用 `POST /api/agent/run` 执行异步 step。
- QStash 调用 `/webhooks/bot-callback` 做 step/completion callback。
- Vercel Cron 调用 `GET /api/agent/gateway`。
- 内部服务使用 service token 调用 `/tool-result`、`/finalize-abandoned`。
- 各聊天平台调用 `/webhooks/:platform/:appId?`。
- Messenger OAuth 页面跳转到 `/messenger/:platform/oauth/callback`。
- Messenger 平台事件进入 `/messenger/webhooks/:platform`。

还有一个静态路由例外：

```txt
/api/agent/stream
```

搜索结果显示它仍在：

```txt
src/app/(backend)/api/agent/stream/...
```

由于文件注释说静态 route 优先于 catch-all，所以 `/api/agent/stream` 不由这个 Hono app 处理，而是由自己的 Next.js route 处理。

### 下游：它分发给谁

`index.ts` 直接依赖两类下游：

第一类是 handlers：

```ts
botCallback
execAgent
finalizeAbandoned
gatewayCallback
gatewayCron
gatewayStart
messengerInstall
messengerOAuthCallback
messengerWebhook
platformWebhook
runStep
runStepHealth
toolResult
```

这些 handler 负责真正业务处理。

第二类是 middlewares：

```ts
bearerSecretAuth
qstashAuth
qstashOrApiKeyAuth
serviceTokenAuth
```

这些 middleware 负责请求进入业务前的认证/鉴权。

更深层的下游包括：

- `AiAgentService`：启动 agent operation。
- `AgentRuntimeCoordinator`：读取 operation metadata。
- `AgentRuntimeService`：执行 agent step。
- `getServerDB()`：获取服务端数据库连接。
- Redis/QStash：用于异步调度、状态协调、工具结果等待等。
- bot/gateway/messenger service：处理平台消息、OAuth、gateway 生命周期。

## 运行/调用流程

### 流程一：启动一个 agent operation

```txt
POST /api/agent
  -> qstashOrApiKeyAuth()
  -> execAgent()
  -> getServerDB()
  -> new AiAgentService(serverDB, userId)
  -> aiAgentService.execAgent(...)
  -> 返回 operationId 等结果
```

这一流程的关键点是：`index.ts` 只决定“这个路径用哪个认证、进入哪个 handler”，具体的参数校验和业务执行在 `execAgent.ts`。

### 流程二：执行 agent 的某一步

```txt
POST /api/agent/run
  -> qstashAuth()
  -> runStep()
  -> 读取 operationId / stepIndex / context
  -> AgentRuntimeCoordinator.getOperationMetadata(operationId)
  -> new AgentRuntimeService(serverDB, metadata.userId)
  -> agentRuntimeService.executeStep(...)
  -> 返回 step 状态
```

如果 step 已经被别的实例执行中：

```txt
runStep()
  -> result.locked === true
  -> HTTP 429
  -> Retry-After: 37
```

这说明该接口天然面向异步分布式执行环境，需要处理重复触发、锁竞争和重试。

### 流程三：工具结果回传

```txt
POST /api/agent/tool-result
  -> serviceTokenAuth()
  -> toolResult()
  -> 根据当前片段推断：写入 Redis，供 runtime 等待方读取
```

依据是路由注释里的 `LPUSH'd to Redis`，以及 `ToolResultWaiter` 注释提到会等待从 `tool-result` 入口进入 Redis 的结果。

### 流程四：平台消息 webhook

```txt
POST /api/agent/webhooks/:platform/:appId?
  -> platformWebhook()
  -> 根据 platform/appId 分发到对应 bot 平台逻辑
```

这个流程面向外部聊天平台。URL 中的 `platform` 是平台标识，`appId` 可选。不同平台 client 会把 webhook URL 注册成 `/api/agent/webhooks/<platform>/<applicationId>`。

### 流程五：Messenger OAuth 安装

```txt
GET /api/agent/messenger/:platform/install
  -> messengerInstall()
  -> 跳转到对应平台 OAuth 授权页

GET /api/agent/messenger/:platform/oauth/callback
  -> messengerOAuthCallback()
  -> 处理 OAuth callback
```

它和普通 `/webhooks/:platform/:appId?` 的区别是：这里是 Messenger 集成安装/授权链路，不只是消息回调。

## 小白阅读顺序

1. 先读 `src/server/agent-hono/index.ts`  
   目标是建立路由地图：哪些 URL 存在、用什么 method、走哪个 handler、套了什么 middleware。

2. 再读挂载点 `src/app/(backend)/api/agent/[[...route]]/route.ts`  
   这能理解为什么 Hono app 可以处理 Next.js 的 `/api/agent/*` 请求。重点看 `app.fetch(request)`。

3. 接着读 `handlers/execAgent.ts`  
   这是最容易理解的业务入口：收 JSON、校验参数、调用 `AiAgentService.execAgent()`、返回结果。

4. 然后读 `handlers/runStep.ts`  
   这是 agent runtime 的关键异步执行入口。重点理解 `operationId`、`stepIndex`、`AgentRuntimeCoordinator`、`AgentRuntimeService.executeStep()`。

5. 再读 `middlewares/qstashOrApiKeyAuth.ts` 和 `middlewares/qstashAuth.ts`  
   这样能理解为什么不同路径使用不同认证。特别注意 QStash 签名验证需要读取 raw body。

6. 最后按兴趣读 gateway / bot / messenger 相关 handler  
   如果关注聊天平台集成，读 `platformWebhook.ts`、`messengerInstall.ts`、`messengerOAuthCallback.ts`、`messengerWebhook.ts`。  
   如果关注后台任务和运行守护，读 `gatewayCron.ts`、`gatewayStart.ts`、`gatewayCallback.ts`、`finalizeAbandoned.ts`、`toolResult.ts`。

## 常见误区

1. **误以为这个文件实现了业务逻辑**  
   它主要是路由装配层。真正的业务在 `handlers/*` 和更下游的 service/module 中。

2. **误以为 `/api/agent/*` 全都由这个 Hono app 处理**  
   不完全是。注释明确说静态 `route.ts` 优先于 catch-all。比如搜索结果里 `/api/agent/stream` 有自己的静态 route，因此不一定经过 `src/server/agent-hono/index.ts`。

3. **误以为没有 middleware 的路由就没有认证**  
   例如 `/gateway/callback` 的注释说明认证放在 handler 内部，是为了 disabled-feature 场景能先短路返回 `204`。`platformWebhook`、`messengerWebhook` 这类外部平台 webhook 也可能在 handler 或平台 adapter 内部做签名校验。

4. **误把 `POST /api/agent` 和 `POST /api/agent/run` 看成同一种接口**  
   `/api/agent` 是启动 operation；`/api/agent/run` 是执行某个 operation 的单步。前者用 `AiAgentService.execAgent()`，后者用 `AgentRuntimeService.executeStep()`。

5. **误以为 QStash 只负责启动任务**  
   从代码看，QStash 至少用于 `/run` 的 step 执行，也用于 `/webhooks/bot-callback`。`/api/agent` 还支持 QStash 签名或 API key 双认证。

6. **误忽略 `basePath('/api/agent')`**  
   在 Hono 中注册的是 `app.post('/run', ...)`，真实 HTTP 路径是 `/api/agent/run`。阅读时要把 `basePath` 和后续 route path 拼起来看。

7. **误认为健康检查都是统一格式或统一位置**  
   这里 `GET /run` 和 `GET /finalize-abandoned` 都是健康检查，但它们是分别注册的，并不是全局 health endpoint。

8. **误认为 `:appId?` 是必填**  
   `/webhooks/:platform/:appId?` 里的 `?` 表示 `appId` 可选，所以 `/api/agent/webhooks/discord` 和 `/api/agent/webhooks/discord/app-1` 都可能匹配。
