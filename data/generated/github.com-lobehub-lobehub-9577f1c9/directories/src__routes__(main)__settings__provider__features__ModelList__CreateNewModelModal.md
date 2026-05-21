# 目录：src/routes/(main)/settings/provider/features/ModelList/CreateNewModelModal

## 它负责什么

`CreateNewModelModal` 是“设置 → 模型服务商 → 模型列表”里的新增自定义模型弹窗。用户在某个 provider 页面点击新增模型时，这个目录负责展示表单、收集模型配置、校验必填项，并把数据提交到 `aiInfra` store 的 `createNewAiModel` 动作。

它不是一个独立页面，而是嵌在 provider 设置页里的局部 UI 能力。目录内的核心职责可以分成三层：

1. `index.tsx`：弹窗容器，控制 Modal 打开关闭、提交按钮、loading 状态、调用 store 创建模型。
2. `Form.tsx`：模型配置表单，定义用户能填写哪些模型字段。
3. `ExtendParamsSelect.tsx`：扩展参数选择器，给模型挂载额外运行时控制项，例如 reasoning effort、thinking budget、image aspect ratio、image resolution 等。

从命名看是“创建新模型”，但它的表单 `ModelConfigForm` 也被编辑弹窗复用：`ModelConfigModal/index.tsx` 会从这里 import `../CreateNewModelModal/Form`。所以这个目录既承载“新增模型”的弹窗，也提供“模型配置表单”这个可复用组件。

## 关键组成

### `index.tsx`

默认导出 `ModelConfigModal`，实际就是新增模型的 Modal 组件。

它接收两个 props：

```ts
interface ModelConfigModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}
```

关键 import：

- `Button`, `Modal` 来自 `@lobehub/ui`，负责弹窗和按钮 UI。
- `FormInstance` 来自 `antd`，用于保存子表单实例。
- `useTranslation` 来自 `react-i18next`，读取 `modelProvider` 和 `common` 命名空间文案。
- `useAiInfraStore` 来自 `@/store/aiInfra`，读取当前 provider 和创建模型动作。
- `ProviderSettingsContext` 来自上级目录，用来判断是否显示 deployment name。
- `ModelConfigForm` 来自本目录的 `Form.tsx`。

核心状态：

- `formInstance`：由子组件 `ModelConfigForm` 通过 `onFormInstanceReady` 回传。
- `loading`：提交过程中的按钮 loading。
- `editingProvider`：来自 `s.activeAiProvider!`，表示当前正在配置的 provider id。
- `createNewAiModel`：store action，负责真正创建模型。

提交逻辑在 OK 按钮的 `onClick` 里：

```ts
if (!editingProvider || !formInstance) return;
const data = formInstance.getFieldsValue();

setLoading(true);

try {
  await formInstance.validateFields();
  await createNewAiModel({ ...data, providerId: editingProvider });
  setLoading(false);
  closeModal();
} catch {
  setLoading(false);
}
```

也就是说，Modal 本身不关心数据如何持久化，只负责：

1. 从表单拿值。
2. 校验字段。
3. 补上当前 `providerId`。
4. 调用 `createNewAiModel`。
5. 成功后关闭弹窗。

这里的 `destroyOnHidden` 表示弹窗隐藏后销毁子内容，下次打开会重新创建表单。`zIndex={1251}` 的注释说明是为了高于 Select 的 `1150` 层级，避免弹窗里 Select 下拉层级冲突。

### `Form.tsx`

默认导出 `ModelConfigForm`，是新增/编辑模型共用的表单主体。

props：

```ts
interface ModelConfigFormProps {
  idEditable?: boolean;
  initialValues?: ChatModelCard;
  onFormInstanceReady: (instance: FormInstance) => void;
  showDeployName?: boolean;
  type?: AiModelType;
}
```

其中：

- `idEditable` 控制模型 id 是否可编辑，默认 `true`。
- `initialValues` 用于编辑场景回填已有模型配置。
- `onFormInstanceReady` 把 `Form.useForm()` 创建出来的实例交给父组件。
- `showDeployName` 控制是否展示 `config.deploymentName` 字段。
- `type` 在当前片段中声明了但没有被使用。

表单字段包括：

- `id`：模型 id，必填。
- `config.deploymentName`：部署名称，只在 `showDeployName` 为真时出现。
- `displayName`：展示名称。
- `contextWindowTokens`：上下文窗口 token 数，使用 `MaxTokenSlider`。
- `settings.extendParams`：扩展参数，使用本目录的 `ExtendParamsSelect`。
- `abilities.functionCall`：是否支持 function call。
- `abilities.vision`：是否支持视觉。
- `abilities.reasoning`：是否支持推理。
- `abilities.search`：是否支持搜索。
- `abilities.imageOutput`：是否支持图片输出。
- `abilities.video`：是否支持视频。
- `type`：模型类型，使用 antd `Select`。

