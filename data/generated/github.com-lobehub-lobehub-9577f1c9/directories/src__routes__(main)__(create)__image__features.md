# 目录：src/routes/(main)/(create)/image/features

## 它负责什么

`src/routes/(main)/(create)/image/features` 是「创建图片」页面在路由层内的 image 专属功能组件集合。它不直接定义整条路由，也不直接实现后端生成逻辑，而是把通用的 `create` 生成页面框架、图片生成专用的 `useImageStore`、图片配置控件、Prompt 输入区、生成结果流组合起来。

从调用关系看，外层页面在 `src/routes/(main)/(create)/image/index.tsx` 中使用：

```tsx
<CreateGenerationPage PromptInput={PromptInput} Workspace={ImageWorkspace} path="/image" />
```

也就是说，这个目录提供两个关键能力：

1. `PromptInput`：让用户输入图片生成 prompt、选择模型、调整图片参数、上传参考图并触发生成。
2. `ImageWorkspace` / `GenerationFeed`：展示当前 topic 下的生成批次、生成中状态、成功图片、错误状态，以及复用、复制、删除、下载等操作。

它本质上是「图片生成页面的业务 UI 层」，上游接入 route/layout，下游接入 `useImageStore`、文件上传 Store、AI 模型基础设施 Store、通用生成页面组件和图片生成服务。

## 关键组成

### `ImageWorkspace`

入口文件：

```text
src/routes/(main)/(create)/image/features/ImageWorkspace/index.tsx
```

`ImageWorkspace` 是工作区适配层。它把通用组件 `GenerationWorkspace` 和 image 专属实现拼起来：

- `GenerationFeed`：图片生成结果列表。
- `PromptInput`：图片 prompt 输入框。
- `SkeletonList`：加载占位。
- `useImageStore`：图片生成状态来源。
- `generationTopicSelectors.activeGenerationTopicId`：当前 topic。
- `generationBatchSelectors.currentGenerationBatches`：当前 topic 下的生成批次。
- `generationBatchSelectors.isCurrentGenerationTopicLoaded`：当前 topic 是否加载完成。

这里的重点是：`ImageWorkspace` 自己不关心如何生成图片，也不关心批次如何存储，它只把 `GenerationWorkspace` 需要的组件和 selectors 传进去。

### `PromptInput`

入口文件：

```text
src/routes/(main)/(create)/image/features/PromptInput/index.tsx
```

这是本目录最核心的交互组件，负责图片生成前的全部输入区逻辑。

它主要做这些事：

- 读取并修改 `prompt` 参数。
- 读取当前模型与 provider。
- 根据模型参数 schema 判断哪些配置项可用。
- 渲染模型切换面板 `ModelSwitchPanel`。
- 渲染图片生成参数配置弹层 `ConfigAction`。
- 支持参考图上传和内联预览 `InlineImageReference`。
- 支持 prompt 优化动作 `PromptTransformAction`。
- 点击生成时检查登录状态，不登录则走 `loginRequired.redirect`。
- 登录后调用 `useImageStore((s) => s.createImage)` 发起生成。
- 读取 URL query 中的 `prompt`、`model` 参数，并在初始化后自动填入或自动生成。

它会动态判断模型支持哪些参数，例如：

- `imageUrl`
- `imageUrls`
- `quality`
- `resolution`
- `size`
- `seed`
- `steps`
- `cfg`
- `promptExtend`
- `watermark`
- `webSearch`

这些判断来自：

```ts
imageGenerationConfigSelectors.isSupportedParam
```

因此同一个 `PromptInput` 面对不同图片模型时，配置面板会自动变化。

### `ConfigPanel`

目录：

```text
src/routes/(main)/(create)/image/features/ConfigPanel
```

`ConfigPanel` 是图片生成参数控件集合。它通过 `index.ts` 对外导出多个控件：

```ts
export { default as AspectRatioSelect } ...
export { default as CfgSliderInput } ...
export { default as DimensionControlGroup } ...
export { default as ImageNum } ...
export { default as ImageUpload } ...
export { default as ImageModelItem } ...
export { default as QualitySelect } ...
export { default as ResolutionSelect } ...
export { default as SeedNumberInput } ...
export { default as SizeSelect } ...
export { default as StepsSliderInput } ...
export { useAutoDimensions } ...
```

这些组件一般不自己维护最终业务状态，而是通过 `useImageStore` 或 `useGenerationConfigParam` 读写 `generationConfig`。

代表组件如下。

`QualitySelect` 使用：

```ts
useGenerationConfigParam('quality')
```

从当前参数 schema 中取枚举值，并把 `standard`、`hd` 转成 i18n 文案。

