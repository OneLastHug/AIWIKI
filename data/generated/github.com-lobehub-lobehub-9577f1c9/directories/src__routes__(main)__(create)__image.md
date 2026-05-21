# 目录：src/routes/(main)/(create)/image

## 它负责什么

`src/routes/(main)/(create)/image` 是桌面主应用里“创建/生成”体系下的图像生成页面路由目录，对应 SPA 路径 `/image`。它把通用的生成页面框架和图像生成专属能力组合起来：顶部导航、左侧生成主题列表、主工作区、底部/首页 Prompt 输入框、图像模型选择、图像参数配置、参考图上传、生成结果流展示、批次操作、图像快捷键注册等。

从职责边界看，它不是后端生成服务本身，也不是图像 store 的定义处；它主要是“页面装配 + 图像生成 UI”。真正的数据状态来自 `@/store/image`，通用页面壳来自 `src/routes/(main)/(create)/features/*`，模型列表来自 `@/store/aiInfra`，用户登录态来自 `@/store/user`。

需要注意：按当前 `spa-routes` 规范，`src/routes/` 理想上应只放薄 route segment，业务 UI 应放到 `src/features/`。但这个目录下仍有较多 `features/` 子目录，属于仓库中尚未完全迁移到新结构的历史/渐进式形态。阅读时不要误以为这是新代码应继续复制的最佳组织方式。

## 关键组成

`index.tsx` 是 `/image` 的页面入口。它是一个很薄的组装层，导入通用 `CreateGenerationPage`，再传入图像专属的 `PromptInput`、`ImageWorkspace` 和路径 `path="/image"`。`CreateGenerationPage` 会根据 URL 是否带 `topic` 查询参数决定展示形态：没有 `topic` 时展示居中的首页 Prompt；有 `topic` 时展示工作区，并在底部固定展示 Prompt 输入。

`_layout/index.tsx` 是 `/image` 的 route layout。它导入通用 `GenerationLayout`，并传入图像命名空间相关配置：`namespace="image"`、`navKey="image"`、`viewModeStatusKey="imageTopicViewMode"`、`useStore={useImageStore}`、`generationTopicsSelector={generationTopicSelectors.generationTopics}`。它还通过 `breadcrumb` 设置面包屑为 `tab.image`，并通过 `extra={<RegisterHotkeys />}` 注册图像页面快捷键。

`_layout/RegisterHotkeys.tsx` 很小，只调用 `useRegisterImageHotkeys()`，返回 `null`。它的存在说明快捷键生命周期绑定在 `/image` layout 上，而不是具体某个输入框组件上。

`loading.tsx` 渲染 `@/components/Loading/BrandTextLoading`，`debugId` 为 `"Image Page"`，用于路由懒加载或页面加载期间的占位。

`NotSupportClient.tsx` 是一个不支持当前客户端/部署形态时的引导页组件。它使用 `@lobehub/ui`、`FeatureList`、`react-i18next`、`DATABASE_SELF_HOSTING_URL`、`OFFICIAL_URL` 等展示功能说明和跳转链接。根据当前片段推断，它用于某些图像功能不可用场景，但在本次读取到的路由注册和主页面入口中没有看到直接引用，因此具体挂载点需要再查更上层业务条件或 cloud override。

`features/ImageWorkspace/index.tsx` 是图像工作区适配器。它把通用 `GenerationWorkspace` 和图像 store 绑定起来，传入 `GenerationFeed`、`PromptInput`、`SkeletonList`，以及几个 selector：当前 topic id、当前 generation batches、当前 topic 是否已加载。

`features/PromptInput/index.tsx` 是交互最重的组件。它负责 Prompt 文本、模型切换、参数面板、参考图内联上传、登录校验、URL 参数预填与自动生成。它通过 `useGenerationConfigParam` 读写图像生成配置，例如 `prompt`、`imageUrl`、`imageUrls`、`quality`、`resolution`、`size`、`steps`、`cfg`、`seed`、`watermark`、`promptExtend`、`webSearch`。它通过 `useFetchAiImageConfig()` 拉取图像模型/参数配置，通过 `imageGenerationConfigSelectors.isSupportedParam` 判断当前模型支持哪些配置项，再按支持情况动态显示 UI。

`features/ConfigPanel/index.ts` 是参数控件的导出聚合层，向外暴露 `CfgSliderInput`、`DimensionControlGroup`、`ImageNum`、`QualitySelect`、`ResolutionSelect`、`SeedNumberInput`、`SizeSelect`、`StepsSliderInput`、`ImageUpload`、`useAutoDimensions` 等。`PromptInput` 主要从这里消费图像配置控件。

