# 目录：src/commands/feedback

## 它负责什么

`src/commands/feedback` 是 Claude Code 内置 `/feedback` 斜杠命令的命令层入口，同时提供别名 `/bug`。它本身不承担完整的反馈表单、脱敏、提交网络请求、GitHub issue 草稿生成等业务细节，而是把这些工作交给 `src/components/Feedback.tsx` 中的 `Feedback` Ink 组件完成。

从职责边界看，这个目录主要做三件事：

第一，声明命令元信息。`src/commands/feedback/index.ts` 定义命令名 `feedback`、别名 `bug`、命令类型 `local-jsx`、描述文案、参数提示 `[report]`，并通过 `load: () => import('./feedback.js')` 延迟加载真正的 JSX 实现。

第二，控制命令是否可用。`isEnabled()` 会根据环境变量、隐私级别、组织策略和用户类型隐藏该命令。例如 Bedrock、Vertex、Foundry、`DISABLE_FEEDBACK_COMMAND`、`DISABLE_BUG_COMMAND`、essential traffic only、`USER_TYPE === 'ant'`、以及 `allow_product_feedback` 策略不允许时，命令都会被禁用。

第三，把命令调用转换成 `Feedback` 组件渲染。`src/commands/feedback/feedback.tsx` 的 `call()` 从命令上下文里取 `abortController.signal`、当前会话 `messages` 和用户传入的参数，把它们传给 `renderFeedbackComponent()`，最终返回一个 React 节点。

因此，这个目录是“命令注册与组件桥接层”，不是反馈系统的全部实现。

## 直接子目录地图

该目录没有直接子目录，只有两个文件：

`src/commands/feedback/index.ts`：命令定义文件，负责注册 `/feedback` 与 `/bug`，声明命令类型、描述、参数提示、启用条件和懒加载入口。

`src/commands/feedback/feedback.tsx`：命令执行文件，负责把本地 JSX 命令上下文转换为 `Feedback` 组件所需的 props，并导出 `call()` 供命令系统调用。

根据当前片段推断，这里刻意保持为非常薄的一层：命令层只关心“什么时候出现、如何启动”，具体 UI 状态机、数据收集和提交逻辑都放在组件层，避免命令目录膨胀。

## 关键入口

最重要的入口是 `src/commands/feedback/index.ts` 的默认导出 `feedback`。它是一个满足 `Command` 类型的对象，会被 `src/commands.ts` 导入并放入 `COMMANDS()` 列表。命令系统后续通过统一的命令解析、过滤和执行流程识别它。

`feedback` 的关键字段包括：

`name: 'feedback'`：用户输入 `/feedback` 时匹配此命令。

`aliases: ['bug']`：用户输入 `/bug` 时也会进入同一条命令路径。

`type: 'local-jsx'`：表示该命令执行后会渲染一个本地 Ink/React 组件，而不是返回纯文本 prompt 或直接执行普通本地命令结果。

`argumentHint: '[report]'`：提示用户可以直接跟一段反馈描述，例如 `/feedback something broke`。这段参数会作为初始描述传入 UI。

`isEnabled()`：命令可见性与可用性的核心判断。这里不是简单 feature flag，而是综合环境变量、隐私模式、组织策略和内部用户类型。

`load: () => import('./feedback.js')`：真正执行时才加载 `feedback.tsx` 编译后的模块，符合命令系统里常见的懒加载模式。

第二个入口是 `src/commands/feedback/feedback.tsx` 的 `call()`。它接收 `onDone`、`context` 和可选 `args`，将 `args` 作为 `initialDescription`，然后调用 `renderFeedbackComponent()` 返回 `<Feedback />`。

`renderFeedbackComponent()` 也是一个值得注意的辅助入口。它把 `abortSignal`、`messages`、`initialDescription`、`backgroundTasks` 统一传入 `Feedback` 组件。虽然当前 `call()` 没有传 `backgroundTasks`，但这个函数保留了参数，说明它也可能被其他路径复用来启动同一个反馈界面。

## 主流程位置

主流程可以分成“命令注册”“命令启动”“反馈组件执行”三段。

第一段在 `src/commands.ts`。该文件静态导入 `feedback`，然后把它放进 `COMMANDS()` 返回的命令数组中。用户在 REPL 中输入斜杠命令后，命令系统会在这类内置命令列表里查找名称或别名。`/feedback` 和 `/bug` 都会命中 `src/commands/feedback/index.ts` 导出的同一个命令对象。

