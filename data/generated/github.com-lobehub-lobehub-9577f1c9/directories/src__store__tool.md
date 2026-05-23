# 目录：src/store/tool

## 它负责什么

`src/store/tool` 是 LobeHub 前端工具体系的 Zustand store 聚合层，负责把“工具”相关的多种来源统一成一个 `useToolStore`：普通插件、自定义插件、内置工具、MCP 插件市场、Klavis MCP 服务、LobeHub Skill、Agent Skill、Agent Document Skills 等，都在这里组合状态、动作和选择器。

从职责上看，它不是某一个工具的具体业务实现目录，而是工具能力的客户端状态中枢。它保存安装列表、工具 manifest、加载状态、工具配置、服务连接状态、技能列表等数据；提供安装、卸载、刷新、调用、校验、连接测试等 action；再通过 selector 把不同来源的工具合并成 UI 或运行时需要的视图，例如工具元信息列表、可发现工具列表、某个工具的 manifest、某个 API 的展示控制等。

这个目录采用典型的 LobeHub Zustand 分片模式：每个业务来源放在 `slices/<name>` 下，分片导出 `initialState`、`action`、`selectors`，最后由 `store.ts` 聚合为一个完整的 `ToolStore`。

## 直接子目录地图

`src/store/tool/selectors` 是跨分片的统一 selector 层。核心文件是 `src/store/tool/selectors/tool.ts`，它会组合内置工具、已安装插件、LobeHub Skill、Klavis 服务等来源，形成 `toolSelectors.metaList`、`discoverableMetaList`、`availableToolsForDiscovery`、`getManifestById`、`isToolHasUI` 等统一查询入口。

`src/store/tool/slices` 是工具 store 的主要业务分片目录。它下面不是按页面划分，而是按工具来源或工具类型划分。

`src/store/tool/slices/plugin` 管理普通插件，包括已安装插件、插件 manifest、插件设置、插件安装状态、刷新和校验等。

`src/store/tool/slices/customPlugin` 管理用户自定义插件，包括新增、安装、重装、卸载、更新，以及编辑中的 `newCustomPlugin` 状态。

`src/store/tool/slices/builtin` 管理内置工具。它还包含一个更深的 `executors` 目录，放置内置工具调用执行器，例如 web browsing、message、notebook、page agent、agent documents、skills 等。这个分片不仅维护内置工具安装/卸载状态，也负责 `invokeBuiltinTool` 这类运行时调用入口。

`src/store/tool/slices/mcpStore` 管理 MCP 插件市场和安装流程，包括 MCP 插件列表、分页、安装进度、连接测试、取消安装、卸载等。

`src/store/tool/slices/klavisStore` 管理 Klavis 服务连接。它保存用户连接的 Klavis servers、server tools，并提供创建、授权完成、刷新工具、移除和调用 Klavis tool 的 action。

`src/store/tool/slices/lobehubSkillStore` 管理 LobeHub Skill 服务连接和工具调用，包括 provider 状态、授权 URL、token 刷新、工具列表刷新、撤销授权和 `callLobehubSkillTool`。

`src/store/tool/slices/agentSkills` 管理用户或 Agent 相关技能，包括创建、更新、删除、导入、刷新、获取详情等。

`src/store/tool/slices/agentDocumentSkills` 管理某个 Agent 的文档技能列表，提供刷新、清空和 SWR 拉取入口。

## 关键入口

`src/store/tool/index.ts` 是外部导出的轻量入口，只导出 `helpers`，以及 `getToolStoreState`、`useToolStore`。业务代码通常不直接关心内部 store 组合细节，而是从这里拿 store hook 或辅助函数。

`src/store/tool/store.ts` 是最核心的聚合入口。它定义 `ToolStore` 类型，将 `ToolStoreState` 与各分片 action 类型合并；然后在 `createStore` 中展开 `initialState`，再用 `flattenActions` 组合 `createPluginSlice`、`createCustomPluginSlice`、`createBuiltinToolSlice`、`createMCPPluginStoreSlice`、`createKlavisStoreSlice`、`createLobehubSkillStoreSlice`、`createAgentSkillsSlice`、`createAgentDocumentSkillsSlice` 和 `ToolStoreResetAction`。最后通过 `createWithEqualityFn` 创建 `useToolStore`，接入 devtools 名称 `tools`，并通过 `expose('tool', useToolStore)` 暴露调试入口。

`src/store/tool/initialState.ts` 是状态聚合入口。它把各分片的 `initialPluginState`、`initialCustomPluginState`、`initialBuiltinToolState`、`initialMCPStoreState`、`initialKlavisStoreState`、`initialLobehubSkillStoreState`、`initialAgentSkillsState`、`initialAgentDocumentSkillsState` 合并成 `initialState`。如果要理解 store 里有哪些顶层状态字段，应先看这里，再进入对应分片的 `initialState.ts`。

