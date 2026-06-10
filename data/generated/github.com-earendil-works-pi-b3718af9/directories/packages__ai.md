# 目录：packages/ai

## 它负责什么

根据当前片段推断，目标目录 `packages/ai` 在本次可读工作区中未能定位到，因此无法可靠展开它的真实源码职责、模块边界和内部调用流程。任务给出的仓库根目录是 `/data/project/AIWIKI/data/repos/github.com-earendil-works-pi-b3718af9/source`，目标相对路径是 `packages/ai`，但在当前执行环境里进入该根目录后，实际工作目录落在 `/data`，并且对 `packages/ai`、`packages/ai/package.json` 的读取均未命中。

因此，本篇文档不能把 `packages/ai` 解释为某个具体实现目录，也不能臆测它包含哪些 provider、model、client、streaming、schema 或生成脚本。唯一可以确定的是：按照仓库约定和 `AGENTS.md` 中的规则，`packages/ai` 很可能是 monorepo 中负责 AI 模型抽象、模型元数据、调用封装或与上层 agent/coding-agent 通信的包；但这是根据任务路径命名和开发规则推断，不是来自源码内容的确认。

如果后续工作区恢复到正确仓库根目录，建议重新读取 `packages/ai/package.json`、`packages/ai/src`、`packages/ai/test` 和相邻包对它的引用，再生成正式源码地图。

## 直接子目录地图

当前没有足够证据列出 `packages/ai` 的真实直接子目录。

从任务目标和仓库规则可以看出，`packages/ai` 被视为一个独立 package，因为规则中多次出现 `packages/ai/src/models.generated.ts`、`packages/ai/scripts/generate-models.ts` 这类路径。这说明该目录至少在预期仓库中应包含：

- `src`：根据路径规则推断，这是主要源码目录。`models.generated.ts` 位于这里，说明模型清单或模型能力表可能作为生成产物进入运行时代码。
- `scripts`：根据路径规则推断，包含模型数据生成脚本。规则明确要求不要直接改 `src/models.generated.ts`，而要更新 `scripts/generate-models.ts` 后再重新生成。
- 可能存在 `test`：根据 monorepo 常见结构和命令规则推断，包级测试通常会放在 package 内部，但当前片段没有直接证据。
- 可能存在 `CHANGELOG.md`：仓库规则说明每个 `packages/*` 下有 changelog，因此 `packages/ai/CHANGELOG.md` 很可能存在，用于记录该包的 `[Unreleased]` 变更。

以上都是根据当前片段推断，依据是仓库级规则中出现的固定路径和包管理约定，而不是对目标目录的成功读取。

## 关键入口

当前无法确认 `packages/ai` 的真实导出入口。

正常情况下，一个 TypeScript package 的关键入口应首先从 `packages/ai/package.json` 判断，例如 `exports`、`main`、`types`、`scripts`、`dependencies` 和 `devDependencies`。这一步在当前环境中未成功读取，因此不能确认它是否导出 `src/index.ts`、是否有子路径导出、是否面向 ESM、是否依赖特定 SDK，也不能确认它的公共 API 名称。

根据现有规则能确认的一点是：`packages/ai/src/models.generated.ts` 不应被视为人工维护入口。它更像是生成文件，真实维护入口应是 `packages/ai/scripts/generate-models.ts`。如果调用方需要模型列表或模型能力，运行时代码可能间接消费 `models.generated.ts`；但开发者修改模型源数据时，应走生成脚本，而不是手改生成结果。

因此，当前可写成源码学习入口的只有：

- `packages/ai/package.json`：恢复可读后应优先查看，用来确认包名、导出面、构建脚本和依赖边界。
- `packages/ai/src`：恢复可读后应查看目录索引，用来确认运行时代码组织。
- `packages/ai/scripts/generate-models.ts`：根据规则推断，这是模型元数据生成链路的维护入口。
- `packages/ai/src/models.generated.ts`：根据规则推断，这是生成产物，适合阅读结构，不适合直接修改。

## 主流程位置

当前无法给出 `packages/ai` 的确定主流程位置，因为源码目录没有成功读取。

根据路径命名和仓库规则，主流程可能分为两类：

第一类是运行时 AI 调用流程。它通常会从 `packages/ai` 的公开导出进入，向上服务 `packages/agent`、`packages/coding-agent` 或 TUI 层。若该包确实承担 AI 适配职责，主流程一般会围绕“选择模型、构造请求、发送到 provider、处理流式响应、统一错误和 token/usage 信息”展开。具体入口必须以 `package.json` 的 `exports` 和 `src` 下的实际文件为准。

第二类是模型元数据生成流程。这里有较强证据：仓库规则明确提到 `packages/ai/scripts/generate-models.ts` 和 `packages/ai/src/models.generated.ts`，并要求修改模型信息时先改生成脚本再再生生成文件。这说明模型数据不是单纯手写维护，而是由脚本统一生成。该流程的主线大概率是：生成脚本读取上游或内置模型定义，规范化成项目内类型，再输出到 `src/models.generated.ts`，最后被运行时代码导入使用。

需要注意，这两类流程的具体函数名、类型名和调用顺序当前都不能确认。正式阅读时，应避免直接从文件名猜实现，应从导出入口和调用方引用反向验证。

## 推荐阅读顺序

1. 先读 `packages/ai/package.json`，确认它在 monorepo 中的包名、导出入口、构建方式和依赖范围。不要先从某个深层实现文件开始，否则容易把内部辅助模块误认为公共 API。

2. 再看 `packages/ai/src` 的一级结构，识别哪些文件是公共入口，哪些是 provider 实现、模型数据、类型定义、请求封装或工具函数。overview 深度只需要建立地图，不需要逐文件展开。

3. 接着查上层调用方如何使用该包，例如搜索对包名或 `packages/ai` 导出符号的引用。这样可以把 `packages/ai` 的职责放回整体系统：它是被 agent 层调用，还是也被 CLI/TUI 直接调用。

4. 然后阅读 `packages/ai/scripts/generate-models.ts` 和 `packages/ai/src/models.generated.ts`。前者看维护逻辑，后者看生成后的数据形态。重点理解“模型信息从哪里来、如何转成内部结构、运行时如何消费”。

5. 最后看测试或 changelog。如果存在 `packages/ai/test`，优先读覆盖主流程的测试；如果存在 `packages/ai/CHANGELOG.md`，可以快速了解该包近期变动集中在 provider、模型列表、错误处理还是 API 形态。

## 常见误区

一个常见误区是把 `packages/ai/src/models.generated.ts` 当作普通源码维护。仓库规则已经明确要求不要直接修改它，而要修改 `packages/ai/scripts/generate-models.ts` 并重新生成。阅读时可以把生成文件当作数据结构样本，但开发时不应把它当作源头。

另一个误区是只看 `packages/ai` 内部，不看调用方。AI 包通常是基础能力层，真正的业务语义可能在 `packages/agent`、`packages/coding-agent` 或 TUI 层。只读 AI 包内部，容易误判某些抽象为什么存在，也容易看不出哪些 API 是稳定边界。

还要避免从目录名直接推断 provider 行为。即使目录叫 `ai`，它也不一定直接封装所有外部模型服务；也可能只维护模型元数据、统一类型、token 估算、消息格式转换，具体请求执行在其他包中完成。当前片段证据不足，不能下结论。

最后，不要在 overview 阶段逐个叶子文件解释。`packages/ai` 如果是一个较大的基础包，学习重点应是边界：公共入口在哪里、生成文件从哪里来、上层如何调用、模型和 provider 信息如何流动。等这些主线清楚后，再进入具体实现文件会更有效。
