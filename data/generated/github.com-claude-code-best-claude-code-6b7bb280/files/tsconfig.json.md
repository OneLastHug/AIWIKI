# 文件：tsconfig.json

## 一句话定位

这是整个仓库的 TypeScript 总配置入口，负责定义语言目标、模块解析方式、路径别名、类型检查范围，以及哪些源代码会进入 `tsc --noEmit` 的严格校验流程。根据当前片段推断，它是仓库级类型系统的“总开关”，多个子包再通过 `extends` 继承它或继承它的基础层。

## 它暴露/定义了什么

它主要定义三类东西。第一是编译器行为：`target: ESNext`、`module: ESNext`、`moduleResolution: bundler`、`jsx: react-jsx`、`strict: true`、`noEmit: true` 等，决定项目按什么语义被检查。第二是运行环境声明：`types: ["bun"]`，说明全局类型偏向 Bun 运行时。第三是仓库内部模块映射：`src/*`、`@claude-code-best/builtin-tools/*`、`@claude-code-best/mcp-client/*`、`@claude-code-best/agent-tools/*`、`@claude-code-best/weixin/*`，把工作区包和源码目录映射成可直接导入的路径。

它还定义了检查边界：`include` 只覆盖 `src/**/*.ts`、`src/**/*.tsx`、`packages/**/*.ts`、`packages/**/*.tsx`，`exclude` 仅排除 `node_modules`。这意味着仓库里的主业务代码、工作区包代码都会进入统一的类型检查。

## 谁调用它

直接调用者不是业务代码，而是工具链和工作流。最明确的是 `package.json` 里的 `typecheck` 脚本：`tsc --noEmit`。CI 里也会跑同样的类型检查，所以它是提交前、持续集成和本地验证都会经过的配置文件。

另外，多个子包的 `tsconfig.json` 会继承它或继承 `tsconfig.base.json` 再由这里补强；例如 `packages/builtin-tools/tsconfig.json`、`packages/@ant/computer-use-swift/tsconfig.json`、`packages/@ant/model-provider/tsconfig.json` 等都会受到它的影响。编辑器里的 TypeScript 语言服务同样会读取它来做跳转、补全和报错定位。

## 它调用谁

它不“调用”运行时代码，但会引用一个上层基础配置：`extends: "./tsconfig.base.json"`。也就是说，它先继承基础编译选项，再在仓库级别加上路径别名和文件范围控制。

从效果上看，它间接驱动了 `tsc`、IDE 语言服务、CI 里的 typecheck 任务，以及所有依赖这些路径别名的包。`paths` 的存在还会影响各个包之间的导入解析，尤其是 `src/*` 和 workspace 包入口。

## 核心流程

核心流程可以概括成四步。先继承 `tsconfig.base.json` 的通用规则，再覆盖成仓库需要的编译策略。随后通过 `paths` 建立单仓库多包的导入捷径，让源码与工作区包都能用稳定别名互相引用。接着用 `include` 把真正需要检查的源码纳入范围，避免无关目录干扰。最后，`noEmit: true` 让这个文件只负责类型校验，不参与产物生成，因此它更像一个静态约束层，而不是构建配置。

## 关键函数的高层作用

这个文件本身没有函数，关键是字段级职责：

`extends` 负责继承公共编译基线，减少重复配置。  
`compilerOptions.strict` 负责把全仓库推入严格类型模式，是零错误 typecheck 的核心前提。  
`compilerOptions.moduleResolution: "bundler"` 负责贴合 Bun/现代打包器的解析行为，避免 Node 旧式解析与实际运行环境脱节。  
`compilerOptions.paths` 负责建立仓库内部包边界与别名映射，是跨 package 导入稳定性的关键。  
`include` 和 `exclude` 负责限定检查面，确保 `tsc` 聚焦在真正的业务和包代码上。

## 修改风险

这个文件改动面很大，风险通常不是“本文件报错”，而是全仓库连锁失败。改 `paths` 很容易导致大量 import 失效，尤其是 `src/*` 和 workspace 包入口。改 `moduleResolution`、`module` 或 `target` 可能让 Bun、编辑器、打包器的解析行为分叉。删减 `include` 会让某些源码脱离类型检查，表面上更快，实则降低约束。放宽 `strict`、`noEmit` 或 `types`，会直接削弱仓库的类型安全和运行时一致性。

如果要动它，最好同步跑 `bun run typecheck`，并检查受影响的子包 `tsconfig.json` 是否仍然沿用正确的继承链。
