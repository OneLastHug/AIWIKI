# 文件：packages/coding-agent/src/core/agent-session-services.ts

## 一句话定位

`agent-session-services.ts` 是 `packages/coding-agent` 里“创建 AgentSession 之前的运行时服务装配层”：它把某个有效 `cwd` 下需要共用的配置、认证、模型注册、资源加载、扩展注册和诊断信息组装成 `AgentSessionServices`，再提供一个薄封装把这些服务交给真正的 `createAgentSession`。

## 它暴露/定义了什么

文件主要暴露四类 API：

`AgentSessionRuntimeDiagnostic`：运行时诊断结构，只有 `info`、`warning`、`error` 三种级别和一条 `message`。注释明确说明这些问题不会在这里直接打印或退出，而是返回给上层应用决定是否展示、是否中止启动。

`CreateAgentSessionServicesOptions`：创建 cwd 绑定服务的输入。核心字段是 `cwd`，可选传入 `agentDir`、`authStorage`、`settingsManager`、`modelRegistry`、扩展 flag 值、资源加载配置和 reload 配置。这里的设计允许测试或上层调用注入已有服务，也允许默认创建。

`AgentSessionServices`：服务容器，包含 `cwd`、`agentDir`、`AuthStorage`、`SettingsManager`、`ModelRegistry`、`ResourceLoader` 和 `diagnostics`。它是这个文件的核心产物。

`createAgentSessionServices` 与 `createAgentSessionFromServices`：前者负责创建服务容器，后者负责基于已有服务创建真正的 AgentSession。

## 谁调用它

直接引用点显示，生产代码里 `packages/coding-agent/src/main.ts` 调用 `createAgentSessionServices`，说明 CLI 或应用入口会先构建服务，再继续创建会话。`packages/coding-agent/src/core/agent-session-runtime.ts` 也引用 `AgentSessionServices`、`AgentSessionRuntimeDiagnostic` 和 `createAgentSessionServices`，根据当前片段推断，它负责持有当前 session 的服务状态，并在 cwd 改变或会话重建时复用这层装配逻辑。`packages/coding-agent/src/core/index.ts` 和 `packages/coding-agent/src/index.ts` 重新导出这些类型与函数，供包外 SDK 用户使用。

测试中，`packages/coding-agent/test/agent-session-runtime-events.test.ts`、`packages/coding-agent/test/agent-session-branching.test.ts`、`packages/coding-agent/test/suite/agent-session-runtime.test.ts` 以及多个 regression 测试直接构造 services，说明它也是会话运行时测试的基础夹具入口。

## 它调用谁

它调用 `resolvePath` 规范化 `cwd` 和可选 `agentDir`；调用 `getAgentDir` 获取默认 agent 数据目录；用 `AuthStorage.create(join(agentDir, "auth.json"))` 创建认证存储；用 `SettingsManager.create(cwd, agentDir)` 创建设置管理器；用 `ModelRegistry.create(authStorage, join(agentDir, "models.json"))` 创建模型注册表；实例化 `DefaultResourceLoader` 并调用 `reload` 加载资源、扩展和配置。

扩展相关逻辑通过 `resourceLoader.getExtensions()` 取得运行时扩展状态，然后把 `pendingProviderRegistrations` 注册到 `modelRegistry.registerProvider`。最后，`createAgentSessionFromServices` 调用 `./sdk.ts` 里的 `createAgentSession`，把 services 和模型、thinking、工具过滤、自定义工具、`sessionStartEvent` 等会话参数原样传下去。

## 核心流程

第一步，`createAgentSessionServices` 先把输入路径固定成绝对语义：`cwd` 必经 `resolvePath`，`agentDir` 要么来自选项，要么来自默认 `getAgentDir`。注释强调 CLI 传入的资源路径应提前解析成绝对路径，避免后续 cwd 切换后被重新解释。

第二步，创建或复用基础服务：认证、设置、模型注册表、资源加载器。这里的服务都绑定当前有效 `cwd`，所以如果 session 的工作目录切换，上层应重新创建这一组 services。

第三步，`DefaultResourceLoader.reload` 读取当前 cwd、agentDir 和 settings 下的资源。随后从扩展运行时状态里取出待注册 provider，逐个注册到 `ModelRegistry`。注册失败不会抛出终止，而是转为 `AgentSessionRuntimeDiagnostic` 的 `error`。

第四步，应用扩展 flag。`applyExtensionFlagValues` 先收集所有扩展声明的 flags，再校验用户传入的 flag 名称和值类型。未知 flag 和 string flag 缺值都会变成 error 诊断；boolean flag 只要出现就写入 `true`；string flag 需要实际字符串值。

第五步，返回完整 `AgentSessionServices`。真正创建会话时，上层再调用 `createAgentSessionFromServices`，让模型选择、工具选择、session manager 等会话级输入和这组 cwd 绑定服务组合起来。

## 关键函数的高层作用

`createAgentSessionServices` 是核心函数。它不是业务会话执行器，而是 session 运行前的依赖注入容器构建器。它负责路径归一化、默认服务创建、资源加载、扩展 provider 注册和诊断收集，最终保证上层拿到一组彼此一致、绑定同一 `cwd` 和 `agentDir` 的服务。

`createAgentSessionFromServices` 是边界适配函数。它不做额外决策，只把已有 services 拆开，加上 `sessionManager`、模型、thinking level、工具开关、自定义工具和启动事件，转交给 `createAgentSession`。这个拆分的意义是：调用方可以先创建 services，再基于 services 解析模型、工具和配置，最后才构造 AgentSession。

`applyExtensionFlagValues` 是辅助校验函数。它把 CLI 或调用方传入的扩展 flag 写入扩展 runtime，同时把未知 flag、缺少 string 值这类问题收集成诊断。

## 修改风险

最高风险在服务生命周期。`AgentSessionServices` 明确是 cwd-bound，如果把 `SettingsManager`、`ResourceLoader` 或 `ModelRegistry` 的创建时机改成跨 cwd 复用，可能导致 cwd 切换后读取旧资源、旧设置或旧扩展状态；相关 regression 测试名里已有 `reload-stale-resource-settings`，说明这类问题曾经出现过。

第二个风险是扩展 provider 注册顺序和清理。当前逻辑注册 `pendingProviderRegistrations` 后会清空数组，避免重复注册。若移除清空或把注册移动到 reload 之前，可能造成重复 provider、扩展模型不可见，或诊断时机改变。

第三个风险是诊断语义。这里刻意“不打印、不退出”，而是返回 `diagnostics`。如果改成抛异常或直接输出，会改变 CLI、SDK 和测试对启动错误的处理方式，尤其影响扩展配置错误、未知 flag 这类可聚合问题。

第四个风险是 flag 类型处理。boolean flag 当前忽略传入值并设为 `true`，string flag 必须有字符串值。调整这套规则会影响 CLI 选项解析与扩展 API 的契约，可能让已有扩展的参数行为变化。

第五个风险是 `createAgentSessionFromServices` 的透传完整性。新增 session 选项时，如果只改 `CreateAgentSessionOptions` 或 `createAgentSession`，却忘了在这里的 options 类型和透传对象中补齐，SDK 用户通过 services 创建 session 时会出现能力缺失。
