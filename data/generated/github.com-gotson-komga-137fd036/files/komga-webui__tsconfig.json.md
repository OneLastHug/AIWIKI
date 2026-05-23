# 文件：komga-webui/tsconfig.json

## 它负责什么

`komga-webui/tsconfig.json` 是 Komga 前端项目的 TypeScript 编译配置文件。它不直接写业务逻辑，而是告诉 TypeScript、Vue CLI、Jest、Webpack 以及编辑器：前端源码应该按什么 JavaScript 目标编译、如何解析模块、哪些全局类型可用、哪些文件要纳入类型检查，以及项目里的路径别名应该如何理解。

从同目录 `package.json` 可以看出，`komga-webui` 是一个 Vue 2 前端应用，核心技术栈包括 `vue`、`vue-router`、`vuex`、`vuetify`、`typescript`、`@vue/cli-service`、`@vue/cli-plugin-typescript`、`@vue/cli-plugin-unit-jest`。因此这个 `tsconfig.json` 主要服务于 Vue CLI 的 TypeScript 构建、开发服务器、单元测试和 IDE 类型提示。

它的作用可以概括为三点：

1. 约束 TypeScript 代码质量，例如启用 `strict`。
2. 适配 Vue 2 单文件组件、Webpack、Jest、Vuetify 等工具链。
3. 定义前端源码范围和 `@/` 路径别名，让项目中的导入路径保持简洁。

## 关键组成

这个文件的主体是 `compilerOptions`、`include` 和 `exclude` 三块。

`compilerOptions.target` 设置为 `esnext`，表示 TypeScript 输出目标面向较新的 ECMAScript 能力。也就是说，TypeScript 不会刻意把语法降级到很老的浏览器环境。实际浏览器兼容性通常还会由 Babel、Vue CLI、`.browserslistrc` 等共同决定，而不是只靠 `tsconfig.json`。

`compilerOptions.module` 也是 `esnext`，表示模块语法保留为现代 ES Module 风格。这很适合交给 Webpack/Vue CLI 继续做打包、代码分割和优化。

`compilerOptions.strict` 设置为 `true`，这是比较重要的质量开关。它会开启一组严格类型检查规则，例如更严格的空值、函数参数、隐式 `any` 等检查。对于一个大型前端项目来说，这能尽早暴露类型问题，但也要求业务代码、Vue 组件和测试代码的类型声明相对规范。

`compilerOptions.jsx` 设置为 `preserve`，表示如果项目里出现 `.tsx` 或 JSX 语法，TypeScript 不负责最终转换 JSX，而是保留给后续工具链处理。虽然这个仓库主要是 Vue 2 项目，但 `include` 中确实包含了 `src/**/*.tsx` 和 `tests/**/*.tsx`，说明配置上允许 TSX 文件存在。

`compilerOptions.importHelpers` 设置为 `true`，表示 TypeScript 在需要辅助函数时倾向于从 `tslib` 引入 helper，而不是在每个编译文件中重复生成辅助代码。这样可以减少重复输出。这里需要注意，具体是否实际产生影响，还取决于 Vue CLI、Babel 和 TypeScript loader 的处理链路。

`compilerOptions.moduleResolution` 为 `node`，表示模块解析方式按 Node.js 生态常见规则处理，例如解析 `node_modules`、识别包入口、补全扩展名等。这与 Vue CLI/Webpack 项目是匹配的。

`compilerOptions.esModuleInterop` 和 `allowSyntheticDefaultImports` 都是为了改善 CommonJS 与 ES Module 混用时的导入体验。前端依赖里有不少历史包或 CommonJS 风格包，例如 `lodash`、部分 Vue 生态插件等，这两个配置能让 `import xxx from 'xxx'` 这种写法更容易通过类型检查。

`compilerOptions.sourceMap` 为 `true`，表示生成 source map，方便开发时在浏览器 DevTools 或测试错误栈中映射回 TypeScript/Vue 源码。

`compilerOptions.useUnknownInCatchVariables` 设置为 `false`。在较新的 TypeScript 中，`catch (e)` 的变量默认可以被视为 `unknown`，这更安全但需要更多类型收窄。这里显式设为 `false`，意味着 catch 变量更接近旧行为，通常是为了减少现有代码迁移成本。

`compilerOptions.baseUrl` 是 `"."`，表示模块路径解析以 `komga-webui` 目录为基础。配合下面的 `paths` 使用。

`compilerOptions.paths` 定义了一个关键别名：

```json
"@/*": [
  "src/*"
]
```

这意味着项目中可以写：

```ts
import Something from '@/xxx'
```

来代替相对路径：

```ts
import Something from '../../xxx'
```

在 Vue CLI 项目中，`@` 指向 `src` 是非常常见的约定。这个配置主要给 TypeScript 和 IDE 理解别名；Webpack/Vue CLI 通常也会有对应的解析规则。

