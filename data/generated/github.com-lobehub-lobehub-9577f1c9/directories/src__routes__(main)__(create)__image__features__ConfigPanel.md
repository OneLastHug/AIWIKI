# 目录：src/routes/(main)/(create)/image/features/ConfigPanel

## 它负责什么

`ConfigPanel` 是图像创建页面里“生成参数配置控件”的集合目录。它并不是一个完整页面，也不是一个单独的 `ConfigPanel.tsx` 容器，而是把模型选择、图片上传、尺寸控制、数量选择、质量/分辨率/尺寸/seed/steps/cfg 等控件拆成多个可复用组件，再通过 `index.ts` 统一导出给上层页面使用。

从路径位置看，它属于 `src/routes/(main)/(create)/image/features/` 下的图像创建功能区。这里的代码虽然在 `routes` 目录中，但实际承担的是图像生成页面的局部业务 UI：读取 `useImageStore` 里的生成配置，读取 `useAiInfraStore` 里的可用图像模型，调用 `useFileStore` 上传参考图或输入图，并把用户操作回写到图像生成配置状态中。

它处理的核心问题有四类：

1. 选择图像生成模型：通过 provider/model 组合更新当前图像生成模型。
2. 配置生成参数：宽高、比例、图片数量、质量、分辨率、尺寸、seed、steps、cfg 等。
3. 上传输入图片：支持点击选择、拖拽上传、上传进度、尺寸校验、文件大小校验。
4. 按模型能力约束 UI：比如模型是否支持 `width` / `height`，尺寸范围是多少，上传图是否满足约束。

## 关键组成

入口文件是 `index.ts`。它导出了一组配置控件：

- `AspectRatioSelect`
- `CfgSliderInput`
- `DimensionControlGroup`
- `ImageNum`
- `ImageUpload`
- `ImageModelItem`
- `QualitySelect`
- `ResolutionSelect`
- `SeedNumberInput`
- `SizeSelect`
- `StepsSliderInput`
- `useAutoDimensions`

这说明上层通常不会直接引用深层文件，而是从 `ConfigPanel` 聚合入口取组件。例外是 `PromptInput` 里也直接引用了 `components/ModelSelect/ImageModelItem`，用于更细粒度的模型展示。

`constants.ts` 目前只定义：

```ts
export const CONFIG_PANEL_WIDTH = 260;
```

它被 `MultiImagesUpload` 使用，用于根据面板宽度计算多图上传区域的可用宽度。这个常量体现了该目录对“右侧/底部配置面板固定宽度”的布局假设。

`style.ts` 定义 `configPanelStyles`，使用 `createStaticStyles` 创建两个通用拖拽样式：

- `dragOver`：拖拽悬停时放大、变主色边框、加主色阴影。
- `dragTransition`：统一控制 transform、border-color、box-shadow 的过渡动画。

这两个样式被 `ImageUpload` 的空态和成功态复用，保证拖拽反馈一致。

`ImageConfigSkeleton.tsx` 是加载骨架屏。它用 `Flexbox` 和 `Skeleton` 模拟模型选择、图片上传、参数控制、底部图片数量控制的结构。根据当前片段推断，它用于图像配置初始化期间的占位展示，依据是组件注释写明了 “Skeleton loading state for image configuration panel”，且布局与配置面板的控件顺序一致。

`components/ModelSelect/index.tsx` 是模型选择器。它依赖：

- `useAiInfraStore(aiProviderSelectors.enabledImageModelList)` 获取已启用、支持图像的 provider 和模型列表。
- `useImageStore` 与 `imageGenerationConfigSelectors.model/provider` 获取当前模型。
- `setModelAndProviderOnSelect` 写回用户选择。
- `useNavigate` 跳转到 provider 设置页。
- `ProviderItemRender` 和 `ImageModelItem` 渲染 provider/model 的展示项。

它的行为有几个细节：

