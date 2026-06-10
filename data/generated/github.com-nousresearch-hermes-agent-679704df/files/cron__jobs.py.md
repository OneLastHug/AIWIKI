# 文件：cron/jobs.py

## 一句话定位

`cron/jobs.py` 是 Hermes cron 功能的“作业数据库与状态机”层：负责把定时任务保存到 `~/.hermes/cron/jobs.json`，解析调度表达式，维护 `next_run_at`、运行状态、重复次数、输出目录和技能引用，但不负责真正执行 agent 或投递消息。

## 它暴露/定义了什么

这个文件主要定义四类能力：

1. 调度解析：`parse_duration()`、`parse_schedule()`、`compute_next_run()` 把用户输入的 `"30m"`、`"every 2h"`、cron 表达式、ISO 时间转换成统一的 schedule dict，并计算下一次运行时间。
2. Job CRUD：`create_job()`、`get_job()`、`list_jobs()`、`update_job()`、`remove_job()`、`resolve_job_ref()` 管理任务记录。
3. 运行状态推进：`get_due_jobs()`、`advance_next_run()`、`mark_job_run()`、`pause_job()`、`resume_job()`、`trigger_job()` 供调度器在 tick 周期内判断、预推进、结算。
4. 输出与维护：`save_job_output()` 保存每次运行输出；`rewrite_skill_refs()` 在 curator 合并或裁剪 skill 后修复 cron job 里的 skill 引用。

它还定义了关键常量和锁：`CRON_DIR`、`JOBS_FILE`、`OUTPUT_DIR`、`ONESHOT_GRACE_SECONDS`、`_jobs_file_lock`。其中 `_jobs_file_lock` 很重要，因为调度器可能并行跑 job，多个线程会同时读改写 `jobs.json`。

## 谁调用它

直接调用者主要有：

`cron/scheduler.py`：导入 `get_due_jobs()`、`advance_next_run()`、`mark_job_run()`、`save_job_output()`，这是运行时最核心的调用方。scheduler 负责 tick、执行任务、投递结果，而 `cron/jobs.py` 负责告诉它哪些任务到期、运行前后如何更新状态。

`tools/cronjob_tools.py`：把这些函数包装成 agent 可用的 cron 管理工具，例如创建、暂停、恢复、触发和删除任务。

`hermes_cli/cron.py`、`hermes_cli/web_server.py`、`gateway/platforms/api_server.py`：分别服务 CLI、Dashboard/API、OpenAI-compatible API server 等入口，提供任务列表、详情、创建和更新等管理能力。

`agent/curator.py`、`agent/curator_backup.py`：使用 `rewrite_skill_refs()` 或 `load_jobs()`/`save_jobs()`，在技能维护、备份恢复场景中同步 cron 任务引用。

测试覆盖集中在 `tests/cron/`、`tests/tools/test_cronjob_tools.py`、`tests/test_timezone.py` 等，说明该文件是 cron 子系统的稳定契约层。

## 它调用谁

它依赖 `hermes_constants.get_hermes_home()` 确定 profile-aware 的 Hermes home，因此任务和输出默认落在当前 profile 的 `cron/` 目录下。它调用 `hermes_time.now` 获取带 Hermes 时区语义的当前时间，避免直接使用系统时间造成时区不一致。写文件时调用 `utils.atomic_replace()`，通过临时文件、`fsync`、原子替换降低 `jobs.json` 或输出文件损坏风险。

可选依赖 `croniter` 用于解析和推进标准 cron 表达式；如果缺失，cron 表达式创建或下一次运行计算会失败或返回 `None`。在 profile 校验中，`_normalize_profile()` 延迟导入 `hermes_cli.profiles.normalize_profile_name()` 和 `resolve_profile_env()`。文件系统方面，它使用 `Path`、`tempfile`、`shutil`、`os.chmod` 管理目录、权限和输出清理。

## 核心流程

创建任务时，`create_job()` 先调用 `parse_schedule()` 解析调度；若是一次性任务且未指定 `repeat`，自动设为 `repeat=1`。随后规范化 skill、model、provider、base_url、script、toolsets、workdir、profile、context_from 等字段。`no_agent=True` 时必须提供 `script`，因为此模式跳过 agent，脚本本身就是任务。最后生成短 UUID，计算 `next_run_at`，读入现有 jobs，追加后写回 `jobs.json`。

