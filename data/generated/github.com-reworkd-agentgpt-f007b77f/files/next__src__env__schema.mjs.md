# 文件：next/src/env/schema.mjs

## 一句话定位

`next/src/env/schema.mjs` 是 Next.js 前端工程的环境变量契约中心：它用 `zod` 定义服务端与客户端可用环境变量的类型、默认值、必填规则和暴露边界，并把 `process.env` 中允许读取的键显式映射出来，供后续校验入口使用。

## 它暴露/定义了什么

该文件主要导出四个对象：

`serverSchema`：服务端环境变量的 Zod schema。它约束 `DATABASE_URL`、`NODE_ENV`、`NEXTAUTH_SECRET`、`NEXTAUTH_URL`、`OPENAI_API_KEY` 以及 Google、GitHub、Discord OAuth 凭据等变量。

`serverEnv`：服务端环境变量白名单。它不是 schema，而是从 `process.env` 手动取出的实际输入对象，字段与 `serverSchema` 对齐。

`clientSchema`：客户端环境变量的 Zod schema。它只定义 `NEXT_PUBLIC_` 前缀变量，例如功能开关、CDN、Vercel 环境、后端地址、最大循环次数、Pusher key 等，并给多数变量提供默认值。

`clientEnv`：客户端环境变量白名单。它手动列出允许被 Next.js 构建期内联、并最终可能暴露到浏览器侧的 `NEXT_PUBLIC_` 变量。

文件内部还定义了两个小工具：`requiredForProduction()` 和 `stringToBoolean()`。

## 谁调用它

直接调用者主要有三个：

`next/src/env/server.mjs` 导入 `serverSchema`、`serverEnv`，在服务端环境校验入口中执行 `serverSchema.safeParse(serverEnv)`。该入口又被 `next/next.config.mjs` 动态导入，因此在 `dev` 或 `build` 阶段会提前验证环境变量，除非设置 `SKIP_ENV_VALIDATION`。

`next/src/env/client.mjs` 导入 `clientSchema`、`clientEnv`，校验客户端变量，并导出经过解析后的 `env`。

`next/src/server/auth/auth.ts` 直接导入 `serverEnv`，用于 NextAuth 的 Google、GitHub、Discord provider 配置。这里没有使用已校验的 `env`，而是读取原始映射对象；根据当前片段推断，这是为了在认证配置中方便访问 OAuth 凭据，但它也意味着这些字段会保持 `string | undefined` 的形态。

间接使用者更多：业务代码通常从 `next/src/env/client.mjs` 或 `next/src/env/server.mjs` 导出的 `env` 读取值，例如后端 API 地址、`OPENAI_API_KEY`、Vercel 环境等。

## 它调用谁

它只依赖 `zod` 和 Node/Next.js 注入的 `process.env`。

`z.object()`、`z.string()`、`z.enum()`、`z.preprocess()`、`z.coerce.number()`、`default()`、`optional()` 等用于描述变量规则。`process.env.NODE_ENV` 决定生产环境下某些变量是否必填；`process.env.VERCEL`、`process.env.VERCEL_URL` 用于放宽 Vercel 部署时 `NEXTAUTH_URL` 的校验策略。

它不调用项目内其他模块，也不发起网络请求、数据库连接或认证初始化。

## 核心流程

核心流程可以理解为“声明契约，然后显式取值”。

第一步，定义服务端契约。`serverSchema` 要求 `DATABASE_URL` 必须是 URL，`NODE_ENV` 必须是 `development`、`test`、`production` 之一；`NEXTAUTH_SECRET` 在生产环境必填，非生产环境可选；`NEXTAUTH_URL` 会先尝试使用 `VERCEL_URL` 作为替代来源，并在 Vercel 环境下不强制 URL 协议格式；OAuth 凭据和 `OPENAI_API_KEY` 都是可选但非空字符串。