`features/GenerationFeed/index.tsx` 将 `useImageStore(generationBatchSelectors.currentGenerationBatches)` 取出的当前生成批次传给通用 `GenerationFeed`，并用图像专属的 `GenerationBatchItem` 渲染每个 batch。

`features/GenerationFeed/BatchItem.tsx` 是批次卡片。它展示参考图、Prompt markdown、生成结果网格、模型标签、尺寸、生成数量、创建时间，并提供三个批次级操作：复用设置、复制 Prompt、删除批次。它还会识别 `AsyncTaskErrorType.InvalidProviderAPIKey`，遇到无效 API key 时渲染 `GenerationInvalidAPIKey`。另外它调用 `useRenderBusinessBatchItem(batch)`，说明商业版或业务扩展可以替换默认 batch 渲染。

## 上下游关系

上游路由注册在两个桌面 router 配置中保持同步：

`src/spa/router/desktopRouter.config.tsx` 使用 `dynamicElement(() => import('@/routes/(main)/(create)/image'))` 和 `dynamicLayout(() => import('@/routes/(main)/(create)/image/_layout'))` 注册动态加载版本。

`src/spa/router/desktopRouter.config.desktop.tsx` 使用静态 import：`ImagePage` 和 `DesktopImageLayout`。两者的 route tree 都是 `path: 'image'`，其 index child 渲染图像页面，并设置 `routeMeta({ icon: Image, titleKey: 'navigation.image' })`。

上游导航/模式切换还有 `GenerationMediaModeSegment`。它在图像/视频模式之间跳转：选择 video 时去 `/video`，否则去 `/image`。这说明 `/image` 和 `/video` 是同一创建体系下的平级媒体生成入口。

下游状态主要进入 `@/store/image`。页面从 store 读取初始化状态、当前模型、当前 provider、是否正在创建、当前 topic、当前生成批次，也调用 store action：`createImage()`、`setModelAndProviderOnSelect()`、`removeGenerationBatch()`、`reuseSettings()` 等。

下游配置能力依赖 AI infra 和用户状态。`PromptInput` 从 `@/store/aiInfra` 的 `enabledImageModelList` 获取可用图像模型，从 `@/store/user` 的 `authSelectors.isLogin` 判断是否登录。未登录点击生成会调用 `loginRequired.redirect({ timeout: 2000 })`。

下游 UI 复用大量通用生成组件：`CreateGenerationPage`、`GenerationLayout`、`GenerationWorkspace`、`GenerationFeed`、`GenerationPromptInput`、`GenerationMediaModeSegment`、`ConfigAction`、`InlineImageReference`、`GenerationInvalidAPIKey`。所以图像页面并不是从零实现一套生成界面，而是在通用“create generation”框架上做图像适配。

还有反向复用关系：`video` 目录里的部分组件复用了图像目录下的 `GenerationItem` action/styles、`ElapsedTime`、`AspectRatioSelect`、`ImageUpload` 等。这说明当前图像目录里的某些组件已经成为媒体生成公共能力的事实来源，但路径仍在 `image/features` 下，未来如果继续整理，可能适合迁到更通用的 create features 区域。

## 运行/调用流程

用户访问 `/image` 后，React Router 命中 `path: 'image'`。外层先加载 `_layout/index.tsx`，渲染 `GenerationLayout`。这个 layout 会显示生成主题侧边栏，并通过 `<Outlet />` 放置 index 页面内容，同时注册图像快捷键。

index 页面渲染 `DesktopImagePage`，它调用 `CreateGenerationPage`。`CreateGenerationPage` 先用 `useMatch({ path: '/image', end: true })` 确认当前就是 `/image`，再读取 URL query 中的 `topic`。没有 `topic` 时，它认为是首页状态，在中间显示 `PromptInput showTitle`；有 `topic` 时，它渲染 `ImageWorkspace embedInput={false}`，并在页面底部另放一个 `PromptInput`。

`PromptInput` 初始化时会拉取图像 AI 配置，读取当前模型支持的参数。它还处理两个 URL 参数：`model` 和 `prompt`。如果 URL 带 `model`，等 `isInit` 后会在 `enabledImageModelList` 中寻找对应模型并切换 provider/model，然后清掉 query。若 URL 带 `prompt` 且用户已登录，会写入 prompt，清掉 query，并延迟约 100ms 调用 `createImage()`，实现“带 prompt 链接直接生成”。

