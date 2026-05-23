# 目录：src/server/routers/lambda/__tests__/integration

## 它负责什么

这个目录是 `src/server/routers/lambda` 下的集成测试集合，重点验证的是 Lambda router 相关功能的“完整调用链路”，而不是单个函数的局部行为。根据当前片段推断，它主要覆盖 `Router -> Service -> Model -> Database` 这一层级的联动，关注点是参数在链路中是否正确传递、数据库约束是否生效、事务是否完整，以及真实业务流程在多模块协作下是否仍然成立。

和同级的普通单元测试相比，这里更偏向“场景验证”。从文件命名看，覆盖面集中在 `message`、`topic`、`task`、`agentEval`、`agentSkills`、`agentDocumentVfs`、`aiAgent` 这些业务域，说明它更像是 Lambda router 的关键路径回归层。

## 直接子目录地图

这个目录下真正的直接子目录不多，主要是两块：

1. `aiAgent/`  
   这是最核心的子树，专门放 `aiAgent` 相关集成测试和公共辅助函数。里面能看到 `execAgent.integration.test.ts`、`execAgents.integration.test.ts`、`execGroupAgent.integration.test.ts`、`multiRoundTools.integration.test.ts`、`aiAgent.createClientTaskThread.integration.test.ts`、`aiAgent.createClientGroupAgentTaskThread.integration.test.ts` 等文件，说明这里关注的是 agent 执行、分组执行、线程创建、多轮工具调用等较复杂流程。

2. `helpers/`  
   目前只看到 `openaiMock.ts`，它的角色是给集成测试提供 OpenAI Responses API 的模拟流，属于跨多个测试文件复用的测试支撑层。

除目录外，根层还放着一批独立的 `.integration.test.ts`，例如 `message.integration.test.ts`、`topic.integration.test.ts`、`task.integration.test.ts`、`agentEval.integration.test.ts`、`agentSkills.integration.test.ts`、`agentDocumentVfs.integration.test.ts`、`agentEval.run.integration.test.ts`。这些更像按业务域拆开的入口测试文件。

## 关键入口

这个目录里最像“入口”的文件有四类：

- `README.md`：说明这个目录的测试目标、集成测试概念、运行方式和编写原则。它是理解目录定位的第一站。
- `setup.ts`：提供集成测试通用上下文与测试数据构造函数，比如 `createTestContext`、`createTestUser`、`createTestAgent`、`createTestTopic`、`cleanupTestUser`。
- `aiAgent/helpers.ts`：提供 agent 场景专用辅助能力，比如等待操作完成的轮询函数、`FILE_SERVICE_MOCK`、以及 OpenAI Responses 流的 mock 构造器。
- `helpers/openaiMock.ts`：从命名看属于更底层的流式接口 mock，通常会被 `aiAgent` 或其他涉及模型响应流的测试直接复用。

如果把它当成测试体系的入口，这几个文件分别对应“说明文档、通用夹具、领域夹具、协议 mock”。

## 主流程位置

主流程并不在这个目录内部实现，而是被这些测试所驱动。真正的业务主链路在上层 router 文件里，例如 `src/server/routers/lambda/aiAgent.ts`、`message.ts`、`topic.ts`、`task.ts`、`agentEval.ts`、`agentSkills.ts`、`agentDocument.ts`、`session.ts`、`agent.ts` 等。

从当前测试文件名看，几个关键流程位置大致是：

- `aiAgent/*`：覆盖 agent 运行、分组执行、线程创建、多轮工具回合。
- `message.integration.test.ts`、`topic.integration.test.ts`：覆盖消息与主题的核心写入/读取链路。
- `task.integration.test.ts`、`agentEval.integration.test.ts`、`agentEval.run.integration.test.ts`：覆盖任务与评估执行链路。
- `agentSkills.integration.test.ts`、`agentDocumentVfs.integration.test.ts`：覆盖技能与文档虚拟文件系统相关链路。

所以这里的“主流程位置”不是业务逻辑本身，而是把业务逻辑串起来做端到端验证的观察点。

## 推荐阅读顺序

1. 先读 `README.md`，确认这个目录想验证什么、为什么要做集成测试。
2. 再读 `setup.ts`，弄清楚通用上下文、测试用户、测试 agent/topic 的创建和清理方式。
3. 接着读 `helpers/openaiMock.ts` 和 `aiAgent/helpers.ts`，理解流式响应与 agent 场景的通用 mock。
4. 然后按业务域看根层测试文件：先 `message`、`topic`、`task`，再到 `agentEval`、`agentSkills`、`agentDocumentVfs`。
5. 最后进入 `aiAgent/` 子目录，因为那里是流程最复杂、辅助函数最多、也最容易暴露集成问题的地方。

## 常见误区

1. 把这里当成单元测试目录。这里更适合看“真实链路是否通”，不是看某个函数分支是否覆盖完整。
2. 只看测试断言，不看 `setup.ts`。很多上下文构造和清理逻辑都在这里，漏看会误判测试意图。
3. 忽略 `aiAgent/helpers.ts` 这种共享辅助文件。它往往定义了测试里最关键的等待机制和流式 mock。
4. 以为 `README.md` 的结构示意就是当前真实目录。根据当前片段推断，README 里还保留了旧式的 `tests/integration/routers/` 说明，和现有文件布局不完全一致，阅读时要以实际文件树为准。
5. 只关注成功路径，不看超时、终止态、mock 流和数据库清理。集成测试真正容易出问题的，通常正是这些边界条件。
