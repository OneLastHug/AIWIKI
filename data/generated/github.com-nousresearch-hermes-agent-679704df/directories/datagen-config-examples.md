# 目录：datagen-config-examples

## 它负责什么

`datagen-config-examples` 是 Hermes Agent 仓库里的“数据生成配置样例”目录，用来展示如何批量运行 agent、生成 tool-calling trajectories，以及如何对生成后的轨迹做压缩处理。它本身不是核心运行时模块，也没有 Python 包结构；更像是一组可复制、可改写的启动模板，帮助开发者把 `batch_runner.py`、环境配置、数据集 JSONL、轨迹压缩器串起来。

从当前片段看，这个目录覆盖两类典型任务：一类是浏览器自动化数据生成，另一类是 Web research 数据生成。前者通过 shell 脚本直接调用 `batch_runner.py`，并指定浏览器任务分布、模型、并发 worker、最大轮数和临时 system prompt；后者通过 YAML 配置描述环境、工具集、批大小、输出目录和压缩参数。另一个 YAML 则面向后处理阶段，说明如何用 `trajectory_compressor.py` 把已经生成的长轨迹压到目标 token 预算内。

这个目录的价值在于说明“数据生成任务应该如何被描述和启动”，而不是实现数据生成逻辑。真正的执行逻辑在仓库根部的 `batch_runner.py` 和 `trajectory_compressor.py`，agent 对话循环则继续下沉到 `run_agent.py`、工具调度到 `model_tools.py`、工具集定义到 `toolsets.py`。

## 直接子目录地图

`datagen-config-examples` 当前没有直接子目录，只有几个顶层样例文件：

`run_browser_tasks.sh` 是浏览器任务批处理示例脚本，负责拼出一次完整的 `python batch_runner.py ...` 调用。

`example_browser_tasks.jsonl` 是最小示例数据集，每行一个 JSON 对象，核心字段是 `prompt`。这些 prompt 覆盖页面浏览、信息抽取、表单填写、结果写文件等浏览器自动化场景。

`web_research.yaml` 是 Web research 批量生成配置，声明 `environment: web-research`、可用 `toolsets`、并发数、批大小、模型、输出目录、临时 system prompt、压缩配置和 eval 节奏。

`trajectory_compression.yaml` 是轨迹压缩后处理配置，声明 tokenizer、压缩目标、保护轮次、摘要模型、输出策略、并发处理和 metrics 设置。

## 关键入口

最直接的入口是 `datagen-config-examples/run_browser_tasks.sh`。它创建 `logs` 目录，生成带时间戳的日志文件，定位脚本所在目录，然后调用 `batch_runner.py`，传入 `--dataset_file`、`--batch_size`、`--run_name`、`--distribution`、`--model`、`--base_url`、`--num_workers`、`--max_turns` 和一段面向浏览器自动化的 `--ephemeral_system_prompt`。这个入口适合理解“从 JSONL prompt 到批量轨迹输出”的最短路径。

第二个入口是 `datagen-config-examples/web_research.yaml`。它不是可执行文件，而是给 `batch_runner.py --config` 使用的配置样例。注释里给出的主调用形态是 `python batch_runner.py --config datagen-config-examples/web_research.yaml --run_name web_research_v1`。它适合理解配置驱动的数据生成方式。

第三个入口是 `datagen-config-examples/trajectory_compression.yaml`。根据当前片段和仓库搜索结果推断，它对应根目录 `trajectory_compressor.py` 的 `--config` 参数，用于压缩已有 trajectories。依据是 `trajectory_compressor.py` 中存在 `CompressionConfig`、`TrajectoryCompressor`、`compress_trajectory`、`compress_trajectory_async`、`target_max_tokens`、`compression_metrics.json` 等配置读取和处理逻辑。

## 主流程位置

