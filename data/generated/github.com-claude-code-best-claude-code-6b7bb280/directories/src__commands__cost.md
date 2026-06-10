# 目录：src/commands/cost

## 它负责什么

`src/commands/cost` 是一个很薄的命令适配目录，核心职责不是自己定义一套新命令，而是把旧入口 `/cost` 统一转发到现在的主命令 `/usage`。从当前片段看，这里对应的是“向后兼容层”：保留用户仍可能输入的 `/cost`，但实际执行逻辑已经收敛到 `src/commands/usage`。

目录内仍保留了一个真正执行成本查询的实现文件 `cost.ts`。它会读取会话总成本、订阅状态和当前超额使用情况，再按用户类型决定返回怎样的文本。换句话说，这里处理的是“成本展示”这个能力本身，而 `index.ts` 处理的是“命令名和入口兼容”。

## 直接子目录地图

根据当前片段推断，这个目录下面没有子目录，只有两个文件：

- `src/commands/cost/index.ts`：命令入口层，直接重导出 `../usage/index.js`
- `src/commands/cost/cost.ts`：成本输出逻辑，返回本地命令结果

这个结构很像一个迁移中的桥接目录，目录层级本身很浅，不承担复杂分发。

## 关键入口

最关键的入口是 `src/commands/cost/index.ts`。它的注释已经明确说明：`/cost` 是 `/usage` 的别名，且这里直接 `export { default } from '../usage/index.js'`。这意味着外部只要从 `cost/index` 导入，拿到的仍然是统一的 `usage` 命令定义。

真正的数据输出入口在 `src/commands/cost/cost.ts`。这里导入了 `formatTotalCost`、`currentLimits`、`isClaudeAISubscriber` 和 `LocalCommandCall`，说明它是一个本地命令调用处理器，负责把当前会话费用整理成可显示文本。

## 主流程位置

主流程可以按两层理解。

第一层是命令注册层。`src/commands/usage/index.ts` 把 `usage` 定义为主命令，并声明 `aliases: ['cost', 'stats']`。也就是说，从命令体系上看，`/cost` 只是 `/usage` 的别名，不再是独立产品入口。

第二层是执行层。`src/commands/cost/cost.ts` 的逻辑分支很清晰：

- 如果当前用户是 Claude AI 订阅用户，先输出订阅提示
- 如果正在使用 overage，再补充说明超额额度状态
- 如果环境变量 `USER_TYPE` 是 `ant`，额外显示真实成本
- 如果不是订阅用户，直接输出 `formatTotalCost()`

从 `src/commands.ts` 的注册处也能看到，`usage` 被放进 `REMOTE_SAFE_COMMANDS` 和 `BRIDGE_SAFE_COMMANDS`，说明它不仅能在本地 TUI 使用，也被远程/桥接模式允许执行。

## 推荐阅读顺序

1. 先看 `src/commands/cost/index.ts`，确认这里是别名转发层。
2. 再看 `src/commands/usage/index.ts`，理解 `/usage` 才是主定义。
3. 然后看 `src/commands/cost/cost.ts`，把输出逻辑和订阅判断串起来。
4. 最后看 `src/commands.ts` 中 `usage` 的注册位置，理解它在全局命令表里的权限范围。
5. 如果要追踪真实金额计算，再顺着 `formatTotalCost` 进入 `src/cost-tracker.js`。

## 常见误区

- 把 `src/commands/cost` 当成独立业务目录。实际上它更像兼容壳，核心命令已经迁到 `usage`。
- 只看 `cost.ts` 就以为 `/cost` 的命令定义也在这里。真正的命令名、别名和加载入口在 `src/commands/usage/index.ts`。
- 忽略 `src/commands.ts` 的远程安全列表。`usage` 是否可在 remote/bridge 场景运行，受这里的注册影响。
- 误以为订阅用户永远看不到成本。代码里对 `USER_TYPE === 'ant'` 有显式例外，会强制补出成本信息。
- 忽略 `currentLimits.isUsingOverage` 的分支。这个目录展示的不只是“花了多少钱”，还有当前是否在超额额度上运行。
