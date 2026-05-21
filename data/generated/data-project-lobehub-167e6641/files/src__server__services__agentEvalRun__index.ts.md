# 文件：src/server/services/agentEvalRun/index.ts

## 文件职责
这个文件位于 `src/server/services/agentEvalRun`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { LOADING_FLAT } from '@lobechat/const';
import { type LobeChatDatabase } from '@lobechat/database';
import { evaluate } from '@lobechat/eval-rubric';
import type {
import { RequestTrigger } from '@lobechat/types';
import debug from 'debug';
import {
import { MessageModel } from '@/database/models/message';
import { ThreadModel } from '@/database/models/thread';
import { TopicModel } from '@/database/models/topic';
import { AgentService } from '@/server/services/agent';
import { AgentRuntimeService } from '@/server/services/agentRuntime/AgentRuntimeService';
import { AiAgentService } from '@/server/services/aiAgent';
import {
export class AgentEvalRunService {
```

## 主要对外内容
```text
const roundCost = (v: number): number => Math.round(v * 1e6) / 1e6;
const EVAL_AGENT_RUNTIME_QSTASH_RETRIES = 10;
const EVAL_AGENT_RUNTIME_QSTASH_RETRY_DELAY = '10000 * (1 + retried)';
const RESUMABLE_THREAD_STATUSES = new Set(['error', 'timeout']);
const log = debug('lobe-server:eval-run-service');
interface ResumableCaseTarget {
interface ResumableThreadResult extends EvalThreadResult {
const getThreadResultStatus = (
const resetResumedThreadResult = (thread: EvalThreadResult): EvalThreadResult => ({
export class AgentEvalRunService {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { LOADING_FLAT } from '@lobechat/const';
import { type LobeChatDatabase } from '@lobechat/database';
import { evaluate } from '@lobechat/eval-rubric';
import type {
  EvalBenchmarkRubric,
  EvalRunAgentSnapshot,
  EvalRunConfig,
  EvalRunInputConfig,
  EvalRunMetrics,
  EvalRunTopicResult,
  EvalThreadResult,
  RubricType,
} from '@lobechat/types';
import { RequestTrigger } from '@lobechat/types';
import debug from 'debug';

import {
  AgentEvalBenchmarkModel,
  AgentEvalDatasetModel,
  AgentEvalRunModel,
  AgentEvalRunTopicModel,
  AgentEvalTestCaseModel,
} from '@/database/models/agentEval';
import { MessageModel } from '@/database/models/message';
import { ThreadModel } from '@/database/models/thread';
import { TopicModel } from '@/database/models/topic';
import { AgentService } from '@/server/services/agent';
import { AgentRuntimeService } from '@/server/services/agentRuntime/AgentRuntimeService';
import { AiAgentService } from '@/server/services/aiAgent';
import {
  AgentEvalRunWorkflow,
  type ResumeAgentTrajectoryPayload,
  type ResumeThreadTrajectoryPayload,
} from '@/server/workflows/agentEvalRun';

/** Round cost to at most 6 decimal places to avoid floating-point noise */
const roundCost = (v: number): number => Math.round(v * 1e6) / 1e6;
const EVAL_AGENT_RUNTIME_QSTASH_RETRIES = 10;
const EVAL_AGENT_RUNTIME_QSTASH_RETRY_DELAY = '10000 * (1 + retried)';
const RESUMABLE_THREAD_STATUSES = new Set(['error', 'timeout']);

const log = debug('lobe-server:eval-run-service');

interface ResumableCaseTarget {
  caseStatus?: string | null;
  input: string;
  resumeStatus?: 'error' | 'timeout';
  sortOrder: number | null;
  testCaseId: string;
  threadId?: string;
}

interface ResumableThreadResult extends EvalThreadResult {
  status: 'error' | 'timeout';
}

const getThreadResultStatus = (
  evalResult: Record<string, unknown>,
): EvalThreadResult['status'] | undefined => {
  const { status } = evalResult;

  if (status === 'completed' || status === 'error' || status === 'external' || status === 'timeout')
    return status;

  if (evalResult.passed === true) return 'passed';
  if (evalResult.passed === false) return 'failed';

  return undefined;
};

const resetResumedThreadResult = (thread: EvalThreadResult): EvalThreadResult => ({
  threadId: thread.threadId,
  status: thread.status === 'external' ? 'external' : 'running',
});

export class AgentEvalRunService {
  private readonly db: LobeChatDatabase;
  private readonly userId: string;
  private readonly runModel: AgentEvalRunModel;
  private readonly benchmarkModel: AgentEvalBenchmarkModel;
  private readonly datasetModel: AgentEvalDatasetModel;
  private readonly runTopicModel: AgentEvalRunTopicModel;
  private readonly testCaseModel: AgentEvalTestCaseModel;
  private readonly messageModel: MessageModel;
  private readonly threadModel: ThreadModel;
  private readonly topicModel: TopicModel;
  private readonly agentService: AgentService;

  constructor(db: LobeChatDatabase, userId: string) {
    this.db = db;
    this.userId = userId;
    this.runModel = new AgentEvalRunModel(db, userId);
    this.benchmarkModel = new AgentEvalBenchmarkModel(db, userId);
    this.datasetModel = new AgentEvalDatasetModel(db, userId);
    this.runTopicModel = new AgentEvalRunTopicModel(db, userId);
    this.testCaseModel = new AgentEvalTestCaseModel(db, userId);
    this.messageModel = new MessageModel(db, userId);
    this.threadModel = new ThreadModel(db, userId);
    this.topicModel = new TopicModel(db, userId);
    this.agentService = new AgentService(db, userId);
  }

  async createRun(params: {
    config?: EvalRunInputConfig;
    datasetId: string;
    name?: string;
    targetAgentId?: string;
  }) {
    const agentSnapshot = params.targetAgentId
      ? await this.snapshotAgentConfig(params.targetAgentId)
      : undefined;

    const config = { ...params.config, agentSnapshot };

    const run = await this.runModel.create({ ...params, config });

    // Pre-create Topics and RunTopics for all test cases (status='pending')
    const testCases = await this.testCaseModel.findByDatasetId(params.datasetId);

    if (testCases.length > 0) {
      const createdTopics = await this.topicModel.batchCreate(
        testCases.map((tc) => ({
          agentId: params.targetAgentId ?? undefined,
          title: `[Eval Case #${(tc.sortOrder ?? 0) + 1}] ${tc.content?.input?.slice(0, 50) || 'Test Case'}...`,
          trigger: RequestTrigger.Eval,
        })),
      );

      await this.runTopicModel.batchCreate(
        createdTopics.map((topic, index) => ({
          runId: run.id,
          status: 'pending' as const,
          testCaseId: testCases[index].id,
          topicId: topic.id,
        })),
      );
    }

    return run;
  }

  async deleteRun(id: string) {
    // 1. Get associated topics before deletion (cascade will remove run_topics rows)
    const runTopics = await this.runTopicModel.findByRunId(id);
    const topicIds = runTopics.map((rt) => rt.topicId).filter(Boolean);

    // 2. Delete the run (cascades to run_topics)
    const result = await this.runModel.delete(id);

    // 3. Delete orphaned topics
    if (topicIds.length > 0) {
      await this.topicModel.batchDelete(topicIds);
    }

    return result;
  }

  async abortRun(runId: string) {
    // 1. Find all running RunTopics and interrupt their agent operations
    const runTopics = await this.runTopicModel.findByRunId(runId);
    const runningTopics = runTopics.filter((t) => t.status === 'running');

    if (runningTopics.length > 0) {
      const agentRuntimeService = new AgentRuntimeService(this.db, this.userId);
      for (const rt of runningTopics) {
        const opId = (rt.evalResult as EvalRunTopicResult)?.operationId;
        if (opId) {
          try {
            await agentRuntimeService.interruptOperation(opId);
          } catch {
            // best effort
          }
        }
      }
    }

    // 2. Mark all pending/running RunTopics as aborted (error + 'Aborted')
    await this.runTopicModel.batchMarkAborted(runId);

    // 3. Update run status to aborted
    await this.runModel.update(runId, { status: 'aborted' });
  }

  async retryErrorCases(runId: string): Promise<{ retryCount: number }> {
    const run = await this.runModel.findById(runId);
    if (!run) throw new Error('Run not found');

    const allTopics = await this.runTopicModel.findByRunId(runId);
    const errorTopics = allTopics.filter((t) => t.status === 'error' || t.status === 'timeout');

    if (errorTopics.length === 0) return { retryCount: 0 };

    // Collect test case IDs and info for recreation
    const errorTestCases = errorTopics.map((t) => ({
      id: t.testCaseId,
      input: t.testCase?.content?.input,
      sortOrder: t.testCase?.sortOrder,
    }));

    // 1. Delete error/timeout RunTopics
    await this.runTopicModel.deleteErrorRunTopics(runId);

    // 2. Delete orphan Topics (old conversations)
    const topicIds = errorTopics.map((t) => t.topicId).filter(Boolean);
    if (topicIds.length > 0) await this.topicModel.batchDelete(topicIds);

    // 3. Create new Topics and pending RunTopics for the error test cases
    const createdTopics = await this.topicModel.batchCreate(
      errorTestCases.map((tc) => ({
        agentId: run.targetAgentId ?? undefined,
        title: `[Eval Case #${(tc.sortOrder ?? 0) + 1}] ${tc.input?.slice(0, 50) || 'Test Case'}...`,
        trigger: RequestTrigger.Eval,
      })),
    );

    await this.runTopicModel.batchCreate(
      createdTopics.map((topic, index) => ({
        runId,
        status: 'pending' as const,
        testCaseId: errorTestCases[index].id,
        topicId: topic.id,
      })),
    );

    // 4. Set run status to pending
    await this.runModel.update(runId, { status: 'pending' });

    return { retryCount: errorTopics.length };
  }

  async retrySingleCase(runId: string, testCaseId: string) {
    const run = await this.runModel.findById(runId);
    if (!run) throw new Error('Run not found');

    const runTopic = await this.runTopicModel.findByRunAndTestCase(runId, testCaseId);
    if (!runTopic) throw new Error('RunTopic not found');

    // 1. Delete old RunTopic
    await this.runTopicModel.deleteByRunAndTestCase(runId, testCaseId);

    // 2. Delete old Topic
    if (runTopic.topicId) {
      await this.topicModel.batchDelete([runTopic.topicId]);
    }

    // 3. Create new Topic
    const [newTopic] = await this.topicModel.batchCreate([
      {
        agentId: run.targetAgentId ?? undefined,
        title: `[Eval Case #${(runTopic.testCase?.sortOrder ?? 0) + 1}] ${runTopic.testCase?.content?.input?.slice(0, 50) || 'Test Case'}...`,
        trigger: RequestTrigger.Eval,
      },
    ]);

    // 4. Create new RunTopic with pending status
    await this.runTopicModel.batchCreate([
      {
        runId,
        status: 'pending' as const,
        testCaseId,
        topicId: newTopic.id,
      },
    ]);

    // 5. Set run status to running
    await this.runModel.update(runId, { status: 'running' });
  }

  async canResumeTrajectory(params: { runId: string; testCaseId: string; threadId?: string }) {
    const invalidResumeTargetReason = 'Invalid resume target';
    const trajectoryNotResumableReason = 'Trajectory is not resumable';
    const resumeLimitReachedReason = 'Resume limit reached';

    log('canResumeTrajectory: %O', params);
    const run = await this.runModel.findById(params.runId);
    if (!run) return { canResume: false, reason: invalidResumeTargetReason };

    if (!['aborted', 'failed', 'running'].includes(run.status)) {
      return { canResume: false, reason: trajectoryNotResumableReason };
    }

    const runTopic = await this.runTopicModel.findByRunAndTestCase(params.runId, params.testCaseId);
    if (!runTopic) return { canResume: false, reason: invalidResumeTargetReason };

    log('canResumeTrajectory: runTopic.status=%s topicId=%s', runTopic.status, runTopic.topicId);

    const k = run.config?.k ?? 1;
    const hasInvalidThreadTarget = (k === 1 && !!params.threadId) || (k > 1 && !params.threadId);
    if (hasInvalidThreadTarget) {
      return { canResume: false, reason: invalidResumeTargetReason };
    }

    if (!runTopic.topicId) {
      return { canResume: false, reason: invalidResumeTargetReason };
    }

    if (k === 1 && !RESUMABLE_THREAD_STATUSES.has(runTopic.status ?? '')) {
      log('canResumeTrajectory: rejected — runTopic.status=%s', runTopic.status);
      return { canResume: false, reason: trajectoryNotResumableReason };
    }

    if (params.threadId) {
      const thread = await this.threadModel.findById(params.threadId);

      if (!thread || thread.topicId !== runTopic.topicId || thread.type !== 'eval') {
        return { canResume: false, reason: invalidResumeTargetReason };
      }

      const targetThread = runTopic.evalResult?.threads?.find(
        (item) => item.threadId === params.threadId,
      );

      if (!targetThread || !RESUMABLE_THREAD_STATUSES.has(targetThread.status ?? '')) {
        return { canResume: false, reason: trajectoryNotResumableReason };
      }

      const maxSteps = run.config?.maxSteps;
      const prevSteps =
        ((thread.metadata as Record<string, unknown> | null)?.steps as number | undefined) ?? 0;

      if (maxSteps && prevSteps >= maxSteps) {
        log(
          'canResumeTrajectory: rejected thread — prevSteps=%d >= maxSteps=%d',
          prevSteps,
          maxSteps,
        );
        return { canResume: false, reason: resumeLimitReachedReason };
      }
    }

    // pass@1 resumes track steps on the runTopic; pass@k uses per-thread metadata above.
    if (k > 1) return { canResume: true as const };

    // Reject if the previous run already exhausted maxSteps
    const maxSteps = run.config?.maxSteps;
    const prevSteps = runTopic.evalResult?.steps ?? 0;
    if (maxSteps && prevSteps >= maxSteps) {
      log('canResumeTrajectory: rejected — prevSteps=%d >= maxSteps=%d', prevSteps, maxSteps);
      return { canResume: false, reason: resumeLimitReachedReason };
    }

    return { canResume: true as const };
  }

  /**
   * Batch-check which error/timeout cases in a run can be resumed.
   * Returns one entry per candidate case with canResume + optional reason.
   */
  async getResumableCases(runId: string) {
    const run = await this.runModel.findById(runId);
    if (!run) return [];

    const allTopics = await this.runTopicModel.findByRunId(runId);
    const k = run.config?.k ?? 1;
    const candidates = allTopics
      .map((topic) => this.getResumableCaseTarget(topic, k))
      .filter((topic): topic is ResumableCaseTarget => !!topic);

    const results = await Promise.all(
      candidates.map(async (candidate) => {
        const check = await this.canResumeTrajectory({
          runId,
          testCaseId: candidate.testCaseId,
          threadId: candidate.threadId,
        });
        return {
          caseStatus: candidate.caseStatus,
          canResume: check.canResume,
          input: candidate.input,
          reason: 'reason' in check ? check.reason : undefined,
          resumeStatus: candidate.resumeStatus,
          sortOrder: candidate.sortOrder,
          testCaseId: candidate.testCaseId,
          threadId: candidate.threadId,
        };
      }),
    );

    return results;
  }

  async resumeTrajectory(params: { runId: string; testCaseId: string; threadId?: string }) {
    log('resumeTrajectory: %O', params);
    const resumeCheck = await this.canResumeTrajectory(params);
    if (!resumeCheck.canResume) {
      log('resumeTrajectory: canResume=false reason=%s', resumeCheck.reason);
      throw new Error(resumeCheck.reason);
    }

    const target = await this.resolveTrajectoryResumeTarget(params);
    const { envPrompt, parentMessageId, run, thread, topicId } = target;
    log(
      'resumeTrajectory: resolved target — topicId=%s parentMessageId=%s threadId=%s',
      topicId,
      parentMessageId,
      thread?.id,
    );

    if (thread) {
      log('resumeTrajectory: triggering resume-thread-trajectory');
      await AgentEvalRunWorkflow.triggerResumeThreadTrajectory({
        appContext: { threadId: thread.id, topicId },
        envPrompt,
        maxSteps: run.config?.maxSteps,
        parentMessageId,
        runId: run.id,
        targetAgentId: run.targetAgentId ?? undefined,
        testCaseId: params.testCaseId,
        threadId: thread.id,
        topicId,
        userId: this.userId,
      });
    } else {
      log('resumeTrajectory: triggering resume-agent-trajectory');
      await AgentEvalRunWorkflow.triggerResumeAgentTrajectory({
        appContext: { topicId },
        envPrompt,
        maxSteps: run.config?.maxSteps,
        parentMessageId,
        runId: run.id,
        targetAgentId: run.targetAgentId ?? undefined,
        testCaseId: params.testCaseId,
        topicId,
        userId: this.userId,
      });
    }

    const result = {
      mode: thread ? ('thread' as const) : ('single' as const),
      runId: run.id,
      testCaseId: params.testCaseId,
      threadId: thread?.id,
      topicId,
      triggered: true,
    };
    log('resumeTrajectory: done %O', result);
    return result;
  }

  private getResumableCaseTarget(
    runTopic: {
      evalResult?: EvalRunTopicResult | null;
      status?: string | null;
      testCase?: { content?: { input?: string } | null; sortOrder?: number | null } | null;
      testCaseId: string;
    },
    k: number,
  ): ResumableCaseTarget | undefined {
    if (k === 1) {
      if (!RESUMABLE_THREAD_STATUSES.has(runTopic.status ?? '')) return undefined;

      return {
        caseStatus: runTopic.status,
        input: runTopic.testCase?.content?.input ?? '',
        resumeStatus: runTopic.status as 'error' | 'timeout',
        sortOrder: runTopic.testCase?.sortOrder ?? null,
        testCaseId: runTopic.testCaseId,
      };
    }

    const resumableThread = this.getResumableThread(runTopic.evalResult?.threads);
    if (!resumableThread?.status) return undefined;

    return {
      caseStatus: runTopic.status,
      input: runTopic.testCase?.content?.input ?? '',
      resumeStatus: resumableThread.status,
      sortOrder: runTopic.testCase?.sortOrder ?? null,
      testCaseId: runTopic.testCaseId,
      threadId: resumableThread.threadId,
    };
  }

  private getResumableThread(threads?: EvalThreadResult[]) {
    return threads?.find((thread): thread is ResumableThreadResult =>
      RESUMABLE_THREAD_STATUSES.has(thread.status ?? ''),
    );
  }

  /**
   * Resume a timed-out single-agent trajectory (pass@1).
   * Claims the runTopic via CAS (timeout → running) for idempotency, then
   * calls execAgent with resume=true so the runtime continues from parentMessageId.
   */
  async executeResumedTrajectory(params: ResumeAgentTrajectoryPayload) {
    const {
      appContext,
      envPrompt,
      maxSteps,
      parentMessageId,
      runId,
      targetAgentId,
      testCaseId,
      topicId,
    } = params;

    const resumeCheck = await this.canResumeTrajectory({ runId, testCaseId });
    if (!resumeCheck.canResume) {
      return { reason: resumeCheck.reason, status: 'cancelled' as const, topicId };
    }

    // Look up the pre-created RunTopic and reset it for resume
    log(
      'executeResumedTrajectory: run=%s testCase=%s topicId=%s parentMessageId=%s',
      runId,
      testCaseId,
      topicId,
      parentMessageId,
    );
    const runTopic = await this.runTopicModel.findByRunAndTestCase(runId, testCaseId);
    if (!runTopic) {
      throw new Error(`RunTopic not found for run=${runId} testCase=${testCaseId}`);
    }

    // Capture accumulated telemetry from previous runs before clearing evalResult
    const prevSteps = runTopic.evalResult?.steps ?? 0;
    const prevCost = runTopic.evalResult?.cost ?? 0;
    const prevLlmCalls = runTopic.evalResult?.llmCalls ?? 0;
    const prevToolCalls = runTopic.evalResult?.toolCalls ?? 0;
    const prevTokens = runTopic.evalResult?.tokens ?? 0;
    log('executeResumedTrajectory: prev telemetry steps=%d cost=%d', prevSteps, prevCost);
    const now = new Date();

    await this.runTopicModel.updateByRunAndTopic(runId, topicId, {
      createdAt: now, // reset for timeout tracking — resume is a fresh time window
      evalResult: null,
      passed: null,
      score: null,
      status: 'running',
    });

    await this.runModel.update(runId, { startedAt: now, status: 'running' });

    const aiAgentService = new AiAgentService(this.db, this.userId);
    const webhookUrl = '/api/workflows/agent-eval-run/on-trajectory-complete';
    const userId = this.userId;
    const db = this.db;

    try {
      const execResult = await aiAgentService.execAgent({
        agentId: targetAgentId,
        appContext,
        autoStart: true,
        trigger: RequestTrigger.Eval,
        hooks: [
          {
            handler: async (event) => {
              // Local mode: directly record completion
              const service = new AgentEvalRunService(db, userId);
              await service.recordTrajectoryCompletion({
                runId,
                status: event.status || event.reason || 'done',
                telemetry: {
                  completionReason: event.reason,
                  cost: (event.cost ?? 0) + prevCost,
                  duration: event.duration,
                  errorDetail: event.errorDetail,
                  errorMessage: event.errorMessage,
                  llmCalls: (event.llmCalls ?? 0) + prevLlmCalls,
                  steps: (event.steps ?? 0) + prevSteps,
                  toolCalls: (event.toolCalls ?? 0) + prevToolCalls,
                  totalTokens: (event.totalTokens ?? 0) + prevTokens,
                },
                testCaseId,
              });
            },
            id: 'eval-trajectory-complete',
            type: 'onComplete' as const,
            webhook: {
              body: { runId, testCaseId, userId },
              delivery: 'qstash' as const,
              url: webhookUrl,
            },
          },
        ],
        ...(envPrompt && { evalContext: { envPrompt } }),
        initialStepCount: prevSteps,
        maxSteps,
        parentMessageId,
        prompt: '',
        resume: true,
        userInterventionConfig: { approvalMode: 'headless' },
      });

      if (execResult?.operationId) {
        await this.runTopicModel.updateByRunAndTopic(runId, topicId, {
          evalResult: { operationId: execResult.operationId, rubricScores: [] },
        });
      }

      return { status: 'started' as const, topicId };
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Agent execution failed to start';
      console.error(
        `[resume-agent-trajectory] execAgent failed for run=${runId} testCase=${testCaseId}:`,
        error,
      );

      // Record error and finalize the run if all test cases are done
      const { allDone } = await this.recordTrajectoryCompletion({
        runId,
        status: 'error',
        telemetry: { completionReason: 'error', errorMessage },
        testCaseId,
      });

      if (allDone) {
        await AgentEvalRunWorkflow.triggerFinalizeRun({ runId, userId: this.userId });
      }

      return { reason: errorMessage, status: 'error' as const, topicId };
    }
  }

  /**
   * Resume a timed-out thread trajectory (pass@k).
   * Claims the runTopic via CAS (timeout → running) for idempotency, then
   * calls execAgent with resume=true so the runtime continues from parentMessageId.
   */
  async executeResumedThreadTrajectory(params: ResumeThreadTrajectoryPayload) {
    const {
      appContext,
      envPrompt,
      maxSteps,
      parentMessageId,
      runId,
      targetAgentId,
      testCaseId,
      threadId,
      topicId,
    } = params;

    const resumeCheck = await this.canResumeTrajectory({ runId, testCaseId, threadId });
    if (!resumeCheck.canResume) {
      return { reason: resumeCheck.reas
```
