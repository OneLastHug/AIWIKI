# 目录：src/routes/(main)/settings/provider/features/ProviderConfig/UpdateProviderInfo

## 它负责什么

`UpdateProviderInfo` 是“设置 / 模型服务商 / Provider 配置”页面里，专门用于编辑自定义 AI Provider 基础信息的一个小功能目录。

它只服务于自定义 provider，不负责内置 provider 的 API Key、Base URL、模型列表、连通性检查等主配置项。它的职责更窄：在自定义 provider 的标题区域展示一个齿轮按钮，点击后打开一个 `FormModal`，允许用户更新这个自定义 provider 的展示信息和 SDK 类型，并支持删除该 provider。

从父级 `ProviderConfig/index.tsx` 可以看到它的挂载条件：

```tsx
{isCustom && <UpdateProviderInfo />}
```

也就是说，只有 `isCustom` 为真时才出现这个入口。内置 provider 走正常的 `ProviderConfig` 表单，不会显示这个“更新 provider 信息”的齿轮按钮。

这个目录实际承担三类事情：

1. 在 provider 配置卡片标题栏提供“编辑自定义 Provider 信息”的入口。
2. 通过弹窗表单更新 `name`、`description`、`logo`、`settings.sdkType` 等元信息。
3. 在保存前对 `settings` 做归一化，特别是处理 `supportResponsesApi` 和 `enableResponseApi` 的兼容关系。

## 关键组成

这个目录下有三个文件：

```text
UpdateProviderInfo/
├── index.tsx
├── SettingModal.tsx
└── normalizeProviderSettings.test.ts
```

`index.tsx` 是目录入口组件，默认导出 `UpdateProviderInfo`。

它是一个很薄的 UI 入口组件，核心逻辑是：

- 使用 `useTranslation('modelProvider')` 读取文案。
- 使用本地 `useState(false)` 维护弹窗开关 `open`。
- 通过 `useAiInfraStore(aiProviderSelectors.activeProviderConfig, isEqual)` 读取当前激活的 provider 配置。
- 渲染一个带 `SettingsIcon` 的小号文本按钮。
- 点击按钮时调用 `e.preventDefault()` 和 `e.stopPropagation()`，然后 `setOpen(true)`。
- 当 `open && providerConfig` 成立时渲染 `SettingModal`。

这里的 `preventDefault` 和 `stopPropagation` 很关键，因为这个按钮位于 provider 配置组标题区域。标题区域本身可能有折叠、跳转或其他点击行为，齿轮按钮需要只触发“打开编辑弹窗”，不能冒泡影响外层表单组。

`SettingModal.tsx` 是真正的编辑弹窗。虽然组件内部命名为 `CreateNewProvider`，但它在这里实际用于“更新已有自定义 provider”。从 props 可见它接收：

- `id: string`：当前 provider id。
- `initialValues: AiProviderDetailItem`：弹窗表单初始值。
- `open?: boolean`：是否打开。
- `onClose?: () => void`：关闭回调。

它使用的主要依赖包括：

- `FormModal`：来自 `@lobehub/ui`，承载弹窗表单。
- `Input`、`TextArea`、`Select`：表单控件。
- `ProviderIcon`：SDK 类型下拉选项中的图标。
- `App.useApp()`：拿到 antd 的 `message` 和 `modal`。
- `useNavigate()`：删除后跳转到 `/settings/provider/all`。
- `useAiInfraStore`：读取 `updateAiProvider` 和 `deleteAiProvider` 两个 store action。
- `CUSTOM_PROVIDER_SDK_OPTIONS`：自定义 provider 可选 SDK 类型列表。
- `normalizeProviderSettings`、`isResponsesApiSupportedSdkType`：保存前处理 provider settings。

`SettingModal` 的表单分为两组：

第一组是基础信息 `basicItems`：

- `id`：只展示 `initialValues.id`，不是可编辑输入框。
- `name`：provider 名称，必填。
- `description`：描述。
- `logo`：logo URL。

第二组是配置项 `configItems`：

- `settings.sdkType`：SDK 类型，必填，下拉选项来自 `CUSTOM_PROVIDER_SDK_OPTIONS`。

`CUSTOM_PROVIDER_SDK_OPTIONS` 位于相邻目录 `src/routes/(main)/settings/provider/features/customProviderSdkOptions.ts`，包含：

- `openai`
- `azure`
- `anthropic`
- `google`
- `cloudflare`
- `qwen`
- `volcengine`
- `ollama`
- `router`

其中 `router` 在 UI 展示图标时会映射成 `newapi`：

