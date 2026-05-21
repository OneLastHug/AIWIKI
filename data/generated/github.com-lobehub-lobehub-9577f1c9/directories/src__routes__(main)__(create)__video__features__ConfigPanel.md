# 目录：src/routes/(main)/(create)/video/features/ConfigPanel

## 它负责什么

`ConfigPanel` 是视频生成页里“配置相关 UI 组件”的小型目录。它不直接承担完整页面渲染，也不直接发起视频生成请求，而是提供可复用的配置控件，供视频创作输入区 `PromptInput` 组合使用。

从当前代码看，它主要负责三类事情：

1. 视频模型选择项的展示  
   `VideoModelItem` 用统一的 `GenerationModelItem` 渲染视频模型，并指定 `priceKind="video"`，让模型项按视频生成计价方式展示价格信息。

2. 视频参考帧上传  
   `FrameUpload` 包装了图片生成配置面板里的 `ImageUpload`，但数据源改成视频 store 的 `useVideoGenerationConfigParam`。它用于写入视频生成参数里的 `imageUrl` 或 `endImageUrl`。

3. 视频配置加载骨架屏  
   `VideoConfigSkeleton` 描述了视频配置面板加载时的占位结构，包括模型选择、首帧/尾帧、比例、分辨率、时长、seed、音频/固定镜头开关等。

需要注意：当前目录名叫 `ConfigPanel`，但并没有一个默认导出的“大面板组件”。真正的配置弹层内容目前主要写在 `src/routes/(main)/(create)/video/features/PromptInput/index.tsx` 里，通过 `ConfigAction` 组合多个局部配置项。

## 关键组成

`index.ts`

这是目录的公开出口，目前只导出两个组件：

```ts
export { default as FrameUpload } from '@/routes/(main)/(create)/video/features/ConfigPanel/components/FrameUpload';
export { default as VideoModelItem } from '@/routes/(main)/(create)/video/features/ConfigPanel/components/ModelSelect/VideoModelItem';
```

也就是说，外部通过 `ConfigPanel` 目录能拿到 `FrameUpload` 和 `VideoModelItem`。但 `components/ModelSelect/index.tsx` 里的 `ModelSelect` 没有从这里导出，当前也没有被直接调用到。根据当前片段推断，它可能是早期或备用的独立模型选择下拉框实现，后来视频输入区改用了通用的 `ModelSwitchPanel`。

`VideoConfigSkeleton.tsx`

这是客户端组件，用 `@lobehub/ui` 的 `Flexbox` 和 `Skeleton` 搭出加载态。它只做视觉占位，不连接 store，也没有业务判断。

骨架结构与视频配置项大体对应：

- `ModelSelect`
- `FrameUpload: imageUrl`
- `FrameUpload: endImageUrl`
- `AspectRatio`
- `Resolution`
- `Duration`
- `Seed`
- `generateAudio switch`
- `cameraFixed switch`

它的存在说明视频配置在初始化或数据加载时可能需要占位体验，不过当前抽样调用方中没有看到它被直接引用。

`components/FrameUpload.tsx`

这是视频首帧/尾帧上传控件。它接收一个参数：

```ts
paramName: 'endImageUrl' | 'imageUrl'
```

内部调用：

```ts
useVideoGenerationConfigParam(paramName)
```

拿到当前参数值、写入函数、最大文件大小、图片尺寸约束，然后把这些传给图片侧已有的 `ImageUpload`。

核心逻辑在 `handleChange`：

```ts
const url = typeof data === 'string' ? data : data?.url;
setValue((url ?? null) as any);
```

也就是说，无论 `ImageUpload` 回传的是纯 URL 字符串，还是 `{ url, dimensions }` 对象，最终视频 store 里只保存 URL。上传图片的尺寸信息只用于上传/校验阶段，不会作为视频生成参数继续保存。

这里复用了图片生成目录的上传组件：

```ts
import { ImageUpload } from '@/routes/(main)/(create)/image/features/ConfigPanel';
```

所以视频参考帧上传能力实际上依赖图片配置面板已有的上传、拖拽、校验等能力。

`components/ModelSelect/VideoModelItem.tsx`

这是一个非常薄的适配组件：

```tsx
const VideoModelItem = (props: VideoModelItemProps) => (
  <GenerationModelItem {...props} priceKind="video" showPrice={true} />
);
```

它接收 `model-bank` 里的 `AiModelForSelect` 字段，并额外支持：

- `providerId`
- `showBadge`
- `showPopover`

它的作用不是重新实现模型项 UI，而是告诉通用模型项组件：这是视频模型，要显示视频价格。

`components/ModelSelect/index.tsx`

这是一个完整的独立模型下拉框组件 `ModelSelect`。它使用：

- `useAiInfraStore(aiProviderSelectors.enabledVideoModelList)` 获取已启用的视频模型供应商列表
- `useVideoStore(videoGenerationConfigSelectors.model/provider)` 获取当前选中模型和供应商
- `setModelAndProviderOnSelect` 写回视频生成配置
- `ProviderItemRender` 渲染供应商分组
- `VideoModelItem` 渲染模型项
- `useNavigate` 跳转到供应商设置页

