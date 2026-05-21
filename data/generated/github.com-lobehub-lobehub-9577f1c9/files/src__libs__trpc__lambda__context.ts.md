# 文件：src/libs/trpc/lambda/context.ts

## 它负责什么

`src/libs/trpc/lambda/context.ts` 是 LobeHub 后端 tRPC Lambda 类接口的“请求上下文构造器”。它的职责不是处理具体业务，而是在每一次 tRPC 请求进入 router 之前，把请求里能识别出的认证信息、客户端信息、追踪信息和响应头容器整理成统一的 `LambdaContext`，供后续 tRPC middleware 和 procedure 使用。

这个文件主要服务于三类 tRPC endpoint：

- `src/app/(backend)/trpc/lambda/[trpc]/route.ts`
- `src/app/(backend)/trpc/mobile/[trpc]/route.ts`
- `src/app/(backend)/trpc/tools/[trpc]/route.ts`

这些 route 都通过 `fetchRequestHandler` 接入 tRPC，并把 `createContext: () => createLambdaContext(req)` 传进去。也就是说，`context.ts` 产出的对象会成为 `ctx`，后续所有 tRPC 中间件和业务 procedure 都围绕这个 `ctx` 判断用户身份、读取 token、做鉴权或补充上下文。

从代码看，它重点解决四类问题：

1. 识别当前请求对应的 `userId`。
2. 支持多种认证来源：开发 mock、`X-API-Key`、OIDC token、Better Auth session。
3. 提取通用请求上下文：`clientIp`、`userAgent`、`mp_token`、trace context。
4. 为 tRPC response 扩展预留 `resHeaders`。

## 关键组成

### 1. `extractClientIp`

```ts
const extractClientIp = (request: NextRequest): string | undefined => {
  const forwardedFor = request.headers.get('x-forwarded-for');
  ...
  const realIp = request.headers.get('x-real-ip')?.trim();
  ...
};
```

这个小函数负责从请求头中推断客户端 IP。优先级是：

1. `x-forwarded-for`
2. `x-real-ip`
3. 没有则返回 `undefined`

`x-forwarded-for` 可能是逗号分隔的代理链，所以这里只取第一个 IP。这个设计符合常见反向代理场景：第一个值通常代表原始客户端 IP。

它只返回字符串，不做复杂校验。根据当前片段推断，后续如果有风控、日志、限流或审计逻辑，需要的是“尽量提取到的客户端 IP”，而不是强校验后的网络地址对象。

### 2. `validateApiKeyUserId`

```ts
const validateApiKeyUserId = async (apiKey: string): Promise<string | null> => {
  if (!validateApiKeyFormat(apiKey)) return null;

  const db = await getServerDB();
  const apiKeyRecord = await ApiKeyModel.findByKey(db, apiKey);

  if (!apiKeyRecord) return null;
  if (!apiKeyRecord.enabled) return null;
  if (isApiKeyExpired(apiKeyRecord.expiresAt)) return null;

  ...
  return apiKeyRecord.userId;
};
```

这是 `X-API-Key` 认证的核心逻辑。它做了几层判断：

- `validateApiKeyFormat(apiKey)`：先看格式是否合法。
- `ApiKeyModel.findByKey(db, apiKey)`：到数据库查找 key 对应记录。
- `apiKeyRecord.enabled`：确认 key 没被禁用。
- `isApiKeyExpired(apiKeyRecord.expiresAt)`：确认 key 未过期。
- `updateLastUsed(apiKeyRecord.id)`：认证成功后异步更新最后使用时间。

这里有一个重要细节：`updateLastUsed` 是 fire-and-forget：

```ts
void userApiKeyModel.updateLastUsed(apiKeyRecord.id).catch(...)
```

也就是说，更新最后使用时间失败不会阻塞当前请求认证成功。失败只会写 `debug` 和 `console.error`。这说明 API key 的“是否可用”与“记录最近使用时间”被刻意解耦，避免统计字段更新失败影响正常调用。

如果数据库查询、校验过程抛错，函数会返回 `null`，并记录错误。外层看到 `null` 会把用户视为未认证。

### 3. `OIDCAuth`

```ts
export interface OIDCAuth {
  [key: string]: any;
  payload: any;
  sub: string;
}
```

`OIDCAuth` 描述 OIDC token 认证成功后放进上下文里的信息。

