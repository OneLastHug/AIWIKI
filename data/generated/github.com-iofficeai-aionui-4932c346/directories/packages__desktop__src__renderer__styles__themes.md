# 目录：packages/desktop/src/renderer/styles/themes

## 它负责什么

`packages/desktop/src/renderer/styles/themes` 是桌面端 renderer 侧的基础主题样式目录，主要承接“静态 CSS 主题底座”的职责。它不负责主题选择、配置存储或 IPC 分发，而是为渲染进程提供一组可被全局样式加载的 CSS 变量、基础色彩规则和默认配色方案规则。

从当前仓库片段看，AionUi 的主题系统分成两层：一层是这里的 CSS 主题基础设施，另一层是 TypeScript 运行时主题系统。运行时主题系统位于 `packages/desktop/src/common/theme`、`packages/desktop/src/renderer/utils/theme`、`packages/desktop/src/renderer/hooks/system/useTheme.ts`、`packages/desktop/src/renderer/hooks/context/ThemeContext.tsx` 等位置，负责读取配置、解析主题、写入 DOM 属性、注入 token 样式，并通过 IPC 同步到其他窗口。`styles/themes` 更像是这些运行时机制的样式承接层：当根节点存在 `data-theme="light"` 或 `data-theme="dark"`，或者存在 `data-color-scheme="default"` 时，这里的 CSS 可以提供默认外观基础。

该目录与 `packages/desktop/src/renderer/styles/arco-override.css`、`packages/desktop/src/renderer/styles/layout.css`、`packages/desktop/src/renderer/styles/markdown.css` 同属 renderer 全局样式体系。区别在于，`themes` 更关注主题变量和颜色方案，`arco-override.css` 更关注 Arco Design 组件的全局覆盖，`layout.css` 更偏布局基线，`markdown.css` 则服务内容渲染场景。

## 直接子目录地图

这个目录当前没有直接子目录，是一个较小的主题 CSS 聚合目录。直接文件包括：

`packages/desktop/src/renderer/styles/themes/index.css`：根据命名推断是主题 CSS 的聚合入口，通常用于集中引入 `base.css` 和配色方案文件，供 renderer 全局样式入口加载。

`packages/desktop/src/renderer/styles/themes/base.css`：根据当前片段推断是主题基础变量或基础选择器定义的位置，可能定义与 `data-theme` 相关的通用 CSS 变量、背景色、文字色、边框色等底层 token。

`packages/desktop/src/renderer/styles/themes/default-color-scheme.css`：根据命名推断是默认 color scheme 的规则文件，和 `index.html` 里的 `data-color-scheme="default"` 属性存在语义对应关系。

`packages/desktop/src/renderer/styles/themes/README.md`：目录说明文档，通常用于解释本目录的设计目的、变量约定或迁移背景。由于本任务只做概览，阅读时可把它当作理解该目录边界的第一资料。

## 关键入口

静态入口首先看 `packages/desktop/src/renderer/styles/themes/index.css`。它是目录内最像“对外出口”的文件，其他全局样式或 renderer 初始化代码如果要接入主题 CSS，通常不会逐个引用 `base.css`、`default-color-scheme.css`，而是通过这个聚合入口进入。当前命令输出没有展示 import 链，因此这里属于根据文件命名和目录结构的推断。

运行时入口不在本目录，而在 `packages/desktop/src/renderer/utils/theme/applyTheme.ts`。其中 `applyTheme(theme)` 会把 `theme.appearance` 写到 `document.documentElement` 的 `data-theme`，并把同样的 appearance 写到 `body` 的 `arco-theme`。这一步使 CSS 选择器、Arco 主题覆盖和自定义 token 注入能够同时生效。该文件还会通过 `theme-tokens`、`theme-decoration` 两个 style 节点注入解析后的 token 和自定义 CSS。

更上层的 React 入口是 `packages/desktop/src/renderer/hooks/system/useTheme.ts` 和 `packages/desktop/src/renderer/hooks/context/ThemeContext.tsx`。`useTheme.ts` 负责初始化主题、读取 `theme.activeId` 和 `theme.userThemes`、调用 `resolveActiveTheme`、执行 `applyTheme`，并监听 `ipcBridge.theme.changed`。`ThemeContext.tsx` 则把主题能力包装成 React context，向组件暴露 `theme`、`setTheme`、`activeTheme`、`selectTheme` 等接口。

## 主流程位置

