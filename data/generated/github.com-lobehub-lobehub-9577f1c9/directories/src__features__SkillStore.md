# 目录：src/features/SkillStore

## 它负责什么

`src/features/SkillStore` 是“技能商店”功能的前端聚合层，主要以弹窗形式承载技能发现、搜索、安装/连接入口和详情查看。它不直接作为 SPA route 出现，而是被设置页等位置调用，例如 `src/routes/(main)/settings/skill/index.tsx` 通过 `createSkillStoreModal` 打开商店弹窗。

从当前片段看，这个目录负责把多种技能来源统一展示在一个商店界面中：LobeHub 官方技能、内置工具、内置 Agent 技能、Klavis 服务、MCP 市场插件、自定义插件，以及 Marketplace Agent Skills。它自身更偏 UI 编排和交互入口，实际数据、安装状态、连接状态、搜索状态多来自 `useToolStore`、`useServerConfigStore`、`useUserStore` 以及常量包 `@lobechat/const`。

整体结构是典型的“入口弹窗 -> 内容容器 -> 搜索与标签页 -> 不同来源列表 -> 详情弹窗”的分层。`SkillStore` 不负责工具执行，也不负责 MCP 协议细节；它主要负责用户在商店里看到什么、点哪里打开详情、如何触发连接/安装相关 store action。

## 直接子目录地图

`Search` 是商店顶部搜索区。它根据当前 tab 将关键字分发到不同状态：MCP 搜索写入 `useToolStore` 的 `mcpSearchKeywords`，自定义插件搜索写入 `customPluginSearchKeywords`，LobeHub 与 Skills tab 则通过父组件传入的回调保存本地关键字。

`SkillList` 是列表区域的主体目录，按技能来源继续拆分。`SkillList/LobeHub` 负责聚合官方来源：内置 Agent 技能、内置工具、LobeHub Skill providers、Klavis server types。`SkillList/MCP` 负责 MCP 插件市场列表，结合 `useFetchMCPPluginList`、`loadMoreMCPPlugins`、`resetMCPPluginList` 等 store action 做分页与搜索。`SkillList/Custom` 展示用户自定义插件。`SkillList/Community` 提供社区/市场类条目组件。`SkillList/MarketSkills` 展示 Marketplace Agent Skills。`SkillList/Builtin` 放内置技能/工具卡片。`AddSkillButton`、`ImportFromGithubModal`、`ImportFromUrlModal`、`UploadSkillModal` 则是新增或导入技能的入口组件。

`SkillDetail` 是技能详情弹窗目录，负责不同类型技能的详情 Provider、公共详情布局以及详情页签。它把 Builtin、Builtin Agent Skill、Klavis、LobeHub 四类详情入口统一到 `SkillDetailInner`，再由 `Header`、`Nav`、`Overview`、`Schema`、`Agents` 等组件展示详情内容。

根目录下的 `index.tsx` 和 `SkillStoreContent.tsx` 是关键入口。前者创建弹窗并包上市场认证上下文，后者组织整个商店 UI。

## 关键入口

`src/features/SkillStore/index.tsx` 暴露 `createSkillStoreModal`。这是外部打开技能商店的主入口。它调用 `createModal`，设置弹窗宽度、全屏能力、标题、body 样式，并用 `MarketAuthProvider` 包裹 `SkillStoreContent`。这里的 `getContainer` 特意把 Modal 渲染到 `LOBE_THEME_APP_ID` 对应节点中，根据注释是为了让 Modal 与 `DropdownMenu` portal 处在同一层叠上下文。

`src/features/SkillStore/SkillStoreContent.tsx` 是商店主体入口。它定义 `SkillStoreTab`：`LobeHub`、`Skills`、`MCP`、`Custom`。组件内部维护当前 tab，以及 LobeHub 和 Skills 两类本地搜索关键字。顶部用 `Segmented` 切换 tab，右侧放 `AddSkillButton`，下面放 `Search`。列表区域并不是切换时卸载组件，而是四个列表都存在，通过 `display: flex/none` 控制显示，这意味着某些列表的初始化和内部状态可能会保留。

`src/features/SkillStore/SkillDetail/index.tsx` 暴露四个详情弹窗工厂：`createBuiltinAgentSkillDetailModal`、`createBuiltinSkillDetailModal`、`createKlavisSkillDetailModal`、`createLobehubSkillDetailModal`。列表卡片点击详情时通常会调用这些函数。

## 主流程位置

商店打开主流程在 `src/features/SkillStore/index.tsx` 和 `src/features/SkillStore/SkillStoreContent.tsx`。外部调用 `createSkillStoreModal` 后，弹窗渲染 `SkillStoreContent`；用户通过 `Segmented` 选择 LobeHub、Skills、MCP 或 Custom；`Search` 根据当前 tab 更新对应关键字；当前 tab 对应的列表组件展示结果。

