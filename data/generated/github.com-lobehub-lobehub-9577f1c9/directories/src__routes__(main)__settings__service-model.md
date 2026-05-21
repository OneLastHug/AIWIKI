# 目录：src/routes/(main)/settings/service-model

## 它负责什么

`src/routes/(main)/settings/service-model` 是设置页里“服务模型”页签的路由页面入口。这个目录目前只有一个文件：

- `index.tsx`

它本身不实现复杂业务逻辑，而是把几个设置模块组合成一个页面：

1. 渲染设置页标题：`SettingHeader title={t('tab.serviceModel')}`
2. 渲染核心的模型分配表单：`ModelAssignmentsForm`
3. 根据服务端 feature flag 条件渲染语音识别/语音合成相关设置：`STT`、`OpenAI`
4. 根据服务端 feature flag 条件渲染图像生成默认数量设置：`Image`

从架构分层看，它属于 `src/routes` 下的“薄路由页面”：页面入口负责组合 feature，不直接承载模型选择、用户设置持久化、表单更新等业务细节。真正的业务 UI 在 `src/features/ServiceModel`、`settings/tts/features`、`settings/image/features` 等位置。

## 关键组成

### `index.tsx`

核心代码结构如下：

```tsx
'use client';

import { useTranslation } from 'react-i18next';

import { ModelAssignmentsForm } from '@/features/ServiceModel';
import SettingHeader from '@/routes/(main)/settings/features/SettingHeader';
import { featureFlagsSelectors, useServerConfigStore } from '@/store/serverConfig';

import Image from '../image/features/Image';
import OpenAI from '../tts/features/OpenAI';
import STT from '../tts/features/STT';

const Page = () => {
  const { t } = useTranslation('setting');
  const { enableSTT, showAiImage } = useServerConfigStore(featureFlagsSelectors);

  return (
    <>
      <SettingHeader title={t('tab.serviceModel')} />
      <ModelAssignmentsForm />
      {enableSTT && (
        <>
          <STT />
          <OpenAI />
        </>
      )}
      {showAiImage && <Image />}
    </>
  );
};

export default Page;
```

这个文件有几个重点：

- `'use client'`：说明这是客户端组件，需要在浏览器侧使用 hooks 和 Zustand store。
- `useTranslation('setting')`：从 `setting` 命名空间读取设置页文案，标题 key 是 `tab.serviceModel`。
- `useServerConfigStore(featureFlagsSelectors)`：读取服务端配置里的功能开关。
- `ModelAssignmentsForm`：页面最核心的“模型分配”设置表单。
- `STT` / `OpenAI` / `Image`：从相邻 settings 子页面复用过来的设置块，不是本目录私有实现。

### `ModelAssignmentsForm`

`ModelAssignmentsForm` 位于：

```text
src/features/ServiceModel/ModelAssignmentsForm.tsx
```

并通过：

```text
src/features/ServiceModel/index.ts
```

导出：

```ts
export { default as ModelAssignmentsForm } from './ModelAssignmentsForm';
```

它负责配置不同系统能力使用哪个模型。表单分成两组：

- `serviceModel.modelAssignments.title`
- `serviceModel.optionalFeatures.title`

第一组包含默认助手和多个系统 Agent 模型：

```ts
const SYSTEM_AGENT_MODEL_ITEMS = [
  { key: 'topic' },
  { key: 'generationTopic' },
  { key: 'translation' },
  { key: 'historyCompress' },
  { key: 'agentMeta' },
];
```

这些项目大致对应：

- 话题识别/命名
- 生成话题
- 翻译
- 历史压缩
- Agent 元信息生成

第二组是可选功能：

```ts
const OPTIONAL_FEATURE_ITEMS = [
  { key: 'inputCompletion' },
  { key: 'promptRewrite' },
];
```

它们除了模型选择外，还带有 `Switch` 开关，用于启用或关闭对应能力。

`ModelAssignmentsForm` 的数据来源主要是 `useUserStore`：

- `settingsSelectors.defaultAgent(s)`：读取默认助手配置
- `settingsSelectors.currentSystemAgent(s)`：读取系统 Agent 配置
- `s.updateDefaultAgent`：更新默认助手模型
- `s.updateSystemAgent`：更新系统 Agent 模型或开关
- `s.isUserStateInit`：判断用户状态是否初始化完成

在用户状态还没有初始化完成时，它会渲染：

```tsx
<Skeleton active paragraph={{ rows: 8 }} title={false} />
```

模型选择控件统一使用：

```tsx
<ModelSelect showAbility={false} />
```

`showAbility={false}` 表示这个场景只关心模型选择本身，不展示模型能力标签或能力信息。

### `STT`

`STT` 位于：

