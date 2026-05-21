# 目录：src/routes/(main)/(create)/video/features

## 它负责什么

`src/routes/(main)/(create)/video/features` 是 `/video` 创建页的“视频生成业务 UI 层”。它不定义路由本身，而是被同级的 `src/routes/(main)/(create)/video/index.tsx` 作为页面主体使用：页面把这里的 `PromptInput` 和 `VideoWorkspace` 传给通用的 `CreateGenerationPage`，从而形成完整的视频生成页面。

这个目录的核心职责可以概括为三件事：

1. 渲染视频生成输入区：模型选择、提示词输入、参考帧上传、比例/分辨率/时长/seed/水印/音频等参数配置。
2. 渲染视频生成工作区：把视频专用的 store、selector、输入框、生成列表和骨架屏接入通用 `GenerationWorkspace`。
3. 渲染视频生成结果流：根据异步任务状态展示加载中、成功视频、失败提示，并提供复制提示词、复用参数、下载、删除等操作。

从架构上看，它是一个“视频域适配层”：大量复用 `(create)/features` 下的通用生成组件，也复用 image 生成页的一些上传、样式和操作按钮组件，但所有状态读写都切到 `useVideoStore` 和视频相关 selectors。

## 关键组成

`ConfigPanel/`

这个目录更像“视频配置控件集合”的出口。目前 `ConfigPanel/index.ts` 只导出两个组件：

- `FrameUpload`
- `VideoModelItem`

`FrameUpload` 位于 `ConfigPanel/components/FrameUpload`，负责上传单张视频参考图，支持的参数名是 `'imageUrl' | 'endImageUrl'`。它内部调用 `useVideoGenerationConfigParam(paramName)` 读取当前值、文件大小限制、图片约束，并复用 image 创建页的 `ImageUpload` 组件。上传变化后只把结果里的 `url` 写回视频生成配置。

`VideoModelItem` 位于 `ConfigPanel/components/ModelSelect/VideoModelItem`，是视频模型在选择器中的展示项。它包了一层通用 `GenerationModelItem`，固定传入 `priceKind="video"` 和 `showPrice={true}`，说明视频模型列表会展示视频价格信息。

`ConfigPanel/components/ModelSelect/index.tsx` 是完整的视频模型选择器。它从 `useAiInfraStore(aiProviderSelectors.enabledVideoModelList)` 读取已启用的视频模型供应商列表，从 `useVideoStore` 读取当前 `model/provider`，选择后调用 `setModelAndProviderOnSelect(model, provider)`。如果没有 provider 或某 provider 没有模型，它会给出跳转到 `/settings/provider/...` 的选项。这个组件虽然没有从 `ConfigPanel/index.ts` 统一导出，但属于同一配置面板能力。

`PromptInput/`

`PromptInput/index.tsx` 是视频生成输入区的主组件，文件较重，是本目录最值得先读的实现。

它主要依赖：

- `useVideoGenerationConfigParam`：按参数名读写视频生成配置，例如 `prompt`、`imageUrl`、`imageUrls`、`endImageUrl`、`duration` 等。
- `useVideoStore`：读取 `isCreating`、`isInit`、当前模型、当前 provider，并调用 `createVideo`、`setModelAndProviderOnSelect`。
- `videoGenerationConfigSelectors.isSupportedParam`：判断当前模型/配置是否支持某个参数，决定控件是否显示。
- `useAiInfraStore(aiProviderSelectors.enabledVideoModelList)`：用于处理 URL query 中传入的 `model`。
- `useUserStore(authSelectors.isLogin)`：生成前做登录检查。
- `useFetchAiVideoConfig()`：拉取视频生成配置能力，根据当前上下文推断，它会影响支持参数、枚举值、上下限等。

内部拆了多个小控件：

- `AspectRatioItem`：渲染比例选择，复用 image 配置里的 `AspectRatioSelect`。
- `SizeItem`：渲染 size 选择。
- `ResolutionItem`：渲染分辨率 `Segmented`。
- `DurationItem`：如果有枚举值就用 `Segmented`，否则用 `SliderWithInput`。
- `SeedItem`：用 `InputNumber` 输入 seed，并提供随机 seed 按钮。
- `SwitchItem`：用于 `cameraFixed`、`generateAudio`、`watermark`、`webSearch` 这类布尔参数。
- `PromptExtendItem`：如果 `promptExtend` 有枚举值则用 `Segmented`，否则用 `Switch`。

`PromptInput` 还处理两个 query 参数：