调度运行时，scheduler 调用 `get_due_jobs()`。该函数在锁内读取所有任务，跳过 disabled job，恢复缺失的 `next_run_at`，把过期太久的 interval/cron 任务快进到未来时间，避免 gateway 重启后补跑一大批旧任务。仍在宽限期内且到期的任务会被返回给 scheduler。

执行前，scheduler 可调用 `advance_next_run()` 预先推进 recurring job 的 `next_run_at`。这是防崩溃设计：如果进程在执行中挂掉，重启后不会反复触发同一轮 recurring job。一次性任务不会被预推进，以便重启后仍可重试。

执行后，scheduler 调用 `mark_job_run()` 写入 `last_run_at`、`last_status`、`last_error`、`last_delivery_error`，增加 `repeat.completed`，达到重复次数上限时删除任务；否则重新计算 `next_run_at`。如果 recurring job 无法算出下一次时间，它会进入 `state="error"`，但不会被静默禁用。

输出保存由 `save_job_output()` 完成，路径为 `OUTPUT_DIR / job_id / timestamp.md`。`_job_output_dir()` 会拒绝包含 `..`、斜杠、反斜杠、绝对路径等危险 job id，防止输出写入或删除逃逸 cron output 目录。

## 关键函数的高层作用

`parse_schedule()` 是用户输入到内部 schedule 的入口，支持一次性 duration、循环 interval、cron 表达式和 ISO 时间戳，并把 naive 时间转换为本地时区感知时间。

`compute_next_run()` 是状态机的时间推进核心。一次性任务通过 `_recoverable_oneshot_run_at()` 提供短宽限期；interval 基于 `last_run_at + minutes`；cron 基于 `croniter` 从当前或上次运行时间推进。

`create_job()` 是任务记录构造器，承担大量兼容和校验逻辑，包括 legacy `skill` 与新 `skills` 对齐、profile/workdir 验证、`no_agent` 约束、默认投递目标选择。

`update_job()` 是受控更新入口。它禁止修改 `id`，因为 `id` 会参与输出路径；当 schedule、skills、workdir、profile 被更新时，会重新规范化派生字段。

`get_due_jobs()` 是调度器的读取端核心，负责“哪些任务现在该跑”以及“哪些错过太久应该快进”。它不执行任务，只返回规范化 job dict。

`mark_job_run()` 是执行后的结算核心，处理成功/失败、投递失败、重复次数、下一次运行、完成或错误状态。

`rewrite_skill_refs()` 是 curator 集成点，用于把 job 中旧 skill 名改为合并后的 umbrella skill，或删除已裁剪 skill，避免任务运行时静默失去预期指令。

辅助函数如 `_normalize_job_record()`、`_apply_skill_fields()`、`_normalize_workdir()`、`_normalize_profile()`、`_secure_file()` 主要负责兼容旧数据、输入规范化和权限收紧。

## 修改风险

最高风险是破坏 `jobs.json` 的读写兼容性。这个文件显式兼容旧字段，例如单数 `skill`、缺失 `next_run_at`、nullable `prompt/name/schedule_display`、naive timestamp。修改 schema 时必须考虑旧用户数据和手工编辑数据。

第二个风险是并发写入。`mark_job_run()`、`advance_next_run()`、`get_due_jobs()`、`rewrite_skill_refs()` 都依赖 `_jobs_file_lock` 保护读改写流程。绕过锁直接 `load_jobs()` 后 `save_jobs()`，可能覆盖另一个线程刚写入的运行状态。

第三个风险是路径安全。`id` 不可更新、`_job_output_dir()` 的校验、`remove_job()` 删除输出目录前先解析路径，都是为了避免路径逃逸。任何放宽 job id 或输出路径规则的改动都可能变成任意文件写入/删除问题。

第四个风险是调度语义。`advance_next_run()` 选择 recurring job 的 at-most-once 行为，`get_due_jobs()` 选择错过太久就快进，`ONESHOT_GRACE_SECONDS` 选择一次性任务短暂补偿。看似小的时间计算改动，可能造成重复执行、漏执行或重启后突发补跑。

第五个风险是 profile 与 workdir。`profile` 存的是稳定 profile 名而不是路径，`workdir` 必须是存在的绝对目录。修改这里会影响 scheduler 运行时的配置、凭据、脚本、skills、memory 和工具工作目录解析。

第六个风险是 curator skill 重写。`skills` 与 legacy `skill` 必须始终对齐，否则老调用方和新调用方会看到不同任务配置，导致任务运行时加载的技能不一致。
