# 目录：src/commands/btw

## 它负责什么

`src/commands/btw` 负责实现 `/btw` 这个“即时本地 JSX 命令”。它的作用不是发起普通的主对话，而是让用户在 Claude 正在处理主任务时，临时插入一个侧边问题，拿到一个独立回答，同时尽量复用当前会话的上下文和缓存前缀。换句话说，它是一个“不中断主线程的快速追问”入口。

根据当前片段推断，这个目录还承担了两个配套职责：一是把 `/btw` 作为命令注册到命令系统里，二是渲染一个小型交互面板，显示问题、加载状态、回答内容，以及错误或退出提示。

## 直接子目录地图

根据当前片段推断，这个目录下面没有更深的子目录，只有两个直接文件：

- `src/commands/btw/index.ts`：命令定义与注册信息
- `src/commands/btw/btw.tsx`：命令执行时加载的 React/Ink 组件与核心逻辑

这个结构很典型：`index.ts` 负责告诉系统“有这么一个命令”，`btw.tsx` 负责真正跑起来。

## 关键入口

最关键的入口是 `src/commands/btw/index.ts`。这里导出一个 `Command` 对象，核心字段是：

- `type: 'local-jsx'`
- `name: 'btw'`
- `immediate: true`
- `argumentHint: '<question>'`
- `load: () => import('./btw.js')`

其中 `immediate: true` 很重要，说明它属于“立即型”本地 JSX 命令，不需要等完整命令流结束。`load()` 指向 `btw.js`，也就是运行时真正加载 `src/commands/btw/btw.tsx` 编译产物的地方。

另一个入口是 `btw.tsx` 中导出的 `call()`。它会接收：

- `onDone`：命令结束回调
- `context`：当前处理用户输入的上下文
- `args`：用户输入的 `/btw` 参数

如果参数为空，它会直接返回用法提示；如果有问题文本，就开始构建侧问流程。

## 主流程位置

主流程基本集中在 `src/commands/btw/btw.tsx`，可以按四段理解：

1. **参数校验与计数**
   `call()` 先 `trim()` 用户输入，空输入时返回 `Usage: /btw <your question>`。随后会把 `settings` 里的 `btwUseCount` 加一，用于后续提示和埋点式行为控制。

2. **界面渲染**
   `BtwSideQuestion` 组件负责显示 `/btw` 标题、问题文本、加载中的 `SpinnerGlyph`、最终 `Markdown` 回答，以及错误信息。它还支持键盘交互：`Esc`、`Enter`、空格或 `Ctrl+C/Ctrl+D` 关闭，`Up/Down` 或 `Ctrl+P/Ctrl+N` 滚动内容。

3. **缓存安全参数构建**
   `buildCacheSafeParams()` 是这里的核心逻辑之一。它会优先调用 `getLastCacheSafeParams()` 复用主线程最近一次发送给模型的 `systemPrompt`、`userContext`、`systemContext`，再配合当前 `toolUseContext` 和 `forkContextMessages` 组装侧问请求。这样做的目的，是尽量保持前缀字节一致，提升 prompt cache 命中率。

4. **真正发起侧问**
   组件挂载后会调用 `runSideQuestion({ question, cacheSafeParams })`。如果返回 `response`，就显示 Markdown；如果失败，则展示 `errorMessage(err)`；如果还在等待，就显示“Answering...”。

从依赖关系上看，这个目录的主流程还和这些位置连着：

- `src/utils/sideQuestion.ts`：侧问触发和检索逻辑的共用工具
- `src/utils/forkedAgent.ts`：缓存安全参数与 fork 上下文相关能力
- `src/screens/REPL.tsx`：把 `/btw` 视为 immediate local-jsx command 的宿主
- `src/components/PromptInput/PromptInput.tsx`、`src/components/Spinner.tsx`：输入高亮和提示文案的联动

## 推荐阅读顺序

1. 先看 `src/commands/btw/index.ts`，确认命令如何被注册。
2. 再看 `src/commands/btw/btw.tsx` 顶部的 import，建立它依赖了哪些上下文、工具和 UI 组件。
3. 接着读 `call()`，抓住参数校验、计数更新和组件返回这条主线。
4. 然后读 `BtwSideQuestion`，理解交互、渲染和异步请求的关系。
5. 最后看 `buildCacheSafeParams()`，这是这个目录最容易被忽略、但最影响体验的部分。

## 常见误区

- **把 `/btw` 当成普通聊天命令**：它更像是一个并行侧问入口，不是主对话的替代品。
- **只看 UI 不看上下文复用**：真正关键的是 `buildCacheSafeParams()`，它决定是否能复用主线程前缀和当前上下文。
- **忽略 `immediate: true`**：这个标记决定它会以即时命令方式工作，和普通延迟执行的命令不是一类。
- **以为没有输入就只是空白返回**：实际上它会显式回 `Usage: /btw <your question>`，这也是命令接口的一部分。
- **把滚动和退出逻辑看轻**：这里不是一次性纯文本输出，而是一个可交互面板，键盘控制是完整流程的一部分。
