# 文件：packages/coding-agent/examples/extensions/with-deps/index.ts
## 一句话定位
这是一个 `coding-agent` 扩展示例的入口文件，专门演示“扩展自己带依赖”时如何被加载，并通过 `registerTool` 注册一个依赖第三方库 `ms` 的工具；根据当前片段推断，它更偏向验证 `jiti` 能否从扩展目录自己的 `node_modules` 正确解析模块。

## 它暴露/定义了什么
这个文件默认导出一个函数 `default function (pi: ExtensionAPI)`，它不是一个业务模块，而是扩展初始化器。它只向宿主暴露一件事：注册名为 `parse_duration` 的工具。工具定义里包含 `name`、`label`、`description`、`parameters` 和 `execute`，参数结构由 `Type.Object(...)` 声明。

## 谁调用它
从文件结构看，它不会被应用内部显式业务代码直接调用，而是由扩展加载器在装载这个 example extension 时调用默认导出函数，并把 `ExtensionAPI` 实例传进来。随后，当用户或测试流程触发这个扩展注册的工具时，运行时会回调 `execute`。根据当前片段推断，这通常发生在 coding-agent 的扩展测试或示例启动流程里。

## 它调用谁
它主要调用三类对象。第一类是宿主注入的 `pi.registerTool(...)`，这是核心交互点。第二类是 `ms(params.duration as ms.StringValue)`，用于把人类可读时长转成毫秒。第三类是 `Type.Object` 和 `Type.String`，它们来自 `typebox`，用于描述工具参数 schema。工具执行阶段还会通过 `throw new Error(...)` 把非法输入显式失败。

## 核心流程
流程很短但层次清楚。启动时，扩展入口函数拿到 `ExtensionAPI`，立刻注册一个工具。该工具的参数只有一个 `duration` 字符串。用户触发工具后，`execute` 读取 `params.duration`，传给 `ms` 做解析；如果返回 `undefined`，就判定为无效输入并抛错；否则把原始字符串和计算结果拼成文本内容返回，供上层对话系统展示。这里返回对象里还带 `details: {}`，说明它遵守了宿主工具返回协议。

## 关键函数的高层作用
`default function (pi: ExtensionAPI)` 是整个扩展的初始化入口，职责是“声明能力”，不是处理业务。`pi.registerTool(...)` 是扩展与宿主之间的注册接口，决定这个扩展能向系统增加什么能力。`execute` 是真正的执行点，负责输入校验、调用 `ms` 解析、构造返回结果。`Type.Object(...)` 则保证工具参数 schema 可被宿主理解和校验。

## 修改风险
这类文件改动面看起来小，但风险集中。第一，`ms` 依赖于扩展目录自己的依赖安装状态，README 已明确写了需要在该目录执行 `npm install`，否则示例可能直接失效。第二，`params.duration as ms.StringValue` 依赖类型断言，若宿主传入的参数形状变化，运行期可能出现隐性错误。第三，`ms` 的解析结果允许 `undefined`，所以错误分支不能删，否则非法输入会被错误地当成有效值。第四，`registerTool` 的参数协议和返回结构一旦和宿主版本不一致，示例可能看似能跑，实际工具展示或调用链会断裂。