- `model`：页面初始化完成后，在启用的视频模型列表中查找对应模型，找到后设置 `model/provider`，随后清掉 query。
- `prompt`：登录状态下自动写入提示词，并在短暂延迟后自动调用 `createVideo()`，随后清掉 query。

生成按钮逻辑也在这里：如果未登录，调用 `loginRequired.redirect({ timeout: 2000 })`；如果已登录，则调用 `createVideo()`。

`GenerationFeed/`

`GenerationFeed/index.tsx` 是视频生成结果流入口。它从 `useVideoStore(generationBatchSelectors.currentGenerationBatches)` 读取当前主题下的生成批次，然后把数据传给通用的 `src/routes/(main)/(create)/features/GenerationFeed`，并通过 `renderBatchItem` 指定每个 batch 用 `VideoGenerationBatchItem` 渲染。

`BatchItem.tsx` 是单个视频生成批次的核心渲染组件。它读取 batch 中的第一个 generation：

```ts
const generation = batch.generations[0];
```

因此当前 UI 逻辑主要按“一个 batch 对应一个视频结果”处理。它根据 `generation.task.status` 分为三类：

- `AsyncTaskStatus.Success` 且有 `asset.url`：渲染 `VideoSuccessItem`。
- `AsyncTaskStatus.Error`：渲染 `VideoErrorItem`。
- 其他状态：渲染 `VideoLoadingItem`。

它还做了几类操作：

- `useCheckGenerationStatus(...)`：当任务未结束时轮询或检查生成状态。
- `handleDelete`：删除单个 generation。
- `handleDeleteBatch`：删除整个 batch。
- `handleCopyPrompt`：复制 prompt。
- `handleReuseSettings`：把 batch 的 `model/provider/config` 写回当前输入区。
- `handleDownload`：下载生成的视频文件，文件名由 prompt 前缀和创建时间组成。
- `handleCopyError`：复制错误信息。

特殊分支包括：

- `useRenderBusinessVideoBatchItem(batch)`：业务侧可以接管某些 batch 的渲染。
- `AsyncTaskErrorType.InvalidProviderAPIKey`：渲染 `GenerationInvalidAPIKey`，提示供应商 API key 无效。
- `ProviderContentModeration`：失败项中显示内容审核相关翻译。

`VideoSuccessItem.tsx` 渲染成功视频。它把 `generation.asset` 当作 `VideoGenerationAsset`，用原生 `<video controls loop playsInline>` 展示视频，并使用 `coverUrl` 或 `thumbnailUrl` 作为 poster。操作按钮复用 image 生成页的 `ActionButtons`，支持下载和删除。

`VideoLoadingItem.tsx` 渲染生成中状态。它根据 `avgLatencyMs` 估算进度，默认平均耗时是 `180_000ms`。进度起点存在 `sessionStorage`，key 形如 `generation_start_time_${generationId}`。进度最多显示到 99%，到 99% 后额外显示 `ElapsedTime`。注意这个进度是前端估算，不代表后端真实任务进度。

`VideoErrorItem.tsx` 渲染失败状态。它会尝试把 runtime error type 翻译为用户可读文案；如果不是内容审核错误，则显示最多两行的错误详情。点击失败块会触发复制错误信息。

`VideoReferenceFrames.tsx` 根据文件名和调用方式可知用于展示 batch 配置里的 `imageUrl`、`imageUrls`、`endImageUrl` 等参考帧。当前片段中 `BatchItem` 会在 batch 有参考图时把这些参数传给它。

`VideoWorkspace/`

`VideoWorkspace/index.tsx` 是视频工作区适配器。它没有自己实现布局，而是把视频域组件和 store selector 注入通用 `GenerationWorkspace`：

- `GenerationFeed={GenerationFeed}`
- `PromptInput={PromptInput}`
- `SkeletonList={SkeletonList}`
- `useStore={useVideoStore}`
- selectors：
  - `activeGenerationTopicId`
  - `currentGenerationBatches`
  - `isCurrentGenerationTopicLoaded`

它接受 `embedInput?: boolean`，默认 `true`，用于控制输入框是否嵌入工作区。页面入口 `video/index.tsx` 把它作为 `Workspace` 传给 `CreateGenerationPage`。

`VideoWorkspace/SkeletonList.tsx` 和 `ConfigPanel/VideoConfigSkeleton.tsx` 从命名看是加载占位组件。根据当前片段推断，前者用于工作区生成列表未加载时的骨架屏，后者用于视频配置能力或模型配置未就绪时的配置区骨架。

