# 目录：src/commands/add-dir

## 它负责什么

`src/commands/add-dir` 负责“把一个目录加入当前 Claude Code 的可工作目录集合”这件事。它既是一个可从命令面板触发的本地 JSX 命令，也是整个权限/工作区体系里给用户新增目录的统一入口之一。根据当前片段推断，这个目录的职责不是单纯做字符串解析，而是把“路径校验、权限上下文更新、会话态生效、可选持久化”串成一条完整流程。

这里的目录还承担两个面向用户的场景：

1. 直接输入 `/add-dir <path>`，走校验后再决定是否加入。
2. 不带参数时，直接弹出目录选择/确认界面，让用户交互式添加。

## 直接子目录地图

这个目录下没有子目录，只有 3 个文件，结构很紧凑：

- `src/commands/add-dir/index.ts`：命令定义与懒加载入口。
- `src/commands/add-dir/add-dir.tsx`：真正执行 `/add-dir` 的 UI 和主逻辑。
- `src/commands/add-dir/validation.ts`：目录合法性校验与提示文案生成。

从结构上看，它是一个“单命令、小闭环”的目录，没有再向下拆分更多层级。主要复杂度都集中在 `add-dir.tsx` 的交互流程，以及 `validation.ts` 的判定规则。

## 关键入口

最外层入口是 `index.ts`。它导出一个 `Command` 描述对象，名字是 `add-dir`，类型是 `local-jsx`，并通过 `load: () => import('./add-dir.js')` 延迟加载实际实现。这说明它是挂在命令系统里的标准本地 JSX 命令，而不是一次性脚本。

上层注册点可以在两处看到：

- `src/commands.ts` 把 `addDir` 纳入全局命令集合。
- `src/main.tsx` 的 CLI 选项里有 `--add-dir <directories...>`，说明同一个概念也有启动参数版本，用于启动时预置可访问目录。

此外，`AddWorkspaceDirectory` 组件也复用了这里的校验逻辑，说明这个目录不仅服务于命令入口，也服务于权限 UI。

## 主流程位置

主流程集中在 `src/commands/add-dir/add-dir.tsx`。

它的核心顺序大致是：

1. 读取参数并拿到当前 `AppState`。
2. 如果没有传路径，就直接渲染 `AddWorkspaceDirectory` 交互界面。
3. 如果传了路径，先调用 `validateDirectoryForWorkspace()`。
4. 校验失败时，用 `addDirHelpMessage()` 生成错误提示，并通过 `AddDirError` 展示。
5. 校验成功后，再渲染 `AddWorkspaceDirectory`，让用户确认是否添加。
6. 真正添加时，`handleAddDirectory()` 会同步更新：
   - `toolPermissionContext`
   - `bootstrap/state` 里的 additional directories
   - `SandboxManager` 配置
   - 可选的本地设置持久化
7. 最后通过 `onDone()` 回传结果消息。

`validation.ts` 则负责把“能不能加”这件事说清楚。它会：

- 处理空路径。
- 用 `expandPath()` 和 `resolve()` 归一化路径。
- 用 `stat()` 判断是否存在且是否为目录。
- 把 `ENOENT`、`ENOTDIR`、`EACCES`、`EPERM` 归为“找不到路径”类结果。
- 检查目标目录是否已经包含在现有工作目录里，避免重复添加。
- 把失败原因映射成用户可读的帮助文案。

## 推荐阅读顺序

1. 先看 `src/commands/add-dir/index.ts`，确认它在命令系统里的形态。
2. 再看 `src/commands/add-dir/validation.ts`，理解路径校验和失败分支。
3. 最后看 `src/commands/add-dir/add-dir.tsx`，把“校验 -> UI -> 添加 -> 持久化”的完整链路串起来。
4. 如果要理解它如何影响整个程序，再回到 `src/commands.ts`、`src/main.tsx`，以及 `src/components/permissions/rules/AddWorkspaceDirectory.tsx`。

## 常见误区

1. 把它当成单纯的 CLI 参数处理目录。实际上它同时服务于命令入口、交互式界面和权限更新。
2. 只看 `add-dir.tsx` 不看 `validation.ts`。路径是否可加入的规则基本都在后者，漏看会误判失败分支。
3. 以为添加目录只改了一个状态。实际它还会刷新 sandbox 配置，并影响后续 Bash/文件访问范围。
4. 忽略“记住目录”和“仅本次会话”两种模式。`handleAddDirectory()` 里通过 `destination` 区分了 `localSettings` 与 `session`。
5. 把 `--add-dir` 和 `/add-dir` 视为不同体系。按现有代码看，它们是同一能力的两个入口，一个偏启动时配置，一个偏运行时交互。
