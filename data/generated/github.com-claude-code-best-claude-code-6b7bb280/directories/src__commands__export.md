# 目录：src/commands/export

## 它负责什么

`src/commands/export` 负责 REPL 内部的 `/export` 斜杠命令，用来把“当前会话上下文中的消息”渲染成纯文本，并导出到文件或交给交互式导出界面处理。它不是完整的导出系统，也不负责读取历史 session、解析日志索引、处理 `.json/.jsonl` 文件；那些属于 `src/main.tsx` 中注册的顶层 `claude export` 命令及其 handler 路径。

这个目录的职责可以概括为三件事：

第一，声明 `/export` 命令的元信息，包括命令名、说明、参数提示和懒加载入口。第二，在命令被触发时，从 `ToolUseContext` 里取出当前 `messages` 和可用 `tools`，调用 `renderMessagesToPlainText` 生成文本内容。第三，根据用户是否传入文件名决定导出路径：有参数时直接写入当前工作目录下的 `.txt` 文件；没有参数时返回 `ExportDialog`，由 Ink UI 继续处理文件名、保存或剪贴板等交互。

从目录规模看，这里是一个很薄的命令适配层。真正的消息渲染逻辑在 `src/utils/exportRenderer.tsx`，真正的交互 UI 在 `src/components/ExportDialog.tsx`，命令注册聚合在 `src/commands.ts`。

## 直接子目录地图

`src/commands/export` 当前没有直接子目录，只有两个文件：

`src/commands/export/index.ts` 是命令注册入口，导出一个 `Command` 对象。它声明该命令类型为 `local-jsx`，命令名为 `export`，描述为导出当前 conversation 到文件或剪贴板，参数提示为 `[filename]`，并通过 `load: () => import('./export.js')` 懒加载具体实现。

`src/commands/export/export.tsx` 是命令运行逻辑。它包含文件名生成、首条 prompt 提取、文件名清洗、消息渲染、直接写文件和返回 `ExportDialog` 的主流程。

由于没有子目录，这个目录不承担复杂分层；可以把它理解为 `/export` 命令的一层外壳。

## 关键入口

最直接的入口是 `src/commands/export/index.ts` 里的默认导出 `exportCommand`。这个对象满足 `Command` 类型，关键字段是：

`type: 'local-jsx'` 表明它会在本地 REPL 中渲染 React/Ink UI，而不是普通文本命令。相邻上下文里 `src/commands.ts` 对 `local-jsx` 命令还有 bridge safety 相关判断，默认这类命令不适合远程 bridge 执行，除非显式标记为 bridge-safe。

`name: 'export'` 决定用户在 REPL 里输入的斜杠命令名通常是 `/export`。

`argumentHint: '[filename]'` 说明文件名是可选参数。传入文件名时走直接写文件逻辑；不传时弹出导出对话框。

`load: () => import('./export.js')` 是懒加载实现，实际调用时加载 `src/commands/export/export.tsx` 编译后的模块。

上层聚合入口在 `src/commands.ts`。相邻上下文显示该文件通过 `import exportCommand from './commands/export/index.js'` 引入，并把它放入命令列表。也就是说，`src/commands/export` 自己只声明命令，不主动注册到 Commander；REPL 命令系统由 `src/commands.ts` 统一汇总。

需要区分的是，`src/main.tsx` 还注册了一个顶层命令 `claude export <source> <outputFile>`。它的描述是导出指定 session、日志索引或 `.json/.jsonl` 文件到文本，并懒加载 `src/cli/handlers/ant.js` 中的 `exportHandler`。这个顶层命令和本目录的 `/export` 同名但不是同一条执行链。

## 主流程位置

主流程集中在 `src/commands/export/export.tsx` 的 `call(onDone, context, args)` 函数。

流程第一步是渲染当前会话内容。`call` 先调用内部函数 `exportWithReactRenderer(context)`，后者取 `context.options.tools || []`，再调用 `renderMessagesToPlainText(context.messages, tools)`。这说明 `/export` 导出的对象是当前内存中的 conversation messages，并且渲染时会参考工具定义，以便把 tool use、tool result 或相关消息结构转成可读纯文本。具体格式不在本目录内定义，而在 `src/utils/exportRenderer.tsx`。

