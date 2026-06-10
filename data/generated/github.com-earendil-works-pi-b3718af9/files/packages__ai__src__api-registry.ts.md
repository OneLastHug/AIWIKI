# 文件：packages/ai/src/api-registry.ts
## 一句话定位
这是 `packages/ai` 里“文本/对话模型 provider 注册中心”的核心文件，负责把某个 `api` 标识映射到具体的流式生成实现，并向上层 `stream.ts` 提供统一的查找、注册、清理接口。

## 它暴露/定义了什么
它定义了两层类型：面向外部注册的 `ApiProvider`，以及内部存储用的 `ApiProviderInternal`。前者要求提供 `api`、`stream`、`streamSimple`，后者是经过包装后的运行时版本。文件还导出了 5 个关键函数：`registerApiProvider`、`getApiProvider`、`getApiProviders`、`unregisterApiProviders`、`clearApiProviders`。

底层实现只维护一个全局 `Map<string, RegisteredApiProvider>`，键是 `api` 字符串，值里除了 provider 本体，还可附带 `sourceId`，用于成组卸载。

## 谁调用它
最直接的调用者是 `packages/ai/src/stream.ts`：`stream()` 和 `streamSimple()` 会先通过 `getApiProvider(model.api)` 找到对应实现，再真正执行 provider 的流式函数。`packages/ai/src/providers/register-builtins.ts` 会在模块初始化时批量 `registerApiProvider`，把内建 provider 注入 registry。`packages/ai/src/providers/faux.ts` 也会用它注册测试/模拟 provider，并在结束时通过 `unregisterApiProviders` 清理。`packages/ai/src/index.ts` 只是把它整体 re-export 给包外使用。

## 它调用谁
这个文件本身几乎不依赖业务模块，只引入了 `./types.ts` 里的类型。运行时没有再去调用其他 provider 或网络逻辑，职责很纯：管理注册表和做一致性校验。

## 核心流程
核心流程很简单，但很关键。`registerApiProvider()` 会把外部传入的 `stream`、`streamSimple` 包装成内部函数：先检查 `model.api` 是否和注册时的 `api` 一致，不一致就直接抛错，避免 provider 被错误模型调用。然后把包装后的 provider 存入全局 `Map`，同时记录 `sourceId`。

查询时，`getApiProvider(api)` 只按 `api` 取值；`getApiProviders()` 则返回当前已注册 provider 的数组，适合调试或枚举。`unregisterApiProviders(sourceId)` 会遍历整个 registry，把同一 `sourceId` 的条目删掉，这通常用于某个模块或插件卸载。`clearApiProviders()` 是全量清空，主要面向测试或重置场景。

## 关键函数的高层作用
`wrapStream()` 和 `wrapStreamSimple()` 是这里最重要的保护层。它们不做业务转换，只做“接口对齐 + 防误用”两件事：确认 `model.api` 匹配当前 provider，再把类型收窄后转发给真正的实现。`registerApiProvider()` 则是把这种保护层固定进 registry，确保后续所有调用都经过校验。

## 修改风险
这个文件是全局状态中心，改动风险主要在三类。第一，`api` 与 `model.api` 的一致性校验如果放松或改坏，错误 provider 可能被静默调用，问题会扩散到所有流式请求。第二，`sourceId` 的生命周期管理如果出错，容易留下陈旧注册项，表现为“明明卸载了模块却还能被调用”。第三，`clearApiProviders()` 会影响整个进程内所有调用者，测试和并行任务里尤其敏感。

根据当前片段推断，它是 `packages/ai` 的基础设施层：看起来简单，但它决定了上层 `stream` 分发是否可靠，因此任何改动都应重点检查注册、卸载、以及 `api` 校验这三条路径。
