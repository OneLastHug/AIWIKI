# 目录：skills/creative/ascii-video

## 它负责什么

`skills/creative/ascii-video` 是 Hermes Agent 内置 creative 技能中的一个“ASCII 视频制作”技能目录。它不直接提供一个可执行的固定渲染器，而是给 Agent 提供一套制作指南、架构约定和参考代码片段，指导 Agent 按用户需求生成“单文件 Python 渲染脚本”，再用该脚本把视频、音频、图片、文本或纯生成式数学图案转换为彩色 ASCII 风格视频。

这个目录覆盖的输出形态包括 MP4、GIF、PNG image sequence，也强调“输出是真正的视频帧”，不是终端 escape code。核心思想是：把 ASCII 字符当作视觉媒介，把视频制作当作完整的影像管线处理。`SKILL.md` 中反复强调创意概念、场景分段、色彩统一、亮度控制、shader 后处理和首版输出质量，因此它既是技术说明，也是创作规范。

从仓库结构看，它属于 `skills/creative` 下的技能包。Hermes 的技能系统会读取 `SKILL.md` 的 frontmatter 和正文，让模型在相关用户请求中获得专门工作流。这里的 frontmatter 声明了技能名 `ascii-video`、描述 `ASCII video: convert video/audio to colored ASCII MP4/GIF.`，以及支持平台 `linux`、`macos`、`windows`。

## 直接子目录地图

该目录很浅，直接子目录只有一个：

`skills/creative/ascii-video/references`

这个子目录是技能的知识库，放置分主题的参考文档。它不是 Python 包，也没有运行时代码入口；其中的 Markdown 文件主要提供可复用的设计模式、函数协议、渲染片段、性能建议和排错清单。根据当前片段推断，这些内容会在 Agent 执行 ASCII 视频任务时被按需阅读，而不是在 Hermes 启动时作为模块导入。

目录根部还有两个关键文档：

`skills/creative/ascii-video/SKILL.md` 是技能主入口，面向 Agent 描述何时使用、整体管线、创意标准、模式选择、实现步骤和关键注意事项。

`skills/creative/ascii-video/README.md` 更像面向人类读者的概览版说明，压缩介绍这个技能是什么、支持哪些输入输出、默认管线、网格系统、字符调色板、色彩策略、value field、particle、shader、blend mode 等能力边界。

`references` 下的主要文件按职责可以分为几组：`architecture.md` 负责网格、字体、字符 palette、颜色系统、section 和编码架构；`inputs.md` 负责音频、视频、图片、歌词、TTS 等输入分析；`effects.md` 负责 value field、噪声、粒子、SDF、坐标变换等视觉生成材料；`composition.md` 负责多层合成、blend mode、tonemap、feedback、mask、文字可读性背景；`shaders.md` 负责后处理链、shader 调度和 shader catalog；`scenes.md` 负责 scene protocol、`Renderer`、`SCENES` 表、clip 渲染和场景设计模式；`optimization.md` 负责硬件检测、质量档位、缓存、并行渲染和性能预算；`troubleshooting.md` 负责常见实现错误和平台问题。

## 关键入口

最关键入口是 `skills/creative/ascii-video/SKILL.md`。它定义了技能被使用时的总路线：先判断任务是否属于 ASCII video、text art video、terminal-style video、audio visualizer in ASCII、Matrix-style effects 等场景，再进入“创意构思 -> 技术设计 -> 编写脚本 -> 质量验证”的流程。

第二个入口是 `skills/creative/ascii-video/README.md`。它适合快速理解这个技能的能力边界，尤其是支持模式、六阶段 pipeline、grid system、character palettes、color strategies、value field generators、particle systems、shader pipeline 和 blend/composition 能力。相比 `SKILL.md`，它更像产品说明和能力索引。

第三类入口是 `references/*.md`。这些不是统一从一个 `index.md` 进入，而是由 `SKILL.md` 和 `README.md` 在不同主题中直接引用。例如实现输入分析时看 `references/inputs.md`，实现多层渲染和亮度控制时看 `references/composition.md`，组织场景时看 `references/scenes.md`，做性能优化和并行编码时看 `references/optimization.md`。

## 主流程位置

主流程在 `SKILL.md` 的 “Pipeline Architecture” 和 “Workflow” 两块中最集中。它把所有模式抽象成同一个六阶段链路：

`INPUT -> ANALYZE -> SCENE_FN -> TONEMAP -> SHADE -> ENCODE`

`INPUT` 负责加载源素材。视频模式读取视频帧，音频模式读取采样，图片模式读取静态图或序列，生成式模式可以没有外部输入，TTS 模式还会涉及语音生成和混音。

