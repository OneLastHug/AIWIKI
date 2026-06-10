# 文件：packages/coding-agent/examples/extensions/README.md

## 一句话定位

`packages/coding-agent/examples/extensions/README.md` 是 `pi-coding-agent` 扩展示例目录的总览页，用来帮助开发者快速理解“扩展可以接入哪些能力、每类能力对应哪些示例文件、写一个扩展的最小结构是什么”。它不是运行时代码，而是扩展体系的索引型学习入口。

## 它暴露/定义了什么

这个文件主要定义三类信息。第一类是扩展的使用方式：可以通过 `pi --extension examples/extensions/permission-gate.ts` 显式加载扩展，也可以把扩展复制到 `~/.pi/agent/extensions/` 让系统自动发现。第二类是示例清单：按功能域组织大量扩展示例，包括生命周期与安全、自定义工具、命令与 UI、Git 集成、系统提示词与压缩、资源发现、消息通信、会话元数据、自定义 provider、外部依赖等。第三类是扩展编写范式：通过一个 TypeScript 片段展示默认导出函数接收 `ExtensionAPI`，然后用 `pi.on` 监听事件、用 `pi.registerTool` 注册工具、用 `pi.registerCommand` 注册命令。

它还强调了两个关键模式：字符串参数应使用 `StringEnum`，避免 Google API 不兼容；扩展状态应优先放进 tool result 的 `details`，再在 `session_start` 等事件中从会话分支重建，以支持 fork 和会话恢复。

## 谁调用它

严格说，运行时代码不会“调用”这个 README。它的直接消费者是扩展作者、维护者、AIWIKI 这类源码学习工具，以及需要从示例入手理解 `pi-coding-agent` 扩展 API 的用户。

根据当前片段推断，实际运行链路中会被调用的是 README 列出的 `.ts` 扩展文件，而不是 README 本身。用户通过 CLI 的 `--extension` 参数，或通过 `~/.pi/agent/extensions/` 自动发现机制，把扩展交给 `packages/coding-agent/src/core/extensions/loader.ts`、`runner.ts`、`wrapper.ts` 一类扩展基础设施加载和执行。依据是 README 的 Usage 段落明确写了 `--extension` 和扩展目录复制方式，同仓库也存在 `src/core/extensions/*` 文件。

## 它调用谁

README 本身不调用任何模块。它引用和示范的核心依赖包括 `@earendil-works/pi-coding-agent` 暴露的 `ExtensionAPI` 类型、`typebox` 的 `Type` schema 构造器，以及 `@earendil-works/pi-ai` 的 `StringEnum`。文档还指向 `packages/coding-agent/docs/extensions.md` 作为完整扩展文档入口。

从示例代码看，扩展运行时会依赖 `pi` 注入的 API 对象：`pi.on` 接入事件总线，`pi.registerTool` 把新工具挂到 agent 可调用工具集合，`pi.registerCommand` 把斜杠命令挂到交互命令系统；工具执行期间通过 `ctx.ui.confirm`、`ctx.ui.notify` 等 UI API 与用户交互，通过 `ctx.sessionManager.getBranch()` 读取会话历史并恢复状态。

## 核心流程

这个 README 描述的核心流程可以概括为“发现扩展、注册能力、运行时拦截或补充行为”。

第一步，开发者选择一个示例或编写自己的扩展文件。扩展文件通常默认导出一个函数，参数是 `ExtensionAPI`。第二步，CLI 通过 `--extension` 显式加载，或从用户扩展目录自动发现。第三步，扩展初始化时调用 `pi.on`、`pi.registerTool`、`pi.registerCommand` 等 API，将事件处理器、工具、命令、UI 渲染器、资源、provider 或状态逻辑注册到宿主。第四步，agent 会话运行时触发对应事件，例如工具调用前触发 `tool_call`，会话启动触发 `session_start`，模型切换触发 `model_select`，输入处理触发 `input`。第五步，扩展根据事件上下文决定是否放行、阻断、转换输入、展示 UI、调用自定义工具、更新状态或终止本轮执行。

README 中的分类表体现了扩展能力边界很广：既可以做安全门禁，如 `permission-gate.ts`、`protected-paths.ts`；也可以做工具增强，如 `todo.ts`、`tool-override.ts`、`structured-output.ts`；还可以深度改造交互体验，如 `modal-editor.ts`、`custom-footer.ts`、`doom-overlay/`；甚至可以接入 provider、远程 SSH、微虚拟机和外部依赖。

## 关键函数的高层作用

`export default function (pi: ExtensionAPI)` 是扩展入口。宿主加载扩展后调用它，并把可注册能力的 `pi` 对象传入。扩展初始化逻辑都应挂在这里。

`pi.on("tool_call", handler)` 用于订阅生命周期事件。README 示例在 `tool_call` 中检查 `bash` 命令是否包含 `rm -rf`，再通过确认弹窗决定是否返回 `{ block: true }`。这代表扩展可以在内置工具执行前做审计、确认、拦截或改写。

`ctx.ui.confirm` 是交互确认接口，适合危险操作门禁。类似的 UI API 在示例清单中还包括 `ctx.ui.select()`、`ctx.ui.setEditorText()`、`ctx.ui.setStatus()`、`ctx.ui.setWidget()`、`ctx.ui.setFooter()` 等，用于定制 TUI 行为。

`pi.registerTool` 用于注册自定义工具。工具需要声明 `name`、`label`、`description`、`parameters` 和 `execute`。其中 `parameters` 用 schema 描述模型可传入的结构化参数，`execute` 在模型调用工具时运行，并返回标准 tool result。

`execute(toolCallId, params, onUpdate, ctx, signal)` 是自定义工具的核心执行函数。它接收工具调用 ID、结构化参数、更新回调、上下文和取消信号，返回 `content` 和 `details`。README 特别强调 `details` 可用于持久化状态，这对 session fork 和恢复很重要。

`pi.registerCommand` 用于注册交互命令，例如 `/hello`。命令的 `handler` 接收参数和上下文，可以更新 UI、修改会话、触发运行时行为或调用扩展自己的逻辑。

`StringEnum` 的作用是定义字符串枚举参数。README 明确提示不要用 `Type.Union([Type.Literal(...)])` 表达字符串选项，因为这会影响 Google API 兼容性。

## 修改风险

这个文件虽然只是 README，但它是扩展示例体系的导航页，修改风险主要来自“文档与真实能力不一致”。如果新增、删除或重命名 `examples/extensions/*` 示例，却没有同步更新表格，用户会按照过期路径加载失败，AIWIKI 生成的学习文档也会误导读者。

第二个风险是 API 示例过期。README 中的代码片段直接展示 `ExtensionAPI`、`pi.on`、`pi.registerTool`、`pi.registerCommand`、`ctx.ui.*`、tool result `details` 等关键接口；如果底层类型或事件名变更，而这里仍保留旧写法，会导致扩展作者复制后无法通过类型检查或运行失败。

第三个风险是兼容性提示被误删。`StringEnum` 和 `details` 持久化不是普通风格建议，而是跨 provider 兼容和会话 fork 正确性的约束。删除这些说明会让示例看起来更短，但会增加自定义工具在 Google API、会话恢复、分支复制场景下的隐性故障。

第四个风险是分类边界混乱。当前 README 按能力域组织示例，便于读者从“我要做安全拦截、我要加工具、我要改 UI、我要接 provider”反向定位文件。随意移动条目或把实验性示例放进核心类别，可能降低学习效率，也会让扩展体系的能力边界变得不清晰。
