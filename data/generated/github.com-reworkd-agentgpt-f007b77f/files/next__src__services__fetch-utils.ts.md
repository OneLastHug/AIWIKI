# 文件：next/src/services/fetch-utils.ts

## 一句话定位

`next/src/services/fetch-utils.ts` 是前端服务层的通用 HTTP 请求封装文件，负责把业务代码里的后端请求统一拼接到 `NEXT_PUBLIC_BACKEND_URL`，附加认证与组织请求头，并用 `zod` schema 对响应 JSON 做运行时校验和类型推断。

## 它暴露/定义了什么

该文件定义了一个内部辅助函数 `getHeaders(accessToken, organizationId)`，以及四个导出的请求函数：`get`、`post`、`put`、`delete_`。

这些函数都是泛型函数，泛型约束为 `T extends z.ZodTypeAny`，调用方传入一个 `zod` schema 后，返回值类型会被推断为 `Promise<z.infer<T>>`。因此它不仅是网络请求工具，也是前端 API 响应类型收敛点：请求成功后必须经过 `schema.parse(await response.json())`，否则会在运行时抛出校验错误。

`delete_` 使用下划线命名，是为了避开 JavaScript/TypeScript 中 `delete` 关键字。

## 谁调用它

根据当前仓库检索，直接调用点集中在前端 hooks 和服务类中：

`next/src/hooks/useModels.ts` 使用 `get("/api/models", ModelList, session?.accessToken)` 获取可用模型列表，并依赖 `next-auth` session 中的 `accessToken`。

`next/src/hooks/useTools.ts` 使用 `get("/api/agent/tools", ToolsResponseSchema)` 获取工具列表，然后与 `localStorage` 中的启用状态合并。

`next/src/services/api/org.ts` 的 `OrganizationApi.get(name)` 使用它请求 `/api/auth/organization/${name}`，读取组织用户信息。

`next/src/services/workflow/oauthApi.ts` 的 `OauthApi` 多个方法使用它请求 OAuth 安装、卸载、信息查询接口，并传入 `accessToken` 与 `organizationId`。

根据当前片段推断，虽然 `post`、`put`、`delete_` 在本次检索范围内没有直接调用，但它们是为同一套服务层风格预留的写操作封装。

## 它调用谁

它直接依赖三类外部能力：

第一，浏览器或 Next.js 运行环境提供的全局 `fetch`，负责真实网络请求。

第二，`next/src/env/client.mjs` 导出的 `env`，特别是 `env.NEXT_PUBLIC_BACKEND_URL`，用于把相对 API path 转换成完整后端地址。`client.mjs` 本身会通过环境变量 schema 校验，确保暴露到客户端的变量都以 `NEXT_PUBLIC_` 开头。

第三，`zod`，用于把接口响应从不可信 JSON 转成经过校验的前端数据结构。这里的 `z` 只作为 type import 使用，但传入的 schema 对象在运行时会执行 `parse`。

## 核心流程

核心流程很固定：调用方提供 `path`、响应 `schema`，写操作额外提供 `body`，可选传入 `accessToken` 与 `organizationId`。函数内部先用 `env.NEXT_PUBLIC_BACKEND_URL + path` 生成请求地址，再通过 `getHeaders` 生成请求头。

请求头始终包含 `"Content-Type": "application/json"`，并始终包含 `Authorization: Bearer ${accessToken || ""}`。如果传入了 `organizationId`，会额外加入 `"X-Organization-Id"`。这意味着即使没有 token，也会发送一个空 bearer header。

随后执行 `fetch`。如果 `response.ok` 为 false，函数抛出错误并终止；如果成功，则读取 `response.json()`，再交给调用方传入的 `zod` schema 解析，最终返回强类型数据。

## 关键函数的高层作用

`getHeaders` 是请求头构造器，封装认证 token 与组织上下文。它让 `OauthApi` 这类需要多租户上下文的服务不必自己拼 header。

`get` 是当前实际使用最广的函数，承担读取类接口请求。模型列表、工具列表、组织信息、OAuth 状态查询都走这条路径。

`post`、`put`、`delete_` 是写操作封装，流程与 `get` 基本一致，只是会把 `body` 通过 `JSON.stringify` 放入请求体，并设置对应 HTTP method。它们目前不承载复杂逻辑，主要提供统一的请求形状与响应校验入口。

需要注意错误处理略有差异：`get` 和 `post` 在失败时统一抛出 `"Request failed"`，而 `put` 和 `delete_` 抛出 `response.statusText`。这会影响上层 UI 能拿到的错误信息一致性。

## 修改风险

最大风险是它位于前端请求链路的底层。一旦修改 `getHeaders`、URL 拼接或错误处理，会同时影响 `useModels`、`useTools`、`OrganizationApi`、`OauthApi` 等多个业务入口。

修改 `Authorization` 行为要谨慎。当前代码在 token 缺失时仍发送 `Bearer `，后端如果依赖该 header 的存在或格式，改成省略 header 可能产生兼容性问题；反过来，继续发送空 token 也可能影响某些公开接口或代理层判断。

修改 `schema.parse` 行为风险也很高。如果改成不校验或宽松解析，前端类型安全会下降；如果 schema 更严格，则后端字段微小变化会直接导致页面请求失败。这里的校验是“接口契约边界”，不是普通格式化代码。

错误处理目前信息较粗，`get`、`post` 不读取后端错误体。如果要增强错误信息，需要确认上层是否依赖现有 `Error("Request failed")` 文案，以及是否会暴露敏感后端错误。

最后，`env.NEXT_PUBLIC_BACKEND_URL` 是客户端环境变量。任何把它替换为服务端私有变量、相对路径或动态来源的修改，都需要同时考虑浏览器端、Next.js 构建期环境校验、部署环境和跨域配置。
