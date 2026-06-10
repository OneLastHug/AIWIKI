# 目录：cron

## 它负责什么

`cron` 目录实现 Hermes Agent 的定时任务系统。它不是传统意义上只解析 crontab 的薄封装，而是把“任务定义、调度判断、执行、输出保存、结果投递、运行状态回写”都串成一套内部机制。根据 `cron/__init__.py` 的说明，这套系统支持 cron 表达式、间隔任务、一次性任务，可以让 agent 自动执行计划任务、创建提醒或后续动作，并且任务执行由 gateway daemon 周期性驱动。

这个目录的核心边界很清楚：`cron/jobs.py` 管“任务是什么、什么时候该跑、状态如何保存”；`cron/scheduler.py` 管“到点以后怎么跑、怎么投递、怎么避免重复执行”。外部入口包括 CLI 的 `/cron` 命令、API server 的 jobs API、工具层的 `tools.cronjob_tools`，以及 gateway 后台每 60 秒调用一次的 scheduler tick。

任务数据默认存放在 Hermes home 下的 `cron/jobs.json`，运行输出保存到 Hermes home 下的 `cron/output/{job_id}/{timestamp}.md`。这里的 Hermes home 是 profile-aware 的，不应理解为固定的 `~/.hermes`；源码里通过 `get_hermes_home()` 或相关封装动态解析。

## 直接子目录地图

`cron` 当前没有直接子目录，只有三个 Python 文件：

`cron/__init__.py`：包级导出层，把任务 CRUD 和 `tick()` 暴露成 `cron.create_job`、`cron.list_jobs`、`cron.tick` 等统一接口。它也用文档字符串说明了 cron 系统的定位：gateway 每 60 秒 tick 一次，文件锁避免多进程重复执行。

`cron/jobs.py`：任务存储与管理层。它负责解析 schedule、计算 `next_run_at`、创建/更新/暂停/恢复/删除/触发任务、加载和保存 `jobs.json`、筛出 due jobs、记录运行结果、保存输出文件，以及修复/规范化历史任务字段。

`cron/scheduler.py`：执行调度层。它提供 `tick()` 作为调度主入口，内部获取到期任务、推进下次运行时间、按安全规则并发或串行执行任务、构建 agent prompt、运行脚本或 AIAgent、保存输出、投递结果、标记任务状态。

## 关键入口

包级入口是 `cron/__init__.py` 暴露的 `create_job`、`get_job`、`list_jobs`、`remove_job`、`update_job`、`pause_job`、`resume_job`、`trigger_job`、`tick` 和 `JOBS_FILE`。调用方如果只需要管理任务或触发调度，通常不需要直接碰内部函数。

任务管理入口集中在 `cron/jobs.py`。`create_job()` 是创建任务的主入口，接收 `prompt`、`schedule`、`name`、`repeat`、`deliver`、`origin`、`skills`、`model`、`provider`、`script`、`context_from`、`enabled_toolsets`、`workdir`、`profile`、`no_agent` 等字段。这里能看出 cron job 不只是“定时 prompt”，还支持绑定 skill、指定模型和 provider、运行前置脚本、串联其他任务输出、限定 toolsets、指定项目工作目录、指定 Hermes profile，甚至以 `no_agent=True` 跳过 LLM，直接把脚本输出作为任务结果。

调度入口是 `cron/scheduler.py` 的 `tick(verbose=True, adapters=None, loop=None)`。gateway 后台线程会周期性调用它；手工或测试场景也可以直接调用。`tick()` 内部使用 Hermes home 下的 `cron/.tick.lock` 做跨进程文件锁，避免 gateway、独立 daemon 或手动 tick 重叠执行同一批任务。

单任务执行入口是 `run_job(job)`，它会先应用 per-job profile 上下文，再进入 `_run_job_impl(job)`。`_run_job_impl()` 是真正执行路径：如果任务是 `no_agent`，只跑脚本；否则构造 AIAgent 任务上下文，加载配置和 `.env`，处理 delivery target，执行 agent，然后返回完整输出文档、最终响应和错误信息。

外部接入点主要有三类：`cli.py` 中 `_handle_cron_command()` 提供 `/cron list/add/edit/pause/resume/run/remove`；`gateway/platforms/api_server.py` 提供 `/api/jobs` 及单任务 GET/PATCH/DELETE、pause/resume/run 等接口；`tools.cronjob_tools` 被 CLI 和 agent 工具调用，用于把自然语言或工具请求转成 job CRUD 操作。

## 主流程位置

创建任务的主流程在 `cron/jobs.py:create_job()`。它先调用 `parse_schedule()` 解析 schedule，统一处理 one-shot、interval、cron expression 等形态；然后规范化 `repeat`、`deliver`、skills、model/provider/base_url、script、toolsets、workdir、profile、`context_from` 等字段；最后组装 job dict，设置 `created_at`、`next_run_at`、`last_run_at`、`last_status`、`deliver`、`origin` 等状态字段，追加到 `jobs.json`。

