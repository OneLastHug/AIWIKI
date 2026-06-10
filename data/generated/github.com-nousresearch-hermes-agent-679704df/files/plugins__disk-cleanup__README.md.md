# 文件：plugins/disk-cleanup/README.md

## 一句话定位

`plugins/disk-cleanup/README.md` 是 `disk-cleanup` 插件的对外说明页：它不参与运行时执行，而是定义这个插件的行为边界、自动清理策略、可用 slash command 和安全承诺，帮助维护者理解为什么该插件通过 hook 自动运行，而不是作为需要 agent 主动调用的 skill 或普通工具存在。

## 它暴露/定义了什么

该 README 暴露的是“插件契约”，不是 Python API。核心信息包括：

- 插件用途：自动跟踪并清理 Hermes 会话中产生的临时文件，例如测试脚本、临时输出、cron 输出、过期 Chrome profile。
- 作用范围：严格限制在 `$HERMES_HOME` 和 `/tmp/hermes-*`。
- 自动 hook：`post_tool_call` 用于发现和跟踪临时文件，`on_session_end` 用于在会话结束时触发 quick cleanup。
- 手动命令：`/disk-cleanup status`、`dry-run`、`quick`、`deep`、`track`、`forget`。
- 删除规则：`test` 每次会话结束删除，`temp` 超过 7 天删除，`cron-output` 超过 14 天删除；`research`、`chrome-profile`、大文件属于 deep 场景，需要提示确认。
- 安全规则：路径白名单、Windows mount 拒绝、状态目录和核心状态目录排除、`tracked.json` 原子写入。

运行时真正注册这些能力的是 `plugins/disk-cleanup/__init__.py`，清理规则实现位于 `plugins/disk-cleanup/disk_cleanup.py`，插件元数据位于 `plugins/disk-cleanup/plugin.yaml`。

## 谁调用它

README 本身不会被代码调用。根据当前片段推断，它主要被开发者、审查者和用户阅读，用来理解插件行为和操作命令；依据是文件只包含 Markdown 文档，没有被源码引用的迹象。

运行时调用链是另一层：`hermes_cli.plugins.discover_plugins()` 扫描并加载插件，读取 `plugin.yaml` 后导入插件模块，再由 `plugins/disk-cleanup/__init__.py` 的 `register(ctx)` 向插件系统注册 hook 和 slash command。工具调用结束后，`model_tools.py` 通过 `invoke_hook("post_tool_call", ...)` 触发自动跟踪；CLI、gateway 或会话收尾逻辑通过 `invoke_hook("on_session_end", ...)` 触发会话结束清理。用户在会话中输入 `/disk-cleanup ...` 时，插件注册的命令处理器 `_handle_slash()` 会接管。

## 它调用谁

README 不调用任何代码。其描述对应的运行时模块会调用以下对象：

- `hermes_cli.plugins.PluginContext.register_hook()`：注册 `post_tool_call` 和 `on_session_end`。
- `hermes_cli.plugins.PluginContext.register_command()`：注册 `/disk-cleanup`。
- `plugins/disk-cleanup/disk_cleanup.py`：执行状态文件读写、路径安全判断、分类判断、dry-run、quick/deep cleanup、状态格式化。
- `hermes_constants.get_hermes_home()`：解析 profile-aware 的 `$HERMES_HOME`。
- Python 标准库 `pathlib`、`json`、`shutil`、`datetime`：处理路径、状态 JSON、删除文件和时间阈值。

## 核心流程

插件加载时，`register(ctx)` 注册两个 hook 和一个 slash command。之后每次工具调用完成，`_on_post_tool_call()` 检查工具名：如果是 `write_file`，读取参数里的 `path`；如果是 `patch`，保守读取单文件 `path`；如果是 `terminal`，从命令和短输出中提取候选路径。候选路径进入 `_attempt_track()`，先确认文件存在，再由 `disk_cleanup.guess_category()` 判断是否属于 `test`、`temp` 或 `cron-output` 等可自动跟踪类别，最后调用 `track()` 写入 `$HERMES_HOME/disk-cleanup/tracked.json`。

会话结束时，`_on_session_end()` 查看本轮是否自动跟踪过 `test` 文件。如果有，就调用 `disk_cleanup.quick()`。`quick()` 会删除确定安全的项目：所有 `test`，超过 7 天的 `temp`，超过 14 天的 `cron-output`，并清理 `$HERMES_HOME` 下非受保护的空目录。它不会删除需要用户确认的研究资料、Chrome profile 或超大文件。

用户手动执行 `/disk-cleanup` 时，`_handle_slash()` 根据子命令分发：`status` 输出分类统计和 top-10 大文件，`dry-run` 只预览，`quick` 执行安全清理，`deep` 在当前 slash command 语境下不会真正交互确认，而是先 quick，再列出需要确认的项目，`track` 和 `forget` 修改跟踪集合。

## 关键函数的高层作用

`register(ctx)` 是插件入口，把自动 hook 和 slash command 接入 Hermes 插件系统。

`_on_post_tool_call()` 是自动跟踪入口，负责从工具调用参数和结果中提取可能新建的路径，但不直接决定分类和安全性。

`_on_session_end()` 是自动清理入口，只在本轮确实跟踪到测试类文件时触发 `quick()`，避免每次会话结束都无意义扫描。

`track()` 负责把安全范围内的文件写入 `tracked.json`，同时去重、记录大小和时间戳。

`guess_category()` 是自动分类核心，排除 `logs`、`memories`、`sessions`、`skills`、`plugins`、配置文件等敏感或长期状态，只接受符合命名模式的测试/临时文件，以及受限的 cron output。

`quick()` 是无提示清理核心，只删除规则上确定安全的文件和非受保护空目录。

`deep()` 支持更激进的清理，但需要外部传入 `confirm` 回调；README 中的 `/disk-cleanup deep` 更接近“列出需确认项”，不是静默删除。

辅助函数如 `load_tracked()`、`save_tracked()`、`fmt_size()`、`format_status()` 主要服务于状态持久化和展示，理解到这一层即可。

## 修改风险

最大风险是扩大删除范围。`is_safe_path()`、`guess_category()`、`quick()` 里的排除目录和阈值是安全边界，改动时必须防止误删 `$HERMES_HOME` 下的长期状态，例如 logs、sessions、memory、skills、plugins、cron 控制文件和配置文件。

第二类风险是 hook 触发频率。`post_tool_call` 在工具调用后运行，不能抛异常、不能做重扫描、不能阻塞主 agent 流程；当前实现通过 best-effort、异常吞掉和短输出扫描降低影响。若增加解析逻辑，应保持幂等和轻量。

第三类风险是并发和状态文件一致性。`_recent_test_tracks` 使用锁按 `task_id` / `session_id` 记录本轮新增测试文件；`tracked.json` 通过临时文件、备份和 rename 写入。修改这些逻辑可能造成重复清理、漏清理或状态损坏。

第四类风险是文档与实现漂移。README 描述的是用户可见契约，若修改 `disk_cleanup.py` 的阈值、分类名、受保护目录或 slash command 行为，需要同步更新此 README 和 `plugin.yaml`，否则用户会基于错误的清理预期操作。
