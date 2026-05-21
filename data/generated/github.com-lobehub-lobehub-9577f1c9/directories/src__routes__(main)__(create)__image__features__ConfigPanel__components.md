# 目录：src/routes/(main)/(create)/image/features/ConfigPanel/components

## 它负责什么

这个目录是一组“图像创建配置面板”的前端控件组件，位于 `src/routes/(main)/(create)/image/features/ConfigPanel/components`。它不直接负责提交生图任务，而是负责把用户在配置面板中选择的参数写入对应的状态层，供后续图像生成流程读取。

从已读取片段看，这些组件主要服务于 `create/image` 路由下的图像生成配置区域，覆盖几类能力：

- 选择图像生成模型：`ModelSelect`
- 设置尺寸、比例、分辨率：`DimensionControlGroup`、`AspectRatioSelect`、`SizeSelect`、`ResolutionSelect`
- 设置生成参数：`CfgSliderInput`、`StepsSliderInput`、`SeedNumberInput`、`QualitySelect`
- 设置生成张数：`ImageNum`
- 上传或管理参考图：`ImageUpload`、`ImageUrl`、`ImageUrlsUpload`、`MultiImagesUpload`
- 复用基础选择器和数字输入：`Select`、`InputNumber`

它们的共同特点是：组件本身尽量只做 UI 和交互，真正的业务状态来自 store hooks，例如 `useImageStore`、`useAiInfraStore`、`useFileStore`、`useServerConfigStore`，以及 `useGenerationConfigParam`、`useDimensionControl` 这类封装好的配置 hooks。

## 关键组成

`AspectRatioSelect/index.tsx` 是一个比例选择网格组件。它接收 `options`、`value`、`defaultValue`、`onChange`，内部使用 `useMergeState` 同时支持受控和非受控模式。它会判断选项值是否是类似 `16:9` 的比例字符串，如果是，就渲染一个按比例缩放的小矩形；如果不是，就渲染虚线方框，适合表达“自定义”或非标准比例。它依赖 `@lobehub/ui` 的 `Block`、`Grid`、`Text`、`Center`，并通过 `useIsDark` 判断暗色模式下是否启用阴影。

`DimensionControlGroup.tsx` 是宽高和比例的组合控件。它通过 `useDimensionControl()` 取得 `width`、`height`、`aspectRatio`、`isLocked`、`toggleLock`、`setWidth`、`setHeight`、`setAspectRatio`、`widthSchema`、`heightSchema` 和比例选项。UI 上先渲染比例选择器和锁定按钮，再根据 schema 渲染宽度、高度的 `SliderWithInput`。这里的关键不是单个输入框，而是“比例锁定 + 宽高联动”这一组行为被封装在 store hook 里。

`ModelSelect/index.tsx` 负责选择生图模型。它从 `useImageStore` 读取当前 `model` 和 `provider`，通过 `useAiInfraStore(aiProviderSelectors.enabledImageModelList)` 获取当前启用的图片模型列表。它会把模型按 provider 分组，如果没有 provider 或 provider 下没有模型，会展示禁用态提示，并提供跳转到 `/settings/provider/all` 或 `/settings/provider/:id` 的入口。选择模型时，它把形如 `provider/model` 的值拆开，再调用 `setModelAndProviderOnSelect(model, provider)` 写入图像配置。

`ImageModelItem.tsx` 是 `ModelSelect` 的模型展示项。根据当前片段可确认它被 `ModelSelect` 用作下拉项 label 和选中态 label 的展示组件。它通常负责展示模型名称、provider 信息、badge 或 popover。具体视觉细节未展开阅读，因此这里根据调用方式推断：它是模型列表中的原子展示组件。

`CfgSliderInput.tsx` 是很薄的参数控件。它调用 `useGenerationConfigParam('cfg')`，取得 `value`、`setValue`、`min`、`max`，然后渲染 `SliderWithInput`。这说明 `cfg` 参数的边界和当前值不是写死在组件里，而是由当前模型或配置 schema 决定。