数据生成主流程不在这个目录内，而是在 `batch_runner.py`。`run_browser_tasks.sh` 明确调用它，说明该文件负责读取 dataset、按 batch 和 worker 并行调度任务、为每个 prompt 启动 agent 运行，并把结果写入类似 `data/<run_name>/trajectories.jsonl` 的输出位置。具体 agent 执行会进一步进入 `run_agent.py` 的 `AIAgent` 对话循环，工具调用通过 `model_tools.py` 分发，具体工具可用性由 `toolsets.py` 和工具注册系统决定。

浏览器任务的主流程入口在脚本参数组合里体现：`--distribution="browser_tasks"` 决定任务偏向，临时 system prompt 强调先用 `web_search` 找目标，再用 browser tools 导航、点击、填写表单、读取页面状态。根据当前片段推断，`distribution` 会影响 `batch_runner.py` 给 agent 暴露的工具或任务环境；依据是脚本注释中写有 browser、web、vision、terminal 的比例分布，但目录内没有展开实现。

Web research 的主流程由 `web_research.yaml` 描述：`environment: web-research` 指定环境类型，`toolsets: web, file` 限定 agent 可用工具范围，`ephemeral_system_prompt` 要求先搜索、引用来源、简洁回答，`output_dir` 指定轨迹输出目录，`eval_every` 和 `eval_size` 暗示生成过程中可以周期性评估。

轨迹压缩主流程在 `trajectory_compressor.py`。`trajectory_compression.yaml` 说明压缩器会先用 tokenizer 统计 token，然后保护首个 system、人类请求、首个模型响应、首个工具响应和最后若干轮，只对中间内容做摘要压缩；输出阶段可追加 summary notice，并保存压缩 metrics。

## 推荐阅读顺序

建议先读 `datagen-config-examples/example_browser_tasks.jsonl`，快速理解数据集输入格式：一行一个任务，核心就是 `{"prompt": "..."}`。

然后读 `datagen-config-examples/run_browser_tasks.sh`，把输入 JSONL、运行名、模型、并发、最大轮数、临时 system prompt 和输出路径串起来。这里能看到浏览器数据生成的一次完整命令长什么样。

接着读 `datagen-config-examples/web_research.yaml`，对比脚本式参数和 YAML 配置式参数的差异。重点看 `environment`、`toolsets`、`num_workers`、`batch_size`、`model`、`ephemeral_system_prompt`、`output_dir`、`compression`。

再读根目录 `batch_runner.py`，关注它如何解析 `--dataset_file` 或 `--config`、如何创建 worker、如何实例化 agent、如何保存 trajectories。这里只需要顺着配置字段找对应解析逻辑，不必一开始通读所有分支。

最后读 `datagen-config-examples/trajectory_compression.yaml` 和 `trajectory_compressor.py`，理解生成后的轨迹如何被裁剪、摘要和重新输出。若只关心数据生成，可把压缩部分放到最后。

## 常见误区

不要把 `datagen-config-examples` 当成数据生成框架本体。它只是样例目录，核心执行在 `batch_runner.py`、`run_agent.py`、`model_tools.py` 和相关 tools 中。

不要以为 `web_research.yaml` 会自动运行。它只是配置文件，需要通过 `python batch_runner.py --config ...` 传入。

不要把 `ephemeral_system_prompt` 当成会写入训练轨迹的永久 system prompt。文件注释明确说它是 ephemeral，用于生成时引导 agent，不保存到 trajectories。

不要忽略 API key 和外部服务依赖。浏览器任务脚本注释要求在 Hermes 的 `.env` 中配置模型服务 key 和浏览器服务 key；配置里的 `base_url` 指向外部模型服务 `[URL已移除]`。缺少这些依赖时，样例命令无法完整跑通。

不要把 `trajectory_compression.yaml` 用在生成前。它是后处理配置，目标是处理已经完成的 agent trajectories，压缩到训练 token 预算内。

不要逐条解读 `example_browser_tasks.jsonl` 里的每个任务。它的作用是展示输入格式和任务类型覆盖面，不是完整 benchmark。
