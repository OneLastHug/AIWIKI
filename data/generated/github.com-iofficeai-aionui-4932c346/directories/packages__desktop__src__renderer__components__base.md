# 目录：packages/desktop/src/renderer/components/base

## 它负责什么

这个目录是渲染层里 AionUi 的“基础组件集合”与统一出口层。根据当前片段推断，它并不是业务页面目录，而是把一组可复用的基础 UI 封装成稳定 API，供 `packages/desktop/src/renderer` 下的其他模块直接引用。

从 `index.ts` 的导出可以看出，这里主要承担两件事：一是汇总导出组件，二是同步暴露相关类型与常量。也就是说，它的定位更接近“组件仓库门口”，而不是“组件内部实现仓库”。上层代码通常只需要从这里拿到 `AionModal`、`AionSelect` 之类的封装件，不必关心各自内部如何拼装。

## 直接子目录地图

当前片段里，这个目录下**没有直接子目录**，只有文件。可见的核心文件有：

`AionCollapse.tsx`、`AionModal.tsx`、`AionScrollArea.tsx`、`AionSelect.tsx`、`AionSteps.tsx`、`FeedbackButton.tsx`、`FileChangesPanel.tsx`、`ModalWrapper.tsx`、`StepsWrapper.tsx`、`index.ts`

如果从目录职责来看，这些文件可以粗略分成三类：

1. 基础组件本体：`AionModal.tsx`、`AionCollapse.tsx`、`AionSelect.tsx`、`AionScrollArea.tsx`、`AionSteps.tsx`
2. 组合包装层：`ModalWrapper.tsx`、`StepsWrapper.tsx`
3. 业务化或场景化组件：`FeedbackButton.tsx`、`FileChangesPanel.tsx`

## 关键入口

最重要的入口是 `index.ts`。它做的是统一 re-export，也就是把这个目录下的能力收拢成一个稳定的公共出口。代码里已经明确导出了：

- 组件：`AionModal`、`AionCollapse`、`AionSelect`、`AionScrollArea`、`AionSteps`
- 类型：`ModalSize`、`ModalHeaderConfig`、`ModalFooterConfig`、`ModalContentStyleConfig`、`AionModalProps`、`AionCollapseProps`、`AionCollapseItemProps`、`AionSelectProps`、`AionStepsProps`
- 常量：`MODAL_SIZES`

这意味着上层调用通常会优先走 `index.ts`，而不是逐个直引实现文件。对维护者来说，`index.ts` 也是判断这个目录“对外承诺了什么”的第一观察点。

## 主流程位置

如果把这里的主流程理解为“组件如何被组装和对外提供”，那么主线大致落在三层：

1. `index.ts` 负责统一出口和类型转发，这是目录级主入口。
2. `AionModal.tsx`、`AionSteps.tsx` 等文件负责定义真正的基础组件能力，这些是核心实现层。
3. `ModalWrapper.tsx`、`StepsWrapper.tsx` 负责把基础能力再包装成更适合具体场景使用的形态，通常是把通用组件与业务参数、布局规则、交互细节拼起来。

`FileChangesPanel.tsx` 和 `FeedbackButton.tsx` 则更像基于这些基础能力形成的场景组件。根据文件名推断，它们不是基础原子组件，而是把目录里的底层组件再组合成可直接复用的功能块。

## 推荐阅读顺序

1. 先看 `index.ts`，确认这个目录对外暴露了什么。
2. 再看 `AionModal.tsx`，因为它导出了最多的类型与常量，通常最能代表这个目录的封装风格。
3. 然后看 `AionCollapse.tsx`、`AionSelect.tsx`、`AionSteps.tsx`，把基础组件家族的模式补齐。
4. 接着看 `ModalWrapper.tsx`、`StepsWrapper.tsx`，理解“基础组件”和“可用业务形态”之间的转换。
5. 最后再看 `FileChangesPanel.tsx`、`FeedbackButton.tsx`，把这些组件放回具体场景中理解。

## 常见误区

1. 不要把这个目录当成“页面目录”。它更像是渲染层的通用组件出口，而不是某个业务流程的完整实现。
2. 不要只看实现文件，忽略 `index.ts`。这里的统一导出决定了外部代码实际该怎么使用这些组件。
3. 不要把 `Wrapper` 类文件理解成纯样式壳。根据当前片段推断，它们更可能承担参数整形、默认行为注入、布局适配这类逻辑。
4. 不要假设这里还有更深的子目录结构。当前片段显示该目录是扁平结构，重点在文件级组合，而不是多层模块拆分。
5. 不要把 `FeedbackButton.tsx`、`FileChangesPanel.tsx` 误判成底层原子组件。它们更像围绕基础组件形成的上层场景封装。
