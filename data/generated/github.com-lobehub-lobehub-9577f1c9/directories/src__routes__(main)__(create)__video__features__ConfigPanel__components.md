# 目录：src/routes/(main)/(create)/video/features/ConfigPanel/components

## 它负责什么

这个目录是“视频生成配置面板”的局部 UI 组件目录，主要负责两个配置入口：

1. 视频生成模型选择：让用户从已启用的视频模型 provider/model 列表中选择当前视频生成模型。
2. 首尾帧图片上传：把图片上传组件适配到视频生成配置里的 `imageUrl` / `endImageUrl` 参数。

从当前片段看，它不是完整的 `ConfigPanel` 本体，而是 `ConfigPanel` 下面的可复用小组件集合。真正的配置表单、布局、参数项组合逻辑应在上层 `ConfigPanel` 或邻近目录中完成；本目录只处理局部控件的渲染和与 store 参数的连接。

目录内文件：

```text
src/routes/(main)/(create)/video/features/ConfigPanel/components
├── FrameUpload.tsx
└── ModelSelect
    ├── VideoModelItem.tsx
    └── index.tsx
```

当前上层入口 `src/routes/(main)/(create)/video/features/ConfigPanel/index.ts` 只导出了：

```ts
export { default as FrameUpload } from '@/routes/(main)/(create)/video/features/ConfigPanel/components/FrameUpload';
export { default as VideoModelItem } from '@/routes/(main)/(create)/video/features/ConfigPanel/components/ModelSelect/VideoModelItem';
```

注意：`ModelSelect/index.tsx` 在当前入口片段中没有被统一导出。它可能被调用方直接按完整路径引用，或者处于后续待接入状态；根据当前片段无法确认其真实调用方。

## 关键组成

### `FrameUpload.tsx`

`FrameUpload` 是一个很薄的适配组件，用于把图片上传能力接入视频生成参数。

它的 props 只有一个：

```ts
interface FrameUploadProps {
  paramName: 'endImageUrl' | 'imageUrl';
}
```

这说明它只服务两个视频图片参数：

- `imageUrl`：通常可理解为视频生成的起始图、参考图或首帧图。
- `endImageUrl`：通常可理解为视频生成的结束图或尾帧图。

核心依赖：

```ts
import { ImageUpload } from '@/routes/(main)/(create)/image/features/ConfigPanel';
import { useVideoGenerationConfigParam } from '@/store/video/slices/generationConfig/hooks';
```

它没有自己实现上传 UI，而是复用图片生成配置面板里的 `ImageUpload`。视频侧只做三件事：

1. 通过 `useVideoGenerationConfigParam(paramName)` 读取当前参数值和参数约束。
2. 把 `maxFileSize`、`imageConstraints`、`value` 传给 `ImageUpload`。
3. 在 `onChange` 时把上传结果规整为 URL，然后写回视频生成配置 store。

`handleChange` 支持两种输入形态：

```ts
data?: string | { dimensions?: { height: number; width: number }; url: string }
```

如果 `data` 是字符串，就直接当 URL；如果是对象，就取 `data.url`；如果没有数据，则写入 `null`。

```ts
const url = typeof data === 'string' ? data : data?.url;
setValue((url ?? null) as any);
```

这里的 `as any` 是一个值得注意的类型折中：`setValue` 可能是根据 `paramName` 推导出来的强类型 setter，但 `handleChange` 的通用上传返回值与具体参数类型没有完全对齐，所以用 `any` 绕过类型检查。业务上它实际写入的是 `string | null`。

### `ModelSelect/index.tsx`

`ModelSelect` 是视频模型选择器。它使用 `@lobehub/ui` 的 `Select`，并从两个 store 读取数据：

```ts
import { useAiInfraStore } from '@/store/aiInfra';
import { aiProviderSelectors } from '@/store/aiInfra/slices/aiProvider/selectors';
import { useVideoStore } from '@/store/video';
import { videoGenerationConfigSelectors } from '@/store/video/selectors';
```

它关心三类状态：

1. 当前视频生成配置中的 `model`。
2. 当前视频生成配置中的 `provider`。
3. 当前已启用的视频模型 provider 列表。

当前模型和 provider 来自：

```ts
const [currentModel, currentProvider] = useVideoStore((s) => [
  videoGenerationConfigSelectors.model(s),
  videoGenerationConfigSelectors.provider(s),
]);
```