`StepsSliderInput.tsx` 根据命名和 `CfgSliderInput` 的模式推断，应该是同样通过 `useGenerationConfigParam('steps')` 或类似 key 读取 steps 参数，再用滑块输入组件展示。依据是同目录中多个参数控件采用统一命名和同一个配置 hook。

`QualitySelect.tsx` 使用 `useGenerationConfigParam('quality')` 获取 `value`、`setValue`、`enumValues`。它把枚举值映射成 i18n 文案，例如 `standard` 对应 `config.quality.options.standard`，其他值对应 `config.quality.options.hd`。这类组件适合处理模型支持的枚举配置项。

`SizeSelect.tsx` 使用 `useGenerationConfigParam('size')` 获取尺寸枚举，把 `enumValues` 直接映射成 `Select` options。它使用的是本目录下的 `./Select`，而不是直接使用 `@lobehub/ui` 的 `Select`，说明目录里有一个面向配置面板的统一选择器封装。

`ImageNum.tsx` 负责生成张数选择。默认预设为 `[1, 2, 4, 8]`，同时支持自定义数量。它从 `useImageStore(imageGenerationConfigSelectors.imageNum)` 读取当前数量，用 `setImageNum` 更新。最大值会受 `serverConfigSelectors.enableBusinessFeatures` 影响：开启商业功能时默认最大 8，否则默认最大 50。它使用 `Segmented` 展示预设值，点击加号进入编辑模式，用 `InputNumber`、确认按钮和取消按钮完成自定义输入。

`MultiImagesUpload/index.tsx` 是较复杂的参考图上传组件。它支持：

- 空状态点击选择图片
- 拖拽上传图片
- 多图缩略图展示
- 单图大预览
- 删除图片
- 上传进度显示
- 打开 `ImageManageModal` 管理已有图片和新增图片
- 上传成功后把 URL 数组回传给父组件
- 首次只上传一张图时，把图片尺寸 `{ width, height }` 一起回传，供上层自动设置参数

它依赖 `useFileStore((s) => s.uploadWithProgress)` 执行上传，依赖 `useUploadFilesValidation(maxCount, maxFileSize)` 校验文件数量和大小，依赖 `useDragAndDrop` 处理拖放。内部用 `DisplayItem` 维护上传中的临时预览、进度、状态和错误信息。上传前会用 `URL.createObjectURL(file)` 创建本地预览，上传完成或组件卸载时会 `URL.revokeObjectURL` 释放 blob URL。

`ImageManageModal.tsx` 是 `MultiImagesUpload` 的图片管理弹窗。根据当前片段可见它导出了 `ImageItem` 类型，并被 `MultiImagesUpload` 用来接收 `images`、`maxCount`、`open`、`onClose`、`onComplete`。`onComplete` 返回的 `ImageItem[]` 会被拆成已有 URL 和新增 File，再分别更新父级状态和触发上传。

`InputNumber/index.tsx`、`Select/index.tsx` 是本目录内部的基础控件封装。根据命名和 `SizeSelect` 的使用方式推断，它们用于统一配置面板里的输入尺寸、样式、variant 或交互细节，避免每个参数控件重复写同样的 UI 配置。

`ConfigPanel/index.ts` 是上级目录的导出入口。它导出了 `AspectRatioSelect`、`CfgSliderInput`、`DimensionControlGroup`、`ImageNum`、`ImageUpload`、`ImageModelItem`、`QualitySelect`、`ResolutionSelect`、`SeedNumberInput`、`SizeSelect`、`StepsSliderInput` 和 `useAutoDimensions`。注意它没有在当前片段中导出 `ModelSelect`、`MultiImagesUpload`、`ImageUrl`、`ImageUrlsUpload`，这说明部分组件可能被上层直接路径引用，或者还处于局部内部组件状态。

## 上下游关系

上游主要是图像创建页面和配置面板。根据路径结构，调用链大致位于：

