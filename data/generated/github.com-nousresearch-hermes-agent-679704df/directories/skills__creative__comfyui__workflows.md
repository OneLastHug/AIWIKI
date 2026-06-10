# 目录：skills/creative/comfyui/workflows

## 它负责什么

`skills/creative/comfyui/workflows` 是 ComfyUI skill 随包提供的“示例工作流模板库”。它不承担 Python 执行逻辑，也不是 ComfyUI 安装或节点管理入口；它的角色是保存一组已经整理成 **ComfyUI API format** 的 `.json` 工作流，供 `scripts/run_workflow.py`、`scripts/extract_schema.py`、`scripts/check_deps.py` 等脚本直接读取、注入参数、提交到 ComfyUI 服务并下载结果。

这里的重点是“可运行的起点”：用户不必从零搭建一个 ComfyUI graph，而是可以从 SD 1.5、SDXL、Flux、img2img、inpaint、upscale、AnimateDiff、Wan video 等常见任务模板开始。根据 `workflows/README.md`，这些 JSON 的顶层 key 是节点 ID，每个节点包含 `class_type`，属于 API 格式；这和 ComfyUI 编辑器内部保存的 editor format 不同，后者通常包含顶层 `nodes`、`links` 数组，不能被执行脚本直接提交。

## 直接子目录地图

这个目录当前没有直接子目录，只有一层文件：

- `README.md`：工作流目录的导航说明，列出每个模板的用途、模型依赖、最低显存、快速运行命令和注意事项。
- `sd15_txt2img.json`：SD 1.5 文生图模板，偏轻量，典型 512×512 入口。
- `sdxl_txt2img.json`：SDXL 文生图模板，面向 1024×1024 生成。
- `flux_dev_txt2img.json`：Flux Dev 文生图模板，依赖 UNET、DualCLIP、VAE 等较重组件。
- `sdxl_img2img.json`：SDXL 图生图模板，包含 `LoadImage`、`VAEEncode`、`KSampler` 等图像输入链路。
- `sdxl_inpaint.json`：SDXL 局部重绘模板，额外包含 mask 相关节点，例如 `LoadImageMask`、`VAEEncodeForInpaint`。
- `upscale_4x.json`：独立 4 倍超分模板，核心是 `UpscaleModelLoader` 与 `ImageUpscaleWithModel`。
- `animatediff_video.json`：AnimateDiff 文生视频模板，包含 motion module 与视频合成节点。
- `wan_video_t2v.json`：Wan text-to-video 模板，面向较重的视频生成流程。

从目录组织看，它是“扁平模板集合”，不是按模型家族或任务类型拆分的多层工作流仓库。

## 关键入口

本目录内部的关键入口是 `skills/creative/comfyui/workflows/README.md`。它回答三个问题：有哪些模板、每个模板需要什么模型、如何用脚本运行。对于只想了解这个目录的人，应先读这个文件，而不是直接打开各个 JSON。

真正的运行入口在邻近目录 `skills/creative/comfyui/scripts/run_workflow.py`。它通过 `--workflow` 指定本目录中的某个 JSON，读取 workflow 后生成 schema、注入 `--args` 参数、提交到本地或云端 ComfyUI API、轮询或 WebSocket 监听执行状态，最后下载输出文件。

辅助入口包括：

- `skills/creative/comfyui/scripts/extract_schema.py`：从 workflow 中提取可控参数，例如 `prompt`、`seed`、`steps`、模型名等。`workflows/README.md` 建议用它查看“这个工作流能改什么”。
- `skills/creative/comfyui/scripts/check_deps.py`：检查某个 workflow 对当前 ComfyUI 服务的节点、模型依赖是否满足。
- `skills/creative/comfyui/scripts/run_batch.py`：基于同一个 workflow 做多次生成、随机种子或参数 sweep。
- `skills/creative/comfyui/SKILL.md`：更高层的技能说明，解释 ComfyUI skill 的两层架构：`comfy-cli` 负责安装、启动、模型和节点管理；REST/WebSocket API 与 skill 脚本负责 workflow 执行。

