# 文件：src/server/services/agentSignal/store/adapters/redis/policyStateStore.ts

## 文件职责
这个文件位于 `src/server/services/agentSignal/store/adapters/redis`。下面根据源码片段、导入导出和命名推断它在项目中的职责。

## 引入/导出的依赖线索
```text
import { AGENT_SIGNAL_KEYS } from '../../../constants';
import type { AgentSignalPolicyStateStore } from '../../types';
import { readHash, writeHash } from './shared';
export const readPolicyState = async (policyId: string, scopeKey: string) => {
export const writePolicyState = async (
export const redisPolicyStateStore: AgentSignalPolicyStateStore = {
```

## 主要对外内容
```text
export const readPolicyState = async (policyId: string, scopeKey: string) => {
export const writePolicyState = async (
export const redisPolicyStateStore: AgentSignalPolicyStateStore = {
```

## 小白怎么读
1. 先看文件顶部 import，判断它依赖 UI、服务、数据库、状态还是配置。
2. 再看 export 的对象，判断别人如何使用它。
3. 最后看核心实现，不要一开始陷入每一行细节。

## 源码节选（保留原始代码）
```text
import { AGENT_SIGNAL_KEYS } from '../../../constants';
import type { AgentSignalPolicyStateStore } from '../../types';
import { readHash, writeHash } from './shared';

/** Reads one persisted policy-state snapshot for a scope. */
export const readPolicyState = async (policyId: string, scopeKey: string) => {
  return readHash(AGENT_SIGNAL_KEYS.policy(policyId, scopeKey));
};

/** Writes one persisted policy-state snapshot for a scope. */
export const writePolicyState = async (
  policyId: string,
  scopeKey: string,
  data: Record<string, string>,
  ttlSeconds: number,
) => {
  await writeHash(AGENT_SIGNAL_KEYS.policy(policyId, scopeKey), data, ttlSeconds);
};

/** Redis-backed policy-state store used by AgentSignal policies. */
export const redisPolicyStateStore: AgentSignalPolicyStateStore = {
  readPolicyState,
  writePolicyState,
};

```
