# 文件：batch_runner.py

## 一句话定位

`batch_runner.py` 是 Hermes 的离线批量轨迹生成入口：它读取 JSONL prompt 数据集，把任务切成 batch，用多进程并行驱动 `AIAgent` 执行，并产出可恢复、可统计、可合并的训练轨迹文件。

## 它暴露/定义了什么

这个文件主要定义了三类能力。第一是命令行入口 `main()`，通过 `fire.Fire(main)` 暴露为 `python batch_runner.py ...` 的批处理命令。第二是核心编排类 `BatchRunner`，负责数据集加载、切批、checkpoint、resume、统计汇总和最终文件合并。第三是一组 worker/统计函数，包括 `_process_single_prompt()`、`_process_batch_worker()`、`_extract_tool_stats()`、`_extract_reasoning_stats()`、`_normalize_tool_stats()` 和 `_normalize_tool_error_counts()`。

它的输出目录固定在 `data/<run_name>/` 下，主要文件包括 `batch_*.jsonl`、`trajectories.jsonl`、`checkpoint.json`、`statistics.json`。单条轨迹会保存 `conversations`、`metadata`、`completed`、`partial`、`api_calls`、`toolsets_used`、`tool_stats`、`tool_error_counts` 等字段。

## 谁调用它

最直接的调用方是命令行用户，通过 `python batch_runner.py --dataset_file=... --batch_size=... --run_name=...` 启动。仓库内根据当前片段推断，没有常规业务模块直接实例化 `BatchRunner` 作为库调用；`rg` 命中主要是说明文案、兼容注释和测试。

测试层面，`tests/test_batch_runner_checkpoint.py` 直接导入 `BatchRunner` 和 `_process_batch_worker()`，重点覆盖 checkpoint 原子写入、resume 进度保留、无 reasoning 样本的完成标记，以及最终 checkpoint 去重逻辑。这说明该文件的恢复语义是受回归测试保护的核心行为。

## 它调用谁

核心调用链围绕 `AIAgent` 展开。`_process_single_prompt()` 会按 prompt 抽样 toolset，然后创建 `run_agent.AIAgent`，调用 `agent.run_conversation(prompt, task_id=...)`，最后借用 `agent._convert_to_trajectory_format()` 转成训练轨迹格式。

工具集选择来自 `toolset_distributions`：`validate_distribution()` 用于初始化校验，`sample_toolsets_from_distribution()` 用于每个 prompt 的随机 toolset 分配，`list_distributions()`/`print_distribution_info()` 用于 CLI 展示。工具统计的全集来自 `model_tools.TOOL_TO_TOOLSET_MAP`，文件启动时派生出 `ALL_POSSIBLE_TOOLS`，用于统一 JSONL schema 和过滤损坏样本。

环境隔离方面，如果数据行带 `image` 或 `docker_image`，它会调用 `tools.terminal_tool.register_task_env_overrides()` 为该 `task_id` 注册容器镜像、`cwd` 等覆盖项。checkpoint 写入调用 `utils.atomic_json_write()`。并行执行依赖 `multiprocessing.Pool`，进度显示依赖 `rich.progress`。

## 核心流程

初始化阶段，`BatchRunner.__init__()` 校验 distribution，创建 `data/<run_name>/`，加载 JSONL 数据集，只保留包含 `prompt` 的合法行，可选按 `max_samples` 截断，然后按 `batch_size` 切成带原始索引的 batch。

运行阶段，`run(resume=False)` 先处理恢复逻辑。开启 `resume` 时，它不仅读 `checkpoint.json`，还会扫描已有 `batch_*.jsonl`，从轨迹里的第一条 human 消息反推已完成 prompt 文本。这种按内容恢复比单纯按索引更稳，能应对数据集顺序变化。随后它构造 worker 配置，把不可 pickle 的 callable API key 丢弃，让子进程自行恢复凭据。

