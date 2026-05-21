# 目录：src/routes/(main)/(create)/video

## 它负责什么

`src/routes/(main)/(create)/video` 是桌面端 SPA 里的“视频生成”页面路由目录，对应应用中的 `/video` 创作入口。它负责把视频生成页面接入通用的创作页框架，并提供视频专属的输入区、工作区、生成结果流、加载态、错误态和配置项。

从代码结构看，这个目录既包含路由入口文件，也包含页面内部的业务组件：

- `index.tsx`：`/video` 页面的主入口。
- `_layout/index.tsx`：`/video` 路由布局入口，挂载通用生成布局和话题列表。
- `loading.tsx`：页面加载时的品牌加载态。
- `features/`：视频生成页内部功能组件，包括 `PromptInput`、`VideoWorkspace`、`GenerationFeed`、`ConfigPanel` 等。

按照当前仓库的 `spa-routes` 约定，`src/routes` 理想上应只放薄路由入口，复杂 UI 应迁移到 `src/features`。但这个目录目前仍在路由目录下保留了 `features` 子目录，说明它属于尚未完全迁移的历史/渐进式结构。

## 关键组成

### `index.tsx`

`index.tsx` 定义并导出 `DesktopVideoPage`：

```tsx
<CreateGenerationPage PromptInput={PromptInput} Workspace={VideoWorkspace} path="/video" />
```

它本身非常薄，只做三件事：

1. 引入通用创作页容器 `CreateGenerationPage`。
2. 引入视频页自己的 `PromptInput` 和 `VideoWorkspace`。
3. 把 `path="/video"` 传给通用容器，用于判断当前路由是否匹配。

也就是说，`index.tsx` 不直接处理生成逻辑，它只是把“视频输入组件”和“视频工作区组件”插入到通用创作页模板中。

### `_layout/index.tsx`

`_layout/index.tsx` 定义 `VideoLayout`，它复用通用的 `GenerationLayout`：

```tsx
<GenerationLayout
  breadcrumb={[{ href: '/video', title: t('tab.video') }]}
  generationTopicsSelector={generationTopicSelectors.generationTopics}
  namespace="video"
  navKey="video"
  useStore={useVideoStore}
  viewModeStatusKey="videoTopicViewMode"
/>
```

这个布局主要负责视频生成页的外层结构，例如：

- 面包屑：`/video`，显示文案来自 `common` 命名空间的 `tab.video`。
- 当前模块标识：`namespace="video"`、`navKey="video"`。
- 话题数据来源：`useVideoStore`。
- 话题列表选择器：`generationTopicSelectors.generationTopics`。
- 视图模式状态键：`videoTopicViewMode`。

可以把它理解为“视频生成页的话题壳”：页面主体由子路由或页面组件渲染，布局层负责接入生成话题导航、面包屑和通用外框。

### `loading.tsx`

`loading.tsx` 很简单：

```tsx
const VideoLoading = () => <Loading debugId="Video Page" />;
```

它使用 `@/components/Loading/BrandTextLoading`，在视频页异步加载期间显示统一品牌加载态。`debugId="Video Page"` 方便定位是哪一个页面在加载。

### `features/PromptInput`

`PromptInput` 是这个目录中最核心的交互组件，负责视频生成输入框和配置入口。它依赖大量 store selector 和生成配置 hook：

- `useVideoStore`
- `createVideoSelectors.isCreating`
- `videoGenerationConfigSelectors`
- `useVideoGenerationConfigParam`
- `useAiInfraStore(aiProviderSelectors.enabledVideoModelList)`
- `useUserStore(authSelectors.isLogin)`
- `useFetchAiVideoConfig`

它主要做以下事情：

1. 读取和修改视频生成参数，例如：
   - `prompt`
   - `imageUrl`
   - `imageUrls`
   - `endImageUrl`
   - `aspectRatio`
   - `resolution`
   - `size`
   - `duration`
   - `seed`
   - `generateAudio`
   - `promptExtend`
   - `watermark`
   - `cameraFixed`
   - `webSearch`

2. 根据当前模型能力动态显示配置项。  
   例如 `isSupportedParam('imageUrl')` 为真时才显示参考图上传；`isSupportedParam('duration')` 为真时才显示时长配置。