可选模型列表来自：

```ts
const enabledVideoModelList = useAiInfraStore(aiProviderSelectors.enabledVideoModelList);
```

用户选择模型时调用：

```ts
setModelAndProviderOnSelect(model, provider);
```

也就是说，这个组件不是只设置 `model`，而是同时设置 `model + provider`。这是视频模型选择的关键，因为同一个模型名理论上可能出现在不同 provider 下，必须用 provider disambiguate。

#### options 构造逻辑

`ModelSelect` 用 `useMemo` 构造 `Select` 的 `options`，主要分三种情况。

第一种：没有任何已启用的视频 provider。

```ts
if (enabledVideoModelList.length === 0) {
  return [
    {
      disabled: true,
      label: emptyProvider UI,
      onClick: () => navigate('/settings/provider/all'),
      value: 'no-provider',
    },
  ];
}
```

UI 上显示空 provider 提示，并带一个箭头图标。根据当前片段推断，它希望引导用户去 provider 设置页。

第二种：只有一个 provider。

```ts
if (enabledVideoModelList.length === 1) {
  const provider = enabledVideoModelList[0];
  return getVideoModels(provider);
}
```

这种情况下不显示 provider 分组标题，直接展示该 provider 下的视频模型。

第三种：有多个 provider。

```ts
return enabledVideoModelList.map((provider) => ({
  label: provider header,
  options: getVideoModels(provider),
}));
```

多 provider 时使用分组选项。每个分组标题里渲染 `ProviderItemRender`，并放一个 `LucideBolt` 的 `ActionIcon`，点击后跳转到对应 provider 设置页：

```ts
navigate(`/settings/provider/${provider.id}`);
```

这里 `e.stopPropagation()` 用来避免点击设置图标时触发 Select 分组选中或展开相关行为。

#### 模型 value 格式

每个模型 option 的 value 使用：

```ts
value: `${provider.id}/${model.id}`
```

选择时再拆回来：

```ts
const model = value.split('/').slice(1).join('/');
const provider = (option as unknown as ModelOption).provider;
```

这里没有简单使用 `value.split('/')[1]`，而是 `slice(1).join('/')`，说明 `model.id` 本身可能包含 `/`。这是一个重要细节：value 的第一个 `/` 前面是 provider，后面的完整字符串才是 model id。

#### labelRender

`labelRender` 用于控制 Select 已选中值在输入框里的展示形式。

它会从 `enabledVideoModelList` 扁平化查找当前选中的模型：

```ts
const modelInfo = enabledVideoModelList
  .flatMap((provider) =>
    provider.children.map((model) => ({ ...model, providerId: provider.id })),
  )
  .find((model) => props.value === `${model.providerId}/${model.id}`);
```

找到后渲染：

```tsx
<VideoModelItem
  {...modelInfo}
  providerId={modelInfo.providerId}
  showBadge={false}
  showPopover={false}
/>
```

也就是说，下拉列表里可以显示更完整的信息；选中后展示时会隐藏 badge 和 popover，让输入框更简洁。

#### 样式

`ModelSelect` 使用 `createStaticStyles` 和 `cssVar` 定义 Select popup 样式：

```ts
const styles = createStaticStyles(({ css, cssVar }) => ({
  popup: css`
    &.${prefixCls}-select-dropdown .${prefixCls}-select-item-option {
      margin-block: 1px;
      margin-inline: 4px;
      padding-block: 8px;
      padding-inline: 8px;
      border-radius: ${cssVar.borderRadiusSM};
    }
    ...
  `,
}));
```

这是 LobeHub 代码库推荐的零运行时样式写法之一。它只微调下拉项间距、内边距、圆角和选中背景，不承担布局业务。

### `ModelSelect/VideoModelItem.tsx`

`VideoModelItem` 是视频模型项的包装组件。

```ts
import type { AiModelForSelect } from 'model-bank';
import GenerationModelItem from '@/routes/(main)/(create)/components/GenerationModelItem';
```

它的 props 基于 `model-bank` 的 `AiModelForSelect`，额外支持：

```ts
type VideoModelItemProps = AiModelForSelect & {
  providerId?: string;
  showBadge?: boolean;
  showPopover?: boolean;
};
```

组件实现很简单：

