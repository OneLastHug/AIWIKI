# 目录：src/features/ModelSwitchPanel

## 它负责什么

`src/features/ModelSwitchPanel` 是一个可复用的“模型切换面板”特性目录，主要负责在聊天、页面编辑 Copilot、图片/视频生成等入口中展示可用模型，并完成模型与 provider 的选择切换。它不是路由页，而是一个被多个业务入口嵌入的浮层组件：外部传入触发器 `children`，内部用 `DropdownMenuRoot`、`DropdownMenuTrigger`、`DropdownMenuPopup` 组成悬浮面板。

这个目录同时承载三类能力：第一是模型列表浏览，包括按模型聚合、按 provider 分组、搜索、空状态、当前模型定位；第二是模型详情展示，包括上下文长度、能力标签、价格信息等；第三是模型参数控件复用，例如 reasoning effort、thinking budget、image resolution、image aspect ratio、text verbosity 等表单控件。这些控件不只服务面板自身，也被设置页、聊天输入栏参数面板、记忆配置等位置直接引用。

从设计上看，`ModelSwitchPanel` 既支持默认聊天模型列表，也支持外部业务传入 `enabledList`、`ModelItemComponent`、`pricingMode` 来适配图片/视频生成场景。因此它更像一个“模型选择基础设施组件”，而不是单一聊天功能组件。

## 直接子目录地图

`src/features/ModelSwitchPanel/components` 是 UI 主体区，负责浮层内容、工具栏、底部、详情面板、列表渲染和参数表单。顶层的 `PanelContent.tsx` 连接工具栏和列表，`Toolbar.tsx` 处理搜索与分组模式切换，`ModelDetailPanel.tsx` 处理模型详情信息，`Footer.tsx` 提供底部管理入口。

`src/features/ModelSwitchPanel/components/List` 是模型列表渲染区。它把 `useBuildListItems` 产出的结构化列表项转成具体 UI，区分普通聊天模型选择和生成类模型选择。这里包含单 provider 模型、多 provider 模型、按 provider 分组项、空 provider、空模型等渲染路径。

`src/features/ModelSwitchPanel/components/ControlsForm` 是模型扩展参数控件集合。目录里有通用 `ControlsForm.tsx` 和大量具体控件，例如 `ReasoningEffortSlider`、`ThinkingBudgetSlider`、`ImageResolutionSlider`、`ImageAspectRatioSelect` 等。根据当前片段推断，它是全仓复用的“模型能力参数表单控件库”，依据是设置页 `CreateNewModelModal/ExtendParamsSelect.tsx`、聊天输入栏 `Params/Controls.tsx`、记忆设置页都直接从这里 import 单个控件。

`src/features/ModelSwitchPanel/hooks` 是主流程状态和数据组织区。它不直接渲染 UI，而是负责读取当前模型、构造列表项、处理选择回调、维护面板宽高和分组模式。

`src/features/ModelSwitchPanel/__mocks__` 提供测试用模型数据，目前可见 `mockEnabledChatModels.ts`，用于列表或详情测试。

## 关键入口

最核心入口是 `src/features/ModelSwitchPanel/index.tsx`。它默认导出 `ModelSwitchPanel`，定义浮层打开状态、受控/非受控 `open`、`placement`、`openOnHover`，并把业务参数传给 `PanelContent`。外部最常见用法是：

`<ModelSwitchPanel model={model} provider={provider} onModelChange={...}>触发器</ModelSwitchPanel>`

类型入口是 `src/features/ModelSwitchPanel/types.ts`。这里定义了 `ModelSwitchPanelProps`、`GroupMode`、`ListItem`、`ModelWithProviders`。读这个文件可以先了解面板对外支持哪些能力：默认模型来源、外部模型列表、外部模型行组件、切换回调、浮层位置、价格模式等。

内容入口是 `src/features/ModelSwitchPanel/components/PanelContent.tsx`。它决定面板内部结构：先渲染 `Toolbar`，再渲染 `List`；开发模式下用 `react-rnd` 支持横向 resize，普通模式下使用固定宽度。它还决定默认数据来源：如果外部未传 `enabledList`，就使用 `useEnabledChatModels()`。

列表入口是 `src/features/ModelSwitchPanel/components/List/index.tsx`。这里串起列表数据、当前模型、选择动作、限制模型 guard、滚动定位和两套 renderer，是理解主流程的关键文件。

参数表单入口是 `src/features/ModelSwitchPanel/components/ControlsForm/index.ts` 和 `ControlsForm.tsx`。如果目标是学习“模型参数如何组合显示”，应从这里进入，而不是从 `ModelSwitchPanel/index.tsx` 进入。

## 主流程位置

