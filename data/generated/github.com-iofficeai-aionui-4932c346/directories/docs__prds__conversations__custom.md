# 目录：docs/prds/conversations/custom

## 它负责什么
这个目录承载的是 `Custom Agent` 主题的 PRD 文档索引与正文，属于 `conversations` 体系下的一个子专题。它关注的不是运行时代码，而是「设置页 → Agent 管理 → 本地 Agents → Custom Agent」这一条产品链路的需求说明、功能拆解、验收点和工作记录。  
根据当前片段推断，这里是把自定义 Agent 的列表展示、创建、编辑、删除、启用/禁用、连接测试、自动检测等能力集中归档的地方，方便按主题追踪产品演进。

## 直接子目录地图
这个目录下面没有子目录，只有两个直接文件：

- `docs/prds/conversations/custom/README.md`：目录索引页，列出该主题的文档和功能点总览。
- `docs/prds/conversations/custom/custom-agent.md`：正文 PRD，按功能点展开自定义 Agent 的完整需求。

从结构上看，它是一个“文档目录”，不是继续往下拆分的功能树。

## 关键入口
如果只是快速理解这个目录，先看 `docs/prds/conversations/custom/README.md`。它会告诉你这个主题覆盖了哪些功能点，以及每个功能点的状态、模块归类和工作记录。

如果要进入细节，核心正文是 `docs/prds/conversations/custom/custom-agent.md`。这里按 F-CAGENT-01 到 F-CAGENT-16 的顺序描述了完整流程，尤其是：

- 页面入口与 Tab 切换
- Detected Agents 列表
- Custom Agent 列表
- 创建与编辑弹窗
- InlineAgentEditor 表单行为
- 连接测试与保存逻辑
- 自动检测机制

如果你想把文档和实现对应起来，正文里出现的几个关键实现锚点也很重要：`AgentModalContent.tsx`、`LocalAgents.tsx`、`InlineAgentEditor.tsx`、`useCustomAgentsLoader.ts`、`useDetectedAgents.ts`，以及 IPC / 存储相关的 `ipcBridge.acpConversation.getAvailableAgents.invoke()`、`ConfigStorage('acp.customAgents')`、`AgentRegistry`。

## 主流程位置
根据当前片段推断，这个目录本身不直接承载业务实现，主流程位置分布在两层：

第一层是渲染层，负责设置页的页面组织和交互。重点位置通常会落在 `packages/desktop/src/renderer/` 下，与 Agent 设置页相关的组件链路中，正文里已经点名了 `AgentModalContent.tsx`、`LocalAgents.tsx`、`InlineAgentEditor.tsx`。这里决定用户看到什么、点哪里、弹窗怎么开关、列表怎么渲染。

第二层是数据层，负责检测、读取、写回。Detected Agents 走 `ipcBridge.acpConversation.getAvailableAgents.invoke()` 到主进程的 `AgentRegistry`；Custom Agent 则主要通过 `ConfigStorage.get('acp.customAgents')` 读写本地配置。刷新链路里还会看到 `useCustomAgentsLoader.ts`、`refreshCustomAgents.invoke()`、SWR `mutate` 这些位置。

如果把这条链路按用户动作串起来，主流程就是：设置页入口进入 → 切换到本地 Agents → 上半区看已检测列表 → 下半区管理自定义列表 → 通过 `InlineAgentEditor` 新建或编辑 → 保存回 `ConfigStorage` → 刷新列表。  
这是这个目录对应主题的核心闭环。

## 推荐阅读顺序
1. 先读 `docs/prds/conversations/custom/README.md`，把这组文档的边界和功能点总览看清楚。
2. 再读 `docs/prds/conversations/custom/custom-agent.md` 的前半部分，先理解 F-CAGENT-01 到 F-CAGENT-05，这一段是页面结构、列表和 CRUD 主流程。
3. 接着看 F-CAGENT-06 到 F-CAGENT-10，理解表单编辑器的输入、解析和高级模式。
4. 然后看 F-CAGENT-11 到 F-CAGENT-16，补齐测试、删除、启用/禁用、自动检测和加载机制。
5. 最后回看文末的流程图、风险点和附录，建立“文档里的需求”和“代码里的实现点”之间的映射。

## 常见误区
- 误把这个目录当成实现代码目录。它实际是 PRD 文档目录，代码只是在正文里被引用来说明实现位置。
- 误以为 Custom Agent 会像 Detected Agents 一样自动扫描出来。它不是自动检测结果，而是走 `ConfigStorage('acp.customAgents')` 的本地配置通路。
- 误把设置页的过滤逻辑和通用 hook 混为一谈。正文已经指出 `LocalAgents.tsx` 的过滤规则和 `useDetectedAgents` 并不完全相同。
- 误以为高级 JSON 编辑器会保留所有字段。根据正文描述，提交时只会重建表单暴露的字段，额外字段可能被丢弃。
- 误以为 `enabled` 需要显式填写。正文里说明它有默认值，未显式关闭时会被视为开启。
- 误把 `remote`、`custom`、`preset` 三类 Agent 当成同一种来源。这个主题里它们的数据通路不同，尤其是 Custom Agent 和自动检测结果是分开的。
