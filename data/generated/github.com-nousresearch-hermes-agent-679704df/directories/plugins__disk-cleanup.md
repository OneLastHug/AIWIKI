# 目录：plugins/disk-cleanup

## 它负责什么

`plugins/disk-cleanup` 是 Hermes Agent 的一个通用插件，用来自动跟踪并清理会话过程中产生的临时性文件。它关注的对象不是用户长期资产，而是测试脚本、临时输出、cron 输出、过期的 chrome profile、空目录等“运行过程副产物”。它的设计目标是把清理行为从 agent 的显式操作中拿出来，改为通过插件 hook 自动发生：agent 不需要记得调用某个工具或技能，插件会在工具调用后尝试识别新产生的可清理文件，并在会话结束时执行安全清理。

这个插件的安全边界很明确：清理范围被限制在 `HERMES_HOME` 和 `/tmp/hermes-*` 之内。`disk_cleanup.py` 中的 `is_safe_path()` 会拒绝范围外路径，README 也强调不会触碰系统目录、agent 日志目录和核心配置/状态目录。插件自己的状态保存在 `$HERMES_HOME/disk-cleanup/`，主要包括 `tracked.json` 和 `cleanup.log`，不放在普通日志目录下。

从职责上看，它分成两层：`__init__.py` 负责接入 Hermes 插件系统、处理 hook 和 slash command；`disk_cleanup.py` 负责实际的确定性清理规则、状态读写、路径安全判断和状态格式化。`plugin.yaml` 则声明插件元数据和需要的 hook。

## 直接子目录地图

该目录当前没有直接子目录，只有少量顶层文件：

`plugins/disk-cleanup/plugin.yaml`：插件清单，声明名称 `disk-cleanup`、版本、描述、作者，以及使用的 hook：`post_tool_call`、`on_session_end`。

`plugins/disk-cleanup/__init__.py`：插件入口层。这里维护工具调用后的自动跟踪逻辑、会话结束时的自动 quick cleanup 逻辑，以及 `/disk-cleanup` slash command 的参数分发。

`plugins/disk-cleanup/disk_cleanup.py`：核心库层。这里实现路径安全判断、`tracked.json` 状态管理、分类规则、`track()`、`forget()`、`dry_run()`、`quick()`、状态展示和日志写入等功能。

`plugins/disk-cleanup/README.md`：面向维护者的说明文档，概括 hook 行为、删除阈值、slash command 和安全策略。

## 关键入口

第一入口是 `plugin.yaml`。Hermes 的通用插件系统会发现 `plugins/<name>/plugin.yaml`，读取插件元数据，并按插件加载约定导入对应包。这里的 `hooks` 字段表明插件会参与 `post_tool_call` 和 `on_session_end` 两个生命周期点。

第二入口是 `plugins/disk-cleanup/__init__.py`。从当前片段可见，它定义了 `_on_post_tool_call()`、`_on_session_end()` 和 `_handle_slash()`。根据 Hermes 插件体系和该文件的职责说明推断，文件后部应通过插件 `register(ctx)` 一类注册函数把这些回调挂到插件上下文中：`post_tool_call` 用于工具调用后检查候选路径，`on_session_end` 用于会话结束时触发 quick cleanup，CLI 子命令则暴露为 `/disk-cleanup`。

第三入口是手动 slash command：`/disk-cleanup`。`_handle_slash()` 支持 `status`、`dry-run`、`quick`、`deep`、`track <path> <category>`、`forget <path>`。这些命令不是 agent 工具，而是插件注册到 Hermes CLI/命令体系中的用户操作入口，用于查看状态、预演清理、立即清理或手动维护跟踪列表。

## 主流程位置

自动跟踪主流程位于 `plugins/disk-cleanup/__init__.py` 的 `_on_post_tool_call()`。它只关注少数可能创建文件的工具调用：`write_file`、`patch`、`terminal`。对于 `write_file` 和 `patch`，它从参数里取路径；对于 `terminal`，它会从命令参数和较短的输出文本中提取类似文件路径的片段。提取出的候选路径交给 `_attempt_track()`，后者会检查路径是否存在，调用 `disk_cleanup.guess_category()` 推断分类，再通过 `disk_cleanup.track(..., silent=True)` 写入跟踪状态。只有分类为 `test` 的新跟踪项会被记录到 `_recent_test_tracks`，供会话结束时判断是否需要自动清理。