`modelTypeOptions` 通过 `useMemo` 生成，枚举来自 `model-bank` 的 `AiModelType`，当前包含：

```ts
chat
embedding
tts
stt
image
video
text2music
realtime
```

显示文案来自：

```ts
providerModels.item.modelConfig.type.options.${value}
```

如果翻译结果不等于原始 value，会显示成 `翻译名 (value)`，便于用户同时看到本地化名称和内部类型值。

表单最外层 `div` 拦截 `onClick` 和 `onKeyDown` 的冒泡。根据当前片段推断，这是为了避免弹窗、父级列表项、快捷键或外层交互被表单内部点击/键盘事件误触发。

### `ExtendParamsSelect.tsx`

默认导出 `ExtendParamsSelect`，同时导出了 `normalizeExtendParamsValue`，因为测试文件 `__tests__/ExtendParamsSelect.test.tsx` 从该文件 import 了这个函数。

这个组件是表单里 `settings.extendParams` 的输入控件，负责选择模型支持的扩展控制参数。它依赖大量 `ModelSwitchPanel` 中的控制组件，用于在选项提示或预览中展示这些参数未来在模型切换面板里的控制形态。

关键 import 包括：

- UI：`Flexbox`、antd 的 `Popover`、`Select`、`Space`、`Switch`、`Tag`、`theme`、`Typography`。
- 类型：`ExtendParamsType` 来自 `model-bank`。
- i18n：`Trans`, `useTranslation`。
- 控制组件：例如 `ReasoningEffortSlider`、`ThinkingBudgetSlider`、`ImageAspectRatioSelect`、`ImageResolutionSlider`、`TextVerbositySlider` 等。

文件中定义了几个重要配置结构。

`EXTEND_PARAMS_OPTIONS` 是扩展参数候选项列表，每项包含：

```ts
type ExtendParamsOption = {
  hintKey: string;
  key: ExtendParamsType;
};
```

它把可选参数 key 和说明文案 key 绑定起来，例如：

- `disableContextCaching`
- `enableReasoning`
- `enableAdaptiveThinking`
- `reasoningBudgetToken`
- `reasoningBudgetToken32k`
- `reasoningBudgetToken80k`
- `effort`
- `deepseekV4ReasoningEffort`
- `opus47Effort`
- `reasoningEffort`
- `gpt5ReasoningEffort`
- `gpt5_1ReasoningEffort`
- `gpt5_2ReasoningEffort`
- `gpt5_2ProReasoningEffort`
- `grok4_20ReasoningEffort`
- `grok4_3ReasoningEffort`
- `hy3ReasoningEffort`
- `codexMaxReasoningEffort`
- `textVerbosity`
- `thinking`
- `thinkingBudget`
- `thinkingLevel`
- `thinkingLevel2`
- `thinkingLevel3`
- `thinkingLevel4`
- `urlContext`
- `imageAspectRatio`
- `imageAspectRatio2`
- `imageResolution`
- `imageResolution2`

`TITLE_KEY_ALIASES` 用于把变体参数复用到基础 i18n 标题。例如多个模型专属的 reasoning effort 变体，都复用 `reasoningEffort` 的标题；`imageAspectRatio2` 复用 `imageAspectRatio`；`thinkingLevel2/3/4` 复用 `thinkingLevel`。注释里说明它需要和 `ControlsForm.tsx` 同步。

`PREVIEW_META` 用来给不同参数补充展示元信息，例如：

- `labelSuffix`：标题后缀，如 `(GPT-5.2)`、`(Codex)`、`(Nano Banana 2)`。
- `previewWidth`：Popover 或预览区域宽度。
- `tag`：展示底层请求参数名，例如 `reasoning_effort`、`thinking.budget_tokens`、`aspect_ratio`、`resolution`。

根据当前片段推断，`ExtendParamsSelect` 的运行方式大致是：

1. 接收表单传入的 `value` 和 `onChange`。
2. 先用 `normalizeExtendParamsValue` 规整 value，兼容空值、旧格式或异常格式。
3. 把 `EXTEND_PARAMS_OPTIONS` 转换成 antd `Select` 的 options。
4. 每个 option 通过 i18n 显示标题、说明、标签和预览控件。
5. 用户选择后，把 `ExtendParamsType[]` 写回 `settings.extendParams`。

