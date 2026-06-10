# 文件：skills/creative/comfyui/workflows/README.md

## 一句话定位

`skills/creative/comfyui/workflows/README.md` 是 ComfyUI 技能内置示例工作流目录的说明页：它告诉使用者这些 `*.json` 是可直接提交给 ComfyUI API 的 starter workflows，并给出模型依赖、最低显存、运行命令和常见注意事项。

## 它暴露/定义了什么

这个文件本身不暴露 Python API、类或函数，而是定义了一组“可用工作流资产”的索引和使用约定。核心内容包括：

- 示例工作流清单：`sd15_txt2img.json`、`sdxl_txt2img.json`、`flux_dev_txt2img.json`、`sdxl_img2img.json`、`sdxl_inpaint.json`、`upscale_4x.json`、`animatediff_video.json`、`wan_video_t2v.json`。
- 每个工作流的用途、必需模型和最低 VRAM 预期。
- 使用 `scripts/run_workflow.py` 执行工作流的命令模板，包括 txt2img、img2img、本地运行和云端运行。
- 使用 `scripts/extract_schema.py` 查看可调参数、使用 `scripts/check_deps.py` 检查节点和模型依赖的入口。
- API 格式约束：这些 JSON 顶层是 ComfyUI 节点 ID，节点内含 `class_type`，不是编辑器格式的 `nodes` / `links`。
- 若云端模型名和本地模型名不同，可以通过 `--args` 覆盖 `ckpt_name`、`vae_name`、`unet_name` 等参数。

它的“输出”不是运行时对象，而是给 AI 助手和人类使用者提供一套可靠的工作流选择表和执行范式。

## 谁调用它

严格意义上没有代码直接调用这个 Markdown 文件。它主要被 `skills/creative/comfyui/SKILL.md` 引用：技能入口在 “Example workflows (`workflows/`)” 中说明该目录包含 SD 1.5、SDXL、Flux Dev、img2img、inpaint、upscale、AnimateDiff、Wan T2V 等示例，并提示 “See `workflows/README.md`”。

根据当前片段推断，调用关系更接近“文档驱动的人工/Agent 选择流程”：当用户要求生成图像、视频、修复图片、放大图片或运行 ComfyUI 工作流时，ComfyUI skill 会指导 Agent 先选择或准备 API-format workflow，再用脚本执行。这个 README 就是 Agent 在选择内置示例工作流时的目录说明。

测试代码不会读取 README，但会使用同目录下的 workflow JSON。`skills/creative/comfyui/tests/conftest.py` 把 `workflows/` 作为 fixture 来源，`test_common.py`、`test_run_workflow.py` 等测试会加载其中的 `sd15_txt2img.json`、`flux_dev_txt2img.json`、`animatediff_video.json`、`wan_video_t2v.json` 等文件验证解析、参数注入和视频工作流识别逻辑。

## 它调用谁

作为 Markdown 文件，它不主动调用任何模块。但它显式指向三类脚本入口：

- `skills/creative/comfyui/scripts/run_workflow.py`：负责加载 workflow、注入参数、上传输入图、提交到 ComfyUI、本地或云端监控执行、下载输出。
- `skills/creative/comfyui/scripts/extract_schema.py`：负责分析 API-format workflow，提取可控参数、输出节点、模型依赖和 embedding 依赖。
- `skills/creative/comfyui/scripts/check_deps.py`：负责检查 workflow 在当前 ComfyUI 服务上是否缺少模型、节点或 embedding。

这些脚本共同构成 README 命令示例背后的实际执行链路。README 还间接依赖 `scripts/_common.py` 的共享能力，因为上述脚本会使用其中的 `unwrap_workflow`、`looks_like_video_workflow`、`resolve_api_key`、`resolve_url`、HTTP helper、模型依赖遍历等基础函数。

## 核心流程

第一步是选择 workflow。用户根据任务类型在表格中选择对应 JSON：普通文生图用 `sd15_txt2img.json` 或 `sdxl_txt2img.json`，高质量 Flux 文生图用 `flux_dev_txt2img.json`，图生图用 `sdxl_img2img.json`，局部重绘用 `sdxl_inpaint.json`，放大用 `upscale_4x.json`，视频生成用 `animatediff_video.json` 或 `wan_video_t2v.json`。

第二步是确认依赖。README 给出每个 workflow 的模型要求和显存预估，用户可以进一步运行 `check_deps.py` 检查当前本地或云端环境是否真的具备所需 checkpoint、VAE、文本编码器、motion module、upscaler 或自定义节点。