它至少包含：

- `sub`：用户 ID。
- `payload`：完整 token payload。
- 其他任意字段：通过 `[key: string]: any` 放宽结构。

这个类型比较宽松，说明 OIDC payload 可能携带不同用途的数据。例如在下游 `heteroOperationAuth` middleware 中，会读取 `ctx.oidcAuth.purpose` 来判断是否是 `hetero-operation` token。这个字段没有在接口中显式声明，而是依赖索引签名支持。

### 4. `AuthContext`

```ts
export interface AuthContext {
  clientIp?: string | null;
  jwtPayload?: ClientSecretPayload | null;
  marketAccessToken?: string;
  oidcAuth?: OIDCAuth | null;
  resHeaders?: Headers;
  traceContext?: OtContext;
  userAgent?: string;
  userId?: string | null;
}
```

这是 tRPC Lambda 上下文的主体结构。关键字段包括：

- `userId`：当前认证出的用户 ID。可能是 `string`、`null` 或 `undefined`。
- `oidcAuth`：OIDC token 认证结果。
- `marketAccessToken`：从 cookie `mp_token` 提取的市场访问 token。
- `clientIp`：从请求头推断出的客户端 IP。
- `userAgent`：请求头 `user-agent`。
- `traceContext`：从 traceparent 等 header 中提取的 OpenTelemetry 上下文。
- `resHeaders`：给后续流程追加响应 header 使用。
- `jwtPayload`：类型上存在，但当前文件没有实际写入。根据当前片段推断，这是历史兼容或为其他认证路径预留的字段。

需要特别注意 `userId` 的三种状态：

- `string`：已认证。
- `null`：明确认证失败或明确拒绝 fallback。
- `undefined`：没有认证信息、认证未命中，或者认证流程没有得到用户。

下游 `userAuth` middleware 使用 `if (!ctx.userId)` 判断，因此 `null` 和 `undefined` 都会被视为未登录。

### 5. `createContextInner`

```ts
export const createContextInner = async (params?: {...}): Promise<AuthContext> => {
  const responseHeaders = new Headers();

  return {
    clientIp: params?.clientIp,
    marketAccessToken: params?.marketAccessToken,
    oidcAuth: params?.oidcAuth,
    resHeaders: responseHeaders,
    traceContext: params?.traceContext,
    userAgent: params?.userAgent,
    userId: params?.userId,
  };
};
```

这是一个“纯组装”函数，负责把已解析好的参数转成最终上下文对象。

它的注释说明了设计意图：测试时不想 mock Next.js 的 request/response，所以把内部构造逻辑拆出来。测试文件 `src/libs/trpc/lambda/context.test.ts` 中大量直接调用 `createContextInner({ userId: 'user-1' })` 来构造 router caller 的上下文。

它每次都会创建新的 `Headers`：

```ts
const responseHeaders = new Headers();
```

这保证每个请求上下文都有独立的响应头容器，不会跨请求共享。

### 6. `LambdaContext`

```ts
export type LambdaContext = Awaited<ReturnType<typeof createContextInner>>;
```

这个类型是从 `createContextInner` 的返回值推导出来的。它被 `src/libs/trpc/lambda/init.ts` 使用：

```ts
export const trpc = initTRPC.context<LambdaContext>().create(...)
```

也就是说，整个 lambda tRPC 体系里的 `ctx` 类型都来自这里。

这个设计有一个好处：只要 `createContextInner` 返回结构变化，`LambdaContext` 会自动同步，避免手写类型和真实返回值漂移。

### 7. `createLambdaContext`

```ts
export const createLambdaContext = async (request: NextRequest): Promise<LambdaContext> => {
  ...
};
```

这是对真实 HTTP 请求使用的上下文构造入口。它负责完整认证流程。

认证优先级如下：

1. 开发环境 mock 用户。
2. `X-API-Key`。
3. OIDC token。
4. Better Auth session。
5. 都失败则返回未认证上下文。

下面按流程展开。

#### 开发环境 mock

```ts
const isDebugApi = request.headers.get('lobe-auth-dev-backend-api') === '1';
const isMockUser = process.env.ENABLE_MOCK_DEV_USER === '1';

if (process.env.NODE_ENV === 'development' && (isDebugApi || isMockUser)) {
  return createContextInner({
    userId: process.env.MOCK_DEV_USER_ID,
  });
}
```

