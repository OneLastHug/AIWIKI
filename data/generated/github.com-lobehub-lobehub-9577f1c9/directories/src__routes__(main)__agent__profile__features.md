# 目录：src/routes/(main)/agent/profile/features

## 它负责什么

`src/routes/(main)/agent/profile/features` 是桌面主路由下“Agent Profile 编辑页”的局部功能目录。它支撑的是 `src/routes/(main)/agent/profile/index.tsx` 这个页面：左侧主区域用于编辑当前 Agent 的头像、名称、模型、工具、系统提示词、进阶设置与发布状态，右侧还会挂载 `AgentBuilder` 面板。

这个目录的核心职责可以分成三层：

1. 页面级编辑体验：`ProfileEditor`、`EditorCanvas`、`Header` 共同组成 Agent 配置编辑页面。
2. 局部编辑器状态：`store/`、`ProfileProvider`、`StoreUpdater`、`ProfileHydration` 管理富文本编辑器实例、编辑器状态、保存快捷键和防抖保存。
3. 与全局 Agent 数据联动：大量读写来自 `@/store/agent` 的 `useAgentStore`，包括当前 Agent 的 `meta`、`config`、`systemRole`、`editorData`、保存状态、发布信息、异构 Agent 配置等。

需要特别注意：这个目录虽然位于 `src/routes/.../features`，但它承担了较重的业务 UI 和状态逻辑，并不是传统意义上“薄 route”。这是当前代码的实际结构；从仓库约定看，新增大型业务逻辑更推荐迁移或沉淀到 `src/features/` 下。

## 关键组成

`ProfileProvider.tsx` 是局部 Zustand store 的 Provider。它通过 `useEditor()` 取得 `@lobehub/editor` 的编辑器实例，然后调用本目录 `store/createStore({ editor })` 创建页面局部 store，并挂载 `StoreUpdater`。也就是说，富文本编辑器实例不是直接到处传 props，而是放进本页面的 `useProfileStore` 里共享。

`store/` 是这个目录自己的局部状态层：

- `index.ts`：使用 `zustand/traditional` 的 `createWithEqualityFn` 和 `subscribeWithSelector` 创建 store，并通过 `zustand-utils/createContext` 暴露 `Provider`、`useProfileStore`、`useStoreApi`。
- `initialState.ts`：定义 `editor`、`editorState`、`streamingContent`、`streamingInProgress` 等局部状态。
- `action.ts`：定义编辑器保存与流式写入相关动作，例如 `handleContentChange`、`flushSave`、`startStreaming`、`appendStreamingContent`、`finishStreaming`。
- `selectors.ts`：目前只提供 `editor` 和 `editorState` 两个 selector。

`StoreUpdater.tsx` 负责把 `useEditorState(editor)` 得到的编辑器状态同步回 `useProfileStore`。后续 `EditorCanvas/useSlashItems.tsx` 会使用 `editorState?.codeblock()` 这类命令，所以这里相当于把编辑器运行态暴露给斜杠菜单等 UI。

`ProfileHydration.tsx` 负责快捷键挂载。它读取 `flushSave`，调用 `useRegisterFilesHotkeys()` 和 `useSaveDocumentHotkey(flushSave)`，让保存快捷键可以触发当前编辑器的防抖保存 flush。

`Header/` 是页面顶部操作栏。`Header/index.tsx` 使用 `NavHeader`，左侧展示自动保存状态、市场状态、审核状态、fork 来源，右侧提供更多菜单和右侧 AgentBuilder 面板开关。更多菜单里包含：

- 打开高级设置：`useAgentStore.setState({ showAgentSetting: true })`
- 发布到社区：走 `useMarketPublish`
- 删除 Agent：调用 `useHomeStore((s) => s.removeAgent)`，成功后 `navigate('/')`

`Header/AgentPublishButton/useMarketPublish.ts` 封装发布流程。它从 `useAgentStore` 读取当前 Agent 的 `meta`、`config`、`systemRole`、模型、插件、聊天配置等，再通过 `lambdaClient.market.agent.publishOrCreate.mutate` 提交到市场。它还会用 `checkOwnership` 判断当前用户是否需要 fork 确认。