`PromptInput/Title.tsx`

这是提示词输入区标题组件。它被 `PromptInput` 通过 `showTitle` 控制是否展示，通常用于不同布局下决定输入区是否需要单独标题。

## 上下游关系

上游调用方主要是同级视频路由：

- `src/routes/(main)/(create)/video/index.tsx`
  - 引入 `PromptInput`
  - 引入 `VideoWorkspace`
  - 渲染 `<CreateGenerationPage PromptInput={PromptInput} Workspace={VideoWorkspace} path="/video" />`

- `src/routes/(main)/(create)/video/_layout/index.tsx`
  - 使用通用 `GenerationLayout`
  - 传入 `useVideoStore`
  - 传入 `generationTopicSelectors.generationTopics`
  - 设置 `namespace="video"`、`navKey="video"`、`viewModeStatusKey="videoTopicViewMode"`
  - 面包屑指向 `/video`

这说明 `/video` 页不是孤立页面，而是挂在 create 生成体系下的一个具体生成类型。

横向复用关系很明显：

- 复用 `src/routes/(main)/(create)/features/CreateGenerationPage`
- 复用 `src/routes/(main)/(create)/features/GenerationLayout`
- 复用 `src/routes/(main)/(create)/features/GenerationWorkspace`
- 复用 `src/routes/(main)/(create)/features/GenerationFeed`
- 复用 `src/routes/(main)/(create)/features/GenerationInput`
- 复用 image 创建页的 `ImageUpload`、`AspectRatioSelect`、`ActionButtons`、部分样式和 `ElapsedTime`

下游状态和服务主要来自：

- `@/store/video`
  - `useVideoStore`
  - `createVideo`
  - `removeGeneration`
  - `removeGenerationBatch`
  - `useCheckGenerationStatus`
  - `setModelAndProviderOnSelect`
  - `setParamOnInput`

- `@/store/video/selectors`
  - `createVideoSelectors`
  - `generationBatchSelectors`
  - `videoGenerationConfigSelectors`
  - `videoGenerationTopicSelectors`

- `@/store/video/slices/generationConfig/hooks`
  - `useVideoGenerationConfigParam`

- `@/store/aiInfra`
  - 视频模型列表和 provider 列表

- `@/store/user`
  - 登录态判断

- `@/types/generation`
  - `GenerationBatch`
  - `Generation`
  - `VideoGenerationAsset`

- `@/types/asyncTask`
  - `AsyncTaskStatus`
  - `AsyncTaskErrorType`

## 运行/调用流程

1. 用户进入 `/video`。

2. 路由层加载 `src/routes/(main)/(create)/video/_layout/index.tsx`，渲染通用 `GenerationLayout`。这个 layout 接入 `useVideoStore` 和视频 topic selector，因此侧边栏/历史主题等能力走视频域状态。

3. 页面入口 `src/routes/(main)/(create)/video/index.tsx` 渲染 `CreateGenerationPage`，并把本目录的 `PromptInput` 与 `VideoWorkspace` 注入进去。

4. `PromptInput` 初始化时调用 `useFetchAiVideoConfig()`，读取当前视频生成配置能力。各配置控件通过 `useVideoGenerationConfigParam(paramName)` 绑定具体参数。

5. 如果 URL 上带 `model` query，`PromptInput` 会在 `enabledVideoModelList` 中查找该模型，找到后调用 `setModelAndProviderOnSelect` 设置当前模型和 provider，并清掉 query。

6. 如果 URL 上带 `prompt` query 且用户已登录，`PromptInput` 会写入 prompt，清掉 query，并在约 100ms 后自动调用 `createVideo()`。

7. 用户手动点击生成时，`PromptInput` 先判断登录态。未登录则触发登录提示；已登录则调用 `createVideo()`。

8. `createVideo()` 会通过 `useVideoStore` 创建视频生成任务，并把任务加入当前 topic 的 generation batch。具体后端调用不在本目录中，但本目录负责消费结果。

9. `VideoWorkspace` 把视频 store 和 selectors 传入通用 `GenerationWorkspace`，通用工作区读取当前 topic、加载状态和 batch 列表。

10. `GenerationFeed/index.tsx` 读取 `currentGenerationBatches`，交给通用 `GenerationFeed` 排版，每个 batch 使用 `VideoGenerationBatchItem` 渲染。

