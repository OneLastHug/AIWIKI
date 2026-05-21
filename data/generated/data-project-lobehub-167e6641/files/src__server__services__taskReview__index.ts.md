# 文件：src/server/services/taskReview/index.ts

## 文件职责
这个文件位于 `src/server/services/taskReview`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { DEFAULT_SYSTEM_AGENT_CONFIG } from '@lobechat/const';
import { evaluate, type EvaluateResult, type RubricResult } from '@lobechat/eval-rubric';
import type { EvalBenchmarkRubric } from '@lobechat/types';
import debug from 'debug';
import { UserModel } from '@/database/models/user';
import type { LobeChatDatabase } from '@/database/type';
import { initModelRuntimeFromDB } from '@/server/modules/ModelRuntime';
export interface ReviewConfig {
export interface ReviewJudge {
export interface ReviewResult {
export class TaskReviewService {
```

## 主要对外内容
```text
const log = debug('task-review');
export interface ReviewConfig {
export interface ReviewJudge {
export interface ReviewResult {
export class TaskReviewService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { DEFAULT_SYSTEM_AGENT_CONFIG } from '@lobechat/const';
import { evaluate, type EvaluateResult, type RubricResult } from '@lobechat/eval-rubric';
import type { EvalBenchmarkRubric } from '@lobechat/types';
import debug from 'debug';

import { UserModel } from '@/database/models/user';
import type { LobeChatDatabase } from '@/database/type';
import { initModelRuntimeFromDB } from '@/server/modules/ModelRuntime';

const log = debug('task-review');

export interface ReviewConfig {
  autoRetry: boolean;
  enabled: boolean;
  judge: ReviewJudge;
  maxIterations: number;
  rubrics: EvalBenchmarkRubric[];
}

export interface ReviewJudge {
  model?: string;
  prompt?: string;
  provider?: string;
}

export interface ReviewResult {
  iteration: number;
  overallScore: number;
  passed: boolean;
  rubricResults: RubricResult[];
  suggestions: string[];
}

export class TaskReviewService {
  private db: LobeChatDatabase;
  private userId: string;

  constructor(db: LobeChatDatabase, userId: string) {
    this.db = db;
    this.userId = userId;
  }

  async review(params: {
    content: string;
    iteration?: number;
    judge: ReviewJudge;
    rubrics: EvalBenchmarkRubric[];
    taskName: string;
  }): Promise<ReviewResult> {
    const { content, rubrics, judge, taskName, iteration = 1 } = params;

    // 1. Resolve model/provider
    const { model, provider } = await this.resolveModelConfig(judge);

    log(
      'Starting review for task %s (iteration %d, model=%s, provider=%s, rubrics=%d)',
      taskName,
      iteration,
      model,
      provider,
      rubrics.length,
    );

    // 2. Initialize ModelRuntime for LLM-based rubrics
    const modelRuntime = await initModelRuntimeFromDB(this.db, this.userId, provider);

    // 3. Run evaluate() from @lobechat/eval-rubric
    const result: EvaluateResult = await evaluate(
      {
        actual: content,
        rubrics,
        testCase: { input: taskName },
      },
      {
        matchContext: {
          generateObject: async (payload) => {
            return (modelRuntime as any).generateObject(
              {
                messages: payload.messages as any[],
                model: payload.model || model,
                schema: { name: 'judge_score', schema: payload.schema },
              },
              { metadata: { trigger: 'task-review' } },
            );
          },
          judgeModel: model,
        },
        passThreshold: 0.6,
      },
    );

    log('Review complete: %s (score: %.2f, passed: %s)', taskName, result.score, result.passed);

    return {
      iteration,
      overallScore: Math.round(result.score * 100),
      passed: result.passed,
      rubricResults: result.rubricResults,
      suggestions: [],
    };
  }

  private async resolveModelConfig(
    judge: ReviewJudge,
  ): Promise<{ model: string; provider: string }> {
    if (judge.model && judge.provider) {
      return { model: judge.model, provider: judge.provider };
    }

    const userModel = new UserModel(this.db, this.userId);
    const settings = await userModel.getUserSettings();
    const systemAgent = settings?.systemAgent as Record<string, any> | undefined;
    const topicConfig = systemAgent?.topic;
    const defaults = DEFAULT_SYSTEM_AGENT_CONFIG.topic;

    return {
      model: judge.model || topicConfig?.model || defaults.model,
      provider: judge.provider || topicConfig?.provider || defaults.provider,
    };
  }
}

```