`compilerOptions.types` 声明了全局可用的类型包：

```json
"types": [
  "webpack-env",
  "jest",
  "vuetify",
  "webpack"
]
```

这几个类型分别服务于不同场景：

`webpack-env` 提供 Webpack 环境相关类型，例如 `require.context` 这类 Webpack 特有 API。

`jest` 提供测试环境的全局类型，例如 `describe`、`it`、`expect`。

`vuetify` 提供 Vuetify 组件库相关类型支持。

`webpack` 提供 Webpack 本身的类型定义。`package.json` 里也有 `@types/webpack`，与这里对应。

`compilerOptions.lib` 包含：

```json
"lib": [
  "esnext",
  "dom",
  "dom.iterable",
  "scripthost"
]
```

这表示项目代码可以使用现代 ECMAScript API、浏览器 DOM API、可迭代 DOM 集合，以及部分脚本宿主环境类型。对于浏览器前端来说，`dom` 和 `dom.iterable` 很关键，例如 `document`、`window`、`NodeList`、`File`、`Blob` 等类型都来自这些库。

`include` 指定参与 TypeScript 处理的文件范围：

```json
"include": [
  "src/**/*.ts",
  "src/**/*.tsx",
  "src/**/*.vue",
  "tests/**/*.ts",
  "tests/**/*.tsx"
]
```

这里可以看出，项目的主源码在 `src`，测试代码在 `tests`。同时它把 `.vue` 单文件组件纳入类型检查范围，这依赖 Vue CLI 的 TypeScript 插件和 Vue 相关类型处理能力。

`exclude` 只排除了：

```json
"exclude": [
  "node_modules"
]
```

这表示第三方依赖目录不参与项目自身的 TypeScript 编译检查，避免性能问题和外部包类型噪音。

## 上下游关系

上游来看，`tsconfig.json` 被多个工具读取或间接使用。

第一类是 Vue CLI。`package.json` 中定义了：

```json
"serve": "vue-cli-service serve --port 8081",
"build": "vue-cli-service build",
"test:unit": "vue-cli-service test:unit",
"lint": "vue-cli-service lint --mode production"
```

这些命令都会进入 Vue CLI 工具链。由于项目安装了 `@vue/cli-plugin-typescript`，Vue CLI 在开发、构建、检查 TypeScript 时会读取 `tsconfig.json`。

第二类是类型检查插件。同目录的 `fork-ts-checker.config.js` 内容很短：

```js
module.exports = {
  typescript: {
    memoryLimit: 4096,
  },
}
```

这说明项目使用 fork-ts-checker 相关机制做 TypeScript 类型检查，并把 TypeScript 检查进程的内存上限设为 4096 MB。它本身不重写 `tsconfig.json` 的规则，而是调整类型检查运行时资源。根据当前片段推断，实际类型规则仍主要来自 `tsconfig.json`，依据是 `fork-ts-checker.config.js` 只配置了 `memoryLimit`。

第三类是 Jest。`jest.config.js` 使用：

```js
module.exports = {
  preset: '@vue/cli-plugin-unit-jest/presets/typescript-and-babel',
}
```

这个 preset 表明测试会走 Vue CLI 提供的 TypeScript + Babel Jest 预设。因为 `tsconfig.json` 的 `include` 包含 `tests/**/*.ts` 和 `tests/**/*.tsx`，同时 `types` 包含 `jest`，所以测试文件里的 Jest 全局函数能被识别。

第四类是 Webpack/Vue 打包配置。`vue.config.js` 配置了 `publicPath`、i18n 插件选项、开发服务器，以及一条特殊 Webpack 规则，用于处理 `readium` 和 `r2d2bc` 的 `.css.resource` 文件。这里的 Webpack 配置和 `tsconfig.json` 是并行关系：`vue.config.js` 决定打包行为，`tsconfig.json` 决定 TypeScript 类型和模块解析行为。二者共同服务于 `vue-cli-service serve` 和 `vue-cli-service build`。

下游来看，`tsconfig.json` 影响的是整个 `komga-webui/src` 和 `komga-webui/tests` 下的 TypeScript、TSX、Vue 文件。任何使用 `@/` 别名、Jest 全局对象、Webpack 环境 API、Vuetify 类型、DOM API 的代码，都依赖这里的配置才能在类型层面正常工作。

## 运行/调用流程

开发模式下，开发者执行：

```bash
npm run serve
```

实际运行的是：

```bash
vue-cli-service serve --port 8081
```

Vue CLI 启动开发服务器，读取 `vue.config.js` 中的 `devServer` 配置，同时通过 TypeScript 插件读取 `tsconfig.json`。当它处理 `src/**/*.ts`、`src/**/*.tsx`、`src/**/*.vue` 时，会使用这里的 `compilerOptions` 理解模块格式、类型库、路径别名和严格类型规则。

