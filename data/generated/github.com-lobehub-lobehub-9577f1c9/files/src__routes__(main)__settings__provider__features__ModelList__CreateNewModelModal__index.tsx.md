# 文件：src/routes/(main)/settings/provider/features/ModelList/CreateNewModelModal/index.tsx

## 它负责什么

这个文件定义了“新增自定义模型”的弹窗组件，默认导出 `ModelConfigModal`。

它的职责很集中：在模型供应商设置页里打开一个 `Modal`，挂载 `ModelConfigForm` 表单，让用户填写模型信息，然后调用 `useAiInfraStore` 里的 `createNewAiModel` 创建模型。创建成功后关闭弹窗，并触发下游模型列表刷新。

它不直接渲染模型列表，也不直接请求 TRPC。它只是 UI 弹窗和 store action 之间的一层连接：

```tsx
<ModelConfigForm showDeployName={showDeployName} onFormInstanceReady={setFormInstance} />
```

表单本体在同目录的 `Form.tsx`，当前文件只负责弹窗外壳、按钮、提交逻辑、loading 状态和关闭逻辑。

## 关键组成

### `ModelConfigModalProps`

```ts
interface ModelConfigModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}
```

这是一个受控弹窗组件。父组件负责持有 `open` 状态，当前组件只通过 `setOpen(false)` 关闭弹窗。

常见调用方式来自 `ModelTitle` 和 `EmptyModels`：

```tsx
<CreateNewModelModal open={showModal} setOpen={setShowModal} />
```

### `ModelConfigModal`

```ts
const ModelConfigModal = memo<ModelConfigModalProps>(({ open, setOpen }) => {
```

组件被 `memo` 包裹，说明它依赖 props 和内部状态渲染，父级无关更新时可以减少重复渲染。

内部主要状态有两个：

```ts
const [formInstance, setFormInstance] = useState<FormInstance>();
const [loading, setLoading] = useState(false);
```

`formInstance` 是 antd `Form` 实例，由子组件 `ModelConfigForm` 创建后通过 `onFormInstanceReady` 回传。当前组件用它读取字段和触发表单校验。

`loading` 控制确认按钮的 loading 状态，防止创建请求进行中时按钮没有反馈。

### i18n

```ts
const { t } = useTranslation(['modelProvider', 'common']);
```

这个弹窗使用两个翻译 namespace：

- `modelProvider`：弹窗标题、模型配置表单相关文案。
- `common`：通用按钮文案，比如 `cancel`、`ok`。

标题来自：

```ts
t('providerModels.createNew.title')
```

取消和确认按钮分别来自：

```ts
t('cancel', { ns: 'common' })
t('ok', { ns: 'common' })
```

### store 依赖

```ts
const [editingProvider, createNewAiModel] = useAiInfraStore((s) => [
  s.activeAiProvider!,
  s.createNewAiModel,
]);
```

这里从 `aiInfra` store 中取两个东西：

- `activeAiProvider`：当前正在编辑的模型供应商 ID。
- `createNewAiModel`：创建新模型的 action。

注意 `s.activeAiProvider!` 使用了非空断言。实际提交时又做了保护：

```ts
if (!editingProvider || !formInstance) return;
```

所以非空断言主要是为了类型推断方便，运行时仍然允许缺失并提前返回。

### `ProviderSettingsContext`

```ts
const { showDeployName } = use(ProviderSettingsContext);
```

这里使用 React 19 的 `use(context)` 读取 `ProviderSettingsContext`，不是传统的 `useContext`。

`showDeployName` 决定表单里是否显示部署名称字段。这个字段主要用于某些供应商需要把模型 ID 和实际部署名分开的场景，例如 Azure/OpenAI 兼容部署类配置。根据当前片段推断，其依据是 `Form.tsx` 中：

```tsx
{showDeployName && (
  <Form.Item name={['config', 'deploymentName']}>
    <Input />
  </Form.Item>
)}
```