`ProfileEditor/` 是页面主体编辑表单。`ProfileEditor/index.tsx` 读取当前 Agent 配置并判断是否是异构 Agent：

- 普通 Agent：显示 `ModelSelect`、`AgentTool`、`EditorCanvas`、`AgentSettings`。
- 异构 Agent：显示 `CloudHeterogeneousConfig` 和 `HeterogeneousAgentStatusCard` 的 tabs，用于配置 cloud/desktop 环境下的异构 provider 参数。

`ProfileEditor/AgentHeader.tsx` 负责头像、背景色和标题编辑。头像支持 emoji、模型头像、自定义上传和删除；标题本地维护 `localTitle`，再用 `useDebounceFn` 防抖调用 `updateMeta({ title })`，避免输入时频繁写全局 store。

`ProfileEditor/AgentTool.tsx` 只是一个适配层，复用 `@/features/ProfileEditor` 导出的 `AgentTool`，并固定传入 `filterAvailableInWeb`、`showWebBrowsing`、`useAllMetaList`。这说明工具配置 UI 的通用实现不在当前目录，而在全局 feature 中。

`EditorCanvas/` 是系统提示词富文本编辑器：

- `index.tsx` 挂载 `@lobehub/editor/react` 的 `Editor`。
- 初始内容优先使用 `config.editorData`，没有结构化 editorData 时回退到 `config.systemRole`。
- `onTextChange` 调用本地 store 的 `handleContentChange(updateConfig)`，最终把 markdown 和 json 两份内容保存到 Agent config。
- 编辑器启用聊天输入富文本插件、表格、mention、toolbar 和 slash menu。
- `useSlashItems.tsx` 定义 `/h1`、`/h2`、`/ul`、`/table`、`/tex`、`/codeblock` 等斜杠菜单命令。
- `TypoBar.tsx` 根据命名推断是编辑器 toolbar，当前片段没有展开阅读，作用应是富文本排版工具条。

`AgentSettings/` 是高级设置弹窗。`AgentSettings/index.tsx` 监听全局 `useAgentStore((s) => s.showAgentSetting)`，打开一个 `@lobehub/ui` 的 `Modal`。`Content.tsx` 内部复用 `@/features/AgentSetting` 的 `AgentSettings` 组件，并提供侧边菜单，目前可见 tab 包括 opening 和 self iteration。它通过 `optimisticUpdateAgentConfig`、`optimisticUpdateAgentMeta` 保存高级设置。

## 上下游关系

上游页面是 `src/routes/(main)/agent/profile/index.tsx`。该页面用 `ProfileProvider` 包裹整个编辑区，然后渲染 `ProfileArea` 和 `AgentBuilder`。`ProfileArea` 内部根据 `useAgentStore(agentSelectors.isAgentConfigLoading)` 决定显示 loading 还是页面内容，加载完成后渲染 `Header` 和 `ProfileEditor`。

主要上游状态来自 `@/store/agent`：

- `agentSelectors.currentAgentConfig`：当前 Agent 的模型、provider、systemRole、editorData、agencyConfig 等。
- `agentSelectors.currentAgentMeta`：头像、标题、描述、背景色、市场 identifier 等。
- `agentSelectors.currentAgentSystemRole`：发布校验和 token 统计使用。
- `updateAgentConfig`、`updateAgentMeta`、`optimisticUpdateAgentConfig`、`optimisticUpdateAgentMeta`：保存配置和元信息。
- `saveStatus`、`lastUpdatedTime`：给 `AutoSaveHint` 展示保存状态。
- `showAgentSetting`：控制高级设置弹窗显隐。
- `streamingSystemRole`、`streamingSystemRoleInProgress`：驱动 `EditorCanvas` 的流式系统提示词更新。

其他重要依赖包括：