```tsx
const iconProvider = value === 'router' ? 'newapi' : (value as string);
```

这是一个纯展示层兼容处理，表示 `router` SDK 类型在图标体系中复用 `newapi` 的 provider 图标。

`normalizeProviderSettings.test.ts` 是测试文件，但它测试的不是本目录内部函数，而是相邻共享模块 `../../providerSettings` 中的：

- `isResponsesApiSupportedSdkType`
- `normalizeProviderSettings`

测试放在这个目录下，说明这个归一化逻辑主要是为了 `UpdateProviderInfo/SettingModal` 的保存流程服务。

`providerSettings.ts` 的核心规则是：

- 只有 `openai` 和 `router` 支持 Responses API。
- 当 `sdkType` 是 `openai` 或 `router` 时，自动设置 `supportResponsesApi: true`。
- 当 `sdkType` 切换到不支持 Responses API 的类型时，移除 `supportResponsesApi`。
- 会合并旧 settings 和新 settings，尽量保留无关字段，例如 `modelEditable`、`showModelFetcher`。
- 如果移除 `supportResponsesApi` 后没有任何 settings 字段，则返回 `undefined`。

## 上下游关系

上游调用方是父级 provider 配置组件：

```text
src/routes/(main)/settings/provider/features/ProviderConfig/index.tsx
```

它在构造 provider 配置组标题区域时，把 `UpdateProviderInfo` 放进 `headerExtra`：

```tsx
const headerExtra = (
  <Flexbox horizontal align={'center'} gap={8}>
    {extra}
    {isCustom && <UpdateProviderInfo />}
    {canDeactivate && ... && <EnableSwitch id={id} key={id} />}
  </Flexbox>
);
```

因此 `UpdateProviderInfo` 的上游上下文是“某个 provider 的配置卡片标题栏”。它不是单独页面，也不是路由入口，而是 provider 配置 UI 的一个局部操作按钮。

它依赖的状态来源是 `useAiInfraStore`：

- `index.tsx` 使用 `aiProviderSelectors.activeProviderConfig` 读取当前激活 provider 的完整配置。
- `SettingModal.tsx` 使用 `updateAiProvider` 保存更新。
- `SettingModal.tsx` 使用 `deleteAiProvider` 删除当前自定义 provider。

它依赖的类型来自：

```text
@/types/aiProvider
```

主要包括：

- `AiProviderDetailItem`
- `UpdateAiProviderParams`
- `AiProviderSDKType`
- `AiProviderSettings`

它依赖的 UI 和基础设施包括：

- `@lobehub/ui`
- `@lobehub/icons`
- `antd`
- `lucide-react`
- `react-i18next`
- `react-router-dom`

下游影响主要有两类。

第一类是数据层影响：调用 `updateAiProvider(id, finalValues)` 后，当前自定义 provider 的名称、描述、logo、SDK 类型、settings/config 等信息会被更新到 AI Infra store 对应的数据源中。具体持久化细节不在当前目录内，根据当前片段推断由 `useAiInfraStore` 的 action 继续向 service 或后端 API 分发。

第二类是页面流转影响：调用 `deleteAiProvider(id)` 删除后，会执行：

```tsx
navigate('/settings/provider/all');
```

也就是把用户带回 provider 总览页，避免仍停留在已经删除的 provider 配置页。

## 运行/调用流程

典型编辑流程如下：

1. 用户进入设置页中的某个自定义 provider 配置。
2. `ProviderConfig/index.tsx` 判断当前 provider 是自定义 provider，即 `isCustom === true`。
3. 标题区域渲染 `UpdateProviderInfo` 齿轮按钮。
4. `UpdateProviderInfo/index.tsx` 从 `useAiInfraStore` 读取当前激活 provider 配置 `providerConfig`。
5. 用户点击齿轮按钮。
6. 点击事件阻止默认行为和冒泡，然后设置 `open = true`。
7. 如果 `open` 为真且 `providerConfig` 存在，则渲染 `SettingModal`。
8. `SettingModal` 用 `initialValues={providerConfig}` 初始化表单。
9. 用户修改名称、描述、logo 或 `settings.sdkType`。
10. 用户点击更新按钮，触发 `onFinish(values)`。
11. `onFinish` 先设置 `loading = true`。
12. 代码构造 `finalValues`，其中 `settings` 会通过 `normalizeProviderSettings` 合并旧 settings 和新 settings。
13. 如果新的 `sdkType` 不支持 Responses API，则把 `config.enableResponseApi` 设为 `false`。
14. 调用 `updateAiProvider(id, finalValues)`。
15. 保存成功后关闭 loading，显示 `updateAiProvider.updateSuccess` 成功提示，并调用 `onClose` 关闭弹窗。

