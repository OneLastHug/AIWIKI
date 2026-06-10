# 文件：packages/ai/scripts/generate-image-models.ts

## 一句话定位

`packages/ai/scripts/generate-image-models.ts` 是 `@earendil-works/pi-ai` 包的图片模型目录生成脚本：它从 OpenRouter 的模型接口拉取可输出图片的模型，把外部模型元数据标准化为仓库内部的 `ImagesModel` 结构，并生成 `packages/ai/src/image-models.generated.ts` 供运行时代码查询。

## 它暴露/定义了什么

这个文件不是库入口，不向外导出 API；它是一个可执行 Node ESM 脚本，顶部有 `#!/usr/bin/env node`，末尾直接调用 `main()`。内部主要定义：

- `OpenRouterModelRecord`：脚本本地使用的 OpenRouter 模型记录形状，只覆盖生成逻辑关心的字段，如 `id`、`name`、`architecture.input_modalities`、`architecture.output_modalities`、`pricing`。
- `fetchOpenRouterImageModels()`：从 OpenRouter 拉取图片输出模型，并转换为 `ImagesModel<"openrouter-images">[]`。
- `generateImageModelsFile()`：把标准化后的模型数组序列化成 TypeScript 源码字符串。
- `main()`：串联拉取、生成、写文件。

它最终产物是 `packages/ai/src/image-models.generated.ts` 中的 `IMAGE_MODELS` 常量，而不是脚本自身的导出。

## 谁调用它

直接调用方主要来自 `packages/ai/package.json`：

- `generate-image-models`: `node scripts/generate-image-models.ts`
- `build`: 先运行 `npm run generate-models`，再运行 `npm run generate-image-models`，然后执行 TypeScript 构建
- `prepublishOnly`: 通过 `npm run build` 间接调用

根据当前片段推断，开发者也可以在 `packages/ai` 包内手动运行 `npm run generate-image-models` 来刷新图片模型清单；依据是生成文件头部也提示通过该脚本更新。

生成结果的运行时消费者是 `packages/ai/src/image-models.ts`。该文件导入 `IMAGE_MODELS`，再提供 `getImageModel()`、`getImageModels()` 等查询函数。`packages/ai/src/index.ts` 继续导出 `image-models.ts`，因此包使用者最终通过公开 API 间接使用这份生成数据。

## 它调用谁

脚本依赖的外部和内部对象很少：

- Node 标准库：`fs.writeFileSync` 写入生成文件；`path.dirname`、`path.join` 计算路径；`url.fileURLToPath` 从 `import.meta.url` 推出当前脚本目录。
- 全局 `fetch`：请求 OpenRouter 模型列表接口，并带上 `output_modalities=image` 查询条件。
- 内部类型：从 `../src/types.ts` 引入 `ImagesModel` 类型，用来约束生成逻辑中的模型结构。
- 生成产物使用的类型：生成文件内会导入 `ImagesApi`、`ImagesModel` from `./types.ts`，并用 `satisfies Record<string, Record<string, ImagesModel<ImagesApi>>>` 校验生成常量。

## 核心流程

脚本启动后先通过 `fileURLToPath(import.meta.url)` 和 `dirname()` 得到 `scripts` 目录，再把 `packageRoot` 定位到 `packages/ai`。随后 `main()` 调用 `fetchOpenRouterImageModels()`。

拉取阶段会请求 OpenRouter 的模型列表，并遍历返回的 `data`。每条模型记录会被提取输入、输出模态：脚本只接受 `"text"` 和 `"image"` 两种模态，并用 `Set` 去重。若输出模态不包含 `"image"`，该模型会被跳过；若输入模态为空，则默认补成 `["text"]`。之后脚本把 OpenRouter 字段映射到内部 `ImagesModel`：`api` 固定为 `"openrouter-images"`，`provider` 固定为 `"openrouter"`，`baseUrl` 固定为脚本常量，成本字段从 `pricing` 读取并乘以 `1_000_000`，即转成每百万单位的价格表示。

生成阶段由 `generateImageModelsFile()` 完成。它先按 `id` 字典序排序，保证输出稳定；再把每个模型对象序列化成 TypeScript 对象字面量，并给单个对象追加 `satisfies ImagesModel<"openrouter-images">`。最后按 provider 分组生成 `IMAGE_MODELS` 常量，目前只有 `openrouter` 一组。

写入阶段把字符串写到 `packages/ai/src/image-models.generated.ts`。如果脚本顶层 `main()` 抛错，会打印错误并 `process.exit(1)`；但注意 `fetchOpenRouterImageModels()` 自己捕获请求或解析错误后返回空数组，因此网络失败不会让进程失败，而可能生成一个空的 `openrouter` 模型表。

## 关键函数的高层作用

`fetchOpenRouterImageModels()` 是数据适配层。它把 OpenRouter 的松散 JSON 结构转成仓库内部的强类型 `ImagesModel`，并在这里处理模态过滤、默认输入模态、provider/api 标识和价格单位换算。这个函数决定哪些上游模型会进入最终的图片模型清单。

`generateImageModelsFile()` 是代码生成层。它不再关心网络数据来源，只负责把已标准化的模型数组变成可提交、可类型检查的 TypeScript 文件。排序逻辑放在这里，目的是减少重复生成时的无意义 diff。

`main()` 是编排层。它负责连接“拉取模型数据”和“写入生成文件”两个步骤，并决定输出路径。

`OpenRouterModelRecord` 和路径初始化代码只是脚本支撑结构，作用是描述输入 JSON 的最小字段集合和定位包根目录。

## 修改风险

最高风险是生成结果的运行时兼容性。`packages/ai/src/image-models.ts` 依赖 `IMAGE_MODELS` 的 provider 分组结构，并基于生成常量推导 `KnownImagesProvider`、模型 ID 和 API 类型；如果改动生成对象的层级、键名、`api` 字段或 `provider` 字段，`getImageModel()` / `getImageModels()` 的类型推导和运行时查询都会受影响。

第二个风险是上游数据失败时的行为。当前 `fetchOpenRouterImageModels()` 捕获错误并返回空数组，构建可能继续成功但生成空目录；如果发布流程中网络短暂失败，就可能把可用图片模型意外删除。修改这里时要明确是希望“失败即中断构建”，还是继续保持“尽力生成”。

第三个风险是价格单位和字段语义。脚本把 `pricing.prompt`、`pricing.completion`、`input_cache_read`、`input_cache_write` 统一乘以 `1_000_000`。如果 OpenRouter 字段单位变化，或内部 `ImagesModel.cost` 语义变化，生成出的价格会系统性错误。

第四个风险是模型过滤范围。目前只保留输入/输出模态中的 `"text"`、`"image"`，并要求输出包含 `"image"`。如果未来支持更多模态，或者图片模型需要携带额外能力字段，必须同步更新 `ImagesModel` 类型、生成逻辑、`image-models.ts` 查询层以及相关测试。

最后，脚本内生成的是 TypeScript 源码字符串，缩进和 `JSON.stringify(...).replace()` 会直接影响生成文件格式。调整序列化模板时要关注 `npm run check` 的类型校验和稳定 diff，避免每次生成都产生无关变化。