### `Modal`

弹窗来自 `@lobehub/ui`：

```tsx
<Modal
  destroyOnHidden
  maskClosable
  open={open}
  title={t('providerModels.createNew.title')}
  zIndex={1251}
  ...
>
```

几个关键属性：

- `destroyOnHidden`：关闭后销毁弹窗内容，下一次打开会重新挂载表单，避免旧表单值残留。
- `maskClosable`：点击遮罩可以关闭。
- `open`：由父组件控制显示/隐藏。
- `zIndex={1251}`：注释说明 `Select is 1150`，这里主动把弹窗层级设得更高，避免表单里的下拉组件或其他浮层层级冲突。
- `styles.body`：限制弹窗 body 最大高度并使用 column flex 布局。

### footer 按钮

footer 自定义了两个按钮：

```tsx
footer={[
  <Button key="cancel" onClick={closeModal}>...</Button>,
  <Button key="ok" loading={loading} type="primary" onClick={async () => {...}}>...</Button>,
]}
```

取消按钮只关闭弹窗。

确认按钮负责完整提交流程：

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

这里有一个细节：它先 `getFieldsValue()`，再 `validateFields()`。通常 antd 更常见的写法是 `const data = await formInstance.validateFields()`，这样能拿到校验后的字段值。当前写法依赖 `getFieldsValue()` 已经能读到最新表单状态；如果校验失败，请求不会执行。

失败时 `catch` 只关闭 loading，不弹错误。错误提示可能由 antd 表单校验自身显示，或者由上层请求机制处理；根据当前片段无法确认服务端错误是否有全局提示。

## 上下游关系

### 上游：谁打开这个弹窗

当前文件主要有两个直接调用方。

第一个是 `ModelTitle/index.tsx`。当模型列表标题区域允许新增模型时，会显示一个加号按钮：

```tsx
{showAddNewModel && (
  <>
    <Button
      icon={PlusIcon}
      size={'small'}
      onClick={() => {
        setShowModal(true);
      }}
    />
    <CreateNewModelModal open={showModal} setOpen={setShowModal} />
  </>
)}
```

也就是说，在普通模型列表顶部，如果供应商配置允许 `showAddNewModel`，用户可以点加号打开该弹窗。

第二个是 `EmptyModels.tsx`。当某个供应商模型列表为空时，空状态区域也提供新增按钮：

```tsx
<Button
  icon={PlusIcon}
  onClick={() => {
    setShowModal(true);
  }}
>
  {t('providerModels.list.addNew')}
</Button>
<CreateNewModelModal open={showModal} setOpen={setShowModal} />
```

所以这个弹窗既服务于“列表顶部新增”，也服务于“空列表引导新增”。

### 上游：上下文从哪里来

`ProviderSettingsContext` 在 `ModelList/index.tsx` 中提供：

```tsx
<ProviderSettingsContext
  value={{ modelEditable, sdkType, showAddNewModel, showDeployName, showModelFetcher }}
>
```

当前文件只消费其中的 `showDeployName`。这意味着是否显示部署名称字段，不是弹窗自己判断，而是由更上层的供应商配置页面决定。

### 下游：表单字段来自哪里

当前文件导入同目录的：

```ts
import ModelConfigForm from './Form';
```

`Form.tsx` 定义了新增模型时可填写的字段，包括：

- `id`：模型 ID，必填。
- `config.deploymentName`：部署名称，受 `showDeployName` 控制。
- `displayName`：显示名称。
- `contextWindowTokens`：上下文窗口 token 数。
- `settings.extendParams`：扩展参数。
- `abilities.functionCall`：函数调用能力。
- `abilities.vision`：视觉能力。
- `abilities.reasoning`：推理能力。
- `abilities.search`：搜索能力。
- `abilities.imageOutput`：图片输出能力。
- `abilities.video`：视频能力。
- `type`：模型类型，例如 `chat`、`embedding`、`tts`、`stt`、`image`、`video`、`text2music`、`realtime`。