第二段在 `src/commands/feedback/index.ts` 和 `src/commands/feedback/feedback.tsx`。命令系统先通过 `isEnabled()` 判断是否允许展示和执行该命令；允许后通过 `load()` 动态导入实现模块；执行时进入 `call()`。`call()` 将命令参数保存为初始描述，并把当前会话消息、取消信号和完成回调传入 `Feedback` 组件。

第三段在 `src/components/Feedback.tsx`，这是实际业务主流程所在。`Feedback` 组件内部有 `Step` 状态机：`userInput`、`consent`、`submitting`、`done`。用户先输入或编辑问题描述；按 Enter 后进入 consent 确认页；确认后 `submitReport()` 收集报告数据；提交完成后显示反馈 ID，并允许按 Enter 打开浏览器起草公开 issue。

报告数据包括当前描述、消息数量、时间、平台、终端、版本、当前会话 transcript、最近一次 API 请求、内存错误日志、最后一个 assistant message id、Git 仓库状态，以及可能存在的 subagent transcript 和 raw transcript jsonl。敏感信息脱敏由 `redactSensitiveInfo()` 和 `getSanitizedErrorLogs()` 处理。提交动作由 `submitFeedback()` 完成，它会刷新 OAuth token、构造认证头，并向 Anthropic 反馈接口发送内容。这里涉及真实外部地址，文档中省略为 `[URL已移除]`。

另外，`generateTitle()` 会调用 `queryHaiku()` 为后续 issue 草稿生成标题；`createGitHubIssueUrl()` 会组合 issue 标题、描述、环境信息和错误日志，并按 URL 长度限制截断。真实 GitHub 地址在本文中省略为 `[URL已移除]`。

## 推荐阅读顺序

建议先读 `src/commands/feedback/index.ts`。它最短，也最能说明这个目录在命令系统中的角色：命令名、别名、类型、启用条件、懒加载入口都集中在这里。

然后读 `src/commands/feedback/feedback.tsx`。重点看 `call()` 如何从 `LocalJSXCommandContext` 取出 `abortController.signal` 和 `messages`，以及 `args` 如何变成 `initialDescription`。读完这里就能理解命令层和 UI 层之间的接口。

接着跳到 `src/components/Feedback.tsx`，只看结构即可，不必一开始逐行读。先抓住 `Feedback` 组件的状态机，再看 `submitReport()` 收集哪些数据，最后看 `submitFeedback()`、`generateTitle()`、`createGitHubIssueUrl()` 这些辅助函数。

如果想理解命令如何被全局发现，再回看 `src/commands.ts` 中对 `feedback` 的 import 和 `COMMANDS()` 数组位置。这里能确认 `/feedback` 是内置命令集合的一部分，不是插件命令或动态 skill 命令。

## 常见误区

不要把 `src/commands/feedback` 当成完整反馈功能目录。真正复杂的逻辑在 `src/components/Feedback.tsx`，包括 UI、脱敏、transcript 收集、API 提交、标题生成和 issue 草稿 URL 生成。

不要忽略 `isEnabled()`。这个命令在很多环境下不会出现，包括第三方云 provider、禁用反馈的环境变量、essential traffic only、内部 `ant` 用户路径，以及组织策略禁止产品反馈时。排查“为什么没有 `/feedback`”时应优先看这里。

不要把 `/bug` 理解成独立命令。它只是 `aliases: ['bug']`，最终进入同一个 `feedback` 命令和同一个 `Feedback` 组件。

不要以为命令参数会直接提交。`/feedback some text` 只会把 `some text` 作为表单初始描述，用户仍会进入确认流程，看到将包含的环境信息、Git 信息和 transcript，再确认提交。

不要把 FeedbackSurvey 和这个目录混为一谈。`src/components/FeedbackSurvey` 是会话中轻量满意度调查相关组件；它可能引导用户使用 `/feedback`，但不是 `/feedback` 命令本身的实现目录。

不要在学习这个目录时过度展开所有叶子逻辑。overview 深度下，重点是命令层如何注册、如何启用、如何跳转到 `Feedback` 组件；脱敏规则、URL 截断、OAuth 刷新、具体网络错误处理属于后续深入阅读主题。