证据是：组件 props 位于 `ExtendParamsSelectProps`，组件定义为 `memo<ExtendParamsSelectProps>(({ value, onChange }) => ...)`；测试文件专门覆盖 `normalizeExtendParamsValue`；`Form.tsx` 中该组件被挂在 `name={['settings', 'extendParams']}` 的 `Form.Item` 下。

### `__tests__/ExtendParamsSelect.test.tsx`

测试文件位于本目录的 `__tests__` 下，目标是 `ExtendParamsSelect`。从 import 看，它重点测试 `normalizeExtendParamsValue`，说明这个目录对“扩展参数值的格式兼容”比较重视。

虽然当前没有展开测试内容，但可以确定它不是测试 Modal 提交，而是测试扩展参数选择器中的值归一化逻辑。

## 上下游关系

### 上游调用方

当前片段能看到三个相关调用点：

1. `ModelList/EmptyModels.tsx`

   在没有模型时展示空状态，并引入：

   ```ts
   import CreateNewModelModal from './CreateNewModelModal';
   ```

   用户从空状态点击新增时，会打开这个 Modal。

2. `ModelList/ModelTitle/index.tsx`

   在模型列表标题区域引入：

   ```ts
   import CreateNewModelModal from '../CreateNewModelModal';
   ```

   根据路径推断，这里通常是列表标题栏里的“新增模型”入口。

3. `ModelList/ModelConfigModal/index.tsx`

   这里不使用整个新增弹窗，而是复用表单：

   ```ts
   import ModelConfigForm from '../CreateNewModelModal/Form';
   ```

   说明 `Form.tsx` 是新增和编辑共享的配置表单。新增场景由 `CreateNewModelModal/index.tsx` 负责提交到 `createNewAiModel`；编辑场景则由 `ModelConfigModal` 自己处理提交逻辑。

### 下游依赖

`CreateNewModelModal` 下游主要连接这些模块：

- `@/store/aiInfra`

  读取 `activeAiProvider`，调用 `createNewAiModel`。这是数据写入的核心下游。

- `ProviderSettingsContext`

  读取 `showDeployName`，控制是否出现 deployment name 字段。这个字段常见于 Azure OpenAI 等 provider，因为实际调用模型时可能需要部署名而不是模型 id。

- `@/types/llm`

  `ChatModelCard` 作为 `initialValues` 类型，说明表单结构和模型卡片配置结构对齐。

- `model-bank`

  提供 `AiModelType` 和 `ExtendParamsType`。这两个类型把 UI 表单和模型能力定义绑定到同一套模型元数据规范。

- `@/components/MaxTokenSlider`

  用于编辑 `contextWindowTokens`。

- `@/features/ModelSwitchPanel/components/ControlsForm/*`

  `ExtendParamsSelect` 大量复用模型切换面板里的控制组件。这样新增模型时配置的扩展参数，和聊天时实际展示的模型参数控制项能保持一致。

- `src/locales/default/modelProvider.ts` 及生成后的 locale 文件

  表单 label、extra、placeholder、option title、hint 都依赖 `modelProvider` 命名空间。

## 运行/调用流程

典型新增流程如下：

1. 用户进入某个 provider 的模型设置页。
2. 页面从 `aiInfra` store 或路由上下文中确定当前 active provider。
3. 用户点击空状态或标题栏里的新增按钮。
4. 调用方维护 `showModal` / `setShowModal`，把 `open={showModal}` 传给 `CreateNewModelModal`。
5. `CreateNewModelModal` 打开 `Modal`。
6. Modal 内渲染 `ModelConfigForm`。
7. `ModelConfigForm` 调用 `Form.useForm()` 创建 antd 表单实例。
8. `useEffect` 执行 `onFormInstanceReady(formInstance)`，把实例交给 Modal。
9. 用户填写模型 id、展示名、上下文 token、能力开关、模型类型、扩展参数等字段。
10. 如果当前 provider 的 `ProviderSettingsContext.showDeployName` 为真，表单额外显示 `config.deploymentName`。
11. 用户点击 OK。
12. Modal 从 `formInstance.getFieldsValue()` 读取所有字段。
13. 调用 `formInstance.validateFields()` 校验必填项，当前明确必填的是 `id`。
14. 校验成功后调用：

    ```ts
    createNewAiModel({ ...data, providerId: editingProvider })
    ```

15. store 完成创建后，Modal 关闭。
16. 因为设置了 `destroyOnHidden`，Modal 关闭后内部表单销毁，下次打开重新初始化。

扩展参数选择流程可以单独理解：

