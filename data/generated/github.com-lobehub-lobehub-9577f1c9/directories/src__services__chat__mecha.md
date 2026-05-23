# 目录：src/services/chat/mecha

## 它负责什么

`src/services/chat/mecha` 是聊天服务里的“模型执行前装配层”。它不直接负责 UI，也不是后端数据库服务，而是把一次对话请求送进模型运行时之前需要准备的内容集中起来：解析当前 agent 配置、合并内置 agent 的运行时提示词、裁剪或注入工具、生成上下文消息、补齐模型扩展参数、读取客户端密钥配置，并把用户显式选择的 skill/tool 内容预加载到请求上下文中。

根据当前片段推断，用户给定的仓库根目录下没有直接发现 `src/services/chat/mecha`，可读到的同名实现位于 `project/lobehub/src/services/chat/mecha`。该目录与 `src/services/chat/index.ts`、`src/store/chat/slices/aiChat/actions/streamingExecutor.ts`、`src/store/chat/slices/aiChat/actions/conversationLifecycle.ts` 有直接调用关系，因此这里可以视为聊天发送链路中“从前端 store 状态到模型 runtime payload”的核心拼装模块。

这个目录的命名 `mecha` 可以理解为“机械核心”：它把 agent、model、tool、skill、memory、context-engine 等多个子系统的状态装配成模型可消费的结构。它本身不是一个独立业务页面，也不是单一算法文件，而是一组面向聊天执行流程的 resolver、composer、preloader。

## 直接子目录地图

该目录当前没有直接子目录，全部是一层 TypeScript 文件与测试文件。地图式看，可以分成几组：

- 统一出口：`src/services/chat/mecha/index.ts`，集中导出本目录对外使用的能力。
- Agent 配置解析：`src/services/chat/mecha/agentConfigResolver.ts`，负责决定当前请求使用普通 agent 还是 builtin agent，并合并 system role、plugins、chatConfig。
- 上下文工程：`src/services/chat/mecha/contextEngineering.ts`，负责把消息历史、系统提示、工具说明、群组上下文、记忆、文档、运行时 step context 等交给 context-engine 生成最终模型消息。
- 模型运行与参数：`src/services/chat/mecha/clientModelRuntime.ts`、`src/services/chat/mecha/modelParamsResolver.ts`，分别负责初始化客户端模型 runtime，以及根据模型能力生成扩展参数。
- 工具与技能装配：`src/services/chat/mecha/toolSetComposer.ts`、`src/services/chat/mecha/toolPreload.ts`、`src/services/chat/mecha/skillEngineering.ts`、`src/services/chat/mecha/skillPreload.ts`，分别覆盖 tool manifest 合并、用户选中 tool 内容预加载、客户端 skill set 生成、用户选中 skill 内容预加载。
- 记忆辅助：`src/services/chat/mecha/memoryManager.ts`，负责从 user memory store 读取 persona 和 topic memories，并组合成 `UserMemoryData`。
- 测试：同目录下的 `*.test.ts` 覆盖 resolver、context engineering、tool composer、model params、runtime 初始化等关键行为。

## 关键入口

最重要的入口是 `src/services/chat/mecha/index.ts`。上层通常不直接关心目录内文件拆分，而是从这里导入 `resolveAgentConfig`、`contextEngineering`、`initializeWithClientStore`、`resolveModelExtendParams`、`combineUserMemoryData`、`resolveTopicMemories`、`resolveUserPersona`、`composeEnabledTools` 等函数。

`resolveAgentConfig` 是 agent 维度入口。它从 agent store 和 group store 读取配置，判断 agent 是否是 `@lobechat/builtin-agents` 里的内置 slug；如果是内置 agent，会调用 `getAgentRuntimeConfig` 生成运行时 system role、plugins、chatConfig。如果处在 page 或 task scope，还会自动注入 `PageAgentIdentifier` 或 `TaskIdentifier` 对应的工具与提示词。它也处理一些执行场景约束，例如 `disableTools`、`isSubAgent`、非 page scope 下移除 page-agent、群组 supervisor 特殊识别等。

`contextEngineering` 是上下文维度入口。它接收 `messages`、`manifests`、`tools`、`model`、`provider`、`systemRole`、`historySummary`、`agentDocuments`、`groupId`、`agentId`、`initialContext`、`stepContext`、`memoryContext` 等输入，然后借助 `@lobechat/context-engine` 的能力生成最终 `OpenAIChatMessage[]`。从导入和代码结构看，它会融合工具 manifest、builtin tool 场景、群组成员信息、Agent Builder/Group Agent Builder/Agent Management 上下文、Klavis/Creds 信息、用户记忆、topic 引用、notebook 文档、历史摘要等。