第三步是查看可调参数。`extract_schema.py` 会从 workflow 的节点输入中提取 `prompt`、`negative_prompt`、`seed`、`steps`、`ckpt_name` 等友好参数。README 后半部分强调，模型名参数也会被 schema 暴露，因此本地和云端模型命名不一致时可以通过 `--args` 覆盖。

第四步是执行。`run_workflow.py` 读取 JSON，使用 `unwrap_workflow` 确认它是 API 格式；解析 `--args`；必要时通过 `--input-image` 上传输入图并把返回文件名注入参数；调用 `extract_schema` 得到参数映射；用 `inject_params` 把用户参数写入 workflow 副本；通过 `ComfyRunner.submit` 提交到 ComfyUI；最后等待完成并下载输出。

第五步是处理特殊工作流。img2img 的 `denoise` 控制源图保留程度；inpaint mask 约定白色为重绘区域、黑色为保留区域；视频类 workflow 运行时间长，脚本会根据视频输出节点把默认超时从 300 秒提高到 900 秒。

## 关键函数的高层作用

这个 README 没有函数。它引用的关键执行函数集中在脚本层：

`run_workflow.py` 中的 `ComfyRunner` 是运行器封装，负责根据本地或云端 host 组织 URL、设置 API key header、检查服务、上传图片、提交 workflow、轮询或监听执行状态、下载输出。

`run_workflow.py` 中的 `load_schema` 在没有传入 schema 文件时调用 `extract_schema.py` 的 `extract_schema`，实现“无需手写参数映射”的默认体验。

`run_workflow.py` 中的 `inject_params` 是 README 中 `--args` 能工作的核心。它基于 schema 找到参数对应的 `node_id` 和 `field`，复制 workflow 后写入新值；如果目标字段当前是节点链接，则拒绝覆盖，避免把图结构连线破坏成普通字面值。

`run_workflow.py` 中的 `download_outputs` 遍历 ComfyUI history 输出，兼容 `images`、`gifs`、`videos`、`video`、`audio` 等不同输出键，并通过安全路径拼接避免服务端返回的文件名逃逸 `--output-dir`。

`extract_schema.py` 中的 `extract_schema` 负责把 ComfyUI 节点图转成用户友好的参数表。它会识别正向/反向 prompt 节点、输出节点、模型依赖、embedding 引用，并生成 summary，例如是否包含 seed、是否是视频工作流。

`check_deps.py` 的主流程会加载 workflow、调用 `unwrap_workflow` 校验格式，再用 `check_deps` 对照运行中的 ComfyUI 服务检查依赖是否 ready。

## 修改风险

最高风险是破坏 README 与实际 workflow JSON 的一致性。表格里的文件名、模型名、VRAM 需求、任务描述如果和 `workflows/*.json` 不一致，用户会选择错误 workflow，`check_deps.py` 也可能给出看似矛盾的报告。

第二类风险是命令路径。README 位于 `workflows/` 目录内，所以示例使用 `python3 ../scripts/run_workflow.py`。如果把示例复制到 `SKILL.md` 或仓库根目录语境，路径需要改成 `python3 scripts/run_workflow.py` 或相应相对路径；随意统一路径会让其中一个使用场景失效。

第三类风险是外部服务和模型命名变化。云端 checkpoint 可能带 `-fp16` 后缀，本地模型通常使用原始文件名。README 当前通过“Cloud vs local model names” 说明覆盖方式，这是必要的缓冲层；如果删掉这段，云端运行 Flux、SD1.5、SDXL 示例时更容易因为模型名不匹配失败。

第四类风险是 API-format 约束被弱化。整个脚本链路依赖 API 格式 workflow；编辑器格式需要从 ComfyUI UI 重新导出。如果文档没有明确区分，用户会把社区下载的 editor workflow 直接传给 `run_workflow.py`，触发格式错误。

第五类风险是资源预期过于乐观。Flux Dev 和 Wan T2V 对显存要求高，视频 workflow 耗时长。降低 README 中的 VRAM 或 timeout 提示会导致用户误以为本地轻量机器可稳定运行，实际会遇到 OOM、长时间等待或云端限制。

第六类风险是安全提示缺失。虽然目标 README 没有展开安全模型，但 `SKILL.md` 已说明未知 workflow 的 custom nodes 具备执行 Python 的信任风险。若未来在 README 增加更多第三方 workflow 推荐，应同步提醒先检查来源和节点依赖，避免把“示例目录”扩展成不受信任 workflow 的直接运行入口。