开发环境下，如果请求头 `lobe-auth-dev-backend-api: 1` 或环境变量 `ENABLE_MOCK_DEV_USER=1`，会直接使用 `MOCK_DEV_USER_ID` 构造上下文。

注意这里直接返回，后续不会提取 cookie、trace、IP、session 等信息。这是一个开发调试快速通道，不是生产认证逻辑。

#### 通用请求信息提取

```ts
const userAgent = request.headers.get('user-agent') || undefined;
const clientIp = extractClientIp(request);

const cookieHeader = request.headers.get('cookie');
const cookies = cookieHeader ? parse(cookieHeader) : {};
const marketAccessToken = cookies['mp_token'];

const traceContext = extractTraceContext(request.headers);
```

认证之前，函数先提取通用上下文：

- `userAgent`
- `clientIp`
- `marketAccessToken`
- `traceContext`

然后放入 `commonContext`，供不同认证分支复用。

`marketAccessToken` 来自 cookie `mp_token`。下游 `marketUserInfo` middleware 还会从数据库里的用户设置读取 market token，并优先使用数据库 token，cookie token 只是 fallback。

#### API key 认证

```ts
const apiKeyToken = request.headers.get(LOBE_CHAT_API_KEY_HEADER)?.trim();
```

`LOBE_CHAT_API_KEY_HEADER` 固定为：

```ts
const LOBE_CHAT_API_KEY_HEADER = 'X-API-Key';
```

如果请求带了 `X-API-Key`，会优先走 API key 认证。

认证成功：

```ts
return createContextInner({
  ...commonContext,
  traceContext,
  userId: apiKeyUserId,
});
```

认证失败：

```ts
return createContextInner({
  ...commonContext,
  traceContext,
  userId: null,
});
```

这里最重要的行为是：只要请求携带了 `X-API-Key`，就不会 fallback 到 OIDC 或 Better Auth session。

测试文件也明确覆盖了这个行为：

- API key 成功时，不调用 session，也不调用 OIDC JWT 校验。
- API key 无效时，即使请求里同时有 `Oidc-Auth`，也不会 fallback，`userId` 返回 `null`。

这是一个安全设计：避免客户端传了错误或伪造 API key 后，又意外靠浏览器 session 通过认证，造成认证语义混乱。

#### OIDC 认证

```ts
if (authEnv.ENABLE_OIDC) {
  const oidcAuthToken = request.headers.get(LOBE_CHAT_OIDC_AUTH_HEADER);
  ...
}
```

只有 `authEnv.ENABLE_OIDC` 开启时才会尝试 OIDC。token 来源是 `LOBE_CHAT_OIDC_AUTH_HEADER`，测试中 mock 为 `Oidc-Auth`，真实值由 `@/envs/auth` 导出。

流程是：

1. 读取 OIDC token。
2. `validateOIDCJWT(oidcAuthToken)` 校验无状态 JWT。
3. 把 token 信息组装成 `oidcAuth`。
4. 使用 `getServerDB()` 获取数据库。
5. `assertOIDCUserActive(db, userId)` 检查用户当前状态。
6. 成功则立即返回上下文。

组装 `oidcAuth` 的代码：

```ts
oidcAuth = {
  payload: tokenInfo.tokenData,
  ...tokenInfo.tokenData,
  sub: tokenInfo.userId,
};
```

这里有一个细节：`...tokenInfo.tokenData` 在中间，最后 `sub: tokenInfo.userId` 会覆盖 payload 中可能存在的 `sub`。因此上下文里的 `oidcAuth.sub` 以 `validateOIDCJWT` 返回的 `userId` 为准。

另一个重要安全点是 `assertOIDCUserActive`。注释说明：先验证 JWT，再检查当前用户状态，这样被封禁或删除的用户不能继续拿已签发但尚未过期的 token 调用接口。

OIDC 异常分两类：

- 如果是 inactive user 错误：直接返回 `userId: null`，不 fallback。
- 如果是普通 OIDC 校验失败：记录错误，然后继续尝试 Better Auth session。

这说明系统区分“token 无效”和“用户明确不可用”：

- token 无效可能是请求没带对、过期、格式错，可以继续看是否有 session。
- 用户 inactive 是明确拒绝，不应该再用其他认证方式绕过。

#### Better Auth session