`src/store/tool/helpers.ts` 是偏展示和表单辅助的工具函数集合，例如读取插件标题、描述、标签、头像，判断是否是自定义插件，判断 settings schema 是否为空。它不负责状态流转。

## 主流程位置

工具数据加载主流程分散在各 slice 的 action 中。普通插件走 `src/store/tool/slices/plugin/action.ts`，关键方法包括 `refreshPlugins`、`useFetchInstalledPlugins`、`updatePluginSettings`、`validatePluginSettings`。自定义插件走 `src/store/tool/slices/customPlugin/action.ts`，关键方法包括 `installCustomPlugin`、`reinstallCustomPlugin`、`uninstallCustomPlugin`、`updateCustomPlugin`。

内置工具调用主流程在 `src/store/tool/slices/builtin/action.ts` 和 `src/store/tool/slices/builtin/executors/index.ts`。前者提供 `invokeBuiltinTool`、`transformApiArgumentsToAiState`、`toggleBuiltinToolLoading` 等 store action；后者提供 `getExecutor`、`hasExecutor`、`invokeExecutor` 等执行器注册和调度入口。具体内置工具的执行逻辑在 `src/store/tool/slices/builtin/executors/*` 下。

MCP 相关主流程在 `src/store/tool/slices/mcpStore/action.ts`，包括 `useFetchMCPPluginList`、`installMCPPlugin`、`updateMCPInstallProgress`、`testMcpConnection`、`uninstallMCPPlugin`。Klavis 与 LobeHub Skill 的连接和远程工具调用分别在 `src/store/tool/slices/klavisStore/action.ts`、`src/store/tool/slices/lobehubSkillStore/action.ts`。

工具在 UI 或发现流程中的统一读取位置是 `src/store/tool/selectors/tool.ts`。例如 `availableToolsForDiscovery` 会根据当前状态把内置工具、已安装插件、已连接 Klavis servers、已连接 LobeHub Skill servers 合并为可发现工具列表，并做去重与环境可用性过滤。根据当前片段推断，这个 selector 是“激活工具 / 工具发现”类功能的重要数据来源，依据是代码注释明确提到 `activateTools`，并且它直接构建跨来源的 discoverable tools。

## 推荐阅读顺序

建议先读 `src/store/tool/store.ts`，理解 `ToolStore` 如何由多分片合成，以及 `useToolStore` 如何创建和暴露。

第二步读 `src/store/tool/initialState.ts`，建立顶层状态字段的地图。这里能快速知道这个 store 覆盖哪些工具来源。

第三步读 `src/store/tool/selectors/tool.ts`，因为它展示了不同来源的工具如何被统一成应用可消费的数据模型，尤其是 `metaList`、`discoverableMetaList`、`availableToolsForDiscovery`。

第四步按业务目标进入分片。如果关心插件安装，读 `slices/plugin` 和 `slices/customPlugin`；如果关心内置工具运行，读 `slices/builtin/action.ts` 和 `slices/builtin/executors/index.ts`；如果关心 MCP 市场，读 `slices/mcpStore`；如果关心第三方服务连接，读 `slices/klavisStore`、`slices/lobehubSkillStore`；如果关心 Agent 技能，读 `slices/agentSkills`、`slices/agentDocumentSkills`。

第五步再看测试文件，例如 `builtinToolRegistry.test.ts`、各 slice 下的 `*.test.ts` 和 selector 测试，用来确认边界行为，而不是一开始就从测试反推结构。

## 常见误区

不要把 `src/store/tool` 理解成“工具 UI 组件目录”。它主要是 Zustand 状态与 action 层，UI 展示通常在其他 `features` 或组件目录中消费这里的 store 和 selectors。

不要只看 `slices/plugin` 就认为所有工具都是插件。当前目录把 builtin tools、custom plugins、MCP、Klavis、LobeHub Skill、Agent Skills 都纳入同一个 store，但它们的数据来源、安装方式和调用路径并不相同。

不要绕过聚合 selector 自己拼工具列表。`toolSelectors` 已经处理了跨来源合并、环境可用性、隐藏/可发现规则、Klavis 和 LobeHub Skill 去重等逻辑。直接读取单个 state 字段可能导致 UI 与实际工具发现结果不一致。

不要把 `builtin` 分片只当成静态 manifest 列表。它下面的 `executors` 是内置工具真正执行的位置，`invokeBuiltinTool` 会和执行器调度产生关系。

不要忽略 `flattenActions`。这个 store 的 slice action 多为 class-based action，不能简单假设对象展开就能保留方法绑定。`store.ts` 使用 `flattenActions` 是为了符合当前 Zustand action 组织规范。

不要把 `useFetch*` action 当成普通异步函数看待。这里很多 `useFetchInstalledPlugins`、`useFetchMCPPluginList`、`useFetchAgentSkills`、`useFetchProviderTools` 返回的是 SWR response，更接近 React hook 风格的数据订阅入口，调用位置需要符合 React 使用习惯。
