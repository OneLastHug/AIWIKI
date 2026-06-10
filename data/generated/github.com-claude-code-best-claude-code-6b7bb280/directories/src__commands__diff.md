# 目录：src/commands/diff

## 它负责什么

`src/commands/diff` 是终端里 `/diff` 命令的入口目录，职责很明确：把“查看差异”这件事包装成一个可调用的本地 JSX 命令。它同时覆盖两类差异来源：当前工作区的未提交变更，以及会话过程中每一轮产生的 per-turn diff。

从结构上看，这个目录不负责真正的 diff 计算，而是负责“命令层编排”。真正的数据获取和展示逻辑分别落在 `src/hooks/useDiffData.ts`、`src/hooks/useTurnDiffs.ts` 和 `src/components/diff/*` 里。根据当前片段推断，这里是一个很薄的适配层，核心任务是把命令系统、会话消息和差异视图串起来。

## 直接子目录地图

这个目录下没有子目录，只有两个文件：

- `src/commands/diff/index.ts`：命令注册描述文件，声明 `/diff` 的类型、名称、说明和懒加载入口。
- `src/commands/diff/diff.tsx`：命令执行入口，实际渲染 `DiffDialog`。

也就是说，这里没有继续向下拆的业务层级；它本身就是一个最外层的命令包装目录。若要理解完整链路，需要把视线移到同级的 `src/components/diff` 和更上层的 `src/commands.ts`。

## 关键入口

最关键的入口有三个层次：

1. `src/commands/diff/index.ts`
   这里定义了命令元数据：
   - `type: 'local-jsx'`
   - `name: 'diff'`
   - `description: 'View uncommitted changes and per-turn diffs'`
   - `load: () => import('./diff.js')`

   这说明 `/diff` 不是 prompt 命令，也不是 shell 命令，而是一个本地 React/Ink 视图命令。

2. `src/commands/diff/diff.tsx`
   这是命令真正的执行点。它会动态导入 `../../components/diff/DiffDialog.js`，然后把 `context.messages` 传进去，再把 `onDone` 交回给命令框架。

3. `src/commands.ts`
   这里把 `diff` 注册进全局 `COMMANDS` 数组。也就是说，命令系统是否能看到 `/diff`，最终取决于这里的汇总注册。

## 主流程位置

主流程可以按“入口 -> 对话框 -> 子视图”理解：

- `src/commands/diff/index.ts` 先把 `/diff` 声明为可加载命令。
- `src/commands/diff/diff.tsx` 进入 UI 层，创建 `DiffDialog`。
- `src/components/diff/DiffDialog.tsx` 是主控制器：
  - 通过 `useDiffData()` 读取当前工作区 diff；
  - 通过 `useTurnDiffs(messages)` 收集每一轮会话 diff；
  - 把两类来源合并成 `sources`；
  - 用 `viewMode` 在“文件列表”与“单文件详情”之间切换；
  - 用 `useKeybindings()` 处理左右切换 diff 来源、上下移动文件、回车进入详情、返回列表、退出对话框等交互。
- `src/components/diff/DiffFileList.tsx` 负责列表模式，处理滚动窗口、文件数分页、选中文件高亮和行数摘要。
- `src/components/diff/DiffDetailView.tsx` 负责详情模式，按文件类型分支展示：
  - 普通文件：读取本地文件内容，交给 `StructuredDiff`
  - `isUntracked`：提示新文件尚未暂存
  - `isBinary`：提示二进制文件不可显示
  - `isLargeFile`：提示超过大小限制
  - `isTruncated`：提示内容被截断

这里最重要的控制点是 `DiffDialog`。它既决定“当前看哪个来源”，也决定“当前看列表还是详情”，还是整个 `/diff` 体验的状态机核心。

## 推荐阅读顺序

1. 先看 `src/commands/diff/index.ts`
   先确认它在命令体系里的身份。

2. 再看 `src/commands/diff/diff.tsx`
   这一步能知道命令如何把上下文送入 UI。

3. 然后看 `src/components/diff/DiffDialog.tsx`
   这是主流程中枢，最能体现整个目录的行为模型。

4. 接着看 `src/components/diff/DiffFileList.tsx`
   理解列表如何分页、选中和显示统计。

5. 最后看 `src/components/diff/DiffDetailView.tsx`
   看单文件详情如何接入 `StructuredDiff`，以及各种特殊文件状态如何被兜底。

如果要补全上下文，再回到 `src/commands.ts` 看 `/diff` 是怎样被装配进全局命令表的。

## 常见误区

1. 以为 `src/commands/diff` 里包含 diff 算法本身  
   实际上不是。这里主要是命令壳层和 UI 编排，真实 diff 展示逻辑在 `src/components/diff`，数据来源在 hooks 里。

2. 以为它只看 git 工作区  
   不对。它同时支持当前工作区差异和会话内 per-turn diff，`DiffDialog` 会把两种来源合并成可切换的视图源。

3. 以为列表和详情是两个独立页面  
   实际上它们是同一个对话框里的两种模式，由 `viewMode` 切换。

4. 以为 `DiffDetailView` 只是渲染补丁文本  
   它还会读取磁盘上的实际文件内容，用于语法与多行结构判断，并对未跟踪、二进制、大文件等情况做专门分支处理。

5. 以为这里有很多目录层次  
   当前片段里没有子目录，目录本身很薄，真正的复杂度被拆到相邻的组件和 hooks 中了。