这些字段最终会被 `formInstance.getFieldsValue()` 读取，然后合并 `providerId` 传给 store。

### 下游：创建模型 action

当前文件调用：

```ts
await createNewAiModel({ ...data, providerId: editingProvider });
```

`createNewAiModel` 定义在 `src/store/aiInfra/slices/aiModel/action.ts`：

```ts
createNewAiModel = async (data: CreateAiModelParams): Promise<void> => {
  await aiModelService.createAiModel(data);
  await this.#get().refreshAiModelList();
};
```

也就是说创建完成后，store 会刷新当前供应商的模型列表。

再往下，`aiModelService.createAiModel` 定义在 `src/services/aiModel/index.ts`：

```ts
createAiModel = async (params: CreateAiModelParams) => {
  return lambdaClient.aiModel.createAiModel.mutate(params);
};
```

它通过 TRPC 调用后端 `lambdaClient.aiModel.createAiModel`。

后端路由在 `src/server/routers/lambda/aiModel.ts`：

```ts
createAiModel: aiModelProcedure.input(CreateAiModelSchema).mutation(async ({ input, ctx }) => {
  const data = await ctx.aiModelModel.create(input);

  return data?.id;
}),
```

所以完整链路是：

`CreateNewModelModal` → `useAiInfraStore.createNewAiModel` → `aiModelService.createAiModel` → `lambdaClient.aiModel.createAiModel.mutate` → `aiModelRouter.createAiModel` → `ctx.aiModelModel.create`。

## 运行/调用流程

1. 用户进入某个供应商的模型设置页。
2. `ModelList` 在上层通过 `ProviderSettingsContext` 提供供应商相关配置，比如 `showDeployName`。
3. 如果允许新增模型，`ModelTitle` 显示加号按钮；如果模型列表为空，`EmptyModels` 显示新增按钮。
4. 用户点击新增按钮，父组件执行 `setShowModal(true)`。
5. `CreateNewModelModal` 收到 `open={true}`，渲染 `Modal`。
6. 弹窗内部挂载 `ModelConfigForm`。
7. `ModelConfigForm` 内部调用 `Form.useForm()` 创建 antd 表单实例。
8. `ModelConfigForm` 通过 `onFormInstanceReady={setFormInstance}` 把表单实例传回弹窗组件。
9. 用户填写模型 ID、显示名称、能力、类型、token 等配置。
10. 用户点击确认按钮。
11. 当前组件先检查 `editingProvider` 和 `formInstance` 是否存在。
12. 调用 `formInstance.getFieldsValue()` 获取表单数据。
13. 设置 `loading=true`，确认按钮进入加载状态。
14. 调用 `formInstance.validateFields()` 执行表单校验。
15. 校验通过后调用：

```ts
createNewAiModel({ ...data, providerId: editingProvider })
```

16. store action 调用服务层创建模型。
17. 服务层通过 TRPC mutation 调用后端。
18. 后端调用 `ctx.aiModelModel.create(input)` 落库。
19. 创建成功后，store 调用 `refreshAiModelList()` 刷新当前供应商模型列表。
20. 当前弹窗设置 `loading=false` 并调用 `closeModal()`。
21. `closeModal()` 执行 `setOpen(false)`，父组件状态变更，弹窗关闭。
22. 因为 `destroyOnHidden`，弹窗内容关闭后会被销毁，下次打开是新的表单实例。

## 小白阅读顺序

1. 先读当前文件的 props：

```ts
interface ModelConfigModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}
```

先理解这是一个“父组件控制开关”的弹窗。

2. 再看 `return` 里的 `Modal`。

重点看 `open`、`title`、`footer`、`onCancel` 和子组件 `ModelConfigForm`。这能快速知道它展示什么、怎么关闭、确认按钮做什么。

