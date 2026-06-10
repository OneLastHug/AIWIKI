# 文件：packages/coding-agent/examples/README.md
## 一句话定位
这是 `pi-coding-agent` 示例目录的导航页，用最小成本告诉读者这里有哪些示例、各自解决什么问题，以及应该先看哪一类内容。它本身不承载业务逻辑，主要负责把“如何用 SDK”和“如何写扩展”两条学习路径分开。

## 它暴露/定义了什么
它定义的是文档结构，而不是运行时 API。当前片段里明确暴露了两类内容：`sdk/` 目录，面向 `createAgentSession()` 的程序化使用；`extensions/` 目录，展示生命周期事件、工具拦截、自定义工具、命令与快捷键、自定义 UI、Git 集成、系统提示词修改、外部集成和自定义 provider 等扩展能力。它还给出三个继续深入的入口：`sdk/README.md`、`../docs/extensions.md`、`../docs/skills.md`。另外，从目录列表可以看出 `rpc-extension-ui.ts` 也是 examples 下的一个示例文件，但当前 README 没有专门展开它。

## 谁调用它
根据当前片段推断，直接“调用”它的不是代码，而是人和上层文档：开发者在浏览 `packages/coding-agent/README.md` 或进入 `packages/coding-agent/examples/` 时会先读到它；文档站点或仓库浏览器也可能把它当作 examples 目录首页。它更像一个索引节点，而不是被程序 import 的模块。

## 它调用谁
它不调用任何运行时代码，只通过相对链接把读者带到后续文档。它把注意力导向 `sdk/`、`extensions/` 以及上层的 `docs/extensions.md`、`docs/skills.md`，相当于一个分流器：先选学习主题，再进入更具体的示例或说明。

## 核心流程
阅读路径非常直接：先看 README 判断 examples 下有哪些主题；如果要做自动化或集成，就进入 `sdk/`；如果要扩展编辑器行为、工具、UI 或外部系统，就进入 `extensions/`；如果要理解扩展与技能的边界，再回到相关 docs。它的价值在于把抽象能力拆成可探索的入口，减少读者在大仓库里盲找。

## 关键函数的高层作用
这个文件没有函数定义，核心作用体现在文档条目本身：`sdk/` 负责说明如何通过 `createAgentSession()` 启动和管理会话；`extensions/` 负责展示如何挂接事件、工具、命令、UI 和外部服务；`SDK Reference`、`Extensions Documentation`、`Skills Documentation` 则是三条更权威的延伸路径。换句话说，README 的“关键函数”不是代码函数，而是这些跳转入口的组织作用。

## 修改风险
这类文件改动风险不在编译，而在认知偏差。最常见的问题是：目录结构改了但 README 没同步，导致链接失效或学习路径过时；或者把示例分类改得太碎，读者找不到入口。另一个风险是过度概括，弱化了 `sdk` 和 `extensions` 的边界，容易让新读者误以为所有示例都能互相替代。若后续新增示例文件，最好同步更新这个索引页，否则它会很快失去导航价值。