1. 表单字段名是 `settings.extendParams`。
2. `ExtendParamsSelect` 接收当前值。
3. 组件将值归一化为可识别的扩展参数列表。
4. 用户从 Select 中选择一个或多个扩展参数。
5. 每个扩展参数通过 i18n 显示标题、说明，部分参数带有 Tag 或预览控件。
6. 选择结果写回表单，最终随 `settings.extendParams` 一起提交。

## 小白阅读顺序

1. 先读 `index.tsx`

   目标是弄懂弹窗怎么打开、怎么关闭、点 OK 后发生什么。重点看 `open/setOpen`、`formInstance`、`loading`、`useAiInfraStore`、`createNewAiModel`。

2. 再读 `Form.tsx`

   目标是理解“一个自定义模型”在这个页面能配置哪些字段。重点看每个 `Form.Item` 的 `name`，因为它决定最终提交对象的结构，例如 `['abilities', 'vision']` 会形成：

   ```ts
   {
     abilities: {
       vision: true
     }
   }
   ```

3. 然后读 `ExtendParamsSelect.tsx` 的顶部配置

   不建议一开始就陷入组件渲染细节。先看 `EXTEND_PARAMS_OPTIONS`、`TITLE_KEY_ALIASES`、`PREVIEW_META`，理解有哪些扩展参数、它们的文案和预览如何组织。

4. 再看 `ExtendParamsSelect` 组件主体

   重点找 `value`、`onChange`、`normalizeExtendParamsValue`、`Select` options 的组装逻辑。这个组件的难点不是 UI，而是“参数 key、文案、预览控件、实际表单值”之间的映射。

5. 最后看调用方

   查看 `EmptyModels.tsx` 和 `ModelTitle/index.tsx`，理解 Modal 是从哪里打开的；查看 `ModelConfigModal/index.tsx`，理解为什么 `Form.tsx` 不能只按“新增”场景来理解。

## 常见误区

1. 误以为这个目录只用于新增模型

   `index.tsx` 的确是新增弹窗，但 `Form.tsx` 被编辑弹窗 `ModelConfigModal` 复用。改表单字段时要同时考虑新增和编辑两个场景。

2. 误以为表单字段都是平铺的

   很多字段是嵌套路径，例如 `['config', 'deploymentName']`、`['settings', 'extendParams']`、`['abilities', 'functionCall']`。最终提交给 store 的对象会是嵌套结构，不是简单的一层 key-value。

3. 误以为 `showDeployName` 是本组件自己判断的

   它来自 `ProviderSettingsContext`。也就是说，是否展示 deployment name 是由 provider 设置上下文决定的，不是由表单内部根据 provider id 硬编码判断。

4. 误以为 `ExtendParamsSelect` 只是普通下拉框

   它背后绑定的是 `model-bank` 的 `ExtendParamsType`，还和 `ModelSwitchPanel` 的 ControlsForm 控件保持同步。新增一个扩展参数时，通常不只要改 Select option，还要考虑运行时控制面板、i18n 文案、预览信息和测试。

5. 误删 `TITLE_KEY_ALIASES`

   这些 alias 用于让模型专属变体复用基础标题文案。例如 `gpt5_2ReasoningEffort` 复用 `reasoningEffort` 标题。如果删除，可能导致标题 fallback 到 key 本身，或者需要补大量重复翻译。

6. 误把 `idEditable` 当成新增场景逻辑

   `idEditable` 默认是 `true`，新增模型时可以编辑 id；编辑模型时可能传 `false`，防止修改模型主键。它属于表单复用能力，不是 Modal 自己的状态。

7. 误以为点击 Cancel 会重置 store

   Cancel 只执行 `setOpen(false)`。由于 `destroyOnHidden`，UI 表单会销毁，但它不会主动调用 store action，也不会修改 provider 数据。

8. 忽略 `zIndex={1251}`

   这个值看似小细节，但注释说明 Select 是 `1150`。如果调整 Modal 或 Select 的层级，可能导致下拉菜单被遮挡或浮层顺序异常。

9. 忽略 `normalizeExtendParamsValue` 的测试

   既然有专门测试，说明扩展参数值可能存在兼容旧数据或异常输入的需求。修改 `ExtendParamsSelect` 时，应先理解这个归一化函数的输入输出约定。

10. 误以为 route 目录下都是纯页面文件

    这个目录位于 `src/routes/(main)/.../features/...`，属于设置页局部 feature。按照仓库较新的约定，路由文件应尽量薄，业务 UI 更推荐放到 `src/features`。但当前代码已经采用了路由内局部 feature 的组织方式，阅读和小改时应先尊重现有结构。