它处理了几个状态：

- 没有启用视频供应商：显示 `ModelSwitchPanel.emptyProvider`，点击跳转 `/settings/provider/all`
- 某个供应商没有模型：显示 `ModelSwitchPanel.emptyModel`，点击跳转 `/settings/provider/${provider.id}`
- 多个供应商：按供应商分组展示模型，供应商标题右侧有设置按钮
- 单个供应商：直接展示模型列表，不做分组

选择值格式是：

```ts
`${provider.id}/${model.id}`
```

切换时再拆回：

```ts
const model = value.split('/').slice(1).join('/');
const provider = (option as unknown as ModelOption).provider;
setModelAndProviderOnSelect(model, provider);
```

这里用 `slice(1).join('/')` 而不是简单取第二段，是为了兼容模型 id 本身可能包含 `/` 的情况。

## 上下游关系

上游数据主要来自视频 store 和 AI 基础设施 store。

`useVideoGenerationConfigParam`

路径：

`src/store/video/slices/generationConfig/hooks.ts`

这是配置项组件读取和写入参数的核心 hook。调用时传入参数名，例如：

```ts
useVideoGenerationConfigParam('imageUrl')
useVideoGenerationConfigParam('endImageUrl')
useVideoGenerationConfigParam('duration')
```

它从视频 store 中读取：

- `parameters`
- `parametersSchema`

然后返回：

- `value`
- `setValue`
- `enumValues`
- `min`
- `max`
- `step`
- `maxCount`
- `maxFileSize`
- `imageConstraints`

这意味着 UI 控件不是写死能力，而是根据当前模型的 `parametersSchema` 动态决定可选值、约束和是否显示。

`parametersSchema`

默认视频模型和参数 schema 定义在：

`src/store/video/slices/generationConfig/initialState.ts`

默认 provider 是：

```ts
ModelProvider.LobeHub
```

默认 model 是：

```ts
dreamina-seedance-2-0-260128
```

默认参数 schema 中包含：

- `aspectRatio`
- `duration`
- `endImageUrl`
- `generateAudio`
- `imageUrls`
- `prompt`
- `resolution`
- `seed`

其中 `endImageUrl` 有一个关键字段：

```ts
requiresImageUrl: true
```

这表示尾帧依赖首帧或参考图。真正生成前会在 `createVideo` 里做校验。

模型切换

模型切换逻辑在：

`src/store/video/slices/generationConfig/action.ts`

`setModelAndProviderOnSelect(model, provider)` 会：

1. 根据 provider 和 model 找到启用的视频模型
2. 从模型参数 schema 中提取默认值
3. 保留旧参数中仍被新模型支持的关键输入项
4. 更新 `model`、`provider`、`parameters`、`parametersSchema`
5. 登录状态下记录用户最后选择的视频模型和供应商

它会特别保留：

- `prompt`
- `imageUrl`
- `imageUrls`
- `endImageUrl`

所以用户切换模型时，提示词和参考图不会轻易丢失，但会根据新模型 schema 做归一化。

下游调用主要在 `PromptInput`

路径：

`src/routes/(main)/(create)/video/features/PromptInput/index.tsx`

当前视频创作输入区直接使用了 `VideoModelItem`，也复用了图片侧的配置控件：

```ts
import { AspectRatioSelect } from '@/routes/(main)/(create)/image/features/ConfigPanel';
import Select from '@/routes/(main)/(create)/image/features/ConfigPanel/components/Select';
import VideoModelItem from '@/routes/(main)/(create)/video/features/ConfigPanel/components/ModelSelect/VideoModelItem';
```

在 `PromptInput` 中，模型选择不是使用本目录的 `ModelSelect`，而是使用通用的：

```tsx
<ModelSwitchPanel
  ModelItemComponent={VideoModelItem}
  enabledList={enabledVideoModelList}
  pricingMode="video"
/>
```

配置项则通过 `ConfigAction` 弹出，里面根据 `isSupportedParam` 判断模型是否支持某项，再决定是否渲染：

- `AspectRatioItem`
- `ResolutionItem`
- `SizeItem`
- `SeedItem`
- `SwitchItem`
- `PromptExtendItem`
- `DurationItem`

生成请求

最终点击生成时，`PromptInput` 调用：

```ts
createVideo()
```

实际逻辑在：

`src/store/video/slices/createVideo/action.ts`

它会从视频 store 取出当前：

- `parameters`
- `provider`
- `model`

然后调用：

```ts
videoService.createVideo({
  generationTopicId,
  model,
  params: parameters,
  provider,
});
```

因此 `ConfigPanel` 目录里的组件只是修改 `parameters` 或展示模型信息；真正请求服务端是在 `createVideo` action 中完成。

## 运行/调用流程

典型的视频生成配置流程如下：

1. 页面进入视频创作区域，`PromptInput` 渲染主输入框、模型按钮、配置按钮、参考帧内联上传区域。

2. `useFetchAiVideoConfig()` 拉取或初始化视频模型配置；视频 store 中维护当前 `model`、`provider`、`parameters`、`parametersSchema`。

