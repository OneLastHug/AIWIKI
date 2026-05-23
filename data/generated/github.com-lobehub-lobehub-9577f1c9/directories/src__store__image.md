# 目录：src/store/image

## 它负责什么

`src/store/image` 是图片生成能力在前端侧的 Zustand 状态中心。它不直接渲染页面，也不是后端生成服务本身，而是把“图片生成界面需要的状态与动作”集中到一个 store：生成参数、当前会话主题、各主题下的生成批次、创建/重生成图片的流程状态，以及尺寸比例等辅助计算。

从 `src/store/image/store.ts` 可以看到，这个 store 暴露的核心是 `useImageStore` 和 `getImageStoreState`。它通过 `createWithEqualityFn` 创建 Zustand hook，通过 `subscribeWithSelector` 支持选择器订阅，通过 `createDevtools('image')` 接入调试工具，并用 `expose('image', useImageStore)` 暴露调试入口。整体结构符合 LobeHub store 的常见模式：`initialState` 聚合状态，多个 slice 聚合 action，`selectors.ts` 统一导出读取逻辑。

这个目录的业务边界可以概括为：前端图片生成工作台的状态编排层。真正的网络请求会下沉到 `@/services/image`、`@/services/generationTopic`、`@/services/generationBatch`、`@/services/generation`、`@/services/chat` 等服务；模型、用户设置和供应商能力则从 `@/store/aiInfra`、`@/store/user`、`@/store/global` 等邻近 store 读取。

## 直接子目录地图

`src/store/image/slices` 是主要业务分区，按图片生成流程拆成四块：

`src/store/image/slices/generationConfig` 管理图片生成配置。这里处理 provider、model、参数 schema、默认值、输入参数、尺寸、宽高比例锁定等状态。它会读取模型参数定义，并借助 `src/store/image/utils/aspectRatio.ts`、`src/store/image/utils/size.ts` 做比例与尺寸适配。

`src/store/image/slices/generationTopic` 管理图片生成主题。主题可以理解为图片生成历史的会话分组。它负责创建主题、切换主题、删除主题、刷新主题列表，以及根据 prompt 调用聊天服务自动总结标题。

`src/store/image/slices/generationBatch` 管理某个主题下的生成批次。一个批次通常对应一次生成请求产生的一组图片。它负责拉取批次、删除单张 generation、删除整个 batch、轮询异步生成状态，并把结果写回 `generationBatchesMap`。

`src/store/image/slices/createImage` 是创建图片的流程编排层。它从配置 slice 读取参数，从主题 slice 获取当前主题，从批次 slice 刷新结果，然后调用 `imageService.createImage` 发起生成。

`src/store/image/utils` 是轻量工具区，目前主要围绕图片尺寸和宽高比：`aspectRatio.ts`、`size.ts` 以及对应测试文件。它不是状态层，而是给 `generationConfig` 提供可测试的纯计算能力。

## 关键入口

最重要的入口是 `src/store/image/index.ts`。外部模块通常从这里导入 `useImageStore`、`getImageStoreState` 或 `ImageStore` 类型，而不是直接访问内部 slice。

`src/store/image/store.ts` 是 store 组装入口。它定义 `ImageStore` 接口，把 `GenerationConfigAction`、`GenerationTopicAction`、`GenerationBatchAction`、`CreateImageAction`、`ResetableStore` 和 `ImageStoreState` 合并为一个完整 store。它还通过 `flattenActions` 组合四个 slice：`createGenerationConfigSlice`、`createGenerationTopicSlice`、`createGenerationBatchSlice`、`createCreateImageSlice`，并加入 `ImageStoreResetAction`。

`src/store/image/initialState.ts` 是状态聚合入口。它把 `initialGenerationConfigState`、`initialGenerationTopicState`、`initialGenerationBatchState`、`initialCreateImageState` 合并成 `initialState`。

`src/store/image/selectors.ts` 是 selector 聚合入口，统一转出四个 slice 的 selector：`createImage`、`generationBatch`、`generationConfig`、`generationTopic`。阅读消费方时，如果看到 `imageGenerationConfigSelectors`、`generationTopicSelectors`、`generationBatchSelectors`，基本都可以回到这里和对应 slice 定位。