并行阶段，父进程用 `Pool.imap_unordered()` 分发 batch。每个 `_process_batch_worker()` 在自己的进程里顺序处理该 batch 内的 prompt。单个 prompt 运行 agent、抽取工具调用统计、抽取 reasoning 覆盖率、转换轨迹。成功且有轨迹的结果会追加写入对应 `batch_<n>.jsonl`；完全没有 reasoning 的样本会被丢弃，但仍记入 completed，避免 resume 时反复重跑。

收尾阶段，父进程随着每个 batch 完成增量更新 checkpoint；全部结束后汇总工具成功率、reasoning 统计，并重新扫描所有 `batch_*.jsonl` 合并为 `trajectories.jsonl`。合并时会用 `ALL_POSSIBLE_TOOLS` 过滤包含幻觉工具名或非法 JSON 的损坏条目，最后写 `statistics.json` 并打印摘要。

## 关键函数的高层作用

`BatchRunner.run()` 是总控函数，承担 resume、worker 配置、多进程调度、增量 checkpoint、最终合并和统计输出，是修改时最需要完整理解的入口。

`_process_single_prompt()` 是单样本执行单元，负责容器镜像预检、task 环境覆盖、toolset 抽样、`AIAgent` 初始化、对话执行和轨迹转换。它直接决定每条训练样本的行为边界。

`_process_batch_worker()` 是进程池实际调用的函数。它过滤已完成索引，串行执行 batch 内样本，写 `batch_*.jsonl`，并返回该 batch 的聚合统计。注意它只追加 batch 文件，父进程负责全局 checkpoint。

`_extract_tool_stats()` 从 OpenAI 风格 messages 中把 assistant 的 `tool_calls` 与后续 tool 消息配对，统计 count/success/failure。失败判断依赖 JSON 里的 `error`、`success: false`，以及非 JSON 内容是否显式以 `Error:` 开头。

`_extract_reasoning_stats()` 统计 assistant turn 是否含 `<REASONING_SCRATCHPAD>` 或原生 `reasoning` 字段，用于过滤没有 reasoning 的样本。

`_load_dataset()`、`_create_batches()`、`_load_checkpoint()`、`_save_checkpoint()`、`_scan_completed_prompts_by_content()`、`_filter_dataset_by_completed()` 是支撑函数，职责分别是输入清洗、切批、恢复状态读写和按内容跳过已完成样本。

## 修改风险

最高风险是 checkpoint/resume 语义。当前设计同时使用索引和 prompt 内容恢复，且测试明确防止 completed prompt 重复写入；改动 `completed_prompts_set`、`batch_stats`、`_scan_completed_prompts_by_content()` 或最终聚合时，容易导致断点续跑重复、漏跑或 checkpoint 膨胀。

第二类风险是轨迹 schema。`tool_stats` 和 `tool_error_counts` 被规范化为包含所有已知工具，是为了避免下游 HuggingFace/Arrow/Parquet 读取时 schema 不一致。删除规范化、改变字段类型或引入未过滤工具名，可能破坏训练数据加载。

第三类风险是多进程可 pickle 边界。`config` 会跨 `multiprocessing.Pool` 传入 worker，里面不能放复杂闭包或不可序列化对象；文件里已经专门处理 callable `api_key`，新增配置项时要保持这一点。

第四类风险是 `AIAgent` 参数和轨迹格式耦合。这里调用了私有方法 `agent._convert_to_trajectory_format()`，说明 batch 输出依赖 `run_agent.py` 的内部格式约定；如果 agent message 结构、tool call 结构或 reasoning 字段变化，这里的统计和过滤逻辑也要同步更新。

最后，`main()` 中参数 `list_distributions` 与导入的 `list_distributions()` 同名。根据当前片段推断，这段 CLI 分支存在名称遮蔽风险：进入 `if list_distributions:` 后再调用 `list_distributions()` 可能会把布尔参数当函数调用。修改 CLI 参数时应顺手检查这一处，避免“列出 distribution”功能失效。