3. 用户点击模型按钮时，`PromptInput` 打开 `ModelSwitchPanel`。模型项由 `VideoModelItem` 渲染，因此列表里显示视频模型信息和视频价格。

4. 用户选择模型后，调用 `setModelAndProviderOnSelect(model, provider)`。store 根据新模型的 schema 重建参数默认值，并尽量保留旧的 prompt、首帧、参考图、尾帧。

5. 用户添加参考帧时，当前主流程使用的是 `InlineVideoFrames`。如果使用 `FrameUpload`，则它会通过 `useVideoGenerationConfigParam('imageUrl' 或 'endImageUrl')` 把上传结果写入视频参数。

6. 用户打开配置按钮时，`ConfigAction` 显示可用配置项。每个配置项先通过 `isSupportedParam` 判断当前模型是否支持该参数。例如模型不支持 `cameraFixed`，就不会显示固定镜头开关。

7. 用户修改配置项时，统一通过 `useVideoGenerationConfigParam(paramName).setValue` 调用 `setParamOnInput`，更新 store 中的 `parameters[paramName]`。

8. 用户点击生成时，`createVideo` 读取当前参数并校验。若模型 schema 声明 `endImageUrl.requiresImageUrl`，且用户只给了尾帧但没有首帧/参考图，会弹出 warning 并中止生成。

9. 校验通过后，`videoService.createVideo` 发送生成请求。请求参数就是当前 store 中积累出来的 `parameters`。

## 小白阅读顺序

1. 先看 `index.ts`  
   了解这个目录对外暴露什么。你会发现它只公开 `FrameUpload` 和 `VideoModelItem`，不是完整配置面板。

2. 再看 `VideoModelItem.tsx`  
   这是最简单的文件。它能帮助你理解“视频模型项”其实复用了通用的 `GenerationModelItem`，只是指定了 `priceKind="video"`。

3. 再看 `FrameUpload.tsx`  
   重点看它如何把图片上传组件 `ImageUpload` 接到视频配置参数上。这里能理解“UI 组件”和“store 参数”之间的桥接方式。

4. 接着看 `components/ModelSelect/index.tsx`  
   虽然它当前不是主要调用路径，但它完整展示了模型选择下拉框如何组织 provider、model、空状态和设置跳转。读它可以理解视频模型列表的数据结构。

5. 然后看 `PromptInput/index.tsx`  
   这是实际页面组合点。重点看：
   - `ModelSwitchPanel` 如何使用 `VideoModelItem`
   - `ConfigAction` 里如何按 `isSupportedParam` 渲染不同配置项
   - `GenerationPromptInput` 如何触发 `createVideo`

6. 最后看 store  
   推荐顺序：
   - `src/store/video/slices/generationConfig/hooks.ts`
   - `src/store/video/slices/generationConfig/initialState.ts`
   - `src/store/video/slices/generationConfig/action.ts`
   - `src/store/video/slices/createVideo/action.ts`

   读完这几处，就能串起“模型 schema -> UI 控件 -> store 参数 -> 生成请求”的完整链路。

## 常见误区

1. 误以为 `ConfigPanel` 目录里有完整配置面板  
   当前没有。真正的配置弹层内容在 `PromptInput/index.tsx` 的 `ConfigAction` 中组合。这个目录更像是视频配置控件的零件库。

2. 误以为 `components/ModelSelect/index.tsx` 是当前主入口  
   根据当前调用方搜索结果，视频输入区实际使用的是通用 `ModelSwitchPanel`，并传入 `VideoModelItem`。本目录的 `ModelSelect` 虽然实现完整，但当前片段中没有看到直接调用。

3. 误以为配置项是固定写死的  
   不是。是否显示某个配置项，主要由当前模型的 `parametersSchema` 决定。`isSupportedParam('duration')` 为真才显示时长，`isSupportedParam('generateAudio')` 为真才显示音频开关。

4. 误以为上传图片会保存尺寸信息  
   `FrameUpload` 的 `handleChange` 只把 URL 写进视频参数。`dimensions` 只在上传组件返回值里短暂出现，最终没有进入 `parameters`。

5. 误以为尾帧可以单独使用  
   默认 schema 中 `endImageUrl` 声明了 `requiresImageUrl: true`。生成前 `createVideo` 会检查：如果有尾帧但没有首帧或参考图，会提示 `endFrameRequiresStartFrame` 并停止生成。

6. 误以为切换模型会清空所有输入  
   `setModelAndProviderOnSelect` 会基于新模型 schema 生成默认参数，但会尝试保留 `prompt`、`imageUrl`、`imageUrls`、`endImageUrl` 等关键输入。只是如果新模型不支持某些参数，这些参数可能会被归一化或移除。

7. 误以为视频配置组件完全独立于图片配置组件  
   实际上视频侧复用了很多图片侧能力，例如 `ImageUpload`、`AspectRatioSelect` 和 `Select`。因此修改图片配置面板里的基础上传或选择组件，可能影响视频生成页的配置体验。