- 没有任何 provider 时，展示禁用项 `ModelSwitchPanel.emptyProvider`，点击逻辑指向 `/settings/provider/all`。
- provider 有但没有模型时，展示禁用项 `ModelSwitchPanel.emptyModel`，点击逻辑指向 `/settings/provider/${provider.id}`。
- 多 provider 时使用分组 options，每组头部展示 provider 信息和一个设置按钮。
- `value` 使用 `${provider}/${model}` 组合字符串，但真正写入 store 时会拆回 `model` 和 `provider`。
- 对模型 id 中可能包含 `/` 的情况，使用 `value.split('/').slice(1).join('/')` 还原 model，而不是简单取第二段。

`components/DimensionControlGroup.tsx` 是尺寸控制组。它调用 `useDimensionControl()`，拿到：

- `isLocked`
- `toggleLock`
- `width`
- `height`
- `aspectRatio`
- `setWidth`
- `setHeight`
- `setAspectRatio`
- `widthSchema`
- `heightSchema`
- `options`

UI 上包含三个区域：

1. 宽高比例选择器 `AspectRatioSelect`。
2. 宽度 `SliderWithInput`。
3. 高度 `SliderWithInput`。

如果当前模型参数 schema 不支持宽或高，对应 slider 不会渲染。锁定按钮在 `LockIcon` 和 `UnlockIcon` 之间切换，文案来自 `image` namespace 下的 `config.aspectRatio.*`。

`components/ImageUpload.tsx` 是单图上传组件，复杂度较高。它包含：

- `ImageUploadProps`：支持 `value`、`onChange`、`maxFileSize`、`imageConstraints`、`placeholderHeight` 等。
- 内部 `UploadState`：记录 `previewUrl`、`progress`、`status`、`error`。
- `CircularProgress`：上传进度圆环。
- `Placeholder`：未上传时的点击/拖拽区域。
- `UploadingDisplay`：上传中预览图和进度遮罩。
- `SuccessDisplay`：上传成功后的图片预览、删除按钮、换图遮罩。

它使用 `useFileStore((s) => s.uploadWithProgress)` 执行上传，并通过 `onStatusUpdate` 更新本地进度。上传成功后，如果结果包含 `dimensions`，会把 `{ url, dimensions }` 传给 `onChange`；否则兼容旧 API，只传 `url` 字符串。这种设计说明该组件既服务旧的“只需要 URL”的调用方，也服务新场景中“上传后自动识别图片尺寸”的调用方。

`hooks/useUploadFilesValidation.ts` 封装上传前校验。它调用 `utils/imageValidation.ts` 中的：

- `validateImageFiles`
- `validateImageDimensions`
- `formatFileSize`

并通过 `antd` 的 `App.useApp().message` 展示错误。它负责把底层错误码转换成用户可读提示，比如文件过大、图片数量超限、尺寸过小、尺寸过大、宽高比不合法。

`hooks/useAutoDimensions.ts` 封装“根据上传图片自动设置生成宽高”的逻辑。它从 `useImageStore` 读取当前模型的 `parametersSchema`，判断是否支持 `width` 和 `height`，再用 `constrainDimensions` 把原图尺寸压到模型约束范围内，最后调用 `setWidth` 和 `setHeight`。它还导出 `extractUrlAndDimensions`，用于兼容 `ImageUpload` 的两种回调格式：字符串 URL 或 `{ url, dimensions }` 对象。

`utils/dimensionConstraints.ts` 的 `constrainDimensions` 是纯函数。它按以下顺序处理尺寸：

1. 如果超过最大值，按比例缩小。
2. 如果低于最小值，按比例放大。
3. 先做一次 min/max 边界裁剪。
4. 四舍五入到 8 的倍数。
5. 再做一次 min/max 边界裁剪。

“8 的倍数”通常是图像生成模型对尺寸的常见要求，这里通过注释也明确说明了这一点。

`utils/imageValidation.ts` 是上传校验的纯工具层，包含文件大小、图片数量、图片尺寸读取、尺寸范围和宽高比校验。它使用 `URL.createObjectURL(file)` 和 `new globalThis.Image()` 读取本地图片的自然宽高，并在 `onload` / `onerror` 后释放 blob URL。

## 上下游关系