```tsx
const VideoModelItem = (props: VideoModelItemProps) => (
  <GenerationModelItem {...props} priceKind="video" showPrice={true} />
);
```

这说明 LobeHub 对“生成类模型项”有一个通用展示组件 `GenerationModelItem`，视频场景只是在它之上固定两个参数：

- `priceKind="video"`：价格信息按视频模型维度展示。
- `showPrice={true}`：展示价格。

因此，`VideoModelItem` 的价值不是复杂逻辑，而是把“视频模型展示规则”固定下来，避免调用方每次重复传 `priceKind` 和 `showPrice`。

## 上下游关系

### 上游

本目录的上游主要是视频创建页面的 `ConfigPanel` 或其他视频创建配置 UI。

根据路径可以看出它位于：

```text
src/routes/(main)/(create)/video/features/ConfigPanel/components
```

也就是主站创建流里的 video 功能配置面板局部组件。上层应该负责：

- 决定哪些配置项显示。
- 决定 `FrameUpload` 用于 `imageUrl` 还是 `endImageUrl`。
- 决定是否渲染 `ModelSelect`。
- 管理整体表单布局和提交/生成行为。

当前读取到的入口 `ConfigPanel/index.ts` 只导出了 `FrameUpload` 和 `VideoModelItem`。没有看到 `ModelSelect` 的导出或调用方，因此关于 `ModelSelect` 的上游调用只能根据组件命名和实现推断：它应服务于视频生成配置面板中的“模型选择”配置项。

### 下游

本目录的下游依赖可以分成四类。

第一类是 UI 组件：

- `@lobehub/ui`：`Select`、`Flexbox`、`ActionIcon`、`Icon`。
- `antd-style`：`createStaticStyles`、`cssVar`。
- `lucide-react`：`LucideArrowRight`、`LucideBolt`。
- 图片配置侧的 `ImageUpload`。
- 通用生成模型展示组件 `GenerationModelItem`。
- 通用 provider 展示组件 `ProviderItemRender`。

第二类是 store：

- `useVideoStore`
- `videoGenerationConfigSelectors`
- `useVideoGenerationConfigParam`
- `useAiInfraStore`
- `aiProviderSelectors.enabledVideoModelList`

视频生成配置值来自 `useVideoStore`，视频模型候选列表来自 `useAiInfraStore`。

第三类是路由：

- `useNavigate` from `react-router-dom`

当 provider 或 model 配置为空时，组件会跳转到设置页：

```text
/settings/provider/all
/settings/provider/:providerId
```

第四类是 i18n：

- `useTranslation('components')`

使用的 key 包括：

```text
ModelSwitchPanel.emptyModel
ModelSwitchPanel.emptyProvider
ModelSwitchPanel.goToSettings
```

这些文案不写死在组件里，而是走 `components` namespace。

## 运行/调用流程

### 首尾帧上传流程

1. 上层渲染 `FrameUpload`，并传入 `paramName`。
2. `FrameUpload` 调用 `useVideoGenerationConfigParam(paramName)`。
3. hook 返回当前值 `value`、写入函数 `setValue`、上传大小限制 `maxFileSize`、图片尺寸约束 `imageConstraints`。
4. `FrameUpload` 渲染图片侧复用的 `ImageUpload`。
5. 用户上传、替换或清空图片时，`ImageUpload` 调用 `onChange`。
6. `FrameUpload.handleChange` 把返回值统一转换为 URL 或 `null`。
7. `setValue` 写回视频生成配置 store。
8. 上层视频配置或生成流程读取更新后的 `imageUrl` / `endImageUrl`。

这个流程的重点是：`FrameUpload` 自己不关心上传服务、图片存储、尺寸校验细节；这些由 `ImageUpload` 和 `useVideoGenerationConfigParam` 提供。它只做“视频配置参数适配”。

### 模型选择流程

1. `ModelSelect` 从 `useVideoStore` 读取当前 `model` 和 `provider`。
2. 它从 `useAiInfraStore` 读取 `enabledVideoModelList`。
3. 根据 provider 数量生成 Select options：
   - 0 个 provider：显示空 provider 提示。
   - 1 个 provider：直接显示模型列表。
   - 多个 provider：按 provider 分组显示模型。
