# 目录：next/src/server/auth

## 它负责什么

`next/src/server/auth` 是这个 Next.js 应用的服务端认证配置中心，负责把 `next-auth`、Prisma 数据库适配器、第三方 OAuth 登录、本地开发登录、服务端 session 读取逻辑组合在一起。它不是 UI 登录页，也不是业务权限判断层，而是“认证基础设施层”：定义用户如何登录、session 如何落库、服务端如何拿到当前用户、session 对象里额外补充哪些字段。

从当前片段看，这个目录的核心职责有四类：

第一，统一导出 `authOptions(req, res)`，供 `next-auth` API 路由使用。实际挂载点在 `next/src/pages/api/auth/[...nextauth].ts`，这里调用 `NextAuth(req, res, authOptions(req, res))`，因此所有认证请求最终都会进入本目录生成的配置。

第二，接入 Prisma。`index.ts` 中用 `PrismaAdapter(prisma)` 作为 `next-auth` 的 adapter，说明用户、账号、session 等认证数据主要通过 Prisma 写入数据库。目录本身不定义 Prisma schema，但依赖数据库中的 `session`、`organizationUser`、`organization` 等模型来补全登录态。

第三，根据环境切换认证方式。`index.ts` 会检查 `env.NEXT_PUBLIC_VERCEL_ENV`，当值为 `"development"` 时使用 `local-auth.ts` 的开发登录配置，否则使用 `auth.ts` 的生产 OAuth 配置。也就是说，这里同时维护“真实 OAuth 登录”和“本地不安全凭据登录”两套认证入口。

第四，扩展 session 内容。`commonOptions.callbacks.session` 会在每次构造服务端 session 时查询数据库，把 `sessionToken` 写入 `session.accessToken`，并把 `user.id`、`user.superAdmin`、`user.organizations` 注入 `session.user`。这些字段的 TypeScript 类型扩展位于邻近的 `next/src/types/next-auth.d.ts`。

## 直接子目录地图

这个目录当前没有直接子目录，只有三个主要文件：

`next/src/server/auth/index.ts` 是聚合入口，也是推荐首先阅读的文件。它负责创建 Prisma adapter、定义公共 `session` callback、按环境合并生产或开发认证配置，并导出 `getServerAuthSession`。

`next/src/server/auth/auth.ts` 是生产认证配置。它声明 `GoogleProvider`、`GithubProvider`、`DiscordProvider`，并统一指定登录页为 `/signin`。

`next/src/server/auth/local-auth.ts` 是开发环境认证配置。它使用 `Credentials` provider，通过输入用户名和 `superAdmin` 字段创建或更新用户，并手动创建 `next-auth.session-token` cookie。文件里的 provider 名称已经明确标注为 `Development Only (Insecure)`，说明它只应服务于本地开发体验。

## 关键入口

最外部的 HTTP 入口是 `next/src/pages/api/auth/[...nextauth].ts`。这是 NextAuth 的 catch-all API 路由，负责接收 `/api/auth/*` 系列请求，例如 signin、callback、session 等。它本身很薄，只把请求交给 `NextAuth`，真正配置由 `next/src/server/auth/index.ts` 提供。

目录内部最关键的入口是 `authOptions(req, res)`。这个函数不是静态常量，而是一个根据请求响应对象动态生成配置的函数。原因是开发模式的 `local-auth.ts` 需要读写 cookie，因此必须拿到当前 `req`、`res`。

服务端业务代码常用入口是 `getServerAuthSession(ctx)`。它封装了 `getServerSession(ctx.req, ctx.res, authOptions(ctx.req, ctx.res))`，让其他服务端模块不必重复导入和拼装 `authOptions`。邻近调用点可见于 `next/src/server/api/trpc.ts`，tRPC context 通过它获取 `session`，再把 session 放入后续 API 处理上下文。

前端侧的入口不在本目录，但与本目录强相关：`next/src/pages/_app.tsx` 使用 `SessionProvider`，`next/src/hooks/useAuth.ts` 封装 `useSession`、`signIn`、`signOut`，`next/src/pages/signin.tsx` 展示 providers 并触发登录。它们消费的是本目录配置产生的 NextAuth 行为。

## 主流程位置

