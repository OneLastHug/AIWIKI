# 文件：skills/creative/p5js/README.md

## 一句话定位

`skills/creative/p5js/README.md` 是 `p5js` 创意编程技能的用户级总览页，用来说明这个 skill 能生成什么、支持哪些模式、依赖什么、目录里有哪些参考资料和脚本；它不是运行入口，也不包含业务逻辑，而是帮助人和 agent 快速理解 `skills/creative/p5js/` 这套 p5.js 生产流水线的边界。

## 它暴露/定义了什么

该文件主要定义四类信息。第一是能力定位：使用 p5.js 创建浏览器端交互视觉艺术、生成艺术、数据可视化、动画、3D、图像处理和音频响应作品。第二是输出契约：推荐产物是单个自包含 HTML 文件，基础运行只依赖现代浏览器和 CDN 脚本。第三是模式与导出格式表：包括 HTML、PNG、GIF、MP4、SVG，以及各自大致方法。第四是目录索引：把 `SKILL.md`、`references/`、`scripts/` 的职责列出来，让后续实现者知道该读哪里、用哪个辅助脚本。

它没有定义 Python 函数、JavaScript 函数或 Hermes 注册项；真正的 skill 元数据和工作流说明在 `skills/creative/p5js/SKILL.md`。

## 谁调用它

根据当前片段推断，Hermes 的 skill 加载机制主要围绕 `SKILL.md` 工作，而不是直接加载该 README。依据是 `tools/skills_tool.py` 的 `skill_view` 工具说明：默认读取 skill 的 `SKILL.md`，并可通过 `file_path` 加载 `references/`、`templates/`、`scripts/` 等关联文件；`agent/skill_commands.py` 也通过 slash skill 命令把 `SKILL.md` 注入上下文。

因此，这个 README 的“调用者”更准确地说是人类维护者、文档浏览者，或 agent 在需要目录说明时通过通用文件读取能力读取它。仓库内未看到核心代码硬编码调用 `skills/creative/p5js/README.md`。

## 它调用谁

README 自身不调用任何代码。它引用和指向同目录资源：`skills/creative/p5js/SKILL.md` 作为主工作流文档，`skills/creative/p5js/references/*.md` 作为按主题拆分的知识库，`skills/creative/p5js/scripts/setup.sh` 用于依赖检查，`skills/creative/p5js/scripts/serve.sh` 用于本地服务，`skills/creative/p5js/scripts/render.sh` 和 `skills/creative/p5js/scripts/export-frames.js` 用于 headless 导出。

它还描述 p5.js 运行时能力，如 `saveCanvas()`、`saveGif()`、p5.js-svg renderer 等，但这些只是用户生成作品时会用到的外部 API，不是 README 的直接依赖。

## 核心流程

README 表达的主流程是“从提示词到可运行视觉作品”。用户或 agent 先根据需求选择模式，例如生成艺术、交互体验、3D 场景或音频响应；然后生成一个自包含 HTML sketch；基础预览直接在浏览器打开；如果需要本地资源，则配合本地服务器；如果需要静态或动画导出，则在 sketch 内使用 p5.js 保存函数，或通过 `render.sh`、`export-frames.js` 走 Puppeteer 加 ffmpeg 的批量渲染链路。

从技能体系看，README 是索引页，`SKILL.md` 才是执行规范；当上下文不足时，agent 应按 `SKILL.md` 的提示用 `skill_view(name="p5js", file_path="references/...")` 继续加载专题资料。

## 关键函数的高层作用

该 README 没有本地函数。它提到的关键能力可以按外部函数/脚本理解：`saveCanvas()` 负责从当前 p5.js canvas 保存 PNG；`saveGif()` 负责导出 GIF；`scripts/render.sh` 包装 headless 视频导出流程，先调用 `export-frames.js` 抓取帧，再用 ffmpeg 编码 MP4；`scripts/export-frames.js` 使用 Puppeteer 打开 HTML，并在 deterministic 模式下依赖 sketch 设置 `noLoop()` 和 `window._p5Ready = true`，再通过 `redraw()` 一帧一帧截图。

辅助脚本如 `setup.sh`、`serve.sh` 只承担环境检查和本地预览支持，不是创作逻辑核心。

## 修改风险

最大风险是把 README 写得与 `SKILL.md`、`references/` 或脚本实际能力不一致。例如新增导出格式、改脚本参数、调整目录结构后只改 README，会误导使用者；反过来只改脚本不改 README，也会让技能入口文档过期。

第二个风险是误导 Hermes skill 机制。README 不应暗示自己是注册入口或自动加载入口；skill 的可发现性来自 `SKILL.md` frontmatter 和技能扫描逻辑。如果把关键执行规则只放在 README，而不放进 `SKILL.md`，agent 默认加载 skill 时可能看不到这些规则。

第三个风险是外部依赖描述。该文件目前说基础使用只需现代浏览器，但 headless 导出需要 Node.js、Puppeteer、ffmpeg；如果修改导出链路或 CDN 版本，必须同步检查 `scripts/render.sh`、`scripts/export-frames.js` 和相关 `references/export-pipeline.md`，否则会造成“文档能跑、脚本不能跑”或“脚本已变、文档仍旧”的断层。
