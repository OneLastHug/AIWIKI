# 目录：src/commands/plugin

## 它负责什么

`src/commands/plugin` 是 Claude Code 里 `/plugin` 命令的整套 UI 与路由层。它不只是一个“插件管理页”，而是把插件相关的多种工作流统一收进同一个入口：发现和安装插件、管理已安装插件、管理 marketplace、校验插件包、展示错误与帮助说明。

从结构上看，这个目录承担的是“命令入口后的交互编排”，真正的业务能力大多分散在 `src/utils/plugins/*`、`src/state/*` 和更底层的插件加载/存储模块里。这里负责的是把这些能力拼成可用的终端界面。

## 直接子目录地图

这个目录本身没有继续向下展开的业务子目录，当前可见的直接子目录只有 `__tests__`，而且只放了 `parseArgs.test.ts` 这一类命令解析测试。也就是说，这里更像一个“扁平的功能目录”，不是一棵多层树。

按文件角色来看，可以粗分为几组：

- 入口包装：`index.tsx`、`plugin.tsx`
- 总控与路由：`PluginSettings.tsx`、`parseArgs.ts`、`types.ts`
- 插件发现与安装：`DiscoverPlugins.tsx`、`BrowseMarketplace.tsx`、`AddMarketplace.tsx`
- 已安装插件管理：`ManagePlugins.tsx`、`UnifiedInstalledCell.tsx`、`unifiedTypes.ts`
- marketplace 管理：`ManageMarketplaces.tsx`
- 校验与错误：`ValidatePlugin.tsx`、`PluginErrors.tsx`、`PluginTrustWarning.tsx`
- 配置向导：`PluginOptionsFlow.tsx`、`PluginOptionsDialog.tsx`
- 辅助工具：`pluginDetailsHelpers.tsx`、`usePagination.ts`

## 关键入口

最外层入口是 `index.tsx`。它把这个目录注册成一个本地 JSX 命令，名字是 `plugin`，别名是 `plugins` 和 `marketplace`，描述是“Manage Claude Code plugins”，并通过动态导入加载 `./plugin.js`。

真正的命令执行入口在 `plugin.tsx`。这个文件非常薄，只做一件事：把 `onDone` 和 `args` 传给 `PluginSettings`。因此可以把它理解为“命令协议层”和“UI 总控层”之间的适配器。

`PluginSettings.tsx` 是这里最关键的总入口。它先调用 `parsePluginArgs(args)`，再把解析结果映射成初始 `ViewState`，然后根据当前状态决定渲染哪一个子面板。它同时也是 tab 切换、错误计数、退出、子页面回跳、插件刷新标记的统一协调点。

`parseArgs.ts` 是这个目录的命令路由基础。它把 `/plugin` 后面的字符串解析成结构化命令，比如 `install`、`manage`、`marketplace add`、`validate`、`help` 等。测试文件 `__tests__/parseArgs.test.ts` 直接覆盖了这层分支。

## 主流程位置

主流程基本可以概括成一条线：

1. 全局 CLI 注册 `/plugin` 命令。根据 `src/main.tsx` 的命令树，`plugin` 是一个正式子命令，也有 `plugins`、`marketplace` 这类别名入口。
2. 命令被转交到 `src/commands/plugin/index.tsx`，再由 `plugin.tsx` 进入 `PluginSettings`。
3. `PluginSettings.tsx` 先解析参数，再决定初始视图：
   - `help` 直接输出帮助文本
   - `validate` 进入 `ValidatePlugin`
   - `marketplace list` 进入 `MarketplaceList`
   - `add-marketplace` 进入 `AddMarketplace`
   - 其余情况进入带 `Tabs` 的主界面
4. 主界面分成四个 tab：`discover`、`installed`、`marketplaces`、`errors`。
5. 每个 tab 内部再委派到对应子组件，例如 `DiscoverPlugins`、`BrowseMarketplace`、`ManagePlugins`、`ManageMarketplaces`。
6. 某些动作会触发后续配置流程，比如安装完成后进入 `PluginOptionsFlow`，再由 `PluginOptionsDialog` 逐项补齐用户配置。

从代码形态上看，这里是一个典型的“状态驱动型终端界面”：`viewState` 决定渲染哪条分支，`setViewState` 负责在不同工作流之间跳转，`setResult` 则把结果回传给命令完成回调。

## 推荐阅读顺序

如果是第一次理解这个目录，建议按下面顺序看：

1. `index.tsx`，先确认命令是怎么被挂到 CLI 上的。
2. `plugin.tsx`，看入口怎么交给 UI 总控。
3. `parseArgs.ts`，理解命令字符串如何变成结构化路由。
4. `types.ts`，先把 `ViewState` 的状态集合看清楚。
5. `PluginSettings.tsx`，这是整个目录的中枢，负责调度所有子页面。
6. 再按需看 `DiscoverPlugins.tsx`、`ManagePlugins.tsx`、`ManageMarketplaces.tsx`、`AddMarketplace.tsx`、`ValidatePlugin.tsx` 这些具体工作流。

如果你只想抓主干，不用一开始就钻到 `pluginDetailsHelpers.tsx`、`usePagination.ts` 这些辅助层。

## 常见误区

一个常见误区是把这个目录当成“插件业务实现本体”。实际上，这里更多是命令 UI 和流程编排，真正的数据读写、缓存、权限、市场加载、插件扫描都在 `src/utils/plugins/*` 和相关状态模块里。

第二个误区是忽略 `PluginSettings.tsx` 的中心地位。很多人会先看 `DiscoverPlugins` 或 `ManagePlugins`，但如果不先理解 `viewState`、`activeTab` 和 `parsePluginArgs`，很容易看不懂页面为什么会跳来跳去。

第三个误区是把 marketplace 和 plugin 当成两个完全独立的命令。这里的设计明显是合并的：`/plugin marketplace ...` 只是 `/plugin` 的一个分支，`marketplace` 还被当作别名入口之一。

最后，`__tests__` 里的测试只覆盖了参数解析这类基础逻辑，不代表整个目录只有这点复杂度。根据当前片段推断，真正的复杂度集中在 `PluginSettings.tsx` 的状态分发，以及各个子面板和底层插件系统之间的联动。