判断任务是否到期的主流程在 `cron/jobs.py:get_due_jobs()` 和内部 `_get_due_jobs_locked()`。它读取所有任务，过滤 disabled/paused 状态，检查 `next_run_at`，处理过期或缺失 `next_run_at` 的恢复逻辑，并针对 recurring job 做 catch-up grace 控制，避免 gateway 重启后把大量错过的旧任务集中爆发执行。

调度执行的主流程在 `cron/scheduler.py:tick()`。它先拿文件锁，再调用 `get_due_jobs()`，随后对 recurring job 先执行 `advance_next_run()`，这是一个重要设计：在真正执行任务前推进下一次运行时间，用来维护 at-most-once 语义。之后它根据环境变量 `HERMES_CRON_MAX_PARALLEL` 或 config.yaml 的 `cron.max_parallel_jobs` 决定并发度。带 `workdir` 或 `profile` 的任务会串行执行，因为它们会临时影响进程级运行状态；其他任务进入 `ThreadPoolExecutor` 并行执行。

单个任务的执行主流程在 `cron/scheduler.py:_run_job_impl()`。`no_agent` 路径会运行 `script`，空输出或 `wakeAgent=false` 被视作静默成功，失败则生成告警内容。默认 LLM 路径会延迟导入 `AIAgent`，初始化 session store，运行可选 pre-check script，构建 prompt，并对组装后的 prompt 做注入扫描；如果扫描命中，会返回 blocked 结果而不运行 agent。随后它设置 cron session 相关上下文变量、解析投递目标、加载配置和模型参数、创建 agent 执行任务。执行结束后由 `tick()` 的内部 `_process_job()` 保存输出、投递结果并调用 `mark_job_run()` 回写状态。

结果投递逻辑集中在 `cron/scheduler.py` 的 `_resolve_delivery_target()`、`_deliver_result()` 及其周边函数。它支持 origin、本地、各 gateway platform home target，以及插件平台声明的 cron delivery env var。`[SILENT]` 是特殊标记：输出仍会保存到本地审计文件，但不会投递到聊天平台。

## 推荐阅读顺序

建议先读 `cron/__init__.py`，建立最小心智模型：这个包导出哪些能力、谁负责调用 `tick()`。

第二步读 `cron/jobs.py` 的函数列表和 `create_job()`。这里能看懂 job 数据结构，也能看到 schedule、repeat、deliver、skills、script、workdir、profile、no_agent 等字段的语义。理解 job shape 后，再看 `list_jobs()`、`update_job()`、`pause_job()`、`resume_job()`、`trigger_job()`、`remove_job()` 会很顺。

第三步读 `cron/jobs.py:get_due_jobs()`、`advance_next_run()`、`mark_job_run()`、`save_job_output()`。这几处决定任务生命周期如何从“计划中”变成“到期、执行、记录结果、推进下一次”。

第四步读 `cron/scheduler.py:tick()`。这是运行时总控，重点看文件锁、due jobs、提前推进 `next_run_at`、串行/并行分组、保存输出、投递结果、状态回写。

第五步再读 `cron/scheduler.py:_run_job_impl()`。这部分较长，建议按两条路径看：先看 `no_agent` 脚本路径，再看默认 AIAgent 路径。默认路径中重点关注 prompt 构建、injection scanner、profile/workdir 上下文、toolset 解析、delivery context，而不是陷入每个配置细节。

最后看邻近入口：`cli.py:_handle_cron_command()` 理解用户怎么通过 `/cron` 操作任务；`gateway/platforms/api_server.py` 的 jobs API 理解 dashboard 或外部 HTTP 客户端如何管理任务；`tools.cronjob_tools` 理解 agent 工具层如何创建和修改 cron job。

## 常见误区

不要把 `cron` 理解成只负责解析 cron 表达式。它同时承担任务数据库、运行状态、输出归档、agent 执行桥接、平台投递和安全限制。

不要认为任务一定会启动 AIAgent。`no_agent=True` 的任务会跳过 LLM，直接运行脚本并投递 stdout；普通任务也可以用脚本作为 wake gate 或上下文来源。

不要假设所有到期任务都并行执行。带 `workdir` 或 `profile` 的任务会修改环境变量、Hermes home 或 cwd 相关状态，因此 scheduler 会把它们放入串行分组。

不要绕过 `create_job()` 手写 `jobs.json`。`create_job()` 会做 schedule 解析、字段规范化、workdir/profile 校验、`next_run_at` 初始化和 `no_agent` 合法性检查；手写数据可能导致 `get_due_jobs()` 走恢复路径，甚至造成任务无法按预期执行。

不要把 `origin` 当成实时 gateway session。源码中特意说明 cron 执行是内部 scheduler context，`origin` 主要用于结果投递路由，不应该让工具误以为这是一个正在交互的用户会话。

不要忽略 `[SILENT]`。它不是失败，而是“本次没有需要推送的内容”；输出仍然会被保存，方便审计。

不要以为 `/cron run <job_id>` 会立即在 CLI 进程中执行任务。它的语义是触发任务，让任务在下一次 scheduler tick 中运行。实际执行仍由 scheduler 主流程处理。