- `@lobehub/editor` / `@lobehub/editor/react`：富文本编辑器、editor state、插件和命令。
- `@/features/ModelSelect`：模型选择器。
- `@/features/ProfileEditor`：复用通用 `AgentTool`。
- `@/features/AgentSetting`：复用高级设置主体。
- `@/features/AgentBuilder`：页面右侧构建器，由上层页面挂载。
- `@/services/marketApi`：查询 Agent 市场状态、版本审核状态、fork 来源。
- `lambdaClient.market.agent`：发布或更新社区 Agent。
- `@/layout/AuthProvider/MarketAuth`：发布前市场登录鉴权。
- `@/store/global`：控制右侧面板、语言、feature flag 等。
- `@/store/file`：头像文件上传。
- `@/store/home`：删除 Agent 后更新首页/会话列表状态。

下游输出主要是对全局 Agent store 的更新：用户改标题、头像、模型、工具、提示词或高级设置时，最终都会写回 `useAgentStore` 所管理的当前 Agent 数据；发布流程则进一步把这些数据打包提交到市场接口。

## 运行/调用流程

页面进入 `src/routes/(main)/agent/profile/index.tsx` 后，最外层 `Suspense` 显示 `Loading` 作为兜底。随后 `ProfileProvider` 创建本页面局部 store，把 `@lobehub/editor` 实例注入进去，并让 `StoreUpdater` 持续同步 `editorState`。

`ProfileArea` 先检查当前 Agent 配置是否加载中。如果 `isAgentConfigLoading` 为真，显示 `BrandTextLoading`；否则渲染顶部 `Header` 和主体 `ProfileEditor`。外层内容区绑定了点击聚焦逻辑：用户点击编辑区域空白处时，会调用 `editor?.focus()` 聚焦富文本编辑器。

`Header` 渲染后会根据当前 Agent 的 `marketIdentifier` 异步查询市场状态、fork 来源和版本审核状态。用户点击更多菜单中的“高级设置”时，只是把 `showAgentSetting` 设为 true，真正的弹窗由 `ProfileEditor` 末尾的 `AgentSettings` 组件响应并打开。用户点击发布时，`Header` 会先校验名称和 systemRole，再检查是否处于审核中，然后弹确认框；确认后如果未登录市场则先 `signIn()`，最后调用 `useMarketPublish().publish()`。

`ProfileEditor` 读取当前 Agent config。若当前 Agent 是异构 Agent，则不显示模型选择和普通工具配置，而是显示 cloud/desktop 的异构配置 tabs。若是普通 Agent，则先显示 `AgentHeader`，然后是 `ModelSelect` 和 `AgentTool`，之后进入 `EditorCanvas`。

`EditorCanvas` 初始化时会判断 `editorData` 是否存在且有 `root` 字段。有结构化编辑器数据时调用 `editor.setDocument('json', editorData)`；否则如果有 `systemRole`，调用 `editor.setDocument('markdown', systemRole)`。用户编辑文本触发 `onTextChange`，`handleContentChange(updateConfig)` 会从编辑器同时读取 markdown 和 json，并通过防抖保存为：

```ts
{
  editorData: structuredClone(jsonContent || {}),
  systemRole: markdownContent || '',
}
```

保存不是立即每次请求，而是由 `EDITOR_DEBOUNCE_TIME` 和 `EDITOR_MAX_WAIT` 控制的 debounced save。快捷键保存则通过 `ProfileHydration` 调用 `flushSave()`，把等待中的保存立刻提交。

流式生成系统提示词时，`EditorCanvas` 会监听全局 `streamingSystemRole` 和 `streamingSystemRoleInProgress`。流式过程中它直接 `editor.setDocument('markdown', streamingSystemRole || '')`，并阻止普通 `onTextChange` 保存；当流式结束后延迟 100ms 再调用 `handleContentChange(updateConfig)`，确保编辑器内部 json 状态完成同步后再保存。

## 小白阅读顺序

1. 先读 `src/routes/(main)/agent/profile/index.tsx`  
   这里能看到整个页面的骨架：`ProfileProvider`、`Header`、`ProfileEditor`、`ProfileHydration`、`AgentBuilder` 是如何组合的。

