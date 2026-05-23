# 文件：komga-webui/babel.config.js

## 它负责什么

`komga-webui/babel.config.js` 是 Komga 前端工程的 Babel 配置入口。它告诉 Vue CLI：在开发、生产构建、单元测试等需要转译 JavaScript/TypeScript/Vue 单文件组件脚本的场景中，使用 Vue CLI 官方提供的 Babel 预设：

```js
module.exports = {
  presets: [
    '@vue/cli-plugin-babel/preset',
  ],
}
```

这个文件本身不写具体的语法转换规则，而是把转换规则委托给 `@vue/cli-plugin-babel/preset`。该预设会结合 Vue CLI、Babel、`core-js`、`.browserslistrc` 等配置，决定要把源码中的现代 JavaScript 语法转换到什么兼容程度，并在需要时处理 polyfill 相关逻辑。

从仓库上下文看，`komga-webui` 是一个 Vue 2 前端项目：`package.json` 中依赖 `vue`、`vue-router`、`vuex`、`vuetify`，脚本通过 `vue-cli-service` 启动、构建、测试和 lint。因此这个 Babel 配置属于 Vue CLI 工程的基础构建配置，而不是业务代码。

## 关键组成

这个文件只有一个导出：

```js
module.exports = {
  presets: [
    '@vue/cli-plugin-babel/preset',
  ],
}
```

`module.exports` 使用 CommonJS 方式导出配置对象。Babel、Vue CLI、Jest 等 Node.js 工具读取配置文件时，会加载这个对象。

`presets` 是 Babel 的预设列表。预设可以理解为“一组 Babel 插件和默认规则的集合”。这里没有逐个配置 `@babel/plugin-*`，而是只使用一个高级预设。

`@vue/cli-plugin-babel/preset` 是 Vue CLI Babel 插件提供的官方预设。它通常负责：

- 读取项目的目标浏览器范围；
- 根据目标环境决定是否转译现代语法；
- 配合 `core-js` 处理运行时兼容；
- 与 Vue CLI 的 webpack 构建链路集成；
- 让 `.vue`、`.js`、`.ts` 中需要 Babel 处理的代码走统一规则。

项目中 `package.json` 明确声明了相关依赖：

- `@vue/cli-plugin-babel`
- `@vue/cli-service`
- `babel-jest`
- `core-js`
- `typescript`
- `@vue/cli-plugin-typescript`
- `@vue/cli-plugin-unit-jest`

这说明 Babel 配置不仅和浏览器构建有关，也和测试环境中的代码转译有关。

## 上下游关系

上游主要是前端源码和构建命令。

源码位于 `komga-webui/src`，包括：

- `komga-webui/src/App.vue`
- `komga-webui/src/components/*.vue`
- `komga-webui/src/functions/*.ts`
- `komga-webui/src/i18n.ts`
- `komga-webui/src/locales/*.json`

这些源码中可能包含 Vue 单文件组件、TypeScript、现代 JavaScript 语法、依赖导入等内容。Babel 不直接负责 Vue 模板编译，也不直接做 TypeScript 类型检查，但它会参与脚本代码的语法转换流程。

构建入口来自 `komga-webui/package.json`：

```json
"scripts": {
  "serve": "vue-cli-service serve --port 8081",
  "build": "vue-cli-service build",
  "test:unit": "vue-cli-service test:unit",
  "lint": "vue-cli-service lint --mode production"
}
```

其中和 `babel.config.js` 关系最直接的是：

- `npm run serve`：开发服务器构建前端代码；
- `npm run build`：生产环境打包；
- `npm run test:unit`：单元测试时通过 Jest/Vue CLI 转译代码。

测试配置在 `komga-webui/jest.config.js` 中：

```js
module.exports = {
  preset: '@vue/cli-plugin-unit-jest/presets/typescript-and-babel',
}
```

这里的 `typescript-and-babel` 明确表示单元测试会同时使用 TypeScript 和 Babel 链路。根据当前片段推断，`babel.config.js` 会被 Jest 相关预设间接读取，用于测试环境里的 Babel 转换。

下游主要是构建产物和测试运行环境：

- 开发环境中，Babel 转换后的代码进入 webpack dev server；
- 生产构建中，Babel 转换后的代码进入最终打包产物；
- 单元测试中，Babel 转换后的代码交给 Jest 执行；
- 浏览器兼容性由 Babel 预设结合 `.browserslistrc` 决定。

同目录的 `.browserslistrc` 内容是：

```text
> 0.5%
ios >= 12
last 2 versions
not dead
```

这表示项目希望支持使用率超过 0.5%、iOS 12 及以上、各浏览器最近两个版本、且仍被维护的浏览器。Babel 预设会根据这些目标判断哪些语法需要转换，哪些可以保留。

`komga-webui/vue.config.js` 则负责 Vue CLI/webpack 层面的配置，例如：

- `publicPath`
- i18n 插件选项
- dev server 配置
- 对 `readium`、`r2d2bc` 的特殊 CSS 资源规则

它和 `babel.config.js` 是并列关系：`vue.config.js` 管 webpack/Vue CLI 构建行为，`babel.config.js` 管 Babel 语法转译规则。两者都会被 `vue-cli-service` 在构建时读取，但职责不同。

## 运行/调用流程

开发启动时，大致流程是：

