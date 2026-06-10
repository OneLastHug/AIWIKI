# 文件：packages/agent/src/index.ts
## 一句话定位
这是 `@earendil-works/pi-agent-core` 的统一入口文件，本身几乎不承载业务逻辑，主要职责是把分散在 `agent.ts`、`agent-loop.ts`、`harness/*`、`proxy.ts`、`types.ts` 等模块里的能力汇总成对外稳定的公共 API。

## 它暴露/定义了什么
它没有定义新的运行时逻辑，而是集中做 re-export。对外暴露的内容可以分成几层：核心 Agent 能力（`./agent.ts`）、循环执行能力（`./agent-loop.ts`）、测试和运行时支架（`./harness/agent-harness.ts` 以及 `messages.ts`、`prompt-templates.ts`、`session/*`、`skills.ts`、`system-prompt.ts`、`utils/*`）、压缩与分支摘要相关工具（`compaction/*`）、代理工具（`proxy.ts`）以及类型定义（`types.ts`）。其中 `uuidv7` 是明确点名导出的实用函数，其余大多是整模块透出。

## 谁调用它
根据当前片段推断，它主要被三类调用方使用。第一类是外部用户，通过包名 `@earendil-works/pi-agent-core` 直接导入。第二类是仓库内的上层包，尤其是 `packages/coding-agent`，仓库里大量示例、测试和源码都直接从这个包名导入。第三类是构建和发布链路，`tsconfig.json` 里把 `@earendil-works/pi-agent-core` 映射到 `packages/agent/src/index.ts`，所以内部 TypeScript 也会把这里当成解析入口。

## 它调用谁
它本身不执行业务调用，但通过 export 关系把下游模块接到公共 API 上。也就是说，真实的逻辑入口在 `agent.ts`、`agent-loop.ts`、`harness/compaction/compaction.ts`、`harness/session/session.ts` 等文件中；`index.ts` 只是把这些实现汇总后重新对外输出。

## 核心流程
整体流程很简单：消费者只要从包根部导入，就能拿到完整的 Agent 能力集合，而不用记住内部目录结构。这样做的实际效果是把“运行时 Agent”“会话与持久化”“上下文压缩”“技能与提示词”“代理与类型”这些能力统一成一个边界。对上层来说，入口文件就是稳定契约；对下层来说，具体实现仍然分散在各自职责明确的模块里。

## 关键函数的高层作用
这里没有独立实现函数，重点是被转出的关键 API。`collectEntriesForBranchSummary`、`generateBranchSummary`、`prepareBranchEntries` 负责分支摘要准备与生成；`calculateContextTokens`、`estimateTokens`、`compact`、`shouldCompact`、`prepareCompaction` 等负责上下文评估与压缩决策；`serializeConversation` 把会话序列化为可处理结构；`findCutPoint`、`findTurnStartIndex`、`getLastAssistantUsage` 属于压缩流程中的定位辅助；`uuidv7` 则提供会话或实体的唯一标识生成。辅助模块如 `messages.ts`、`session/*`、`utils/truncate.ts` 更偏基础设施，一般直接服务于这些核心流程。

## 修改风险
这个文件是公共 API 汇总点，改动风险主要在“破坏面”而不是“算法面”。新增、删除或改名任何 export，都可能直接影响 `packages/coding-agent`、示例、测试和外部使用者。因为它承担入口职责，哪怕只是调整导出方式，也可能影响类型可见性、文档示例、打包产物和树摇结果。若后续要动这里，优先核对 `packages/agent/package.json`、`tsconfig.json` 的路径映射，以及仓库内所有 `@earendil-works/pi-agent-core` 的消费点，避免把一个稳定入口改成了隐性断点。
