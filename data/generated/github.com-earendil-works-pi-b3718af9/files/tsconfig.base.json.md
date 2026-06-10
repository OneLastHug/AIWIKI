# 文件：tsconfig.base.json

## 一句话定位
这是整个仓库的 TypeScript 基线配置，统一规定编译目标、模块体系、类型检查强度和源码输出行为，让根配置与各包构建配置在同一套规则下工作。

## 它暴露/定义了什么
它只定义 `compilerOptions`，没有 `include`、`exclude` 或路径别名，本质上提供的是可被继承的编译参数集合。这里面最关键的是：`target: ES2022`、`module: Node16`、`moduleResolution: Node16`、`strict: true`、`erasableSyntaxOnly: true`、`declaration`/`sourceMap` 相关输出、`allowImportingTsExtensions` 与 `rewriteRelativeImportExtensions`，以及 `experimentalDecorators`、`emitDecoratorMetadata` 这类对语言特性的开关。根据当前片段推断，它的职责不是描述某个单独包，而是定义仓库默认的 TypeScript 运行边界。

## 谁调用它
它被 `tsconfig.json` 直接 `extends`，也被多个包的构建配置继承，包括 `packages/agent/tsconfig.build.json`、`packages/ai/tsconfig.build.json`、`packages/tui/tsconfig.build.json`、`packages/coding-agent/tsconfig.build.json` 和 `packages/coding-agent/tsconfig.examples.json`。也就是说，真正调用它的不是业务代码，而是 TypeScript 编译链和 IDE 语言服务，再加上这些下游 `tsconfig`。

## 它调用谁
它不直接调用任何代码或模块。它只是被上层 `tsconfig` 继承，并通过这些继承关系间接影响 `packages/*/src`、`packages/*/test`、`packages/coding-agent/examples` 的编译与检查行为。根据当前片段推断，最终生效点通常是 `tsc`、`tsserver` 以及仓库内的检查脚本。

## 核心流程
核心流程是“先定基线，再分层覆盖”。根 `tsconfig.json` 先继承它，再补充仓库级别的 `noEmit`、`paths` 和 `include/exclude`；各包的 `tsconfig.build.json` 再继承它，覆盖 `outDir`、`rootDir` 和面向产物的路径映射。这样一来，开发态和构建态共享同一套语言规则，但在输出目录、入口解析和声明文件引用上各自独立。这个结构能避免各包自己发散配置，也能保证生成产物时的类型与模块解析和源码时期一致。

## 关键函数的高层作用
这里没有函数，关键的是配置项分组的作用：
- 编译与模块组：`target`、`module`、`moduleResolution`、`lib` 决定代码以什么语言级别和 Node 语义运行。
- 类型安全组：`strict`、`skipLibCheck`、`forceConsistentCasingInFileNames`、`types: ["node"]` 约束项目级类型质量。
- 源码兼容组：`erasableSyntaxOnly`、`allowImportingTsExtensions`、`rewriteRelativeImportExtensions` 适配当前仓库的 TypeScript 写法。
- 产物组：`declaration`、`declarationMap`、`sourceMap`、`inlineSources` 决定构建输出是否带声明、映射和源码信息。
- 语言特性组：`experimentalDecorators`、`emitDecoratorMetadata`、`useDefineForClassFields: false` 影响装饰器和类字段语义。

## 修改风险
改这个文件的风险很高，因为它会同时影响所有继承它的包。比如改 `moduleResolution` 可能让路径解析和现有 `paths` 映射失配；改 `strict` 或 `erasableSyntaxOnly` 可能让大量源码和测试突然报错；改 `rewriteRelativeImportExtensions`、`allowImportingTsExtensions` 可能直接破坏构建产物中的导入路径；改装饰器相关选项则可能改变运行时行为，而不是只影响类型检查。最需要小心的是它看起来像“基础配置”，但实际上是整个仓库编译语义的共同前提。