1. 在 `komga-webui` 下执行 `npm run serve`。
2. `package.json` 中的脚本调用 `vue-cli-service serve --port 8081`。
3. Vue CLI 读取工程配置，包括 `vue.config.js`、`babel.config.js`、`.browserslistrc` 等。
4. webpack 处理 `src` 下的 Vue、TypeScript、JavaScript 源码。
5. 需要 Babel 转译的脚本代码交给 `@vue/cli-plugin-babel/preset`。
6. Babel 根据 Vue CLI 预设和浏览器目标输出兼容后的代码。
7. 开发服务器把结果提供给浏览器访问。

生产构建时，大致流程是：

1. 执行 `npm run build`。
2. `vue-cli-service build` 读取同一套配置。
3. Babel 处理源码语法兼容。
4. webpack 继续做打包、代码分割、资源处理、压缩等工作。
5. 输出可部署的前端静态资源。

单元测试时，大致流程是：

1. 执行 `npm run test:unit`。
2. `vue-cli-service test:unit` 启动 Jest。
3. `jest.config.js` 使用 `@vue/cli-plugin-unit-jest/presets/typescript-and-babel`。
4. TypeScript 和 Babel 共同参与测试文件、源码文件的转换。
5. Jest 执行转换后的测试代码。

这个文件没有显式调用方，因为 Babel 配置通常不是被业务代码 `import` 的，而是被工具链按约定文件名自动发现。也就是说，`komga-webui/babel.config.js` 的“调用方”不是某个源码函数，而是 `vue-cli-service`、Babel、Jest 这类构建/测试工具。

## 小白阅读顺序

建议按下面顺序理解这个文件：

1. 先看 `komga-webui/package.json`

   重点看 `scripts` 和 `devDependencies`。你会知道这个前端项目通过 `vue-cli-service` 运行，并且安装了 `@vue/cli-plugin-babel`、`@vue/cli-plugin-typescript`、`@vue/cli-plugin-unit-jest`。

2. 再看 `komga-webui/babel.config.js`

   这个文件虽然短，但它回答了一个核心问题：项目的 Babel 转译规则从哪里来？答案是 `@vue/cli-plugin-babel/preset`。

3. 再看 `komga-webui/.browserslistrc`

   Babel 是否需要转换某些语法，取决于目标浏览器。这里的 `ios >= 12`、`last 2 versions` 等规则会影响最终转译策略。

4. 再看 `komga-webui/jest.config.js`

   它说明测试环境使用 `typescript-and-babel` 预设，因此 Babel 配置也会影响单元测试中的代码转换。

5. 最后看 `komga-webui/vue.config.js`

   它不是 Babel 配置，但它和 `babel.config.js` 一起组成 Vue CLI 项目的构建配置层。理解两者分工后，就能避免把 webpack 配置、Vue 插件配置、Babel 语法转换混为一谈。

6. 如果继续深入，再看 `komga-webui/src`

   `src` 下的 `.vue`、`.ts`、`.js` 文件就是被这套构建链路处理的主要输入。比如 `src/components` 是 Vue 组件，`src/functions` 是 TypeScript 工具函数，`src/i18n.ts` 和 `src/locales` 与国际化有关。

## 常见误区

误区一：认为 `babel.config.js` 会直接打包文件。

Babel 只负责语法转换，不负责完整打包。真正组织依赖、处理资源、输出 bundle 的是 Vue CLI 背后的 webpack。`babel.config.js` 是构建链路中的一环，不是完整构建器。

误区二：认为这个文件没有写具体规则，所以没有作用。

虽然文件只有一个 preset，但这个 preset 很重要。`@vue/cli-plugin-babel/preset` 代表 Vue CLI 官方默认 Babel 方案，会结合项目依赖、`core-js`、浏览器目标等做很多隐式工作。

误区三：把 `babel.config.js` 和 `vue.config.js` 混为一谈。

`babel.config.js` 关注 JavaScript 语法转换；`vue.config.js` 关注 Vue CLI 和 webpack 行为，例如 public path、dev server、资源规则、插件选项。它们都服务构建，但层级不同。

误区四：认为 Babel 会做 TypeScript 类型检查。

Babel 可以参与 TypeScript 代码的转换，但类型检查不是 Babel 的主要职责。项目中还有 `typescript`、`@vue/cli-plugin-typescript`、`fork-ts-checker.config.js` 等相关配置，说明类型检查和语法转换是分开的。

误区五：认为所有浏览器都会拿到完全相同的“旧语法”代码。

实际转换程度取决于 `.browserslistrc`。这个项目指定了 `> 0.5%`、`ios >= 12`、`last 2 versions`、`not dead`，所以 Babel 会围绕这些目标环境决定转换范围，而不是无条件把所有语法都降到很老的标准。

误区六：认为业务代码会手动导入这个文件。

业务组件不会写 `import './babel.config.js'`。这个文件由 Babel/Vue CLI/Jest 按配置约定读取。它属于工具链配置，不属于运行时业务模块。

误区七：随意删除 `core-js` 或 `@vue/cli-plugin-babel`。

`package.json` 中同时存在 `core-js` 和 `@vue/cli-plugin-babel`。在 Vue CLI Babel 预设下，它们通常参与兼容性处理。随意删除可能导致构建失败，或者在某些目标浏览器中出现运行时兼容问题。
