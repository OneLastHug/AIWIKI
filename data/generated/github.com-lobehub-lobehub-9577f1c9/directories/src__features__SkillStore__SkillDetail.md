# 目录：src/features/SkillStore/SkillDetail

## 它负责什么

这个目录负责「技能商店」里的详情查看与弹窗展示，核心作用不是列表浏览，而是把某个 skill 的来源、说明、结构化信息和相关动作，统一包装成可复用的详情视图。根据当前片段推断，它覆盖了几类来源的详情形态，包括 LobeHub 自身技能、builtin 技能、builtin agent 技能，以及 Klavis 相关技能。

它在工程里的位置很清楚：`src/features/SkillStore` 是技能商店的业务域，`SkillDetail` 是其中的详情子域，和上层的 `Search`、`SkillList` 并列。上层负责入口和列表，这一层负责“点进某个技能之后看什么、怎么展示、怎么按来源切换内容”。

## 直接子目录地图

这个目录下面没有再嵌套更深的子目录，主体是一组并列的 TSX 模块和样式文件。按职责可以粗分为几块：

- 详情入口与编排：`index.tsx`、`SkillDetailInner.tsx`
- 来源适配层：`BuiltinDetailProvider.tsx`、`BuiltinAgentSkillDetailProvider.tsx`、`KlavisDetailProvider.tsx`、`LobehubDetailProvider.tsx`
- 来源内容层：`BuiltinSkillDetailContent.tsx`、`BuiltinAgentSkillDetailContent.tsx`、`KlavisSkillDetailContent.tsx`、`LobehubSkillDetailContent.tsx`
- 页面骨架与导航：`Header.tsx`、`Nav.tsx`、`Overview.tsx`
- 结构化信息展示：`Schema.tsx`、`Agents.tsx`、`AgentItem.tsx`
- 状态与占位：`DetailContext.tsx`、`VirtuosoLoading.tsx`
- 样式：`style.ts`、`styles.ts`

如果把它看成一条链路，真正的“入口页”是 `index.tsx`，真正的“内容切换层”是各个 `*DetailProvider.tsx` 和对应的 `*SkillDetailContent.tsx`。

## 关键入口

最关键的入口是 `src/features/SkillStore/SkillDetail/index.tsx`。这里直接导出多个 `create...Modal()` 工厂函数，用 `createModal()` 把不同来源的详情组件包进统一弹窗。当前能看到四个主要入口：

- `createBuiltinAgentSkillDetailModal`
- `createBuiltinSkillDetailModal`
- `createKlavisSkillDetailModal`
- `createLobehubSkillDetailModal`

这些入口都把标题统一到 `t('dev.title.skillDetails', { ns: 'plugin' })`，说明它们共享同一个“技能详情”语义，只是内容来源不同。

父级入口是 `src/features/SkillStore/index.tsx`，这里的 `createSkillStoreModal()` 会打开整个技能商店弹窗，并把 `SkillStoreContent` 放进 `MarketAuthProvider` 里。也就是说，`SkillDetail` 不是单独被页面路由直接挂载，而是被技能商店主弹窗间接使用。

## 主流程位置

主流程可以理解为“从技能商店进入详情，再按来源渲染具体内容”：

1. `src/features/SkillStore/index.tsx` 打开商店主弹窗。
2. `SkillStoreContent` 负责商店主体交互，用户在列表或搜索结果里选择某个技能。
3. 进入详情时，`src/features/SkillStore/SkillDetail/index.tsx` 选择对应的 `create...SkillDetailModal()`。
4. 具体 modal 再交给某个 `*SkillDetailContent.tsx`。
5. 若需要更细的组织，`SkillDetailInner.tsx`、`Header.tsx`、`Nav.tsx`、`Overview.tsx`、`Schema.tsx`、`Agents.tsx` 共同组成详情页骨架和信息分区。
6. `DetailContext.tsx` 用来在详情树内部共享当前 skill 的上下文，避免 props 在多个分区里层层传递。
7. `VirtuosoLoading.tsx` 提供长列表或异步加载时的占位状态。

根据文件命名推断，这个目录的设计重点不是单一页面，而是“一个详情壳子，多种来源内容”的适配模式。

## 推荐阅读顺序

1. 先看 `src/features/SkillStore/index.tsx`，理解商店弹窗从哪里打开。
2. 再看 `src/features/SkillStore/SkillDetail/index.tsx`，把各类详情 modal 的入口认清。
3. 接着看 `SkillDetailInner.tsx`、`Header.tsx`、`Nav.tsx`，建立详情页骨架概念。
4. 然后看 `DetailContext.tsx`，理解详情内部状态如何共享。
5. 最后按来源挑一条链路读 `BuiltinDetailProvider.tsx`、`BuiltinSkillDetailContent.tsx`，或者 `LobehubDetailProvider.tsx`、`LobehubSkillDetailContent.tsx`，再去看 `Schema.tsx`、`Overview.tsx`、`Agents.tsx` 这些分区组件。

## 常见误区

- 把 `SkillDetail` 当成路由页面。它更像弹窗内的详情模块，入口是 modal 工厂，不是路由组件。
- 只看 `index.tsx` 就以为看完了。这里主要是入口分发，真正的展示逻辑在各个 `*DetailContent.tsx` 和 `*Provider.tsx`。
- 忽略来源差异。builtin、builtin agent、Klavis、LobeHub 的详情不是同一套数据源，适配层是这个目录存在的核心原因。
- 把 `Header`、`Nav`、`Overview` 这些组件当成纯视觉碎片。它们实际上承载了详情导航、信息总览和结构化展示，是主流程的一部分。
- 以为 `SkillDetail` 自己负责技能列表。列表职责在 `SkillList`，这里负责的是选中后的详情表达。
