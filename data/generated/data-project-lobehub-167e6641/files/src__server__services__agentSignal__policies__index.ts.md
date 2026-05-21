# 文件：src/server/services/agentSignal/policies/index.ts

## 文件职责
这个文件位于 `src/server/services/agentSignal/policies`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { AgentSignalMiddleware } from '../runtime/middleware';
import type { CreateAnalyzeIntentPolicyOptions } from './analyzeIntent';
import { createAnalyzeIntentPolicy } from './analyzeIntent';
import type {
import type { CreateFeedbackDomainJudgePolicyOptions } from './analyzeIntent/feedbackDomain';
import type { CreateFeedbackSatisfactionJudgePolicyOptions } from './analyzeIntent/feedbackSatisfaction';
import type { CreateReviewNightlyPolicyOptions } from './reviewNightly';
import { createReviewNightlyPolicy } from './reviewNightly';
export * from './actionIdempotency';
export * from './analyzeIntent';
export * from './analyzeIntent/actions';
export * from './analyzeIntent/feedbackAction';
export * from './analyzeIntent/feedbackDomain';
export * from './analyzeIntent/feedbackDomainAgent';
export * from './analyzeIntent/feedbackSatisfaction';
export * from './reviewNightly';
export * from './types';
export interface CreateDefaultAgentSignalPoliciesOptions extends CreateFeedbackDomainJudgePolicyOptions {
export const createDefaultAgentSignalPolicies = (
```

## 主要对外内容
```text
export interface CreateDefaultAgentSignalPoliciesOptions extends CreateFeedbackDomainJudgePolicyOptions {
type DefaultAgentSignalPolicyFactory = (
const DEFAULT_AGENT_SIGNAL_POLICY_FACTORIES: DefaultAgentSignalPolicyFactory[] = [
export const createDefaultAgentSignalPolicies = (
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { AgentSignalMiddleware } from '../runtime/middleware';
import type { CreateAnalyzeIntentPolicyOptions } from './analyzeIntent';
import { createAnalyzeIntentPolicy } from './analyzeIntent';
import type {
  SkillManagementActionHandlerOptions,
  UserMemoryActionHandlerOptions,
} from './analyzeIntent/actions';
import type { CreateFeedbackDomainJudgePolicyOptions } from './analyzeIntent/feedbackDomain';
import type { CreateFeedbackSatisfactionJudgePolicyOptions } from './analyzeIntent/feedbackSatisfaction';
import type { CreateReviewNightlyPolicyOptions } from './reviewNightly';
import { createReviewNightlyPolicy } from './reviewNightly';

export * from './actionIdempotency';
export * from './analyzeIntent';
export * from './analyzeIntent/actions';
export * from './analyzeIntent/feedbackAction';
export * from './analyzeIntent/feedbackDomain';
export * from './analyzeIntent/feedbackDomainAgent';
export * from './analyzeIntent/feedbackSatisfaction';
export * from './reviewNightly';
export * from './types';

export interface CreateDefaultAgentSignalPoliciesOptions extends CreateFeedbackDomainJudgePolicyOptions {
  classifierDiagnostics?: CreateAnalyzeIntentPolicyOptions['classifierDiagnostics'];
  feedbackSatisfactionJudge?: CreateFeedbackSatisfactionJudgePolicyOptions;
  nightlyReview?: CreateReviewNightlyPolicyOptions['nightlyReview'];
  procedure?: CreateAnalyzeIntentPolicyOptions['procedure'];
  selfFeedbackIntent?: CreateReviewNightlyPolicyOptions['selfFeedbackIntent'];
  selfReflection?: CreateReviewNightlyPolicyOptions['selfReflection'];
  skillIntentClassifier?: CreateAnalyzeIntentPolicyOptions['skillIntentClassifier'];
  skillManagement?: SkillManagementActionHandlerOptions;
  userMemory?: UserMemoryActionHandlerOptions;
}

type DefaultAgentSignalPolicyFactory = (
  options: CreateDefaultAgentSignalPoliciesOptions,
) => AgentSignalMiddleware[];

const DEFAULT_AGENT_SIGNAL_POLICY_FACTORIES: DefaultAgentSignalPolicyFactory[] = [
  (options) => [createAnalyzeIntentPolicy(options)],
  (options) =>
    createReviewNightlyPolicy({
      nightlyReview: options.nightlyReview,
      selfFeedbackIntent: options.selfFeedbackIntent,
      selfReflection: options.selfReflection,
    }),
];

/**
 * Creates the default Agent Signal policy stack with optional self-iteration source handlers.
 *
 * Use when:
 * - Runtime creation needs the standard analyze-intent policies
 * - Callers want to opt into nightly self-review, self-reflection, or self-feedback handlers
 *   with explicit handler options
 *
 * Expects:
 * - Optional self-iteration options are complete bundles for their source handlers
 * - Missing optional options mean the corresponding source handler is not installed
 *
 * Returns:
 * - Middleware list that installs analyze-intent policies and enabled source handlers
 */
export const createDefaultAgentSignalPolicies = (
  options: CreateDefaultAgentSignalPoliciesOptions = {},
): AgentSignalMiddleware[] => {
  return DEFAULT_AGENT_SIGNAL_POLICY_FACTORIES.flatMap((createPolicy) => createPolicy(options));
};

```
