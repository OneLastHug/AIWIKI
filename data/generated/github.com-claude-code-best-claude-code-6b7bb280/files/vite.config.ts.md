# 文件：vite.config.ts
## 一句话定位
这是仓库的 Vite 打包配置入口，专门服务于 CLI 的生产构建：把 `src/entrypoints/cli.tsx` 打成适合 Node/Bun 运行的 SSR 产物，并在构建期处理 feature flag、`import.meta.require`、原始文本资源和少量兼容性补丁。

## 它暴露/定义了什么
它默认导出一个 `defineConfig(...)` 的 Vite 配置对象，同时在文件内部定义了两个关键辅助能力：

1. `isAcknowledgedBuildWarning(...)`：过滤掉仓库里已经确认并接受的构建告警。
2. `rawAssetPlugin(...)`：把 `.md`、`.txt`、`.html`、`.css` 这类文件按原始字符串导入，而不是交给默认资源处理。

配置本身还显式定义了：
- `ssr` 目标为 `node`
- 构建入口为 `src/entrypoints/cli.tsx`
- 输出到 `dist`
- 产物分 chunk，而不是单文件
- 全局 `define` 替换 `MACRO.*` 和 `process.env.NODE_ENV`
- `resolve.alias` 中的 `src/` 路径别名

## 谁调用它
主要调用者是 Vite 构建链本身，也就是 `vite build`。从 `package.json` 可以直接看到：
- `build:vite` 会先跑 `vite build`
- `build:vite:only` 直接调用 `vite build`
- `prepublishOnly` 也会走这条链
- CI 里也会执行 `bun run build:vite`

根据当前片段推断，这个文件不会在运行时被 CLI 直接加载，它只在构建阶段生效。

## 它调用谁
它依赖并调用了这些外部模块和脚本：

- `./scripts/defines`：读取 `getMacroDefines()`，把版本号、构建时间和若干空白占位宏注入到编译期。
- `./scripts/vite-plugin-feature-flags`：把 `feature('X')` 这类条件在打包前折叠成布尔字面量。
- `./scripts/vite-plugin-import-meta-require`：修正 `import.meta.require`，让产物在 Node 环境下也能工作。
- Node 标准库：`path`、`url`、`fs`，用于定位项目根目录和读取原始资源文件。

同时，它也在 Rollup 层面配置了 `onwarn`，把特定 warning 交给 `isAcknowledgedBuildWarning()` 统一吞掉。

## 核心流程
这份配置的核心不是“页面应用打包”，而是“命令行程序的可移植构建”。流程大致是：

1. 先把项目根目录算出来，作为所有路径的锚点。
2. 在 `build.rollupOptions.input` 里指定 CLI 入口 `src/entrypoints/cli.tsx`。
3. 通过 `ssr: true` 和 `ssr.target: 'node'` 告诉 Vite：这是 Node 运行时产物，不是浏览器包。
4. 在 Rollup 插件阶段先做三件事：
   - 将 feature gate 提前折叠，避免某些分支里的不可达 `require()` 影响解析
   - 把 `.md/.txt/.html/.css` 按 raw string 导入
   - 修复 `import.meta.require` 的兼容性
5. 在 `define` 阶段注入 `MACRO.VERSION`、`MACRO.BUILD_TIME` 等常量，并强制 `NODE_ENV=production`。
6. 在 `resolve` 阶段统一 `src/` 别名、React 单例依赖和扩展名解析顺序。
7. 对已知、可接受的 warning 做白名单过滤，减少构建噪音。

## 关键函数的高层作用
`isAcknowledgedBuildWarning(...)` 的作用不是“处理所有 warning”，而是维护一个很窄的白名单，避免已知噪音淹没真正的问题。它当前放行两类情况：一类是和 `@protobufjs+inquire` 相关的 `EVAL`，另一类是和若干具体文件有关的 `INEFFECTIVE_DYNAMIC_IMPORT`。

`rawAssetPlugin(...)` 的职责很单一：让特定扩展名文件像字符串一样被导入。它适合承载 prompt、模板、文档片段或静态样式文本，避免被默认资源策略改写。

`featureFlagsPlugin()` 和 `importMetaRequirePlugin()` 不是本文件定义，但它们是这份配置的骨架。前者决定“哪些分支会被打掉”，后者决定“产物能不能在 Node 上正常 require 兼容模块”。

## 修改风险
这类文件改动的风险通常不在语法，而在构建语义：

- 改错 `ssr.external/noExternal` 会导致依赖被错误内联或遗漏，运行时才炸。
- 改坏 feature flag 折叠，会让不可达代码提前被 Rollup 解析，触发缺失文件或错误导入。
- 放宽或删掉 warning 白名单，容易淹没真正的新问题；过度收窄则会让 CI 噪音回潮。
- `rawAssetPlugin` 扩展名列表如果变动，某些文本资源可能被当成普通模块处理，导致导入结果变化。
- `define` 中的宏如果和 `scripts/defines.ts` 不一致，会造成版本、构建时间或生产模式判断错位。
- `resolve.dedupe` 若处理不当，React 相关包可能出现多实例，进而引发 Hooks 或上下文异常。

总的来说，这个文件是“构建行为的总开关”，改它时要按产物兼容性来评估，而不是只看构建能否跑通。
