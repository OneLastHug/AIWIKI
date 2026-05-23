# 文件：komga-webui/jest.config.js

## 它负责什么

`komga-webui/jest.config.js` 是 `komga-webui` 前端项目的 Jest 单元测试配置入口。

这个文件本身没有定义复杂规则，只导出一个 Jest 配置对象：

```js
module.exports = {
  preset: '@vue/cli-plugin-unit-jest/presets/typescript-and-babel',
}
```

它的职责是告诉 Jest：当前项目的测试环境不要手写一整套 `transform`、`moduleNameMapper`、`.vue` 文件处理、TypeScript 编译规则，而是直接使用 Vue CLI 官方 Jest 插件提供的 `typescript-and-babel` 预设。

从仓库上下文看，`komga-webui` 是一个 Vue 2 + TypeScript 前端项目，依赖中包含 `vue`、`vue-router`、`vuex`、`vuetify`，测试相关依赖包括 `jest`、`@vue/cli-plugin-unit-jest`、`@vue/test-utils`、`@vue/vue2-jest`、`babel-jest`、`ts-jest`、`@types/jest`。因此这个配置文件主要服务于 TypeScript、Babel、Vue 单文件组件共同存在的测试场景。

## 关键组成

这个文件只有一个关键字段：`preset`。

`preset: '@vue/cli-plugin-unit-jest/presets/typescript-and-babel'`

它表示继承 `@vue/cli-plugin-unit-jest` 包里内置的 Jest 预设。这个预设名称中的 `typescript-and-babel` 很重要，说明测试编译链路同时考虑两类处理：

一是 TypeScript。项目源码和测试文件会包含 `.ts`，例如 `tests/unit/functions/book-spreads.spec.ts`、`tests/unit/functions/toc.spec.ts`、`tests/unit/types/pageLoader.spec.ts`。`tsconfig.json` 也明确把 `tests/**/*.ts`、`tests/**/*.tsx` 加入编译范围，并在 `types` 中包含 `jest`。

二是 Babel。`komga-webui/babel.config.js` 使用：

```js
module.exports = {
  presets: [
    '@vue/cli-plugin-babel/preset',
  ],
}
```

这说明测试过程中如果需要转换现代 JavaScript 语法，会继续沿用 Vue CLI 的 Babel 预设。

`module.exports` 是 CommonJS 导出形式。Jest 配置文件通常运行在 Node.js 环境里，因此这里没有使用 `export default`，而是使用 `module.exports` 暴露配置对象。

这个文件没有显式配置以下内容：

- 没有自定义 `testMatch` 或 `testRegex`，测试文件发现规则交给 Vue CLI / Jest 预设处理。
- 没有自定义 `transform`，`.ts`、`.js`、`.vue` 的转换规则交给预设处理。
- 没有自定义 `moduleNameMapper`，例如 `@/` 到 `src/` 的别名解析主要依赖 Vue CLI 预设和项目配置协同。
- 没有配置 `setupFiles` 或 `setupFilesAfterEnv`，说明当前片段里没有看到全局测试初始化文件。
- 没有配置覆盖率规则，覆盖率收集策略应由命令行或默认配置决定。

## 上下游关系

上游入口主要是 `komga-webui/package.json` 里的测试脚本：

```json
"test:unit": "vue-cli-service test:unit"
```

开发者执行 `npm run test:unit` 时，会调用 Vue CLI 的 `vue-cli-service test:unit`。这个命令来自 `@vue/cli-plugin-unit-jest`，它会启动 Jest，并读取项目里的 `jest.config.js` 作为 Jest 配置入口。

`jest.config.js` 再把实际配置委托给 `@vue/cli-plugin-unit-jest/presets/typescript-and-babel`。这个预设会和项目中的其他配置共同工作：

- `komga-webui/package.json` 提供 Jest、Vue Test Utils、TypeScript、Babel、Vue Jest 等依赖。
- `komga-webui/babel.config.js` 提供 Babel 预设，测试时处理现代 JS 语法。
- `komga-webui/tsconfig.json` 提供 TypeScript 编译上下文，包括 `strict: true`、`types: ["webpack-env", "jest", "vuetify", "webpack"]`、`paths` 中的 `@/* -> src/*`。
- `komga-webui/tests` 下的 `.spec.ts` 文件是下游被执行的测试用例。

测试目录当前包含：

- `komga-webui/tests/unit/functions/book-spreads.spec.ts`
- `komga-webui/tests/unit/functions/toc.spec.ts`
- `komga-webui/tests/unit/types/pageLoader.spec.ts`

根据当前片段推断，这些测试主要覆盖 `src` 中的工具函数和类型相关逻辑，而不是完整页面端到端行为。依据是测试文件位于 `tests/unit/functions` 和 `tests/unit/types`，且项目测试脚本是 `test:unit`。