2. 再读 `features/ProfileProvider.tsx` 和 `features/store/index.ts`  
   理解为什么当前目录有一个局部 `useProfileStore`，以及它和全局 `useAgentStore` 不是同一个东西。

3. 读 `features/store/action.ts`  
   重点看 `handleContentChange`、`flushSave`、`startStreaming`、`finishStreaming`。这几个函数解释了提示词编辑、结构化 editorData、markdown systemRole、防抖保存之间的关系。

4. 读 `features/ProfileEditor/index.tsx`  
   这里是主体分支逻辑：普通 Agent 和异构 Agent 的 UI 完全不同。普通 Agent 走模型、工具、提示词编辑；异构 Agent 走 cloud/desktop provider 配置。

5. 读 `features/EditorCanvas/index.tsx`  
   这是最重要的编辑器文件。理解初始化优先级、`onTextChange` 保存、streaming 期间禁止保存、streaming 结束后补保存这几段逻辑，基本就能掌握系统提示词编辑链路。

6. 读 `features/Header/index.tsx` 和 `Header/AgentPublishButton/useMarketPublish.ts`  
   理解顶部状态、打开高级设置、删除 Agent、发布到社区、fork 确认、审核状态等页面级动作。

7. 最后读 `features/AgentSettings/Content.tsx`  
   它说明高级设置弹窗并没有在本目录重新实现所有设置项，而是复用 `@/features/AgentSetting` 的通用设置组件。

## 常见误区

1. 误以为 `useProfileStore` 保存的是 Agent 数据  
   实际上当前目录的 `useProfileStore` 主要保存编辑器实例、编辑器状态和流式编辑辅助状态。真正的 Agent 配置和元信息在 `@/store/agent` 的 `useAgentStore` 里。

2. 误以为提示词只保存 markdown  
   `EditorCanvas` 保存时同时写 `systemRole` 和 `editorData`。`systemRole` 是 markdown 文本，便于模型使用；`editorData` 是编辑器 json 状态，便于恢复富文本结构。初始化时也优先恢复 `editorData`，没有时才回退到 `systemRole`。

3. 误以为 `AgentSettings` 是独立设置页面  
   它只是一个弹窗壳。真正的设置内容来自 `@/features/AgentSetting`，当前目录只负责把当前 Agent 的 `config`、`meta`、`id` 和更新回调传进去。

4. 误以为发布按钮只是简单提交当前表单  
   发布流程会校验名称和 systemRole、检查审核状态、处理市场登录、检查 ownership、必要时 fork 确认，并把模型、插件、聊天参数、tokenUsage、editorData、tags 等一起提交到 `lambdaClient.market.agent.publishOrCreate.mutate`。

5. 误以为普通 Agent 和异构 Agent 共享同一套编辑 UI  
   `ProfileEditor/index.tsx` 明确分支：异构 Agent 显示 `CloudHeterogeneousConfig` 和 `HeterogeneousAgentStatusCard`，不会显示普通的 `ModelSelect` 和 `AgentTool`。同时 `Header` 里右侧 AgentBuilder 面板开关也对异构 Agent 隐藏。

6. 误以为流式生成期间会走普通输入保存  
   `EditorCanvas` 在 `streamingInProgress` 为真时直接 return，不触发普通 `handleContentChange`。流式结束后才延迟保存，避免 editor json 状态还没更新就被读取。

7. 误以为 `Header/AgentPublishButton` 下所有文件都一定由 `AgentPublishButton/index.tsx` 统一挂载  
   从当前片段看，`Header/index.tsx` 直接使用了 `ForkConfirmModal`、`PublishResultModal` 和 `useMarketPublish`，而不是只通过一个按钮组件完成发布。阅读时应以 `Header/index.tsx` 的实际 import 为准。

8. 误把这个目录当成纯 route segment  
   按仓库规范，`src/routes` 通常应保持页面段较薄，业务逻辑放到 `src/features`。但这个目标目录实际包含较多 feature 级逻辑，是当前页面的局部实现。后续新增大块逻辑时，应留意是否更适合沉淀到全局 `src/features/`。
