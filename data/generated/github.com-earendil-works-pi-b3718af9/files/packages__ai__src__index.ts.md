# 文件：packages/ai/src/index.ts
## 一句话定位
这是 `@earendil-works/pi-ai` 的根入口聚合层，负责把包内最常用的类型、注册表、模型、provider、工具函数和 OAuth 相关类型统一对外暴露，方便外部只通过一个入口导入整个 AI SDK。

## 它暴露/定义了什么
这个文件本身几乎不定义业务逻辑，核心工作是做“出口目录”。它把 `typebox` 的 `Type`、`Static`、`TSchema` 重新导出，同时把 `api-registry.ts`、`models.ts`、`stream.ts`、`types.ts`、`utils/*`、`session-resources.ts`、`images.ts`、`providers/register-builtins.ts` 等模块的公共 API 汇总到包根入口。  
根据当前片段推断，它是该包的主对外面板，因为 `packages/ai/package.json` 的 `main`、`types`、`exports["."]` 都指向构建后的 `dist/index.*`。

## 谁调用它
调用方主要是包外消费者和同仓库内的上层包。仓库里能直接看到 `packages/agent`、`packages/coding-agent`、`scripts/browser-smoke-entry.ts`、以及大量 `packages/ai/README.md` 示例都通过 `@earendil-works/pi-ai` 导入。  
此外，`tsconfig.json` 把 `@earendil-works/pi-ai` 映射到 `packages/ai/src/index.ts`，说明在源码开发态下，这个文件也是整个包入口解析点。

## 它调用谁
它自身没有运行时流程，只做静态 re-export，所以“调用谁”更多是“依赖谁”。它直接依赖 `typebox`，以及包内多个子模块：`api-registry.ts`、`env-api-keys.ts`、`image-models.ts`、`images.ts`、`models.ts`、`providers/*`、`utils/*` 等。  
这些被导出的模块才是真正承载逻辑的地方，例如 provider 注册、模型选择、流式完成、图片生成、诊断和验证。

## 核心流程
1. 外部代码从 `@earendil-works/pi-ai` 导入，而不是分别找各个子文件。  
2. 这个入口把稳定的公共能力集中暴露出去，形成单一 SDK 面。  
3. 下游包按需拿到类型、注册函数、模型函数、OAuth 类型或工具函数。  
4. 构建时，`dist/index.js` 和 `dist/index.d.ts` 成为发布给 npm 的主入口。

## 关键函数的高层作用
这里没有业务函数定义，最关键的其实是几个“导出面”：
- `Type`、`Static`、`TSchema`：把 `typebox` 的 schema 能力提升为包级基础设施，供模型参数、工具参数和校验逻辑统一使用。
- `export * from "./providers/register-builtins.ts"`：让默认 provider 注册能力从根入口可见，保证消费者一导入包就能获得内置能力。
- `export * from "./utils/validation.ts"`、`./utils/json-parse.ts`、`./utils/overflow.ts`：把 AI 交互中常用的修复、校验、上下文溢出判断能力统一提供给上层。

## 修改风险
这个文件是公共 API 的总开关，风险很高。任何增删导出都会影响 `packages/agent`、`packages/coding-agent` 以及外部安装者的编译和运行。  
最常见的风险有三类：一是删掉现有导出导致下游缺符号；二是把 type-only 导出改成值导出或反过来，造成构建差异；三是新增导出却没有同步维护 `package.json` 的 subpath exports、README 和发布产物，导致源码能用、发布包不能用。  
如果要改这里，通常要把它当作 API 变更来审，优先确认是否会破坏已有 import 路径和类型面。