```text
src/routes/(main)/settings/tts/features/STT.tsx
```

在 `service-model/index.tsx` 中只有当 `enableSTT` 为真时才渲染。

它负责语音转文字相关设置，使用 `useUserStore(settingsSelectors.currentSettings)` 读取 `tts` 设置，然后通过 `setSettings({ tts: values })` 持久化修改。

它包含两个表单项：

- `sttServer`：选择 STT 服务
- `sttAutoStop`：是否自动停止语音识别

### `OpenAI`

`OpenAI` 位于：

```text
src/routes/(main)/settings/tts/features/OpenAI.tsx
```

同样只有当 `enableSTT` 为真时才渲染。它配置 OpenAI 语音相关模型：

- `['openAI', 'ttsModel']`
- `['openAI', 'sttModel']`

也就是说，虽然这个模块名字是 `OpenAI`，但它在设置结构里挂在 `tts.openAI` 下，分别控制 TTS 和 STT 使用的 OpenAI 模型。

### `Image`

`Image` 位于：

```text
src/routes/(main)/settings/image/features/Image.tsx
```

只有当 `showAiImage` 为真时才渲染。

它负责图像生成默认数量设置，读取：

```ts
settingsSelectors.currentImageSettings
```

并通过：

```ts
setSettings({ image: values })
```

更新用户图像设置。

核心表单项是：

```ts
name: 'defaultImageNum'
```

输入组件是：

```tsx
<FormSliderWithInput
  disabled={isUpdating}
  max={MAX_DEFAULT_IMAGE_NUM}
  min={MIN_DEFAULT_IMAGE_NUM}
  step={1}
/>
```

也就是滑块加数字输入框的组合。

## 上下游关系

### 上游：settings 页签容器

这个目录不是直接被 React Router 单独作为独立路由树加载，而是作为 settings 页签内容的一部分被 settings 容器调用。

普通 Web 版本的映射在：

```text
src/routes/(main)/settings/features/componentMap.ts
```

其中：

```ts
[SettingsTabs.ServiceModel]: dynamic(() => import('../service-model'), {
  loading: loading('Settings > ServiceModel'),
}),
```

说明 `service-model` 页签是动态加载的。进入该页签时，才会 import `../service-model`。

桌面版本的映射在：

```text
src/routes/(main)/settings/features/componentMap.desktop.ts
```

其中：

```ts
import ServiceModel from '../service-model';

export const componentMap = {
  [SettingsTabs.ServiceModel]: ServiceModel,
};
```

桌面版本使用静态 import，而不是 dynamic import。

实际渲染发生在：

```text
src/routes/(main)/settings/features/SettingsContent.tsx
```

核心逻辑是：

```tsx
const Component = componentMap[tab as keyof typeof componentMap] || componentMap.appearance;
return <Component {...componentProps} />;
```

对于 `SettingsTabs.ServiceModel`，`SettingsContent` 会额外传入 `mobile`：

```ts
[
  SettingsTabs.About,
  SettingsTabs.ServiceModel,
  SettingsTabs.Provider,
  SettingsTabs.Profile,
  SettingsTabs.Stats,
  SettingsTabs.Usage,
  SettingsTabs.Security,
  ...
].includes(tab as any)
```

不过根据当前片段，`service-model/index.tsx` 的 `Page` 组件没有声明 props，也没有使用 `mobile`。这意味着目前传入的 `mobile` 对该页面没有实际影响，可能只是 settings 容器为了多个页签统一处理而保留的兼容参数。

### 上游：旧页签重定向

`SettingsContent.tsx` 里还有一段重定向映射：

```ts
const REDIRECT_MAP: Record<string, string> = {
  [SettingsTabs.Common]: SettingsTabs.Appearance,
  [SettingsTabs.ChatAppearance]: SettingsTabs.Appearance,
  [SettingsTabs.Agent]: SettingsTabs.ServiceModel,
  [SettingsTabs.TTS]: SettingsTabs.ServiceModel,
  [SettingsTabs.Image]: SettingsTabs.ServiceModel,
};
```

这说明以前可能存在独立的 `Agent`、`TTS`、`Image` 设置页签，现在它们会被重定向到 `ServiceModel`。

根据当前片段推断：`service-model` 是一次设置页整合后的入口，把“默认 Agent 模型”“系统 Agent 模型”“语音模型”“图像默认设置”集中到一个页签里。依据是旧的 `Agent`、`TTS`、`Image` tab 都被重定向到了 `SettingsTabs.ServiceModel`，而该页面又直接组合了模型分配、STT/OpenAI、Image 三类设置块。

### 上游：左侧设置菜单

设置菜单的分类 hook 在：

```text
src/routes/(main)/settings/hooks/useCategory.tsx
```

