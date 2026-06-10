# 目录：skills/creative/p5js

## 它负责什么

`skills/creative/p5js` 是 Hermes 内置 skills 体系中的一个创意编码技能包，面向 p5.js 项目生成与交付。它不是应用运行时代码，也不是 Python 包，而是一套给 Agent 使用的“工作流说明 + 参考资料 + 辅助脚本 + HTML 模板”。目标是让 Agent 在用户提出 p5.js、generative art、canvas animation、interactive visualization、WebGL、shader、audio-reactive visual 等需求时，能按固定生产流程输出可运行的浏览器视觉作品。

这个目录的核心定位可以概括为：把自然语言创意需求转成一个自包含 HTML sketch，并支持预览、交互调参、PNG/GIF/MP4/SVG 等导出路径。默认技术栈是 p5.js 1.11.3，通过 CDN 引入；基础使用只需要浏览器，不要求构建步骤。涉及高质量导出时，才会进入 Node.js、Puppeteer、ffmpeg 这类可选工具链。

从 `SKILL.md` 的内容看，这个技能特别强调“作品质量”和“创作流程”：先定义 creative concept，再设计 canvas、renderer、interaction、export format，然后写单文件 HTML，最后预览、导出、验证。它要求生成物不要停留在教程级示例，而要具备颜色系统、构图层次、运动词汇、纹理细节和项目特有的算法行为。

## 直接子目录地图

`skills/creative/p5js` 的直接结构很小，主要分三类：

`references/` 是知识库目录，按主题拆分 p5.js 创作所需的技术与设计参考。它不是运行入口，而是 Agent 写 sketch 时按需查阅的专题手册。当前包含 `core-api.md`、`shapes-and-geometry.md`、`visual-effects.md`、`animation.md`、`typography.md`、`color-systems.md`、`webgl-and-3d.md`、`interaction.md`、`export-pipeline.md`、`troubleshooting.md`。这些文件覆盖 canvas 初始化、draw loop、offscreen buffers、噪声、粒子、flow field、动画、字体、颜色、混合模式、WebGL、音频交互、导出和常见问题。

`scripts/` 是辅助执行脚本目录，服务于本地预览和导出流程。`setup.sh` 检查 Node.js、npm、Puppeteer、ffmpeg、Python3、浏览器等可选依赖；`serve.sh` 用 Python 或 Node 启动本地静态服务器，适合加载本地字体、图片、数据文件；`export-frames.js` 用 Puppeteer 截取 canvas 帧；`render.sh` 把 HTML sketch 渲染为帧序列，再通过 ffmpeg 编码成 MP4。

`templates/` 是模板目录，目前关键文件是 `viewer.html`。它提供交互式生成艺术 viewer：左侧 sidebar、seed 切换、参数滑条、重新生成、重置、下载 PNG、响应式 canvas 等基础框架。具体项目需要替换算法、参数、配色、标题和描述，但保留 seed 与 action 的通用交互骨架。

根目录下还有两个重要文件：`SKILL.md` 是技能被 Agent 使用时的主说明；`README.md` 是面向读者的简短目录说明和快速介绍。

## 关键入口

最关键入口是 `skills/creative/p5js/SKILL.md`。它包含 frontmatter 元数据，例如 `name: p5js`、简短 description、版本、支持平台、tags、related skills。根据 Hermes skills 的约定，这类 `SKILL.md` 会被技能加载流程识别，用来告诉 Agent 什么时候使用该技能、按什么流程工作、查哪些参考资料、采用什么输出标准。

`SKILL.md` 内部的“Pipeline”是行为入口：`CONCEPT → DESIGN → CODE → PREVIEW → EXPORT → VERIFY`。这不是代码函数，但它定义了 Agent 执行 p5.js 任务时的主线。后续的 “Workflow” 又把流程细化为 creative vision、technical design、code sketch、preview/export 等步骤。

第二个入口是 `skills/creative/p5js/templates/viewer.html`。当任务是“interactive generative art”，尤其需要 seed 浏览、参数调节、PNG 下载时，`SKILL.md` 明确要求从这个模板开始。它本身就是完整 HTML，可以作为项目初始壳层。

第三个入口是导出脚本组合：`scripts/render.sh` 调用 `scripts/export-frames.js`。前者负责命令行参数解析、帧数计算、依赖检查和 ffmpeg 编码；后者负责通过 Puppeteer 打开 HTML、定位 canvas、等待 `window._p5Ready`、逐帧截图。对于 MP4 或高分辨率批量导出，这两者是实际执行入口。

## 主流程位置