```ts
const session = await auth.api.getSession({
  headers: request.headers,
});
```

如果没有 API key，且 OIDC 没有成功返回，就会尝试 Better Auth session。

认证成功时：

```ts
userId = session.user.id;
```

然后返回：

```ts
return createContextInner({
  ...commonContext,
  traceContext,
  userId,
});
```

如果 session 不存在或没有 `user.id`，就返回 `userId` 为 `undefined` 的上下文。后续访问 `authedProcedure` 时会被 `userAuth` middleware 拦截并抛 `UNAUTHORIZED`。

如果 `auth.api.getSession` 抛错，函数会记录错误，然后走最后兜底返回。

#### 最终兜底

```ts
return createContextInner({ ...commonContext, traceContext, userId });
```

所有认证路径都没有成功时，仍然返回一个上下文对象，而不是抛错。

这符合 tRPC 的常见设计：context 构造阶段尽量只“识别身份”，不直接决定某个 procedure 是否允许访问。是否必须登录，由 `publicProcedure`、`authedProcedure`、`heteroAuthedProcedure` 等 procedure 类型和 middleware 决定。

## 上下游关系

### 上游：Next.js route handler

三个 route handler 会调用它：

- `src/app/(backend)/trpc/lambda/[trpc]/route.ts`
- `src/app/(backend)/trpc/mobile/[trpc]/route.ts`
- `src/app/(backend)/trpc/tools/[trpc]/route.ts`

它们的结构基本一致：

```ts
return fetchRequestHandler({
  createContext: () => createLambdaContext(req),
  endpoint: '/trpc/lambda',
  router: lambdaRouter,
  ...
});
```

区别主要是 endpoint 和 router：

- `/trpc/lambda` → `lambdaRouter`
- `/trpc/mobile` → `mobileRouter`
- `/trpc/tools` → `toolsRouter`

因此 `context.ts` 是这三组 tRPC API 的共同上下文入口。

### 平级：tRPC 初始化

`src/libs/trpc/lambda/init.ts` 使用 `LambdaContext` 初始化 tRPC：

```ts
export const trpc = initTRPC.context<LambdaContext>().create({
  transformer: superjson,
  errorFormatter(...)
});
```

这说明：

- `context.ts` 定义运行时上下文。
- `init.ts` 把这个上下文类型绑定到 tRPC。
- `index.ts` 再基于这个 `trpc` 导出 router、procedure 和 caller factory。

### 下游：procedure 和 middleware

`src/libs/trpc/lambda/index.ts` 定义了几类 procedure：

```ts
const baseProcedure = trpc.procedure.use(openTelemetry);

export const publicProcedure = baseProcedure;
export const authedProcedure = baseProcedure.use(oidcAuth).use(userAuth);
export const heteroAuthedProcedure = baseProcedure.use(heteroOperationAuth).use(userAuth);
```

这些 middleware 会消费 `context.ts` 提供的字段。

#### `userAuth`

路径：`src/libs/trpc/middleware/userAuth.ts`

```ts
if (!ctx.userId) {
  throw new TRPCError({ code: 'UNAUTHORIZED' });
}
```

它只关心 `ctx.userId` 是否存在。不存在就拒绝访问。通过后，它把上下文缩窄为：

```ts
ctx: { userId: ctx.userId }
```

因此在 `authedProcedure` 后续 resolver 中，`ctx.userId` 可以被当成已登录用户 ID 使用。

#### `oidcAuth`

路径：`src/libs/trpc/lambda/middleware/oidcAuth.ts`

```ts
if (ctx.oidcAuth) {
  if (ctx.oidcAuth.purpose === 'hetero-operation') {
    throw new TRPCError(...)
  }

  return next({
    ctx: { oidcAuth: ctx.oidcAuth, userId: ctx.oidcAuth.sub },
  });
}
```

它会把 OIDC 认证结果转成 `userId`。但它会拒绝 `purpose === 'hetero-operation'` 的 token，避免这种长生命周期、特定用途 token 被普通登录接口复用。

#### `heteroOperationAuth`

路径：`src/libs/trpc/lambda/middleware/heteroOperationAuth.ts`

```ts
if (!ctx.oidcAuth || ctx.oidcAuth.purpose !== 'hetero-operation') {
  throw new TRPCError(...)
}
```

