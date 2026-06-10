# 文件：tsconfig.json

## 一句话定位

`tsconfig.json` 是 AionUi 仓库根级 TypeScript 工程配置，负责给桌面端主进程、渲染进程、构建配置、测试配置等 TypeScript 文件提供统一的类型检查、模块解析、路径别名和 JSX 编译语义；它本身不产物代码，而是作为编译器、编辑器和工具链共同读取的“类型系统入口”。

## 它暴露/定义了什么

这个文件主要定义了 `compilerOptions`、`include` 和 `exclude` 三类内容。

`compilerOptions` 暴露的是全仓库 TypeScript 语义：`target: "ES6"` 决定输出语法基线，`lib: ["ES2023", "DOM", "DOM.Iterable"]` 同时允许较新的 ECMAScript API 与浏览器 DOM 类型，适合 Electron 项目中 renderer 代码和部分共享代码的类型推断。`module: "esnext"` 与 `moduleResolution: "bundler"` 表明模块解析交给现代 bundler 生态处理，和 `electron-vite`、Vite 风格更一致。`noEmit: true` 是关键：根配置只做类型检查，不负责生成 JS 或声明文件。`allowJs: true` 让 JS 文件可以进入 TypeScript 项目语义；`noImplicitAny: true` 提升类型严格度，但并不是完整 `strict: true`。

它还定义了项目最重要的路径别名：`@/*` 指向 `packages/desktop/src/*`，`@process/*` 指向主进程目录，`@renderer/*` 指向渲染进程目录，`@worker/*` 指向主进程 worker 子目录。这些别名是业务代码 import 的稳定入口，避免大量相对路径穿透。

`include` 将类型检查范围限定在 `packages/desktop/src/**/*`、`uno.config.ts`、`packages/desktop/electron.vite.config.ts`、`playwright.config.ts` 和 renderer 的 `types.d.ts`。`exclude` 特意排除了 `BunSqliteDriver.ts` 和它的 Bun 测试文件，说明这部分代码可能依赖 Bun 专属运行时或类型环境，不适合由根 TypeScript 配置统一检查；这是根据当前片段推断，依据是排除路径位于数据库 driver 且文件名包含 `Bun`。

## 谁调用它

直接调用者主要是 TypeScript 相关工具链。根据 `package.json` 和项目指南可见，`bunx tsc --noEmit` 会读取根 `tsconfig.json` 做全局类型检查；编辑器的 TypeScript language server 也会读取它，为跳转、补全、诊断和路径别名解析服务。

构建和运行脚本虽然多通过 `electron-vite dev --config packages/desktop/electron.vite.config.ts`、`electron-vite build --config packages/desktop/electron.vite.config.ts` 执行，但这些工具在处理 TypeScript、路径别名、配置文件类型时通常会参考根级 TypeScript 配置或与其保持一致。测试侧的 `vitest run`、`playwright test --config playwright.config.ts` 涉及 TypeScript 配置文件和源码导入，也间接受它约束。根据当前片段推断，`oxlint`、`oxfmt` 不以它作为主要规则来源，但会与它定义的源码范围、别名习惯共同构成开发体验。

## 它调用谁

`tsconfig.json` 不像运行时代码那样“调用函数”。它被 TypeScript 编译器消费，并声明编译器应当如何调用底层解析逻辑：读取 `packages/desktop/src` 下源码，加载 `uno.config.ts`、`packages/desktop/electron.vite.config.ts`、`playwright.config.ts`，解析 React JSX，读取 JSON 模块，按 `paths` 映射解析 `@/`、`@process/`、`@renderer/`、`@worker/` import。

从依赖关系看，它“指向”的外部能力包括 TypeScript 标准库 `ES2023`、浏览器类型库 `DOM` / `DOM.Iterable`、项目源码目录，以及 bundler 模式模块解析器。`skipLibCheck: true` 还意味着它不会深入检查第三方 `.d.ts` 的内部一致性，从而减少依赖包类型噪声和类型检查成本。

## 核心流程

开发者运行类型检查、启动开发环境、执行测试或打开编辑器时，工具首先定位根 `tsconfig.json`。随后 TypeScript 根据 `include` 建立项目文件集合，并排除 `exclude` 中 Bun SQLite driver 相关文件。进入语义分析后，编译器按 `compilerOptions` 解析语法、模块和类型：源码中的 JSX 被视为 React JSX；JSON import 可被类型系统接受；JS 文件也允许参与检查；`@renderer/foo` 这类路径会被改写到 `packages/desktop/src/renderer/foo` 方向解析。

当代码只需要类型验证时，`noEmit: true` 阻止 TypeScript 输出文件，构建产物交给 `electron-vite` 和后续 builder 脚本处理。也就是说，这份配置在流程中处于“校验与解析中枢”的位置，而不是“打包产物生成器”。

## 关键函数的高层作用

这个文件没有函数、类或运行时逻辑，因此不存在传统意义上的核心函数。学习时应把关键字段当作“配置级函数”理解：`compilerOptions` 决定类型系统行为，`paths` 决定跨目录 import 如何落点，`include` 决定哪些源码进入工程图谱，`exclude` 决定哪些特殊运行时文件被根检查跳过。辅助字段如 `sourceMap`、`outDir` 在 `noEmit: true` 的根配置下更多是兼容性或工具读取用途，不是当前文件的主行为中心。

## 修改风险

最高风险是改 `paths`。别名一旦变动，`packages/desktop/src` 内大量 `@/`、`@process/`、`@renderer/` 导入可能立刻失效，且会影响编辑器、测试、构建三条链路。其次是改 `moduleResolution` 或 `module`，它会改变 ESM、包导出、扩展名和 bundler 风格解析规则，可能造成本地类型检查通过但构建失败，或相反。

改 `lib` 也要谨慎。移除 `DOM` 会让 renderer 代码的浏览器 API 类型丢失；过度增加 Node/Bun 运行时类型则可能掩盖主进程与渲染进程 API 边界问题。改 `include` 会影响哪些文件被 `tsc --noEmit` 覆盖，范围过窄会漏检，范围过宽可能把脚本、测试或平台专属文件纳入错误环境。特别是 `exclude` 中的 Bun SQLite driver，如果直接移除排除项，可能暴露 Bun 专属 API 在普通 TypeScript 环境下的类型错误；要先确认对应类型依赖和运行时边界。

`allowJs`、`noImplicitAny`、`skipLibCheck` 也会改变项目的质量门槛。收紧它们可能引发大量历史问题，放松它们则降低类型检查价值。修改后至少应运行 `bunx tsc --noEmit`，若涉及 renderer、配置文件或测试入口，还应结合 `bun run test`、`bun run test:e2e` 或相关构建命令验证工具链没有分叉。