`src/routes/(main)/(create)/image`  
→ `features/ConfigPanel`  
→ `components/*`

这些组件面向页面提供可组合的参数控件。上层负责决定哪些控件出现、如何排列，以及提交生成任务时如何读取配置。

下游主要分为四类：

第一类是图像配置状态。多个组件通过 `useImageStore` 或 `useGenerationConfigParam` 读写生成配置。例如 `ImageNum` 写入 `imageNum`，`CfgSliderInput` 写入 `cfg`，`QualitySelect` 写入 `quality`，`SizeSelect` 写入 `size`，`ModelSelect` 写入 `model` 和 `provider`。

第二类是 AI provider 和模型状态。`ModelSelect` 通过 `useAiInfraStore` 和 `aiProviderSelectors.enabledImageModelList` 获取可用图片模型。它不是直接请求接口，而是消费已经进入 store 的 provider/model 列表。

第三类是文件上传系统。`MultiImagesUpload` 通过 `useFileStore.uploadWithProgress` 上传图片，并把上传后的远程 URL 传给父组件。它并不自己保存最终业务配置，而是通过 `onChange` 把结果交给上层。

第四类是通用 UI 和 i18n。组件大量使用 `@lobehub/ui`、`antd-style`、`lucide-react` 和 `react-i18next`。文案 namespace 主要有 `image` 和 `components`，例如尺寸、质量属于 `image`，多图上传和模型切换提示属于 `components`。

## 运行/调用流程

典型的模型选择流程如下：

1. `ModelSelect` 渲染时从 `useImageStore` 读取当前 `provider` 和 `model`。
2. 它从 `useAiInfraStore` 读取启用的图片模型列表。
3. 如果没有 provider，显示空状态，并允许跳转到 provider 设置页。
4. 如果 provider 存在但模型为空，显示 provider 分组下的空模型提示。
5. 用户选择某个模型后，组件把 `provider/model` 拆成 `provider` 和 `model`。
6. 调用 `setModelAndProviderOnSelect(model, provider)` 更新图像生成配置。

典型的尺寸控制流程如下：

1. `DimensionControlGroup` 调用 `useDimensionControl()`。
2. hook 返回当前宽高、比例、锁定状态和 schema。
3. 用户切换比例时调用 `setAspectRatio`。
4. 用户点击锁按钮时调用 `toggleLock`。
5. 用户调整宽度或高度时调用 `setWidth`、`setHeight`。
6. 宽高是否联动、是否受模型约束，不在组件内实现，而是在 `useDimensionControl` 和相关 store 逻辑中处理。

典型的参数选择流程如下：

1. 参数组件调用 `useGenerationConfigParam('<param>')`。
2. hook 返回当前值、可选枚举、最小值、最大值、更新函数等。
3. 组件渲染 `Select`、`SliderWithInput` 或数字输入。
4. 用户修改值后调用 `setValue`。
5. store 中的 generation config 更新，后续生成请求读取这个配置。

典型的多图上传流程如下：

1. `MultiImagesUpload` 根据 `value` 判断当前是空状态、单图、多图还是上传中。
2. 用户点击空状态、拖拽图片，或在管理弹窗中加入新文件。
3. 组件先调用 `validateFiles(files, currentUrls.length)` 校验数量和大小。
4. 校验通过后，为每个文件创建本地 blob URL，用于即时预览。
5. 调用 `uploadWithProgress` 上传文件，并通过 `onStatusUpdate` 更新进度。
6. 所有上传 promise 完成后，收集成功的远程 URL。
7. 如果是首次上传且只有一张图，还会把图片尺寸一起回传。
8. 调用 `onChange(updatedUrls)` 或 `onChange({ urls, dimensions })` 通知父组件。
9. 清理 blob URL，短暂展示成功状态后清空上传中的临时 `displayItems`。

## 小白阅读顺序

