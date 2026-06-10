# 目录：packages/coding-agent/docs

## 它负责什么

`packages/coding-agent/docs` 按目标描述应是 `packages/coding-agent` 包内的文档目录，用来承载 coding agent 相关的说明材料，而不是运行时代码入口。它的角色通常是把 `packages/coding-agent` 的使用方式、架构约定、开发流程、测试方式、交互模式或示例说明集中放在源码包旁边，方便维护者在修改 agent 行为前先理解设计边界。

但根据当前可读取片段，目标路径没有被成功定位：在受限环境中尝试读取 `packages/coding-agent/docs`、`packages/coding-agent` 时返回 `No such file or directory`，同时当前 shell 实际落点显示为 `/data`，不是预期的仓库根目录。也就是说，下面对该目录职责的判断只能作为“根据当前片段推断”，依据是任务给出的目标路径、仓库规则中多次提到的 `packages/coding-agent` 包，以及相邻开发约定里关于 `packages/coding-agent/test/suite/`、`pi Interactive Mode`、release smoke test 的描述。

从仓库规则看，`packages/coding-agent` 是一个核心包，涉及交互式 coding agent、测试套件、faux provider、release shrinkwrap、CLI smoke test 等能力。因此 `packages/coding-agent/docs` 更可能是面向开发者和维护者的包内知识入口，而不是用户站点文档或生成产物。

## 直接子目录地图

当前片段无法列出 `packages/coding-agent/docs` 的真实直接子目录。目标路径读取失败，所以不能可靠说明它下面是否有 `architecture`、`guides`、`examples`、`testing`、`providers` 之类的目录。

根据当前片段推断，如果该目录存在，它的直接子目录大概率会按主题拆分，而不是按源码模块一一镜像。可能的路径角色包括：

`packages/coding-agent/docs`：包级文档根目录，承接入口说明、开发者说明、交互模式说明或架构概览。

`packages/coding-agent/docs/...`：若存在下级目录，应优先按“使用场景”理解，例如测试、交互式 TUI、provider 接入、release 或调试流程，而不是把它当作源码实现目录。

由于没有文件清单，不能逐项展开，也不能确认是否存在 README、Markdown 指南、图片资源、自动生成文档或示例片段。

## 关键入口

当前无法读取到真实文件名，因此不能确认 `packages/coding-agent/docs/README.md` 是否存在。按照常见包内文档结构，推荐先寻找这些入口：

`packages/coding-agent/docs/README.md`：如果存在，通常是本目录的导航页，说明文档主题和阅读路径。

`packages/coding-agent/README.md`：这是包级入口，比 `docs` 更靠近 npm 包或 workspace 包的对外说明，适合先确认 coding agent 的目标、命令和使用边界。

`packages/coding-agent/package.json`：这是包的工程入口，用来确认脚本、依赖、导出形式、测试命令和构建方式。文档里的命令通常要回到这里校验。

`packages/coding-agent/src`：这是实现入口。若文档提到 agent 主循环、会话、工具调用、provider、TUI 交互或文件编辑能力，最终都应回到 `src` 下找对应实现。

`packages/coding-agent/test/suite`：仓库规则明确提到这里是 coding agent 测试套件位置，并要求使用 `test/suite/harness.ts` 和 faux provider。若 docs 讲行为约定，测试目录通常是最可靠的行为样本。

## 主流程位置

根据当前片段推断，`packages/coding-agent/docs` 自身不承载主流程代码；它应该描述主流程，真正实现位于 `packages/coding-agent/src` 及测试目录中。

主流程可以按以下线索定位：

第一层是 CLI 或包入口。应从 `packages/coding-agent/package.json` 的 `bin`、`exports`、`scripts` 查起，找到启动 coding agent 的 TypeScript 入口。release smoke test 中出现 `/tmp/pi-local-release/node/pi`、`/tmp/pi-local-release/bun/pi`、`pi -p "Say exactly: ok"` 和交互模式启动，说明 coding agent 最终会被顶层 `pi` 命令串起来。

第二层是交互式会话。仓库规则给出了 tmux 测试方式：运行 `./pi-test.sh`，输入 prompt，使用 Escape、`C-o` 等按键。这说明主流程中有 TUI 或终端交互层，负责读取用户输入、渲染状态、处理快捷键并驱动 agent 回合。

第三层是 agent 执行循环。coding agent 的核心流程通常包括接收用户任务、构造上下文、调用 provider、解析模型输出、执行工具、处理文件读写或命令结果、再把结果反馈给模型或用户。docs 如果讲架构，应服务于理解这条链路。

第四层是测试验证。`packages/coding-agent/test/suite/harness.ts` 和 faux provider 是行为回归的关键位置。文档如果讲“如何验证某个 agent 行为”，应和这些测试入口互相印证。

## 推荐阅读顺序

1. 先读 `packages/coding-agent/README.md`，确认这个包对外提供什么能力、和顶层 `pi` 命令是什么关系。

2. 再读 `packages/coding-agent/docs/README.md` 或 docs 根目录下的总览文件。如果没有总览文件，就先看命名最宽泛的架构、开发或 testing 文档。

3. 接着看 `packages/coding-agent/package.json`，把文档里提到的命令、脚本、测试方式和实际工程配置对齐。

4. 然后进入 `packages/coding-agent/src`，只追主链路：CLI 入口、会话启动、模型 provider 调用、工具执行、终端渲染和错误处理。overview 阶段不要逐文件读叶子模块。

5. 最后看 `packages/coding-agent/test/suite`，尤其是 `test/suite/harness.ts` 和 regressions 目录。这里能帮助确认文档描述的是设计意图，还是已经被测试固定下来的行为契约。

## 常见误区

不要把 `packages/coding-agent/docs` 当成运行时代码目录。它的价值是建立地图，真正行为要回到 `packages/coding-agent/src` 和测试套件确认。

不要只读 docs 就修改 agent 行为。coding agent 涉及命令执行、文件编辑、模型 provider、交互式终端和测试 harness，文档可能滞后，必须用源码和测试校验。

不要跳过 `package.json`。很多关键入口不是靠文件名猜出来的，而是由 workspace 脚本、bin 配置、exports 和依赖关系决定。

不要把 `packages/coding-agent/test/suite` 和普通单测等同看待。仓库规则明确要求这里使用 harness 和 faux provider，说明它承担的是 agent 行为级回归验证，而不是只测某个小函数。

不要在 overview 阶段逐个叶子文件解释。这个目录的学习重点应是“文档如何组织 coding agent 的知识”和“文档如何指向源码主流程”，而不是把每个 Markdown 文件当成独立模块拆解。

当前结论受限于目标路径未成功读取；若后续能访问真实 `packages/coding-agent/docs` 文件清单，应优先用实际直接子目录、README 标题和文档内引用来替换以上推断内容。