其中 `ServiceModel` 出现在 Agent 分组里：

```ts
{
  icon: Sparkles,
  key: SettingsTabs.ServiceModel,
  label: t('tab.serviceModel'),
}
```

所以用户在设置页左侧点击“服务模型”菜单项时，会激活 `SettingsTabs.ServiceModel`，随后 `SettingsContent` 根据 `componentMap` 渲染本目录页面。

### 下游：用户设置 store

本目录直接或间接依赖两个 store：

```ts
useServerConfigStore
useUserStore
```

`useServerConfigStore(featureFlagsSelectors)` 决定页面中哪些设置块可见：

- `enableSTT` 控制 `STT` 和 `OpenAI`
- `showAiImage` 控制 `Image`

`useUserStore` 由下游组件使用，用于读取和更新用户设置：

- `ModelAssignmentsForm` 更新默认助手和系统 Agent 模型
- `STT` / `OpenAI` 更新 `tts` 设置
- `Image` 更新 `image` 设置

### 下游：表单和 UI 组件

该页面的 UI 主要由下游组件实现：

- `@lobehub/ui` 的 `Form`、`Flexbox`、`Icon`、`Skeleton`、`Select`
- `antd` 的 `Switch`
- `lucide-react` 的 `Loader2Icon`
- 本项目的 `ModelSelect`
- 本项目的 `FormSliderWithInput`

所以 `service-model/index.tsx` 不是“表单实现文件”，而是“设置块组合文件”。

## 运行/调用流程

一个典型调用流程如下：

1. 用户进入 settings 页面，例如 `/settings/serviceModel` 或对应的 SPA 路由。
2. settings 容器读取当前激活 tab，也就是 `SettingsTabs.ServiceModel`。
3. `SettingsContent` 在 `componentMap` 中找到 `SettingsTabs.ServiceModel` 对应组件。
4. Web 版本通过 dynamic import 加载 `../service-model`；桌面版本通过静态 import 使用 `ServiceModel`。
5. `service-model/index.tsx` 执行 `Page` 组件。
6. `Page` 使用 `useTranslation('setting')` 获取标题文案。
7. `Page` 使用 `useServerConfigStore(featureFlagsSelectors)` 获取功能开关。
8. 页面首先渲染 `SettingHeader`，标题是 `t('tab.serviceModel')`。
9. 页面渲染 `ModelAssignmentsForm`。
10. `ModelAssignmentsForm` 从 `useUserStore` 读取默认助手和系统 Agent 配置。
11. 如果用户状态未初始化，`ModelAssignmentsForm` 显示 `Skeleton`。
12. 初始化完成后，`ModelAssignmentsForm` 渲染模型选择表单。
13. 用户修改默认助手模型时，调用 `updateDefaultAgent({ config: { model, provider } })`。
14. 用户修改系统 Agent 模型时，调用 `updateSystemAgent(key, value)`。
15. 用户切换 `inputCompletion` 或 `promptRewrite` 时，也调用 `updateSystemAgent(key, { enabled })`。
16. 如果 `enableSTT` 为真，页面继续渲染 `STT` 和 `OpenAI` 设置块。
17. `STT` 修改时调用 `setSettings({ tts: values })`。
18. `OpenAI` 修改时也调用 `setSettings({ tts: values })`，但字段落在 `tts.openAI` 下。
19. 如果 `showAiImage` 为真，页面渲染 `Image` 设置块。
20. `Image` 修改默认图像数量时调用 `setSettings({ image: values })`。

可以把这个页面理解成一个“设置聚合页”：

```text
SettingsContent
  -> componentMap[SettingsTabs.ServiceModel]
    -> src/routes/(main)/settings/service-model/index.tsx
      -> SettingHeader
      -> ModelAssignmentsForm
        -> useUserStore.updateDefaultAgent
        -> useUserStore.updateSystemAgent
      -> STT, OpenAI if enableSTT
        -> useUserStore.setSettings({ tts })
      -> Image if showAiImage
        -> useUserStore.setSettings({ image })
```

## 小白阅读顺序

建议按下面顺序阅读，不要一开始就跳进 store 内部：

1. `src/routes/(main)/settings/service-model/index.tsx`

   先看页面组合关系。这个文件很短，能快速建立全局印象：页面标题、模型分配、语音设置、图像设置。

2. `src/routes/(main)/settings/features/componentMap.ts`

   看 `SettingsTabs.ServiceModel` 如何映射到 `../service-model`。这一步能理解“为什么访问 settings 的某个 tab 会渲染这个目录”。

3. `src/routes/(main)/settings/features/SettingsContent.tsx`

   看 settings 页签容器如何根据 `activeTab` 渲染组件，以及旧 tab 如何重定向到 `ServiceModel`。