构建模式下，开发者执行：

```bash
npm run build
```

实际运行的是：

```bash
vue-cli-service build
```

此时 Vue CLI 进入生产构建流程。`vue.config.js` 中的 `publicPath` 会根据 `NODE_ENV === 'production'` 变成 `'./'`，而 TypeScript 代码仍然依据 `tsconfig.json` 进行解析和检查。`target: "esnext"`、`module: "esnext"` 让后续打包链路继续处理现代 JS 和模块。

单元测试时，开发者执行：

```bash
npm run test:unit
```

实际运行的是：

```bash
vue-cli-service test:unit
```

Jest 会使用 `@vue/cli-plugin-unit-jest/presets/typescript-and-babel`。测试文件纳入 `tsconfig.json` 的 `include`，并通过 `types: ["jest"]` 获得测试全局变量类型。这样测试里使用 `describe`、`it`、`expect` 时不需要每个文件手动导入类型。

编辑器场景下，例如 VS Code 打开 `komga-webui`，TypeScript language service 会读取 `tsconfig.json`。这会影响自动补全、跳转定义、类型错误提示和路径别名识别。比如源码里写 `@/store` 或 `@/components/xxx` 时，编辑器能够知道 `@` 对应 `src`。

## 小白阅读顺序

建议先读 `komga-webui/package.json`，因为它能告诉你这个前端项目是怎么启动、构建和测试的。重点看 `scripts`、`dependencies`、`devDependencies`。读完会知道这是 Vue 2 + Vue CLI + TypeScript + Vuetify + Jest 项目。

第二步读 `komga-webui/tsconfig.json`。先不要逐项死记，先抓住三条主线：编译目标是什么、类型检查严不严格、源码范围包括哪些文件。也就是重点看 `target`、`module`、`strict`、`paths`、`types`、`include`。

第三步读 `komga-webui/vue.config.js`。它解释了 Vue CLI 打包和开发服务器的特殊配置，例如生产环境 `publicPath`、i18n 插件、开发服务器 WebSocket、特殊 CSS resource 处理规则。这样你能区分：哪些是 TypeScript 规则，哪些是 Webpack/Vue CLI 打包规则。

第四步读 `komga-webui/jest.config.js`。它很短，但能帮助你理解为什么 `tsconfig.json` 里要包含 `tests/**/*.ts`、`tests/**/*.tsx`，以及为什么 `types` 里有 `jest`。

第五步读 `komga-webui/fork-ts-checker.config.js`。它只配置了 TypeScript 检查的内存上限，说明这个项目的类型检查可能比较重，或者为了避免大型 Vue/TypeScript 项目在检查时内存不足。

最后再进入 `komga-webui/src` 具体源码。遇到 `@/xxx` 导入时，回到 `tsconfig.json` 的 `paths` 就能理解它为什么能解析到 `src/xxx`。

## 常见误区

第一个误区是把 `tsconfig.json` 当成最终打包配置。它不是。它主要控制 TypeScript 编译和类型检查。真正的 Vue CLI、Webpack、开发服务器、资源处理配置在 `vue.config.js` 和 Vue CLI 内部配置里。

第二个误区是认为 `target: "esnext"` 就等于项目只能运行在最新浏览器。实际浏览器兼容性通常还受到 Babel、Vue CLI、Browserslist、依赖转译策略影响。`tsconfig.json` 这里只说明 TypeScript 自身输出目标偏现代。

第三个误区是认为 `paths` 会自动影响所有运行环境。`@/* -> src/*` 这个配置主要告诉 TypeScript 和编辑器如何解析别名。运行时、测试时、打包时也需要对应工具链支持。这个项目使用 Vue CLI，通常 Vue CLI 已经内置了 `@` 指向 `src` 的别名，因此两边能配合起来。

第四个误区是忽略 `types` 的限制。`types` 一旦显式声明，TypeScript 会优先只包含这些全局类型包，而不是把所有 `@types/*` 都自动塞进全局环境。这能减少类型污染，但如果新增工具需要全局类型，可能也要同步更新这里。

第五个误区是看到 `strict: true` 就以为所有代码都完全类型安全。严格模式会提高检查强度，但 Vue 2、装饰器、mixin、第三方库声明、`.vue` 文件 shim 等场景仍可能存在类型边界。类型系统能发现很多问题，但不能替代运行时测试。

第六个误区是把 `include` 理解成“项目只存在这些文件”。它只是 TypeScript 类型检查和编译视角下纳入的文件范围。项目中还会有 `.js` 配置文件、样式、静态资源、环境变量文件等，它们不一定出现在 `include` 中，但仍然会影响构建和运行。