4. 每个模型用 `VideoModelItem` 渲染。
5. `VideoModelItem` 内部转发到 `GenerationModelItem`，并固定为视频价格展示。
6. 用户选择一个模型时，Select 的 `value` 形如 `providerId/modelId`。
7. `onChange` 拆出 `model`，并从 option 上读取 `provider`。
8. 如果新旧值不同，调用 `setModelAndProviderOnSelect(model, provider)`。
9. 视频生成配置 store 更新后，面板和后续生成请求使用新的 provider/model。

空状态下的特殊 value：

```text
no-provider
providerId/empty
```

这些值不会触发模型设置：

```ts
if (value === 'no-provider' || value.includes('/empty')) return;
```

这可以避免把空状态 option 误写进视频生成配置。

## 小白阅读顺序

1. 先看 `VideoModelItem.tsx`  
   这个文件最简单。它说明视频模型项只是通用 `GenerationModelItem` 的视频场景包装。理解它以后，再看 `ModelSelect` 里为什么可以直接用 `<VideoModelItem {...model} />`。

2. 再看 `FrameUpload.tsx`  
   重点看 `paramName`、`useVideoGenerationConfigParam` 和 `ImageUpload`。这个文件可以帮助理解 LobeHub 常见模式：组件本身不保存业务状态，而是通过 store hook 绑定配置参数。

3. 然后看 `ModelSelect/index.tsx` 的状态读取部分  
   先理解这几行：

   ```ts
   const [currentModel, currentProvider] = useVideoStore(...)
   const setModelAndProviderOnSelect = useVideoStore(...)
   const enabledVideoModelList = useAiInfraStore(...)
   ```

   这三组数据分别回答：“当前选中了什么”“怎么写回选择”“可选项从哪里来”。

4. 接着看 `getVideoModels`  
   它是把 provider 下的 children 模型转换为 Select option 的核心函数。

5. 最后看 `onChange` 和 `labelRender`  
   `onChange` 负责把 UI 选择写回 store；`labelRender` 负责让选中后的展示更简洁。这两个位置能帮助理解 `Select` 的数据结构和展示结构是分开的。

## 常见误区

1. 误以为 `FrameUpload` 负责真正上传图片  
   它不负责上传实现。真正的上传 UI 和上传行为来自图片创建配置里的 `ImageUpload`。`FrameUpload` 只是把上传结果写入视频生成配置参数。

2. 误以为 `FrameUpload` 可以绑定任意视频参数  
   它的 `paramName` 类型被限制为 `'endImageUrl' | 'imageUrl'`。如果要支持别的图片参数，需要先确认 `useVideoGenerationConfigParam` 是否支持该参数，再扩展类型和业务约束。

3. 误以为模型 value 可以简单按 `/` 分成两段  
   `ModelSelect` 的 value 是 `${provider.id}/${model.id}`，但 `model.id` 可能自己包含 `/`。所以代码用：

   ```ts
   value.split('/').slice(1).join('/')
   ```

   这是为了保留完整 model id。

4. 误以为选择模型只需要保存 model id  
   这里必须同时保存 provider 和 model。`setModelAndProviderOnSelect(model, provider)` 的存在说明 provider 是视频生成配置的一部分，不是纯展示信息。

5. 误以为 `VideoModelItem` 是复杂组件  
   它只是 `GenerationModelItem` 的视频场景包装。真正的模型名称、徽标、popover、价格展示等细节大概率在 `GenerationModelItem` 内部。

6. 误以为 `ModelSelect` 已经一定通过 `ConfigPanel/index.ts` 暴露给外部  
   当前读取到的 `ConfigPanel/index.ts` 只导出了 `FrameUpload` 和 `VideoModelItem`，没有导出 `ModelSelect`。因此 `ModelSelect` 可能是被直接路径引用，也可能暂未接入。根据当前片段无法确认，需要进一步查看调用方才能定论。

7. 误以为空 provider / 空 model 的 option 会写入配置  
   `onChange` 明确拦截了 `no-provider` 和包含 `/empty` 的 value，因此这些空状态只用于 UI 提示或跳转引导，不应进入视频生成配置。

8. 误以为这是一个完全独立的视频配置系统  
   这个目录复用了多个跨功能模块：图片侧 `ImageUpload`、创建通用 `GenerationModelItem`、全局模型选择相关 `ProviderItemRender`、`aiInfra` provider store。它更像是视频创建流程对通用创建能力和 AI provider 能力的组合层。