主题主流程从页面启动阶段开始。`packages/desktop/src/renderer/index.html` 的 `<html>` 默认带有 `data-theme="light"` 和 `data-color-scheme="default"`，并在内联脚本中尝试从 `localStorage` 读取 `__aionui_theme`，同步恢复 `data-theme`，以减少启动时的主题闪烁。随后 body 也会同步设置 `arco-theme`。

React 初始化后，`packages/desktop/src/renderer/hooks/system/useTheme.ts` 中的初始化逻辑继续接管主题状态：它等待配置服务可用，读取当前激活主题 id，合并内置主题和用户主题，再通过 `packages/desktop/src/common/theme/resolveTheme.ts` 解析出真正可用的 `Theme`。解析成功后调用 `applyTheme` 写入 DOM 和动态 style，并通过 `ipcBridge.theme.setActive` 通知主进程缓存和广播。

跨窗口同步通过 `packages/desktop/src/common/adapter/ipcBridge.ts` 中的 `theme.changed`、`theme.setActive`、`theme.requestCurrent` 完成。根据当前片段推断，主进程持有当前 resolved theme 的缓存，renderer 在主题变更时发布，其他窗口或弹出界面收到后调用自己的 `applyTheme`。例如 `packages/desktop/src/renderer/pet/petConfirmRenderer.ts` 会监听主进程主题变化并应用主题。

配置迁移流程在 `packages/desktop/src/common/config/configService.ts` 和 `packages/desktop/src/common/theme/migrateThemeConfig.ts`。旧配置中的 `theme`、`css.activeThemeId`、`css.themes` 会迁移到新的 `theme.activeId`、`theme.userThemes`。这说明当前主题体系已经从简单 light/dark 切换，演进到了“内置主题 + 用户主题 + token/css 扩展”的统一模型。

## 推荐阅读顺序

建议先读 `packages/desktop/src/renderer/styles/themes/README.md`，确认目录作者对 CSS 变量、默认方案和边界的说明。随后看 `packages/desktop/src/renderer/styles/themes/index.css`，理解本目录对外暴露了哪些 CSS 片段。再看 `base.css` 与 `default-color-scheme.css`，把 `data-theme`、`data-color-scheme` 和实际变量定义对应起来。

理解静态样式后，再转到运行时链路：先看 `packages/desktop/src/renderer/index.html`，了解启动时如何避免主题闪烁；再看 `packages/desktop/src/renderer/utils/theme/applyTheme.ts`，掌握 DOM 属性和动态 style 注入；然后看 `packages/desktop/src/renderer/hooks/system/useTheme.ts` 与 `packages/desktop/src/renderer/hooks/context/ThemeContext.tsx`，理解 React 层如何选择和传播主题。最后补读 `packages/desktop/src/common/theme/types.ts`、`packages/desktop/src/common/theme/resolveTheme.ts`、`packages/desktop/src/common/theme/migrateThemeConfig.ts`，把主题数据结构、兜底逻辑和旧配置迁移串起来。

## 常见误区

不要把 `styles/themes` 理解成完整的主题系统。它只是 renderer 全局 CSS 主题底座，真正的主题选择、配置读取、主题解析、IPC 广播和动态 token 注入都在 TypeScript 运行时链路中。

不要只改 `data-theme` 相关 CSS 而忽略 Arco。应用主题时同时设置了 `html[data-theme]` 和 `body[arco-theme]`，Arco Design 组件的表现还受到 `packages/desktop/src/renderer/styles/arco-override.css` 以及 Arco 自身主题机制影响。

不要在业务组件里硬编码颜色绕过这里的变量体系。项目约定要求颜色使用语义 token 或 CSS 变量；如果组件直接写死颜色，可能在 dark/light 或用户主题下出现不可读、对比度不足、边框不一致等问题。

不要把 `data-color-scheme="default"` 和 `data-theme="light"` 混为一谈。前者更像配色方案类别，后者是 light/dark 外观属性。根据当前片段推断，`default-color-scheme.css` 处理默认色彩方案，而 `applyTheme.ts` 主要驱动 `data-theme` 和 Arco 的 appearance。

不要在本目录新增复杂业务样式。这里应保持为主题基础层；页面、组件、Markdown、布局和 Arco 覆盖都有各自位置。把业务样式塞进 `themes` 会让主题变量和具体 UI 规则耦合，后续维护和主题扩展都会变难。
