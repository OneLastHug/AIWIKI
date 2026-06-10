# 文件：uno.config.ts

## 一句话定位

`uno.config.ts` 是项目的 UnoCSS 全局配置入口，集中定义原子类预设、内容扫描范围、语义化颜色 token、Arco Design 兼容规则、全局 preflight 样式和少量快捷类，是 renderer 样式体系和主题变量之间的桥接层。

## 它暴露/定义了什么

该文件默认导出 `defineConfig(...)` 的 UnoCSS 配置对象。配置内容主要包括：

- `presets`：启用 `presetMini()`、`presetExtra()`、`presetWind3()`，让项目可以使用 UnoCSS 基础能力、额外预设能力，以及接近 Tailwind/Windi 风格的工具类。
- `transformers`：启用 `transformerVariantGroup()` 和 `transformerDirectives({ enforce: 'pre' })`，支持变体分组写法，以及在 CSS 中使用 UnoCSS 指令。
- `content.pipeline`：用正则指定参与扫描的模块类型，包括 `.ts`、`.tsx`、`.js`、`.jsx`、`.vue`、`.css`，排除 `node_modules` 和 `.html`。
- `rules`：补充项目自定义工具类规则，尤其是 Arco Design 变量映射、项目特殊颜色、`animate-wiggle` 动画类。
- `preflights`：注入全局基础 CSS，包括所有元素默认 `color: inherit`，以及 `wiggle` 关键帧。
- `shortcuts`：定义 `flex-center` 这类组合工具类。
- `theme.colors` 和 `theme.fontFamily`：把项目语义颜色、品牌色、AOU 色阶、组件专用色等映射到 CSS 变量，并统一 `mono` 等宽字体栈。

## 谁调用它

直接调用方不是业务代码，而是 UnoCSS 在构建/开发服务中的配置加载机制。根据 `package.json` 可见，项目通过 `electron-vite dev --config packages/desktop/electron.vite.config.ts` 启动开发，通过 `electron-vite build --config packages/desktop/electron.vite.config.ts` 打包；同时依赖中包含 `unocss` 和 `unocss-preset-extra`。因此根据当前片段推断，`electron-vite`/Vite 构建链中的 UnoCSS 插件会自动读取仓库根目录的 `uno.config.ts`，再扫描 renderer 相关源码中的 class 名并生成 CSS。

业务侧的“调用”通常体现为 JSX/TSX、CSS、Vue 文件里写入 `bg-base`、`text-t-primary`、`border-arco-1`、`flex-center`、`animate-wiggle` 等类名；这些类名不会 import 此文件，而是在构建时被 UnoCSS 识别并展开。

## 它调用谁

文件顶部从 `unocss` 调用 `defineConfig`、`presetMini`、`presetWind3`、`transformerDirectives`、`transformerVariantGroup`，从 `unocss-preset-extra` 调用 `presetExtra`。配置规则生成的 CSS 大量引用运行时 CSS 变量，例如 `--text-primary`、`--bg-base`、`--primary`、`--color-text-1`、`--color-fill-1` 等；这些变量应由项目全局主题样式或 Arco Design 样式注入。根据仓库规范，Arco 主题覆盖集中在 `packages/desktop/src/renderer/styles/arco-override.css`，所以这里更像消费主题变量，而不是定义变量源头。

## 核心流程

构建或开发服务启动后，UnoCSS 读取 `uno.config.ts`，先注册预设和 transformer，再按 `content.pipeline.include` 扫描模块内容。这里使用正则而不是 glob，是为了兼容 `electron-vite` 将 renderer root 设置到 `packages/desktop/src/renderer/` 后，普通 glob 可能解析成错误嵌套路径的问题。扫描到类名后，UnoCSS 先用预设处理通用工具类，再用 `rules` 匹配项目扩展类，最后把匹配结果输出为 CSS。全局 `preflights` 会额外注入基础样式和动画 keyframes，`theme.colors` 则让 `bg-*`、`text-*`、`border-*` 等主题色类指向 CSS 变量，从而跟随明暗主题和 Arco token 变化。

## 关键函数的高层作用

`defineConfig` 是配置包装函数，提供 UnoCSS 配置结构和类型推断，是本文件唯一真正的导出入口。

`presetMini`、`presetWind3`、`presetExtra` 负责扩展可用工具类集合。`presetMini` 提供基础原子类，`presetWind3` 提供更接近主流 utility CSS 的语法，`presetExtra` 补充额外能力。

`transformerVariantGroup` 让代码可以写分组变体，减少重复前缀；`transformerDirectives` 让 CSS 文件中的 UnoCSS 指令在较早阶段被处理。

`rules` 中的正则规则是本文件最关键的项目逻辑：它把 `text-1` 到 `text-4` 映射到 Arco 的 `--color-text-*`，把 `bg-fill-*`、`border-arco-*`、`bg-primary-light-*`、`bg-primary-1` 等映射到 Arco 色彩变量，也定义了若干项目专用别名和 `animate-wiggle`。这些规则决定了业务 class 名最终生成什么 CSS 属性。

`preflights.getCSS` 是全局样式注入点；这里只做默认文字继承和动画定义，范围小但影响全局。

## 修改风险

最大风险是 class 名和 CSS 变量的契约被破坏。比如删除或改名 `theme.colors` 中的 `t-primary`、`base`、`brand`、`aou`，会让大量 `text-t-primary`、`bg-base`、`text-aou-*` 之类的类失效或变色。修改 `rules` 中的正则也要谨慎，因为它们覆盖 Arco token 的桥接语义；例如 `border-1` 和 `border-arco-1` 在注释中已经区分了项目背景色边框与 Arco 官方边框色，混淆后可能造成全局边框观感回退。

`content.pipeline` 的 include/exclude 风险也很高。这里特意用正则匹配绝对 module id，说明曾经存在 Vite root 导致 glob 扫描错误的问题；随意改回 glob，可能让 renderer 里的类名不被扫描，表现为开发环境或打包产物缺 CSS。

`preflights` 是全局注入，任何新增选择器都会影响整站。尤其是 `* { color: inherit; }` 与 Arco 组件默认样式存在叠加关系，调整时需要检查基础文本、按钮、弹窗、表单、代码块等组件。`animate-wiggle` 这种动画类虽然局部使用，但 keyframes 名称全局可见，改名会让已有 `animate-wiggle` class 只剩 animation 引用而没有关键帧。

新增颜色时应优先挂到现有 CSS 变量体系，而不是写死颜色值；否则会破坏项目“语义 token + 主题变量”的样式约定，也不利于暗色主题和 Arco 主题覆盖。
