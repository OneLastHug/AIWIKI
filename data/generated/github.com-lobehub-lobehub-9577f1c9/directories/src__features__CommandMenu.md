# 目录：src/features/CommandMenu

## 它负责什么

这个目录实现的是全局命令菜单，也就是应用里的 `Cmd+K` / 命令面板。它不是单纯的搜索框，而是一个统一入口：可以做页面跳转、上下文命令切换、搜索结果跳转、主题切换、AI 发送、创建新会话/页面/知识库等操作。整体上它更像一个“操作中枢”，通过 `cmdk` 提供键盘驱动的命令体验。

从代码结构看，这里把“展示层”和“行为层”分得比较清楚：`index.tsx` 负责挂载、portal 和渲染分支；`useCommandMenu.ts` 负责大部分动作和副作用；`CommandMenuContext.tsx` 负责菜单内部状态；`utils/` 负责上下文识别和命令集合组装。

## 直接子目录地图

这个目录的直接子目录只有两个：

- `components/`：放菜单内部的基础 UI 片段。当前可见的是 `CommandInput.tsx`、`CommandFooter.tsx`、`CommandItem.tsx`，以及一个 `index.ts` 统一导出。它们更像“积木”，供主菜单、搜索结果、上下文命令等多个分支复用。
- `utils/`：放纯逻辑工具，不直接渲染 UI。这里有 `context.ts` 用于根据 pathname 判断当前菜单上下文，`contextCommands.ts` 用于构建上下文命令表，还有 `queryParser.ts` 这类搜索语法解析工具及对应测试。

目录根部还放着多组功能分支文件：`MainMenu.tsx`、`ContextCommands.tsx`、`SearchResults.tsx`、`ThemeMenu.tsx`、`AskAIMenu.tsx`、`AskAgentCommands.tsx`，以及 `types.ts`、`styles.ts`、`README.md`、若干测试文件。它们不再往下分层，说明这个 feature 采用的是“扁平主模块 + 两个轻量子目录”的组织方式。

## 关键入口

最核心的入口是 `index.tsx`。它是默认导出的 `CommandMenu` 组件，内部用 `createPortal` 把菜单挂到 `.ant-app` 或 `document.body` 上，并通过 `useGlobalStore` 里的 `showCommandMenu` 控制显示与关闭。

与它直接配套的外部挂载点有两个：

- `src/layout/GlobalProvider/CmdkLazy.tsx`：这里用 `lazy(() => import('@/features/CommandMenu'))` 懒加载整个命令菜单，说明它是全局级功能，但不是首屏立即加载。
- `src/store/global/actions/workspacePane.ts`：这里的 `toggleCommandMenu()` 是打开/关闭菜单的状态入口。根据当前片段推断，页面头部快捷按钮、热键处理等地方也是通过这个全局状态触发它的。

内部最重要的支撑入口有三个：

- `CommandMenuContext.tsx`：封装 `pages`、`search`、`typeFilter`、`selectedAgent` 等状态。
- `useCommandMenu.ts`：封装实际动作，比如跳转、发消息、创建会话、创建库、切主题、外链打开。
- `utils/context.ts` 与 `utils/contextCommands.ts`：决定“当前在哪”和“当前上下文下该显示哪些命令”。

## 主流程位置

主流程基本集中在这几处：

1. `index.tsx` 负责生命周期和渲染骨架。它先判断是否 mounted，再定位挂载根节点，最后通过 `CommandMenuProvider` 包住 `CommandMenuContent`。关闭时有一段 150ms 的收尾动画逻辑。
2. `CommandMenuContext.tsx` 负责把当前路由 `pathname` 变成菜单上下文。这里会派生出 `menuContext`、`activeAgentId`、`page`、`viewMode` 等值，并对 `search` 做 `parseSearchQuery()` 解析。
3. `useCommandMenu.ts` 是行为中枢。它会：
   - 用 `useDebounce` 和 `useSWR` 做搜索；
   - 通过 `lambdaClient.search.query.query()` 拉取统一搜索结果；
   - 处理 `handleNavigate`、`handleExternalLink`、`handleThemeChange`、`handleCreateSession` 等动作；
   - 把搜索词带到 `/agent/*`、`/image`、`/resource/*` 等页面。
4. `MainMenu.tsx`、`ContextCommands.tsx`、`SearchResults.tsx`、`AskAIMenu.tsx` 则是具体渲染分支。它们根据 `page`、`search`、`menuContext` 决定显示哪一组命令。
5. `utils/contextCommands.ts` 负责命令表合成。这里有基础 settings 命令，也有 `enableBusinessFeatures` 打开的业务扩展命令，显示前会过滤掉当前子路径。

## 推荐阅读顺序

如果你是第一次读这个目录，建议按下面顺序看：

1. `index.tsx`：先看整体挂载和分支入口。
2. `CommandMenuContext.tsx`：看状态如何在菜单内部流转。
3. `useCommandMenu.ts`：看真正的动作和副作用。
4. `utils/context.ts`、`utils/contextCommands.ts`：看上下文怎么识别、命令怎么拼装。
5. `MainMenu.tsx`、`ContextCommands.tsx`、`SearchResults.tsx`：看三类核心展示分支。
6. `components/CommandInput.tsx`、`components/CommandItem.tsx`、`components/CommandFooter.tsx`：看基础交互件。
7. `README.md`：适合做补充说明，但它更像设计文档，不一定完全和实现同步。

## 常见误区

- 容易把 `CommandMenuContext.tsx` 里的 `Context` 类型当成真实返回值。实际 `detectContext()` 最终返回的是 `MenuContext`，不是完整的 `Context` 对象。
- 容易以为 `setViewMode()` 还在控制状态。实际上它现在是兼容旧调用的空实现，`viewMode` 已经由 `search.trim().length > 0` 派生。
- 容易把 `SearchResults.tsx` 看成纯展示层。实际上它也承载了大量跳转规则，不只是渲染列表。
- 容易忽略 `enableBusinessFeatures`。`contextCommands.ts` 会在 settings 下追加业务命令，是否出现取决于服务器配置。
- 容易以为命令菜单直接由路由控制。实际上它主要由 `useGlobalStore().status.showCommandMenu` 驱动，路由只是决定当前上下文和命令集合。
- 容易把 `components/index.ts` 当成完整公开 API。它这里只导出了 `CommandFooter`、`CommandInput`、`CommandItem`，核心逻辑仍在根部文件里。