3. 处理登录状态。  
   点击生成时，如果用户未登录，会调用：

   ```ts
   loginRequired.redirect({ timeout: 2000 });
   ```

   已登录则执行：

   ```ts
   await createVideo();
   ```

4. 处理 URL query 参数。  
   它会读取：
   - `prompt`
   - `model`

   如果 URL 中带了 `model`，并且模型列表已初始化，就尝试在 `enabledVideoModelList` 中找到对应模型，并调用 `setModelAndProviderOnSelect` 设置当前模型和 provider。

   如果 URL 中带了 `prompt`，且用户已登录，则会自动填入 prompt，并在短暂延迟后自动调用 `createVideo()`。这说明 `/video?prompt=...` 可以作为一种“带提示词直达生成”的入口。

5. 管理参考帧。  
   组件支持单图、多图和尾帧：
   - `imageUrl`
   - `imageUrls`
   - `endImageUrl`

   它通过 `InlineVideoFrames` 展示和编辑这些参考图片，并根据模型能力决定最多可添加多少张。

6. 组合输入框左右操作区。  
   `GenerationPromptInput` 的左侧操作包括：
   - `GenerationMediaModeSegment mode="video"`
   - `ModelSwitchPanel`
   - `ConfigAction`
   - duration 快捷配置按钮

   右侧操作是：
   - `PromptTransformAction mode="video"`

### `features/VideoWorkspace`

`VideoWorkspace` 是视频页的工作区适配层，它复用通用 `GenerationWorkspace`：

```tsx
<GenerationWorkspace
  GenerationFeed={GenerationFeed}
  PromptInput={PromptInput}
  SkeletonList={SkeletonList}
  embedInput={embedInput}
  useStore={useVideoStore}
  selectors={{
    activeGenerationTopicId: videoGenerationTopicSelectors.activeGenerationTopicId,
    currentGenerationBatches: generationBatchSelectors.currentGenerationBatches,
    isCurrentGenerationTopicLoaded: generationBatchSelectors.isCurrentGenerationTopicLoaded,
  }}
/>
```

它不直接渲染列表，而是把视频页需要的组件和 selector 注入通用工作区：

- `GenerationFeed`：视频生成结果流。
- `PromptInput`：底部或空状态里的输入框。
- `SkeletonList`：加载骨架。
- `useVideoStore`：视频生成状态源。
- `selectors`：当前话题、当前批次、当前话题是否加载完成。

### `features/GenerationFeed`

`GenerationFeed/index.tsx` 也是一层适配：

```tsx
<GenerationFeed
  batches={currentGenerationBatches ?? []}
  renderBatchItem={(batch) => <VideoGenerationBatchItem batch={batch} key={batch.id} />}
/>
```

它从 `useVideoStore(generationBatchSelectors.currentGenerationBatches)` 读取当前话题下的生成批次，然后交给通用 `GenerationFeed` 展示。每个 batch 的具体渲染由 `VideoGenerationBatchItem` 完成。

### `features/GenerationFeed/BatchItem.tsx`

`VideoGenerationBatchItem` 是单个视频生成批次的核心展示组件。它负责：

- 显示 prompt。
- 显示参考帧。
- 根据任务状态渲染成功、失败或加载中。
- 轮询生成状态。
- 删除单个 generation。
- 删除整个 batch。
- 复制 prompt。
- 复用当前生成设置。
- 下载生成后的视频。
- 处理无效 API Key 错误。
- 委托业务侧自定义渲染。

关键状态判断是：

```ts
generation.task.status === AsyncTaskStatus.Success
generation.task.status === AsyncTaskStatus.Error
```

如果状态是成功且有 `generation.asset.url`，渲染 `VideoSuccessItem`。  
如果状态是错误，渲染 `VideoErrorItem`。  
否则渲染 `VideoLoadingItem`。

它还调用：

```ts
useCheckGenerationStatus(
  generation?.id ?? '',
  generation?.task.id ?? '',
  activeTopicId!,
  !isFinalized,
);
```

这说明只要任务没有进入成功或错误终态，组件就会继续检查生成状态。根据当前片段推断，`useCheckGenerationStatus` 应该是 `useVideoStore` 中封装的异步任务状态轮询逻辑。

### `VideoSuccessItem`

`VideoSuccessItem` 负责成功结果展示：

```tsx
<video
  controls
  loop
  playsInline
  poster={asset.coverUrl || asset.thumbnailUrl}
  src={asset.url}
/>
```

