# 目录：src/commands/model

## 它负责什么

`src/commands/model` 是 Claude Code 里 `/model` 命令的专用实现目录，职责非常集中：让用户查看当前模型、通过交互式选择器切换模型，或者直接在命令后面带模型名完成一次性设置。根据当前片段推断，它是“模型切换”这个用户动作的唯一局部入口，而不是模型解析、provider 选择或 API 调用本身的实现地。真正的模型能力与解析逻辑主要在 `src/utils/model/*` 一带，这个目录更像是命令层的薄封装。

从使用体验看，它同时覆盖两种路径：一种是无参数时打开 `ModelPicker` 让用户选；另一种是 ` /model <model>` 直接设置。它还会处理 `default`、别名、校验、1M 访问限制、fast mode 联动和额外用量提示，因此是一个“命令调度 + 状态写入 + 结果反馈”的组合点。

## 直接子目录地图

这个目录下**没有更深一层的子目录**。从当前扫描结果看，只有两个文件：

- `src/commands/model/index.ts`
- `src/commands/model/model.tsx`

因此这里不是“树状功能目录”，而是一个典型的命令小目录：`index.ts` 负责命令声明和懒加载，`model.tsx` 负责实际交互与业务分流。

## 关键入口

最先看的入口是 `src/commands/model/index.ts:5-15`。它导出一个 `Command` 定义，名字就是 `model`，`description` 会动态显示当前模型，`argumentHint` 是 `[model]`，`load` 则指向 `./model.js`。这里的作用不是执行逻辑，而是把 `/model` 这条命令挂到命令系统里。

第二个关键入口是 `src/commands/model/model.tsx:255-281` 的 `call` 函数。它是实际命令分发器：

- 无参数时，返回 `ModelPickerWrapper`
- 带帮助参数时，输出简短说明
- 带普通参数时，进入 `SetModelAndClose`
- 带 `info` 参数时，显示当前模型信息

另外，`src/commands.ts:219-230, 289-330` 把 `model` 这个命令注册进全局 `COMMANDS` 列表，所以 `/model` 并不是孤立存在的，它是命令中心的一部分。

## 主流程位置

主流程基本都在 `src/commands/model/model.tsx`：

1. `call()` 先清理参数并按 `COMMON_INFO_ARGS`、`COMMON_HELP_ARGS`、普通参数、空参数四路分流。
2. `ModelPickerWrapper` 负责交互式菜单。取消时只回显当前模型；选择后会写入 `mainLoopModel`，清空 `mainLoopModelForSession`，并顺带处理 fast mode、额外用量和日志事件。
3. `SetModelAndClose` 负责直接设置。它先做一层约束检查：
   - `isModelAllowed()` 检查组织级限制
   - `isOpus1mUnavailable()`、`isSonnet1mUnavailable()` 检查 1M 访问
   - `isKnownAlias()` 判断是否是预置别名
   - `validateModel()` 校验自定义模型名
4. 真正落状态的动作集中在 `setModel()`：更新 `mainLoopModel`、清空会话级覆盖、同步 fast mode 状态，并拼接用户可见结果消息。
5. `ShowModelAndClose` 负责读取当前模型和 `effortValue`，把“当前模型”与“会话覆盖”说清楚。

如果只看控制流，可以把它理解成：**展示状态 -> 校验输入 -> 写入 AppState -> 自动补偿 fast mode -> 输出结果**。这条链路比单纯的命令更完整，因为它还承担了用户感知层面的回显。

## 推荐阅读顺序

1. 先看 `src/commands/model/index.ts`，确认 `/model` 是如何被声明成命令的。
2. 再看 `src/commands.ts` 里 `model` 被加入全局命令表的位置，理解它如何进入命令系统。
3. 然后读 `src/commands/model/model.tsx` 的 `call()`，先抓四路分发。
4. 接着看 `ModelPickerWrapper` 和 `SetModelAndClose`，理解交互式和参数式两条主路径。
5. 最后回看 `src/utils/model/model.ts`、`src/utils/model/validateModel.ts`、`src/utils/model/check1mAccess.ts`、`src/utils/model/modelAllowlist.ts`，补齐命令层依赖的底层规则。

## 常见误区

第一，容易把这个目录当成“模型系统本体”。实际上它只是命令层入口，真正的模型解析、默认值、别名和兼容规则大多在 `src/utils/model/`。

第二，容易忽略 `mainLoopModelForSession`。这个字段会和 `mainLoopModel` 共同决定展示内容，`ShowModelAndClose` 里已经明确区分了“当前模型”和“会话覆盖模型”。

第三，容易以为 `/model` 只是改一个字符串。实际上它还会联动 fast mode、额外用量判断、1M 权限提示和组织级限制，所以不是纯配置写入。

第四，`default` 不是普通模型名，而是一个特殊语义：它会被转换成 `null`，再映射回默认模型设置。这一点在 `SetModelAndClose` 里很关键。

第五，别把 `index.ts` 当成实现文件。它只是命令描述与懒加载壳，真正逻辑都在 `model.tsx`。
