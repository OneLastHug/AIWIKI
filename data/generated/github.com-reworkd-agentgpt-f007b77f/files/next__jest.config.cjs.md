# 文件：next/jest.config.cjs

## 一句话定位

`next/jest.config.cjs` 是 `next` 前端应用的 Jest 测试入口配置文件，负责把普通 Jest 运行时接入 Next.js 项目的编译、环境变量和模块解析规则，让 `npm test` 能直接测试 TypeScript、React、Next 相关代码。

## 它暴露/定义了什么

这个文件最终通过 `module.exports` 暴露一个由 `next/jest` 包装后的 Jest 配置。它不是导出一个纯对象，而是导出 `createJestConfig(customJestConfig)` 的结果。这样做的核心原因是 Next.js 的配置加载可能是异步的，Jest 在读取配置时需要让 `next/jest` 先完成 Next 项目上下文初始化。

文件内部主要定义两层内容：

`createJestConfig`：由 `nextJest({ dir: "./" })` 创建，表示测试配置应以当前 `next` 应用目录为根，加载该目录下的 Next 配置与环境变量。

`customJestConfig`：项目自定义 Jest 配置，目前包含 `moduleDirectories` 和 `testEnvironment`。其中 `moduleDirectories: ["node_modules", "<rootDir>/"]` 允许测试代码除正常依赖外，也从项目根目录解析模块；`testEnvironment: "jest-environment-jsdom"` 则让测试运行在模拟浏览器 DOM 的环境里。

## 谁调用它

直接调用者是 Jest CLI。`next/package.json` 中的脚本为 `test: cross-env SKIP_ENV_VALIDATION=1 jest`，开发者执行 `npm test` 或等价命令时，Jest 会按默认规则查找并加载 `jest.config.cjs`。因此这个文件属于测试工具链入口，而不是业务代码运行时入口。

间接调用链可以理解为：开发者或 CI 执行 `npm test`，`cross-env` 设置 `SKIP_ENV_VALIDATION=1`，随后启动 `jest`，Jest 发现并读取 `next/jest.config.cjs`，再由该配置委托 `next/jest` 生成最终测试配置。

## 它调用谁

它主要调用三个外部能力：

`require("next/jest")`：引入 Next 官方提供的 Jest 配置适配器。该适配器通常负责处理 Next 项目中常见的 Babel/SWC 转换、CSS/静态资源 mock、环境变量和 Next 配置加载等问题。

`nextJest({ dir: "./" })`：创建一个配置工厂，告诉 `next/jest` 以当前目录作为 Next app 根目录。根据当前片段推断，这里的当前目录应是 `next` 包目录，因为 `package.json`、`tsconfig.json` 和测试目录都位于 `next` 下。

`createJestConfig(customJestConfig)`：把项目自定义配置合并进 Next 生成的默认 Jest 配置，并导出给 Jest 使用。

## 核心流程

测试启动后，Jest 先加载 `next/jest.config.cjs`。文件第一步引入 `next/jest`，第二步用 `dir: "./"` 创建 Next-aware 的 Jest 配置生成器。这个阶段本身不运行测试，也不扫描用例，而是准备一套“如何运行测试”的规则。

接着文件定义 `customJestConfig`。这里没有复杂的测试匹配规则、覆盖率规则或 mock 映射，只设置了模块目录和运行环境。`moduleDirectories` 影响 `import` / `require` 的解析路径；`testEnvironment` 影响测试代码是否能访问 `window`、`document` 等浏览器对象。当前仓库已有 `next/__mocks__/matchMedia.mock.ts` 直接向 `window` 注入 `matchMedia`，这说明至少部分测试假设存在浏览器式全局对象，`jsdom` 是必要背景。

最后，`module.exports = createJestConfig(customJestConfig)` 把控制权交给 `next/jest`。最终配置不是简单地等于 `customJestConfig`，而是 Next 默认测试配置与本项目补充项的组合。

## 关键函数的高层作用

`nextJest` 是最关键的函数。它把 Jest 与 Next.js 项目模型连接起来，避免手写大量 transform、环境加载和资源处理规则。对于 Next 13 项目，如果绕开它直接写 Jest 配置，容易出现 TypeScript/JSX 转换失败、Next 特有导入无法解析、环境变量加载顺序不一致等问题。

`createJestConfig` 是由 `nextJest` 返回的工厂函数。它的职责是接收项目自定义 Jest 配置，并在 Next 配置加载完成后生成 Jest 真正使用的最终配置。文件注释也明确指出，这种导出方式是为了确保 `next/jest` 能加载异步的 Next.js config。

`customJestConfig` 不是函数，但它是项目层面的扩展点。后续如果要加 `setupFilesAfterEnv`、`moduleNameMapper`、`testMatch`、`collectCoverageFrom`，通常会加在这里，而不是替换掉 `next/jest` 的包装流程。

## 修改风险

最大的风险是破坏 `next/jest` 的包装。若把 `module.exports` 改成直接导出 `customJestConfig`，测试可能仍能启动，但 Next.js 相关转换、配置加载和资源处理会丢失，React/Next 组件测试很容易出现编译或模块解析问题。

`dir: "./"` 对工作目录敏感。如果测试命令从 `next` 目录执行，这个配置是合理的；如果未来 monorepo 根目录统一运行 Jest，需要重新确认 `rootDir` 与 `dir` 的关系。根据当前片段推断，`next/package.json` 的 `test` 脚本位于 `next` 包内，因此当前写法匹配该包内运行方式。

修改 `testEnvironment` 风险也较高。把 `jest-environment-jsdom` 改成 `node` 会让依赖 `window`、`document`、`matchMedia` 的测试失败，例如现有 mock 文件就是围绕 `window.matchMedia` 编写的。除非测试范围明确转向纯服务端逻辑，否则不应轻易切换。

`moduleDirectories` 会影响模块解析优先级。加入 `"<rootDir>/"` 可以简化根路径导入，但也可能让本地文件名与第三方包名冲突时产生非预期解析。若未来引入 `tsconfig.json` 的 `paths`，更稳妥的方式通常是在 Jest 中显式配置 `moduleNameMapper`，而不是继续扩大隐式搜索路径。

当前文件没有启用 `setupFilesAfterEnv`。如果后续使用 `@testing-library/jest-dom` 的自定义 matcher，或希望全局注册 `matchMedia` mock，需要在这里接入 setup 文件。但新增 setup 会影响所有测试用例，应避免放入有副作用的业务初始化、网络请求或真实环境变量校验逻辑。