它与 `oidcAuth` 正好相反，只接受 `purpose: 'hetero-operation'` 的 OIDC token。根据注释，这类 token 用于 hetero-agent ingest/finish endpoint。

这说明 `context.ts` 不直接判断某个 OIDC token 能访问哪些业务接口，它只负责把 token 解析成 `ctx.oidcAuth`；具体用途限制由不同 middleware 处理。

#### `marketUserInfo`

路径：`src/libs/trpc/lambda/middleware/marketUserInfo.ts`

它消费：

- `ctx.userId`
- `ctx.serverDB`
- `ctx.marketAccessToken`

其中 `marketAccessToken` 就是 `context.ts` 从 cookie `mp_token` 取出的值。该 middleware 会进一步读取用户设置里的 market token，并优先使用数据库里的 token。

### 测试调用方

`createContextInner` 被大量测试直接使用，比如：

- `src/server/routers/lambda/agentSignal.test.ts`
- `src/server/routers/lambda/config/index.test.ts`
- `src/server/routers/lambda/__tests__/messenger.test.ts`
- `src/libs/trpc/middleware/userAuth.test.ts`
- `src/libs/trpc/lambda/context.test.ts`

这说明 `createContextInner` 是测试构造 tRPC caller 的标准入口。测试不需要构造真实 `NextRequest`，只要传入 `userId`、`oidcAuth` 等字段即可。

## 运行/调用流程

一次典型的 `/trpc/lambda` 请求流程如下：

1. 浏览器、客户端或工具调用 `/trpc/lambda/...`、`/trpc/mobile/...` 或 `/trpc/tools/...`。
2. Next.js route handler 收到 `NextRequest`。
3. route handler 调用 `prepareRequestForTRPC(req)` 克隆/适配请求，避免 Next.js 16 body stream 被消费的问题。
4. route handler 把 `createContext: () => createLambdaContext(req)` 传给 `fetchRequestHandler`。
5. tRPC 在处理 procedure 前调用 `createLambdaContext(req)`。
6. `createLambdaContext` 先判断是否是开发 mock 请求。
7. 如果不是 mock，提取 `userAgent`、`clientIp`、cookie 中的 `mp_token`、trace context。
8. 如果请求带 `X-API-Key`：
   - 校验 API key 格式。
   - 查数据库。
   - 检查 enabled 和 expiresAt。
   - 成功则返回带 `userId` 的 context。
   - 失败则返回 `userId: null`，并且不再尝试 OIDC/session。
9. 如果没有 API key，且启用了 OIDC：
   - 读取 OIDC header。
   - 校验 JWT。
   - 检查用户是否 active。
   - 成功则返回带 `oidcAuth` 和 `userId` 的 context。
   - inactive 用户直接返回 `userId: null`。
   - 普通 OIDC 失败继续尝试 session。
10. 调用 Better Auth 的 `auth.api.getSession`：
    - session 有效则返回带 `userId` 的 context。
    - session 无效则返回未认证 context。
11. tRPC 根据 router 中的 procedure 类型继续执行：
    - `publicProcedure`：不要求 `userId`。
    - `authedProcedure`：先经过 `oidcAuth`，再经过 `userAuth`，没有 `userId` 会抛 `UNAUTHORIZED`。
    - `heteroAuthedProcedure`：要求 `ctx.oidcAuth.purpose === 'hetero-operation'`，再要求 `userId`。
12. 业务 resolver 使用 `ctx.userId`、`ctx.marketAccessToken`、`ctx.traceContext` 等字段完成后续操作。

可以把它理解成一条认证优先级链：

```text
development mock
  -> X-API-Key
  -> OIDC token
  -> Better Auth session
  -> anonymous context
```

其中两个分支会“失败即终止 fallback”：

```text
invalid X-API-Key -> userId: null -> 不再尝试 OIDC/session
inactive OIDC user -> userId: null -> 不再尝试 session
```

## 小白阅读顺序

1. 先看 `AuthContext` 接口  
   先理解最终 `ctx` 里有哪些字段。重点看 `userId`、`oidcAuth`、`marketAccessToken`、`traceContext`、`resHeaders`。

2. 再看 `createContextInner`  
   这是最简单的上下文组装函数。看懂它以后，就知道最终返回对象长什么样。

3. 再看 `createLambdaContext` 的前半段  
   从开发 mock、`userAgent`、`clientIp`、cookie、trace context 开始看。这些是与认证无关的通用信息。

