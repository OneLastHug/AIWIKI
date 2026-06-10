# 文件：ui-tui/packages/hermes-ink/src/native-ts/yoga-layout/index.ts

## 一句话定位

`ui-tui/packages/hermes-ink/src/native-ts/yoga-layout/index.ts` 是 `hermes-ink` 内置的纯 TypeScript Yoga/Flexbox 布局引擎实现，用来替代外部 `yoga-layout`/WASM 运行时，为终端 UI DOM 树计算 `left/top/width/height`、padding、border、margin 等布局结果。

## 它暴露/定义了什么

这个文件主要暴露三类内容。

第一类是 Yoga 枚举和类型：从 `./enums.js` 导入并重新导出 `Align`、`Direction`、`Display`、`Edge`、`FlexDirection`、`Gutter`、`Justify`、`MeasureMode`、`Overflow`、`PositionType`、`Unit`、`Wrap` 等常量类型，使上层适配层可以继续使用接近 Yoga 原生 API 的枚举接口。

第二类是布局对象模型：`Config`、`Node`、`Value`、`Yoga`。其中 `Node` 是核心类，保存 `style`、`layout`、`parent`、`children`、`measureFunc`、dirty 标记和多组缓存字段。它提供 Yoga 风格 API，例如 `insertChild()`、`removeChild()`、`setWidth()`、`setFlexGrow()`、`setMargin()`、`setMeasureFunc()`、`calculateLayout()`、`getComputedWidth()`、`freeRecursive()` 等。

第三类是模块级实例和诊断入口：默认导出 `YOGA_INSTANCE`，提供 `Yoga.Node.create()`、`Yoga.Config.create()` 这类工厂；`loadYoga()` 返回同一个实例的 `Promise`，用于兼容历史上的异步加载边界；`getYogaCounters()` 返回本轮布局访问节点数、测量次数、缓存命中数和 live node 数。

## 谁调用它

直接调用者主要有两个。

`ui-tui/packages/hermes-ink/src/ink/layout/yoga.ts` 是最重要的适配层。它从本文件导入默认 `Yoga`、枚举和 `Node` 类型，然后用 `YogaLayoutNode` 把底层 Yoga 风格 API 转换成 `LayoutNode` 接口。上层代码通常不会直接操作本文件的 `Node`，而是通过 `createYogaLayoutNode()` 创建适配后的布局节点。

`ui-tui/packages/hermes-ink/src/ink/ink.tsx` 直接导入 `getYogaCounters()`，在根节点 `onComputeLayout` 中调用 `rootNode.yogaNode.calculateLayout(this.terminalColumns)` 后记录布局耗时和计数器，用于性能观测。

间接调用链是：`dom.createNode()` 为普通 DOM 节点创建 `yogaNode`，文本节点设置 `measureTextNode`，RawAnsi 节点设置 `measureRawAnsiNode`；React reconciler 提交后触发根节点布局；渲染阶段再通过 `getComputedLeft()`、`getComputedTop()`、`getComputedWidth()`、`getComputedHeight()` 读取结果并输出到终端。

## 它调用谁

本文件几乎不调用外部运行时，只依赖同目录的 `ui-tui/packages/hermes-ink/src/native-ts/yoga-layout/enums.ts`。布局计算全部在文件内部完成。

内部调用关系以 `Node.calculateLayout()` 为入口：它重置计数器和 generation，调用 `layoutNode()` 做递归布局，最后调用 `roundLayout()` 做像素/字符网格取整。`layoutNode()` 又调用 `resolveEdges4Into()`、`computeFlexBasis()`、`resolveFlexibleLengths()`、`layoutAbsoluteChild()`、`boundAxis()`、`resolveGap()`、`collectLayoutChildren()` 等辅助函数。叶子节点有 `measureFunc` 时，会回调上层传入的文本测量函数。

## 核心流程

整体流程可以概括为“建树、设样式、标脏、布局、读取结果”。

创建节点时，`Yoga.Node.create()` 实际 new 出 `Node`，其默认样式是 column 方向、`alignItems: Stretch`、`display: Flex`、`positionType: Relative`、宽高 auto、padding/margin/border 未定义。DOM 操作通过 `insertChild()`/`removeChild()` 维护父子关系，并向上 `markDirty()`。