主流程文档位于 `skills/creative/p5js/SKILL.md` 的 “Pipeline” 和 “Workflow” 段落。这里定义了从创意到成品的完整路径：先把用户 prompt 转成视觉概念，包括 mood、visual story、color world、shape language、motion vocabulary；再决定 mode、canvas size、renderer、frame rate、export target、interaction model；然后写单文件 HTML，通常按 globals、`preload()`、`setup()`、`draw()`、helpers、classes、event handlers 组织；最后通过浏览器预览或脚本导出，并检查视觉质量、性能和目标尺寸下的效果。

交互式生成艺术的主流程落在 `templates/viewer.html`。模板已经把 seed 导航、参数更新、重新生成、下载等 UI 流程固化好，项目实现者主要替换 `PARAMS`、绘制算法、调参控件和 palette。根据当前片段推断，模板的设计意图是减少每个 p5.js 交互作品重复搭建控制面板的成本，保持生成艺术项目的通用操作体验。

视频导出的主流程落在 `scripts/render.sh` 与 `scripts/export-frames.js`。`render.sh` 负责把 `--width`、`--height`、`--fps`、`--duration` 等参数转换成总帧数，创建临时帧目录，再调用 Node 脚本截帧，最后用 ffmpeg 编码。`export-frames.js` 则有两种捕获模式：如果 sketch 在 `setup()` 中调用 `noLoop()` 并设置 `window._p5Ready = true`，就使用 `redraw()` 做确定性逐帧捕获；否则退回 timed fallback，精度较低，可能出现掉帧或重复帧。

参考资料的主流程不是线性的，而是按问题分流：基础 canvas 和 draw loop 看 `references/core-api.md`；视觉效果看 `references/visual-effects.md`；运动设计看 `references/animation.md`；颜色与背景看 `references/color-systems.md`；3D 和 shader 看 `references/webgl-and-3d.md`；鼠标、键盘、触摸、音频、滚动看 `references/interaction.md`；导出问题看 `references/export-pipeline.md`；性能和浏览器问题看 `references/troubleshooting.md`。

## 推荐阅读顺序

建议先读 `skills/creative/p5js/README.md`，快速建立目录角色、支持模式和导出格式的整体认识。它比 `SKILL.md` 短，适合作为入口地图。

然后读 `skills/creative/p5js/SKILL.md`，重点看 “Creative Standard”、“Modes”、“Stack”、“Pipeline”、“Workflow”。这部分决定 Agent 应该如何思考 p5.js 任务，而不是只提供 API 片段。

接着读 `templates/viewer.html`。如果你关心这个技能如何产出可交互的生成艺术作品，这个模板比零散参考更重要。它展示了 seed、参数、canvas 区域和下载操作如何组织在一个单文件 HTML 中。

之后按任务类型读 `references/`。做普通 sketch 先看 `core-api.md`、`color-systems.md`、`shapes-and-geometry.md`；做粒子、噪声、纹理、反馈先看 `visual-effects.md`；做动画看 `animation.md`；做字体视觉看 `typography.md`；做 3D 或 shader 看 `webgl-and-3d.md`；做交互或音频响应看 `interaction.md`；准备交付时看 `export-pipeline.md` 和 `troubleshooting.md`。

最后再看 `scripts/`。如果只是浏览器打开 HTML，不一定需要脚本；如果要 headless export、MP4、批量帧、高分辨率输出，再阅读 `setup.sh`、`serve.sh`、`export-frames.js`、`render.sh`。

## 常见误区

一个常见误区是把这个目录当成普通 p5.js 示例库。实际上它没有一组可直接复用的成品 sketch，而是给 Agent 的生产规范和参考系统。真正的项目 HTML 需要根据用户需求生成。

另一个误区是以为所有任务都要跑 Node 或 ffmpeg。基础 p5.js 输出是单文件 HTML，用浏览器即可运行；Node.js、Puppeteer、ffmpeg 只服务于 headless 截帧和 MP4 等导出场景。

不要忽视 `SKILL.md` 中的创意标准。该技能明确反对默认配色、纯黑白背景、教程式粒子系统、无层次构图。阅读时应把它理解为“创作质量约束”，不是可有可无的风格建议。

也不要在视频导出时直接假设实时动画捕获一定精确。`export-frames.js` 的确定性路径依赖 sketch 配合：需要 `noLoop()`、`window._p5Ready = true`，并允许脚本调用 `redraw()`。如果没有这些约定，只能 timed fallback，适合预览但不适合要求帧级一致性的动画。

最后，`templates/viewer.html` 不是所有项目的唯一模板。`SKILL.md` 明确区分了交互式生成艺术和简单 sketch、动画、视频导出：前者优先用 viewer 模板，后者可以使用 bare HTML。理解这个分流，才能正确定位模板和脚本的边界。