`StepsSliderInput` 使用：

```ts
useGenerationConfigParam('steps')
```

把模型 schema 中的 `min`、`max` 交给 `SliderWithInput`。

`ImageNum` 控制一次生成几张图。它读取：

```ts
imageGenerationConfigSelectors.imageNum
```

并通过：

```ts
setImageNum
```

写回 Store。它有一个业务特性相关的最大值逻辑：

- 如果 `enableBusinessFeatures` 开启，默认最大值是 `8`。
- 否则默认最大值是 `50`。

预设数量是 `[1, 2, 4, 8]`，也支持自定义输入。

`DimensionControlGroup` 负责宽高和纵横比控制。它使用：

```ts
useDimensionControl()
```

得到：

- `width`
- `height`
- `aspectRatio`
- `isLocked`
- `toggleLock`
- `setWidth`
- `setHeight`
- `setAspectRatio`
- `widthSchema`
- `heightSchema`
- `options`

它不是简单的两个数字输入，而是带有纵横比锁定、schema 限制和 slider 输入的组合控件。

### 图片上传相关组件与 hooks

相关文件：

```text
ConfigPanel/components/ImageUpload.tsx
ConfigPanel/components/MultiImagesUpload/index.tsx
ConfigPanel/hooks/useDragAndDrop.ts
ConfigPanel/hooks/useUploadFilesValidation.ts
ConfigPanel/hooks/useAutoDimensions.ts
ConfigPanel/utils/imageValidation.ts
ConfigPanel/utils/dimensionConstraints.ts
```

`ImageUpload` 是单图上传组件，支持：

- 点击选择图片。
- 拖拽上传。
- 上传中本地 blob 预览。
- 上传进度展示。
- 上传成功后展示远程图片。
- 删除或替换图片。
- 文件大小校验。
- 图片尺寸校验。
- 上传成功后把 `url` 或 `{ url, dimensions }` 传给上层。

它调用：

```ts
useFileStore((s) => s.uploadWithProgress)
```

真正上传文件。上传组件本身不负责后端存储，只负责 UI、校验和回调。

`useUploadFilesValidation` 统一封装文件校验逻辑，底层调用 `imageValidation.ts` 中的工具：

- `validateImageFileSize`
- `validateImageCount`
- `getImageDimensions`
- `validateImageDimensions`
- `validateImageFiles`
- `formatFileSize`

校验失败后会通过 `antd` 的 `message.error` 展示 i18n 错误文案。

`useAutoDimensions` 的作用是：当上传图片返回尺寸信息时，如果当前模型支持 `width` 和 `height` 参数，就自动把上传图片的尺寸约束后写入生成配置。

它会读取：

```ts
imageGenerationConfigSelectors.parametersSchema
imageGenerationConfigSelectors.isSupportedParam('width')
imageGenerationConfigSelectors.isSupportedParam('height')
```

然后调用：

```ts
setWidth
setHeight
```

尺寸约束来自 `model-bank` 的 `DEFAULT_DIMENSION_CONSTRAINTS`，并通过 `constrainDimensions` 做调整。

### `GenerationFeed`

入口文件：

```text
src/routes/(main)/(create)/image/features/GenerationFeed/index.tsx
```

它是图片生成结果流的 image 适配层。它读取当前生成批次：

```ts
useImageStore(generationBatchSelectors.currentGenerationBatches)
```

然后传给通用的：

```ts
@/routes/(main)/(create)/features/GenerationFeed
```

并通过 `renderBatchItem` 指定每个批次用 `GenerationBatchItem` 渲染。

### `GenerationBatchItem`

文件：

```text
src/routes/(main)/(create)/image/features/GenerationFeed/BatchItem.tsx
```

一个 batch 表示一次生成请求，里面可能有多张图片结果。`GenerationBatchItem` 负责渲染：

- 参考图 `ReferenceImages`
- prompt Markdown
- 生成图片网格
- 模型标签 `ModelTag`
- 宽高标签
- 生成数量标签
- 创建时间
- 批次操作按钮

它支持的批次操作包括：

- `reuseSettings`：复用当前批次的模型、provider 和配置，但会排除 `seed`。
- `copyPrompt`：复制 prompt 到剪贴板。
- `deleteBatch`：删除当前批次。

特殊逻辑：

如果 batch 中任意 generation 的错误类型是：

```ts
AsyncTaskErrorType.InvalidProviderAPIKey
```

则渲染 `GenerationInvalidAPIKey`，提示 API Key 无效。

此外，它还接入了：

```ts
useRenderBusinessBatchItem(batch)
```