删除流程如下：

1. 用户在弹窗底部点击危险按钮“删除”。
2. 代码调用 `modal.confirm` 弹出确认框。
3. 用户确认后执行 `deleteAiProvider(id)`。
4. 删除成功后跳转到 `/settings/provider/all`。
5. 调用 `onClose` 关闭弹窗。
6. 显示 `updateAiProvider.deleteSuccess` 成功提示。

这里有一个容易忽略的兼容逻辑：`supportResponsesApi` 属于 `settings`，而 `enableResponseApi` 属于 `config`。保存时先归一化 `settings.supportResponsesApi`，再根据 SDK 支持情况关闭 `config.enableResponseApi`。也就是说，一个 SDK 如果不支持 Responses API，不仅 settings 里不会再声明支持，实际配置中的启用开关也会被强制关掉。

## 小白阅读顺序

建议按下面顺序阅读：

1. 先看 `ProviderConfig/index.tsx` 中 `headerExtra` 附近的代码，理解 `UpdateProviderInfo` 出现在什么位置，以及为什么只有 `isCustom` 时才显示。
2. 再看 `UpdateProviderInfo/index.tsx`，它很短，重点理解“齿轮按钮 + 读取 activeProviderConfig + 条件渲染 SettingModal”。
3. 接着看 `SettingModal.tsx` 的 props 和 `onFinish`，这是这个目录的核心逻辑。
4. 然后看 `basicItems` 和 `configItems`，理解弹窗里有哪些字段。
5. 再看 `features/customProviderSdkOptions.ts`，了解 SDK 类型下拉框有哪些选项。
6. 再看 `features/providerSettings.ts`，理解 `supportResponsesApi` 是如何随 `sdkType` 自动增删的。
7. 最后看 `normalizeProviderSettings.test.ts`，用测试用例反推边界行为，尤其是从 `openai/router` 切换到 `anthropic/google` 这类不支持 Responses API 的场景。

如果只想快速掌握主线，优先读：

```text
ProviderConfig/index.tsx 的 headerExtra
UpdateProviderInfo/index.tsx
UpdateProviderInfo/SettingModal.tsx 的 onFinish
features/providerSettings.ts
```

## 常见误区

第一个误区是把 `UpdateProviderInfo` 当成 provider 主配置表单。实际上它只编辑自定义 provider 的“基础资料”和 SDK 类型，不负责 API Key、代理地址、模型列表等完整配置。那些配置项在父级 `ProviderConfig/index.tsx` 的主表单里处理。

第二个误区是认为这个组件对所有 provider 生效。它只在 `isCustom` 为真时渲染。内置 provider 的标题区域显示帮助文档链接、启用开关等，不会显示这个编辑自定义 provider 信息的齿轮按钮。

第三个误区是忽略点击事件中的 `stopPropagation`。这个齿轮按钮在标题栏里，如果不阻止冒泡，点击按钮可能同时触发外层标题栏行为，导致折叠状态变化或其他副作用。

第四个误区是只看表单字段，没看保存前的归一化。`settings.sdkType` 不是简单保存；保存前会经过 `normalizeProviderSettings`，并根据 SDK 类型自动处理 `supportResponsesApi`。这保证了 `openai`、`router` 默认支持 Responses API，而 `anthropic` 等不支持的 SDK 不会残留旧的 `supportResponsesApi: true`。

第五个误区是混淆 `supportResponsesApi` 和 `enableResponseApi`。前者表示该 provider settings 是否支持 Responses API，后者表示配置里是否启用 Responses API。当 SDK 类型切换到不支持 Responses API 时，代码会同时移除/关闭相关状态，避免 UI 或运行时出现“显示可启用但实际不支持”的不一致。

第六个误区是被 `SettingModal.tsx` 内部组件名 `CreateNewProvider` 误导。这个名字看起来像“创建新 provider”，但在当前目录里它通过 `initialValues` 和 `updateAiProvider` 实现的是更新已有自定义 provider。根据当前片段推断，这可能是从创建 provider 的弹窗逻辑演化或复用而来，文件名和调用方式才是判断职责的主要依据。

第七个误区是认为删除只是本地关闭弹窗。实际删除确认后会调用 `deleteAiProvider(id)`，随后导航到 `/settings/provider/all`。这是为了让用户离开已删除 provider 的详情配置页，避免页面还引用一个不存在的 provider。
