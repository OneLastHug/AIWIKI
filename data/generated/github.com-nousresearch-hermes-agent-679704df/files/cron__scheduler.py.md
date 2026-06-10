# 文件：cron/scheduler.py

## 一句话定位

`cron/scheduler.py` 是 Hermes 内置 cron 自动化的执行调度层：负责定期扫描到期任务、加锁防重入、运行脚本或唤醒 `AIAgent`、保存输出，并把结果投递回消息平台或本地审计目录。

## 它暴露/定义了什么

该文件主要定义调度器运行时能力，而不是任务存储模型。核心公开面包括 `tick()`、`run_job()`、`SILENT_MARKER`，以及一组被测试和网关复用的解析/投递辅助函数，例如 `_resolve_delivery_targets()`、`_resolve_delivery_target()`、`_deliver_result()`、`_run_job_script()`、`_build_job_prompt()`、`_parse_wake_gate()`、`_resolve_home_env_var()`、`_is_known_delivery_platform()`。

它还定义了 `CronPromptInjectionBlocked`，用于在组装后的 cron prompt 命中注入扫描时中断任务执行，避免非交互式、自动批准的 cron agent 被恶意 skill 或动态内容劫持。

## 谁调用它

最主要调用方是 `gateway/run.py` 的 `_start_cron_ticker()`。网关后台线程默认每 60 秒调用一次 `cron.scheduler.tick(verbose=False, adapters=adapters, loop=loop)`，并把当前运行中的平台 adapter 与 asyncio loop 传进来，方便 cron 结果优先走 live adapter 投递。

`hermes_cli/cron.py` 的 `cron_tick()` 也会调用 `tick(verbose=True)`，用于 `hermes cron tick` 这类手动触发场景。`cron/__init__.py` 重新导出 `tick`，测试集中也直接导入 `run_job()`、`_build_job_prompt()`、`_run_job_script()`、投递解析函数等做边界验证。

## 它调用谁

任务存储和状态更新依赖 `cron/jobs.py`：`get_due_jobs()` 获取到期任务，`mark_job_run()` 记录运行结果，`save_job_output()` 持久化输出，`advance_next_run()` 推进下一次运行时间。

配置和路径依赖 `hermes_constants.get_hermes_home()`、`hermes_cli.config.load_config()`、`_expand_env_vars()`，并通过 `_job_profile_context()` 临时切换 Hermes profile。执行 agent 时，根据当前片段和测试引用推断，`run_job()` 会直接构造 `run_agent.AIAgent` 并调用对话接口。消息投递依赖 `tools.send_message_tool._send_to_platform()`、`gateway.config.load_gateway_config()`、`gateway.platforms.base.BasePlatformAdapter`，有 live adapter 时优先调用 adapter 的 `send()`、`send_voice()`、`send_image_file()`、`send_video()`、`send_document()`。

## 核心流程

调度入口是 `tick()`。根据文件头注释和上下文，它会使用 `~/.hermes/cron/.tick.lock` 一类文件锁避免多个进程或线程重叠执行。进入临界区后，`tick()` 从 `cron/jobs.py` 读取 due jobs，对每个任务调用 `run_job()`，最后根据任务类型推进下一次运行或记录失败。profile 任务会串行运行，因为 `_job_profile_context()` 会临时修改进程环境变量，不能和其他任务并发混用。

`run_job()` 是单个任务的执行编排。它会处理任务的 profile、脚本、no-agent 模式、prompt 构造、工具集限制、agent 调用、输出保存和结果投递。任务如果配置了 `script`，先由 `_run_job_script()` 在 `HERMES_HOME/scripts/` 沙盒内执行；脚本输出可作为 prompt 上下文，也可通过最后一行 JSON 的 `{"wakeAgent": false}` 作为 wake gate 跳过 agent。