`initializeWithClientStore` 是模型 runtime 入口。它通过 `createPayloadWithKeyVaults(provider)` 从客户端 store 组合供应商鉴权配置，再调用 `ModelRuntime.initializeWithProvider` 初始化模型运行时，并默认加入 `dangerouslyAllowBrowser: true`，说明这里服务于浏览器侧模型调用场景。

`resolveModelExtendParams` 是模型参数入口。它通过 `aiModelSelectors` 查询当前 provider/model 是否支持扩展参数，再把 chatConfig 里的 reasoning、thinking、effort、verbosity、URL context、图片比例和分辨率等配置转换成 runtime 需要的参数形态。

## 主流程位置

发送消息主流程主要不在 `mecha` 目录里启动，而是在上游调用它。

第一段在 `src/store/chat/slices/aiChat/actions/conversationLifecycle.ts`。这里会在会话生命周期中调用 `resolveSelectedSkillsWithContent` 和 `resolveSelectedToolsWithContent`，把用户消息中显式选择的 `<skill ... />`、`<tool ... />` 或旧格式 `<action ... />` 解析出来，并尽量附加对应内容。skill 侧可能读取 builtin skills、agent skills，并在 creds skill 场景注入用户凭据摘要；tool 侧主要从 builtin tools 或 installed plugins 的 manifest 里提取 systemRole 与 API 描述。

第二段在 `src/store/chat/slices/aiChat/actions/streamingExecutor.ts`。这里是 agent 执行状态组装的位置，会调用 `resolveAgentConfig` 得到本次回复 agent 的最终配置，再调用 `composeEnabledTools` 合并工具清单。`composeEnabledTools` 的一个关键保护是：当 scope 是 page 但 page editor 未挂载时，会丢弃 page-agent 工具，避免模型调用过期 editor 引用。

第三段在 `src/services/chat/index.ts`。这是 chat service 更靠近模型调用的主入口：它调用 `contextEngineering` 生成模型消息，调用 `resolveModelExtendParams` 生成模型扩展参数，并在需要客户端模型能力时调用 `initializeWithClientStore`。因此阅读主流程时，不应只看 `mecha`，还要把它放回 `chat service -> streaming executor -> conversation lifecycle` 的链路里理解。

## 推荐阅读顺序

1. 先读 `src/services/chat/mecha/index.ts`，建立本目录对外 API 的边界感。
2. 再读 `src/store/chat/slices/aiChat/actions/streamingExecutor.ts` 中调用 `resolveAgentConfig` 和 `composeEnabledTools` 的片段，理解它在发送链路中的位置。
3. 接着读 `src/services/chat/mecha/agentConfigResolver.ts`，重点看普通 agent、builtin agent、page scope、task scope、group supervisor、sub-agent 这些分支。
4. 然后读 `src/services/chat/mecha/contextEngineering.ts`，只抓输入来源和输出目的，不必一开始深挖每种 builtin tool 的上下文注入细节。
5. 再读 `src/services/chat/mecha/modelParamsResolver.ts` 和 `src/services/chat/mecha/clientModelRuntime.ts`，理解模型能力与 provider runtime 初始化。
6. 最后读 `toolPreload.ts`、`skillPreload.ts`、`toolSetComposer.ts`、`skillEngineering.ts`、`memoryManager.ts`，补齐 tool、skill、memory 的辅助装配逻辑。

## 常见误区

不要把 `mecha` 当成“真正调用所有模型 API 的地方”。它更像执行前的装配层，实际模型 runtime 来自 `@lobechat/model-runtime`，上游服务入口在 `src/services/chat/index.ts`。

不要把 `contextEngineering.ts` 理解成简单的 prompt 拼接文件。它会读取多个 store，处理群组、工具、记忆、文档、历史摘要、step context 等，职责是把复杂客户端状态转换成 context-engine 可生成的模型消息。

不要忽略 `agentConfigResolver.ts` 里的 scope 分支。page、task、group、sub-agent、broadcast 场景会改变 tools/plugins/systemRole，很多“为什么模型看到了某个工具”或“为什么某个工具被移除”的答案都在这里。

不要以为 `plugins`、`tools`、`manifests` 是同一层概念。`plugins` 更像 agent 配置中的启用标识；`manifests` 是工具描述与 API 元数据；`tools` 是最终传给模型 function/tool calling 的结构。`toolSetComposer.ts` 正是在这些层之间做合并与过滤。

不要以为 memory 会在发送时发起网络请求。`memoryManager.ts` 明确只从缓存读取 topic memories，注释说明相关数据应由 ChatList 的 SWR 预加载，避免发送消息被记忆检索网络请求阻塞。

不要跳过测试文件。虽然本文不逐文件展开，但 `agentConfigResolver.test.ts`、`contextEngineering.test.ts`、`modelParamsResolver.test.ts`、`toolSetComposer.test.ts` 覆盖了大量边界场景，是理解这个目录真实行为的高密度材料。
