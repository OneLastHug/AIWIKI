# 文件：skills/creative/manim-video/README.md

## 一句话定位

`skills/creative/manim-video/README.md` 是 `manim-video` 技能目录的轻量入口说明，用来告诉读者这个技能面向“用 Manim Community Edition 生成数学/技术动画视频”的生产流水线，并给出最小依赖与 setup 检查命令；真正驱动代理行为的详细规范在同目录的 `SKILL.md` 和 `references/` 下。

## 它暴露/定义了什么

这个 README 暴露的是人类可快速阅读的技能摘要，而不是可执行 API。它定义了三类信息：第一，技能名称和目标，即用 Manim CE 制作类似 3Blue1Brown 风格的动画视频；第二，适用场景，包括概念讲解、方程推导、算法可视化、数据故事和架构图；第三，运行前置条件，即 Python 3.10+、`manim`、LaTeX、`ffmpeg`，并提示可运行 `bash skills/creative/manim-video/scripts/setup.sh` 做环境检查。

它没有 YAML frontmatter，也没有声明 `name`、`description`、`platforms` 等 Hermes 技能元数据。因此它不是技能加载器识别技能的主文件；这些元数据由 `skills/creative/manim-video/SKILL.md` 承担。

## 谁调用它

根据当前片段推断，Hermes 的自动技能发现流程不会直接调用这个 README。相关代码主要扫描 `SKILL.md`，例如 `agent/prompt_builder.py`、`agent/skill_commands.py`、`tools/skills_tool.py` 都围绕 `SKILL.md` 建立技能列表、平台过滤、描述提取和 slash command 映射。

这个 README 的实际调用者更可能是人：开发者、技能维护者、文档读者，或正在浏览技能目录的用户。工具层面上，`tools/skills_tool.py` 的 `skill_view` 支持通过 `file_path` 读取技能目录中的辅助文件；由于 `README.md` 属于同一技能目录下的普通 Markdown 文件，它可以被显式读取，但不会作为默认技能提示注入。

## 它调用谁

README 本身不执行代码，但它指向一个可执行入口：`skills/creative/manim-video/scripts/setup.sh`。该脚本会检查 `python3`、Python 包 `manim`、`pdflatex` 和 `ffmpeg` 是否可用，并用 `ok`、`fail` 两个 shell 辅助函数输出检查结果。

README 还间接依赖 Manim CE 生态：Manim 负责场景渲染与动画引擎，LaTeX 负责公式排版，`ffmpeg` 负责视频拼接、转码或音频合成。README 中的 Manim 官网链接属于外部资料入口，这里按要求不展开真实地址，记为 `[URL已移除]`。

## 核心流程

README 用一句话概括了完整生产链路：从文本提示出发，代理负责创意规划、Python 代码生成、渲染、场景拼接和迭代优化。结合 `SKILL.md` 的相邻上下文，可以还原更完整的流程：先写 `plan.md` 明确叙事弧线、场景列表、视觉元素、配色和旁白；再写单个 `script.py`，每个 Manim `Scene` 类对应一个可独立渲染的场景；随后用 `manim -ql` 做草稿渲染，用 `manim -qh` 做最终渲染；多场景输出后通过 `ffmpeg concat` 拼接为 `final.mp4`；如需要旁白或背景音，再用 `ffmpeg` 进行音频混合；最后通过预览帧或成片审查节奏、可读性和视觉一致性。

README 只保留了这个流程的入口层表达，没有展开具体命令、代码模板和质量规则。这种分层让 README 适合快速识别技能用途，而把高密度操作规范放在 `SKILL.md`、`references/rendering.md`、`references/visual-design.md`、`references/equations.md` 等文件中。

## 关键函数的高层作用

这个文件没有定义函数、类或模块级变量，因此不存在需要逐个解释的核心函数。它的“关键接口”是文档中的 setup 命令：`bash skills/creative/manim-video/scripts/setup.sh`。

相邻脚本 `scripts/setup.sh` 中的 `ok()` 负责格式化成功检查项，`fail()` 负责格式化失败检查项；主体逻辑依次验证 Python、Manim、LaTeX、`ffmpeg`，并根据累计的 `errors` 数量输出最终状态。这些是环境诊断辅助逻辑，不参与视频生成。

如果从技能使用角度看，真正的核心“函数式入口”是 Hermes 的 `skill_view(name="manim-video")` 以及 slash command 技能触发机制，但它们读取的是 `SKILL.md`，不是这个 README。

## 修改风险

最大风险是把 README 写得与 `SKILL.md` 不一致。比如 README 说只需要 `pip install manim`，但 `SKILL.md` 要求 Manim CE v0.20+、LaTeX 和 `ffmpeg`；如果版本、依赖或流程描述不同步，会误导用户排查环境问题。

第二个风险是误以为修改 README 会改变代理行为。由于技能发现和提示注入依赖 `SKILL.md`，只改 README 通常不会改变 Hermes 加载 `manim-video` 后的行为。若要调整代理在规划、编码、渲染、设计标准方面的实际指令，应修改 `skills/creative/manim-video/SKILL.md` 或对应 `references/` 文件。

第三个风险是外部链接与命令路径。README 当前包含外部 Manim 链接和相对 setup 命令；如果目录结构变化，`bash skills/creative/manim-video/scripts/setup.sh` 会失效。若文档生成系统或站点镜像对真实 URL 有限制，也需要避免直接暴露外部地址，改用受控文本或站内说明。

第四个风险是把 README 扩写成完整教程，导致它与 `SKILL.md`、网站自动生成文档重复。这个文件更适合作为轻量索引：说明“这是什么、能做什么、先检查什么”，深层制作规则应继续留在 `SKILL.md` 和 `references/` 中。
