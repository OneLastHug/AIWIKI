# 目录：src/commands/stickers

## 它负责什么

`src/commands/stickers` 是 Claude Code 内置 slash command `/stickers` 的实现目录。它的职责非常单一：当用户在交互式 REPL/TUI 中执行 `stickers` 命令时，尝试调用系统浏览器打开 Claude Code 贴纸订购页面，并把执行结果以文本形式返回给命令系统。

这个目录不是贴纸资源目录，也不包含图片、素材、下载逻辑或订单 API。它只是一个“打开外部页面”的本地命令包装层。目录中的实现依赖 `src/utils/browser.js` 提供的 `openBrowser()`，真正的平台差异、浏览器打开方式、命令执行细节都不在本目录内。

从命令元数据看，`stickers` 被声明为 `type: 'local'`，意味着它是本地执行的命令，而不是 prompt 扩展命令、JSX UI 命令或 Commander CLI 子命令。它还设置了 `supportsNonInteractive: false`，说明它不支持非交互模式；也就是说，它更偏向 `/stickers` 这类 REPL 内部命令，而不是 `claude -p` 或脚本管道里的稳定输出能力。

## 直接子目录地图

这个目录没有直接子目录，只有两个顶层文件：

`src/commands/stickers/index.ts`：命令声明入口。这里定义命令名称、描述、类型、是否支持非交互，以及懒加载执行模块的 `load` 函数。

`src/commands/stickers/stickers.ts`：命令执行入口。这里导出 `call()`，负责打开外部贴纸页面，并返回 `LocalCommandResult`。

因此阅读这个目录时，不需要建立复杂的模块地图。它是典型的“小命令目录”：`index.ts` 负责注册元信息，具体行为放在同名实现文件中。

## 关键入口

最关键的入口是 `src/commands/stickers/index.ts`。它默认导出一个满足 `Command` 类型的对象：

`type: 'local'` 表示这是一个本地命令。

`name: 'stickers'` 决定用户侧命令名，也就是通常看到的 `/stickers`。

`description: 'Order Claude Code stickers'` 用于帮助列表、命令选择器或自动补全展示。

`supportsNonInteractive: false` 表示该命令不进入非交互命令能力范围。

`load: () => import('./stickers.js')` 是懒加载入口。命令列表加载时只需要命令元数据，真正执行时才导入 `stickers.ts` 对应的运行模块。这里源码使用 `.js` 后缀是 TypeScript ESM 项目的常见写法，运行或构建后由模块解析对应产物。

执行入口在 `src/commands/stickers/stickers.ts` 的 `call()`。它构造贴纸页面地址，调用 `openBrowser(url)`，然后根据返回值生成文本结果。成功时返回类似“正在浏览器中打开贴纸页面”的文本；失败时返回“无法打开浏览器，请访问：[URL已移除]”这一类提示。注意文档中不展开真实地址，源码里实际常量是外部贴纸页面。

## 主流程位置

从当前片段可以确定的注册链路在 `src/commands.ts`。该文件导入 `src/commands/stickers/index.js`，并把 `stickers` 放入内置命令集合中。也就是说，`src/commands/stickers` 本身只定义命令，真正让它出现在全局命令列表里的是 `src/commands.ts`。

主流程可以概括为：

用户在交互式界面中输入 `/stickers`。

命令系统在内置命令集合里找到 `name: 'stickers'` 的本地命令。根据当前片段推断，这个匹配和分发由 REPL/命令系统统一处理，依据是 `stickers` 只提供 `Command` 元数据和 `load()`，本目录没有自行解析用户输入的逻辑。

命令执行器调用 `load()`，动态导入 `src/commands/stickers/stickers.ts` 对应模块。

执行器调用模块导出的 `call()`。

`call()` 调用 `openBrowser(url)` 尝试打开外部页面。

如果 `openBrowser()` 返回 `true`，命令返回 `{ type: 'text', value: ... }`，告诉用户浏览器正在打开；如果返回 `false`，命令仍然返回文本结果，但内容变成失败提示和备用访问地址。

另外，`src/commands.ts` 的 `REMOTE_SAFE_COMMANDS` 集合中也包含 `stickers`，注释说明这类命令在 remote mode 下被认为是安全的。本命令不访问项目文件、不读写 git、不运行 shell 工具，也不依赖 IDE/MCP 上下文，因此符合“低副作用命令”的形态。不过它仍然有一个本地副作用：尝试打开浏览器。理解 remote safe 时不要把它等同于“完全无副作用”，它更像是“不会破坏本地工程状态”。

## 推荐阅读顺序

建议先读 `src/commands/stickers/index.ts`。这个文件最短，但包含了判断命令身份的全部关键信息：它叫什么、属于哪种命令、是否支持非交互、执行模块从哪里加载。读完这个文件后，就能知道 `/stickers` 在命令系统里的位置。

第二步读 `src/commands/stickers/stickers.ts`。这里是实际行为：导入 `LocalCommandResult` 类型和 `openBrowser()`，实现 `call()`。重点关注它没有参数解析、没有状态读写、没有权限检查，也没有复杂错误对象，只把浏览器打开结果折叠成一个文本返回值。

第三步看 `src/commands.ts` 中和 `stickers` 相关的几处引用。这里能看到它被导入到全局命令集合，并被加入 `REMOTE_SAFE_COMMANDS`。这一步的价值不在于理解贴纸命令本身，而是理解“一个小型内置 slash command 如何接入整体命令系统”。

如果还要继续向外追踪，可以看 `src/utils/browser.js` 或其 TypeScript 源文件对应实现，确认 `openBrowser()` 在不同平台上如何工作。但这已经超出 `src/commands/stickers` 的目录职责，属于依赖工具函数的下游细节。

## 常见误区

第一个误区是把这个目录当成“贴纸功能模块”。实际上它没有贴纸数据模型、订单流程、素材文件或支付集成，只是打开一个外部页面。它更接近快捷入口，而不是业务系统。

第二个误区是把 `stickers` 理解成顶层 CLI 子命令。根据当前片段，它注册在 `src/commands.ts` 的内置命令体系中，且 `supportsNonInteractive: false`，更符合 REPL slash command 的模式，不是 `src/main.tsx` 里 Commander 注册的那类完整命令。

第三个误区是忽略 `load()` 的懒加载意义。`index.ts` 不直接导入执行函数，而是返回 `import('./stickers.js')`。这让命令列表可以先加载元数据，只有真正执行时才加载实现模块。对于这个小命令性能差异不大，但它符合整个命令系统的统一结构。

第四个误区是认为 `REMOTE_SAFE_COMMANDS` 意味着命令完全没有外部行为。`/stickers` 不会改项目文件，也不需要本地开发上下文，但它会尝试打开浏览器。因此它是“对工程状态安全”，不是“没有任何系统交互”。

第五个误区是把失败路径当成异常处理。`call()` 没有抛出自定义异常，也没有返回错误类型；它只是根据 `openBrowser()` 的布尔结果返回普通文本。命令调用方看到的仍是 `type: 'text'` 的 `LocalCommandResult`，失败信息是展示内容的一部分，而不是独立错误通道。