生产登录主流程大致是：浏览器访问登录页 `next/src/pages/signin.tsx`，页面通过 `getProviders` 获取可用 provider；用户选择 Google、GitHub 或 Discord 后调用 `signIn(providerId)`；请求进入 `next/src/pages/api/auth/[...nextauth].ts`；该路由调用 `authOptions(req, res)`；非 development 环境下合并 `commonOptions` 与 `auth.ts` 的 OAuth providers；NextAuth 完成 OAuth callback 后通过 Prisma adapter 创建或关联用户、账号和 session；之后 session callback 再从数据库查询最新 session token 和组织成员关系，返回扩展后的 `session`。

开发登录主流程不同：`authOptions(req, res)` 在 development 环境下使用 `local-auth.ts`。用户通过 Credentials provider 提交 `name` 和 `superAdmin`；`authorize` 用 zod 校验参数，再用 adapter 按 email 查找用户，不存在则创建用户，存在则更新用户名和 `superAdmin`。随后 `signIn` callback 手动调用 `adapter.createSession` 创建一个月有效期的 session，并用 `setCookie` 写入 `next-auth.session-token`。`jwt.encode` 再从 cookie 中取出这个 token，`decode` 返回 `null`，根据当前片段推断，这是为了让 Credentials 登录也走数据库 session token，而不是使用普通 JWT session。

服务端鉴权主流程位于 `next/src/server/auth/index.ts` 与 `next/src/server/api/trpc.ts` 的组合处。tRPC context 调用 `getServerAuthSession` 得到当前 session；需要登录的 procedure 再判断 `ctx.session` 和 `ctx.session.user` 是否存在。认证目录负责“拿到并丰富 session”，具体业务是否允许访问则由 API 层继续判断。

## 推荐阅读顺序

建议先读 `next/src/pages/api/auth/[...nextauth].ts`，确认 NextAuth 的外部挂载方式很薄，所有复杂度都被委托给 `next/src/server/auth`。

第二步读 `next/src/server/auth/index.ts`。重点看 `commonOptions`、`callbacks.session`、`authOptions(req, res)` 和 `getServerAuthSession`。这能建立全局地图：哪些配置是公共的，哪些配置按环境替换，session 中的扩展字段从哪里来。

第三步读 `next/src/server/auth/auth.ts`。它很短，只要确认生产环境有哪些 OAuth provider、使用哪些环境变量、登录页指向哪里即可。

第四步读 `next/src/server/auth/local-auth.ts`。这部分比生产配置更容易误解，重点看 Credentials provider、`authorize`、`signIn` callback、cookie 写入和 `jwt.encode/decode` 的特殊处理。

最后再读邻近消费者：`next/src/server/api/trpc.ts`、`next/src/types/next-auth.d.ts`、`next/src/hooks/useAuth.ts`、`next/src/pages/signin.tsx`。这些文件能帮助理解认证配置如何被服务端 API 和前端页面实际消费。

## 常见误区

不要把 `auth.ts` 当作整个认证系统的唯一入口。它只是生产 OAuth provider 配置，真正对外导出的配置入口是 `index.ts` 里的 `authOptions(req, res)`。

不要忽略 `commonOptions.callbacks.session`。应用中很多地方使用的 `session.accessToken`、`session.user.superAdmin`、`session.user.organizations` 并不是 NextAuth 默认字段，而是在这里通过数据库查询补进去的。若只看 provider 配置，会漏掉权限和组织信息的来源。

不要把 `session.accessToken` 理解成第三方 OAuth access token。根据当前代码，它被赋值为数据库里的 `session.sessionToken`，更像应用自己的 session token。服务层如 `next/src/services/api-utils.ts` 会把它放进 `Authorization: Bearer ...`，因此它在应用内部也承担 API 访问凭据角色。

不要在生产环境使用 `local-auth.ts` 的思路。该文件显式使用 Credentials provider，并允许通过输入控制 `superAdmin`，还手动创建 cookie。根据文件名和 provider 文案，它是开发便利入口，不是安全的真实登录方案。

不要以为这个目录负责页面跳转和 UI 状态。登录页、侧边栏登录按钮、弹窗、受保护路由跳转都在 `pages`、`hooks`、`components` 中；`next/src/server/auth` 只负责服务端认证配置和 session 构造。

不要把组织权限判断放到本目录理解。本目录只把用户所属组织映射到 `session.user.organizations`，后续如何限制某个 API 或页面访问，应继续看 `next/src/server/api`、业务 router 和前端调用逻辑。
