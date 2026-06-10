# 目录：tests/stress

## 它负责什么

`tests/stress` 是 Hermes Agent 中针对 Kanban kernel 的压力测试与“战斗测试”目录，核心目标不是验证普通单元行为，而是把 `hermes_cli.kanban_db` 放到高并发、真实子进程、异常输入、随机操作序列和大规模数据量下反复冲击，观察数据库状态机是否还能维持关键不变量。

从目录内 `README.md` 和脚本注释看，这组测试默认不属于常规测试入口。原因很明确：它们可能运行 30 秒以上，会创建临时 `HERMES_HOME`，启动多个进程或线程，有些还会通过真实 CLI 路径写 heartbeat、complete、worker log。它们更像回归前的专项验证工具，适合在修改 Kanban 调度、任务状态、claim/reclaim、runs 表、parent dependency 或 CLI worker 生命周期时手动运行。

该目录主要围绕几个风险点展开：SQLite 并发写入与 WAL/CAS 保护、任务是否会被重复 claim 或重复 complete、`task_runs` 是否出现孤儿 open run、claim TTL 到期与 late complete 的竞态、父任务未完成时子任务是否会被错误领取、真实子进程是否能通过 DB 协议与 dispatcher 协作，以及大规模任务下核心查询是否出现明显性能退化。

## 直接子目录地图

`tests/stress` 当前没有直接子目录，是一个扁平的脚本集合。目录内文件大致可以按用途分成几类：

`README.md` 说明压力测试的定位、手动运行方式和各脚本覆盖范围。

`conftest.py` 是 pytest 层的保护配置。它添加 `--run-stress` 选项，并在未显式开启时为该目录测试打 skip 标记；同时通过 `collect_ignore_glob = ["*.py"]` 表明这些文件主要按脚本直接运行，而不是让 pytest 自动逐个收集函数。

`_fake_worker.py` 是 `test_subprocess_e2e.py` 使用的模拟 worker 子进程。它不是独立测试入口，而是用于验证真实 subprocess、CLI heartbeat、CLI complete 和日志路径的辅助执行体。

`test_concurrency.py`、`test_concurrency_mixed.py`、`test_concurrency_reclaim_race.py`、`test_concurrency_parent_gate.py` 组成并发与竞态测试组，重点覆盖 claim、complete、block、unblock、archive、release stale claims、crash detection、parent gate 等并发状态转换。

`test_subprocess_e2e.py` 覆盖 dispatcher 启动真实 Python 子进程后的端到端生命周期。

`test_property_fuzzing.py` 使用 Python `random` 生成大量操作序列，持续检查 Kanban DB 不变量。注释中特别说明没有使用 Hypothesis 库。

`test_atypical_scenarios.py` 覆盖异常用户输入和边界场景，例如 unicode、超长字符串、SQL 注入尝试、循环依赖、自父节点、宽 fan-in/fan-out、时钟偏移、特殊 `HERMES_HOME`、大量 runs、跨进程 idempotency-key race、dashboard REST 异常 JSON 等。

`test_benchmarks.py` 是规模基准脚本，记录 `dispatch_once`、`recompute_ready`、`list_tasks`、`build_worker_context`、runs 查询等在 100、1000、10000 任务规模下的延迟。

## 关键入口

最重要的入口是 `tests/stress/README.md`。它直接给出推荐命令，例如对整个目录执行 `pytest tests/stress/ -v -s`，或者单独运行 `python tests/stress/test_concurrency.py`、`python tests/stress/test_subprocess_e2e.py` 等脚本。结合 `conftest.py` 可知，这些测试不是普通 `scripts/run_tests.sh` 的默认组成部分，需要显式 opt-in。

pytest 入口是 `tests/stress/conftest.py` 中的 `pytest_addoption` 和 `pytest_collection_modifyitems`。前者增加 `--run-stress`，后者在未设置该参数时跳过路径中包含 `tests/stress` 的测试项。这里还有一个容易忽略的点：`collect_ignore_glob = ["*.py"]` 表示这些压力脚本的主使用方式是直接作为 `__main__` 运行，而不是 pytest 自动收集模块内测试函数。

业务入口集中在每个脚本的 `main()` 或 `run()`：`test_concurrency.py` 的 `main()` 负责创建临时 home、初始化 DB、播种任务、启动多个 worker 进程并汇总事件；`test_concurrency_mixed.py` 的 `main()` 组织 10 worker 加 reclaimer 的混合操作；`test_concurrency_reclaim_race.py` 的 `main()` 专门制造 TTL 小于工作时长的 reclaim race；`test_subprocess_e2e.py` 的 `main()` 建立 CLI shim 并调用 `dispatch_once`；`test_property_fuzzing.py` 的 `main()` 驱动随机序列与不变量检查；`test_benchmarks.py` 的 `main()` 运行各类规模 benchmark；`test_concurrency_parent_gate.py` 使用 `run()` 作为主流程函数。

## 主流程位置

并发 claim 的主流程在 `tests/stress/test_concurrency.py`。它通过 `multiprocessing` 启动 5 个 worker，对 100 个 ready task 竞争领取。每个 worker 反复执行查询 ready task、调用 `kb.claim_task`、读取 `kb.latest_run`、模拟工作、调用 `kb.complete_task`，最后由主进程聚合 JSON 事件并检查是否存在 double-claim、double-complete、orphan run、SQLite locking 错误等问题。