面板打开流程在 `src/features/ModelSwitchPanel/index.tsx`：组件包住外部触发器，打开后渲染 `PanelContent`。`open` 可以由外部控制，也可以由内部 `internalOpen` 控制；打开方式默认支持 hover。

数据来源流程在 `PanelContent.tsx` 和 `List/index.tsx`。两处都会处理 `enabledList` 默认值：外部传入时优先使用外部列表，否则读取 `useEnabledChatModels()`。当前选中的 `model`、`provider` 由 `useModelAndProvider` 合并 props 与 `useAgentStore` 中的当前 agent 配置得到。

列表构造流程在 `src/features/ModelSwitchPanel/hooks/useBuildListItems.ts`。它输入 `enabledList`、`groupMode`、`searchKeyword`，输出统一的 `ListItem[]`。当没有 provider 时返回 `no-provider`；按模型聚合时会把同 displayName 的模型合并为一个模型项，并记录多个 providers；按 provider 分组时会生成 `group-header`、`provider-model-item`、`empty-model` 等条目。这里还固定让 `lobehub` provider 排在前面。

渲染分发流程在 `src/features/ModelSwitchPanel/components/List/index.tsx`。如果外部传了 `ModelItemComponent`，列表走 `GenerationListItemRenderer`，用于图片/视频等生成场景；否则走 `ListItemRenderer`，用于常规聊天模型选择。列表还会计算 `activeKey`，首次打开时把当前模型滚动到可视区域中间。

选择写回流程在 `src/features/ModelSwitchPanel/hooks/usePanelHandlers.ts`。点击模型后会延迟约 150ms 执行写回，以避免关闭动画期间详情面板闪动。如果外部提供 `onModelChange`，则调用外部回调；否则默认调用 `useAgentStore` 的 `updateAgentConfig`。在聊天输入栏的实际使用中，例如 `src/features/ChatInput/ActionBar/Model/index.tsx`，外部会传入按 agentId 更新的 `updateAgentConfigById`，避免误改当前全局 agent。

面板偏好流程在 `usePanelState.ts` 和 `usePanelSize.ts`。分组模式 `modelSwitchPanelGroupMode` 与宽度 `modelSwitchPanelWidth` 存在 `useGlobalStore` 的 system status 中。开发模式下可以切换分组模式并 resize，非开发模式下固定按模型分组展示。

## 推荐阅读顺序

1. 先读 `src/features/ModelSwitchPanel/types.ts`，建立对 props、列表项类型和分组模式的整体认识。
2. 再读 `src/features/ModelSwitchPanel/index.tsx`，理解它只是浮层壳和对外入口。
3. 接着读 `src/features/ModelSwitchPanel/components/PanelContent.tsx`，看面板主体如何组合工具栏、列表和尺寸逻辑。
4. 然后读 `src/features/ModelSwitchPanel/hooks/useBuildListItems.ts`，这是“enabled providers/models 如何变成可渲染列表”的核心。
5. 继续读 `src/features/ModelSwitchPanel/components/List/index.tsx`，理解普通模型选择和生成类模型选择的 renderer 分流。
6. 最后按需求阅读 `components/List` 下的具体 item renderer、`components/ModelDetailPanel.tsx` 和 `components/ControlsForm`。如果只关心切模型，详情和参数控件可以后置。

## 常见误区

不要把 `ModelSwitchPanel` 理解成只服务聊天页。它的外部引用包括 `src/features/ChatInput/ActionBar/Model/index.tsx`、`src/features/ChatInput/ActionBar/ModelLabel/index.tsx`、`src/features/PageEditor/Copilot/CopilotModelSelect.tsx`，以及图片/视频生成输入区；`ControlsForm` 还被设置页和参数面板复用。

不要认为所有模型列表都来自 agent store。默认聊天场景会走 `useEnabledChatModels()`，但生成类场景可以传入自己的 `enabledList` 和 `ModelItemComponent`。因此改列表结构时要同时考虑普通聊天和 image/video generation 两条路径。

不要忽略 `onModelChange` 的覆盖逻辑。没有传回调时才会默认 `updateAgentConfig`；很多调用方会传自己的更新函数，比如按特定 `agentId` 更新配置。直接在内部强绑某个 store action 容易破坏这些调用方。

不要把 `ControlsForm` 当成面板内部私有实现。它实际是模型扩展参数控件的共享出口，被多个设置和输入场景直接 import。移动或改名这些控件时，影响范围会超过 `ModelSwitchPanel` 自身。

不要只看 `byProvider` 分组效果。当前片段显示分组切换只在 `isDevMode` 下展示，非开发模式会强制使用 `byModel`。如果调试时看不到 provider 分组入口，原因可能是用户设置中的 dev mode 未开启，而不是列表构造逻辑失效。
