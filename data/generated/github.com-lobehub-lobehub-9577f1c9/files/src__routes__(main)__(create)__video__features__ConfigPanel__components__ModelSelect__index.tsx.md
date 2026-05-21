# 文件：src/routes/(main)/(create)/video/features/ConfigPanel/components/ModelSelect/index.tsx

## 它负责什么

这个文件实现的是视频创建页配置面板里的“模型选择器”。它把当前可用的视频 provider 和 model 从全局状态里读出来，组装成 `Select` 下拉框，让用户在创建视频时切换“用哪个 provider 的哪个模型”。

它不只是一个普通下拉框，还处理了几类业务边界：

- 没有任何可用 provider 时，给出“去设置 provider”的空态选项
- 有 provider 但没有可用视频模型时，给出“去设置该 provider”的空态选项
- 有多个 provider 时，按 provider 分组展示模型
- 选中项要用更丰富的 `VideoModelItem` 进行渲染，而不是裸文本
- 切换模型后要把 `model` 和 `provider` 一起写回 `useVideoStore`

## 关键组成

- `useAiInfraStore(aiProviderSelectors.enabledVideoModelList)`：读取当前启用的视频模型 provider 列表
- `useVideoStore(...)`：读取当前视频生成配置里的 `model` 和 `provider`，以及写回动作 `setModelAndProviderOnSelect`
- `useMemo<SelectProps['options']>`：把 store 数据转换成 `Select` 的 option 结构，避免每次渲染都重建
- `VideoModelItem`：单个模型项的展示组件，来自同目录 `VideoModelItem.tsx`
- `ProviderItemRender`：provider 头部展示组件，来自通用的 `@/components/ModelSelect`
- `styles.popup`：通过 `createStaticStyles` 调整 antd 下拉面板的间距、圆角和选中态背景
- `labelRender`：把已选中的 `provider/model` 值映射回完整的视觉展示
- `onChange`：解析 `provider/model` 字符串，并在值变化时同步到 store

这里还有一个细节：`ModelOption` 这个本地类型只为了让 `onChange` 里能从 option 上取出 `provider` 字段，因为默认的 `Select` option 类型不会天然带这个业务信息。

## 上下游关系

上游数据主要来自两个 store：

- `useAiInfraStore` 提供“有哪些视频 provider 和模型可用”
- `useVideoStore` 提供“当前视频创建参数里选了哪个 provider 和 model”

下游则有两条：

- UI 下游：`Select` 下拉框、`VideoModelItem`、`ProviderItemRender`、`ActionIcon`、`Icon`
- 行为下游：调用 `setModelAndProviderOnSelect(model, provider)` 更新视频生成配置；在空态或 provider 标题右侧点按钮时跳转到 `/settings/provider/...`

目录里的相邻文件也能看出它的复用边界。`VideoModelItem.tsx` 只是把通用的 `GenerationModelItem` 包了一层，并固定 `priceKind="video"`，说明这里的“视频模型项”本质上是通用模型卡片在视频场景下的一个定制版本。根据当前片段推断，同目录 `ConfigPanel/index.ts` 只导出了 `VideoModelItem`，而不是把这个 `ModelSelect` 作为公共入口暴露出去，说明它更像是配置面板内部私有组件。

## 运行/调用流程

1. 组件渲染时，先从 `useVideoStore` 取出当前 `provider` 和 `model`
2. 再从 `useAiInfraStore` 取出可用的视频 provider 列表
3. `useMemo` 根据列表生成 `options`
4. 如果没有 provider，生成一个禁用项，文案是“emptyProvider”，点击逻辑指向 `/settings/provider/all`
5. 如果只有一个 provider，就直接展开它的模型列表
6. 如果某个 provider 没有模型，就生成一个禁用项，文案是“emptyModel”，点击逻辑指向该 provider 的设置页
7. 如果有多个 provider，就把 provider 作为分组标题，每组下面放对应模型
8. `labelRender` 在选中后把 `provider/model` 字符串重新映射成完整的 `VideoModelItem`，让输入框显示更丰富
9. `onChange` 拿到新值后，先过滤掉 `no-provider` 和 `empty` 这类空态项，再拆出 `model` 与 `provider`
10. 只有当新值和当前 store 值不同，才调用 `setModelAndProviderOnSelect`

## 小白阅读顺序

先看 `useVideoStore` 和 `useAiInfraStore` 这两条数据来源，弄清楚“当前选中值”和“可选值列表”分别从哪里来。  
接着看 `options` 的 `useMemo`，重点理解三种分支：没有 provider、只有一个 provider、多个 provider。  
然后看 `labelRender`，它决定了选中后输入框里显示什么。  
最后看 `onChange`，确认用户点选后怎样把结果写回状态。

如果想进一步理解视觉层，可以顺着看 `VideoModelItem.tsx`，再看它引用的 `GenerationModelItem`，这样能知道为什么这里的选项比普通文本更“重”。

## 常见误区

- 这个组件的值不是单独的 model，而是 `provider/model` 组合字符串；只看 `model` 会漏掉 provider 上下文
- `disabled: true` 的空态选项不是纯展示，它还带了 `onClick`，用于跳转到设置页
- `labelRender` 只负责已选中的展示，不负责下拉列表里的 option 渲染
- `showBadge={false}` 和 `showPopover={false}` 是刻意关闭的，说明这里想要更轻的选择面板显示
- `onChange` 里先比较新旧值再写 store，是为了避免无意义的重复更新
- `enabledVideoModelList.length === 1` 时不会显示 provider 分组标题，这会让单 provider 场景更紧凑
- `ModelOption` 里的 `label: any` 是对 `Select` option 结构的现实妥协，说明这里的 option 标签本身就是 React 节点，而不是纯字符串