## 运行/调用流程

典型调用流程如下：

1. 开发者在 `komga-webui` 目录执行：

```bash
npm run test:unit
```

2. `package.json` 中的脚本把命令转给：

```bash
vue-cli-service test:unit
```

3. Vue CLI 的单元测试插件启动 Jest。

4. Jest 读取 `komga-webui/jest.config.js`。

5. `jest.config.js` 返回配置对象，指定使用：

```js
@vue/cli-plugin-unit-jest/presets/typescript-and-babel
```

6. Jest 按照该预设处理测试文件。对于当前项目，这意味着它需要能理解：

- `.spec.ts` 测试文件；
- TypeScript 类型语法；
- Babel 转换后的 JavaScript；
- Vue CLI 项目的模块解析规则；
- 可能出现的 Vue 2 组件测试环境。

7. Jest 扫描并运行 `tests/unit` 下的测试文件，例如 `book-spreads.spec.ts`、`toc.spec.ts`、`pageLoader.spec.ts`。

8. 测试文件 import 被测源码，执行断言，输出测试结果。

这里要注意，`jest.config.js` 不是直接运行测试逻辑的地方。它只决定 Jest 如何理解这个项目。真正的测试行为写在 `tests/unit/**/*.spec.ts` 中，被测实现则通常位于 `src` 目录。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先看 `komga-webui/package.json`

   重点看 `scripts.test:unit` 和 `devDependencies`。这里能知道测试命令是 `vue-cli-service test:unit`，也能看到项目使用 Jest、Vue Test Utils、TypeScript、Babel 和 Vue 2 Jest 转换器。

2. 再看 `komga-webui/jest.config.js`

   这个文件很短，只需要理解一个概念：它没有自己写规则，而是继承 Vue CLI 的 Jest 预设。

3. 接着看 `komga-webui/tsconfig.json`

   重点看 `types`、`paths`、`include`。其中 `types` 包含 `jest`，所以测试文件里可以直接使用 Jest 的类型；`include` 包含 `tests/**/*.ts`，说明测试 TypeScript 文件也被纳入项目类型上下文；`paths` 定义了 `@/*` 指向 `src/*`。

4. 再看 `komga-webui/babel.config.js`

   这里能看到 Babel 使用 `@vue/cli-plugin-babel/preset`。Jest 预设名里包含 `babel`，所以理解 Babel 配置有助于理解测试时 JS 语法是如何被转换的。

5. 最后看 `komga-webui/tests/unit` 下的测试文件

   当前测试文件集中在 `functions` 和 `types` 两类目录。阅读这些测试可以反推项目里哪些工具函数、类型逻辑有单元测试保护。

## 常见误区

第一个误区是把 `jest.config.js` 当成测试代码。它不是测试用例，也不会定义业务断言。它只是 Jest 的配置入口，真正的测试代码在 `komga-webui/tests/unit/**/*.spec.ts`。

第二个误区是认为这个项目没有配置 TypeScript 测试。虽然 `jest.config.js` 里没有手写 `ts-jest` 配置，但 `preset` 已经选择了 `typescript-and-babel`，再结合 `package.json` 中的 `ts-jest`、`typescript`、`@types/jest` 和 `tsconfig.json` 中的 `tests/**/*.ts`，可以看出 TypeScript 测试是被支持的。

第三个误区是看到配置很短就以为 Jest 使用原生默认配置。实际不是。短是因为它把规则交给了 `@vue/cli-plugin-unit-jest` 的内置预设。Vue CLI 预设背后会处理 Vue 项目常见的转换、解析和测试环境问题。

第四个误区是随意改成自定义 `transform`。对于 Vue CLI 项目，手动覆盖 `transform` 容易破坏 `.vue`、`.ts`、Babel 三者之间的配合。除非明确遇到预设无法覆盖的特殊场景，否则保持继承官方预设更稳妥。

第五个误区是忽略 `babel.config.js`。Jest 配置虽然只写了一个 `preset`，但 `typescript-and-babel` 说明 Babel 仍然在测试编译链路中有作用。项目的 Babel 行为并不写在 `jest.config.js`，而是在 `komga-webui/babel.config.js` 中。

第六个误区是把 `tsconfig.json` 的 `paths` 当成 Jest 本文件里必须重复配置的内容。当前项目借助 Vue CLI Jest 预设工作，别名解析可能由 Vue CLI 体系协同处理。只有当测试中出现 `@/xxx` 无法解析时，才需要进一步检查是否要在 Jest 层补充 `moduleNameMapper`。根据当前片段不能断定存在该问题。