第二步，手动构造 `serverEnv`。这一步很关键，因为 Next.js middleware 和构建期环境变量分析不能把 `process.env` 当普通对象随意解构。手动列字段既让类型与 schema 对齐，也防止无意读取未声明变量。

第三步，定义客户端契约。`clientSchema` 限定所有可暴露字段都以 `NEXT_PUBLIC_` 开头，并给功能开关、后端地址、Vercel URL、最大循环次数等提供默认值。布尔开关通过预处理把字符串 `"true"` 转成 `true`，其余值会变成 `false`。

第四步，手动构造 `clientEnv`。这保证只有列出的 `NEXT_PUBLIC_` 变量会进入客户端校验与导出链路。

真正的校验不在本文件执行，而是在 `client.mjs`、`server.mjs` 中执行：失败时打印格式化错误并抛出 `Invalid environment variables`，成功后导出解析后的 `env`。

## 关键函数的高层作用

`requiredForProduction()` 的作用是表达“生产环境必填，非生产环境可省略”的规则。目前只用于 `NEXTAUTH_SECRET`。它根据 `process.env.NODE_ENV` 返回不同的 Zod 字符串 schema：生产环境要求最小长度为 1 并 `trim()`，其他环境在同样字符串规则基础上追加 `optional()`。

`stringToBoolean()` 用于解析客户端功能开关。因为浏览器可见环境变量在构建期通常是字符串，它用 `z.preprocess()` 把输入值是否严格等于 `"true"` 转换成布尔值，再交给 `z.boolean()` 校验。注意这不是通用布尔解析：`"1"`、`"TRUE"`、`"false"`、空字符串都会被处理为 `false`。

`NEXTAUTH_URL` 上的 `z.preprocess()` 是另一个关键点。它优先使用 `process.env.VERCEL_URL`，避免 Vercel 部署未显式设置 `NEXTAUTH_URL` 时构建失败；但由于 `VERCEL_URL` 不含协议，处于 Vercel 环境时 schema 只要求字符串，不要求 `url()` 格式。

## 修改风险

最大风险是服务端与客户端边界被破坏。`serverSchema` 中不能放入 `NEXT_PUBLIC_` 变量，`server.mjs` 会检查并抛错；`clientSchema` 中也不能放入非 `NEXT_PUBLIC_` 变量，`client.mjs` 会拒绝。把密钥类变量误加到 `clientSchema` 或 `clientEnv` 会导致敏感信息暴露到浏览器侧。

第二个风险是 schema 与 env 映射不同步。新增变量时必须同时修改 `*Schema` 和对应的 `*Env`，否则可能出现“schema 定义了但永远读不到”或“读取了但不被校验”的问题。由于 Next.js 构建期只内联被显式引用的环境变量，漏加到 `clientEnv` 还会导致客户端拿不到值。

第三个风险是默认值改变会影响运行行为。比如 `NEXT_PUBLIC_BACKEND_URL` 默认指向本地后端，`NEXT_PUBLIC_MAX_LOOPS` 默认是 `25`，功能开关默认多为 `false`。这些值参与 API 请求、功能开关和 agent 行为限制，调整时需要同步确认部署环境变量和业务预期。

第四个风险是生产构建会被校验阻断。`next.config.mjs` 会在未设置 `SKIP_ENV_VALIDATION` 时导入 `src/env/server.mjs`，因此把变量改成必填、收紧 URL 规则或调整 enum，都可能让 `next dev`、`next build` 提前失败。Docker 构建虽然可用 `SKIP_ENV_VALIDATION` 跳过，但运行时仍可能因缺失变量导致认证、数据库或 API 调用异常。

第五个风险是直接使用 `serverEnv` 的代码不会得到 Zod 解析后的默认值或类型收窄。`next/src/server/auth/auth.ts` 读取的是 `serverEnv`，所以 OAuth provider 配置中仍要处理 `undefined`。如果未来希望统一使用校验后的结果，需要评估初始化顺序和循环依赖，不能只在本文件替换导出。
