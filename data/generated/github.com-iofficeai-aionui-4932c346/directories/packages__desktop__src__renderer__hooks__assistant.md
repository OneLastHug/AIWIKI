# 目录：packages/desktop/src/renderer/hooks/assistant

## 它负责什么

`packages/desktop/src/renderer/hooks/assistant` 是渲染进程里“助手管理”页面和引导页共用的一组 React Hooks。它不直接渲染 UI，而是把助手列表、助手编辑抽屉、技能选择、后端执行引擎检测等状态与操作封装起来，供页面组件组合使用。

从当前代码看，这个目录主要服务两个入口场景：设置页的 `packages/desktop/src/renderer/pages/settings/AssistantSettings/index.tsx`，以及引导页组件 `packages/desktop/src/renderer/pages/guid/components/AssistantSelectionArea.tsx`。两处都通过 `@/renderer/hooks/assistant` 引入 `useAssistantList`、`useDetectedAgents`、`useAssistantEditor`，再把这些 hook 返回的数据和 handler 传给 `AssistantEditDrawer`、删除确认弹窗、技能确认弹窗等 UI 组件。

它的边界比较清晰：前端状态管理在这里，真正的持久化、文件读写、助手增删改查、agent 扫描则通过 `ipcBridge` 进入 preload/main 侧。例如助手列表来自 `ipcBridge.assistants.list.invoke()`，创建、更新、删除分别走 `ipcBridge.assistants.create/update/delete`，规则和技能文件读写走 `ipcBridge.fs.readAssistantRule`、`writeAssistantRule`、`readAssistantSkill`，执行引擎刷新走 `ipcBridge.acpConversation.refreshCustomAgents.invoke()`。

## 直接子目录地图

这个目录当前没有直接子目录，只有一层 hook 文件：

`index.ts` 是聚合导出入口，统一暴露 `useDetectedAgents`、`AvailableBackend` 类型、`useAssistantEditor`、`useAssistantList`。

`useAssistantList.ts` 负责助手列表读取、排序、当前选中助手维护，以及判断 extension 来源助手的工具函数。

`useAssistantEditor.ts` 是本目录中最核心、状态最多的 hook，负责创建、编辑、复制、保存、删除、启停助手，以及编辑抽屉内的规则、技能、自定义技能、内置自动技能等状态。

`useDetectedAgents.ts` 负责读取当前可用的执行后端或扩展 agent，并转换成下拉选择器可直接使用的 `AvailableBackend[]`。

因此这里不是“组件目录”，而是一个面向助手管理领域的 hooks 小模块。UI 组件、样式、类型定义和工具函数分散在相邻目录，尤其是 `packages/desktop/src/renderer/pages/settings/AssistantSettings`。

## 关键入口

最外层入口是 `packages/desktop/src/renderer/hooks/assistant/index.ts`。业务页面不直接从具体文件引入，而是从 `@/renderer/hooks/assistant` 统一拿 hook，这让设置页和引导页共享同一套状态逻辑。

页面层的关键消费入口是 `packages/desktop/src/renderer/pages/settings/AssistantSettings/index.tsx`。它组合调用三个 hook：先用 `useAssistantList()` 获取 `assistants`、`activeAssistant`、`activeAssistantId`、`loadAssistants`、`localeKey` 等列表状态；再用 `useDetectedAgents()` 获取 `availableBackends` 和 `refreshAgentDetection`；最后把前两者的一部分能力注入 `useAssistantEditor()`，生成编辑抽屉所需的所有状态与事件。

另一个消费入口是 `packages/desktop/src/renderer/pages/guid/components/AssistantSelectionArea.tsx`。根据当前片段推断，它在引导流程中复用了同一套助手编辑能力，以便用户在引导页内选择或创建助手；依据是该文件同样导入三个 hook，并复用 `AssistantEditDrawer`、`DeleteAssistantModal`、`SkillConfirmModals`。

## 主流程位置

助手列表主流程在 `useAssistantList.ts`。组件挂载后执行 `loadAssistants()`，通过 `ipcBridge.assistants.list.invoke()` 读取后端已合并好的助手列表。注释说明后端会合并 builtin、user、extension 三类助手，前端只负责调用 `sortAssistantsUtil` 排序，并维护 `activeAssistantId`。如果当前选中的助手仍存在就保留，否则自动选择排序后的第一个助手。