11. `VideoGenerationBatchItem` 对未完成任务调用 `useCheckGenerationStatus` 检查状态。根据状态渲染：
    - 加载中：`VideoLoadingItem`
    - 成功：`VideoSuccessItem`
    - 失败：`VideoErrorItem`
    - API key 错误：`GenerationInvalidAPIKey`
    - 业务自定义 batch：`useRenderBusinessVideoBatchItem` 返回的业务组件

12. 用户可以在结果项上执行复用参数、复制 prompt、下载视频、删除 generation 或删除 batch 等操作。这些操作最终回写 `useVideoStore` 或调用浏览器能力，例如 clipboard、download。

## 小白阅读顺序

1. 先读 `src/routes/(main)/(create)/video/index.tsx`  
   这里最短，能看到 `/video` 页面实际只是在 `CreateGenerationPage` 中注入 `PromptInput` 和 `VideoWorkspace`。

2. 再读 `src/routes/(main)/(create)/video/_layout/index.tsx`  
   这里能理解视频页如何接入通用生成布局、视频 topic 和导航 key。

3. 读 `VideoWorkspace/index.tsx`  
   这是理解“视频页如何复用通用工作区”的入口。重点看它传给 `GenerationWorkspace` 的 `GenerationFeed`、`PromptInput`、`SkeletonList`、`useStore` 和 selectors。

4. 读 `PromptInput/index.tsx`  
   这是视频生成输入区的主逻辑。建议先抓住三条线：参数读写 `useVideoGenerationConfigParam`、生成动作 `createVideo`、模型/provider 选择 `setModelAndProviderOnSelect`。

5. 读 `GenerationFeed/index.tsx`  
   这个文件很薄，目的是把当前 batch 列表转成通用 feed 需要的格式。

6. 读 `GenerationFeed/BatchItem.tsx`  
   这是结果项核心。重点看任务状态如何分流到 `VideoSuccessItem`、`VideoLoadingItem`、`VideoErrorItem`，以及复用参数、下载、删除这些操作如何回到 store。

7. 最后读 `ConfigPanel/components`  
   这里是配置控件细节，适合在理解主流程后再看。`FrameUpload`、`ModelSelect`、`VideoModelItem` 都是相对独立的小组件。

## 常见误区

1. 误以为这个 `features` 是全局 `src/features`  
   这里的路径是 `src/routes/(main)/(create)/video/features`，属于路由目录内部的局部 feature。按照仓库新的 `spa-routes` 约定，复杂业务逻辑更推荐沉到 `src/features/<Domain>`，但当前目录是已有 create/video 路由下的实现形态。阅读时要把它理解为“视频路由私有 UI 组件”，不是全局复用 feature。

2. 误以为所有配置项都会固定显示  
   `PromptInput` 会用 `videoGenerationConfigSelectors.isSupportedParam` 判断当前模型是否支持某参数。比如 `imageUrl`、`imageUrls`、`endImageUrl`、`aspectRatio`、`resolution`、`duration`、`seed`、`generateAudio`、`watermark` 等都可能因模型能力不同而显示或隐藏。

3. 误以为加载进度是真实后端进度  
   `VideoLoadingItem` 的百分比是前端基于 `avgLatencyMs` 和开始时间估算出来的，最多到 99%。它主要用于用户体验，不代表后端返回了精确进度。

4. 误以为一个 batch 会展示多个视频  
   `BatchItem.tsx` 当前直接取 `batch.generations[0]`。所以从这个片段看，视频 batch 的 UI 按单个 generation 展示。若未来支持批量视频，需要特别检查这里的假设。

5. 误把删除 generation 和删除 batch 混为一谈  
   `handleDelete` 调用 `removeGeneration(generation.id)`，删除的是单个生成结果；`handleDeleteBatch` 调用 `removeGenerationBatch(batch.id, activeTopicId)`，删除的是整个 batch。两者影响范围不同。

6. 误以为 `prompt` query 只会填充输入框  
   如果 URL 中有 `prompt` 且用户已登录，`PromptInput` 不只会填充 prompt，还会自动调用 `createVideo()` 发起生成。这个行为对外部跳转或分享链接很重要。

7. 误以为视频模型选择只存 model id  
   选择模型时需要同时确定 `model` 和 `provider`。代码中选项值形如 `${provider.id}/${model.id}`，最终会拆成 model 和 provider，再调用 `setModelAndProviderOnSelect` 写入 store。

8. 误以为视频页完全独立于 image 页  
   视频页复用了不少 image 生成页组件，例如 `ImageUpload`、`AspectRatioSelect`、`ActionButtons`、`ElapsedTime` 和部分样式。修改这些共享组件时，可能同时影响 image 和 video 两条生成链路。
