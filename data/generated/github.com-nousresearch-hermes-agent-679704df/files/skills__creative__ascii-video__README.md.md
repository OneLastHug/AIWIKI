# 文件：skills/creative/ascii-video/README.md

## 一句话定位

`skills/creative/ascii-video/README.md` 是 `ascii-video` 创意技能的总览型说明文档，用来向开发者和使用者解释该技能能生成什么、推荐什么渲染架构、有哪些效果组件、性能边界和常见坑；它不是运行时代码入口，也不直接参与 Hermes 的技能加载逻辑。

## 它暴露/定义了什么

这个文件暴露的是一套“彩色 ASCII 视频生成”的设计蓝图，而不是 Python API。它定义了技能的能力范围：把 video、audio、image、text 或纯生成式数学输入转换成 MP4、GIF 或 PNG 序列；默认目标是 1080p、24fps、每个字符单元有完整 RGB 颜色。

文档还定义了几个重要概念层：

- 六类工作模式：`Video-to-ASCII`、`Audio-reactive`、`Generative`、`Hybrid`、`Lyrics/text`、`TTS narration`。
- 统一流水线：`INPUT --> ANALYZE --> SCENE_FN --> TONEMAP --> SHADE --> ENCODE`。
- 网格系统：用不同字号和字符密度构成 `xs` 到 `xxl` 多层 ASCII 画面。
- 视觉词汇库：字符 palette、颜色策略、value field、hue field、coordinate transforms、particles、shader、blend mode、feedback、mask、transition。
- 实现约束：单文件 Python renderer、NumPy/Pillow/SciPy/ffmpeg、无 GPU、并行分段渲染。
- 质量和性能边界：亮度必须经过 `tonemap()`，渲染瓶颈在字符位图合成，`ffmpeg` 管道不能阻塞。

它更像是 `SKILL.md` 的背景说明和能力目录；真正被 agent 注入为技能指令的主文件是同目录的 `SKILL.md`。

## 谁调用它

根据当前片段推断，运行时没有核心代码直接调用这个 README。依据是 `agent/skill_commands.py`、`tools/skills_tool.py`、`agent/prompt_builder.py` 的技能扫描逻辑主要围绕 `SKILL.md` 和 `DESCRIPTION.md`，`scan_skill_commands()` 通过 `iter_skill_index_files(scan_dir, "SKILL.md")` 建立 `/ascii-video` 这类 slash command，`skill_view()` 默认读取技能主内容也是 `SKILL.md`。

因此，这个 README 的“调用者”主要是人和间接阅读场景：

- 开发者查看 `skills/creative/ascii-video/README.md` 理解技能能力。
- agent 在已激活 `ascii-video` 技能后，可能根据 `SKILL.md` 中的引用继续读取 `references/*.md`，但 README 本身不是主加载对象。
- bundled skills 同步流程会把整个 `skills/creative/ascii-video/` 目录作为技能包同步到用户技能目录；README 会随包一起存在，但不是 slash command 的索引文件。

## 它调用谁

README 不执行代码，所以没有真实的函数调用关系。它在文档层面“指向”同目录的多个参考文件和推荐组件：

- `skills/creative/ascii-video/SKILL.md`：技能入口说明，负责告诉 agent 何时使用、如何规划、如何构建单文件 Python renderer。
- `references/architecture.md`：网格、字体、palette、颜色系统、`_render_vf()` 等核心渲染基础。
- `references/composition.md`：`blend_canvas()`、`tonemap()`、`FeedbackBuffer`、mask 和多层合成。
- `references/effects.md`：value field、noise、SDF、particle、coordinate transform 等视觉生成模块。
- `references/shaders.md`：`ShaderChain`、shader catalog、transition 和编码相关建议。
- `references/scenes.md`：scene protocol、`Renderer`、`SCENES`、`render_clip()`、并行渲染和场景设计模式。
- `references/inputs.md`：audio FFT、video sampling、image/text/TTS 输入处理。
- `references/optimization.md` 和 `references/troubleshooting.md`：性能配置、并行策略、平台坑和诊断方式。

这里的“调用”是知识依赖：README 给出总览，具体实现细节分散在 `references/` 下。

## 核心流程

README 描述的核心流程是一个标准化的视频渲染管线。

