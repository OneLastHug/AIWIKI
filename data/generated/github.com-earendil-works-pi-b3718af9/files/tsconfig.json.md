# 文件：tsconfig.json

## 一句话定位

`tsconfig.json` 是仓库根级 TypeScript 类型检查入口，负责把 monorepo 内多个 `packages/*` 的源码、测试和 `coding-agent` 示例纳入同一个类型检查项目，并用 `paths` 把工作区包名映射到本地源码，而不是依赖已构建的 `dist` 产物。

## 它暴露/定义了什么

这个文件定义的是 TypeScript 编译器配置，不暴露运行时代码。它继承 `tsconfig.base.json`，并在根项目层补充三类关键规则：

第一，`compilerOptions.noEmit: true` 表示根级检查只做类型分析，不生成 JavaScript、声明文件或 sourcemap。实际构建应由各 package 自己的构建脚本负责。

第二，`compilerOptions.paths` 定义包名到源码文件的别名解析。例如 `@earendil-works/pi-ai` 指向 `packages/ai/src/index.ts`，`@earendil-works/pi-coding-agent/hooks` 指向 `packages/coding-agent/src/core/hooks/index.ts`，通配形式如 `@earendil-works/pi-tui/*` 指向对应 package 的 `src/*`。这让仓库内部代码可以用发布包名互相引用，同时在开发和检查时直接落到本地源码。

第三，`include` 覆盖 `packages/*/src/**/*`、`packages/*/test/**/*`、`packages/coding-agent/examples/**/*`，说明根检查关注源码、测试和 coding-agent 示例。`exclude` 排除所有 `dist`，并额外排除 `packages/coding-agent/examples/extensions/gondolin/**`，避免把该扩展目录纳入根类型检查。

## 谁调用它

最直接的调用者是根 `package.json` 的 `check` 脚本：`npm run check` 中包含 `tsgo --noEmit`。未显式传入 `--project` 时，根据当前片段推断，`tsgo` 会从仓库根读取默认的 `tsconfig.json`，依据是脚本在根目录定义，且该文件就是根 TypeScript 项目配置。

除此之外，编辑器的 TypeScript language service、`tsserver`、部分 IDE 类型跳转和诊断功能也通常会读取根 `tsconfig.json`。根据当前片段推断，CI 或发布流程也会间接使用它，因为 `package.json` 的 `prepublishOnly` 会执行 `npm run check`，release 脚本通常也会跑检查流程。

## 它调用谁

作为配置文件，它不“调用”函数或模块，但会引用两类外部输入。

第一是 `extends: ./tsconfig.base.json`，根配置会继承基础编译选项。也就是说，严格模式、模块解析、目标版本、库设置等更底层的 TypeScript 行为主要应在 `tsconfig.base.json` 中统一维护，`tsconfig.json` 只覆盖根项目需要的范围和别名。

第二是 `paths` 中列出的本地源码入口，包括 `packages/ai/src/index.ts`、`packages/ai/src/oauth.ts`、`packages/agent/src/index.ts`、`packages/coding-agent/src/index.ts`、`packages/coding-agent/src/core/hooks/index.ts`、`packages/tui/src/index.ts`、`packages/agent-old/src/index.ts` 等。TypeScript 在解析这些包名导入时，会把它们当作候选目标。

## 核心流程

核心流程可以理解为“根级类型检查的输入构建”。

执行 `npm run check` 后，`tsgo --noEmit` 读取 `tsconfig.json`，先合并 `tsconfig.base.json` 的基础选项，再应用根配置里的 `noEmit` 和 `paths`。随后 TypeScript 根据 `include` 收集所有 package 的 `src`、`test` 以及 `packages/coding-agent/examples` 下的文件，同时按 `exclude` 跳过 `dist` 和 `gondolin` 示例扩展。

当这些文件里出现类似 `import { ... } from "@earendil-works/pi-ai"` 的导入时，编译器不会优先把它当作已发布 npm 包或构建输出，而是通过 `paths` 解析到 `packages/ai/src/index.ts`。通配路径也类似，例如 `@earendil-works/pi-ai/*` 可以落到 `packages/ai/src/*.ts` 或 `packages/ai/src/providers/*.ts`。最终检查结果覆盖跨 package 的源码级类型关系，但不会产生输出文件。

## 关键函数的高层作用

这个文件没有函数、类或可执行流程。这里的“关键单元”是配置项。

`extends` 的作用是复用仓库统一 TypeScript 基线，避免每个入口重复声明基础规则。

`noEmit` 的作用是把根项目限定为检查入口，防止一次全仓检查污染输出目录。

`paths` 是最关键的协作规则，保证 workspace 包之间以真实包名导入时仍能解析到源码。这对跨包重构、测试类型检查、编辑器跳转都很重要。

`include` 决定根检查的覆盖面，把源码和测试纳入同一个项目，有利于发现测试中对内部 API 的错误使用。

`exclude` 控制噪声和边界，避免检查构建产物，也避免把特定示例扩展目录纳入统一约束。

## 修改风险

最大风险是改动 `paths` 造成跨包导入解析变化。比如删除 `@earendil-works/pi-ai/dist/*` 或调整 `@earendil-works/pi-coding-agent/hooks`，可能让已有源码、测试或示例无法解析模块，或让类型检查使用错误入口。

第二类风险是扩大或缩小 `include`。扩大范围可能把不适合根级检查的示例、生成文件或实验代码纳入 `npm run check`，导致检查成本和错误数量上升；缩小范围则可能漏掉测试、示例或某个 package 的源码，使 CI 失去覆盖。

第三类风险是移除 `noEmit`。根检查覆盖多个 package，如果开始 emit，可能在源码树中生成非预期产物，和各 package 的构建输出策略冲突。

第四类风险是和 `tsconfig.base.json` 的职责混淆。通用编译语义应放在 base，根文件更适合管理 monorepo 检查范围和路径别名。把 package 专属构建选项放到这里，可能影响所有包的编辑器诊断和 `npm run check`。
