# 目录：skills/creative/manim-video

## 它负责什么

`skills/creative/manim-video` 是 Hermes 内置创意类技能中的一个 Manim 视频制作技能目录，目标是把用户的“数学动画、算法可视化、技术解释、论文讲解、数据故事、架构图演示”等需求，转化为一套可执行的 Manim Community Edition 制作流程。它不是一个运行时 Python 包，也不是一个完整视频项目模板仓库，而是一组面向 Agent 的工作规约、参考手册和环境检查脚本。

从 `SKILL.md` 看，这个技能强调“先规划、再编码、再渲染”的生产管线：先写 `plan.md` 明确叙事弧、场景列表、视觉元素、配色和旁白；再写单文件 `script.py`，每个 Manim `Scene` 独立可渲染；然后用 `manim` 命令生成草稿或成片；最后通过 `ffmpeg` 拼接场景、可选混入音频并做审查。它的核心价值不只是告诉 Agent 如何调用 Manim API，而是把“教育视频的视觉叙事标准”固化成技能提示，包括几何优先、透明度分层、节奏留白、统一字体与色彩、首轮渲染质量等约束。

## 直接子目录地图

这个目录的结构很扁平，直接子目录只有两个：

`references/` 是主要知识库，存放 Manim 动画制作中按主题拆开的参考文档。它覆盖基础对象、动画语法、公式、图表与数据、3D 摄像机、场景规划、渲染、排障、视觉设计、论文解释、装饰元素、updater/value tracker、生产质量检查等主题。这里的文档是 Agent 在具体任务中按需读取的“细分手册”，不是每次都需要全量加载。

`scripts/` 是辅助脚本目录，目前关键文件是 `scripts/setup.sh`。它不负责创建项目，而是做前置环境检查：确认 `python3`、`manim`、`pdflatex`、`ffmpeg` 是否可用，并输出缺失项。根据当前片段推断，这个脚本主要用于技能启用前或用户本地环境排障阶段，因为它只检查依赖，不生成 Manim 示例文件。

目录根部还有 `SKILL.md` 和 `README.md`。`SKILL.md` 是真正的技能入口，定义触发场景、创作标准、依赖、模式、栈、管线、项目结构、实现注意事项和参考文档索引。`README.md` 是面向人类的简短说明，概括技能用途、用例和依赖检查命令。

## 关键入口

最关键入口是 `skills/creative/manim-video/SKILL.md`。Hermes 的技能加载机制通常读取 `SKILL.md` 的 frontmatter 和正文来决定技能名称、描述、版本、平台约束以及 Agent 执行该类任务时应遵守的流程。这里的 frontmatter 声明 `name: manim-video`、`platforms: [linux, macos, windows]`，说明它按设计可跨主流桌面平台使用；正文则承担“任务协议”的作用。

第二入口是 `skills/creative/manim-video/README.md`。它适合快速确认这个目录的定位：用 Manim CE 从文本提示制作 3Blue1Brown 风格动画，并覆盖规划、代码生成、渲染、拼接和迭代细化。它不是主流程细则，更多是目录说明和使用前提示。

第三入口是 `skills/creative/manim-video/scripts/setup.sh`。当用户问“能不能运行 Manim 视频技能”“本机缺什么依赖”“为什么渲染失败”时，这个脚本是最直接的检查入口。它的检查范围也反向说明了技能依赖边界：Python、Manim、LaTeX、ffmpeg 是硬依赖，TTS 只在 `SKILL.md` 中作为可选层出现。

## 主流程位置

主流程集中写在 `SKILL.md` 的 `Pipeline`、`Project Structure`、`Workflow` 和 `Critical Implementation Notes` 部分。它给出的流程是：

`PLAN --> CODE --> RENDER --> STITCH --> AUDIO (optional) --> REVIEW`

其中 `PLAN` 要求先产出 `plan.md`，明确叙事结构、场景拆分、视觉元素、配色和旁白。`CODE` 要求生成单个 `script.py`，并采用“一个 class 对应一个 scene”的 Manim 结构。`RENDER` 使用 `manim -ql` 做草稿、`manim -qh` 做生产输出。`STITCH` 通过 `ffmpeg concat` 把多个 scene 输出合并到 `final.mp4`。`AUDIO` 是可选阶段，可用 `ffmpeg` 混入旁白或背景音乐。`REVIEW` 则强调预览静帧、对照计划检查画面质量，并根据结果调整。

更细的主流程支撑分散在 `references/` 中：场景设计看 `references/scene-planning.md`，对象和布局看 `references/mobjects.md`，动画组合和节奏看 `references/animations.md` 与 `references/animation-design-thinking.md`，公式推导看 `references/equations.md`，数据或算法可视化看 `references/graphs-and-data.md`，3D 场景看 `references/camera-and-3d.md`，最终渲染和音视频处理看 `references/rendering.md`，质量验收看 `references/production-quality.md`，故障处理看 `references/troubleshooting.md`。

## 推荐阅读顺序

初次理解这个目录，建议先读 `README.md`，用很短时间确认它解决什么问题、依赖哪些工具。随后读 `SKILL.md`，重点看 `When to use`、`Creative Standard`、`Pipeline`、`Workflow`、`Critical Implementation Notes` 和 `References` 索引，这能建立完整的地图。

如果要真的使用这个技能制作视频，下一步应读 `references/scene-planning.md`，因为该技能明确要求“先写计划再写代码”。接着读 `references/visual-design.md` 和 `references/production-quality.md`，先把画面层级、字体、配色、空间预算和检查清单建立起来，再进入 API 细节。

进入实现阶段后，按任务类型选择参考：普通动画读 `references/mobjects.md` 和 `references/animations.md`；公式推导读 `references/equations.md`；算法、图表、数据故事读 `references/graphs-and-data.md`；动态跟踪、实时变化对象读 `references/updaters-and-trackers.md`；3D 或镜头运动读 `references/camera-and-3d.md`；论文讲解读 `references/paper-explainer.md`。最后在渲染前后读 `references/rendering.md`、`references/troubleshooting.md`，并可运行 `scripts/setup.sh` 检查环境。

## 常见误区

一个常见误区是把这里当成可直接执行的视频项目。实际它是技能说明目录，不包含现成的 `script.py`、`plan.md` 或 `final.mp4`，这些文件应在用户具体项目目录中生成。`SKILL.md` 中展示的 `project-name/` 结构是推荐产物结构，不是本目录已经存在的代码结构。

第二个误区是跳过规划直接写 Manim 代码。这个技能的主张很明确：先确定叙事弧、视觉节奏和“aha moment”，再写代码。若只把它当作 Manim API 摘要，会丢掉该技能最重要的部分，即教育动画的生产质量约束。

第三个误区是每次都全量阅读 `references/`。这个目录的参考文档是按主题拆分的，正确方式是先用 `SKILL.md` 的 `References` 表定位需要的文档，再按任务类型读取。比如公式动画不一定需要 3D 摄像机文档，论文讲解则更应该关注 `paper-explainer.md`、`scene-planning.md` 和 `production-quality.md`。

第四个误区是把 `scripts/setup.sh` 理解为安装器。它实际是检查脚本，不会自动安装 Manim、LaTeX 或 ffmpeg。缺依赖时，它只会提示缺失项。真正安装仍需要用户或 Agent 根据平台使用对应包管理方式处理。

第五个误区是忽略 Manim 的渲染迭代成本。`SKILL.md` 明确建议总是用 `-ql` 迭代，只有最终输出才用 `-qh`。如果一开始就高质量渲染，多场景视频会显著拖慢调试速度。