上游调用方主要在图像创建页面的相邻功能目录中。当前片段中可见 `src/routes/(main)/(create)/image/features/PromptInput/index.tsx` 引用了：

- `DimensionControlGroup`
- `ImageNum`
- `ImageModelItem`

其中 `DimensionControlGroup` 在 `PromptInput` 大约第 305 行按 `showDimensionControl` 条件渲染；`ImageNum` 在约第 342 行作为某个弹出内容或配置内容传入；`ImageModelItem` 用于模型展示。根据当前片段推断，图像创建页的提示词输入区会把部分配置控件内嵌到输入区或工具栏中，而不是一定以传统右侧面板形式出现。

下游依赖主要有这些：

- `@lobehub/ui`：提供 `Select`、`ActionIcon`、`Flexbox`、`Center`、`Skeleton`、`SliderWithInput` 等 UI。
- `antd`：通过 `App.useApp()` 使用全局 message。
- `antd-style`：通过 `createStaticStyles` 和 `cssVar` 写静态样式。
- `lucide-react`：提供模型设置、上传占位、锁定、删除等图标。
- `react-i18next`：从 `components`、`image` 等 namespace 读取文案。
- `react-router-dom`：`ModelSelect` 用 `useNavigate` 跳到 provider 设置页。
- `@/store/image`：核心生成配置状态，包括当前 model/provider、宽高、数量等。
- `@/store/aiInfra`：可用模型和 provider 列表。
- `@/store/file`：文件上传能力。
- `model-bank`：`useAutoDimensions` 使用 `DEFAULT_DIMENSION_CONSTRAINTS` 作为模型尺寸默认边界。

可以把它理解成一个中间层：上游页面负责决定“什么时候展示哪些控件”，`ConfigPanel` 负责“控件如何展示、如何校验、如何把用户输入写回 store”，下游 store/service 负责真实状态和上传能力。

## 运行/调用流程

典型的模型选择流程如下：

1. 页面渲染模型选择控件。
2. `ModelSelect` 从 `useAiInfraStore` 读取启用的图像 provider/model 列表。
3. 从 `useImageStore` 读取当前 `provider` 和 `model`。
4. 把 provider/model 组合成 `Select` 的 options。
5. 用户选择某个 `${provider}/${model}`。
6. `onChange` 拆分出 provider 和 model。
7. 如果和当前值不同，调用 `setModelAndProviderOnSelect(model, provider)`。
8. 图像生成配置 store 更新，其他参数控件会随模型能力变化重新渲染或调整。

典型的尺寸控制流程如下：

1. `DimensionControlGroup` 调用 `useDimensionControl()`。
2. hook 返回当前宽高、比例、锁定状态、可选比例列表和 schema。
3. 用户切换比例或拖动宽高 slider。
4. 组件调用 `setAspectRatio` / `setWidth` / `setHeight`。
5. store 内部根据锁定状态和模型 schema 处理宽高联动。
6. 组件重新读取 store 状态并更新 UI。

典型的单图上传流程如下：

1. 用户点击 `Placeholder` 或拖拽文件到上传区。
2. `ImageUpload` 取第一个文件；如果拖入多个文件，会弹出 warning。
3. 调用 `validateFiles([file])` 校验数量和文件大小。
4. 调用 `validateDimensions(file)` 校验图片尺寸和宽高比。
5. 创建本地 blob URL 作为预览。
6. 设置 `uploadState` 为 `pending`，展示上传中状态。
7. 调用 `useFileStore.uploadWithProgress({ file, onStatusUpdate, skipCheckFileType: true })`。
8. `onStatusUpdate` 根据上传进度更新 `progress` 和 `status`。
9. 上传成功后，如果返回 `url`，调用 `onChange(result.url)` 或 `onChange({ url, dimensions })`。
10. 释放 blob URL，并延迟清理上传状态。

典型的自动尺寸流程如下：

