# 目录：src/features/ModelSwitchPanel/components/ControlsForm

## 它负责什么

`src/features/ModelSwitchPanel/components/ControlsForm` 是 `ModelSwitchPanel` 里的“模型参数控制表单”区域。根据当前片段推断，它不负责模型列表、模型选择弹窗整体布局，也不直接负责请求发送；它的职责更集中：为不同模型、不同能力类型提供可复用的 UI 控件，让用户在切换或配置模型时调整推理强度、思考预算、上下文缓存、文本详细程度、图片比例与图片分辨率等参数。

这个目录的特点是“控件族”而不是“页面模块”。大多数文件都是一个具体控制项，例如 `ReasoningEffortSlider.tsx`、`ThinkingBudgetSlider.tsx`、`TextVerbositySlider.tsx`、`ContextCachingSwitch.tsx`、`ImageAspectRatioSelect.tsx`。它们通常会被上层 `ControlsForm.tsx` 组合成一个表单区域，再由 `ModelSwitchPanel` 的其他组件嵌入到模型切换面板里。

从命名上看，这里同时覆盖通用控件和模型专属控件。通用控件包括 `EffortSlider.tsx`、`LevelSlider.tsx`、`createLevelSlider.tsx`；模型专属控件包括 `GPT5ReasoningEffortSlider.tsx`、`GPT51ReasoningEffortSlider.tsx`、`GPT52ReasoningEffortSlider.tsx`、`GPT52ProReasoningEffortSlider.tsx`、`DeepSeekReasoningEffortSlider.tsx`、`Grok420ReasoningEffortSlider.tsx`、`Grok43ReasoningEffortSlider.tsx`、`CodexMaxReasoningEffortSlider.tsx`、`Opus47EffortSlider.tsx`、`Hy3ReasoningEffortSlider.tsx` 等。根据当前片段推断，这些专属组件用于把不同模型供应商的参数枚举、等级文案、默认值范围或 UI 呈现差异封装在独立组件里，避免主表单堆满分支逻辑。

## 直接子目录地图

当前片段中，这个目录几乎是扁平结构，只有一个直接子目录：

`src/features/ModelSwitchPanel/components/ControlsForm/__tests__`：测试目录，包含 `ControlsForm.test.tsx` 和 `createLevelSlider.test.tsx`。它说明这个目录至少有两类被重点验证的对象：一是整体 `ControlsForm` 的组合行为，二是 `createLevelSlider` 这种工厂函数或基础构造逻辑。

除 `__tests__` 外，其他内容都是直接放在 `ControlsForm` 根下的 `.tsx` 或 `.ts` 文件。这个布局暗示维护方式偏向“每个控件一个文件”，而不是再按 provider、reasoning、image、thinking 等主题继续拆子目录。阅读时不要期待这里有深层目录承载业务分层，主要分层发生在文件命名和组件组合关系上。

## 关键入口

最重要的入口是 `src/features/ModelSwitchPanel/components/ControlsForm/index.ts`。它通常承担导出门面作用，上层组件应优先从这里拿到 `ControlsForm` 或相关导出，而不是直接依赖内部实现文件。具体导出内容需要结合源码确认；根据当前目录结构推断，它至少会把主表单组件暴露给 `ModelSwitchPanel` 的上层区域。

第二个入口是 `src/features/ModelSwitchPanel/components/ControlsForm/ControlsForm.tsx`。这是目录名对应的主组件，负责把多个控制项按当前模型、当前能力或配置上下文组织起来。它很可能是理解这个目录主流程的第一现场：哪些控件会展示、展示顺序是什么、是否按模型能力做条件渲染、参数变更如何传给上层，都会在这里体现。

第三个入口是 `src/features/ModelSwitchPanel/components/ControlsForm/createLevelSlider.tsx`。从命名和测试文件 `createLevelSlider.test.tsx` 看，它是抽象层入口，用来批量生成“等级型 slider”。像 `ThinkingLevelSlider.tsx`、`ThinkingLevel2Slider.tsx`、`ThinkingLevel3Slider.tsx`、`ThinkingLevel4Slider.tsx`、`ThinkingLevel5Slider.tsx` 这类文件，很可能复用这个工厂逻辑。阅读它能帮助理解为什么目录里有大量相似 slider 文件：它们可能不是重复实现，而是通过同一套等级滑块基础能力配置出不同模型需要的档位。

## 主流程位置

主流程可以理解为四层。

第一层，上层 `ModelSwitchPanel` 决定什么时候展示控制表单。也就是说，用户先进入模型切换面板，选择或查看某个模型；面板再把当前模型、provider、配置状态或回调传给 `ControlsForm`。这个目录本身不是入口页面，而是面板内部的功能区。

第二层，`ControlsForm.tsx` 根据上下文选择控件。根据当前片段推断，它会处理“当前模型支持哪些参数”的分发问题。例如推理模型显示 reasoning effort 或 thinking budget，图像模型显示 aspect ratio 和 resolution，支持上下文缓存的模型显示 `ContextCachingSwitch`，支持文本详细程度的模型显示 `TextVerbositySlider`。如果某些模型需要特殊档位，就切到对应的专属 slider。