建议先看 `ConfigPanel/index.ts`。它告诉你哪些组件是这个面板希望对外暴露的公共能力。虽然不是所有文件都在这里导出，但它是理解这个目录边界的最好入口。

第二步看 `CfgSliderInput.tsx`、`QualitySelect.tsx`、`SizeSelect.tsx`。这几个文件很短，能快速理解本目录最常见的模式：通过 `useGenerationConfigParam` 绑定某个配置 key，再渲染一个 UI 控件。

第三步看 `ImageNum.tsx`。它比普通参数控件多了自定义编辑态、服务端配置限制和预设值逻辑，适合理解“组件内部交互状态”和“全局配置状态”的区别。

第四步看 `DimensionControlGroup.tsx` 和 `AspectRatioSelect/index.tsx`。先看组合组件，再看比例选择器。这样可以理解 `AspectRatioSelect` 是纯 UI 选择器，而真正的宽高联动逻辑来自 `useDimensionControl`。

第五步看 `ModelSelect/index.tsx` 和 `ImageModelItem.tsx`。这里能看到配置面板如何接入 provider/model 体系，也能看到没有 provider、没有模型时如何引导用户去设置页。

第六步看 `MultiImagesUpload/index.tsx` 和 `ImageManageModal.tsx`。这是目录里逻辑最重的一组，涉及本地预览、上传进度、文件校验、弹窗管理、回传 URL 和尺寸信息。建议最后读，否则容易被上传细节分散注意力。

最后再回头看 `ImageUpload.tsx`、`ImageUrl.tsx`、`ImageUrlsUpload.tsx`、`ResolutionSelect.tsx`、`SeedNumberInput.tsx`、`StepsSliderInput.tsx`。这些根据当前片段推断大概率是具体参数或参考图输入的薄封装，阅读时重点看它们绑定的是哪个 config key，以及最终通过什么方式把值写回 store 或父组件。

## 常见误区

不要把这个目录理解成“图像生成业务核心”。它主要是配置面板的 UI 层和交互层。真正的生成请求、模型能力判断、schema 约束、任务提交逻辑应该在 store、service 或更上层的 feature 中。

不要在每个组件里寻找完整业务规则。比如 `DimensionControlGroup` 看起来只是在设置 width 和 height，但宽高约束、比例锁定后的联动行为，大概率封装在 `useDimensionControl` 和相关 generation config store 中。组件只是调用 hook 暴露出来的方法。

不要认为所有选项都是写死的。`QualitySelect`、`SizeSelect`、`CfgSliderInput` 这类组件的选项、边界和值都来自 `useGenerationConfigParam`。这意味着不同模型可能有不同参数范围，组件只是按当前 schema 渲染。

不要忽略空状态。`ModelSelect` 专门处理了没有 provider、provider 下没有模型的场景，并把用户引导到设置页。这类逻辑对实际产品体验很重要，不只是边缘情况。

不要把 `MultiImagesUpload` 的 `value` 当成文件对象数组。它对外主要接收和输出 URL 数组；新文件只在上传过程中作为临时状态存在。上传完成后，父级拿到的是远程 URL，而不是浏览器本地的 `File`。

不要忘记 blob URL 清理。`MultiImagesUpload` 创建本地预览后会在上传完成或组件卸载时调用 `URL.revokeObjectURL`。如果修改这段逻辑，漏掉清理可能导致浏览器内存泄漏。

不要误以为 `onChange` 的返回形态永远是 `string[]`。`MultiImagesUpload` 支持兼容旧 API 的 `string[]`，也支持新 API `{ urls, dimensions }`。上层调用时必须能处理这两种返回值，尤其是首次上传单张图片自动带尺寸的场景。

不要只看 `ConfigPanel/index.ts` 判断全部组件使用情况。当前片段显示该入口没有导出 `ModelSelect`、`MultiImagesUpload`、`ImageUrl`、`ImageUrlsUpload` 等文件，因此这些组件可能被直接路径引用，或作为内部组件被其他文件消费。若要改动导出关系，需要先查调用方。
