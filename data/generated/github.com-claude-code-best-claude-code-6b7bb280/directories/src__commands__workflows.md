# 目录：src/commands/workflows

## 它负责什么

这个目录当前承担的是“工作流脚本命令”的本地命令包装层。根据当前片段推断，它的职责不是自己解析工作流内容，而是把项目根目录下 `.claude/workflows/` 里的用户工作流文件，转换成 Claude Code 可见的 `/xxx` slash command 列表。

从实现上看，这里更像一个很薄的适配器：

- 读取当前工作目录 `getCwd()`
- 调用 `@claude-code-best/builtin-tools/tools/WorkflowTool/createWorkflowCommand.js` 提供的扫描逻辑
- 把扫描结果整理成可读文本返回给 CLI
- 当没有任何工作流文件时，返回提示文案，告诉用户把 YAML 或 Markdown 放到 `.claude/workflows/`

因此，这个目录的重点不是“执行工作流”，而是“发现和列出工作流入口”。

## 直接子目录地图

根据当前仓库片段，这个目录下没有直接子目录，只有一个文件：

- `src/commands/workflows/index.ts`

也就是说，它是一个单文件命令目录，没有再向下拆分出独立的 parser、renderer 或 helper 子目录。真正的工作流规则和扫描细节，已经下沉到 `packages/builtin-tools/src/tools/WorkflowTool/` 这一侧。

如果只看这个目录本身，可以把它理解为“命令注册层”；如果要看完整链路，就必须向上看 `src/commands.ts`，向下看 `packages/builtin-tools/src/tools/WorkflowTool/`。

## 关键入口

最关键的入口是 `src/commands/workflows/index.ts` 里的默认导出对象。它定义了一个 local command：

- `type: 'local'`
- `name: 'workflows'`
- `description: 'List available workflow scripts'`
- `supportsNonInteractive: true`

真正执行时，入口是内部的 `call` 函数。它的行为很直接：

1. 通过 `getWorkflowCommands(getCwd())` 读取当前目录的可用工作流
2. 如果结果为空，返回 “No workflows found...” 的提示
3. 如果有结果，把每个工作流整理成 `/name - description` 的文本列表输出

这个设计说明它是给 CLI 的“发现命令”，不是给运行时直接消费的“执行引擎”。

## 主流程位置

主流程实际上分成两层：

1. `src/commands/workflows/index.ts`
   - 负责把工作流扫描结果包装成命令输出
   - 只处理展示和返回，不做文件系统扫描细节

2. `packages/builtin-tools/src/tools/WorkflowTool/createWorkflowCommand.ts`
   - 负责真正扫描 `.claude/workflows/`
   - 过滤 YAML / Markdown 等工作流文件
   - 为每个文件构造 `Command` 对象
   - 在用户真正调用某个工作流时，读取文件内容并拼成提示词

另外，上游注册点在 `src/commands.ts`：

- `workflowCmd` 由 `feature('WORKFLOW_SCRIPTS')` 控制
- 条件开启后，通过 `require('./commands/workflows/index.js')` 装载
- 再并入总命令列表

所以完整路径是：**feature flag 开关 -> local command 注册 -> 扫描 `.claude/workflows/` -> 输出可用工作流列表 -> 用户调用时再读取具体文件内容**。

## 推荐阅读顺序

如果你是想快速建立这个目录的心智模型，建议按这个顺序看：

1. `src/commands/workflows/index.ts`
   - 先看这个目录自己做了什么

2. `src/commands.ts`
   - 看它如何被 CLI 总命令系统接入
   - 重点关注 `WORKFLOW_SCRIPTS` feature flag

3. `packages/builtin-tools/src/tools/WorkflowTool/createWorkflowCommand.ts`
   - 看工作流文件是怎么被扫描、筛选、封装成命令的

4. `packages/builtin-tools/src/tools/WorkflowTool/constants.ts`
   - 如果需要确认工作流目录名和支持的扩展名，再看这里

5. `packages/builtin-tools/src/tools/WorkflowTool/WorkflowTool.ts`
   - 如果你想理解“运行工作流”而不是“列出工作流”，再继续看这一层

## 常见误区

- 把 `src/commands/workflows` 误认为“工作流执行器”。实际上它更接近列表入口，真正执行逻辑在 `packages/builtin-tools/src/tools/WorkflowTool/`。
- 以为这里会维护很多子目录。根据当前片段，这个目录本身只有 `index.ts`，结构非常薄。
- 忽略 `feature('WORKFLOW_SCRIPTS')`。如果这个开关没启用，`src/commands.ts` 根本不会加载这里的命令。
- 只看本目录，不看 `.claude/workflows/` 约定。这个命令的价值来自项目里的用户工作流文件，不是来自代码目录本身。
- 把“列出工作流”和“执行工作流”混为一谈。这里输出的是可用项清单，真正把工作流内容变成可执行 prompt 的逻辑在下游工具包里。
