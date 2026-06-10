# 子系统：next/src/pages/api/auth

## 解决什么问题

`next/src/pages/api/auth` 是前端 Next.js 应用的认证 API 入口，负责把所有 `/api/auth/*` 请求交给 `NextAuth` 处理。目录中只有 `next/src/pages/api/auth/[...nextauth].ts`，它本身不保存复杂业务逻辑，而是作为 Next.js Pages Router 的 catch-all API route，接收登录、回调、登出、session 查询等 NextAuth 标准请求，并动态组装 `authOptions(req, res)`。

这个子系统解决的是“浏览器、OAuth 服务商、本地开发登录、数据库 session、应用内用户上下文”之间的衔接问题。用户登录后，NextAuth 通过 Prisma adapter 把用户、账号和 session 落到数据库；随后应用通过 `useSession`、`getServerSession` 或封装的 `getServerAuthSession` 获取 session，并在 session 中携带 `accessToken`、`user.id`、`superAdmin`、`organizations` 等业务字段，供 agent、workflow、settings、tRPC 等模块做鉴权和请求转发。

## 相关目录和文件

核心入口是 `next/src/pages/api/auth/[...nextauth].ts`。它导入 `NextAuth` 和 `next/src/server/auth` 暴露的 `authOptions`，在请求到达时调用 `NextAuth(req, res, authOptions(req, res))`。这说明认证配置依赖请求和响应对象，尤其是本地开发模式下需要读写 cookie。

主要配置集中在 `next/src/server/auth/index.ts`。这里创建 `PrismaAdapter(prisma)`，定义通用 `commonOptions`，并按环境选择生产 OAuth 配置或开发 credentials 配置。生产配置在 `next/src/server/auth/auth.ts`，包含 `GoogleProvider`、`GithubProvider`、`DiscordProvider`，并统一把登录页指向 `/signin`。开发配置在 `next/src/server/auth/local-auth.ts`，使用 `Credentials` provider，以用户名模拟用户，并手动创建 session cookie。

类型扩展在 `next/src/types/next-auth.d.ts`，它扩展了 `next-auth` 的 `Session` 和 `User`，让业务代码可以类型安全地访问 `session.accessToken`、`session.user.id`、`session.user.superAdmin`、`session.user.organizations`。环境变量约束在 `next/src/env/schema.mjs`，其中 `NEXTAUTH_SECRET`、`NEXTAUTH_URL`、OAuth client id 和 secret、`DATABASE_URL` 都和认证链路相关。

消费侧包括 `next/src/pages/signin.tsx`、`next/src/pages/_app.tsx`、`next/src/hooks/useAuth.ts`、`next/src/server/api/trpc.ts`、`next/src/services/api-utils.ts`、`next/src/services/workflow/oauthApi.ts`、`next/src/services/agent/*`。这些文件分别负责登录页面、SessionProvider 注入、前端登录登出封装、服务端 session 上下文、向后端 API 附带 bearer token 等。

## 核心对象

`auth` 是 `next/src/pages/api/auth/[...nextauth].ts` 的默认导出函数，也是 Next.js 实际挂载的 API handler。它不直接判断登录方式，而是把控制权交给 `NextAuth`。

`authOptions(req, res)` 是认证配置工厂。它先准备公共配置，再根据 `env.NEXT_PUBLIC_VERCEL_ENV` 判断是否处于 `development`，开发环境使用 `devOptions(commonOptions.adapter, req, res)`，其他环境使用 `prodOptions`，最后通过 `lodash/merge` 合并配置。

`commonOptions` 是所有环境共享的 NextAuth 配置。最关键的是 `adapter: prismaAdapter` 和 `callbacks.session`。`PrismaAdapter` 负责把 NextAuth 的用户、账号、session 映射到 Prisma 数据库；`session` callback 则查询最新的 `prisma.session` 和该用户所属的 `organizationUser`，再把数据库信息写回 `session`。

`prodOptions` 是生产登录方式配置，包含 Google、GitHub、Discord 三个 OAuth provider，并设置 `allowDangerousEmailAccountLinking: true`。这意味着相同邮箱的不同 OAuth 账号可以被自动关联，改动时要特别关注账号接管风险。

`devOptions` 是开发环境的本地登录配置。它用 `Credentials` provider 接收 `name` 和 `superAdmin`，通过 adapter 查找或创建用户；登录成功后手动创建数据库 session，并写入 `next-auth.session-token` cookie。它还覆写 `jwt.encode` 从 cookie 读取 session token，`jwt.decode` 返回 `null`，本质上是让 credentials 登录走数据库 session token 路径。

## 运行流程

浏览器访问 `/signin` 时，页面通过 `getProviders` 获取可用 provider，用户点击 OAuth 或 credentials 登录后，请求会进入 `/api/auth/*`，由 `next/src/pages/api/auth/[...nextauth].ts` 接住。入口函数调用 `authOptions(req, res)` 生成配置，然后交给 NextAuth 处理 provider 授权、回调、cookie、session 等细节。