它把生成资产当作 `VideoGenerationAsset` 使用，展示 HTML 原生 `<video>` 播放器，并复用图片生成结果里的 `ActionButtons` 来提供下载和删除按钮。

### `VideoLoadingItem`

`VideoLoadingItem` 负责生成中的占位展示。它会根据 `avgLatencyMs` 估算进度，默认平均耗时是：

```ts
const DEFAULT_AVG_LATENCY_MS = 180_000;
```

也就是 180 秒。

它用 `sessionStorage` 记录每个 `generationId` 的开始时间：

```ts
generation_start_time_${generationId}
```

然后每秒更新一次进度，最高显示到 99%。如果进度达到 99%，显示 `ElapsedTime`，避免用户误以为任务卡死。

### `VideoErrorItem`

`VideoErrorItem` 负责失败结果展示。它会尝试把错误映射成用户可读文案：

- 如果错误 body 是 `AgentRuntimeErrorType` 中的已知类型，优先使用 `error` 命名空间翻译。
- 如果是内容审核错误 `ProviderContentModeration`，显示对应翻译。
- 否则显示错误 body、错误 name 或 `Unknown error`。

点击错误块会触发复制错误信息，便于用户或开发者排查。

### `features/ConfigPanel`

当前 `ConfigPanel/index.ts` 只导出两个组件：

```ts
export { default as FrameUpload } from './components/FrameUpload';
export { default as VideoModelItem } from './components/ModelSelect/VideoModelItem';
```

在当前读取到的代码中，`PromptInput` 直接使用了：

```ts
VideoModelItem
```

用于模型切换面板中的视频模型条目展示。`FrameUpload` 没有在当前片段里看到直接调用，根据当前片段推断，它可能供其他视频配置入口或后续迁移代码复用。

## 上下游关系

### 路由上游

视频页由桌面路由配置挂载。

在 `src/spa/router/desktopRouter.config.tsx` 中，视频页通过动态导入注册：

```ts
() => import('@/routes/(main)/(create)/video')
() => import('@/routes/(main)/(create)/video/_layout')
path: 'video'
```

在 `src/spa/router/desktopRouter.config.desktop.tsx` 中，视频页通过静态 import 注册：

```ts
import VideoPage from '@/routes/(main)/(create)/video';
import DesktopVideoLayout from '@/routes/(main)/(create)/video/_layout';
```

并同样挂到：

```ts
path: 'video'
```

这符合仓库要求：桌面路由树需要在两个 config 中保持同步。否则 Web/Electron 或不同构建路径可能出现路由缺失、空白页等问题。

### 页面容器上游

`index.tsx` 依赖通用页面容器：

```ts
@/routes/(main)/(create)/features/CreateGenerationPage
```

`CreateGenerationPage` 根据当前是否匹配 `/video` 来决定是否渲染内容，并根据 query 参数 `topic` 判断显示首页输入区还是话题工作区：

- 没有 `topic`：居中显示 `PromptInput`，相当于视频生成首页。
- 有 `topic`：显示 `Workspace`，并在底部显示输入框。

这意味着 `/video` 和 `/video?topic=xxx` 是同一个页面组件里的两种状态。

### 布局上游

`_layout/index.tsx` 依赖：

```ts
@/routes/(main)/(create)/features/GenerationLayout
```

它把视频 store、视频话题 selector 和路由导航信息传入通用布局。这个布局应当负责左侧话题、导航状态或外层结构，具体细节需要继续阅读 `GenerationLayout` 才能完全确认。

### 数据下游

视频页的状态核心是：

```ts
@/store/video
```

当前目录多处使用：

- `useVideoStore`
- `generationTopicSelectors`
- `generationBatchSelectors`
- `videoGenerationTopicSelectors`
- `videoGenerationConfigSelectors`
- `createVideoSelectors`
- `useVideoGenerationConfigParam`

根据当前片段推断，`useVideoStore` 至少负责：

- 当前视频生成参数。
- 当前模型和 provider。
- 当前生成话题。
- 当前生成 batch 列表。
- 创建视频任务 `createVideo()`。
- 删除 generation 或 batch。
- 检查异步任务状态 `useCheckGenerationStatus()`。
- 复用历史 batch 配置。

### 模型和 provider 下游

视频模型列表来自：

```ts
useAiInfraStore(aiProviderSelectors.enabledVideoModelList)
```