会话结束主流程位于 `_on_session_end()`。它会从 `_recent_test_tracks` 中取出本轮新跟踪的测试文件记录；如果本轮没有相关记录，就直接返回。若存在测试文件记录，则调用 `disk_cleanup.quick()` 执行安全清理。清理有结果时，会通过 `disk_cleanup._log()` 写入 `$HERMES_HOME/disk-cleanup/cleanup.log`，记录删除数量、空目录数量和释放空间。这里的设计是“有测试副产物才自动 quick”，避免每个会话结束都无差别扫描和清理。

实际清理规则位于 `plugins/disk-cleanup/disk_cleanup.py`。`track()` 负责校验分类、校验路径安全、去重并写入 `tracked.json`；`forget()` 只从跟踪列表移除路径，不删除文件；`dry_run()` 返回“可自动删除”和“需要确认”的两组项目；`quick()` 执行无交互的安全删除。根据代码注释和 README，`test` 会在任务结束后删除，`temp` 超过 7 天删除，`cron-output` 超过 14 天删除，`research`、`chrome-profile` 和大文件倾向于进入需要确认的 deep 列表，而不是自动删除。

状态管理主流程也在 `disk_cleanup.py`。`get_state_dir()`、`get_tracked_file()`、`get_log_file()` 统一把状态放到 `get_hermes_home() / "disk-cleanup"` 下。`load_tracked()` 读取 `tracked.json`，在 JSON 损坏时尝试从 `.bak` 恢复；`save_tracked()` 采用 `.tmp` 写入、备份旧文件、再替换的方式，降低状态文件损坏风险。`_log()` 是审计日志入口，但它吞掉 `OSError`，避免日志写入失败影响 agent 主流程。

## 推荐阅读顺序

建议先读 `plugins/disk-cleanup/README.md`，快速建立插件意图、清理分类和安全边界的整体认识。这里能帮助你先分清哪些内容会自动删除，哪些只是 deep 模式下列出并等待确认。

第二步读 `plugins/disk-cleanup/plugin.yaml`，确认它不是普通工具模块，而是一个通过插件 hook 运行的通用插件。重点看 `hooks` 字段，因为这决定它接入的是工具调用后和会话结束两个阶段。

第三步读 `plugins/disk-cleanup/__init__.py`。先看文件顶部 docstring，它已经把三类行为讲清楚：`post_tool_call` 自动跟踪、`on_session_end` 自动 quick cleanup、`/disk-cleanup` 手动命令。然后看 `_extract_paths_from_write_file()`、`_extract_paths_from_patch()`、`_extract_paths_from_terminal()`，再看 `_on_post_tool_call()` 和 `_on_session_end()`，最后看 `_handle_slash()` 的命令分发。

第四步读 `plugins/disk-cleanup/disk_cleanup.py`。建议按“路径和状态、路径安全、分类与跟踪、预演、quick 清理、状态展示”的顺序看。这个文件是理解真实删除行为的关键，尤其要关注 `is_safe_path()`、`track()`、`dry_run()` 和 `quick()`。

## 常见误区

第一个误区是把它当成 agent 必须主动调用的工具。实际上它的核心价值正是“自动”：通过 `post_tool_call` 和 `on_session_end` hook 工作，不依赖 agent 在对话中记得运行清理命令。`/disk-cleanup` 只是手动管理入口，不是主流程必需步骤。

第二个误区是以为它会扫描整个磁盘。它不会。`is_safe_path()` 明确把候选路径限制在 `HERMES_HOME` 或 `/tmp/hermes-*`，并且 README 强调系统目录、日志目录、插件目录等敏感位置不会被清理。理解这个边界比记住每个分类更重要。

第三个误区是把 `deep` 理解成“更激进地自动删除”。根据当前片段和 README，`deep` 在 slash command 中会先运行 `quick()`，然后列出需要提示确认的项目；在会话内它不能做真正的交互式确认。因此 deep 更像“安全清理 + 风险项报告”，不是无提示大扫除。

第四个误区是忽略 `tracked.json`。插件不会凭空删除任意匹配文件，主要依据跟踪状态和分类规则工作。自动跟踪发生在工具调用后，手动 `track` 也会写入同一状态文件。调试“为什么没有清理”时，应同时检查路径是否被跟踪、分类是否正确、年龄阈值是否满足、路径是否仍存在、是否位于安全范围内。

第五个误区是把空目录清理和文件分类清理混为一谈。`quick()` 除了处理 tracked 文件，还会删除 `HERMES_HOME` 下的空目录，但会保护一批顶层状态目录，如 `logs`、`sessions`、`plugins`、`skills`、`disk-cleanup` 等。也就是说，空目录清理是附加的 housekeeping 行为，不等同于对所有目录递归删除。
