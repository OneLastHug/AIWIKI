# 文件：packages/ai/bedrock-provider.js
## 一句话定位
这是 `@earendil-works/pi-ai` 包对外提供的 Bedrock 入口转发文件，本身不承载业务逻辑，只把 `./dist/bedrock-provider.js` 里的导出原样暴露出去。根据当前片段推断，它的存在主要是为了让发布后的包在 `exports["./bedrock-provider"]` 下有稳定入口。

## 它暴露/定义了什么
文件内容只有一行：`export * from "./dist/bedrock-provider.js";`。它不定义新函数、不包一层适配器，也不做参数处理。真正对外可见的符号，来自构建产物 `packages/ai/dist/bedrock-provider.js`，而源码侧对应的是 `packages/ai/src/bedrock-provider.ts` 中导出的 `bedrockProviderModule`。

## 谁调用它
外部最直接的调用方是通过包导入路径 `@earendil-works/pi-ai/bedrock-provider` 的消费者。仓库内可以确认的一处调用是在 `packages/coding-agent/src/bun/register-bedrock.ts`，那里直接从这个入口导入 `bedrockProviderModule`。`packages/ai/package.json` 也明确把这个路径挂到了包的 `exports` 表里，所以它是一个正式公共入口，而不是内部私用文件。

## 它调用谁
这个文件自己几乎不“调用”任何业务代码，只是把导出转发到 `./dist/bedrock-provider.js`。顺着源码对应关系看，`packages/ai/src/bedrock-provider.ts` 再从 `./providers/amazon-bedrock.ts` 引入 `streamBedrock` 和 `streamSimpleBedrock`，并把它们封装成 `bedrockProviderModule`。所以真实的实现链路是：入口文件 -> 构建产物 -> 源码入口 -> Bedrock 流式请求实现。

## 核心流程
1. 消费者通过 `@earendil-works/pi-ai/bedrock-provider` 导入。
2. `packages/ai/package.json` 的 `exports` 把这个子路径解析到 `dist/bedrock-provider.js`。
3. 运行时加载的不是源文件本体，而是构建后的实现。
4. 构建产物再向下转到源码里的 Bedrock provider 模块。
5. 最终暴露出用于 Bedrock 调用的流式能力，供像 `register-bedrock.ts` 这样的上层集成代码注册或装配。

## 关键函数的高层作用
这个文件里没有函数。需要理解的核心能力在源码实现侧：
- `streamBedrock`：面向 Bedrock 的流式请求主入口，负责把上层消息和配置送入 Bedrock 运行链路。
- `streamSimpleBedrock`：更轻量的流式入口，通常用于较简单的调用形态或内部复用。
- `bedrockProviderModule`：把上述能力聚合成一个模块对象，方便上层一次性引入并注册。

## 修改风险
这里的风险主要不是“逻辑写错”，而是“入口失配”。如果你改了这个文件，却没有同步 `package.json` 的 `exports`、`dist/bedrock-provider.js` 的构建结果，或者源码侧 `src/bedrock-provider.ts` 的导出形状，外部消费者会直接导入失败。另一个风险是破坏 `bedrockProviderModule` 的稳定接口，像 `packages/coding-agent/src/bun/register-bedrock.ts` 这类调用方会因此出现运行期错误。由于它是公共子路径入口，改动面虽小，但回归面是整个 Bedrock 集成链路。