在生产或非 development 环境中，`authOptions` 合并 `commonOptions` 和 `prodOptions`。用户选择 Google、GitHub 或 Discord 后，NextAuth 完成 OAuth 回调，并通过 Prisma adapter 写入或更新用户、账号、session。后续客户端通过 `SessionProvider`、`useSession` 获取登录态。

在 development 环境中，`authOptions` 合并 `commonOptions` 和 `local-auth.ts` 的配置。credentials 登录时，`authorize` 会把输入的 `name` 当作 email 查找用户；存在则更新用户，不存在则创建用户。`signIn` callback 随后调用 adapter 创建一个有效期约一个月的 session，并把 session token 写入 `next-auth.session-token` cookie。根据当前片段推断，这样做是为了绕过真实 OAuth 配置，方便本地调试需要登录态的功能。

每次 session 被读取时，`commonOptions.callbacks.session` 都会根据 `user.id` 查询最新 session token 和组织关系，并把这些信息补到返回对象。业务代码随后使用 `session.accessToken` 作为 bearer token 调用 `/api/models`、agent backend、workflow OAuth API 等。

## 上下游依赖

上游依赖包括 Next.js API route 机制、`next-auth`、`@next-auth/prisma-adapter`、Prisma 数据库、OAuth provider 环境变量、cookie 读写库 `cookies-next`、`uuid` 和 `zod`。其中数据库是强依赖，因为公共 session callback 使用 `prisma.session.findFirstOrThrow` 和 `prisma.organizationUser.findMany`；如果用户没有可用 session 记录，session 读取会直接失败。

下游依赖主要是应用鉴权和业务 API。`next/src/pages/_app.tsx` 用 `SessionProvider` 把 session 注入 React 树；`next/src/hooks/useAuth.ts` 封装登录、登出和受保护页面跳转；`next/src/server/api/trpc.ts` 通过 `getServerAuthSession` 把 session 放进 tRPC context，并在 protected procedure 中要求 `ctx.session.user` 存在；`next/src/services/api-utils.ts` 会从 `session.accessToken` 生成 `Authorization: Bearer ...` 请求头；agent 和 workflow 相关服务也依赖该 token 访问后端。

## 修改时最容易踩的坑

第一，`next/src/pages/api/auth/[...nextauth].ts` 看起来很薄，但不要把业务逻辑直接塞进这个 API route。现有设计把环境切换、adapter、callbacks 都集中在 `next/src/server/auth`，入口只负责转发给 NextAuth。

第二，`authOptions` 使用 `merge(commonOptions, options)`。`lodash/merge` 会深度合并对象，改 callbacks、pages、adapter、jwt 时要确认是覆盖、合并还是意外继承。尤其是开发配置也有 `callbacks.signIn`，公共配置也有 `callbacks.session`，二者会组合存在。

第三，`session.accessToken` 实际来自数据库 session 的 `sessionToken`，不是 OAuth provider 的 access token。下游把它作为 bearer token 使用时，语义更接近“本站 session token”。如果要接入真实 provider access token，不能直接复用这个字段而不检查调用方含义。

第四，`callbacks.session` 使用 `findFirstOrThrow`，且按 `expires desc` 取最新 session。删除 session、调整 session 表结构、改变 adapter 行为时，可能导致登录用户读取 session 时报错。

第五，生产 provider 使用 `allowDangerousEmailAccountLinking: true`。新增 provider 或改账号关联策略时，需要评估同邮箱跨 provider 自动合并的安全边界。

第六，开发模式判断使用 `env.NEXT_PUBLIC_VERCEL_ENV === "development"`，不是单纯的 `NODE_ENV`。本地或预览环境变量配置不一致时，可能误用 OAuth provider 或误启 credentials 登录。

## 推荐阅读顺序

1. 先读 `next/src/pages/api/auth/[...nextauth].ts`，理解 API route 只是 NextAuth 的统一入口。
2. 再读 `next/src/server/auth/index.ts`，重点看 `PrismaAdapter`、`commonOptions.callbacks.session`、`authOptions(req, res)` 如何组合环境配置。
3. 接着读 `next/src/server/auth/auth.ts`，了解生产环境 OAuth provider 和 `/signin` 登录页配置。
4. 然后读 `next/src/server/auth/local-auth.ts`，理解本地 credentials 登录、手动创建 session、cookie 与 jwt encode 的特殊处理。
5. 补读 `next/src/types/next-auth.d.ts`，确认业务 session 扩展字段。
6. 最后沿消费链阅读 `next/src/pages/signin.tsx`、`next/src/hooks/useAuth.ts`、`next/src/server/api/trpc.ts`、`next/src/services/api-utils.ts`，理解登录态如何进入页面、服务端 API 和后端请求。