模型切换由 `ModelSwitchPanel` 展示，选中后调用：

```ts
setModelAndProviderOnSelect(model, provider)
```

这说明视频页不自己维护 provider 列表，而是依赖统一的 AI 基础设施 store。

### 业务扩展下游

`BatchItem.tsx` 中调用：

```ts
useRenderBusinessVideoBatchItem(batch)
```

如果业务侧判断需要自定义渲染：

```ts
if (shouldRenderBusinessBatchItem) {
  return businessBatchItem;
}
```

这给商业版、云端特殊任务或特定 provider 留了扩展入口。普通开源逻辑只在没有业务自定义时执行默认渲染。

### 复用图片生成组件

视频页复用了不少图片生成页的组件：

- `AspectRatioSelect`
- `Select`
- `ActionButtons`
- `styles`
- `ElapsedTime`

这说明视频生成和图片生成在 UI 形态上高度相似：都是 prompt 输入、配置参数、异步生成、结果流、下载/删除/复用操作。视频页在复用图片页基础组件的同时，补充了视频特有的播放、进度和参考帧逻辑。

## 运行/调用流程

1. 用户访问 `/video`。

2. SPA router 命中 `path: 'video'`，加载：
   - `src/routes/(main)/(create)/video/_layout`
   - `src/routes/(main)/(create)/video/index.tsx`

3. `_layout/index.tsx` 渲染 `GenerationLayout`。  
   它把 `useVideoStore`、视频话题 selector、面包屑和 nav key 传给通用布局。

4. `index.tsx` 渲染 `CreateGenerationPage`。  
   它注入：
   - `PromptInput`
   - `VideoWorkspace`
   - `path="/video"`

5. `CreateGenerationPage` 判断当前 URL：
   - 如果不是 `/video` 精确匹配，返回 `null`。
   - 如果是 `/video` 且没有 `topic`，显示居中的 `PromptInput`。
   - 如果有 `topic`，显示 `VideoWorkspace`，并在页面底部显示 `PromptInput`。

6. `PromptInput` 初始化视频配置：
   - 调用 `useFetchAiVideoConfig()` 拉取视频模型/参数配置。
   - 从 `useVideoStore` 读取当前 prompt、模型、provider、生成状态。
   - 从 `useAiInfraStore` 读取可用视频模型列表。
   - 根据 `isSupportedParam` 判断哪些参数可展示。

7. 用户输入 prompt、选择模型、上传参考帧、调整配置。

8. 用户点击生成：
   - 未登录：触发 `loginRequired.redirect()`。
   - 已登录：调用 `createVideo()`。

9. 根据当前片段推断，`createVideo()` 会把当前 prompt、模型、provider 和 config 提交到视频生成服务，并创建一个 generation batch。

10. `VideoWorkspace` 读取 `topic`：
    - 没有 topic 或正在创建新 topic：显示 `EmptyState`。
    - 有 topic：渲染通用 `Content`，并把 `GenerationFeed`、`SkeletonList`、`PromptInput` 注入进去。

11. `GenerationFeed` 从 `useVideoStore` 读取 `currentGenerationBatches`，逐个渲染 `VideoGenerationBatchItem`。

12. `VideoGenerationBatchItem` 对每个 batch：
    - 读取第一个 `generation`。
    - 如果任务未完成，调用 `useCheckGenerationStatus()` 继续检查状态。
    - 成功：展示 `<video>` 播放器。
    - 失败：展示错误块。
    - 处理中：展示估算进度。
    - 悬浮时显示复用、复制、删除等操作。

13. 用户可对历史结果执行：
    - 复用设置：把 batch 的模型和 config 写回输入区。
    - 复制 prompt。
    - 删除 batch。
    - 删除单个 generation。
    - 下载生成的视频文件。

## 小白阅读顺序

1. 先读 `src/routes/(main)/(create)/video/index.tsx`。  
   这个文件最短，能快速理解视频页不是从零搭建，而是把 `PromptInput` 和 `VideoWorkspace` 塞进通用 `CreateGenerationPage`。

2. 再读 `src/routes/(main)/(create)/features/CreateGenerationPage.tsx`。  
   重点看它如何根据 `topic` query 参数在“首页输入态”和“话题工作区态”之间切换。

