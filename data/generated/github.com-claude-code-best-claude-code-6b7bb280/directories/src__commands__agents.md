# 目录：src/commands/agents

## 它负责什么
`src/commands/agents` 是一层“命令入口壳”，职责不是自己实现 agent 业务，而是把“管理 agent 配置”的交互入口挂到命令系统里。根据当前片段推断，这里负责把命令描述、加载逻辑和实际 UI 组装起来，再交给下游的 `src/components/agents/` 目录处理具体界面与编辑流程。

从语义上看，它和顶层 CLI 里那个 `agents` 子命令不是同一层东西。`src/main.tsx` 里还有一个面向 CLI 的 `agents` 命令，作用是列出已配置的 agents；而这个目录更像是本地 JSX 命令的实现入口，偏交互式管理。

## 直接子目录地图
这个目录本身没有子目录，只有两个文件：

- `src/commands/agents/index.ts`：命令元数据与懒加载入口
- `src/commands/agents/agents.tsx`：真正的执行入口，负责渲染 UI

它依赖的主要下游不是本目录的子层，而是 `src/components/agents/` 这一整棵组件树。那边包含 `AgentsMenu.tsx`、`AgentEditor.tsx`、`AgentsList.tsx`、`CreateAgentWizard.tsx`、`ToolSelector.tsx`、`ModelSelector.tsx` 等，说明这里的命令入口最终会落到一个完整的 agent 管理界面。

## 关键入口
最关键的入口有两个：

- `src/commands/agents/index.ts`
  - 定义了一个 `Command`
  - `name` 是 `agents`
  - `description` 是 `Manage agent configurations`
  - `load` 指向 `./agents.js`

- `src/commands/agents/agents.tsx`
  - 暴露 `call(onDone, context)`
  - 从 `context.getAppState()` 取出 `toolPermissionContext`
  - 调 `getTools(permissionContext)` 组装可用工具
  - 最后渲染 `<AgentsMenu tools={tools} onExit={onDone} />`

这说明它的入口模式很标准：先收集运行上下文，再把工具列表和退出回调传给 UI 层。

## 主流程位置
主流程基本集中在 `src/commands/agents/agents.tsx`，而 UI 交互主线则继续下沉到 `src/components/agents/AgentsMenu.tsx`。从现有文件名和调用关系看，整体流程大致是：

1. 命令系统加载 `src/commands/agents/index.ts`
2. 懒加载 `src/commands/agents/agents.tsx`
3. `call()` 获取 `AppState` 和权限上下文
4. `getTools()` 生成可用工具集合
5. `AgentsMenu` 接管后续交互
6. 在 `src/components/agents/` 内部切换到列表、编辑器或新建向导

根据当前片段推断，真正的“管理动作”不是写在命令目录里，而是分散在 `AgentsMenu`、`AgentEditor`、`CreateAgentWizard` 这些组件中完成。

## 推荐阅读顺序
1. `src/commands/agents/index.ts`  
   先看命令如何被定义和懒加载。

2. `src/commands/agents/agents.tsx`  
   再看它如何把运行时上下文转成 UI 所需参数。

3. `src/components/agents/AgentsMenu.tsx`  
   这是理解整个交互入口的关键。

4. `src/components/agents/CreateAgentWizard.tsx`、`src/components/agents/AgentEditor.tsx`、`src/components/agents/AgentsList.tsx`  
   如果要理解具体管理动作，再继续往下看。

5. `src/main.tsx` 中的 `agents` CLI 命令段  
   只在需要区分“CLI 列表命令”和“本地 JSX 管理命令”时再看。

## 常见误区
- 不要把 `src/commands/agents` 和 `src/main.tsx` 里的 `agents` CLI 命令混为一谈。前者是交互式管理入口，后者是 CLI 层的命令注册。
- 不要把这里当成 agent 配置存储层。这个目录更像路由和装配层，真正的状态、表单、选择器和向导逻辑在 `src/components/agents/`。
- 不要按“目录名叫 agents，就一定有很多子目录”去理解。这个目录本身很薄，实际复杂度都下沉到组件树里了。
- 如果只看 `index.ts`，会误以为这里没有业务；如果只看 `agents.tsx`，又会忽略它依赖的 `AgentsMenu` 及其后续流程。完整理解必须把命令入口和 UI 入口连起来看。