`ANALYZE` 负责提取每帧特征。音频侧包括 FFT、频段能量、RMS、spectral centroid、beat detection 等；视频侧包括 luminance、edges、motion 等；生成式场景则使用合成参数或时间函数。

`SCENE_FN` 是视觉主体位置。场景函数返回 `uint8 H,W,3` 的 pixel canvas，通过 `_render_vf()`、多密度 `GridLayer`、字符 palette、value field、particle、mask、blend mode 等组合出 ASCII 图像层。`references/scenes.md`、`references/effects.md`、`references/architecture.md` 是理解这一层的重点。

`TONEMAP` 是亮度归一化位置。`SKILL.md` 特别强调不要用简单的 `canvas * N` 线性倍增，因为会导致高光裁切或暗部失真；推荐 percentile-based adaptive `tonemap()`，并按场景设置 gamma。这个主题集中在 `references/composition.md`。

`SHADE` 是后处理位置，使用 `ShaderChain` 和 `FeedbackBuffer`。它处理 CRT、bloom、grain、glitch、vignette、chromatic aberration、kaleidoscope、feedback trails 等影像质感，核心参考是 `references/shaders.md` 和 `references/composition.md`。

`ENCODE` 是输出位置。设计上通常把 raw RGB frames pipe 给 `ffmpeg` 编码成 H.264、GIF 或图片序列；复杂项目可以按 clip 分段渲染后 concat，并可 mux audio。相关说明分布在 `README.md`、`references/architecture.md`、`references/scenes.md`、`references/optimization.md` 和 `references/troubleshooting.md`。

## 推荐阅读顺序

建议先读 `skills/creative/ascii-video/SKILL.md`，掌握技能触发场景、创意标准、六阶段 pipeline、工作流和关键实现禁忌。这个文件是目录的总纲，特别要关注 “Modes”、“Pipeline Architecture”、“Workflow”、“Critical Implementation Notes”。

第二步读 `skills/creative/ascii-video/README.md`，用它建立能力地图。README 对 grid、palette、color、value field、particle、shader、blend、scene pattern 的总结更紧凑，适合在正式深入 references 前形成全局印象。

第三步读 `references/architecture.md` 和 `references/composition.md`。前者回答“字符网格、字体、palette、颜色和 section 怎么组织”，后者回答“多层画布如何混合、如何避免画面过暗、feedback 和 mask 如何接入”。这两份是生成一个稳定渲染器的基础。

第四步根据输入类型选择 `references/inputs.md`。如果任务是音频可视化，重点看 audio analysis、beat detection、audio/video sync；如果是 video-to-ASCII，重点看 video sampling、luminance mapping、edge-weighted mapping、motion detection；如果是 TTS 或歌词视频，再看 text、SRT、TTS integration 和 audio mixing。

第五步读 `references/effects.md`、`references/shaders.md`、`references/scenes.md`。这三份决定作品是否只是“能跑”，还是有层次、有运动设计、有场景结构。`effects.md` 给原材料，`shaders.md` 给后处理语言，`scenes.md` 给场景协议、场景表和组合范式。

最后读 `references/optimization.md` 与 `references/troubleshooting.md`。它们适合在脚本接近可运行时使用，处理硬件档位、缓存、并行、Pillow 字体、NumPy broadcasting、ffmpeg pipe deadlock、macOS multiprocessing、亮度诊断等实际问题。

## 常见误区

一个常见误区是把这个目录当成现成命令行工具。根据当前片段看，目录中没有 `main.py`、`cli.py` 或 Python 包入口；它的职责是教 Agent 生成项目专用的单文件 Python renderer，而不是提供一个固定二进制或固定 API。

第二个误区是只关注 ASCII 字符映射，忽略完整影像管线。这里的设计不是简单把像素亮度换成字符，而是强调多 grid density、多层 blend、adaptive tonemap、shader chain、feedback、mask、scene table、parallel encoding 和 audio sync。

第三个误区是把 `references` 当作可一次性照抄的模板库。`SKILL.md` 明确要求每个项目要有创意概念和项目特异性发明，例如自定义字符集、专属色板、特殊 transition 或新的场景隐喻。引用库提供 vocabulary，但最终作品需要组合和改造。

第四个误区是忽略亮度。ASCII on black 天然偏暗，因此主流程要求 `scene_fn() -> tonemap() -> FeedbackBuffer -> ShaderChain -> ffmpeg` 的顺序，并用 percentile/gamma 方式处理亮度。简单乘法增亮是文档中特别标出的反模式。

第五个误区是误判平台兼容性。技能声明支持 Linux、macOS、Windows，但底层实现会涉及 Pillow 字体路径、ffmpeg、multiprocessing、Unicode glyph 支持等差异。相关风险集中在 `references/troubleshooting.md`，真正生成脚本时需要做字体验证、stderr 重定向、worker 状态隔离和输出帧数检查。