1. 某个上游组件接收到 `ImageUpload` 的 `onChange` 数据。
2. 用 `extractUrlAndDimensions` 解析出 `url` 和可选 `dimensions`。
3. 如果有 `dimensions`，并且当前模型支持 `width` / `height`，调用 `autoSetDimensions(dimensions)`。
4. `autoSetDimensions` 根据当前模型的 `parametersSchema.width/height` 生成约束。
5. `constrainDimensions` 调整图片尺寸，使其符合模型范围和 8 的倍数要求。
6. 写回 `setWidth`、`setHeight`。

## 小白阅读顺序

1. 先看 `index.ts`  
   这个文件最短，能快速知道 `ConfigPanel` 对外暴露了哪些能力。注意它导出的是很多小控件，不是一个完整面板。

2. 再看 `components/ModelSelect/index.tsx`  
   这是最容易理解的业务控件：从 provider/model 列表生成下拉选项，用户选择后写回 `useImageStore`。读完它可以理解本目录和 `aiInfra`、`image` 两个 store 的关系。

3. 再看 `components/DimensionControlGroup.tsx`  
   它展示了参数控件的典型模式：组件本身很薄，把复杂逻辑交给 store hook `useDimensionControl()`，然后根据 schema 决定是否渲染宽高 slider。

4. 然后看 `components/ImageUpload.tsx`  
   这是目录里最复杂的组件。建议分块读：先看 `ImageUploadProps`，再看 `Placeholder` / `UploadingDisplay` / `SuccessDisplay` 三种 UI 状态，最后看主组件里的 `handleFileChange` 和 `handleDrop`。

5. 接着看 `hooks/useUploadFilesValidation.ts` 和 `utils/imageValidation.ts`  
   这两个文件是一组：hook 负责接 UI message，utils 负责纯校验逻辑。小白要注意区分“业务错误码”和“展示给用户的错误文案”。

6. 最后看 `hooks/useAutoDimensions.ts` 和 `utils/dimensionConstraints.ts`  
   这部分解释为什么上传图片后可以自动带出宽高，以及为什么宽高会被压到模型允许范围内。

## 常见误区

1. 误以为这里有完整的 `ConfigPanel` 容器  
   实际上当前目录没有一个总面板组件。`index.ts` 是聚合导出文件，上层页面按需组合这些控件。`CONFIG_PANEL_WIDTH` 只是布局常量，不代表这里一定有一个固定宽度的 React 面板。

2. 误以为 `ImageUpload.onChange` 永远返回字符串  
   它兼容两种格式：旧格式是 `string` URL，新格式是 `{ url, dimensions }`。调用方如果只按字符串处理，可能会漏掉自动尺寸能力。

3. 误以为上传组件自己负责生成配置更新  
   `ImageUpload` 只负责上传和把结果通过 `onChange` 抛出去。真正把上传图片的尺寸写入生成配置，是 `useAutoDimensions` 或上层调用方组合完成的。

4. 误以为尺寸 slider 一定显示  
   `DimensionControlGroup` 只有在 `widthSchema` / `heightSchema` 存在时才显示对应 slider。模型不支持宽高参数时，控件不会强行渲染。

5. 误以为拖拽样式只属于 `ImageUpload`  
   拖拽相关样式被抽到 `style.ts` 的 `configPanelStyles`，单图上传和其他上传组件都可以复用。`MultiImagesUpload` 也在同目录下，并使用了 `CONFIG_PANEL_WIDTH`。

6. 误以为模型下拉的空状态可正常选择  
   没有 provider 或 provider 没有模型时，下拉项是 disabled 的引导项。`onChange` 里也显式跳过了 `no-provider` 和 `/empty`，不会把这些占位值写入生成配置。

7. 误以为 model id 不会包含 `/`  
   `ModelSelect` 解析 model 时使用 `split('/').slice(1).join('/')`，说明作者考虑了 model id 中带 `/` 的情况。改这里时不能简单写成 `const [, model] = value.split('/')`。

8. 误以为 `constrainDimensions` 只做 min/max 裁剪  
   它还会保持宽高比缩放，并把结果 round 到 8 的倍数。这个逻辑会改变用户上传图片的原始尺寸，但目的是适配模型约束。