## 主流程位置

主流程不在 `workflows` 目录内部，而在 `scripts/run_workflow.py` 中。根据当前片段推断，围绕本目录 JSON 的执行路径大致是：

1. 用户选择一个 workflow，例如 `workflows/sdxl_txt2img.json`。
2. `run_workflow.py --workflow ... --args '{...}'` 读取 JSON，并通过 `unwrap_workflow()` 确认它是可执行的 API format。
3. 脚本解析 `--args`，必要时通过 `--input-image` 上传本地图像，并把上传后的图片名作为参数注入 workflow。
4. `load_schema()` 调用 `extract_schema` 生成参数映射，`inject_params()` 将用户参数写入对应节点的 `inputs` 字段；如果目标字段是节点连接，脚本会拒绝直接覆盖，避免破坏 graph 连接。
5. `ComfyRunner.submit()` 将 workflow 作为 `prompt` POST 到 ComfyUI 的 `/prompt` 接口。
6. 脚本通过 HTTP polling 或 `--ws` WebSocket 等待结果；视频 workflow 会自动把默认超时从 300 秒提高到 900 秒。
7. 完成后调用 `/history`、`/view` 等接口收集输出，并保存到 `--output-dir`。

所以，本目录保存的是“流程图数据”；运行、校验、上传、监控、下载都由 sibling scripts 完成。

## 推荐阅读顺序

1. 先读 `skills/creative/comfyui/SKILL.md` 的 “What's in this skill”、“Architecture: Two Layers”、“Core Workflow”，建立整体边界：生命周期用 `comfy-cli`，执行用 REST/WebSocket 脚本。
2. 再读 `skills/creative/comfyui/workflows/README.md`，了解本目录模板清单、模型依赖、最低显存和快速命令。
3. 接着读 `skills/creative/comfyui/scripts/run_workflow.py` 的 CLI 参数与主函数，理解 workflow JSON 如何被加载、注入、提交和下载。
4. 然后读 `skills/creative/comfyui/scripts/extract_schema.py`，理解为什么 JSON 里的节点字段能被映射成 `prompt`、`seed`、`ckpt_name` 等用户参数。
5. 最后按任务类型选择性查看某个 JSON，例如先看 `sdxl_txt2img.json` 这种简单文生图，再看 `sdxl_inpaint.json` 或 `wan_video_t2v.json` 这种输入和依赖更多的模板。

## 常见误区

一个常见误区是把这里的 JSON 当成 ComfyUI 编辑器保存文件。当前目录强调的是 API format，它的结构适合脚本提交执行；如果拿到的是 editor format，需要在 ComfyUI UI 中重新导出为 API 格式，不能直接交给 `run_workflow.py`。

第二个误区是认为模板自带模型。这里的 JSON 只引用模型名，不包含模型权重。`README.md` 明确列出每个模板所需 checkpoint、VAE、CLIP、upscaler 或 motion module；本地运行前需要安装，云端运行时也可能要覆盖成云端实际可用的模型名。

第三个误区是把 `workflows` 当成执行层。它没有脚本入口，也不负责联网、排队或下载输出。所有执行行为都在 `scripts/run_workflow.py`、批处理在 `scripts/run_batch.py`、依赖检查在 `scripts/check_deps.py`。

第四个误区是随意改 JSON 中的连接字段。`run_workflow.py` 的注入逻辑会避免把已有 link 覆盖成字面量，因为这会破坏 ComfyUI graph。正确方式是通过 schema 暴露源节点输入，或者在 ComfyUI 中编辑后重新导出。

第五个误区是忽略视频模板的运行成本。`animatediff_video.json`、`wan_video_t2v.json` 属于耗时和显存要求更高的路径，默认超时、模型依赖、云端并发限制都可能和普通文生图不同；阅读时应把它们视为高级示例，而不是基础 smoke test。