4. 接着按认证优先级读  
   顺序读 API key、OIDC、Better Auth session。不要跳着看，因为这个函数的关键就是“谁优先、谁失败后是否 fallback”。

5. 然后看 `src/libs/trpc/lambda/init.ts`  
   这里能看到 `LambdaContext` 如何绑定到 tRPC：

   ```ts
   initTRPC.context<LambdaContext>()
   ```

6. 再看 `src/libs/trpc/lambda/index.ts`  
   这里能看到 `publicProcedure`、`authedProcedure`、`heteroAuthedProcedure` 如何基于 context 做不同级别的访问控制。

7. 最后看几个 middleware  
   推荐顺序：
   - `src/libs/trpc/middleware/userAuth.ts`
   - `src/libs/trpc/lambda/middleware/oidcAuth.ts`
   - `src/libs/trpc/lambda/middleware/heteroOperationAuth.ts`
   - `src/libs/trpc/lambda/middleware/marketUserInfo.ts`

   这样能看到 `ctx.userId`、`ctx.oidcAuth`、`ctx.marketAccessToken` 在下游如何被真正使用。

## 常见误区

### 误区 1：以为 `createLambdaContext` 会直接拒绝未登录请求

它不会直接抛 `UNAUTHORIZED`。它通常会返回一个 context，即使没有认证成功。

真正拒绝未登录请求的是 `userAuth` middleware：

```ts
if (!ctx.userId) {
  throw new TRPCError({ code: 'UNAUTHORIZED' });
}
```

所以是否允许匿名访问，不由 `context.ts` 单独决定，而由 procedure 类型决定。

### 误区 2：以为 API key 失败后还能用 session 登录

不能。只要请求带了 `X-API-Key`，就优先按 API key 处理。API key 无效时，函数会返回 `userId: null`，不会 fallback 到 OIDC 或 Better Auth session。

这个行为在测试中也被明确验证。它避免“错误 API key + 浏览器 session”导致认证来源混杂。

### 误区 3：以为 OIDC 失败一定会拒绝请求

不一定。普通 OIDC 校验失败会记录错误，然后继续尝试 Better Auth session。

但如果失败原因是用户 inactive，则不会 fallback，而是返回 `userId: null`。这是为了防止被封禁或删除的用户通过其他认证路径绕过限制。

### 误区 4：以为 `oidcAuth.sub` 完全来自 token payload

不完全是。代码里虽然展开了 `tokenInfo.tokenData`，但最后显式设置：

```ts
sub: tokenInfo.userId
```

因此最终 `oidcAuth.sub` 以 `validateOIDCJWT` 返回的 `userId` 为准，而不是简单信任 payload 中的 `sub` 字段。

### 误区 5：以为 `resHeaders` 是 Next.js response 本身

`resHeaders` 只是一个新的 `Headers` 对象，被放进 context 里给后续流程使用。它不是 `NextResponse`。具体如何合并到最终响应，需要看 tRPC response meta 或其他响应处理逻辑；在当前文件里只负责创建和传递。

### 误区 6：以为 `marketAccessToken` 一定代表已登录用户

`marketAccessToken` 只是从 cookie `mp_token` 取出的值，和 `userId` 是两条信息。当前文件不会验证它，也不会因为有 `marketAccessToken` 就认为用户已登录。

下游 `marketUserInfo` middleware 会在已有 `userId` 和 `serverDB` 的前提下进一步读取用户信息，并优先使用数据库里的 market token。

### 误区 7：以为 `userId: null` 和 `userId: undefined` 完全一样

对 `userAuth` 来说，两者都会失败，因为 `!ctx.userId` 都为真。

但语义上不同：

- `null` 更像“明确认证失败或明确拒绝 fallback”。
- `undefined` 更像“没有认证信息或没认证出来”。

这个区别在 `createLambdaContext` 中是有意表达的，尤其体现在 invalid API key 和 inactive OIDC user 分支。

### 误区 8：以为 `createContextInner` 只给生产代码用

它主要是为了测试和内部复用方便。很多 router 测试会直接调用：

```ts
createContextInner({ userId: 'user-1' })
```

这样可以绕过 `NextRequest`、cookie、headers、真实认证服务，直接构造 resolver 需要的 `ctx`。
