# 目录：src/commands/copy

## 它负责什么

这个目录实现的是 `/copy` 命令，核心职责是把最近一次助手回复复制到剪贴板；如果用户带上参数 `N`，则复制第 `N` 条最近的助手回复。它不是一个简单的“整段文本复制”工具，而是带有一些面向对话上下文的判断逻辑：会从当前会话消息里回溯可复制的 assistant message，必要时识别其中的 Markdown 代码块，让用户在“整段回复”和“某个代码块”之间选择。

从实现风格看，这里同时承担了三件事：命令注册、交互式选择 UI、以及真正的复制/落盘动作。复制并不只依赖系统剪贴板，还会写一份临时文件到系统临时目录下的 `claude` 子目录，作为剪贴板能力不稳定时的兜底。根据当前片段推断，这个设计主要是为了兼容终端环境里 OSC 52 不一定可用的情况。

## 直接子目录地图

这个目录下面没有更深的子目录，只有两个文件：

- `src/commands/copy/index.ts`：命令元数据层，负责把 `copy` 命令挂到全局命令系统里，并延迟加载真正实现。
- `src/commands/copy/copy.tsx`：实际功能实现，包含消息收集、Markdown 解析、交互选择器、复制与写文件逻辑。

也就是说，这里是一个很典型的“薄入口 + 重实现”结构，目录本身很小，但它接到的是完整的命令生命周期。

## 关键入口

最直接的入口是 `src/commands/copy/index.ts`。它导出一个 `Command` 对象，名字就是 `copy`，描述是“Copy Claude's last response to clipboard…”，并通过 `load: () => import('./copy.js')` 懒加载实现模块。这里的关键点是：启动时只加载最少元数据，真正的 UI 和逻辑在需要时才进来。

第二个入口是 `src/commands/copy/copy.tsx` 里的 `call`。这是实际执行 `/copy` 时被调用的函数，也是本目录最重要的函数。全局命令注册层 `src/commands.ts` 已经把 `src/commands/copy/index.ts` 纳入命令表，所以从整个应用角度看，`copy.tsx` 才是主流程的执行点。

## 主流程位置

主流程可以按下面这条线理解：

1. `call(onDone, context, args)` 先从 `context.messages` 里提取最近的 assistant 文本。
2. `collectRecentAssistantTexts(messages)` 负责倒序扫描消息，跳过非 assistant 消息和 API error 消息，只保留真正有内容的回复，最多回看 20 条。
3. 如果用户传了参数 `N`，就把它解释成“第 N 条最近回复”；`1` 是最新，`2` 是倒数第二条，以此类推。
4. 对目标回复执行 `extractCodeBlocks(markdown)`，把 Markdown 代码块抽出来。
5. 如果没有代码块，或者全局配置 `copyFullResponse` 已经开启，就直接把整段回复复制到剪贴板，并写入临时文件。
6. 如果存在代码块且没有开启“总是复制全文”，就渲染 `CopyPicker`，让用户选择：
   - `Full response`
   - 某个代码块
   - `Always copy full response`
7. 用户确认后，`copyOrWriteToFile()` 统一做剪贴板复制与临时文件写入；`handleWrite()` 则是按 `w` 快捷键只写文件、不复制剪贴板。

这里有几个辅助函数值得记住，但不用把它们当成独立流程来理解：

- `fileExtension()`：根据代码块语言决定文件后缀，并做了简单清洗，避免路径注入。
- `truncateLine()`：给选择器里的代码块标题做宽度截断。
- `writeToFile()` / `copyOrWriteToFile()`：分别处理临时文件写入和“剪贴板 + 文件兜底”的组合动作。

## 推荐阅读顺序

如果你是第一次看这个目录，建议按这个顺序读：

1. 先看 `src/commands/copy/index.ts`，确认这个命令在系统里的注册方式。
2. 再看 `src/commands/copy/copy.tsx` 顶部的 helper 函数，先建立数据流的基本印象。
3. 接着读 `collectRecentAssistantTexts()`、`extractCodeBlocks()` 和 `call()`，把“如何选中目标内容”这条主线看清楚。
4. 最后看 `CopyPicker`，理解交互式选择、快捷键 `w`、以及 `copyFullResponse` 的配置联动。
5. 如果想理解它在全局里的位置，再回到 `src/commands.ts` 看它如何被纳入命令注册表。

## 常见误区

- 容易误以为 `/copy` 只能复制最新一条回复。实际上它支持 `N` 参数，可以回看第 `N` 条最近的 assistant 回复。
- 容易误以为只要回复里有代码块就一定会弹出选择器。实际还要看 `copyFullResponse` 配置；如果这个开关已经打开，就直接复制全文。
- 容易忽略“复制”和“写文件”是两条不同路径。`Enter` 走复制逻辑，`w` 走写文件逻辑，而且 `w` 只写当前焦点内容，不会同步复制到剪贴板。
- 容易忽略临时文件兜底的存在。这里不是单纯依赖系统剪贴板，而是会把内容写到系统临时目录下，增强可用性。
- 容易把 `Always copy full response` 当成一次性选择。实际上它会修改全局配置，后续 `/copy` 默认不再弹出 picker，直到用户去 `/config` 改回去。

如果把这个目录抽象成一句话，就是：它是一个围绕“从历史回复中提取可复制内容”的小型交互命令模块，入口很薄，真正的行为集中在 `copy.tsx` 的 `call` 与 `CopyPicker` 两段主流程里。