3. 接着看确认按钮的 `onClick`。

这是当前文件最核心的逻辑：

```ts
await formInstance.validateFields();
await createNewAiModel({ ...data, providerId: editingProvider });
```

理解这两行，就理解了“校验表单后创建模型”。

4. 然后打开同目录 `Form.tsx`。

当前文件不定义具体表单项，所以必须读 `Form.tsx` 才知道用户到底填写了哪些字段。尤其要注意字段名里的嵌套结构：

```ts
['config', 'deploymentName']
['settings', 'extendParams']
['abilities', 'functionCall']
```

这些会生成嵌套对象，最终进入 `CreateAiModelParams`。

5. 再看 `ProviderSettingsContext.ts`。

这里可以知道 `showDeployName` 是上下文配置，不是弹窗自己的内部状态。

6. 再看调用方 `ModelTitle/index.tsx` 和 `EmptyModels.tsx`。

这一步帮助理解弹窗出现在哪里：一个是列表标题加号，一个是空状态新增按钮。

7. 最后看 store action：

```ts
src/store/aiInfra/slices/aiModel/action.ts
```

重点看 `createNewAiModel`，确认它不是只创建数据，还会刷新模型列表。

## 常见误区

### 误区一：以为这个文件定义了新增模型的所有字段

不是。当前文件只是弹窗容器，具体表单字段在同目录的 `Form.tsx`。如果要改新增模型的字段、校验规则、placeholder、能力选项，主要应该看 `Form.tsx`，不是只看 `index.tsx`。

### 误区二：以为 `open` 是组件内部状态

不是。`open` 和 `setOpen` 都来自父组件。当前组件没有自己决定是否显示，只负责在取消、遮罩关闭或提交成功时调用 `setOpen(false)`。

### 误区三：忽略 `ProviderSettingsContext`

`showDeployName` 会影响表单结构。如果某个供应商新增模型时多了“部署名称”字段，不要在当前文件里找条件判断，条件来自上层 `ModelList` 注入的 `ProviderSettingsContext`。

### 误区四：以为点击 OK 一定会发请求

不一定。确认按钮会先检查：

```ts
if (!editingProvider || !formInstance) return;
```

如果当前没有激活供应商，或者表单实例还没准备好，会直接返回。之后还会执行 `validateFields()`，校验失败也不会调用 `createNewAiModel`。

### 误区五：以为创建成功后当前组件手动更新列表

当前组件只调用 `createNewAiModel`。刷新列表是在 store action 内部完成的：

```ts
await this.#get().refreshAiModelList();
```

所以列表更新逻辑不在弹窗组件里，而在 `aiInfra` store 的模型 slice 中。

### 误区六：忽略 `destroyOnHidden`

`destroyOnHidden` 会让弹窗关闭后销毁内容。这意味着下次打开时表单会重新创建，旧输入不会自然保留。如果想保留未提交的草稿，不能只改 `Form.tsx`，还要重新考虑这个弹窗销毁策略。

### 误区七：把 `getFieldsValue()` 当成校验结果

当前代码先调用：

```ts
const data = formInstance.getFieldsValue();
```

然后再：

```ts
await formInstance.validateFields();
```

这和常见的 `const data = await formInstance.validateFields()` 不完全一样。当前写法依赖 `getFieldsValue()` 读取到的值作为提交数据，而 `validateFields()` 只用于阻止非法提交。读代码时不要误以为 `data` 是 `validateFields()` 返回的结果。

### 误区八：以为错误会自动在这个组件里展示

`catch` 里只做了：

```ts
setLoading(false);
```

它没有调用 `message.error`，也没有把服务端错误渲染出来。表单校验错误会由 antd Form 自己显示；服务端错误是否有全局提示，需要继续查看 TRPC/client 或全局错误处理机制。根据当前片段推断，当前组件本身不负责错误展示。
