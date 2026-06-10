# 目录：packages/agent

## 它负责什么

从目录树看，`packages/agent` 是这个仓库里专门承载“代理执行层”和“代理运行环境”的包。它不是单纯的工具集合，而是把一次 agent 会话如何启动、如何循环处理消息、如何接入 harness、如何做环境隔离和测试支撑，都放在同一个包里。根据当前片段推断，它更像一个可复用的核心运行时：上层给它输入 prompt、消息流或代理配置，它负责把这些输入变成可执行的 agent loop，并通过 harness 和类型定义把运行过程组织起来。

这里同时包含运行时代码、测试、文档和变更记录，说明这个包既面向库内调用，也面向开发者理解和验证其行为。

## 直接子目录地图

- `packages/agent/src`：主实现区，放核心运行逻辑、对外入口和 harness 相关代码。
- `packages/agent/src/harness`：代理测试与运行支架的主体实现区，内部又分成 `compaction`、`env`、`session`、`utils` 等子目录，说明这里处理会话状态、环境抽象、压缩/截断和辅助工具。
- `packages/agent/test`：测试区，覆盖主 loop、harness、系统提示词、技能、存储、会话等行为。
- `packages/agent/test/harness`：harness 专项测试，说明 harness 是这个包的核心复杂区之一。
- `packages/agent/test/scratch`：临时或实验性脚本目录，通常用于快速验证。
- `packages/agent/test/utils`：测试辅助函数。
- `packages/agent/docs`：包内文档，按主题拆分为 `agent-harness.md`、`durable-harness.md`、`hooks.md`、`observability.md`，说明这里不仅实现功能，还刻意记录了使用方式、持久化策略、扩展钩子和可观测性。
  
如果只看目录结构，这个包的知识重心明显集中在 `src/harness` 和 `test/harness`，而不是某个单一入口文件。

## 关键入口

按文件名和常见组织方式判断，关键入口主要有这些：

- `packages/agent/src/index.ts`：对外导出入口，通常是包级 API 的汇总点。
- `packages/agent/src/agent.ts`：代理对象或代理核心能力的主定义处。
- `packages/agent/src/agent-loop.ts`：一次代理运行的主循环位置，通常这里会串起消息读取、模型调用、结果处理与下一轮推进。
- `packages/agent/src/node.ts`：Node 侧入口，可能负责把包接到命令行、Node 运行时或宿主环境上。
- `packages/agent/src/proxy.ts`：代理层封装或转发入口，常见于把外部调用转成内部统一接口。
- `packages/agent/src/harness/agent-harness.ts`：harness 的中枢入口，负责把 agent 和环境、会话、模板、系统提示词拼起来。

`packages/agent/package.json` 也是重要入口，因为它决定该包暴露哪些导出、如何构建、测试和运行。

## 主流程位置

主流程大概率分成三层：

1. 入口装配层  
   `src/index.ts`、`src/node.ts`、`src/proxy.ts` 负责把外部调用引进来，做环境适配与接口汇总。

2. 代理执行层  
   `src/agent.ts`、`src/agent-loop.ts` 是核心执行链。根据命名推断，这里负责代理状态管理、消息回合推进、调用模型或工具后的结果回收，以及终止条件判断。

3. Harness 编排层  
   `src/harness/agent-harness.ts`、`src/harness/system-prompt.ts`、`src/harness/prompt-templates.ts`、`src/harness/messages.ts`、`src/harness/skills.ts`、`src/harness/types.ts` 组成支撑层。它们共同决定提示词怎么拼、消息怎么表示、技能怎么注入、会话结构怎么描述。`src/harness/compaction`、`env`、`session`、`utils` 则对应更细的运行辅助能力。

从测试分布也能反推主流程：`test/agent-loop.test.ts`、`test/agent.test.ts`、`test/harness/*.test.ts` 说明最关键的行为都围绕 loop、harness 和会话模型展开。

## 推荐阅读顺序

1. 先看 `packages/agent/README.md`，建立这个包的用途和术语边界。
2. 再看 `packages/agent/package.json`，确认它的导出面、脚本和构建目标。
3. 接着看 `packages/agent/src/index.ts`、`packages/agent/src/agent.ts`、`packages/agent/src/agent-loop.ts`，把主流程串起来。
4. 然后看 `packages/agent/src/harness/agent-harness.ts`、`packages/agent/src/harness/types.ts`、`packages/agent/src/harness/system-prompt.ts`，理解运行支架。
5. 最后看 `packages/agent/test/agent-loop.test.ts` 和 `packages/agent/test/harness/*.test.ts`，用测试反推设计意图。
6. 如果关心扩展和运维，再补 `packages/agent/docs/observability.md`、`hooks.md`、`durable-harness.md`。

## 常见误区

- 容易把它当成“只有一个 agent 实现文件”的小包，但从目录看它实际上是一个完整运行时，包含 harness、会话、环境、测试和文档。
- 容易只读 `src/agent.ts`，忽略 `src/agent-loop.ts`。真正的行为推进通常在 loop 层，`agent.ts` 更像对象与状态边界。
- 容易忽略 `src/harness`，但这里很可能才是可配置点最多的地方，尤其是 system prompt、模板、技能和会话处理。
- 容易把 `test/scratch` 误认为正式逻辑。它更像临时验证区，不适合当稳定 API 依据。
- 容易只看实现不看测试。这个包的测试很分散，说明它的行为契约主要靠测试固定，尤其是 harness 和 compaction 相关路径。

根据当前片段推断，这个目录最重要的理解方式不是逐文件背诵，而是先抓住 `agent-loop` 的执行链，再看 `harness` 如何把输入、上下文和环境组装成可运行会话。
