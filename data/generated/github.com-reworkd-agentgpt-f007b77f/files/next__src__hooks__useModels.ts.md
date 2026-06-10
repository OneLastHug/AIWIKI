# 文件：next/src/hooks/useModels.ts

## 一句话定位

`next/src/hooks/useModels.ts` 是前端“可选 LLM 模型列表”的读取 hook：它在用户已登录且拿到 `accessToken` 后，请求后端 `/api/models`，校验返回结构，并向设置页提供模型列表与按名称查找模型的能力。

## 它暴露/定义了什么

这个文件定义了一个运行时 schema、一个类型和一个 hook。

`Model` 是 `zod` schema，约束单个模型对象必须包含 `name`、`max_tokens`、`has_access` 三个字段。其中 `name` 是模型名，`max_tokens` 是该模型允许的 token 上限，`has_access` 表示当前用户是否有权限使用该模型。`ModelList` 是模型数组 schema。

`LLMModel` 是从 `Model` 推导出的 TypeScript 类型，供外部组件复用，避免前端手写重复结构。

`useModels()` 是主要导出。它返回 `{ models, getModel }`：`models` 默认是空数组，数据加载成功后变为后端返回的模型列表；`getModel(name)` 用于按模型名从当前缓存数据中查找模型。

## 谁调用它

当前仓库中明确调用它的是 `next/src/pages/settings.tsx`。设置页通过：

`const { models, getModel } = useModels();`

拿到可选模型列表，并传给 `Combo<LLMModel>` 作为模型下拉选项。设置页还用 `getModel(settings.customModelName)` 找到当前设置中的模型，从而决定 token 滑块的最大值。

根据当前片段推断，`useModels.ts` 的主要用户界面入口就是设置页的 Advanced Settings 区域；仓库搜索没有发现其他前端调用点。

## 它调用谁

它直接调用三个外部能力。

第一是 `useSession`，来自 `next-auth/react`。它读取当前认证会话，并取出 `session?.accessToken`，作为后端 API 的 Bearer token。

第二是 `useQuery`，来自 `@tanstack/react-query`。它负责请求生命周期、缓存、重复请求合并和数据状态管理。这里使用的 query key 是 `["llm"]`。

第三是本地封装的 `get`，来自 `next/src/services/fetch-utils.ts`。`get("/api/models", ModelList, session?.accessToken)` 会拼接 `env.NEXT_PUBLIC_BACKEND_URL`，带上 Authorization header 请求后端，并用 `ModelList.parse()` 校验响应 JSON。

后端 `/api/models` 的实现不在当前搜索结果中出现。根据 `fetch-utils.ts` 的实现，它很可能由 `NEXT_PUBLIC_BACKEND_URL` 指向的独立后端服务提供，而不是这个 Next.js 前端目录内的 API route。

## 核心流程

组件渲染时，`useModels()` 先通过 `useSession()` 读取登录态。随后创建 React Query 查询，query key 固定为 `["llm"]`，查询函数调用 `get("/api/models", ModelList, session?.accessToken)`。

这个查询有一个关键开关：`enabled: !!session?.accessToken`。也就是说，只要没有 token，它不会主动请求模型接口。这避免未登录或会话尚未恢复时发出无效请求。

请求成功后，`fetch-utils.get` 会把返回 JSON 交给 `ModelList` 校验。如果后端返回的字段缺失、类型不符，`zod` 会抛错，React Query 会把查询置为错误态。当前 hook 没有把 `isLoading`、`error` 暴露出去，而是只暴露业务需要的 `models` 和 `getModel`。因此调用方看到的是：没数据或请求失败时，`models` 都会表现为空数组。

在 `settings.tsx` 中，模型列表进入 `Combo` 下拉框；用户选中模型后，`updateModel(model)` 会先检查当前 `settings.maxTokens` 是否超过新模型的 `max_tokens`，如果超过就压低到新上限，然后把 `customModelName` 更新为该模型名。后续发起 Agent 请求时，`next/src/utils/interfaces.ts` 的 `toApiModelSettings` 会把 `customModelName` 和 `maxTokens` 转成后端请求体里的 `model`、`max_tokens`。

## 关键函数的高层作用

`useModels()` 是唯一核心函数。它把“认证会话”“远端模型接口”“响应结构校验”“前端模型选择组件需要的数据形状”封装到一起，让设置页不需要关心请求细节。

`getModel(name)` 是一个轻量辅助函数，只在已加载的 `query.data` 中做本地查找。它不触发网络请求，也不处理兜底逻辑。设置页在找不到模型时自己构造了一个 fallback：使用当前 `customModelName`、`max_tokens: 2000`、`has_access: true`，保证 UI 的 token 滑块仍能渲染。

`Model` / `ModelList` 的作用是运行时防线。它们不只是类型提示，而是会真正检查后端响应。如果后端模型字段从 `max_tokens` 改成 `maxTokens`，或者 `has_access` 不再返回布尔值，这里会直接解析失败。

## 修改风险

最大的风险是接口契约变更。`useModels.ts` 强依赖 `/api/models` 返回数组，且每项必须包含 `name`、`max_tokens`、`has_access`。如果后端新增字段通常没问题，但删除字段、改字段名、改类型都会导致整个查询失败，设置页模型列表变空。

第二个风险是缓存 key 过粗。当前 query key 是固定的 `["llm"]`，没有包含用户 id、access token 或组织 id。如果应用未来支持切换账号、组织或权限上下文，固定 key 可能复用旧模型列表。当前代码只读取 `session?.accessToken`，而 `fetch-utils.get` 其实支持 `organizationId`，但这里没有传。

第三个风险是错误状态被隐藏。`useModels()` 只返回 `models: query.data ?? []`，调用方无法区分“还没加载”“未登录”“接口失败”“返回空列表”。如果后续设置页要展示加载态、禁用下拉框或提示权限问题，需要扩展返回值，例如暴露 `isLoading`、`error`、`refetch`。

第四个风险是类型范围不一致。`LLMModel.name` 是任意字符串，但 `settings.tsx` 会把 `model.name as GPTModelNames` 写入设置；而 `GPTModelNames` 在 `next/src/types/modelSettings.ts` 中只允许 `"gpt-3.5-turbo"`、`"gpt-3.5-turbo-16k"`、`"gpt-4"`。如果后端返回新模型名，类型断言会绕过编译保护，但运行时设置可能进入旧类型系统没有覆盖的状态。修改这里时，应同步检查 `GPTModelNames`、默认设置、请求体生成和 UI 文案。