3. 然后读 `src/routes/(main)/(create)/video/_layout/index.tsx`。  
   理解视频页如何接入 `GenerationLayout`、`useVideoStore` 和视频话题列表。

4. 接着读 `src/routes/(main)/(create)/video/features/PromptInput/index.tsx`。  
   这是交互最复杂的文件。建议分块看：
   - 参数读取：`useVideoGenerationConfigParam`
   - 模型切换：`ModelSwitchPanel`
   - 登录与生成：`handleGenerate`
   - query 参数自动填充：两个 `useEffect`
   - 参考帧处理：`handleAddImage`、`handleRemoveImage`、`handleEndImageChange`
   - 配置面板：`ConfigAction`

5. 再读 `src/routes/(main)/(create)/video/features/VideoWorkspace/index.tsx`。  
   理解它只是把视频 store、selector 和结果流组件注入通用 `GenerationWorkspace`。

6. 然后读 `src/routes/(main)/(create)/video/features/GenerationFeed/index.tsx` 和 `BatchItem.tsx`。  
   这里能看到生成结果从 batch 到单个结果项的渲染方式。

7. 最后读三个状态组件：
   - `VideoSuccessItem.tsx`
   - `VideoLoadingItem.tsx`
   - `VideoErrorItem.tsx`

   它们分别对应成功、生成中、失败，是理解结果 UI 的最佳切入点。

8. 如果还想继续深入，再去看 `@/store/video`。  
   当前目录只是调用 store，真正的任务创建、状态轮询、数据更新逻辑应该在 video store 及其 slices 中。

## 常见误区

1. 不要把 `src/routes/(main)/(create)/video/features` 理解成推荐的新结构。  
   按仓库当前规范，`src/routes` 应尽量保持薄路由，复杂业务组件更适合放到 `src/features`。这里保留 `features` 子目录，更像是历史结构或渐进迁移中的状态。

2. 不要以为 `index.tsx` 里有视频生成核心逻辑。  
   `index.tsx` 只是页面装配层。真正的输入、配置、生成触发在 `PromptInput`，结果展示在 `VideoWorkspace` 和 `GenerationFeed`，状态管理在 `useVideoStore`。

3. 不要忽略 `_layout/index.tsx`。  
   视频页不只是一个单页组件，它还依赖 `GenerationLayout` 接入话题列表、面包屑和模块导航。只看 `index.tsx` 会漏掉页面外壳。

4. 不要把 `/video` 和 `/video?topic=xxx` 当成两个完全不同路由。  
   它们由同一个 `CreateGenerationPage` 处理，只是根据 `topic` query 参数切换 UI 状态。

5. 不要认为所有配置项都会一直显示。  
   `PromptInput` 会通过 `videoGenerationConfigSelectors.isSupportedParam` 判断当前模型是否支持某个参数。比如参考图、尾帧、时长、分辨率、音频、水印、固定镜头等，都可能因模型不同而显示或隐藏。

6. 不要以为进度条是真实后端进度。  
   `VideoLoadingItem` 的进度来自本地估算：根据开始时间和 `avgLatencyMs` 计算，最高到 99%。它更像用户体验层的等待反馈，不等于后端真实生成百分比。

7. 不要漏改双路由配置。  
   视频页在 `desktopRouter.config.tsx` 和 `desktopRouter.config.desktop.tsx` 都有注册。以后如果调整 `/video` 路由结构，这两个文件必须保持一致，否则不同桌面构建路径可能表现不一致。

8. 不要把删除 generation 和删除 batch 混为一谈。  
   `handleDelete` 调用 `removeGeneration(generation.id)`，删除单个生成结果；`handleDeleteBatch` 调用 `removeGenerationBatch(batch.id, activeTopicId)`，删除整个批次记录。

9. 不要忽略业务侧渲染扩展。  
   `useRenderBusinessVideoBatchItem(batch)` 可能让某些 batch 走业务自定义 UI。阅读默认 UI 时要记住：不是所有视频 batch 都一定由 `VideoGenerationBatchItem` 的默认分支渲染。

10. 不要把视频页看成完全独立实现。  
    它大量复用通用创作组件和图片生成组件，例如 `CreateGenerationPage`、`GenerationWorkspace`、`GenerationFeed`、`ActionButtons`、`ElapsedTime`、`AspectRatioSelect`。理解视频页时，最好把它看作“通用生成框架 + 视频 store + 视频专属输入与结果渲染”的组合。
