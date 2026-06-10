# 文件：next/src/server/auth/index.ts

## 一句话定位

`next/src/server/auth/index.ts` 是服务端认证配置的汇合层：它把 `NextAuth` 的数据库适配器、公共 session 回调、生产/开发环境 provider 配置组合起来，并提供统一的 `getServerAuthSession` 入口给后端 API 获取当前登录态。

## 它暴露/定义了什么

这个文件对外主要暴露两个能力：

`authOptions(req, res)`：按请求生成完整的 `NextAuth` 配置。它会先准备公共配置 `commonOptions`，再根据环境选择生产 OAuth 配置或本地开发登录配置，最后用 `lodash/merge` 合并成 `AuthOptions`。

`getServerAuthSession(ctx)`：对 `next-auth` 的 `getServerSession` 做一层包装，调用方只需要传入 `req`、`res`，不必在每个文件里重复导入和组装 `authOptions`。

文件内部还定义了 `overridePrisma`、`prismaAdapter` 和 `commonOptions`。其中 `overridePrisma` 目前只是包裹 `PrismaAdapter.createUser`，预留了创建用户后的扩展点；`commonOptions` 是真正影响会话内容的公共配置。

## 谁调用它

直接调用方主要有两个：

`next/src/pages/api/auth/[...nextauth].ts` 调用 `authOptions(req, res)`，把本文件生成的配置交给 `NextAuth`。这是登录、回调、session、登出等 NextAuth API 路由的入口。

`next/src/server/api/trpc.ts` 调用 `getServerAuthSession({ req, res })`，在每个 tRPC 请求创建上下文时取出当前 session，并放入 `ctx.session`。后续 `protectedProcedure` 会依赖这个 session 判断用户是否已登录。

前端组件如 `useSession`、`signIn`、`signOut` 并不直接导入本文件，但会通过 NextAuth 的 API 路由和 session 机制间接受它影响。

## 它调用谁

它调用 `@next-auth/prisma-adapter` 的 `PrismaAdapter(prisma)`，把项目的 Prisma Client 接入 NextAuth 的用户、账号、session 持久化流程。

它调用 `next-auth` 的 `getServerSession`，用于服务端读取当前请求对应的 session。

它调用本目录下的 `./auth` 和 `./local-auth`：`./auth` 提供生产环境的 Google、GitHub、Discord OAuth provider；`./local-auth` 提供 development 环境下的 Credentials 登录，并手动创建数据库 session 与 cookie。

它还直接调用 `prisma.session.findFirstOrThrow` 和 `prisma.organizationUser.findMany`，用于在 session 回调里补充 accessToken、用户 ID、superAdmin 标记和组织列表。

## 核心流程

请求进入 `next/src/pages/api/auth/[...nextauth].ts` 后，API 路由调用 `authOptions(req, res)`。该函数先判断 `env.NEXT_PUBLIC_VERCEL_ENV` 是否等于 `"development"`：如果是，使用 `local-auth.ts` 的本地 Credentials 配置；否则使用 `auth.ts` 的生产 OAuth 配置。

随后，`authOptions` 把环境专属配置与 `commonOptions` 合并。`commonOptions` 始终包含 Prisma adapter 和 `callbacks.session`。当 NextAuth 创建或读取 session 时，这个回调会根据 `user.id` 查询数据库中该用户最新过期时间的 `Session` 记录，并查询 `OrganizationUser` 关联的组织信息，然后把这些字段写回 `session` 对象。

tRPC 请求走另一条路径：`createTRPCContext` 调用 `getServerAuthSession`，后者内部再调用 `getServerSession(ctx.req, ctx.res, authOptions(ctx.req, ctx.res))`。因此 tRPC 的登录态、权限中间件和业务路由拿到的 session 字段，都来自本文件的统一配置和 session 回调增强。

## 关键函数的高层作用

`authOptions(req, res)` 是本文件最关键的函数。它承担“按运行环境选择认证方案”和“注入公共数据库/session 行为”的职责。生产环境依赖 OAuth provider；开发环境依赖本地 Credentials provider，并需要 `req`、`res` 来读写 `next-auth.session-token` cookie。

`getServerAuthSession(ctx)` 是后端读取登录态的标准入口。它避免 tRPC、SSR 或其他服务端代码重复关心 NextAuth 配置细节，也保证服务端拿到的 session 与 API auth 路由使用同一套规则。

`callbacks.session` 是 session 数据扩展的核心。默认 NextAuth session 不会自动带上项目需要的 `superAdmin` 和 `organizations`，这里通过 Prisma 查询补齐，使下游授权逻辑可以直接读取 `ctx.session.user.superAdmin`、`ctx.session.user.organizations`。

`overridePrisma` 当前没有实际业务逻辑，只是在 `createUser` 外包一层 try/catch 扩展点；根据当前片段推断，它可能是为注册用户后初始化组织、额度或审计信息预留的钩子，依据是注释中写了 `Add custom functionality here`，但当前实现未执行任何额外操作。

## 修改风险

最大风险在 `session` 回调。它使用 `findFirstOrThrow` 查询用户 session，如果数据库中没有对应 `Session` 记录，整个 session 获取会抛错，进而影响 tRPC context 创建和受保护接口访问。改这里时要确认开发登录、OAuth 登录、session 过期和多设备登录场景都能正常覆盖。

`session.accessToken` 实际被赋值为数据库 `Session.sessionToken`，不是 OAuth provider 的 access token。修改命名或来源前要检查下游是否把它当作 NextAuth session token 使用，避免破坏现有调用约定。

`authOptions` 使用 `lodash/merge(commonOptions, options)`，而 `merge` 会修改第一个参数。由于 `commonOptions` 是模块级对象，多次调用可能让环境配置或 callbacks 合并结果长期留在同一个对象上。若要重构，建议特别关注开发/生产配置切换、测试环境复用和回调覆盖顺序。

生产和开发认证路径差异较大。`local-auth.ts` 会手动创建 session 并写 cookie，而生产 OAuth 依赖 NextAuth 标准流程。改 adapter、cookie 名、JWT encode/decode 或 provider 配置时，必须分别验证本地 Credentials 登录和生产 OAuth 登录。

`next-auth.d.ts` 扩展了 `Session.user` 类型，假定 session 回调会填充 `id`、`superAdmin`、`organizations`。如果删除或延迟这些字段，TypeScript 可能仍认为字段存在，但运行时会变成 `undefined`，下游权限判断会出现隐蔽问题。