如果业务侧需要替换 batch 渲染，可以返回 `businessBatchItem`。根据当前片段推断，这是给云端或商业功能扩展用的插槽式覆盖点。

### `GenerationItem`

入口文件：

```text
src/routes/(main)/(create)/image/features/GenerationFeed/GenerationItem/index.tsx
```

`GenerationItem` 是单张生成图片的渲染单元。它根据异步任务状态切换三种状态组件：

- `SuccessState`
- `ErrorState`
- `LoadingState`

它读取：

```ts
generation.task.status
```

如果状态是 `AsyncTaskStatus.Success` 且存在 `generation.asset?.url`，渲染成功态。

如果状态是 `AsyncTaskStatus.Error`，渲染错误态。

其他状态，例如 pending 或 processing，则渲染 loading 态。

它还负责：

- 轮询生成状态：`useCheckGenerationStatus(generation.id, generation.task.id, activeTopicId!, shouldPoll)`
- 删除单张生成结果：`removeGeneration`
- 下载图片：`useDownloadImage`
- 复制或复用 seed：`reuseSeed` / `navigator.clipboard.writeText`
- 复制错误信息
- 根据 generation 与 batch 推断展示比例：`getAspectRatio`

这里的一个重要点是：轮询逻辑在 UI 组件挂载时触发，但真正的状态查询动作来自 `useImageStore` 暴露的 `useCheckGenerationStatus`。

## 上下游关系

### 上游：路由和通用创建页框架

直接上游是：

```text
src/routes/(main)/(create)/image/index.tsx
src/routes/(main)/(create)/image/_layout/index.tsx
```

`index.tsx` 把本目录的 `PromptInput`、`ImageWorkspace` 交给通用的 `CreateGenerationPage`。

`_layout/index.tsx` 使用通用 `GenerationLayout`，并把 image 专属参数传进去：

- `namespace="image"`
- `navKey="image"`
- `useStore={useImageStore}`
- `generationTopicsSelector={generationTopicSelectors.generationTopics}`
- `viewModeStatusKey="imageTopicViewMode"`

因此，路由层负责搭页面骨架，本目录负责图片生成页面内部的核心体验。

### 中游：本目录内的 image 专属 UI

本目录主要分成三块：

```text
PromptInput       生成输入与配置
ImageWorkspace    工作区适配
GenerationFeed    生成结果展示
ConfigPanel       图片参数控件集合
```

它们之间的关系大致是：

```text
ImageWorkspace
  ├─ PromptInput
  └─ GenerationFeed
       └─ GenerationBatchItem
            └─ GenerationItem
```

`PromptInput` 同时会使用 `ConfigPanel` 导出的参数控件。

### 下游：Store、Service、通用组件与基础设施

主要下游包括：

```text
@/store/image
@/store/file
@/store/aiInfra
@/store/user
@/store/serverConfig
@/routes/(main)/(create)/features/*
@/features/ModelSwitchPanel
@/features/PromptTransform/PromptTransformAction
@/hooks/useFetchAiImageConfig
@/hooks/useDownloadImage
```

其中最关键的是 `@/store/image`。本目录大量通过 `useImageStore` 读取和修改图片生成状态：

- 当前 prompt
- 当前模型
- 当前 provider
- 参数 schema
- 当前 topic
- 当前 batches
- 是否正在生成
- 创建图片动作
- 删除 batch
- 删除 generation
- 复用设置
- 复用 seed
- 轮询生成状态

根据当前片段推断，真正的生成请求最终会从 `useImageStore` 的 `createImage` action 进入 `imageService.createImage`，因为搜索结果显示：

```text
src/store/image/slices/createImage/action.ts
```

中存在 `createImage()`，并调用了 `imageService.createImage(...)`。本目录本身不直接调用服务层。

文件上传则通过：

```ts
useFileStore((s) => s.uploadWithProgress)
```

完成。上传结果再回填到 image generation config 的 `imageUrl` 或 `imageUrls`。

模型列表来自：

```ts
useAiInfraStore(aiProviderSelectors.enabledImageModelList)
```

登录状态来自：

```ts
useUserStore(authSelectors.isLogin)
```

是否启用商业特性来自：

```ts
useServerConfigStore(serverConfigSelectors.enableBusinessFeatures)
```

## 运行/调用流程

### 页面进入流程

1. 用户访问 `/image`。
2. `src/routes/(main)/(create)/image/index.tsx` 渲染 `CreateGenerationPage`。
3. `CreateGenerationPage` 接收本目录提供的 `PromptInput` 和 `ImageWorkspace`。
4. `_layout/index.tsx` 渲染 `GenerationLayout`，注入 `useImageStore`、topic selector、导航 key 等。
5. `ImageWorkspace` 渲染通用 `GenerationWorkspace`，并传入 image 专属 selectors。
6. 当前 topic 的 batches 由 `GenerationFeed` 展示。