4. `src/routes/(main)/settings/hooks/useCategory.tsx`

   看左侧菜单如何把 `SettingsTabs.ServiceModel` 放到 Agent 分组里。这里能理解用户入口。

5. `src/features/ServiceModel/index.ts`

   看 feature 对外导出什么。这里只有一行导出，很适合作为进入 feature 的入口。

6. `src/features/ServiceModel/ModelAssignmentsForm.tsx`

   重点阅读。这里是本页最核心的业务逻辑，包含默认助手模型、系统 Agent 模型、可选功能开关和更新逻辑。

7. `src/routes/(main)/settings/tts/features/STT.tsx`

   了解 `enableSTT` 打开后，语音转文字设置如何读写 `tts` 配置。

8. `src/routes/(main)/settings/tts/features/OpenAI.tsx`

   了解 OpenAI 的 TTS/STT 模型选项如何挂到 `tts.openAI` 下。

9. `src/routes/(main)/settings/image/features/Image.tsx`

   了解 `showAiImage` 打开后，图像生成默认数量如何读写 `image` 配置。

10. 最后再追 store

   如果还想深入，可以继续看：

   - `useUserStore`
   - `settingsSelectors`
   - `useServerConfigStore`
   - `featureFlagsSelectors`
   - `SettingsTabs`

   但这些已经超出本目录本身，是更底层的状态管理和配置系统。

## 常见误区

1. 误以为 `service-model` 目录实现了完整业务

   这个目录目前只有 `index.tsx`，它主要负责组合。真正的模型分配逻辑在 `src/features/ServiceModel/ModelAssignmentsForm.tsx`。

2. 误以为 `STT`、`OpenAI`、`Image` 属于 `service-model` feature

   它们其实来自相邻 settings 子目录：

   - `../tts/features/STT`
   - `../tts/features/OpenAI`
   - `../image/features/Image`

   `service-model` 只是复用它们。

3. 误以为所有用户都能看到语音和图像设置

   不是。它们受服务端 feature flag 控制：

   - `enableSTT` 为真才显示 `STT` 和 `OpenAI`
   - `showAiImage` 为真才显示 `Image`

4. 误以为 `mobile` props 会影响这个页面

   `SettingsContent` 会给 `SettingsTabs.ServiceModel` 传 `mobile`，但根据当前 `index.tsx` 片段，`Page` 没有接收或使用这个 props。因此当前页面逻辑不区分 mobile/desktop。这个判断只基于当前片段，未来如果 `Page` 增加 props，则需要重新确认。

5. 误以为 `Agent`、`TTS`、`Image` 还是独立设置页签

   `SettingsContent.tsx` 已经把这些旧 tab 重定向到 `ServiceModel`：

   ```ts
   [SettingsTabs.Agent]: SettingsTabs.ServiceModel,
   [SettingsTabs.TTS]: SettingsTabs.ServiceModel,
   [SettingsTabs.Image]: SettingsTabs.ServiceModel,
   ```

   所以当前 UI 入口上，它们被整合到了服务模型页。

6. 误以为 `ModelAssignmentsForm` 只设置默认模型

   它不仅设置默认助手模型，还设置多个系统 Agent 的模型：

   - `topic`
   - `generationTopic`
   - `translation`
   - `historyCompress`
   - `agentMeta`

   同时还管理两个可选能力：

   - `inputCompletion`
   - `promptRewrite`

7. 误以为可选功能关闭后模型选择也消失

   当前实现中，可选功能关闭时只是 label 透明度降低，并通过 `Switch` 控制 `enabled`。`ModelSelect` 仍然存在，用户仍能看到对应模型配置。

8. 误以为 loading 是整个页面级别的

   这里的 loading 粒度较细：

   - `ModelAssignmentsForm` 用 `loadingKey` 区分当前更新的是默认助手、某个系统 Agent，还是可选功能。
   - `STT` 和 `OpenAI` 各自有本地 `loading`。
   - `Image` 使用本地 `isUpdating`。

   所以每个设置块都独立显示保存中的状态。

9. 误以为 Web 和 Desktop 加载方式完全一样

   Web 的 `componentMap.ts` 使用 dynamic import，并显示 `BrandTextLoading`；Desktop 的 `componentMap.desktop.ts` 使用静态 import。两者最终指向同一个 `../service-model`，但加载方式不同。

10. 误以为这里应该新增复杂 UI

   按本仓库的路由约定，`src/routes` 下的页面应保持薄层。如果要扩展“服务模型”的核心业务 UI，更合适的位置通常是 `src/features/ServiceModel`，而不是把大量逻辑直接写进 `src/routes/(main)/settings/service-model/index.tsx`。
