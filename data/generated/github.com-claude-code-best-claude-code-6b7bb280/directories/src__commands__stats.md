# 目录：src/commands/stats

## 它负责什么

`src/commands/stats` 现在不是一个完整独立的统计命令实现，而是 `/stats` 兼容入口目录。它的主要职责是把历史上的 `/stats` 命令名继续保留下来，并导向新的统一命令 `/usage`。从 `src/commands/stats/index.ts` 的注释和导出可以看出，上游对齐版本 `v2.1.118` 之后，`/usage` 成为主命令，`/cost` 和 `/stats` 都作为别名存在。

这个目录里的核心文件只有两个：`index.ts` 和 `stats.tsx`。其中真正参与当前命令注册路径的是 `index.ts`，它直接 `export { default } from '../usage/index.js'`，也就是说任何从 `src/commands/stats/index.ts` 引入命令对象的旧代码，拿到的都会是 `src/commands/usage/index.ts` 导出的统一 `Command`。`stats.tsx` 仍保留了旧式面板调用逻辑，会渲染 `src/components/Stats.tsx`，但从当前片段看，它已不再是 `/stats` 的主执行入口。

## 直接子目录地图

`src/commands/stats` 没有直接子目录，是一个很薄的命令兼容目录。目录结构可以概括为：

`src/commands/stats/index.ts`：当前有效入口，负责把 `stats` 目录重定向到 `usage` 命令定义。它不是自己声明 `name: 'stats'`，而是复用 `usage` 的命令对象，因此 `/stats` 的命令身份来自 `usage` 的 `aliases`。

`src/commands/stats/stats.tsx`：旧统计面板的 JSX 调用文件，内部 `call` 返回 `<Stats onClose={onDone} />`。根据当前片段推断，它更像迁移遗留文件或供局部旧引用使用的备用实现；依据是 `index.ts` 已经显式说明 `/stats` 是 `/usage` 别名，并且全局搜索显示测试也在验证 `stats/index` 不再是 standalone。

## 关键入口

最关键入口是 `src/commands/stats/index.ts`。它没有复杂逻辑，只做一件事：把默认导出转交给 `src/commands/usage/index.ts`。理解这个目录时，应先看这条 re-export，因为它决定了 `/stats` 当前在命令系统里的真实含义。

实际命令定义位于 `src/commands/usage/index.ts`。这里声明：

`type: 'local-jsx'` 表示这是一个本地 Ink/React JSX 命令；

`name: 'usage'` 表示主命令名是 `/usage`；

`aliases: ['cost', 'stats']` 表示 `/cost` 和 `/stats` 都会路由到同一个命令；

`load: () => import('./usage.js')` 表示真正执行时懒加载 `src/commands/usage/usage.tsx`。

因此，用户输入 `/stats` 时，不应理解为进入 `src/commands/stats/stats.tsx`，而应理解为命中了 `/usage` 的别名。`src/commands.ts` 中也有对应注释：“`stats/index.ts` re-exports usage”，并在 `REMOTE_SAFE_COMMANDS` 中把 `usage` 标为安全命令，注释说明 `/cost` 和 `/stats` 是 aliases。

## 主流程位置

当前主流程可以分为三段。

第一段是命令注册。命令聚合发生在 `src/commands.ts`，它导入并维护内置命令集合。这里的注释明确指出 `stats/index.ts` 现在重导出 `usage`，同时远程安全命令集合中保留的是 `usage` 这个命令对象，而不是单独的 `stats` 对象。也就是说 `/stats` 的可用性来自 `usage.aliases`，不是来自独立注册一份 stats 命令。

第二段是命令加载。`src/commands/usage/index.ts` 是统一命令元数据层。它定义 `/usage` 的描述为 “Show session cost, plan usage, and activity stats”，并把 `cost`、`stats` 作为别名。命令被触发后，`load` 懒加载 `src/commands/usage/usage.tsx`，避免在命令列表初始化时提前加载较重 UI 逻辑。

第三段是 UI 分发。`src/commands/usage/usage.tsx` 的 `call(onDone, context)` 返回 `<Settings onClose={onDone} context={context} defaultTab="Usage" />`。注释说明设计目标是统一 `/cost` 和 `/stats`：claude.ai subscriber 走 Settings 的 Usage tab，用于展示 plan limits 与 overages；API 或非订阅用户走 Stats panel，展示 session cost、token counts、activity。实际分流不在 `src/commands/stats` 中，而是在 `Settings`/Usage 相关组件内部完成。若要继续追踪统计数据来源，应从 `src/components/Stats.tsx` 进入，它调用 `aggregateClaudeCodeStatsForRange`，再到 `src/utils/stats.ts` 和 `src/utils/statsCache.ts` 看 session JSONL 聚合、日期范围统计与缓存逻辑。

`src/commands/stats/stats.tsx` 的旧流程更直接：`call` 渲染 `Stats`，`Stats` 再读取 `src/utils/stats.ts` 聚合出的 `ClaudeCodeStats`。但根据当前命令入口，它不是 `/stats` 的主流程位置，只能作为理解历史实现或兼容残留的参考。

## 推荐阅读顺序

1. 先读 `src/commands/stats/index.ts`。这个文件最短，但能立刻建立正确心智：`stats` 目录当前是 alias shim，不是业务实现目录。

2. 再读 `src/commands/usage/index.ts`。这里能看到真实命令名、别名列表、描述和懒加载目标，是 `/stats` 当前为什么还能工作的关键。

3. 接着读 `src/commands/usage/usage.tsx`。它说明统一后的 UI 入口是 `Settings` 的 `Usage` tab，而不是直接渲染旧 `Stats` 面板。

4. 然后看 `src/components/Stats.tsx`。这一步用于理解“activity stats”具体展示什么：日期范围切换、Overview/Models tab、热力图、模型使用、截图/ANSI 渲染等都在这里附近。

5. 最后读 `src/utils/stats.ts`、`src/utils/statsCache.ts`。这两个文件才是统计数据的底层来源，负责读取会话文件、按范围聚合、计算派生字段，并使用缓存避免每次全量扫描。

## 常见误区

第一个误区是把 `src/commands/stats/stats.tsx` 当成 `/stats` 当前入口。它确实导出了 `call`，也确实能渲染 `Stats` 组件，但 `src/commands/stats/index.ts` 已经把默认命令对象重导出为 `usage`，所以命令系统层面的 `/stats` 入口不在这里。

第二个误区是认为 `/stats`、`/cost`、`/usage` 是三套不同命令。当前设计恰好相反：它们被合并到 `usage` 一个 `Command` 对象中，`stats` 和 `cost` 只是 alias。测试目录 `src/commands/usage/__tests__/usage.test.ts` 也围绕这一点做回归验证。

第三个误区是把命令名里的 “stats” 和 Statsig 混为一谈。仓库里大量出现 `Statsig`、`cachedStatsigGates`、`checkStatsigFeatureGate_CACHED_MAY_BE_STALE`，这些属于分析、实验开关或配置缓存体系，和 `src/commands/stats` 这个用户命令目录不是同一件事。

第四个误区是期待 `src/commands/stats` 内部包含统计聚合逻辑。这个目录只承担命令兼容和旧 UI 调用残留；统计聚合在 `src/utils/stats.ts`，缓存持久化在 `src/utils/statsCache.ts`，终端展示主要在 `src/components/Stats.tsx`，订阅/用量页入口则在 `src/components/Settings/Settings.js` 相关组件链路中。