## 主流程位置

创建图片的主流程在 `src/store/image/slices/createImage/action.ts` 的 `createImage()`。流程大致是：先把 `isCreating` 置为 true；读取 `imageNum`、`parameters`、`provider`、`model` 和 `activeGenerationTopicId`；校验参数和 prompt；如果当前没有主题，就通过 `createGenerationTopic` 新建主题，调用 `setTopicBatchLoaded` 预置空批次，随后 `switchGenerationTopic` 切换过去；再调用 `imageService.createImage` 发起图片生成；若不是新主题，则刷新 generation batches；成功后清空 prompt；最后复位创建状态。

重生成流程在同一个文件的 `recreateImage(generationBatchId)`。它会根据旧批次保留 provider、model、config 和原始图片数量，先删除旧批次，再调用 `imageService.createImage` 发起新生成，并刷新批次列表。

主题主流程在 `src/store/image/slices/generationTopic/action.ts`。`createGenerationTopic()` 先内部创建主题，再调用 `summaryGenerationTopicTitle()` 根据 prompts 自动生成标题。内部创建使用乐观更新：先插入临时 topic，再调用 `generationTopicService.createTopic('image')`，之后刷新真实数据。

批次主流程在 `src/store/image/slices/generationBatch/action.ts`。`useFetchGenerationBatches(topicId)` 按主题拉取批次并写入 `generationBatchesMap`；`useCheckGenerationStatus()` 通过 SWR 轮询异步任务状态，成功或失败后停止轮询并更新对应 generation。删除相关动作会先更新前端状态，再调用后端 service，最后 refresh 保持一致。

配置主流程在 `src/store/image/slices/generationConfig/action.ts`。它负责根据 provider/model 取模型卡和参数 schema，抽取默认参数，切换模型时保留 prompt、图片输入和可复用设置，并在宽高或比例锁变化时同步修正 `parameters.width`、`parameters.height`。

## 推荐阅读顺序

建议先读 `src/store/image/store.ts`，理解这个 store 如何组合，以及哪些 slice 被合并到 `ImageStore`。然后读 `src/store/image/initialState.ts` 和 `src/store/image/selectors.ts`，建立状态与读取方式的总览。

第二步读 `src/store/image/slices/createImage/action.ts`，因为它是图片生成的业务编排中心，会把配置、主题、批次三个方向串起来。读完之后再回头看 `generationConfig`，理解生成参数从哪里来；看 `generationTopic`，理解没有当前主题时为什么会自动创建主题；看 `generationBatch`，理解生成结果、删除和状态轮询如何进入页面状态。

最后读 `src/store/image/utils/aspectRatio.ts`、`src/store/image/utils/size.ts` 和测试文件。它们适合在理解配置 slice 后补充阅读，因为这些工具解释了宽高比锁定、尺寸适配等 UI 行为背后的计算规则。

## 常见误区

不要把 `src/store/image` 理解成图片生成引擎。它只是前端状态和流程编排层，真正发起生成的是 `imageService.createImage`，生成状态查询和数据持久化也依赖 services 与后端接口。

不要把 topic 和 batch 混为一谈。`generationTopic` 是会话/历史分组，`generationBatch` 是某个主题下的一次生成结果集合。当前主题由 `activeGenerationTopicId` 表示，批次数据则按 topicId 存在 `generationBatchesMap` 里。

不要绕过 `index.ts` 和 `selectors.ts` 直接散乱读取内部状态。这个目录已经提供了统一入口和 selector 聚合，外部使用时应优先沿着 `useImageStore` 与 selectors 的路径理解。

不要忽略新主题创建时的特殊处理。`createImage()` 在没有 active topic 时会先创建 topic、预置空 batch、切换 topic，再发起生成。这是为了避免新建主题后页面出现不必要的 skeleton 或空白状态。

不要以为所有删除都只是本地状态更新。删除 generation 或 batch 会有乐观更新，但随后仍会调用 `generationService` 或 `generationBatchService`，并通过 refresh 与后端结果对齐。
