# 文件：src/server/services/agentSignal/observability/store.ts

## 文件职责
这个文件位于 `src/server/services/agentSignal/observability`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import type { BaseAction, BaseSignal, ExecutorResult } from '@lobechat/agent-signal';
import {
import { toAgentSignalTraceEvents } from './traceEvents';
import type { AgentSignalObservabilityProjection } from './types';
export const persistAgentSignalObservability = async (
```

## 主要对外内容
```text
const toAttributeRecord = (data: Record<string, unknown>) => {
const resolveSignalDomain = (signalType: string) => {
const resolveSignalOutcome = (signalType: string) => {
const buildTraceAttributes = (input: AgentSignalObservabilityProjection) => ({
const buildChainMetricAttributes = (input: AgentSignalObservabilityProjection) => ({
const buildSourceMetricAttributes = (input: AgentSignalObservabilityProjection) => ({
const buildSignalMetricAttributes = (signal: BaseSignal) => ({
const buildActionMetricAttributes = (action: BaseAction) => ({
const buildActionResultMetricAttributes = (action: BaseAction, result: ExecutorResult) => ({
const buildTransitionMetricAttributes = (signal: BaseAction['signal'], action: BaseAction) => ({
export const persistAgentSignalObservability = async (
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import type { BaseAction, BaseSignal, ExecutorResult } from '@lobechat/agent-signal';
import {
  actionCounter,
  actionDurationHistogram,
  actionResultCounter,
  chainCounter,
  chainDurationHistogram,
  signalActionTransitionCounter,
  signalCounter,
  sourceCounter,
  tracer,
} from '@lobechat/observability-otel/modules/agent-signal';

import { toAgentSignalTraceEvents } from './traceEvents';
import type { AgentSignalObservabilityProjection } from './types';

const toAttributeRecord = (data: Record<string, unknown>) => {
  return Object.fromEntries(
    Object.entries(data).flatMap(([key, value]) => {
      if (value === undefined) return [];
      if (typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string') {
        return [[key, value]];
      }

      return [[key, JSON.stringify(value)]];
    }),
  );
};

const resolveSignalDomain = (signalType: string) => {
  const segments = signalType.split('.');

  return segments.length > 2 ? segments.slice(1, -1).join('.') : signalType;
};

const resolveSignalOutcome = (signalType: string) => {
  return signalType.split('.').at(-1) ?? signalType;
};

const buildTraceAttributes = (input: AgentSignalObservabilityProjection) => ({
  'agent.signal.chain_id': input.record.chainId,
  'agent.signal.final_action_type': input.record.finalActionType ?? 'none',
  'agent.signal.final_status': input.record.finalStatus ?? 'none',
  'agent.signal.scope_key': input.record.scopeKey,
  'agent.signal.source_id': input.record.sourceId,
  'agent.signal.source_type': input.record.sourceType,
  ...(input.record.agentId ? { 'agent.signal.agent_id': input.record.agentId } : undefined),
  ...(input.record.operationId
    ? { 'agent.signal.operation_id': input.record.operationId }
    : undefined),
  ...(input.record.topicId ? { 'agent.signal.topic_id': input.record.topicId } : undefined),
});

const buildChainMetricAttributes = (input: AgentSignalObservabilityProjection) => ({
  'agent.signal.final_status': input.record.finalStatus ?? 'none',
  'agent.signal.source_type': input.record.sourceType,
});

const buildSourceMetricAttributes = (input: AgentSignalObservabilityProjection) => ({
  'agent.signal.source_type': input.record.sourceType,
});

const buildSignalMetricAttributes = (signal: BaseSignal) => ({
  'agent.signal.signal_domain': resolveSignalDomain(signal.signalType),
  'agent.signal.signal_outcome': resolveSignalOutcome(signal.signalType),
  'agent.signal.signal_type': signal.signalType,
  'agent.signal.source_type': signal.source.sourceType,
});

const buildActionMetricAttributes = (action: BaseAction) => ({
  'agent.signal.action_type': action.actionType,
});

const buildActionResultMetricAttributes = (action: BaseAction, result: ExecutorResult) => ({
  'agent.signal.action_type': action.actionType,
  'agent.signal.result_status': result.status,
});

const buildTransitionMetricAttributes = (signal: BaseAction['signal'], action: BaseAction) => ({
  'agent.signal.action_type': action.actionType,
  'agent.signal.signal_domain': resolveSignalDomain(signal.signalType),
  'agent.signal.signal_outcome': resolveSignalOutcome(signal.signalType),
  'agent.signal.signal_type': signal.signalType,
});

/** Persists projected AgentSignal observability artifacts into the default telemetry pipeline. */
export const persistAgentSignalObservability = async (
  input: AgentSignalObservabilityProjection,
): Promise<void> => {
  const traceAttributes = buildTraceAttributes(input);

  await tracer.startActiveSpan(
    'agent_signal.observe',
    { attributes: traceAttributes },
    async (span) => {
      const traceEvents = toAgentSignalTraceEvents({
        actions: input.envelope.actions,
        results: input.envelope.results,
        signals: input.envelope.signals,
        source: input.envelope.source,
      });

      for (const event of traceEvents) {
        span.addEvent(event.type, toAttributeRecord(event.data), event.timestamp);
      }

      span.setAttribute('agent.signal.total_signals', input.record.summary.totalSignals);
      span.setAttribute('agent.signal.total_actions', input.record.summary.totalActions);
      span.setAttribute('agent.signal.total_attempts', input.record.summary.attemptBreakdown.total);
      span.end();
    },
  );

  sourceCounter.add(1, buildSourceMetricAttributes(input));

  for (const signal of input.envelope.signals) {
    signalCounter.add(1, buildSignalMetricAttributes(signal));
  }

  for (const action of input.envelope.actions) {
    actionCounter.add(1, buildActionMetricAttributes(action));
    signalActionTransitionCounter.add(1, buildTransitionMetricAttributes(action.signal, action));
  }

  for (const result of input.envelope.results) {
    const action = input.envelope.actions.find(
      (candidate) => candidate.actionId === result.actionId,
    );

    if (!action) continue;

    actionResultCounter.add(1, buildActionResultMetricAttributes(action, result));

    if (typeof result.attempt.completedAt === 'number') {
      actionDurationHistogram.record(
        result.attempt.completedAt - result.attempt.startedAt,
        buildActionResultMetricAttributes(action, result),
      );
    }
  }

  chainCounter.add(1, buildChainMetricAttributes(input));

  if (typeof input.record.durationMs === 'number') {
    chainDurationHistogram.record(input.record.durationMs, buildChainMetricAttributes(input));
  }
};

```