样式设置阶段，上层通过适配层调用 `setWidth()`、`setFlexDirection()`、`setPadding()` 等方法。本文件把数字、百分比、`auto`、未定义值统一转为 `Value { unit, value }`，并维护 `_hasMargin`、`_hasPadding`、`_hasPosition` 等快速判断标记。

布局阶段，根节点 `calculateLayout(ownerWidth, ownerHeight)` 把可用宽高转换为 `MeasureMode.Exactly` 或 `Undefined`，然后递归进入 `layoutNode()`。`layoutNode()` 先查布局缓存，未命中时解析 padding/border/margin 和显式宽高；如果是带 `measureFunc` 的叶子节点，就调用测量函数得到内容尺寸；如果是容器，则收集普通流子节点和 absolute 子节点，计算 flex basis，按 wrap 拆行，分配 grow/shrink 后的主轴尺寸，再计算交叉轴尺寸、对齐、auto margin、gap、baseline 和 absolute 定位。最后写入每个节点的 `layout` 字段。

收尾阶段，`roundLayout()` 根据 `Config.pointScaleFactor` 对布局值取整，文本节点会有特殊的 ceil/floor 策略，以减少终端字符宽高上的截断问题。

## 关键函数的高层作用

`Node.calculateLayout()` 是公开布局入口，负责开始一轮完整布局、刷新计数器、推进 `_generation`，并在布局后处理根节点相对位置和取整。

`layoutNode()` 是核心算法主体，覆盖叶子测量、容器 flex 布局、wrap 拆行、justify/align 分布、stretch 二次测量、absolute 子节点布局和缓存写入。这个函数决定了 `hermes-ink` 终端界面最终排版行为。

`computeFlexBasis()` 计算子节点在主轴上的基础尺寸。它优先使用 `flexBasis`，其次使用主轴上的显式宽高，否则可能以测量模式递归测量子树。

`resolveFlexibleLengths()` 实现 flex grow/shrink 分配，并处理 min/max 约束导致的冻结逻辑，是容器内空间分配的关键。

`layoutAbsoluteChild()` 处理 `positionType: Absolute` 的子节点，根据 inset、父容器 padding/border、主轴方向和对齐规则确定位置。

`resolveEdge()`、`resolveEdgeRaw()`、`resolveEdges4Into()` 负责把 `left/right/top/bottom`、`horizontal/vertical/all/start/end` 等边值优先级解析成物理四边数值。

`roundLayout()` 把浮点布局落到终端渲染可用的网格上，影响一像素/一字符级别的视觉稳定性。

`getYogaCounters()` 只是性能诊断辅助，用于外部观察访问、测量、缓存命中和 live node 数。

## 修改风险

这个文件是布局核心，修改风险很高。任何 flex 主轴、交叉轴、wrap、gap、auto margin、baseline、absolute 或 min/max 逻辑变化，都可能让整个 TUI 的对齐、滚动区域高度、文本截断和重绘位置发生连锁变化。

缓存字段风险也很高。`_generation`、`_hasL`、`_hasM`、`_cIn/_cOut`、`_fbGen` 等字段用于避免重复测量；如果 dirty 传播、缓存 key 或缓存失效条件不准确，可能出现旧布局复用、文本高度不刷新、滚动高度错误，或者性能明显退化。

与原生 Yoga 兼容性是另一个风险点。上层 `ui-tui/packages/hermes-ink/src/ink/layout/yoga.ts` 假定这里提供 Yoga 近似 API，但本实现并非完整 Yoga：例如部分方法是空实现或简化实现，如 `setBoxSizing()`、`copyStyle()`、`setAspectRatio()`。新增上层样式能力时，如果只在适配层暴露方法而这里没有真实语义，会形成静默行为差异。

终端渲染还依赖取整策略。修改 `roundLayout()`、`roundValue()` 或文本测量相关路径，可能修复某些边界，也可能引入重叠、空行、滚动尾部残留等问题。根据当前片段推断，`render-node-to-output.ts` 中多处注释已经围绕 Yoga 结果做了防御，因此调整本文件时需要同步验证滚动、RawAnsi、文本换行、窗口 resize 和高度受限容器。