第一步是 `INPUT`。输入可以是视频、音频、图片、字幕文本、TTS 文案，或者没有输入的纯生成式场景。视频模式会解码帧，音频模式会读取采样，生成式模式则只需要时间、分辨率和随机种子。

第二步是 `ANALYZE`。音频会提取 6-band FFT、RMS、spectral centroid、flatness、flux、beat detection 等帧级特征；视频会提取 luminance、edge、motion；这些特征供后续场景函数驱动视觉变化。

第三步是 `SCENE_FN`。这是视觉创作核心：场景函数直接返回 `uint8 H,W,3` 像素画布，通常通过多个字符网格、value field、hue field、blend mode、particle layer 组合成画面。文档强调不要只做单层 ASCII，要使用多密度网格制造纹理和深度。

第四步是 `TONEMAP`。由于 ASCII 视频大部分像素是黑底，直接线性放大会裁切高光并让画面发灰，文档要求使用 percentile-based adaptive brightness normalization，并按场景调 gamma。

第五步是 `SHADE`。像素画布进入 `ShaderChain` 和 `FeedbackBuffer`，添加 CRT、bloom、glitch、scanline、color grade、feedback trail 等后期效果。

第六步是 `ENCODE`。最终 raw RGB frame 通过 `ffmpeg` 编码为 H.264 MP4、GIF 或 PNG 序列；较长视频推荐分 clip 并行渲染后再拼接和混音。

## 关键函数的高层作用

目标文件本身没有定义函数，但它反复强调生成脚本中应有的关键函数/类：

`scene_fn()` 是每个场景的主要创作函数，职责是根据时间、音频/视频特征和场景配置生成一帧 RGB canvas。它决定画面的主题、构图、运动和层次。

`tonemap()` 是亮度安全阀，负责用百分位归一化和 gamma 调整把偏暗的 ASCII 画面拉到可观看范围，同时避免简单乘法导致的高光截断。

`_render_vf()` 根据当前文档和 `SKILL.md` 推断是 value field 到字符网格/像素画布的基础渲染 helper，通常负责把亮度场映射到字符 palette，并用预栅格化字体合成到 canvas。

`ShaderChain` 是后处理流水线容器，按配置顺序应用 shader，使场景可以复用 CRT、glow、glitch、color、blur、noise 等效果。

`FeedbackBuffer` 保存上一帧或历史帧，并通过缩放、旋转、位移、镜像、hue shift 等变换重新混合到当前帧，用于拖影、递归、隧道和时间残影。

`render_clip()` 和 scene table 根据当前片段推断负责把时间段映射到具体 scene，并支持分段并行渲染、选择性重渲染和最终拼接。

## 修改风险

最大的风险是把 README 当成运行时入口去改。Hermes 技能加载主要依赖 `SKILL.md` 的 frontmatter 和正文；如果只改 README，slash command 描述、技能激活提示、agent 首次看到的流程可能不会变化。要改变 agent 行为，应优先改 `SKILL.md` 或被其引用的 `references/*.md`。

第二个风险是文档与参考文件失配。README 中列出的组件很多，如 shader 数量、palette 数量、文件结构、reference 文件名。如果 `references/` 发生增删改而 README 没同步，会误导使用者。当前 README 的文件结构里提到 `design-patterns.md`，但实际同目录文件列表显示是 `references/composition.md`、`references/scenes.md` 等，没有看到 `references/design-patterns.md`；这类不一致需要谨慎核对。

第三个风险是过度承诺能力。README 说“38 composable shaders”“21 value field generators”“No GPU”“1080p 24fps default”等，如果实际参考实现或 agent 生成脚本达不到，用户会把文档视为能力保证。修改数字和性能表时应基于可复现 benchmark 或示例脚本。

第四个风险是平台和依赖描述不准。技能声明支持 linux、macos、windows，但 README 依赖 `ffmpeg`、字体、Pillow、SciPy、可选 OpenCV 和 TTS API；任何新增依赖都应同步到 `SKILL.md` 的 prerequisites，并注意仓库依赖上界策略。

第五个风险是外部链接和发布信息。README 原文包含真实仓库链接；在面向内部学习文档或受限环境输出时应移除或替换为占位文本，避免把文档生成系统暴露成外链索引。