### 输入与配置流程

1. `PromptInput` 通过 `useGenerationConfigParam('prompt')` 读取 prompt。
2. 用户输入 prompt 后，`setValue` 写回 image generation config。
3. 用户选择模型时，`ModelSwitchPanel` 调用 `setModelAndProviderOnSelect(model, provider)`。
4. `useFetchAiImageConfig()` 拉取或刷新图片模型配置。
5. 组件通过 `isSupportedParam` 判断当前模型支持哪些参数。
6. 支持的参数才会出现在配置面板中，例如 quality、resolution、size、steps、cfg、seed、watermark 等。
7. 每个配置控件通过 `useGenerationConfigParam(paramName)` 或专用 action 写回 Store。

### 参考图上传流程

1. 如果模型支持 `imageUrl` 或 `imageUrls`，`PromptInput` 会渲染 `InlineImageReference`。
2. 用户添加图片后，回调进入 `handleAddImage`。
3. `handleAddImage` 用 `useAutoDimensions().extractUrlAndDimensions` 兼容两种数据格式：
   - 旧格式：`string`
   - 新格式：`{ url, dimensions }`
4. 如果上传结果带 dimensions，则调用 `autoSetDimensions(dimensions)`。
5. 如果当前模型支持单图 `imageUrl` 且还没有单图，优先写入 `imageUrl`。
6. 否则如果支持多图 `imageUrls`，追加到 `imageUrls`。
7. 删除参考图时，按 URL 判断是清空 `imageUrl` 还是从 `imageUrls` 中移除。

### 点击生成流程

1. 用户点击生成按钮。
2. `PromptInput.handleGenerate` 先判断 `isLogin`。
3. 未登录时调用 `loginRequired.redirect({ timeout: 2000 })`。
4. 已登录时调用 `await createImage()`。
5. 根据当前片段推断，`createImage()` 在 `src/store/image/slices/createImage/action.ts` 中收集当前 Store 里的模型、provider、prompt、参数等，再调用 `imageService.createImage(...)`。
6. 创建后的 batch 和 generation 状态进入 `useImageStore`。
7. `GenerationFeed` 读取 `currentGenerationBatches`，重新渲染列表。

### 生成结果展示流程

1. `GenerationFeed` 把每个 batch 交给 `GenerationBatchItem`。
2. `GenerationBatchItem` 先判断 batch 是否为空，空则不渲染。
3. 如果 batch 内有 API Key 无效错误，展示 `GenerationInvalidAPIKey`。
4. 如果业务侧 `useRenderBusinessBatchItem(batch)` 返回替代渲染，则优先展示业务渲染。
5. 否则渲染 prompt、参考图、图片网格和批次操作区。
6. 每个 generation 交给 `GenerationItem`。
7. `GenerationItem` 判断任务状态：
   - success + asset URL：展示 `SuccessState`
   - error：展示 `ErrorState`
   - 其他：展示 `LoadingState`
8. 非最终状态会通过 `useCheckGenerationStatus` 继续轮询。
9. 用户可以对单张图执行下载、删除、复制错误、复用或复制 seed 等操作。

### URL 参数自动触发流程

`PromptInput` 还会处理 URL query：

- `prompt`
- `model`

当 `modelParam` 存在且 Store 已初始化时，它会在 `enabledImageModelList` 中查找对应模型，并调用 `setModelAndProviderOnSelect` 设置模型和 provider，然后清除 URL 参数。

当 `promptParam` 存在且用户已登录时，它会解码 prompt，写入 prompt 参数，清除 URL 参数，并延迟 `100ms` 自动调用 `createImage()`。

这个逻辑说明 `/image?prompt=...&model=...` 可以作为一种外部跳转到图片生成页并自动启动生成的入口。

## 小白阅读顺序

1. 先读页面入口：

```text
src/routes/(main)/(create)/image/index.tsx
```

理解 `/image` 页面不是自己写完整 UI，而是把 `PromptInput` 和 `ImageWorkspace` 注入 `CreateGenerationPage`。

2. 再读布局入口：

```text
src/routes/(main)/(create)/image/_layout/index.tsx
```

看它如何把 `GenerationLayout`、`useImageStore`、topic selector、breadcrumb 连接起来。

3. 读工作区适配：

```text
src/routes/(main)/(create)/image/features/ImageWorkspace/index.tsx
```

理解 `GenerationWorkspace` 是通用容器，image 目录只负责传入 image 专属组件和 selectors。