LobeHub tab 的主流程集中在 `src/features/SkillStore/SkillList/LobeHub/index.tsx`。它会读取服务端配置开关 `enableLobehubSkill`、`enableKlavis`，从 `useToolStore` 取已连接的 LobeHub Skill servers、Klavis servers、builtin tools、builtin skills，并调用 `useFetchLobehubSkillConnections`、`useFetchUserKlavisServers` 拉取连接状态。随后把不同来源合并成一个 `filteredItems` 数组，再按类型渲染不同卡片。点击详情时进入 `SkillDetail` 的对应 create modal 方法。

MCP tab 的主流程在 `src/features/SkillStore/SkillList/MCP/index.tsx`。根据当前片段推断，它依赖 `useToolStore` 中的 MCP 列表状态、分页状态、搜索 loading 和列表拉取方法，通过 `VirtuosoGrid` 做虚拟化网格渲染，并支持加载更多。依据是该文件导入了 `VirtuosoGrid`、`useFetchMCPPluginList`、`loadMoreMCPPlugins`、`resetMCPPluginList` 等符号。

详情页主流程在 `src/features/SkillStore/SkillDetail`。不同详情 Provider 先根据 `identifier` 获取配置、连接状态、工具 schema、README 和本地化文案，然后写入 `DetailContext`。`SkillDetailInner` 再统一展示：`Header` 显示标题、图标和连接状态；`Nav` 切换 `overview`、`schema`、`agents`；`Overview` 展示介绍，`Schema` 展示工具输入结构，`Agents` 展示使用该技能的 Agent 列表。

连接/授权相关逻辑的核心位置是 `src/features/SkillStore/SkillList/LobeHub/useSkillConnect.ts`。它同时处理 LobeHub Skill 和 Klavis 的连接/撤销流程，包括获取授权地址、打开 OAuth 窗口、轮询状态、清理定时器等。`SkillDetail/Header.tsx` 会使用这个 hook，因此详情页头部也是触发连接操作的重要位置。

## 推荐阅读顺序

建议先读 `src/features/SkillStore/index.tsx`，理解商店如何被外部打开，以及为什么要包 `MarketAuthProvider`。

第二步读 `src/features/SkillStore/SkillStoreContent.tsx`，掌握四个 tab 的页面骨架、搜索状态如何传递、列表如何切换。

第三步读 `src/features/SkillStore/Search/index.tsx`，理解同一个搜索框为什么会写入不同状态。这里能看出 LobeHub、Skills、MCP、Custom 的搜索机制并不完全一样。

第四步读 `src/features/SkillStore/SkillList/LobeHub/index.tsx`，这是最能代表该目录设计意图的列表：它把内置能力、官方 Provider、Klavis 服务合并成统一卡片流。

第五步读 `src/features/SkillStore/SkillList/MCP/index.tsx` 和 `src/features/SkillStore/SkillList/Custom/index.tsx`，分别理解市场插件和用户自定义插件的展示方式。

最后读 `src/features/SkillStore/SkillDetail/index.tsx`、`src/features/SkillStore/SkillDetail/DetailContext.tsx`、`src/features/SkillStore/SkillDetail/SkillDetailInner.tsx`，再按需进入各类 Provider。这样可以先掌握详情弹窗的公共模型，再回头看不同来源如何填充详情数据。

## 常见误区

不要把 `SkillStore` 理解成单一“插件市场”。它实际上聚合了多类能力：builtin tools、builtin agent skills、LobeHub providers、Klavis servers、MCP plugins、custom plugins 和 market agent skills。不同来源的数据结构、安装方式和连接状态都不一样，只是在 UI 上被统一成商店体验。

不要以为搜索逻辑都在父组件中。`SkillStoreContent` 只保存 LobeHub 和 Skills 的搜索关键字；MCP 和 Custom 搜索会直接写入 `useToolStore`。如果排查搜索问题，需要按 tab 分别看状态来源。

不要只看 `SkillList/LobeHub` 目录名就认为它只展示 LobeHub Skill。该列表实际还混入 builtin agent skill、builtin tool、Klavis skill，并根据 server config 开关决定是否展示 LobeHub/Klavis 来源。

不要把详情弹窗的数据来源看成一个接口。`SkillDetail` 用统一的 `DetailContext` 给 UI 消费，但上游 Provider 各不相同：Builtin 从内置工具/技能数据来，LobeHub 从 provider 配置和连接列表来，Klavis 从 server type 和用户服务器连接来。

不要在这个目录里寻找底层安装、执行或协议实现。安装状态、MCP 列表、连接、撤销、工具 schema 拉取等动作主要下沉在 `src/store/tool`、相关 selectors、services 或常量包中；`SkillStore` 只是把这些能力组织成用户可操作的界面入口。