第三层，各个控件组件负责单项参数的 UI 和值映射。`ReasoningEffortSlider.tsx`、`ReasoningTokenSlider.tsx`、`ReasoningTokenSlider32k.tsx`、`ReasoningTokenSlider80k.tsx` 属于 reasoning 参数族；`ThinkingBudgetSlider.tsx`、`ThinkingSlider.tsx`、`ThinkingLevel*.tsx` 属于 thinking 参数族；`ImageAspectRatioSelect.tsx`、`ImageAspectRatio2Select.tsx`、`ImageResolutionSlider.tsx`、`ImageResolution2Slider.tsx` 属于图像生成参数族。数字后缀如 `2`、`3`、`4`、`5` 更像是不同版本或不同档位集合，不宜直接理解为排序优先级。

第四层，基础组件或工厂承载共同交互。`EffortSlider.tsx`、`LevelSlider.tsx`、`createLevelSlider.tsx` 是复用核心，负责把“枚举值、等级标签、slider marks、默认值、disabled 状态、onChange”这类通用问题封装起来。专属 slider 文件大概率只是传入不同配置。

## 推荐阅读顺序

建议先读 `src/features/ModelSwitchPanel/components/ControlsForm/index.ts`，确认对外暴露的真实入口。然后读 `src/features/ModelSwitchPanel/components/ControlsForm/ControlsForm.tsx`，建立整体组合视角：它引用了哪些控件、按什么条件渲染、如何接收和写回参数。

接着读基础抽象：`src/features/ModelSwitchPanel/components/ControlsForm/createLevelSlider.tsx`、`src/features/ModelSwitchPanel/components/ControlsForm/LevelSlider.tsx`、`src/features/ModelSwitchPanel/components/ControlsForm/EffortSlider.tsx`。这一组能解释大量相似 slider 的共性，避免一开始陷入模型专属文件细节。

之后按参数族阅读。需要理解推理参数时，看 `ReasoningEffortSlider.tsx`、`ReasoningTokenSlider.tsx` 及带具体模型名的 reasoning slider；需要理解思考参数时，看 `ThinkingBudgetSlider.tsx`、`ThinkingSlider.tsx`、`ThinkingLevelSlider.tsx` 及其变体；需要理解图片模型参数时，看 `ImageAspectRatioSelect.tsx`、`ImageResolutionSlider.tsx` 及带 `2` 的版本；需要理解开关类能力时，看 `ContextCachingSwitch.tsx`；需要理解文本输出风格时，看 `TextVerbositySlider.tsx`。

最后读 `src/features/ModelSwitchPanel/components/ControlsForm/__tests__/ControlsForm.test.tsx` 和 `src/features/ModelSwitchPanel/components/ControlsForm/__tests__/createLevelSlider.test.tsx`。测试通常会揭示哪些行为是稳定契约，尤其是显示条件、默认值、档位映射和回调行为。

## 常见误区

第一个误区是把这里当成模型选择逻辑的源头。`ControlsForm` 更像是模型切换面板里的参数编辑区，不是 provider 列表、模型元数据或运行时能力定义的根源。真正的模型能力、默认配置或 provider 定义可能在其他 feature、store、config 或 model 相关包中维护。

第二个误区是认为大量 slider 文件代表大量重复逻辑。根据 `createLevelSlider.tsx` 和 `LevelSlider.tsx` 的存在，更合理的理解是：目录用很多小文件封装不同模型的参数差异，公共交互沉到基础 slider 或工厂函数里。修改时应优先确认能否通过配置解决，而不是复制一个新的完整 slider 实现。

第三个误区是按文件名里的数字判断新旧关系。`ImageAspectRatio2Select.tsx`、`ImageResolution2Slider.tsx`、`ThinkingLevel2Slider.tsx` 到 `ThinkingLevel5Slider.tsx` 这类命名可能表示不同参数方案、不同模型档位或兼容版本，不一定表示“2 比 1 新，5 比 4 更推荐”。需要回到 `ControlsForm.tsx` 看它们在什么条件下被选用。

第四个误区是忽略测试目录。这个目录虽然是 UI 控件集合，但 `__tests__` 已经覆盖主表单和 slider 工厂，说明这里的显示和映射逻辑有业务含义。调整档位、默认值、组件选择条件时，应该同步查看测试期望，否则容易造成模型参数 UI 与实际配置不一致。

第五个误区是把控件文案、参数值和模型能力混在一起改。合理边界通常是：控件文件处理展示和交互，基础 slider 处理通用 UI 模式，模型能力和参数 schema 来自上游配置或 store。若需要新增某个模型的控制项，应先找它是否能复用现有 `EffortSlider`、`LevelSlider` 或 `createLevelSlider`，再决定是否新增专属组件。
