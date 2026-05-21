# 目录：src/routes/(main)/(create)/video/features/ConfigPanel/components/ModelSelect

## 它负责什么

这个目录负责“视频生成模型选择器”这一个具体控件。它把视频页当前可用的 provider 和 model 组合成一个 `Select` 下拉框，让用户在创建视频时切换生成模型；同时把“当前选中的模型”反向渲染成更丰富的条目展示，而不是只显示一串 `provider/model` 字符串。

从实现上看，它还承担了两个附加职责：

1. 当没有可用 provider 或没有可用 model 时，给出空状态入口，并直接跳转到 provider 设置页。
2. 在下拉列表里为每个 provider 提供“去设置”的快捷入口，减少用户在视频创建页和设置页之间来回找入口的成本。

## 关键组成

这个目录里只有两个文件：

- `index.tsx`：主组件 `ModelSelect`
- `VideoModelItem.tsx`：视频模型条目的展示壳，复用通用的 `GenerationModelItem`

`index.tsx` 的核心依赖关系比较清晰：

- UI 组件来自 `@lobehub/ui`：`Select`、`Flexbox`、`ActionIcon`、`Icon`
- 样式来自 `antd-style`：`createStaticStyles` 和 `cssVar`
- 图标来自 `lucide-react`：`LucideArrowRight`、`LucideBolt`
- 状态来自 zustand store：
  - `useAiInfraStore(aiProviderSelectors.enabledVideoModelList)` 负责取出可用的视频模型列表
  - `useVideoStore` 负责读写当前视频生成配置
- 文案来自 `react-i18next` 的 `components` 命名空间
- 路由跳转来自 `react-router-dom` 的 `useNavigate`

`VideoModelItem.tsx` 则非常薄，它只是把 `AiModelForSelect` 转交给 `GenerationModelItem`，并固定两个视频场景相关参数：

- `priceKind="video"`
- `showPrice={true}`

这说明视频模型列表并不是专门写一套独立卡片，而是借用全局通用的模型展示组件，只在视频场景下补上价格语义。

## 上下游关系

上游数据来源是视频配置页的两个状态域：

- `useAiInfraStore` 提供“有哪些视频模型可选”
- `useVideoStore` 提供“当前选中了哪个 provider 和 model”

`enabledVideoModelList` 的结构里，每个 provider 下面有 `children`，也就是具体模型。`ModelSelect` 先把它们变成 `Select` 的 options，再把用户选择写回 `useVideoStore`。

下游消费方主要有两类：

- 视频创建流程里的配置面板本身。根据当前片段推断，`ModelSelect` 是 `ConfigPanel` 的首个配置项，`VideoConfigSkeleton.tsx` 里最上面的骨架位注释就是 `ModelSelect`，说明它对应的是同一个位置的真实控件。
- 通用模型展示组件链路。`VideoModelItem` 复用了 `@/routes/(main)/(create)/components/GenerationModelItem`，所以它和全局模型选择 UI 保持一致，只是面向视频场景做了参数适配。

还有一个很明确的旁路依赖：

- `ProviderItemRender` 来自 `@/components/ModelSelect`，说明 provider 行的视觉展示逻辑不是这一个目录自己发明的，而是沿用了全局通用的 provider 渲染器。

## 运行/调用流程

1. 组件挂载后，`ModelSelect` 通过 `useAiInfraStore` 读取当前启用的视频模型列表。
2. 它同时从 `useVideoStore` 读取当前选中的 `currentProvider` 和 `currentModel`。
3. 如果没有任何可用 provider，`options` 会退化成一个禁用项，文案提示“没有 provider”，点击行为则导向 `/settings/provider/all`。
4. 如果有 provider，但某个 provider 没有 model，则该 provider 下会出现一个禁用项，点击后跳转到 `/settings/provider/${provider.id}`。
5. 如果只有一个 provider，就直接展开它的 model 列表，不再显示 provider 分组壳。
6. 如果有多个 provider，则先显示 provider 分组标题，再显示组内 model。
7. 用户选中某个 model 后，`onChange` 会把 `provider` 和 `model` 拆出来，调用 `setModelAndProviderOnSelect(model, provider)` 写回视频配置状态。
8. `labelRender` 会在当前值展示时，把 `provider/model` 重新映射回 `VideoModelItem`，因此输入框里显示的是完整模型卡片，而不是纯文本。

## 小白阅读顺序

1. 先看 `index.tsx`，重点抓住三件事：数据从哪里来、选项怎么生成、选中后写回哪里。
2. 再看 `VideoModelItem.tsx`，理解它为什么只是一个薄封装，以及为什么会固定 `priceKind="video"`。
3. 然后回头看 `ConfigPanel/VideoConfigSkeleton.tsx`，把这个控件放回视频配置面板的位置里，理解它在页面上的先后顺序。
4. 最后补看 `@/components/ModelSelect` 和 `GenerationModelItem`，因为这个目录本身主要是在“组装”，真正的展示规范来自这两个通用组件。

## 常见误区

1. 把它当成独立业务模块。实际上它更像“视频配置面板里的一个选择控件”，核心职责是状态映射，不是独立页面。
2. 误以为它直接维护模型列表。列表数据并不在这里定义，而是从 `useAiInfraStore` 读取，属于上游 store 的职责。
3. 误以为选中值就是纯 model id。这里实际使用的是 `provider/model` 组合值，所以 `onChange` 里必须先拆分字符串再写回状态。
4. 忽略空状态跳转。这里不是简单展示空白，而是把没有 provider / 没有 model 的情况直接导向设置页，属于“可操作空状态”。
5. 只看 `ModelSelect`，不看 `VideoModelItem`。后者虽然很短，但它决定了视频模型在下拉框和输入框里最终呈现成什么样。根据当前片段推断，它是视频页和通用模型展示之间的适配层。
