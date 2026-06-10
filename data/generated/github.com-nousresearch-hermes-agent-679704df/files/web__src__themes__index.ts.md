# 文件：web/src/themes/index.ts

## 一句话定位

`web/src/themes/index.ts` 是 dashboard 前端主题系统的统一出口文件，也就是一个很薄的 barrel module：它不实现主题逻辑，只把 `ThemeProvider`、`useTheme`、内置主题预设和主题类型集中再导出，供页面和组件用 `@/themes` 这个稳定入口访问。

## 它暴露/定义了什么

这个文件暴露三类能力：

第一类是运行时主题上下文能力：从 `./context` 再导出 `ThemeProvider` 和 `useTheme`。`ThemeProvider` 负责把主题状态挂到 React Context，并把主题转换成 `:root` 上的 CSS variables；`useTheme` 是组件读取当前主题、可选主题列表和 `setTheme` 的 hook。

第二类是内置主题数据：从 `./presets` 再导出 `BUILTIN_THEMES` 和 `defaultTheme`。这些是前端本地可直接解析的主题定义，`BUILTIN_THEMES` 是按主题名索引的集合，`defaultTheme` 是兜底主题。

第三类是 TypeScript 类型：从 `./types` 再导出 `DashboardTheme`、`ThemeLayer`、`ThemeListEntry`、`ThemeListResponse`、`ThemePalette`。这些类型描述主题结构、API 返回列表和调色板层级。注意这里使用 `export type`，编译后不会产生运行时代码。

## 谁调用它

直接通过 `@/themes` 或 `./themes` 使用这个入口的主要位置有：

`web/src/main.tsx` 引入 `ThemeProvider`，把整个 React 应用包在主题上下文里。这是主题系统真正生效的根入口。

`web/src/App.tsx` 引入 `useTheme`，读取当前 `theme`，并根据 `theme.layoutVariant` 等字段调整 shell 布局，比如标准布局、cockpit 布局或 tiled 布局。

`web/src/components/ThemeSwitcher.tsx` 引入 `BUILTIN_THEMES`、`useTheme`，并从该入口导入 `DashboardTheme`、`ThemeListEntry` 类型。它是用户切换主题的 UI，依赖 `availableThemes`、`themeName`、`setTheme` 来展示列表和触发切换。

另外，`web/src/lib/api.ts` 直接从 `@/themes/types` 引入 `DashboardTheme`，没有走 `index.ts`。这说明类型入口既可以通过 barrel 暴露给组件，也允许底层 API 层直接依赖具体类型文件。

## 它调用谁

`index.ts` 自身没有函数调用，也没有状态、副作用或条件逻辑。它只通过 ES module re-export 静态依赖三个邻近模块：

`web/src/themes/context.tsx`：主题上下文与应用逻辑所在地。

`web/src/themes/presets.ts`：内置主题定义所在地。

`web/src/themes/types.ts`：主题数据模型和 API 结构类型所在地。

根据当前片段推断，构建工具会把 `@/themes` 解析到该目录的 `index.ts`，依据是多个组件使用 `import { ... } from "@/themes"`，且该文件正好提供这些导出。

## 核心流程

核心流程不是发生在 `index.ts` 内部，而是由它暴露出的模块组合完成。

应用启动时，`web/src/main.tsx` 从 `./themes` 取到 `ThemeProvider`，用它包裹主应用。`ThemeProvider` 初始化时先从 `localStorage` 读取 `hermes-dashboard-theme`，没有记录则使用 `"default"`。初始可选主题来自 `BUILTIN_THEMES`，因此即使后端主题接口失败，前端仍有内置主题可用。

挂载后，`ThemeProvider` 调用 `api.getThemes()` 拉取服务端主题列表。服务端可能返回内置主题摘要，也可能返回用户 YAML 主题的完整 `definition`。这些结果会更新 `availableThemes`，并把用户主题定义缓存到 `userThemeDefs`。

当 `themeName` 或用户主题定义变化时，`ThemeProvider` 解析出完整 `DashboardTheme`，再通过内部 `applyTheme` 把主题字段转换为 CSS variables、字体 stylesheet、custom CSS 和 layout variant。页面组件不需要直接操作 DOM，只需要读取主题上下文或消费 CSS variables。

用户在 `ThemeSwitcher` 中点击主题时，组件调用 `setTheme(name)`。`setTheme` 会校验主题名是否已知，写入 React state 和 `localStorage`，并调用 `api.setTheme(next)` 尝试同步到后端。同步失败会被吞掉，因此前端切换仍然立即生效。

## 关键函数的高层作用

`index.ts` 没有自己定义函数。它的关键意义在于把下面这些核心函数和数据作为公共 API 暴露出去。

`ThemeProvider`：主题系统的运行时容器。它管理当前主题名、可选主题列表、用户主题定义，并负责把主题应用到 DOM 根节点。它是主题状态和 CSS 表现之间的桥。

`useTheme`：组件侧访问主题上下文的 hook。调用者通过它获得 `theme`、`themeName`、`availableThemes`、`setTheme`，不需要知道主题如何从 API 加载、如何落盘或如何写 CSS variables。

`BUILTIN_THEMES`：内置主题注册表。`ThemeProvider` 用它初始化列表和解析内置主题，`ThemeSwitcher` 用它为内置主题绘制 swatch。新增内置主题通常应在 `presets.ts` 注册，而不是改 `index.ts` 的业务逻辑。

`defaultTheme`：主题解析失败时的兜底值。它保证未知主题名、API 失败或用户主题定义尚未加载时，界面仍能回到稳定外观。

辅助函数如 `paletteVars`、`typographyVars`、`layoutVars`、`assetVars`、`componentStyleVars`、`applyTheme` 位于 `context.tsx`，负责把结构化主题对象转换成 CSS variables 和 DOM 注入行为；它们不是由 `index.ts` 直接调用，而是被 `ThemeProvider` 内部使用。

## 修改风险

最大风险是把这个文件误当成普通内部文件。它实际上是 `@/themes` 的公共入口，改变导出名称会直接破坏 `App.tsx`、`ThemeSwitcher.tsx`、`main.tsx` 等调用方。例如删除 `useTheme` 或 `ThemeProvider` 会导致应用无法编译；删除类型导出会影响组件类型检查。

第二个风险是引入运行时副作用。当前 `index.ts` 只是纯 re-export，导入它不会额外执行主题应用逻辑。若在这里添加初始化代码、DOM 操作或 API 调用，会让任何 `@/themes` 的导入都可能触发副作用，增加启动顺序和测试的不确定性。

第三个风险是制造循环依赖。当前 `context.tsx` 直接从 `./presets`、`./types` 导入，避免通过 `index.ts` 反向绕回。如果未来让底层主题模块从 `@/themes` 导入公共入口，容易形成 `index.ts -> context.tsx -> index.ts` 之类的循环，轻则类型和 undefined 问题，重则运行时初始化顺序异常。

第四个风险是错误区分 type export 与 runtime export。`DashboardTheme` 等类型使用 `export type` 是合理的，能避免把纯类型变成运行时依赖。若为了方便改成普通 `export`，通常收益很小，却可能改变打包依赖图。

第五个风险是导出范围膨胀。这个入口应该暴露稳定、面向组件的主题 API，而不是把 `context.tsx` 里的内部 CSS variable builder、DOM 注入函数全部公开。过度公开会让外部组件绕过 `ThemeProvider` 修改主题状态，后续重构成本会明显上升。
