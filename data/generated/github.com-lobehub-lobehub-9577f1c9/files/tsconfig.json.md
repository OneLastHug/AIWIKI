# 文件：tsconfig.json

## 一句话定位

`tsconfig.json` 是仓库根级 TypeScript 编译配置，负责统一主应用、共享包、测试代码和脚本的类型检查边界、模块解析规则、路径别名以及 Next.js/React 的 TypeScript 语义，是 `src` 与大部分 `packages` 能被同一套工具链理解的基础配置。

## 它暴露/定义了什么

这个文件主要定义 `compilerOptions`、`include`、`exclude` 和 `references` 四类能力。`compilerOptions` 指定项目以 `ESNext` 为目标，启用 `strict`、`isolatedModules`、`noEmit`，说明它更偏向类型检查与编辑器语义，而不是直接产物输出。`moduleResolution: "bundler"` 配合 `module: "esnext"`，表明源码最终由 Next.js、Vite、tsx、tsgo/tsc 等工具处理模块打包或执行。

它还定义了关键路径别名：`@/*` 指向 `src/*`，`@/database/*`、`@/const/*`、`@/utils/*`、`@/types/*` 优先指向对应 `packages/*/src/*`，再回退到 `src/*`。这体现了仓库的分层：共享基础能力逐步沉到 `packages`，应用层仍保留兼容入口。`~test-utils` 指向 `tests/utils.tsx`，服务于测试代码复用。

`include` 覆盖 `src`、`packages`、`tests`、`scripts`、根目录 TypeScript 文件、`next-env.d.ts` 以及 `.next/types` / `.next/dev/types`。`exclude` 排除 `node_modules`、桌面/设备/移动 app、临时目录、`e2e` 和 `knip.ts`，避免根类型检查把独立工程或成本较高的边界纳入同一上下文。

## 谁调用它

直接或间接消费它的主要是 TypeScript 生态工具链。`package.json` 中的 `type-check` 使用 `tsgo --noEmit`，`type-check:tsc` 使用 `tsc --noEmit`，它们会读取根 `tsconfig.json` 执行类型检查。Next.js 构建与开发命令，如 `next build`、`next dev`，也会读取根配置，并通过 `plugins: [{ name: "next" }]` 获得 Next 相关类型体验。Vite SPA 构建、Vitest、ESLint、tsx 脚本执行等通常也会基于这份配置或其路径别名约定解析源码；根据当前片段推断，依据是 `package.json` 中存在 `vite build`、`vitest run`、`tsx scripts/...`、`eslint src/ tests/` 等脚本，且根配置覆盖了这些源码范围。

## 它调用谁

配置文件本身不“调用”运行时代码，但它声明了编译器需要理解的外部环境和插件。`lib` 引入 `dom`、`dom.iterable`、`dom.asynciterable`、`esnext`、`webworker`，让浏览器、Web Worker 与现代 ECMAScript API 在类型层可见。`types: ["vitest/globals"]` 把 Vitest 全局测试 API 注入类型环境。`plugins` 引入 Next TypeScript 插件。`references` 指向 `./apps/desktop`，说明根工程与桌面子工程存在 TypeScript project reference 关系，但桌面自身仍由 `apps/desktop/tsconfig.json` 管理。

## 核心流程

开发或 CI 触发类型检查时，工具先读取根 `tsconfig.json`，建立编译上下文。随后根据 `include` 收集 `src`、`packages`、`tests`、`scripts` 等文件，并根据 `exclude` 跳过独立 app、e2e 和临时目录。解析 import 时，编译器先应用 `paths`：例如 `@/utils/foo` 会优先落到 `packages/utils/src/foo`，再尝试 `src/utils/foo`；普通 `@/features/...` 则进入 `src/features/...`。解析完成后，`strict`、`isolatedModules`、`forceConsistentCasingInFileNames` 等规则约束类型安全、单文件转译兼容性和跨平台大小写一致性。由于 `noEmit: true`，根配置不会生成 JS 输出，真正产物由 Next.js、Vite 或各 package/app 自己的构建链完成。

## 关键函数的高层作用

`tsconfig.json` 没有函数或类。这里的“核心单元”是配置项：`compilerOptions` 决定语言能力和类型约束；`paths` 决定仓库内模块边界和别名解析；`include/exclude` 决定根工程类型检查的覆盖范围；`references` 用于把独立 TypeScript 子工程纳入项目引用关系。辅助项如 `$schema` 只服务编辑器校验和补全，不影响运行逻辑。

## 修改风险

最高风险来自 `paths`。调整 `@/*` 或 `@/database/*` 等映射，可能导致同名模块解析到不同实现，出现构建通过但运行路径变化、测试 mock 失效、IDE 跳转与实际打包不一致等问题。尤其是当前多个别名存在 `packages` 优先、`src` 回退的顺序，改变顺序会影响共享包迁移期间的兼容策略。

第二类风险是 `include/exclude`。把 `apps/desktop/**`、`e2e/**` 或更多独立工程纳入根检查，可能显著增加类型检查成本，并暴露这些子工程与根工程不同的 TS 假设；反过来缩小 `include`，可能让脚本、测试或 package 源码脱离类型保护。

第三类风险是编译器语义。关闭 `strict`、修改 `moduleResolution`、取消 `isolatedModules`，都会影响 Next.js/Vite/tsx 对源码的理解。`moduleResolution: "bundler"` 适配现代打包器，改回传统解析可能引发 package exports、条件导出、JSON 模块或别名解析问题。

最后是测试环境污染风险。`types: ["vitest/globals"]` 让全仓类型环境都能看到 Vitest 全局变量，方便测试，但也可能掩盖非测试代码误用测试 API 的问题。若移除它，测试文件可能需要显式导入 `describe`、`it`、`expect`；若继续保留，应依赖 lint 或代码审查防止生产代码误用。
