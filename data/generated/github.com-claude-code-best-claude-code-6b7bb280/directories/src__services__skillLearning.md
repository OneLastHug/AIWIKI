# 目录：src/services/skillLearning

## 它负责什么
这个目录负责一套“从使用过程里学习”的闭环服务。根据当前片段推断，它会从 REPL 会话、工具事件和项目上下文中收集观察，再把这些观察归纳成 `instinct`，进一步聚类、生成可落地的技能产物，最后按生命周期规则决定是创建、合并、替换、归档还是删除。

它不是单一算法模块，而是一组围绕技能学习的基础设施：有特征开关、配置、观察存储、后端注册、会话级分析、运行时编排、技能生成、命令/agent 生成，以及从 project scope 推广到 global scope 的逻辑。

## 直接子目录地图
这个目录下，当前可见的直接子目录只有 `__tests__`。也就是说，它本身不是一个再往下分层的业务树，而是一个以文件为主的服务目录，逻辑主要集中在同级 `.ts` 文件里。

`__tests__` 里覆盖了核心链路的单测和烟雾测试，能看到的测试重点包括 `runtimeObserver`、`promotion`、`observationStore`、`sessionObserver`、`evolution`、`skillLifecycle`、`learningPolicy`、`instinctStore`、`skillGenerator`、`toolEventObserver`、`skillGapStore`、`observerBackend` 等。这个结构说明目录的边界比较清晰：代码和测试都围绕同一条学习流水线展开。

## 关键入口
真正的聚合入口是 `index.ts`。它几乎不做业务计算，只负责把外部会用到的能力统一 re-export 出去，例如 `featureCheck`、`evolution`、`instinctParser`、`learningPolicy`、`instinctStore`、`observationStore`、`promotion`、`runtimeObserver`、`observerBackend`、`skillGenerator`、`skillLifecycle` 等。对调用方来说，`index.ts` 就是这个目录的门面。

如果看运行时入口，最关键的是 `runtimeObserver.ts`。这里定义了 `initSkillLearning()`、`runSkillLearningPostSampling()`、`resetRuntimeObserverForTest()` 等函数，负责把学习系统挂到后采样钩子上，并在启动时做一次后台维护。

如果看开关入口，`featureCheck.ts` 是门禁：`isSkillLearningCompiledIn()` 判断编译期是否包含 `/skill-learning`，`isSkillLearningEnabled()` 判断运行时是否真正开启。

## 主流程位置
主流程基本可以按“采集 -> 分析 -> 生成 -> 落盘 -> 推广”来读：

1. `runtimeObserver.ts` 先做初始化，调用 `registerPostSamplingHook()` 挂接运行时钩子，并在启动时触发清理和衰减维护。
2. 同一个文件里的 `runSkillLearningPostSampling()` 会从 `context.messages` 和 `observationStore` 里拼出新观察，再根据阈值决定走 LLM 后端还是启发式后端。
3. `sessionObserver.ts` 提供启发式分析逻辑，把观察转成 `InstinctCandidate`，并在模块加载时注册 `heuristicObserverBackend`、`llmObserverBackend`。
4. `observerBackend.ts` 维护后端注册表和活动后端选择，支持通过环境变量切换默认分析器。
5. `evolution.ts` 负责把 `instinct` 聚类，并分类成 `skill`、`command` 或 `agent` 候选。
6. `skillGenerator.ts`、`commandGenerator.ts`、`agentGenerator.ts` 负责把候选写成具体产物。
7. `skillLifecycle.ts` 决定与现有技能的关系：创建、合并、替换、归档、删除，同时处理搜索索引和替换清单。
8. `promotion.ts` 负责把项目级 `instinct` 提升为全局级 `instinct`，这是从局部经验走向共享经验的出口。

## 推荐阅读顺序
建议按下面顺序看，会比较顺：

1. `types.ts`，先搞清楚 `SkillObservation`、`Instinct`、`LearnedSkillDraft`、项目上下文这些核心数据结构。
2. `featureCheck.ts`，理解这个子系统什么时候编译进来、什么时候真正运行。
3. `index.ts`，确认对外导出的能力边界。
4. `observerBackend.ts` 和 `sessionObserver.ts`，看分析器是怎么注册和切换的。
5. `runtimeObserver.ts`，这是整条链路的总编排。
6. `evolution.ts`、`skillGenerator.ts`、`skillLifecycle.ts`、`promotion.ts`，分别看“怎么归纳”“怎么生成”“怎么处理生命周期”“怎么升级到全局”。

## 常见误区
最常见的误区是把这个目录当成“只有技能生成器”。实际上它同时处理观察采集、后端分析、启发式识别、生命周期管理和推广，职责比单一生成器宽得多。

另一个误区是忽略运行时门禁。`featureCheck.ts` 里编译期开关和运行期开关不是一回事，`SKILL_LEARNING_ENABLED`、`FEATURE_SKILL_LEARNING`、构建期 `feature('SKILL_LEARNING')` 各有作用。

还有两点容易看错：一是 `sessionObserver.ts` 不只是“会话观察”，它还承担默认后端注册；二是 `promotion.ts` 不只是保存文件，它是在项目级与全局级之间做阈值筛选和升级。

最后，`__tests__` 不是附属说明，而是理解主流程的好入口。这个目录的测试覆盖面很集中，读测试常常比逐个翻实现更快看清学习链路的边界。