编辑主流程在 `useAssistantEditor.ts`。`handleEdit()` 打开编辑抽屉，先填充名称、描述、头像、执行后端等基础字段，再加载内置自动技能。对于 extension assistant，直接使用 assistant 对象上的 `context`，并保持只读思路；对于非 extension assistant，会读取本地规则和技能内容，并加载可用技能目录。`handleCreate()` 则初始化一套空表单状态，默认 agent 为 `claude`，默认头像为机器人表情，并加载技能清单。`handleDuplicate()` 走复制流程，复用原助手的可编辑内容，但将状态置为创建模式。

保存主流程也在 `useAssistantEditor.ts` 的 `handleSave()`。它先校验名称，再处理待导入技能；创建时调用 `ipcBridge.assistants.create.invoke()` 生成助手，必要时写入规则文件；更新时根据助手来源构造不同请求。这里有一个重要分支：builtin assistant 源数据不可变，更新时只发送 `preset_agent_type`；user assistant 才会发送名称、描述、头像、技能等完整字段并写规则文件。保存后会重新加载助手列表，并调用 `refreshAgentDetection()` 刷新执行引擎缓存。

删除和启停也集中在 `useAssistantEditor.ts`。builtin assistant 不能删除，extension assistant 被视为只读，删除会提示用户复制后再编辑。普通 user assistant 删除走 `ipcBridge.assistants.delete.invoke()`。启停通过 `ipcBridge.assistants.setState.invoke({ id, enabled })` 写入状态覆盖，然后重新加载列表并刷新 agent 检测。

执行后端检测主流程在 `useDetectedAgents.ts`。它用 SWR 读取 `DETECTED_AGENTS_SWR_KEY` 对应的数据，fetcher 是 `fetchDetectedAgents`。随后过滤掉 `agent_type === 'remote'` 的项，并把 `AgentMetadata` 映射为 `{ id, name, isExtension }`。这里的 `id` 优先取 `backend`，否则取 `agent_type`，注释明确说明这是为了和 `preset_agent_type` 存储的后端 slug 对齐。

## 推荐阅读顺序

建议先读 `index.ts`，确认这个目录对外暴露的 API 很少，只有三个 hook 和一个类型。

第二步读 `useAssistantList.ts`，它是最容易理解的列表层：加载、排序、选中项、locale key、extension 判断。理解它之后，再看页面如何消费会更顺。

第三步读 `useDetectedAgents.ts`，它代码短，但能解释编辑抽屉里的“主 Agent / 后端选择器”数据从哪里来，以及为什么扩展 agent 和本地 agent 会被统一映射成 `AvailableBackend`。

第四步读 `useAssistantEditor.ts`。这个文件承担大部分业务状态，建议按 handler 阅读，而不是从上到下逐行读：先看 `handleCreate`、`handleEdit`、`handleDuplicate` 理解表单如何进入不同模式；再看 `handleSave` 理解创建和更新差异；最后看 `handleDeleteClick`、`handleDeleteConfirm`、`handleToggleEnabled` 理解来源限制。

第五步回到调用方 `packages/desktop/src/renderer/pages/settings/AssistantSettings/index.tsx`，看三个 hook 的返回值如何被传入 `AssistantEditDrawer` 和列表 UI。需要理解引导流程复用时，再看 `packages/desktop/src/renderer/pages/guid/components/AssistantSelectionArea.tsx`。

## 常见误区

不要把这个目录理解成助手系统的全部实现。它只是 renderer 侧的状态编排层，真正的数据源、文件系统操作、后端 agent 检测都不在这里，而是通过 `ipcBridge` 转发到其他进程或模块。

不要在这里寻找 UI 布局。编辑抽屉、列表卡片、确认弹窗等 UI 在 `packages/desktop/src/renderer/pages/settings/AssistantSettings`，这里返回的是 UI 所需的状态和事件。

不要忽略助手来源差异。`builtin`、`user`、`extension` 的可编辑能力不同：builtin 主要只能覆盖执行后端，extension 基本只读，user 才是完整可编辑、可删除的对象。`useAssistantEditor.ts` 的很多条件分支都是围绕这个来源模型建立的。

不要以为前端会合并三类助手列表。`useAssistantList.ts` 的注释说明合并逻辑在后端完成，前端拿到的是已经合并的列表，只做排序和选中项维护。

不要把 `availableBackends` 当成助手列表。`useDetectedAgents.ts` 返回的是可执行后端或扩展 agent，用于 `preset_agent_type` 选择；助手本身来自 `useAssistantList.ts` 的 `assistants`。

不要绕过 `loadAssistants()` 和 `refreshAgentDetection()`。创建、更新、删除、启停后需要刷新列表和 agent 检测，否则页面状态、下拉选项或引导页可选项可能与后端不一致。