用户点击生成时，`handleGenerate` 先检查登录态。未登录则跳转登录提示；已登录则调用 `useImageStore` 里的 `createImage()`。根据当前片段推断，生成任务创建、异步任务轮询、结果入库/入 store 等逻辑不在本目录，而在 `@/store/image`、services、server/router 等下游模块中。

有 topic 的工作区由 `ImageWorkspace` 接管。它把当前 topic、批次、加载状态 selector 交给通用 `GenerationWorkspace`。如果没有 topic 或正在创建新 topic，则展示 empty state；否则展示 `Content`，其中 `GenerationFeed` 会读取当前批次并逐个渲染 `GenerationBatchItem`。

结果展示时，一个 batch 先显示参考图与 prompt，再把 `batch.generations` 渲染为图片网格。每个批次可复用配置，复用时会调用 `reuseSettings(batch.model, batch.provider, omit(batch.config, ['seed']))`，刻意不复用 `seed`；也可以复制 prompt 或删除 batch。若任一 generation 的错误是 `InvalidProviderAPIKey`，则展示 API key 错误引导组件。

## 小白阅读顺序

1. 先看 `src/spa/router/desktopRouter.config.tsx` 和 `src/spa/router/desktopRouter.config.desktop.tsx` 中的 `Image routes`，确认 `/image` 如何被注册，以及为什么动态/静态两个 router 都要有同样的 route tree。

2. 再看 `src/routes/(main)/(create)/image/_layout/index.tsx`，理解图像页面如何接入通用 `GenerationLayout`、图像 store、topic selector、面包屑和快捷键。

3. 接着看 `src/routes/(main)/(create)/image/index.tsx`，它只有几行，但能说明页面主装配方式：`CreateGenerationPage + PromptInput + ImageWorkspace`。

4. 然后读通用壳 `src/routes/(main)/(create)/features/CreateGenerationPage.tsx`。这里能看懂为什么无 `topic` 是首页输入态，有 `topic` 是工作区态，以及底部输入框如何出现。

5. 继续看 `features/PromptInput/index.tsx`。这是理解图像生成交互的核心：模型选择、参数显示、参考图、URL 参数、登录校验、触发 `createImage()` 都在这里。

6. 再看 `features/ImageWorkspace/index.tsx` 和通用 `GenerationWorkspace`，理解生成结果区域如何根据 topic 和 loading 状态切换。

7. 最后看 `features/GenerationFeed/index.tsx` 与 `features/GenerationFeed/BatchItem.tsx`，理解生成完成后如何展示批次、图片、错误态和操作按钮。

## 常见误区

`src/routes/(main)/(create)/image/features` 不代表新代码也应该继续把复杂业务组件放在 `src/routes` 下。仓库当前规范是 route 薄、feature 厚；这个目录属于已有实现或渐进迁移阶段，新增大块业务 UI 时应优先考虑 `src/features/<Domain>/` 或通用 create features。

`/image` 页面本身不等于图像生成后端。它只是 UI 和 store action 的入口。真正创建任务、调用模型、处理异步结果的逻辑需要继续追 `@/store/image`、相关 services、server routers。

`PromptInput` 里不是所有配置项都会固定显示。它先用 `isSupportedParam` 判断当前模型是否支持某个参数，再决定显示 `quality`、`resolution`、`size`、`steps`、`cfg`、`seed`、`watermark`、`promptExtend`、`webSearch`、参考图等控件。因此换模型后配置面板变化是预期行为。

`imageUrl` 和 `imageUrls` 不是重复字段。当前代码把单图参考和多图参考都纳入 `InlineImageReference`，添加图片时会优先填充 `imageUrl`，再按模型能力追加到 `imageUrls`。同时 `useAutoDimensions` 会尝试从参考图尺寸中自动设置生成尺寸。

`topic` query 很关键。没有 `topic` 时页面看起来像只有一个输入框；带 `topic` 时才进入生成历史/结果工作区。这不是两个路由，而是同一个 `/image` 根据 query 切换状态。

`reuseSettings` 会排除 `seed`。这意味着“复用设置”不是完全复制上一次生成参数，而是复制模型、provider 和大部分配置，但避免沿用随机种子导致行为过于固定。

`NotSupportClient.tsx` 不应直接理解成 `/image` 默认入口。当前读取到的主入口和 router 没有直接引用它；根据当前片段推断，它是某些环境或业务条件下的不支持提示组件，具体触发点需要继续查找调用方或业务覆盖层。
