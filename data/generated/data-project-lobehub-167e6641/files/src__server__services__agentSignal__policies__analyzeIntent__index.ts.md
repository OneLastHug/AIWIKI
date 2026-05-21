# 文件：src/server/services/agentSignal/policies/analyzeIntent/index.ts

## 文件职责
这个文件位于 `src/server/services/agentSignal/policies/analyzeIntent`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { ToolOutcomeProcedureDeps } from '../../procedure/toolOutcome';
import { createToolOutcomeSourceHandler } from '../../procedure/toolOutcome';
import { defineAgentSignalHandlers } from '../../runtime/middleware';
import type { ClassifierDiagnosticsService } from '../../services/classifierServices';
import type { ProcedureStateService } from '../../services/types';
import type {
import { defineSkillManagementActionHandler, defineUserMemoryActionHandler } from './actions';
import { createFeedbackActionPlannerSignalHandler } from './feedbackAction';
import type { CreateFeedbackDomainJudgePolicyOptions } from './feedbackDomain';
import {
import type { CreateFeedbackSatisfactionJudgePolicyOptions } from './feedbackSatisfaction';
import { createFeedbackSatisfactionJudgeProcessor } from './feedbackSatisfaction';
export interface CreateAnalyzeIntentPolicyOptions {
export const createAnalyzeIntentPolicy = (options: CreateAnalyzeIntentPolicyOptions = {}) => {
export default createAnalyzeIntentPolicy;
```

## 主要对外内容
```text
interface AnalyzeIntentProcedureOptions extends ToolOutcomeProcedureDeps {
export interface CreateAnalyzeIntentPolicyOptions {
export const createAnalyzeIntentPolicy = (options: CreateAnalyzeIntentPolicyOptions = {}) => {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { ToolOutcomeProcedureDeps } from '../../procedure/toolOutcome';
import { createToolOutcomeSourceHandler } from '../../procedure/toolOutcome';
import { defineAgentSignalHandlers } from '../../runtime/middleware';
import type { ClassifierDiagnosticsService } from '../../services/classifierServices';
import type { ProcedureStateService } from '../../services/types';
import type {
  SkillManagementActionHandlerOptions,
  UserMemoryActionHandlerOptions,
} from './actions';
import { defineSkillManagementActionHandler, defineUserMemoryActionHandler } from './actions';
import { createFeedbackActionPlannerSignalHandler } from './feedbackAction';
import type { CreateFeedbackDomainJudgePolicyOptions } from './feedbackDomain';
import {
  createFeedbackDomainJudgeSignalHandler,
  createFeedbackDomainResolver,
  createSkillIntentClassifier,
} from './feedbackDomain';
import type { CreateFeedbackSatisfactionJudgePolicyOptions } from './feedbackSatisfaction';
import { createFeedbackSatisfactionJudgeProcessor } from './feedbackSatisfaction';

interface AnalyzeIntentProcedureOptions extends ToolOutcomeProcedureDeps {
  /** Reads handled procedure markers for feedback-action suppression. */
  markerReader: {
    /** Checks whether an active marker suppresses the current procedure candidate. */
    shouldSuppress: (input: {
      domainKey: string;
      intentClass?: string;
      intentClassCandidates?: string[];
      procedureKey: string;
      scopeKey: string;
    }) => Promise<boolean>;
  };
  /** Composed procedure service bundle for migrated procedure processors. */
  procedureState?: ProcedureStateService;
}

/**
 * Options for composing the analyze-intent agent signal policy.
 */
export interface CreateAnalyzeIntentPolicyOptions {
  /** Optional diagnostics sink for recoverable classifier structured-output failures. */
  classifierDiagnostics?: ClassifierDiagnosticsService;
  /** Optional domain judge dependency used by feedback domain classification. */
  feedbackDomainJudge?: CreateFeedbackDomainJudgePolicyOptions['feedbackDomainJudge'];
  /** Optional satisfaction judge dependencies used by feedback satisfaction classification. */
  feedbackSatisfactionJudge?: CreateFeedbackSatisfactionJudgePolicyOptions;
  /** Optional procedure dependencies shared by tool-outcome projection and action planning. */
  procedure?: AnalyzeIntentProcedureOptions;
  /** Optional skill intent classifier dependencies used after skill-domain routing. */
  skillIntentClassifier?: CreateFeedbackDomainJudgePolicyOptions['skillIntentClassifier'];
  /** Optional skill-management action handler dependencies. */
  skillManagement?: SkillManagementActionHandlerOptions;
  /** Optional user-memory action handler dependencies. */
  userMemory?: UserMemoryActionHandlerOptions;
}

export const createAnalyzeIntentPolicy = (options: CreateAnalyzeIntentPolicyOptions = {}) => {
  const feedbackDomainResolver = createFeedbackDomainResolver({
    feedbackDomainJudge: options.feedbackDomainJudge,
  });
  const skillIntentClassifier = createSkillIntentClassifier({
    skillIntentClassifier: options.skillIntentClassifier,
  });

  return defineAgentSignalHandlers([
    ...(options.procedure ? [createToolOutcomeSourceHandler(options.procedure)] : []),
    createFeedbackSatisfactionJudgeProcessor({
      ...options.feedbackSatisfactionJudge,
      classifierDiagnostics:
        options.feedbackSatisfactionJudge?.classifierDiagnostics ?? options.classifierDiagnostics,
    }),
    createFeedbackDomainJudgeSignalHandler({
      classifierDiagnostics: options.classifierDiagnostics,
      resolveDomains: feedbackDomainResolver,
      skillIntentClassifier,
    }),
    createFeedbackActionPlannerSignalHandler({
      markerReader: options.procedure?.markerReader,
      procedure: options.procedure,
    }),
    ...(options.skillManagement
      ? [
          defineSkillManagementActionHandler({
            ...options.skillManagement,
            procedureState:
              options.skillManagement.procedureState ?? options.procedure?.procedureState,
          }),
        ]
      : []),
    ...(options.userMemory ? [defineUserMemoryActionHandler(options.userMemory)] : []),
  ]);
};

export default createAnalyzeIntentPolicy;

```