混合状态转换主流程在 `tests/stress/test_concurrency_mixed.py`。它把操作扩展为 claim/complete、claim/block、unblock、archive，并加入后台 reclaimer，持续调用 `release_stale_claims` 和 `detect_crashed_workers` 一类逻辑。这个脚本更接近日常调度器与 worker 同时改动任务状态时的复杂交错。

reclaim 竞态主流程在 `tests/stress/test_concurrency_reclaim_race.py`。worker 使用很短的 TTL claim task，然后睡眠超过 TTL，让 reclaimer 有机会把任务回收到 ready。之后 worker 再尝试 `complete_task`。这个脚本关注的是 late complete 是否被 CAS 状态条件干净拒绝，以及 run 关闭是否保持一致。

父依赖 gate 主流程在 `tests/stress/test_concurrency_parent_gate.py`。它模拟“先创建 ready child，稍后再补 parent link”的历史竞态，同时 worker 线程不断尝试 claim ready task。预期是 `claim_task` 必须在领取前重新检查 parent completion，发现父任务未 done 时拒绝 claim 并把任务降回不可领取状态。

真实子进程主流程在 `tests/stress/test_subprocess_e2e.py`，辅助脚本是 `tests/stress/_fake_worker.py`。前者创建临时 `HERMES_HOME` 和 `hermes` CLI shim，调用 `kb.dispatch_once(conn, spawn_fn=...)` 让 dispatcher 启动真实 Python 进程；后者在子进程内通过 CLI 写 heartbeat、complete、summary、metadata。该流程验证的不是 mock 行为，而是 PID、环境变量、CLI、DB、日志文件共同组成的真实 worker contract。

随机不变量主流程在 `tests/stress/test_property_fuzzing.py`。`random_op` 生成 create、create_child、claim、complete、block、unblock、archive、heartbeat、release_stale、detect_crashed、recompute_ready、reassign 等操作，`assert_invariants` 在每一步后检查 `tasks`、`task_runs`、`task_events` 之间的关系。它适合发现人工场景没有覆盖到的状态组合。

性能主流程在 `tests/stress/test_benchmarks.py`。`bench` 负责计时，`seed_tasks` 负责播种不同规模和依赖形态的任务，`main()` 分段测量调度、ready 计算、worker context 构建、列表和 runs 查询。根据当前片段推断，结果会打印成表格并写 JSON，用于后续对比性能回退。

## 推荐阅读顺序

建议先读 `tests/stress/README.md`，建立对整个目录的运行成本、覆盖范围和非默认执行方式的认识。

第二步读 `tests/stress/conftest.py`，明确为什么这些脚本不会自然出现在普通 pytest 收集流里，以及 `--run-stress` 和直接执行脚本的区别。

第三步读 `tests/stress/test_concurrency.py`，这是最基础、也最能说明目录设计意图的脚本：多进程、共享 SQLite、claim/complete、事件汇总、不变量断言都在这里集中出现。

第四步读 `tests/stress/test_concurrency_mixed.py` 和 `tests/stress/test_concurrency_reclaim_race.py`，前者扩大操作面，后者聚焦 TTL reclaim 与 late complete 的窄竞态。

第五步读 `tests/stress/test_subprocess_e2e.py` 和 `tests/stress/_fake_worker.py`，理解 dispatcher 与真实 worker 子进程之间靠环境变量、CLI 和 DB 协议协作的路径。

第六步读 `tests/stress/test_property_fuzzing.py`，把前面看到的状态转换抽象成不变量集合。最后再看 `tests/stress/test_atypical_scenarios.py` 和 `tests/stress/test_benchmarks.py`，分别补齐边界输入和规模性能视角。

## 常见误区

不要把 `tests/stress` 当成普通单元测试目录。这里的脚本慢、会起进程、会创建临时 home，并且默认不由 `scripts/run_tests.sh` 执行。修改 Kanban kernel 后如果只跑常规测试，不能说明这些压力场景已经覆盖。

不要忽略 `conftest.py` 的双重保护。一方面它提供 `--run-stress`，另一方面 `collect_ignore_glob = ["*.py"]` 说明很多脚本带有顶层执行假设，直接 `pytest` 收集并不是主要路径。阅读时应优先找 `main()` 或 `run()`，而不是寻找传统 `test_*` 函数。

不要把 `_fake_worker.py` 理解成 mock 单元测试。它的价值正是作为真实 subprocess 运行，通过 CLI 与 DB 交互，用来验证子进程生命周期、heartbeat、complete、metadata 和日志是否符合 dispatcher 预期。

不要只看任务最终状态。这个目录反复检查的是跨表不变量，例如 `tasks.current_run_id` 是否指向仍 open 的 run，open run 是否有 task 指向，claim lock 是否只存在于 running 状态，事件顺序和 run 引用是否一致。Kanban 并发 bug 往往不会只表现为 status 错误。

不要把 benchmark 当成硬性 pass/fail 测试。`test_benchmarks.py` 更像性能观测工具，用于发现数量级回退；它的输出需要结合历史结果和变更背景判断。
