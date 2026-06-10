# 文件：packages/coding-agent/tsconfig.examples.json

## 一句话定位

`packages/coding-agent/tsconfig.examples.json` 是 `@earendil-works/pi-coding-agent` 包内专门给 `examples/**/*.ts` 使用的 TypeScript 类型检查配置，用来让示例代码在仓库源码环境下直接引用本地包源码、相邻 workspace 包源码和特定依赖，而不是依赖已经构建好的 `dist` 产物。

## 它暴露/定义了什么

这个文件本身不暴露运行时代码，也不定义函数、类或模块导出。它定义的是一组 TypeScript 编译器配置：

- `extends`: 继承仓库根部的 `../../tsconfig.base.json`，复用统一的语言级别、模块解析、严格度等基础规则。
- `compilerOptions.noEmit`: 设置为 `true`，表示该配置只做类型检查，不输出 JavaScript 或声明文件。
- `compilerOptions.paths`: 为示例代码提供本地源码别名映射。
- `compilerOptions.skipLibCheck`: 设置为 `true`，跳过依赖声明文件检查，降低示例类型检查被第三方声明噪声阻断的概率。
- `include`: 只纳入 `examples/**/*.ts`。
- `exclude`: 排除 `node_modules` 和 `dist`。

其中最关键的是 `paths`。它把 `@earendil-works/pi-coding-agent` 指向 `./src/index.ts`，把 `@earendil-works/pi-coding-agent/hooks` 指向 `./src/core/hooks/index.ts`，把 `@earendil-works/pi-tui`、`@earendil-works/pi-ai` 指向相邻包源码入口，并把 `typebox` 指向根 `node_modules/typebox`。这说明示例不是按发布包消费模型检查，而是按 monorepo 源码联调模型检查。

## 谁调用它

根据当前片段推断，直接调用者应是开发或 CI 的 TypeScript 检查命令，例如 `tsgo -p packages/coding-agent/tsconfig.examples.json`、`tsc -p packages/coding-agent/tsconfig.examples.json`，或被根部 `npm run check` 间接串联。依据是该文件只含 `noEmit: true`，且 `package.json` 中构建命令使用独立的 `tsconfig.build.json`，说明它不是发布构建入口，而是示例代码类型检查入口。

另一个相关入口是根 `tsconfig.json`，它的 `include` 覆盖了 `packages/coding-agent/examples/**/*`，但根配置还排除了部分扩展示例目录。相比之下，本文件更像 coding-agent 包自有的示例专用配置，负责在包上下文内保证 SDK 示例、extension 示例等 TypeScript 文件能以本地源码方式通过检查。

`packages/coding-agent/package.json` 的 `files` 包含 `examples`，`copy-binary-assets` 也会复制 `examples` 到发布产物目录。这意味着示例代码不仅是仓库内开发材料，也会随包或二进制资源一起分发；因此它们需要单独维护可检查性。

## 它调用谁

作为配置文件，它不“调用”函数，但会驱动 TypeScript 编译器解析这些目标：

- `../../tsconfig.base.json`: 上游基础配置。
- `examples/**/*.ts`: 被检查的示例源文件集合。
- `./src/index.ts`: `@earendil-works/pi-coding-agent` 的本地源码入口。
- `./src/core/hooks/index.ts`: hooks 子路径入口。
- `../tui/src/index.ts`: `@earendil-works/pi-tui` 的本地源码入口。
- `../ai/src/index.ts`: `@earendil-works/pi-ai` 的本地源码入口。
- `../../node_modules/typebox`: `typebox` 依赖的解析位置。

这些映射让示例代码看到当前工作区的最新 API 类型，而不是 npm 发布版本或 `dist` 声明文件。对一个 monorepo 来说，这能更早发现示例与源码 API 演进之间的不一致。

## 核心流程

核心流程可以理解为“示例源码类型检查链路”：

1. TypeScript 进程读取 `packages/coding-agent/tsconfig.examples.json`。
2. 配置继承 `../../tsconfig.base.json`，获得仓库统一的 TypeScript 基础规则。
3. 编译器根据 `include` 收集 `packages/coding-agent/examples/**/*.ts` 下的示例文件。
4. 示例文件中如果导入 `@earendil-works/pi-coding-agent`、`@earendil-works/pi-coding-agent/hooks`、`@earendil-works/pi-tui`、`@earendil-works/pi-ai` 或 `typebox`，会优先按 `paths` 映射解析到本地源码或根依赖。
5. 编译器做语义检查和类型检查，但由于 `noEmit: true`，不会生成构建产物。
6. `node_modules` 和 `dist` 被排除，避免检查外部安装目录和历史构建输出。

这个流程的价值在于：示例代码既能像真实用户一样通过包名导入，又能在仓库开发阶段绑定到未发布的源码类型。这样当 SDK、hooks、TUI 或 AI 包的公开类型改变时，示例会尽早暴露破坏性变化。

## 关键函数的高层作用

本文件没有函数。若把配置项视为“关键机制”，高层作用如下：

`extends` 负责把示例检查纳入全仓库统一 TypeScript 规则，避免示例使用一套孤立标准。

`paths` 是最核心的机制，负责把包名导入改写到 monorepo 源码入口。它决定示例代码到底验证的是本地开发态 API，还是安装态 API。

`include` 控制检查边界，只关注 `examples/**/*.ts`，避免把 `src`、`test`、构建输出或文档脚本混入这个专用检查任务。

`noEmit` 把该配置限定为质量门禁，而不是构建配置。它的目标是发现类型问题，不参与发布产物生成。

`skipLibCheck` 降低第三方声明文件对示例检查的影响。它通常意味着项目更关注自身示例与本地 API 的兼容性，而不是在这里审计依赖声明。

## 修改风险

最大风险是改动 `paths`。如果 `@earendil-works/pi-coding-agent` 不再指向 `./src/index.ts`，示例可能转而解析到已构建的 `dist`、安装包或错误入口，导致类型检查结果和当前源码脱节。这样会掩盖源码 API 变更对示例的影响。

修改 `@earendil-works/pi-coding-agent/hooks` 映射也有较高风险。hooks 是扩展示例常用的 API 面，路径错位会让扩展示例无法验证真实 hook 类型，或者继续依赖已经废弃的入口。

修改 `@earendil-works/pi-tui`、`@earendil-works/pi-ai` 的映射会影响跨包示例。coding-agent 的示例明显覆盖 TUI、provider、SDK、extension 等能力；如果相邻包源码不再被解析，示例可能只在本地偶然通过，在源码联动开发时失去预警能力。

扩大 `include` 会增加检查范围，可能把不应由 examples 配置负责的源码、测试或 fixture 拉进来，造成重复检查或无关错误。缩小 `include` 则可能漏掉示例目录，尤其是新增的 extension 或 SDK 示例。

移除 `noEmit` 风险较高，因为该配置会开始写出编译产物，可能污染工作区或与 `dist`、构建脚本职责重叠。

关闭 `skipLibCheck` 可能提升严格性，但也可能让示例检查被第三方声明问题阻塞。若要调整，应确认根配置、依赖版本和 CI 检查链路能承受新增错误。

总体上，这个文件看似小，但它是 coding-agent 示例代码与本地源码 API 之间的类型契约。修改时应重点验证 `examples` 下 SDK 和 extensions 示例仍能按包名导入，并确认 `npm run check` 或对应 TypeScript 检查任务没有因为解析目标变化而失去覆盖。