4. 重点读输入区：

```text
src/routes/(main)/(create)/image/features/PromptInput/index.tsx
```

这是理解图片生成页面的核心。建议按以下顺序看：

- `useGenerationConfigParam('prompt')`
- `createImage`
- `isSupportedParam`
- `ModelSwitchPanel`
- `ConfigAction`
- `InlineImageReference`
- `handleGenerate`
- `handleAddImage`
- URL query 处理逻辑

5. 再读配置面板出口：

```text
src/routes/(main)/(create)/image/features/ConfigPanel/index.ts
```

先知道有哪些控件，再按需看具体组件。

6. 配置控件建议先看简单的：

```text
ConfigPanel/components/QualitySelect.tsx
ConfigPanel/components/StepsSliderInput.tsx
ConfigPanel/components/ImageNum.tsx
```

这些能帮助理解 `useGenerationConfigParam` 和 `useImageStore` 的读写方式。

7. 然后看尺寸控制：

```text
ConfigPanel/components/DimensionControlGroup.tsx
ConfigPanel/hooks/useAutoDimensions.ts
ConfigPanel/utils/dimensionConstraints.ts
```

这部分涉及模型 schema、宽高限制和上传图片自动设置尺寸。

8. 再看上传：

```text
ConfigPanel/components/ImageUpload.tsx
ConfigPanel/components/MultiImagesUpload/index.tsx
ConfigPanel/hooks/useUploadFilesValidation.ts
ConfigPanel/utils/imageValidation.ts
```

重点看上传前校验、上传中预览、上传成功回调。

9. 最后看结果流：

```text
features/GenerationFeed/index.tsx
features/GenerationFeed/BatchItem.tsx
features/GenerationFeed/GenerationItem/index.tsx
```

理解 batch、generation、task status 三层关系。

## 常见误区

1. 不要把这个目录理解成完整的图片生成系统。

它只是路由内的图片生成 UI feature。真正的状态和动作在 `@/store/image`，真正的创建请求根据当前片段推断在 `imageService.createImage`，文件上传在 `@/store/file`。

2. `ConfigPanel` 不是一个单独的大面板组件。

它更像一组参数控件集合。真正的配置弹层是在 `PromptInput` 中通过 `ConfigAction` 组合出来的。

3. 不是所有模型都会显示所有配置项。

`PromptInput` 会用 `imageGenerationConfigSelectors.isSupportedParam` 判断当前模型支持什么。比如一个模型不支持 `seed`，`SeedNumberInput` 就不会显示；不支持 `imageUrls`，多参考图也不会出现。

4. `imageUrl` 和 `imageUrls` 不是同一个字段。

`imageUrl` 表示单张参考图，`imageUrls` 表示多张参考图。`handleAddImage` 会优先填充空的 `imageUrl`，之后再追加到 `imageUrls`。删除时也会按 URL 判断来源。

5. 上传组件返回值可能不只是 URL 字符串。

`ImageUpload` 的 `onChange` 兼容旧格式和新格式：

```ts
string
{ url, dimensions }
```

`PromptInput` 通过 `extractUrlAndDimensions` 处理这两种格式。如果只按字符串理解，就会漏掉自动设置宽高的逻辑。

6. 生成数量 `ImageNum` 的最大值不是固定的。

它受 `enableBusinessFeatures` 影响。当前代码里，商业特性开启时默认最大值为 `8`，否则为 `50`。不要只看预设 `[1, 2, 4, 8]` 就以为最多只能生成 8 张。

7. `GenerationFeed` 本身不是图片专属的完整列表实现。

`features/GenerationFeed/index.tsx` 使用的是通用 `@/routes/(main)/(create)/features/GenerationFeed`，这里只是传入 image batches 和 `GenerationBatchItem` 渲染函数。

8. 单张图的 loading/error/success 不是由 batch 决定，而是由 generation 的 task status 决定。

`GenerationItem` 读取：

```ts
generation.task.status
```

再决定展示 `SuccessState`、`ErrorState` 还是 `LoadingState`。batch 只是一次请求的集合容器。

9. API Key 错误在 batch 层特殊处理。

如果任意 generation 出现 `AsyncTaskErrorType.InvalidProviderAPIKey`，`GenerationBatchItem` 会直接渲染 `GenerationInvalidAPIKey`。这和普通 generation error 的 `ErrorState` 不是同一路径。

10. URL query 可能触发自动生成。

`PromptInput` 会读取 `prompt` 和 `model` 参数。满足初始化和登录条件后，`prompt` 参数会被写入输入框，并触发 `createImage()`。排查“为什么一进页面就开始生成”时要注意这个逻辑。
