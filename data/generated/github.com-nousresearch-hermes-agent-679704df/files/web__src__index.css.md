# 文件：web/src/index.css

## 一句话定位

`web/src/index.css` 是 dashboard 前端的全局样式入口，负责把 Tailwind v4、`@nous-research/ui` 设计系统、Hermes 默认主题变量、shadcn 兼容 token、全局字体、动画和少量工具类统一挂到整个 React 应用上。

## 它暴露/定义了什么

这个文件不导出 JavaScript 符号，而是定义全局 CSS 能力。主要包括：Tailwind 基础能力；`@nous-research/ui` 的 `fonts.css` 与 `globals.css`；Tailwind 的 `@source` 扫描范围；`JetBrains Mono` 的 `@font-face`；`:root` 上的 Hermes 默认主题变量；`html`、`body`、`#root` 的全屏布局约束；`@theme inline` 中的 Tailwind token 映射；shadcn 风格的 `--color-*`、`--radius-*` 兼容变量；若干 `@keyframes`；以及 `.scrollbar-none`、`.blend-lighter`、`.font-mono-ui`、`.grain`、`.theme-default-filler` 等工具类。

## 谁调用它

直接调用方是 `web/src/main.tsx`，通过 `import "./index.css";` 在 React 根入口加载。加载后，`web/src/App.tsx` 及其所有页面、组件都会通过 Tailwind class、CSS 变量和全局工具类间接依赖它。

更具体地看，`web/src/themes/context.tsx` 的 `ThemeProvider` 会把运行时主题写入 `document.documentElement` 的 inline style，覆盖或补充这里的 `:root` 默认值；`web/src/components/Backdrop.tsx` 消费 `--background-base`、`--warm-glow`、`--noise-opacity-mul`、`--theme-asset-bg` 等变量；`web/src/pages/ChatPage.tsx` 的嵌入式 TUI 区域依赖这里注册的 `JetBrains Mono` 和整体高度策略；大量页面组件依赖 `bg-card`、`text-muted-foreground`、`border-border`、`font-mono-ui` 等兼容 token 或工具类。

## 它调用谁

CSS 层面没有“函数调用”，但它通过 `@import` 引入三个上游样式源：`tailwindcss`、`@nous-research/ui/styles/fonts.css`、`@nous-research/ui/styles/globals.css`。其中注释明确说明 `fonts.css` 必须早于 `globals.css`，因为设计系统变量会引用这些字体族。

它还通过 `@source '../node_modules/@nous-research/ui/dist'` 告诉 Tailwind 扫描已发布的设计系统包，避免设计系统组件用到的 utility class 被 JIT 清理。`@font-face` 通过 `/fonts-terminal/JetBrainsMono-*.woff2` 读取 dashboard public 目录下的终端字体资源。

## 核心流程

应用启动时，`main.tsx` 先加载 `index.css`，Vite 的 Tailwind 插件处理 `@import`、`@source`、`@theme inline` 等 Tailwind v4 语法，生成最终 CSS。随后 React 渲染 `ThemeProvider` 和 `App`。

初始状态下，`:root` 提供 Hermes Teal 默认主题：深色背景、奶油色 midground、透明 foreground、默认字体、圆角和密度。`html`、`body`、`#root` 被设置为高度占满视口且默认隐藏溢出，保证 dashboard 像应用壳一样运行；移动端 media query 改成可滚动页面，避免小屏内容被固定高度裁掉。

运行时用户切换主题时，`ThemeProvider` 会更新同名 CSS 变量。因为本文件把 Tailwind 颜色、间距、字体、圆角都映射到这些变量，所以大部分组件无需重新实现样式逻辑，只要使用既有 class 就能跟随主题变化。

## 关键函数的高层作用

本文件没有 JavaScript 函数。可视为“关键定义”的部分有四类。

`@font-face` 定义 `JetBrains Mono` 常规、粗体、斜体三个字重/样式，服务于 `/chat` 嵌入式 xterm/TUI，避免依赖用户本机是否安装合适等宽字体。

`:root` 定义主题基线，是 Hermes dashboard 的默认视觉契约。它既给 Nous DS 提供 `--foreground`、`--midground`、`--background` 等语义层，也给自定义主题预留 `--theme-font-*`、`--theme-spacing-mul`、`--theme-radius` 等覆盖点。

`@theme inline` 把 CSS 变量接入 Tailwind token。第一段映射 `--spacing`、`--font-sans`、`--font-mono`，让密度和字体影响 utility class；第二段映射 shadcn 兼容颜色与圆角，使旧页面中的 `bg-card`、`text-primary`、`border-input` 等类继续可用。

`@keyframes` 和工具类提供跨组件的小型基础设施：sidebar tooltip、toast、dialog/fade 动画，隐藏滚动条、发光混合、grain 纹理，以及当主题提供 `assets.bg` 时隐藏默认 filler 图片的选择器逻辑。

## 修改风险

最高风险是改动 `:root` 与 `@theme inline` token。这里是设计系统、Tailwind utility、旧 shadcn class 和运行时主题之间的适配层，变量名或语义变动会让许多页面同时出现颜色不可读、边框消失、间距异常或主题切换失效。

第二类风险是全局高度和 overflow。`html`、`body`、`#root` 的桌面固定视口策略服务 dashboard 壳和嵌入式终端；随意改成普通文档流可能破坏侧边栏、ChatPage 的 xterm 容器、弹层和移动端滚动行为。反过来，移动端 media query 如果被删，长页面可能无法滚动。

第三类风险是字体导入顺序和 `@source`。`fonts.css`、`globals.css` 的顺序错误会导致设计系统字体变量指向未注册字体；移除 `@source` 可能让 `@nous-research/ui` 组件中的 Tailwind class 在构建后缺样式。

第四类风险是 shadcn 兼容 token。仓库里大量组件仍使用 `bg-card`、`text-muted-foreground`、`border-border` 等旧约定。重命名或删除这些 token 不只是视觉调整，而是一次跨页面迁移，需要同步检查 `web/src/pages`、`web/src/components` 和插件页面。