agent 路径会通过 `_build_job_prompt()` 把脚本输出、原始 prompt、skill 内容组合成最终 prompt，并进行注入风险防护。cron agent 的工具集会经过 `_resolve_cron_enabled_toolsets()` 和 `_resolve_cron_disabled_toolsets()` 收窄：`cronjob`、`messaging`、`clarify` 永远禁用，同时叠加用户配置里的 `agent.disabled_toolsets`，避免定时任务自我增殖、等待交互或绕过全局 denylist。

输出完成后，`save_job_output()` 保存本地审计记录。若响应以 `SILENT_MARKER` 开头，则根据注释语义跳过外部投递但仍保留本地输出。否则 `_deliver_result()` 根据 `deliver` 字段解析目标，例如 `local`、`origin`、平台名、显式 `platform:chat`，以及 `all` token，再投递到一个或多个目标。

## 关键函数的高层作用

`tick()` 是调度器心跳，负责加锁、找 due jobs、触发执行和推进调度状态，是网关定时线程与 cron 存储之间的主桥梁。

`run_job()` 是单任务执行器，整合 profile、脚本预处理、agent 调用、输出保存、错误记录、投递等步骤。这里的行为变更通常会影响所有自动化任务。

`_build_job_prompt()` 负责生成 agent 真正看到的任务输入。它把脚本输出包装为上下文，并加载任务关联 skills；同时通过 `CronPromptInjectionBlocked` 把组装后的 prompt 安全扫描纳入运行时。

`_run_job_script()` 是脚本沙盒执行器，只允许运行 `HERMES_HOME/scripts/` 下的脚本，`.sh`/`.bash` 走 bash，其他默认走当前 Python 解释器，并设置超时、工作目录、环境变量与敏感信息脱敏。

`_resolve_delivery_targets()` 和 `_deliver_result()` 是投递层核心。前者把任务里的抽象 `deliver` 配置解析为具体平台、chat_id、thread_id；后者根据网关是否在线选择 live adapter 或 standalone send，并处理媒体附件标签。

`_job_profile_context()` 用于跨 profile 执行任务。它临时覆盖 Hermes home 和环境变量，退出后恢复，保证配置、脚本、密钥、agent 构造看到一致的 profile 视图。

`_parse_wake_gate()` 是轻量控制门：脚本最后一行若是 JSON 且显式 `wakeAgent: false`，则跳过 LLM 唤醒，适合监控类任务“无异常不打扰”。

## 修改风险

最高风险在 `run_job()`、`tick()` 和 `_job_profile_context()`。这些函数处在调度、状态持久化、环境切换和 agent 生命周期交界处，错误可能导致任务重复执行、漏执行、profile 串线、环境变量泄漏或失败状态无法推进。

投递相关改动也很敏感。`_KNOWN_DELIVERY_PLATFORMS`、`_HOME_TARGET_ENV_VARS`、`_resolve_delivery_targets()`、`_deliver_result()` 与 gateway 平台注册、线程 topic、live adapter、媒体附件路径都有耦合；新增平台时要同时考虑内置平台表、插件平台的 `cron_deliver_env_var`、gateway config 是否启用，以及测试里的投递解析用例。

脚本执行路径涉及安全边界。不要放宽 `_run_job_script()` 的 `HERMES_HOME/scripts/` 限制，不要随意尊重 shebang 或允许任意绝对路径，否则 cron job 可变成任意命令执行入口。修改脚本输出注入到 prompt 的格式时，也要保留注入扫描和 secret redaction。

工具集解析是另一个安全点。cron agent 是非交互运行，`cronjob`、`messaging`、`clarify` 的默认禁用属于策略约束；如果改动 `_resolve_cron_disabled_toolsets()` 或 per-job `enabled_toolsets` 优先级，可能让任务绕过用户全局禁用配置，或进入等待用户交互的死锁状态。

最后，文件锁和并发策略不能只按单进程思路改。网关后台 ticker、手动 `hermes cron tick`、测试 monkeypatch、profile 任务串行化都依赖当前防重入和恢复机制；任何并行化优化都必须同时验证 `cron/jobs.py` 的文件锁、状态推进和输出写入不会互相覆盖。