流程第二步是判断用户是否传入参数。`args.trim()` 得到 `filename`。如果文件名非空，命令会直接保存文件，不再显示 `ExportDialog`。保存前会确保扩展名为 `.txt`：如果用户传入的名字已经以 `.txt` 结尾，就直接使用；否则会把最后一个扩展名替换成 `.txt`。随后通过 `join(getCwd(), finalFilename)` 拼出当前工作目录下的目标路径，并调用 `writeFileSync_DEPRECATED(filepath, content, { encoding: 'utf-8', flush: true })` 写入。成功后通过 `onDone` 返回 `Conversation exported to: ...`，失败则返回 `Failed to export conversation: ...`。

流程第三步只在没有传入文件名时发生。命令会为弹窗生成默认文件名：先用 `extractFirstPrompt(context.messages)` 找到第一条 `type === 'user'` 的消息，从 string content 或 text block 中提取文本，取第一行，并限制到 50 个字符左右；再用 `sanitizeFilename` 做小写化、移除特殊字符、把空白替换成连字符、合并重复连字符、去掉首尾连字符。最终文件名形如 `YYYY-MM-DD-HHmmss-first-prompt.txt`。如果没有可用 prompt，则退回 `conversation-YYYY-MM-DD-HHmmss.txt`。

流程第四步是返回 React 节点：

`<ExportDialog content={content} defaultFilename={defaultFilename} onDone={...} />`

这说明无参数模式下，命令本身不直接决定最终导出动作，而是把内容和默认文件名交给 `src/components/ExportDialog.tsx`。根据 `index.ts` 的 description，可以推断该对话框覆盖“文件或剪贴板”这类交互，但具体按钮、校验和剪贴板实现应阅读组件本身确认。

## 推荐阅读顺序

1. 先读 `src/commands/export/index.ts`，确认这是一个 `local-jsx` 斜杠命令，以及它如何懒加载 `export.tsx`。
2. 再读 `src/commands.ts` 中引入和汇总 `exportCommand` 的位置，理解 `/export` 如何进入全局 REPL 命令列表。
3. 接着读 `src/commands/export/export.tsx` 的 `call`，这是本目录最核心的执行路径。
4. 然后读同文件的 `extractFirstPrompt`、`sanitizeFilename`、`formatTimestamp`，理解默认文件名策略。
5. 再跳到 `src/utils/exportRenderer.tsx` 的 `renderMessagesToPlainText`，看消息、工具调用、结果消息如何被转换成纯文本。
6. 最后读 `src/components/ExportDialog.tsx`，补齐无参数模式下的 UI 交互细节。
7. 如果要比较两套导出能力，再看 `src/main.tsx` 里的 `claude export` 注册，以及其指向的 `exportHandler`。这一步是相邻上下文，不属于本目录主线。

## 常见误区

第一个误区是把 `/export` 和 `claude export` 当成同一个命令。本目录实现的是 REPL 内部 local-jsx 命令，输入来源是当前 `ToolUseContext.messages`；`claude export` 是顶层 Commander 子命令，输入来源可以是 session ID、日志索引或日志文件路径。两者名字相同，但入口、参数语义和数据来源都不同。

第二个误区是认为这个目录负责完整的文本格式化。实际上 `export.tsx` 只是调用 `renderMessagesToPlainText`，格式化规则在 `src/utils/exportRenderer.tsx`。如果导出的正文内容不符合预期，应优先看 renderer，而不是只改 `src/commands/export`。

第三个误区是认为无参数时也会直接写文件。当前逻辑是：有 `args` 才直接写入 `getCwd()` 下的 `.txt` 文件；没有 `args` 时返回 `ExportDialog`，由 UI 继续处理。默认文件名只是传给对话框的建议值，不等于已经创建了文件。

第四个误区是忽略扩展名处理。传入 `report.md` 这类名字时，代码会替换为 `report.txt`；传入没有扩展名的名字时，根据当前实现 `filename.replace(/\.[^.]+$/, '') + '.txt'` 会追加 `.txt`。所以 `/export my-log` 最终会写 `my-log.txt`。

第五个误区是高估文件名清洗能力。`sanitizeFilename` 只保留小写英文数字、空白和连字符，再把空白转成连字符；中文 prompt 或大部分符号会被移除。对于中文首条 prompt，默认文件名可能退化为只有时间戳或较短片段。根据当前片段推断，这是为了生成跨平台相对安全的文件名，但并不是完整的国际化 slug 方案。

第六个误区是把 `writeFileSync_DEPRECATED` 名字里的 `DEPRECATED` 理解为这个功能不可用。这里只能说明项目中存在一个带历史命名的慢操作封装；是否应该迁移要看 `src/utils/slowOperations.js` 的约定和项目当前规范，不能只凭函数名判断。
